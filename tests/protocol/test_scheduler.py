import asyncio

import pytest

from custom_components.eq3_max.protocol.messages import Frame, FrameError, MsgType, encode_frame
from custom_components.eq3_max.protocol.scheduler import (
    PRIO_REPLY,
    Command,
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
