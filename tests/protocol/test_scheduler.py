import asyncio

import pytest

from custom_components.eq3_max.protocol.messages import Frame, FrameError, MsgType, encode_frame
from custom_components.eq3_max.protocol.scheduler import (
    BUDGET_S,
    PRIO_BACKGROUND,
    PRIO_REPLY,
    Command,
    Outcome,
    RadioScheduler,
    airtime,
)

from .fakes import FakeClock, until

DEV = 0xA1B005


def frame(counter, payload=b"\x6a", dst=DEV):
    return Frame(counter, 0, MsgType.SET_TEMPERATURE, 0xC0FFEE, dst, 0, payload)


class Sender:
    def __init__(self):
        self.lines = []
        self.fail = False

    async def __call__(self, line):
        if self.fail:
            raise ConnectionError("unplugged")
        self.lines.append(line)


@pytest.fixture
async def setup():
    sender = Sender()
    clock = FakeClock()
    sched = RadioScheduler(sender, ack_timeout=0.05, lovf_delay=0.01, clock=clock, budget_poll=0.01)
    task = asyncio.create_task(sched.run())
    yield sched, sender, clock
    task.cancel()


def test_airtime_is_preamble_plus_bytes():
    assert airtime(frame(1)) == pytest.approx(1.0 + 12 * 0.008)


async def test_sends_with_zs_and_acks_by_src_and_counter(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    assert sender.lines[0] == "Zs" + encode_frame(frame(1))
    assert sched.on_ack(0x999999, 1, True) is False
    assert sched.on_ack(DEV, 2, True) is False
    assert sched.on_ack(DEV, 1, True) is True
    await until(lambda: done == [True])


async def test_retries_three_times_then_fails(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: done == [False], timeout=1.0)
    assert len(sender.lines) == 4
    assert len(set(sender.lines)) == 1


async def test_nak_fails_without_retry(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.on_ack(DEV, 1, False)
    await until(lambda: done == [False])
    assert len(sender.lines) == 1


async def test_only_one_in_flight_and_replies_first(setup):
    sched, sender, _ = setup
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x01")))
    await until(lambda: len(sender.lines) == 1)
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x02")))
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x03"), priority=PRIO_REPLY))
    await asyncio.sleep(0.01)
    assert len(sender.lines) == 1
    sched.on_ack(DEV, 1, True)
    await until(lambda: len(sender.lines) == 2)
    assert sender.lines[1].endswith("03")


async def test_newest_command_with_same_key_wins(setup):
    sched, sender, _ = setup
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x01")))
    await until(lambda: len(sender.lines) == 1)
    superseded = []
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x10"), key="set", on_done=superseded.append))
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x20"), key="set"))
    assert sched.queue_length == 2 - 1
    sched.on_ack(DEV, 1, True)
    await until(lambda: len(sender.lines) == 2)
    assert sender.lines[1].endswith("20")
    assert superseded == []


async def test_lovf_resends_same_frame_without_counting_attempt(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.on_lovf()
    await until(lambda: len(sender.lines) == 2)
    sched.on_ack(DEV, 1, True)
    await until(lambda: done == [True])


async def test_send_failure_counts_as_attempt_and_queue_continues(setup):
    sched, sender, _ = setup
    done = []
    sender.fail = True
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: done == [False], timeout=1.0)
    sender.fail = False
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.on_ack(DEV, 2, True)
    await until(lambda: done == [False, True])


async def test_broadcast_does_not_wait_for_ack(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=0, build=lambda c: frame(c, dst=0), expects_ack=False, on_done=done.append))
    await until(lambda: done == [True])


async def test_counter_wraps_after_255(setup):
    sched, sender, _ = setup
    sched._counter = 255
    sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
    await until(lambda: len(sender.lines) == 1)
    assert sender.lines[0][4:6] == "00"


async def test_airtime_window_sums_last_hour(setup):
    sched, sender, clock = setup
    sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
    await until(lambda: len(sender.lines) == 1)
    assert sched.airtime_last_hour == pytest.approx(airtime(frame(1)))
    clock.t += 3601
    assert sched.airtime_last_hour == 0.0


async def test_brake_waits_for_budget():
    sender = Sender()
    clock = FakeClock()
    sched = RadioScheduler(sender, ack_timeout=0.05, clock=clock, brake=True, budget_poll=0.01)
    sched._airtime.append((clock.t, 35.5))
    task = asyncio.create_task(sched.run())
    sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
    await asyncio.sleep(0.05)
    assert sender.lines == []
    clock.t += 3601
    await until(lambda: len(sender.lines) == 1)
    task.cancel()


def broken(counter):
    raise FrameError("temporary mode has no build")


async def test_on_done_exception_does_not_stop_queue(setup):
    sched, sender, _ = setup

    def boom(ok):
        raise RuntimeError("callback")

    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x01"), expects_ack=False, on_done=boom))
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x02"), expects_ack=False))
    await until(lambda: len(sender.lines) == 2)
    assert sender.lines[1].endswith("02")


async def test_on_change_exception_does_not_break_submit_or_queue():
    sender = Sender()
    clock = FakeClock()

    def boom():
        raise RuntimeError("listener")

    sched = RadioScheduler(sender, ack_timeout=0.05, clock=clock, budget_poll=0.01, on_change=boom)
    task = asyncio.create_task(sched.run())
    try:
        sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
        sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x02"), expects_ack=False))
        await until(lambda: len(sender.lines) == 2)
    finally:
        task.cancel()


async def test_build_error_fails_only_that_command(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=broken, on_done=done.append))
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x02"), expects_ack=False))
    await until(lambda: len(sender.lines) == 1)
    assert done == [False]
    assert sender.lines[0].endswith("02")


async def test_ack_during_lovf_delay_finishes_without_resend():
    sender = Sender()
    clock = FakeClock()
    sched = RadioScheduler(sender, ack_timeout=0.05, lovf_delay=0.2, clock=clock, budget_poll=0.01)
    task = asyncio.create_task(sched.run())
    done = []
    try:
        sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
        await until(lambda: len(sender.lines) == 1)
        sched.on_lovf()
        await asyncio.sleep(0.02)
        assert sched.on_ack(DEV, 1, True) is True
        await until(lambda: done == [True])
        await asyncio.sleep(0.3)
        assert len(sender.lines) == 1
    finally:
        task.cancel()


async def test_lovf_and_ack_together_ack_wins_without_resend(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.on_lovf()
    assert sched.on_ack(DEV, 1, True) is True
    await until(lambda: done == [True])
    await asyncio.sleep(0.05)
    assert len(sender.lines) == 1


# --- final fix wave ---

class Gate:
    def __init__(self):
        self.event = asyncio.Event()
        self.calls = 0

    async def __call__(self):
        self.calls += 1
        await self.event.wait()


async def test_wait_ready_blocks_sending_without_counting_attempts():
    sender = Sender()
    gate = Gate()
    sched = RadioScheduler(sender, ack_timeout=0.02, clock=FakeClock(), budget_poll=0.01, wait_ready=gate)
    task = asyncio.create_task(sched.run())
    done = []
    try:
        sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
        await asyncio.sleep(0.15)
        assert sender.lines == [] and done == [] and gate.calls == 1
        gate.event.set()
        await until(lambda: len(sender.lines) == 1)
        sched.on_ack(DEV, 1, True)
        await until(lambda: done == [True])
    finally:
        task.cancel()


async def test_wait_ready_is_awaited_before_every_attempt():
    sender = Sender()
    gate = Gate()
    gate.event.set()
    sched = RadioScheduler(sender, ack_timeout=0.02, clock=FakeClock(), budget_poll=0.01, wait_ready=gate)
    task = asyncio.create_task(sched.run())
    done = []
    try:
        sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
        await until(lambda: done == [False], timeout=1.0)
        assert len(sender.lines) == 4 and gate.calls == 4
    finally:
        task.cancel()



# --- Block 1, Fix-Runde 1 ---

async def test_deadline_passed_while_waiting_for_stick_fails_without_sending():
    sender = Sender()
    clock = FakeClock()
    ready = asyncio.Event()

    async def wait_ready():
        await ready.wait()

    sched = RadioScheduler(sender, ack_timeout=0.05, clock=clock, wait_ready=wait_ready)
    task = asyncio.create_task(sched.run())
    try:
        done = []
        sched.submit(Command(dst=DEV, build=frame, on_done=done.append, deadline=clock() + 30))
        await asyncio.sleep(0.02)
        clock.t += 30
        ready.set()
        await until(lambda: done == [False])
        assert sender.lines == []
    finally:
        task.cancel()


async def test_deadline_stops_retries(setup):
    sched, sender, clock = setup
    done = []
    cmd = Command(dst=DEV, build=frame, on_done=done.append, deadline=clock() + 1)
    sched.submit(cmd)
    await until(lambda: len(sender.lines) == 1)
    clock.t += 1
    await until(lambda: done == [False])
    assert len(sender.lines) == 1 and cmd.sent == 1


async def test_stale_command_is_not_sent(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append, is_stale=lambda: True))
    await until(lambda: done == [False])
    assert sender.lines == []


async def test_cancel_key_drops_waiting_commands(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.submit(Command(dst=DEV, build=frame, key="set:1", on_done=done.append))
    sched.submit(Command(dst=DEV, build=frame, key="other", on_done=done.append))
    assert sched.cancel_key("set:1") == 1
    assert sched.queue_length == 1


# --- Fix: schnelles Wiederoeffnen bei tauben Stick ---

async def test_no_ack_outcome_and_first_send_time(setup):
    from custom_components.eq3_max.protocol.scheduler import Outcome

    sched, sender, clock = setup
    done = []
    cmd = Command(dst=DEV, build=frame, on_done=done.append)
    assert cmd.outcome is None and cmd.first_sent_at is None
    sched.submit(cmd)
    await until(lambda: len(sender.lines) == 1)
    first = clock.t
    clock.t += 10
    await until(lambda: done == [False], timeout=1.0)
    assert cmd.outcome is Outcome.NO_ACK
    assert cmd.first_sent_at == first


async def test_nak_and_ack_outcomes(setup):
    from custom_components.eq3_max.protocol.scheduler import Outcome

    sched, sender, _ = setup
    done = []
    nak = Command(dst=DEV, build=frame, on_done=done.append)
    sched.submit(nak)
    await until(lambda: len(sender.lines) == 1)
    sched.on_ack(DEV, 1, False)
    await until(lambda: done == [False])
    assert nak.outcome is Outcome.NAK
    ack = Command(dst=DEV, build=frame, on_done=done.append)
    sched.submit(ack)
    await until(lambda: len(sender.lines) == 2)
    sched.on_ack(DEV, 2, True)
    await until(lambda: done == [False, True])
    assert ack.outcome is Outcome.ACKED


async def test_not_sent_and_expired_outcomes(setup):
    from custom_components.eq3_max.protocol.scheduler import Outcome

    sched, sender, _ = setup
    done = []
    stale = Command(dst=DEV, build=frame, on_done=done.append, is_stale=lambda: True)
    sched.submit(stale)
    await until(lambda: done == [False])
    assert stale.outcome is Outcome.EXPIRED and stale.first_sent_at is None
    sender.fail = True
    unsent = Command(dst=DEV, build=frame, on_done=done.append)
    sched.submit(unsent)
    await until(lambda: done == [False, False], timeout=1.0)
    assert unsent.outcome is Outcome.NOT_SENT and unsent.first_sent_at is None


async def test_on_finished_runs_after_on_done_with_the_command():
    sender = Sender()
    calls = []
    sched = RadioScheduler(sender, ack_timeout=0.01, clock=FakeClock(), on_finished=lambda c: calls.append(("finished", c)))
    task = asyncio.create_task(sched.run())
    cmd = Command(dst=DEV, build=frame, on_done=lambda ok: calls.append(("done", ok)))
    sched.submit(cmd)
    await until(lambda: len(calls) == 2, timeout=1.0)
    assert calls == [("done", False), ("finished", cmd)]
    task.cancel()


def test_deaf_probe_defaults_to_false():
    assert Command(dst=DEV, build=frame).deaf_probe is False


# --- Block 3: schnelles Senden an wache Schlaefer ---

def test_fast_airtime_has_no_preamble():
    assert airtime(frame(1), fast=True) == pytest.approx(12 * 0.008)


async def test_fast_command_is_sent_with_zf_and_counts_short_airtime(setup):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, fast=True, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    assert sender.lines[0] == "Zf" + encode_frame(frame(1))
    assert sched.airtime_last_hour == pytest.approx(12 * 0.008)
    assert sched.on_ack(DEV, 1, True) is True
    await until(lambda: done == [True])


def test_fast_defaults_to_false():
    assert Command(dst=DEV, build=frame).fast is False


# --- Block 3, Fix-Runde 1: Versuche und Quittungswartezeit je Befehl ---

async def test_per_command_retries_and_ack_timeout(setup):
    sched, sender, _ = setup
    done = []
    cmd = Command(dst=DEV, build=frame, retries=0, ack_timeout=0.02, on_done=done.append)
    sched.submit(cmd)
    await until(lambda: done == [False])
    assert len(sender.lines) == 1
    from custom_components.eq3_max.protocol.scheduler import Outcome

    assert cmd.outcome is Outcome.NO_ACK


def test_per_command_limits_default_to_scheduler():
    cmd = Command(dst=DEV, build=frame)
    assert cmd.retries is None and cmd.ack_timeout is None


async def test_abandon_inflight_fast_command(setup):
    """A fast command on air can be given up (the device started transmitting instead
    of listening): outcome abandoned at once, no retry, nothing else touched."""
    from custom_components.eq3_max.protocol.scheduler import Outcome

    sched, sender, clock = setup
    done = []
    cmd = Command(dst=DEV, build=frame, key="link:x", fast=True, retries=0, ack_timeout=1.0, on_done=done.append)
    sched.submit(cmd)
    await until(lambda: len(sender.lines) == 1)
    assert sched.abandon_inflight("other") is False
    assert sched.abandon_inflight("link:x") is True
    await until(lambda: done == [False])
    assert cmd.outcome is Outcome.ABANDONED and cmd.sent == 1
    assert sched.abandon_inflight("link:x") is False  # nothing on air any more


# --- culfw refuses to send (LOVF): its own budget is empty ---


async def test_lovf_frame_was_not_on_air_no_airtime_no_sent_count():
    sender = Sender()
    sched = RadioScheduler(sender, ack_timeout=0.05, lovf_delay=0.2, clock=FakeClock(), budget_poll=0.01)
    task = asyncio.create_task(sched.run())
    try:
        cmd = Command(dst=DEV, build=frame)
        sched.submit(cmd)
        await until(lambda: len(sender.lines) == 1)
        assert sched.airtime_last_hour == pytest.approx(airtime(frame(1)))
        sched.on_lovf()
        await until(lambda: sched.waiting_for_budget)
        assert sched.airtime_last_hour == 0
        assert cmd.sent == 0 and cmd.first_sent_at is None
        await until(lambda: len(sender.lines) == 2)
        assert not sched.waiting_for_budget
        assert cmd.sent == 1 and sched.airtime_last_hour == pytest.approx(airtime(frame(1)))
    finally:
        task.cancel()


async def test_lovf_warns_once_per_command(setup, caplog):
    sched, sender, _ = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    for count in (1, 2, 3):
        await until(lambda: len(sender.lines) == count)
        sched.on_lovf()
    await until(lambda: len(sender.lines) == 4)
    sched.on_ack(DEV, 1, True)
    await until(lambda: done == [True])
    assert len([r for r in caplog.records if "LOVF" in r.getMessage() and r.levelname == "WARNING"]) == 1


def test_lovf_retry_default_leaves_the_stick_time_to_refill():
    # culfw refills 10 ms per second; a telegram with preamble needs about 110 s of that.
    sched = RadioScheduler(Sender())
    assert sched._lovf_delay == 10.0


async def test_waiting_for_budget_while_the_brake_holds(setup):
    sched, sender, clock = setup
    sched._brake = True
    sched._airtime.append((clock(), 36.0))
    sched.submit(Command(dst=DEV, build=frame))
    await until(lambda: sched.waiting_for_budget)
    assert sender.lines == []
    clock.t += 3601
    await until(lambda: len(sender.lines) == 1)
    assert not sched.waiting_for_budget


# --- never hand the stick a telegram while it is still transmitting the last one ---


async def test_next_send_waits_until_the_abandoned_one_is_off_the_air():
    """A reply given up for a more urgent one (time reply for a pairing pong) left the
    stick with a second "Zs" 180 ms into the 1 s preamble of the first: the nanoCUL hung
    until it was unplugged (10.11.2026)."""
    sender = Sender()
    sched = RadioScheduler(sender, ack_timeout=5.0, clock=FakeClock(), budget_poll=0.01)
    task = asyncio.create_task(sched.run())
    try:
        sched.submit(Command(dst=DEV, build=frame, key="time"))
        await until(lambda: len(sender.lines) == 1)
        assert sched.busy_for == pytest.approx(airtime(frame(1)) + 0.05, abs=0.05)
        sched.submit(Command(dst=DEV, build=frame, key="pong"))
        assert sched.abandon_key("time") is True
        await asyncio.sleep(0.3)
        assert len(sender.lines) == 1  # held back: the first telegram is still on air
        await until(lambda: len(sender.lines) == 2, timeout=2.0)
        assert sched.waited_for_air == 1
    finally:
        task.cancel()


async def test_a_send_after_the_usual_wait_is_not_held_back(setup):
    sched, sender, clock = setup
    done = []
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 1)
    sched.on_ack(DEV, 1, True)  # the answer shows the telegram is through
    sched.submit(Command(dst=DEV, build=frame, on_done=done.append))
    await until(lambda: len(sender.lines) == 2)
    assert sched.waited_for_air == 0


async def test_two_modules_never_send_at_the_same_time():
    """Two modules near each other must not transmit at once: their telegrams overlap,
    and with the same retry interval they overlap again on every attempt (14.11.2026:
    WT on one module, its radiator on the other, both configs lost)."""
    events = []

    class Logged(Sender):
        def __init__(self, name):
            super().__init__()
            self.name = name

        async def __call__(self, line):
            events.append(("send", self.name, asyncio.get_running_loop().time()))
            await super().__call__(line)

    lock = asyncio.Lock()
    a, b = Logged("a"), Logged("b")
    sa = RadioScheduler(a, ack_timeout=0.05, clock=FakeClock(), air_lock=lock)
    sb = RadioScheduler(b, ack_timeout=0.05, clock=FakeClock(), air_lock=lock)
    tasks = [asyncio.create_task(sa.run()), asyncio.create_task(sb.run())]
    try:
        sa.submit(Command(dst=DEV, build=frame))
        sb.submit(Command(dst=0x123456, build=lambda c: frame(c, dst=0x123456)))
        await until(lambda: len(a.lines) >= 1 and len(b.lines) >= 1, timeout=1.0)
        sends = [e for e in events if e[0] == "send"]
        # The second module waits for the first's acknowledgement window (0.05 s).
        assert sends[1][2] - sends[0][2] >= 0.045
    finally:
        for task in tasks:
            task.cancel()


async def test_pending_lists_the_command_on_air_first_then_the_waiting_ones_in_sending_order(setup):
    sched, sender, _ = setup
    assert sched.pending() == []
    sched.submit(Command(dst=DEV, build=frame, key="set:1"))
    await until(lambda: len(sender.lines) == 1)
    sched.submit(Command(dst=DEV, build=frame, key="wp:1:0:1"))
    sched.submit(Command(dst=0x222222, build=frame))
    sched.submit(Command(dst=0x333333, build=frame, key="pong:3", priority=PRIO_REPLY))
    assert sched.pending() == [
        {"dst": DEV, "key": "set:1", "attempts": 1, "on_air": True},
        {"dst": 0x333333, "key": "pong:3", "attempts": 0, "on_air": False},
        {"dst": DEV, "key": "wp:1:0:1", "attempts": 0, "on_air": False},
        {"dst": 0x222222, "key": None, "attempts": 0, "on_air": False},
    ]
    assert sched.queue_length == 3


async def test_background_waits_behind_commands(setup):
    sched, sender, _ = setup
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x01"), priority=PRIO_BACKGROUND, expects_ack=False))
    sched.submit(Command(dst=DEV, build=lambda c: frame(c, b"\x02"), expects_ack=False))
    await until(lambda: len(sender.lines) == 2)
    assert sender.lines[0].endswith("02") and sender.lines[1].endswith("01")


async def test_reserve_expires_instead_of_sending(setup):
    sched, sender, _ = setup
    sched.book_airtime(BUDGET_S - 10.5)  # 10.5 s free, the telegram costs ~1.1 s
    done = []
    cmd = Command(
        dst=DEV, build=lambda c: frame(c), priority=PRIO_BACKGROUND, expects_ack=False, reserve=10.0, on_done=done.append
    )
    sched.submit(cmd)
    await until(lambda: done == [False])
    assert sender.lines == [] and cmd.outcome is Outcome.EXPIRED


async def test_reserve_lets_through_with_room(setup):
    sched, sender, _ = setup
    sched.book_airtime(BUDGET_S - 12.0)
    sched.submit(Command(dst=DEV, build=lambda c: frame(c), expects_ack=False, reserve=10.0))
    await until(lambda: len(sender.lines) == 1)


# --- LOVF for telegrams without acknowledgement and for background telegrams ---


class RefusingSender(Sender):
    """The stick answers LOVF to the first `refuse` telegrams, right after taking them."""

    def __init__(self, refuse=1):
        super().__init__()
        self.refuse = refuse
        self.sched = None

    async def __call__(self, line):
        await super().__call__(line)
        if self.refuse:
            self.refuse -= 1
            asyncio.get_running_loop().call_soon(self.sched.on_lovf)


def refusing(refuse=1, **kwargs):
    sender = RefusingSender(refuse)
    sched = RadioScheduler(
        sender, ack_timeout=0.05, lovf_delay=0.05, clock=FakeClock(), budget_poll=0.01, lovf_wait=0.05, **kwargs
    )
    sender.sched = sched
    return sched, sender


async def test_a_telegram_without_ack_refused_by_lovf_is_not_booked_and_sent_again():
    sched, sender = refusing()
    task = asyncio.create_task(sched.run())
    done = []
    try:
        cmd = Command(dst=0, build=lambda c: frame(c, dst=0), expects_ack=False, on_done=done.append)
        sched.submit(cmd)
        await until(lambda: len(sender.lines) == 1)
        await until(lambda: sched.waiting_for_budget)
        assert sched.airtime_last_hour == 0 and cmd.sent == 0 and cmd.first_sent_at is None and done == []
        await until(lambda: done == [True])
        assert len(sender.lines) == 2 and cmd.outcome is Outcome.SENT and cmd.sent == 1
        assert sched.airtime_last_hour == pytest.approx(airtime(frame(1, dst=0)))
    finally:
        task.cancel()


async def test_a_telegram_without_ack_and_without_lovf_counts_as_sent():
    sched, sender = refusing(refuse=0)
    task = asyncio.create_task(sched.run())
    done = []
    try:
        sched.submit(Command(dst=0, build=lambda c: frame(c, dst=0), expects_ack=False, on_done=done.append))
        await until(lambda: done == [True])
        assert len(sender.lines) == 1 and sched.airtime_last_hour > 0
    finally:
        task.cancel()


@pytest.mark.parametrize("expects_ack", [False, True])
async def test_a_background_telegram_with_reserve_refused_by_lovf_expires(expects_ack):
    sched, sender = refusing()
    task = asyncio.create_task(sched.run())
    done = []
    try:
        cmd = Command(
            dst=DEV, build=frame, priority=PRIO_BACKGROUND, expects_ack=expects_ack, reserve=10.0, on_done=done.append
        )
        sched.submit(cmd)
        sched.submit(Command(
            dst=DEV, build=lambda c: frame(c, b"\x02"), priority=PRIO_BACKGROUND, expects_ack=False, on_done=done.append
        ))
        await until(lambda: len(done) == 2)
        assert done[0] is False and cmd.outcome is Outcome.EXPIRED
        assert cmd.sent == 0 and cmd.first_sent_at is None
        assert len(sender.lines) == 2 and sender.lines[1].endswith("02")   # no retry loop, the next one goes
        assert sched.airtime_last_hour == pytest.approx(airtime(frame(2, b"\x02")))
    finally:
        task.cancel()


async def test_brake_together_with_reserve_expires_instead_of_waiting():
    """The brake holds a command until the hour has room; a background telegram with
    reserve does not go into the reserve once the brake lets it through."""
    sender = Sender()
    clock = FakeClock()
    sched = RadioScheduler(sender, ack_timeout=0.05, clock=clock, brake=True, budget_poll=0.01, lovf_wait=0.01)
    sched.book_airtime(BUDGET_S - 5.0)  # room for the telegram, not for the reserve
    task = asyncio.create_task(sched.run())
    done = []
    try:
        cmd = Command(dst=0, build=lambda c: frame(c, dst=0), expects_ack=False, reserve=10.0, on_done=done.append)
        sched.submit(cmd)
        await until(lambda: done == [False])
        assert sender.lines == [] and cmd.outcome is Outcome.EXPIRED
        clock.t += 3601
        cmd2 = Command(dst=0, build=lambda c: frame(c, dst=0), expects_ack=False, reserve=10.0, on_done=done.append)
        sched.submit(cmd2)
        await until(lambda: done == [False, True])
        assert len(sender.lines) == 1
    finally:
        task.cancel()


async def test_airtime_survives_a_restart(setup):
    """The hour's budget is the transmitter's: what went out before a restart still
    counts, with its age; unusable stored entries are left out."""
    sched, sender, clock = setup
    sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
    await until(lambda: len(sender.lines) == 1)
    clock.t += 600
    log = sched.airtime_log()
    assert log == [(pytest.approx(600), pytest.approx(airtime(frame(1))))]
    fresh = RadioScheduler(Sender(), clock=FakeClock(5.0))
    fresh.restore_airtime([*log, (4000.0, 1.1), (-5.0, 1.1), (10.0, 99.0), (10.0, 0.0)])
    assert fresh.airtime_last_hour == pytest.approx(airtime(frame(1)))
    fresh._clock.t += 3001
    assert fresh.airtime_last_hour == 0.0


async def test_brake_counts_restored_airtime():
    sender = Sender()
    clock = FakeClock()
    sched = RadioScheduler(sender, ack_timeout=0.05, brake=True, clock=clock, budget_poll=0.01)
    sched.restore_airtime([(100.0, 1.2)] * 30)  # 36 s used before the restart
    task = asyncio.create_task(sched.run())
    try:
        sched.submit(Command(dst=DEV, build=frame, expects_ack=False))
        await asyncio.sleep(0.05)
        assert sender.lines == [] and sched.waiting_for_budget
        clock.t += 3600
        await until(lambda: len(sender.lines) == 1)
    finally:
        task.cancel()
