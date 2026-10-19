"""Line to the CUL (culfw): USB serial (nanoCUL) or TCP (a-culfw on a CUN / flashed MAX! Cube)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
import time
from collections.abc import Awaitable, Callable

_LOGGER = logging.getLogger(__name__)

OpenConnection = Callable[[str], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]


async def open_serial(port: str):
    import serial_asyncio_fast  # noqa: PLC0415

    return await serial_asyncio_fast.open_serial_connection(url=port, baudrate=38400)


DEFAULT_TCP_PORT = 2323
TCP_CONNECT_TIMEOUT = 10.0
# Keepalive: a vanished peer (Cube unplugged, WLAN gone) is noticed after ~90 s
# instead of waiting for the watchdog; TCP_USER_TIMEOUT (ms) bounds unacknowledged
# writes to 120 s. Options missing on the platform are skipped.
_KEEPALIVE = (("TCP_KEEPIDLE", 60), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3), ("TCP_USER_TIMEOUT", 120000))


def set_keepalive(sock) -> None:
    """Enable keepalive on a TCP socket; each option on its own, failures only logged."""
    options = [("SO_KEEPALIVE", socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    for name, value in _KEEPALIVE:
        option = getattr(socket, name, None)
        if option is not None:
            options.append((name, socket.IPPROTO_TCP, option, value))
    for name, level, option, value in options:
        try:
            sock.setsockopt(level, option, value)
        except OSError as err:
            _LOGGER.debug("could not set %s on the CUL socket: %s", name, err)


async def open_tcp(host: str, port: int, *, connect_timeout: float = TCP_CONNECT_TIMEOUT):
    """Open a TCP connection to culfw's text port; same (reader, writer) as open_serial."""
    reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), connect_timeout)
    sock = writer.get_extra_info("socket")
    if sock is not None:
        set_keepalive(sock)
    return reader, writer


def tcp_opener(host: str, port: int, *, connect_timeout: float = TCP_CONNECT_TIMEOUT) -> OpenConnection:
    """An open_connection for CulTransport that ignores the target label and dials host:port.

    A reopen (watchdog, fast reopen) closes and redials the TCP connection. Unlike
    DTR on a USB nanoCUL this does not reset the radio module itself.
    """

    async def _open(_target: str):
        return await open_tcp(host, port, connect_timeout=connect_timeout)

    return _open


class CulTransport:
    """Owns the CUL connection: init, reading, reconnect, deaf-stick watchdog.

    `port` is the target handed to `open_connection` (serial path, or a label like
    "host:port" for tcp_opener).
    """

    def __init__(
        self,
        port: str,
        address: int,
        *,
        on_frame: Callable[[str], None],
        on_lovf: Callable[[], None],
        on_connection: Callable[[bool], None],
        on_problem: Callable[[str], None],
        open_connection: OpenConnection = open_serial,
        clock: Callable[[], float] = time.monotonic,
        reconnect_delay: float = 30.0,
        silence_timeout: float = 600.0,
        problem_after: float = 900.0,
        version_timeout: float = 5.0,
        check_interval: float = 30.0,
    ) -> None:
        self._port = port
        self._address = address
        self._on_frame = on_frame
        self._on_lovf = on_lovf
        self._on_connection = on_connection
        self._on_problem = on_problem
        self._open = open_connection
        self._clock = clock
        self._reconnect_delay = reconnect_delay
        self._silence_timeout = silence_timeout
        self._problem_after = problem_after
        self._version_timeout = version_timeout
        self._check_interval = check_interval
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._connected_event = asyncio.Event()
        self._version: str | None = None
        self._task: asyncio.Task | None = None
        self._watchdog: asyncio.Task | None = None
        self._last_tx: float | None = None
        self._last_rx: float | None = None
        # Last received "Z" frame; unlike _last_rx not reset on reconnect.
        self._last_frame_rx: float | None = None
        self._deaf_resets = 0
        self._force_reopen = False
        # One fast reopen per quiet episode; cleared by the next received frame.
        self._fast_reopen_done = False
        self._down_since: float | None = None
        self._port_lost_reported = False
        self._stick_deaf_reported = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def version(self) -> str | None:
        return self._version

    @property
    def clock(self) -> Callable[[], float]:
        """The monotonic clock behind last_frame_rx."""
        return self._clock

    @property
    def last_frame_rx(self) -> float | None:
        """Clock time of the last received "Z" frame (None: none yet)."""
        return self._last_frame_rx

    def request_reopen(self) -> None:
        """Reopen the port now (stick deaf after sending), at most once per quiet episode.

        Unlike a watchdog reopen it never counts toward stick_deaf: one unreachable
        device must not raise the repair issue. Further silence is the watchdog's job.
        """
        if not self._connected:
            return
        if self._fast_reopen_done:
            _LOGGER.debug("fast reopen already done in this quiet episode, left to the watchdog")
            return
        self._fast_reopen_done = True
        self._reopen()

    async def wait_connected(self) -> None:
        """Return once the stick is connected and initialised."""
        await self._connected_event.wait()

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())
        self._watchdog = asyncio.create_task(self._watch())

    async def stop(self) -> None:
        for task in (self._watchdog, self._task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._close_writer()
        self._set_connected(False)

    async def write_line(self, line: str) -> None:
        if not self._connected or self._writer is None:
            raise ConnectionError("CUL not connected")
        try:
            self._writer.write((line + "\n").encode())
            await self._writer.drain()
        except OSError as err:
            raise ConnectionError(str(err)) from err
        if line.startswith(("Zs", "Zf")):
            self._last_tx = self._clock()

    async def _run(self) -> None:
        while True:
            try:
                await self._connect()
                await self._read_loop()
            except asyncio.CancelledError:
                raise
            except (OSError, ConnectionError, asyncio.IncompleteReadError, TimeoutError) as err:
                _LOGGER.debug("CUL connection lost: %s", err)
            except Exception:
                _LOGGER.exception("CUL transport error")
            self._close_writer()
            self._set_connected(False)
            if self._force_reopen:
                self._force_reopen = False
                continue
            self._check_port_lost()
            await asyncio.sleep(self._reconnect_delay)

    async def _connect(self) -> None:
        self._reader, self._writer = await self._open(self._port)
        self._version = await self._handshake()
        for cmd in ("X21", "Zr", f"Za{self._address:06X}"):
            self._writer.write((cmd + "\n").encode())
            await self._writer.drain()
        self._last_tx = None
        self._last_rx = None
        self._set_connected(True)

    async def _handshake(self) -> str:
        assert self._reader is not None and self._writer is not None
        loop = asyncio.get_running_loop()
        for _ in range(3):
            self._writer.write(b"V\n")
            await self._writer.drain()
            # Other lines (frames: over TCP culfw keeps receiving between sessions)
            # are skipped until the answer or the timeout.
            deadline = loop.time() + self._version_timeout
            while (remaining := deadline - loop.time()) > 0:
                try:
                    raw = await asyncio.wait_for(self._reader.readline(), remaining)
                except TimeoutError:
                    break
                if not raw:
                    raise ConnectionError("EOF during handshake")
                text = raw.decode(errors="replace").strip()
                if text.startswith("V "):
                    return text
        raise ConnectionError("no culfw version answer")

    async def _read_loop(self) -> None:
        assert self._reader is not None
        while True:
            raw = await self._reader.readline()
            if not raw:
                raise ConnectionError("EOF")
            text = raw.decode(errors="replace").strip()
            if not text:
                continue
            if text.startswith("Z"):
                self._last_rx = self._clock()
                self._last_frame_rx = self._last_rx
                self._deaf_resets = 0
                self._fast_reopen_done = False
                self._stick_deaf_reported = False
                self._emit(self._on_frame, text)
            elif text.startswith("LOVF"):
                _LOGGER.warning("culfw refused to send (LOVF)")
                self._emit(self._on_lovf)
            else:
                _LOGGER.debug("culfw: %s", text)

    async def _watch(self) -> None:
        while True:
            await asyncio.sleep(self._check_interval)
            try:
                self._watch_once()
            except Exception:
                _LOGGER.exception("CUL watchdog error")

    def _watch_once(self) -> None:
        if self._connected and self._is_deaf():
            _LOGGER.warning("CUL sent but received nothing, reopening port")
            self._reopen_deaf()
        if not self._connected:
            self._check_port_lost()

    def _reopen_deaf(self) -> None:
        self._deaf_resets += 1
        if self._deaf_resets >= 2 and not self._stick_deaf_reported:
            self._stick_deaf_reported = True
            self._emit(self._on_problem, "stick_deaf")
        self._reopen()

    def _reopen(self) -> None:
        self._force_reopen = True
        self._last_tx = None
        self._close_writer()
        # Senders wait for the reconnect instead of burning attempts on a closed port.
        self._set_connected(False)

    def _is_deaf(self) -> bool:
        if self._last_tx is None:
            return False
        if self._last_rx is not None and self._last_rx > self._last_tx:
            return False
        return self._clock() - self._last_tx >= self._silence_timeout

    def _check_port_lost(self) -> None:
        if self._down_since is None or self._port_lost_reported:
            return
        if self._clock() - self._down_since >= self._problem_after:
            self._port_lost_reported = True
            self._emit(self._on_problem, "port_lost")

    def _emit(self, fn: Callable[..., None], *args: object) -> None:
        try:
            fn(*args)
        except Exception:
            _LOGGER.exception("CUL callback failed")

    def _close_writer(self) -> None:
        if self._writer is not None:
            with contextlib.suppress(Exception):
                self._writer.close()
        self._writer = None

    def _set_connected(self, value: bool) -> None:
        if value:
            self._down_since = None
            self._port_lost_reported = False
        elif self._down_since is None:
            self._down_since = self._clock()
        if value:
            self._connected_event.set()
        else:
            self._connected_event.clear()
        if value != self._connected:
            self._connected = value
            self._emit(self._on_connection, value)
