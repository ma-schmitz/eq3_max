"""CulTransport over TCP (a-culfw on a flashed MAX! Cube / CUN) against a local fake CUL."""

import asyncio
import socket

import pytest

from custom_components.eq3_max.protocol.transport import CulTransport, open_tcp, tcp_opener

from .fakes import until

ADDR = 0xC0FFEE
# Real sockets on 127.0.0.1 (the HA test plugin blocks sockets by default).
pytestmark = pytest.mark.usefixtures("socket_enabled")

VERSION = "V 1.26.08 a-culfw Build: private build (unknown) CUBE (F-Band: 868MHz)"


class FakeTcpCul:
    """Local asyncio TCP server speaking the culfw text protocol (CRLF like a-culfw)."""

    def __init__(self, *, answer_version: bool = True, preamble: list[str] | None = None) -> None:
        self.answer_version = answer_version
        self.preamble = preamble or []
        self.connections = 0
        self.received: list[list[str]] = []
        self.writers: list[asyncio.StreamWriter] = []
        self.server: asyncio.Server | None = None
        self.port = 0

    async def start(self, port: int = 0) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", port)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            for writer in self.writers:
                writer.close()
            await self.server.wait_closed()
            self.server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        lines: list[str] = []
        self.received.append(lines)
        self.writers.append(writer)
        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                text = raw.decode().strip()
                lines.append(text)
                if text == "V" and self.answer_version:
                    for extra in self.preamble:
                        writer.write((extra + "\r\n").encode())
                    writer.write((VERSION + "\r\n").encode())
                    await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            writer.close()

    async def send(self, line: str) -> None:
        writer = self.writers[-1]
        writer.write((line + "\r\n").encode())
        await writer.drain()

    def drop_client(self) -> None:
        self.writers[-1].close()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def make(host: str, port: int, **kw):
    events = {"frames": [], "conn": [], "problems": []}
    t = CulTransport(
        f"{host}:{port}",
        ADDR,
        on_frame=events["frames"].append,
        on_lovf=lambda: None,
        on_connection=events["conn"].append,
        on_problem=events["problems"].append,
        open_connection=kw.pop("open_connection", tcp_opener(host, port)),
        **kw,
    )
    return t, events


async def test_open_tcp_returns_streams_with_keepalive():
    cul = FakeTcpCul()
    await cul.start()
    try:
        reader, writer = await open_tcp("127.0.0.1", cul.port)
        sock = writer.get_extra_info("socket")
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
        writer.write(b"V\n")
        await writer.drain()
        assert (await reader.readline()).decode().strip() == VERSION
        writer.close()
    finally:
        await cul.stop()


async def test_open_tcp_connection_refused_raises_oserror():
    with pytest.raises(OSError):
        await open_tcp("127.0.0.1", free_port())


async def test_open_tcp_connect_timeout():
    async def hang(*_a, **_kw):
        await asyncio.sleep(10)

    from unittest.mock import patch

    with patch("asyncio.open_connection", hang), pytest.raises(TimeoutError):
        await open_tcp("192.0.2.1", 2323, connect_timeout=0.01)


async def test_tcp_init_sequence_and_frames_with_crlf():
    cul = FakeTcpCul()
    await cul.start()
    t, ev = make("127.0.0.1", cul.port)
    try:
        await t.start()
        await until(lambda: t.connected)
        assert t.version == VERSION
        await until(lambda: cul.received[0][-1:] == ["ZaC0FFEE"])
        assert cul.received[0] == ["V", "X21", "Zr", "ZaC0FFEE"]
        await cul.send("Z0EF20202A1B005C0FFEE0001193009")
        await until(lambda: ev["frames"] == ["Z0EF20202A1B005C0FFEE0001193009"])
        await t.write_line("Zs0B010040C0FFEEA1B005006A")
        await until(lambda: cul.received[0][-1] == "Zs0B010040C0FFEEA1B005006A")
    finally:
        await t.stop()
        await cul.stop()


async def test_tcp_frames_before_version_answer_are_skipped():
    # culfw keeps X21 across TCP sessions: frames may arrive before the V answer.
    cul = FakeTcpCul(preamble=["Z0B0100600A1B005C0FFEE00", "Z0B0200600A1B005C0FFEE00"])
    await cul.start()
    t, _ = make("127.0.0.1", cul.port, version_timeout=1.0)
    try:
        await t.start()
        await until(lambda: t.connected)
        assert t.version == VERSION
        assert cul.received[0][0] == "V"
        assert cul.received[0].count("V") == 1
    finally:
        await t.stop()
        await cul.stop()


async def test_tcp_connection_refused_retries_until_server_is_up():
    port = free_port()
    attempts = []
    inner = tcp_opener("127.0.0.1", port)

    async def counting(target):
        attempts.append(target)
        return await inner(target)

    t, ev = make("127.0.0.1", port, open_connection=counting, reconnect_delay=0.01)
    cul = FakeTcpCul()
    try:
        await t.start()
        await until(lambda: len(attempts) >= 2)
        assert not t.connected
        await cul.start(port)
        await until(lambda: t.connected)
        assert attempts[0] == f"127.0.0.1:{port}"
        assert ev["conn"] == [True]
    finally:
        await t.stop()
        await cul.stop()


async def test_tcp_server_side_close_reconnects():
    cul = FakeTcpCul()
    await cul.start()
    t, ev = make("127.0.0.1", cul.port, reconnect_delay=0.01)
    try:
        await t.start()
        await until(lambda: t.connected)
        cul.drop_client()
        await until(lambda: cul.connections == 2 and t.connected)
        await until(lambda: cul.received[1][-1:] == ["ZaC0FFEE"])
        assert cul.received[1] == ["V", "X21", "Zr", "ZaC0FFEE"]
        assert ev["conn"] == [True, False, True]
        await cul.send("Z0EF20202A1B005C0FFEE0001193009")
        await until(lambda: len(ev["frames"]) == 1)
    finally:
        await t.stop()
        await cul.stop()


async def test_tcp_reopen_reconnects_immediately():
    cul = FakeTcpCul()
    await cul.start()
    # A long reconnect delay proves the reopen does not wait for it.
    t, _ = make("127.0.0.1", cul.port, reconnect_delay=60.0)
    try:
        await t.start()
        await until(lambda: t.connected)
        t.request_reopen()
        await until(lambda: cul.connections == 2 and t.connected)
    finally:
        await t.stop()
        await cul.stop()


class _RecordingSocket:
    def __init__(self, fail: set[int] | None = None) -> None:
        self.fail = fail or set()
        self.set: dict[tuple[int, int], int] = {}

    def setsockopt(self, level, option, value):
        if option in self.fail:
            raise OSError("not supported")
        self.set[(level, option)] = value


def test_keepalive_options_each_set_independently(caplog):
    import logging

    from custom_components.eq3_max.protocol.transport import set_keepalive

    sock = _RecordingSocket(fail={socket.TCP_KEEPIDLE})
    with caplog.at_level(logging.DEBUG, logger="custom_components.eq3_max.protocol.transport"):
        set_keepalive(sock)
    assert sock.set[(socket.SOL_SOCKET, socket.SO_KEEPALIVE)] == 1
    assert (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) not in sock.set
    # A failing option does not stop the others.
    assert sock.set[(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL)] == 10
    assert sock.set[(socket.IPPROTO_TCP, socket.TCP_KEEPCNT)] == 3
    assert sock.set[(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT)] == 120000
    assert "TCP_KEEPIDLE" in caplog.text


async def test_open_tcp_sets_user_timeout_and_keepidle():
    cul = FakeTcpCul()
    await cul.start()
    try:
        _reader, writer = await open_tcp("127.0.0.1", cul.port)
        sock = writer.get_extra_info("socket")
        assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE) == 60
        assert sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_USER_TIMEOUT) == 120000
        writer.close()
    finally:
        await cul.stop()
