"""A week program costs a telegram per day and device, each with a 1 s wake-up preamble.
Two savings: days a device holds already are not sent again, and a series to one device
follows a WakeUp without the preamble (unanswered, it goes the usual way)."""

import asyncio
import logging

import pytest

from custom_components.eq3_max.protocol import hub as hub_module
from custom_components.eq3_max.protocol.hub import MaxHub
from custom_components.eq3_max.protocol.messages import MsgType, ProfilePoint
from custom_components.eq3_max.protocol.scheduler import PER_BYTE_S, PREAMBLE_S

from .fakes import FakeCul, line, until
from .hubkit import CENTRAL, HT, HT2, WT, LocalClock, Recorder, devices
from .test_week_profile_followup import DAY_A, DAY_B, DAY_C, real_room, stored

WEEK = {day: DAY_A for day in range(7)}


@pytest.fixture
async def hub():
    cul = FakeCul()
    rec = Recorder()
    h = MaxHub(
        "/dev/serial/by-path/x", CENTRAL, devices(),
        on_update=rec.updates.append, on_button=lambda d, t: None, on_device_added=rec.added.append,
        on_device_removed=rec.removed.append, on_problem=rec.problems.append, open_connection=cul.open,
        ack_timeout=0.05, now=lambda: 1_700_000_000.0, local_now=LocalClock(), wake_settle=0.0, wake_series=True,
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, cul, rec
    await h.stop()


def on_air(cul, dst=None):
    """(Zs|Zf, type) of what went to the device, in order (not the hub's own answers)."""
    return [
        (l[:2], l[8:10]) for l in cul.written
        if l[:2] in ("Zs", "Zf") and l[8:10] != "02" and (dst is None or l[16:22] == f"{dst:06X}")
    ]


def acker(cul, *, deaf_to=()):
    """Acknowledge every telegram as it comes, except the kinds in `deaf_to`
    ((Zs|Zf, type) pairs)."""

    async def run():
        n = 0
        while True:
            lines = list(cul.written)
            for l in lines[n:]:
                if l[:2] in ("Zs", "Zf") and l[8:10] != "02" and (l[:2], l[8:10]) not in deaf_to:
                    cul.feed(line(int(l[4:6], 16), 0x02, MsgType.ACK, int(l[16:22], 16), CENTRAL, 0, "00"))
            n = len(lines)
            await asyncio.sleep(0.002)

    return asyncio.create_task(run())


async def stop(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def test_a_week_goes_out_after_one_wake_up_without_preamble(hub, caplog):
    h, cul, _ = hub
    caplog.set_level(logging.INFO)
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, WEEK), 3.0)
    finally:
        await stop(task)
    assert on_air(cul, HT) == [("Zs", "F1"), *[("Zf", "10")] * 7]
    assert len(h.devices[HT].week_profile) == 7
    # One preamble instead of seven: the WakeUp (12 bytes) and seven telegrams of 26.
    assert h.airtime_last_hour == pytest.approx(PREAMBLE_S + PER_BYTE_S * (12 + 7 * 26), abs=0.001)
    assert "7 of 7 telegrams went without wake-up preamble" in caplog.text


async def test_two_telegrams_are_not_worth_a_wake_up(hub):
    h, cul, _ = hub
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A, 3: DAY_B}), 3.0)
    finally:
        await stop(task)
    assert on_air(cul, HT) == [("Zs", "10"), ("Zs", "10")]


async def test_an_unanswered_fast_telegram_goes_out_again_the_usual_way(hub, caplog):
    """The device did not listen after all: the same telegram with preamble, the rest
    too, nothing lost; after two such series the device gets no WakeUp any more."""
    h, cul, _ = hub
    caplog.set_level(logging.INFO)
    task = acker(cul, deaf_to={("Zf", "10")})
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {0: DAY_A, 1: DAY_A, 2: DAY_A}), 5.0)
        assert on_air(cul, HT) == [("Zs", "F1"), ("Zf", "10"), ("Zs", "10"), ("Zs", "10"), ("Zs", "10")]
        assert len(h.devices[HT].week_profile) == 3 and h.devices[HT].week_profile_error is None
        assert "stayed unanswered" in caplog.text
        await asyncio.wait_for(h.set_week_profile(HT, {0: DAY_B, 1: DAY_B, 2: DAY_B}), 5.0)
        assert "it gets none any more" in caplog.text
        before = len(on_air(cul, HT))
        await asyncio.wait_for(h.set_week_profile(HT, {0: DAY_C, 1: DAY_C, 2: DAY_C}), 5.0)
        assert on_air(cul, HT)[before:] == [("Zs", "10")] * 3
    finally:
        await stop(task)


async def test_without_an_answer_to_the_wake_up_the_series_goes_the_usual_way(hub):
    h, cul, _ = hub
    task = acker(cul, deaf_to={("Zs", "F1")})
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {0: DAY_A, 1: DAY_A, 2: DAY_A}), 5.0)
    finally:
        await stop(task)
    assert on_air(cul, HT) == [("Zs", "F1"), ("Zs", "F1"), *[("Zs", "10")] * 3]
    assert len(h.devices[HT].week_profile) == 3


async def test_a_telegram_that_waited_past_the_awake_time_ends_the_series(hub, monkeypatch):
    """No WakeUp per telegram when the queue is slow: each would only add its preamble."""
    h, cul, _ = hub
    monkeypatch.setattr(hub_module, "WAKE_AWAKE_S", 0.0)
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, WEEK), 5.0)
    finally:
        await stop(task)
    assert on_air(cul, HT) == [("Zs", "F1"), *[("Zs", "10")] * 7]
    assert HT not in h._series_failed  # nothing was unanswered


async def test_days_the_device_holds_are_not_sent_again(hub, caplog):
    h, cul, _ = hub
    caplog.set_level(logging.INFO)
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}), 3.0)
        assert await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}), 3.0) == {HT}
        assert len(on_air(cul, HT)) == 1 and "week profile unchanged, nothing sent" in caplog.text
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A, 3: DAY_B}), 3.0)
        assert len(on_air(cul, HT)) == 2 and cul.written[-1][24:26] == "03"  # Tuesday only
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}, force=True), 3.0)
        assert len(on_air(cul, HT)) == 3
    finally:
        await stop(task)
    assert h.devices[HT].week_profile == {"Montag": stored(DAY_A), "Dienstag": stored(DAY_B)}
    assert h.devices[HT].week_profile_writing == []


async def test_a_day_a_failed_write_left_open_is_written_even_if_it_looks_unchanged(hub):
    """A day of two telegrams may be half written: the stored copy says nothing then."""
    h, cul, _ = hub
    dev = h.devices[HT]
    dev.week_profile = {"Montag": stored(DAY_A)}
    dev.week_profile_error = {"message": "x", "key": "k", "placeholders": {}, "missing": ["Montag"]}
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}), 3.0)
    finally:
        await stop(task)
    assert on_air(cul, HT) == [("Zs", "10")] and dev.week_profile_error is None


async def test_only_the_room_mates_that_lack_the_days_are_written(hub):
    h, cul, _ = hub
    real_room(h)
    h.devices[HT2].week_profile = {"Montag": stored(DAY_A)}
    task = acker(cul)
    try:
        reached = await asyncio.wait_for(h.set_week_profile(WT, {2: DAY_A}), 3.0)
        await until(lambda: h.devices[HT].week_profile == {"Montag": stored(DAY_A)})
    finally:
        await stop(task)
    assert reached == {WT, HT, HT2}
    assert on_air(cul, HT2) == [] and len(on_air(cul, HT)) == 1 and len(on_air(cul, WT)) == 1


async def test_an_unanswered_wake_up_counts_against_the_device(hub):
    """A device that ignores the WakeUp must not get one with every write."""
    h, cul, _ = hub
    task = acker(cul, deaf_to={("Zs", "F1")})
    try:
        for day in (DAY_A, DAY_B, DAY_C):
            await asyncio.wait_for(h.set_week_profile(HT, {0: day, 1: day, 2: day}), 5.0)
    finally:
        await stop(task)
    assert [kind for kind in on_air(cul, HT) if kind[1] == "F1"] == [("Zs", "F1")] * 4  # two writes, two attempts each
    assert len([kind for kind in on_air(cul, HT) if kind[1] == "10"]) == 9


async def test_the_series_wake_up_is_not_replaced_by_a_manual_one(hub):
    h, cul, _ = hub
    task = asyncio.create_task(h.set_week_profile(HT, WEEK))
    await until(lambda: on_air(cul, HT) == [("Zs", "F1")])
    h.wake_up(HT)  # queued with its own key
    acking = acker(cul)
    try:
        await asyncio.wait_for(task, 5.0)
    finally:
        await stop(acking)
    assert len(h.devices[HT].week_profile) == 7


async def test_a_fast_telegram_whose_answer_is_lost_is_simply_sent_again(hub):
    """The device took it, the acknowledgement did not arrive: the same day once more with
    preamble (the device answers again), nothing is counted twice or left out."""
    h, cul, _ = hub
    task = acker(cul, deaf_to={("Zf", "10")})
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {0: DAY_A, 1: DAY_B, 2: DAY_C}), 5.0)
    finally:
        await stop(task)
    days = [int(l[24:26], 16) & 0x0F for l in cul.written if l[:2] in ("Zs", "Zf") and l[8:10] == "10"]
    assert days == [0, 0, 1, 2]
    assert h.devices[HT].week_profile_doubt == [] and len(h.devices[HT].week_profile) == 3


async def test_a_day_stays_in_doubt_across_another_write_and_a_restart(hub):
    """Monday went out and was not acknowledged: the device may hold it. Neither a write
    of another day nor a restart makes the stored copy trustworthy again."""
    h, cul, _ = hub
    dev = h.devices[HT]
    dev.week_profile = {"Montag": stored(DAY_A)}
    with pytest.raises(Exception):
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_B}), 5.0)  # nobody answers
    assert dev.week_profile_doubt == ["Montag"]
    task = acker(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(HT, {3: DAY_C}), 3.0)  # clears the error
        assert dev.week_profile_error is None and dev.week_profile_doubt == ["Montag"]
        restored = type(dev).from_dict(dev.to_dict())
        assert restored.week_profile_doubt == ["Montag"]
        before = len(on_air(cul, HT))
        await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}), 3.0)  # looks unchanged, goes out
    finally:
        await stop(task)
    assert len(on_air(cul, HT)) == before + 1 and dev.week_profile_doubt == []


async def test_a_write_cut_off_by_a_stop_leaves_its_day_in_doubt(hub):
    h, cul, _ = hub
    dev = h.devices[HT]
    dev.week_profile = {"Montag": stored(DAY_A)}
    task = asyncio.create_task(h.set_week_profile(HT, {2: DAY_B}))
    await until(lambda: len(on_air(cul, HT)) == 1)
    await h.stop()
    await asyncio.gather(task, return_exceptions=True)
    assert dev.week_profile_doubt == ["Montag"]


async def test_a_refused_day_is_not_in_doubt(hub):
    """NAK at the first telegram: the device keeps what it had."""
    h, cul, _ = hub
    task = asyncio.create_task(h.set_week_profile(HT, {2: DAY_B}))
    await until(lambda: len(on_air(cul, HT)) == 1)
    l = cul.written[-1]
    cul.feed(line(int(l[4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "80"))
    await asyncio.gather(task, return_exceptions=True)
    assert h.devices[HT].week_profile_doubt == []


async def test_a_forced_call_does_not_join_a_write_that_leaves_days_out(hub):
    """Joining would report the forced days written although they never went out."""
    h, cul, _ = hub
    dev = h.devices[HT]
    dev.week_profile = {"Samstag": stored(DAY_A), "Sonntag": stored(DAY_A)}
    plan = {0: DAY_A, 1: DAY_A, 2: DAY_A}
    first = asyncio.create_task(h.set_week_profile(HT, plan))
    await until(lambda: len(on_air(cul, HT)) == 1)          # Monday only
    with pytest.raises(Exception, match="being written"):
        await h.set_week_profile(HT, plan, force=True)
    task = acker(cul)
    try:
        await asyncio.wait_for(first, 3.0)
        forced = asyncio.create_task(h.set_week_profile(HT, plan, force=True))
        await until(lambda: len([k for k in on_air(cul, HT) if k[1] == "10"]) >= 2)
        joined = await asyncio.wait_for(h.set_week_profile(HT, plan, force=True), 3.0)  # a full write: joins
        await asyncio.wait_for(forced, 3.0)
    finally:
        await stop(task)
    assert joined == {HT}
    assert len([k for k in on_air(cul, HT) if k[1] == "10"]) == 1 + 3
