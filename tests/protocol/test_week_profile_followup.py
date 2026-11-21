"""Week program for a room in quick succession: a room mate still busy with the days of
one call follows with the days of the next after its running write (found in the field
21.11.2026: the radiator thermostat kept five of seven days, with a warning only)."""

import asyncio
import logging

from custom_components.eq3_max.protocol.messages import MsgType, ProfilePoint, encode_week_profile_day

from .fakes import line, until
from .hubkit import CENTRAL, HT, HT2, VW, WT, room, sent, thermostat

DAY_A = [ProfilePoint(17.0, 360), ProfilePoint(21.0, 1320), ProfilePoint(17.0, 1440)]
DAY_B = [ProfilePoint(19.0, 1440)]
DAY_C = [ProfilePoint(23.0, 1440)]


def stored(points):
    return [{"temperature": p.temperature, "until": f"{p.until // 60:02d}:{p.until % 60:02d}"} for p in points]


def wp_lines(cul, dst=None):
    """Week program telegrams in the order they went on air, a repeat counted once."""
    out, seen = [], set()
    for l in sent(cul):
        if l[8:10] != "10" or (dst is not None and l[16:22] != f"{dst:06X}"):
            continue
        key = (l[4:6], l[16:22], l[24:])
        if key not in seen:
            seen.add(key)
            out.append(l)
    return out


def days_on_air(cul, dst):
    return [int(l[24:26], 16) & 0x0F for l in wp_lines(cul, dst)]


def ack(cul, l, ok=True):
    cul.feed(line(int(l[4:6], 16), 0x02, MsgType.ACK, int(l[16:22], 16), CENTRAL, 0, "00" if ok else "80"))


async def ack_next(cul, done):
    """Acknowledge the next week program telegram; `done` counts those acknowledged."""
    await until(lambda: len(wp_lines(cul)) > done)
    ack(cul, wp_lines(cul)[done])
    return done + 1


def auto_ack(cul, done=0):
    """Acknowledge every week program telegram from the `done`th on, as it comes."""

    async def run():
        n = done
        while True:
            lines = wp_lines(cul)
            for l in lines[n:]:
                ack(cul, l)
            n = len(lines)
            await asyncio.sleep(0.005)

    return asyncio.create_task(run())


async def stop_acking(task):
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


def real_room(h):
    """The fixture's wall thermostat with HT and HT2 (both directions)."""
    wt, ht, ht2 = h.devices[WT], h.devices[HT], thermostat(h, HT2)
    wt.links = [ht.serial, ht2.serial]
    ht.links = [wt.serial]
    ht2.links = [wt.serial]


async def test_virtual_wall_two_calls_in_a_row_the_mate_gets_all_days(hub, caplog):
    h, cul, _ = hub; room(h, mates=(HT,))
    caplog.set_level(logging.INFO)
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A, 3: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {0: DAY_B, 1: DAY_B}))
    await asyncio.sleep(0.01)
    # The wall thermostat has every day at once; its radiator shows what is still to come.
    assert set(h.devices[VW].week_profile) == {"Samstag", "Sonntag", "Montag", "Dienstag"}
    assert h.devices[HT].week_profile_writing == ["Samstag", "Sonntag", "Montag", "Dienstag"]
    done = 0
    for _ in range(4):
        done = await ack_next(cul, done)
    await asyncio.wait_for(asyncio.gather(first, second), 1.0)
    assert days_on_air(cul, HT) == [2, 3, 0, 1]
    assert h.devices[HT].week_profile == {
        "Montag": stored(DAY_A), "Dienstag": stored(DAY_A), "Samstag": stored(DAY_B), "Sonntag": stored(DAY_B),
    }
    assert h.devices[HT].week_profile_writing == [] and h.devices[HT].week_profile_error is None
    assert "does not follow" not in caplog.text
    assert "after the running week program" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


async def test_virtual_wall_call_waits_for_its_mates(hub):
    """Service calls one after the other (as in the field): the first returns once its
    radiator has the days, so the second finds it free."""
    h, cul, _ = hub; room(h, mates=(HT,))
    acker = auto_ack(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(VW, {d: DAY_A for d in (2, 3, 4, 5, 6)}), 2.0)
        assert list(h.devices[HT].week_profile) == ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
        await asyncio.wait_for(h.set_week_profile(VW, {0: DAY_B, 1: DAY_B}), 2.0)
        assert len(h.devices[HT].week_profile) == 7
        assert days_on_air(cul, HT) == [2, 3, 4, 5, 6, 0, 1]
    finally:
        await stop_acking(acker)


async def test_real_wall_room_mates_follow_after_their_running_write(hub, caplog):
    h, cul, _ = hub; real_room(h)
    first = asyncio.create_task(h.set_week_profile(WT, {2: DAY_A, 3: DAY_A}))
    done = 0
    while not first.done():
        done = await ack_next(cul, done)
        await asyncio.sleep(0.01)
    await first
    # The wall thermostat is through, its radiators are not yet.
    assert h.devices[HT].week_profile_writing and h.devices[HT2].week_profile_writing
    second = asyncio.create_task(h.set_week_profile(WT, {0: DAY_B}))
    acker = auto_ack(cul, done)
    try:
        await asyncio.wait_for(second, 2.0)
        await until(lambda: all(len(h.devices[a].week_profile) == 3 for a in (HT, HT2)))
    finally:
        await stop_acking(acker)
    for address in (HT, HT2):
        assert days_on_air(cul, address) == [2, 3, 0]
        assert h.devices[address].week_profile["Samstag"] == stored(DAY_B)
        assert h.devices[address].week_profile_writing == []
    assert days_on_air(cul, WT) == [2, 3, 0]
    assert "does not follow" not in caplog.text


async def test_queued_calls_for_the_same_weekday_the_later_one_wins(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A, 3: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {3: DAY_B, 4: DAY_B}))
    third = asyncio.create_task(h.set_week_profile(VW, {3: DAY_C}))
    await asyncio.sleep(0.01)
    assert h.devices[HT].week_profile_writing == ["Montag", "Dienstag", "Mittwoch"]
    acker = auto_ack(cul)
    try:
        await asyncio.wait_for(asyncio.gather(first, second, third), 2.0)
    finally:
        await stop_acking(acker)
    # Tuesday of the running write goes first, the queued one (merged: the latest) after it.
    assert days_on_air(cul, HT) == [2, 3, 3, 4]
    assert wp_lines(cul, HT)[1][26:] == encode_week_profile_day(DAY_A)[0].hex().upper()
    assert wp_lines(cul, HT)[2][26:] == encode_week_profile_day(DAY_C)[0].hex().upper()
    assert h.devices[HT].week_profile["Dienstag"] == stored(DAY_C)
    assert h.devices[HT].week_profile["Mittwoch"] == stored(DAY_B)
    assert h.devices[VW].week_profile["Dienstag"] == stored(DAY_C)


async def test_follow_up_runs_after_the_running_write_failed(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {0: DAY_B}))
    await asyncio.sleep(0.01)
    ack(cul, wp_lines(cul)[0], ok=False)  # Monday refused
    # A mate's failure is not the caller's: it is reported at the mate.
    await asyncio.wait_for(first, 1.0)
    await until(lambda: len(wp_lines(cul)) == 2)
    assert days_on_air(cul, HT) == [2, 0]
    assert h.devices[HT].week_profile_writing == ["Samstag"]
    ack(cul, wp_lines(cul)[1])
    await asyncio.wait_for(second, 1.0)
    assert h.devices[HT].week_profile == {"Samstag": stored(DAY_B)}
    # The refused Monday stays reported until a write brings it.
    assert h.devices[HT].week_profile_error["key"] == "week_profile_rejected"
    assert h.devices[HT].week_profile_error["missing"] == ["Montag"]


async def test_a_failing_follow_up_keeps_the_days_of_the_earlier_failure(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {0: DAY_B}))
    await asyncio.sleep(0.01)
    ack(cul, wp_lines(cul)[0], ok=False)  # Monday refused
    await until(lambda: len(wp_lines(cul)) == 2)
    ack(cul, wp_lines(cul)[1], ok=False)  # Saturday refused too
    await asyncio.wait_for(asyncio.gather(first, second), 1.0)
    error = h.devices[HT].week_profile_error
    assert error["key"] == "week_profile_rejected"
    assert error["missing"] == ["Samstag", "Montag"]  # weekday order, nothing lost


async def test_a_follow_up_that_brings_the_missing_days_clears_the_failure(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {2: DAY_B}))
    await asyncio.sleep(0.01)
    ack(cul, wp_lines(cul)[0], ok=False)
    await until(lambda: len(wp_lines(cul)) == 2)
    ack(cul, wp_lines(cul)[1])
    await asyncio.wait_for(asyncio.gather(first, second), 1.0)
    assert h.devices[HT].week_profile == {"Montag": stored(DAY_B)}
    assert h.devices[HT].week_profile_error is None


async def test_stop_drops_a_queued_follow_up(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {0: DAY_B}))
    await asyncio.sleep(0.01)
    await h.stop()
    await asyncio.wait_for(asyncio.gather(first, second), 1.0)
    count = len(sent(cul))
    await asyncio.sleep(0.2)
    assert len(sent(cul)) == count
    assert h._profile_jobs == {} and h._profile_followups == {}
    assert h.devices[HT].week_profile_writing == []
    others = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    assert others == []


async def test_excluded_room_mates_are_not_written(hub):
    """A copy within a room: the source keeps its program, it is not written as a mate."""
    h, cul, _ = hub; real_room(h)
    acker = auto_ack(cul)
    try:
        await asyncio.wait_for(h.set_week_profile(WT, {2: DAY_A}, exclude=(HT,)), 2.0)
        await until(lambda: h.devices[HT2].week_profile == {"Montag": stored(DAY_A)})
    finally:
        await stop_acking(acker)
    assert days_on_air(cul, HT) == [] and h.devices[HT].week_profile == {}
    assert days_on_air(cul, WT) == [2] and days_on_air(cul, HT2) == [2]


async def test_set_week_profile_tells_which_devices_it_covered(hub):
    """The service skips a target the hub already writes as a room mate: it must know
    which ones the call reached. Joining a running write reaches the device only."""
    h, cul, _ = hub; real_room(h)
    acker = auto_ack(cul)
    try:
        first = asyncio.create_task(h.set_week_profile(HT, {2: DAY_A}))
        await until(lambda: h.devices[HT2].week_profile_writing == ["Montag"])
        joined = await asyncio.wait_for(h.set_week_profile(HT2, {2: DAY_A}), 2.0)
        assert joined == {HT2}
        assert await asyncio.wait_for(first, 2.0) == {HT, WT, HT2}
        assert await asyncio.wait_for(h.set_week_profile(HT, {2: DAY_A}, exclude=(HT2,)), 2.0) == {HT, WT}
    finally:
        await stop_acking(acker)


async def test_wait_week_profile_returns_when_running_and_queued_writes_are_done(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    await asyncio.wait_for(h.wait_week_profile(HT), 0.5)  # nothing running
    first = asyncio.create_task(h.set_week_profile(VW, {2: DAY_A}))
    await until(lambda: len(wp_lines(cul)) == 1)
    second = asyncio.create_task(h.set_week_profile(VW, {0: DAY_B}))
    await asyncio.sleep(0.01)
    waiting = asyncio.create_task(h.wait_week_profile(HT))
    ack(cul, wp_lines(cul)[0])
    await until(lambda: len(wp_lines(cul)) == 2)
    await asyncio.sleep(0.02)
    assert not waiting.done()  # the queued Saturday is still to come
    ack(cul, wp_lines(cul)[1])
    await asyncio.wait_for(waiting, 1.0)
    assert h.devices[HT].week_profile_writing == []
    await asyncio.wait_for(asyncio.gather(first, second), 1.0)
