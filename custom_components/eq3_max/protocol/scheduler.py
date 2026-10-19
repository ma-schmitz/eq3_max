"""Radio scheduler: one telegram in flight, ack by (src, counter), airtime."""

from __future__ import annotations

import asyncio
import itertools
import logging
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum

from .messages import Frame, encode_frame

_LOGGER = logging.getLogger(__name__)

PRIO_REPLY = 0
PRIO_COMMAND = 1
PREAMBLE_S = 1.0
PER_BYTE_S = 0.008
BUDGET_S = 36.0
WINDOW_S = 3600.0


def airtime(frame: Frame, fast: bool = False) -> float:
    """Airtime as culfw accounts it: 1 s preamble (not for fast sends) + 8 ms per byte."""
    return (0.0 if fast else PREAMBLE_S) + PER_BYTE_S * (len(encode_frame(frame)) // 2)


class Outcome(Enum):
    """How a command finished (set by the scheduler before on_done)."""

    ACKED = "acked"
    NAK = "nak"
    NO_ACK = "no_ack"  # sent, no ack after all attempts
    SENT = "sent"  # sent, no ack expected
    NOT_SENT = "not_sent"  # the stick did not take the frame (last attempt)
    EXPIRED = "expired"  # deadline passed or stale before sending
    ERROR = "error"  # encoding or unexpected failure


@dataclass
class Command:
    dst: int
    build: Callable[[int], Frame]
    priority: int = PRIO_COMMAND
    key: str | None = None
    expects_ack: bool = True
    on_done: Callable[[bool], None] | None = None
    # Scheduler clock time after which the command is given up without sending.
    deadline: float | None = None
    # True once the command must not go on air any more (e.g. its end time passed).
    is_stale: Callable[[], bool] | None = None
    # An unacknowledged attempt with no reception since may mean a deaf stick
    # (set commands and the reset; not time replies or pongs).
    deaf_probe: bool = False
    # Device is awake right now (e.g. a window contact just sent): "Zf" without the
    # 1 s wake-up preamble instead of "Zs".
    fast: bool = False
    # Per-command limits; None uses the scheduler's ack timeout / retries.
    retries: int | None = None
    ack_timeout: float | None = None
    seq: int = field(default=0, compare=False)
    sent: int = field(default=0, compare=False)
    # Scheduler clock time of the first attempt that went to the stick.
    first_sent_at: float | None = field(default=None, compare=False)
    outcome: Outcome | None = field(default=None, compare=False)


class RadioScheduler:
    def __init__(
        self,
        send_line: Callable[[str], Awaitable[None]],
        *,
        ack_timeout: float = 3.0,
        retries: int = 3,
        lovf_delay: float = 1.0,
        brake: bool = False,
        clock: Callable[[], float] = time.monotonic,
        budget_poll: float = 5.0,
        on_change: Callable[[], None] | None = None,
        wait_ready: Callable[[], Awaitable[None]] | None = None,
        on_finished: Callable[[Command], None] | None = None,
        next_counter: Callable[[], int] | None = None,
    ) -> None:
        self._send_line = send_line
        self._ack_timeout = ack_timeout
        self._retries = retries
        self._lovf_delay = lovf_delay
        self._brake = brake
        self._clock = clock
        self._budget_poll = budget_poll
        self._on_change = on_change
        self._wait_ready = wait_ready
        self._on_finished = on_finished
        self._queue: list[Command] = []
        self._wake = asyncio.Event()
        self._seq = itertools.count()
        self._counter = 0
        # Several modules share one central address: one counter for all of them, so an
        # ACK can never match commands of two modules at once.
        self._next_counter = next_counter
        self._inflight: tuple[int, int] | None = None
        self._ack_event = asyncio.Event()
        self._acked: bool | None = None
        self._lovf = False
        self._airtime: deque[tuple[float, float]] = deque()

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    @property
    def airtime_last_hour(self) -> float:
        cutoff = self._clock() - WINDOW_S
        while self._airtime and self._airtime[0][0] < cutoff:
            self._airtime.popleft()
        return sum(cost for _, cost in self._airtime)

    def submit(self, cmd: Command) -> None:
        """Queue a command. A newer command with the same key replaces the waiting one;
        the replaced command gets no on_done call (intentional)."""
        if cmd.key is not None:
            self._queue = [c for c in self._queue if c.key != cmd.key]
        cmd.seq = next(self._seq)
        self._queue.append(cmd)
        self._wake.set()
        self._changed()

    def now(self) -> float:
        """Current time on the scheduler clock (the reference for Command.deadline)."""
        return self._clock()

    def cancel_key(self, key: str) -> int:
        """Drop waiting commands with this key (no on_done call); returns how many."""
        before = len(self._queue)
        self._queue = [c for c in self._queue if c.key != key]
        dropped = before - len(self._queue)
        if dropped:
            self._changed()
        return dropped

    def take_dst(self, dst: int) -> list[Command]:
        """Remove and return the waiting commands for this device (no on_done call):
        they move to another radio module. A command on air stays."""
        taken = [c for c in self._queue if c.dst == dst]
        if taken:
            self._queue = [c for c in self._queue if c.dst != dst]
            self._changed()
        return taken

    def _expired(self, cmd: Command) -> bool:
        if cmd.deadline is not None and self._clock() >= cmd.deadline:
            return True
        if cmd.is_stale is not None:
            try:
                return bool(cmd.is_stale())
            except Exception:
                _LOGGER.exception("is_stale check failed")
                return True
        return False

    def on_ack(self, src: int, counter: int, ok: bool) -> bool:
        if self._inflight != (src, counter):
            return False
        if self._acked is None:
            self._acked = ok
        self._ack_event.set()
        return True

    def on_lovf(self) -> None:
        if self._inflight is not None:
            self._lovf = True
            self._ack_event.set()

    async def run(self) -> None:
        while True:
            cmd = await self._next()
            try:
                ok = await self._process(cmd)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("command for %06X failed unexpectedly", cmd.dst)
                cmd.outcome = Outcome.ERROR
                ok = False
            self._done(cmd, ok)

    async def _next(self) -> Command:
        while not self._queue:
            self._wake.clear()
            await self._wake.wait()
        cmd = min(self._queue, key=lambda c: (c.priority, c.seq))
        self._queue.remove(cmd)
        self._changed()
        return cmd

    async def _process(self, cmd: Command) -> bool:
        self._counter = self._next_counter() if self._next_counter is not None else (self._counter + 1) & 0xFF
        try:
            frame = cmd.build(self._counter)
            line = ("Zf" if cmd.fast else "Zs") + encode_frame(frame)
            cost = airtime(frame, cmd.fast)
        except Exception:
            _LOGGER.exception("cannot encode command for %06X", cmd.dst)
            cmd.outcome = Outcome.ERROR
            return False
        attempts = 0
        retries = self._retries if cmd.retries is None else cmd.retries
        ack_timeout = self._ack_timeout if cmd.ack_timeout is None else cmd.ack_timeout
        self._acked = None
        self._lovf = False
        self._ack_event.clear()
        try:
            while True:
                if self._wait_ready is not None:
                    # Attempts only count while the stick can actually send.
                    await self._wait_ready()
                if self._brake:
                    await self._wait_budget(cost)
                if self._acked is not None:
                    return self._ack_result(cmd)
                if self._expired(cmd):
                    _LOGGER.debug("command for %06X expired before sending", cmd.dst)
                    cmd.outcome = Outcome.EXPIRED
                    return False
                self._ack_event.clear()
                self._lovf = False
                self._inflight = (frame.dst, frame.counter) if cmd.expects_ack else None
                try:
                    await self._send_line(line)
                except ConnectionError as err:
                    _LOGGER.debug("send failed: %s", err)
                    attempts += 1
                    if attempts > retries:
                        cmd.outcome = Outcome.NOT_SENT
                        return False
                    await asyncio.sleep(ack_timeout)
                    continue
                if cmd.first_sent_at is None:
                    cmd.first_sent_at = self._clock()
                cmd.sent += 1
                self._airtime.append((self._clock(), cost))
                self._changed()
                if not cmd.expects_ack:
                    cmd.outcome = Outcome.SENT
                    return True
                try:
                    await asyncio.wait_for(self._ack_event.wait(), ack_timeout)
                except TimeoutError:
                    if self._acked is not None:
                        return self._ack_result(cmd)
                    attempts += 1
                    if attempts > retries:
                        _LOGGER.warning("no ack from %06X for counter %02X", frame.dst, frame.counter)
                        cmd.outcome = Outcome.NO_ACK
                        return False
                    continue
                if self._acked is not None:
                    return self._ack_result(cmd)
                # LOVF: wait, then resend the same frame without counting an attempt.
                # An ack arriving during this delay is caught by the check at the loop top.
                await asyncio.sleep(self._lovf_delay)
        finally:
            self._inflight = None

    def _ack_result(self, cmd: Command) -> bool:
        ok = bool(self._acked)
        cmd.outcome = Outcome.ACKED if ok else Outcome.NAK
        return ok

    async def _wait_budget(self, cost: float) -> None:
        while self.airtime_last_hour + cost > BUDGET_S:
            await asyncio.sleep(self._budget_poll)

    def _done(self, cmd: Command, ok: bool) -> None:
        if cmd.on_done is not None:
            try:
                cmd.on_done(ok)
            except Exception:
                _LOGGER.exception("on_done callback failed")
        if self._on_finished is not None:
            try:
                self._on_finished(cmd)
            except Exception:
                _LOGGER.exception("on_finished callback failed")

    def _changed(self) -> None:
        if self._on_change is not None:
            try:
                self._on_change()
            except Exception:
                _LOGGER.exception("on_change callback failed")
