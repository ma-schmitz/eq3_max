"""Virtual wall thermostat after the field test: automatic mode only with a known week
program (the 0x42 sets the thermostats' target), and the end of an away period returns
to the state before it."""

import asyncio
import logging
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol import virtual_wall
from custom_components.eq3_max.protocol.devices import WEEKDAYS, MaxDevice
from custom_components.eq3_max.protocol.messages import DeviceType, FrameError, Mode, MsgType, ProfilePoint, encode_until

from .fakes import line, until
from .hubkit import CENTRAL, HT, HT2, VW, room, sent

# Every day: 17 until 06:00, 21 until 22:00, 17 until midnight (LOCAL_NOW is 12:00).
DAY = [
    {"temperature": 17.0, "until": "06:00"},
    {"temperature": 21.0, "until": "22:00"},
    {"temperature": 17.0, "until": "24:00"},
]
POINTS = [ProfilePoint(17.0, 6 * 60), ProfilePoint(21.0, 22 * 60), ProfilePoint(17.0, 24 * 60)]


@pytest.fixture(autouse=True)
def quick_forward(monkeypatch):
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", 0.05)


def week():
    return {day: [dict(p) for p in DAY] for day in WEEKDAYS}


def fast(cul):
    return [l for l in cul.written if l.startswith("Zf")]


def setpoints(cul, dst):
    return [l for l in sent(cul) if l[8:10] == "40" and l[16:22] == f"{dst:06X}"]


def temps(cul):
    return [l for l in sent(cul) if l[8:10] == "42"]


def ack(cul, dst):
    last = next(l for l in reversed(sent(cul)) if l[16:22] == f"{dst:06X}")
    cul.feed(line(int(last[4:6], 16), 0x02, MsgType.ACK, dst, CENTRAL, 0, "0119002A"))


# --- F3: program known ---


async def test_in_room_names_the_wall_and_its_thermostats(hub):
    h, cul, _ = hub
    assert not h.virtual.in_room(HT)
    room(h)
    assert h.virtual.in_room(VW) and h.virtual.in_room(HT) and h.virtual.in_room(HT2)
    assert not h.virtual.in_room(CENTRAL)


async def test_program_known_needs_all_seven_days(hub):
    h, cul, _ = hub; vw = room(h)
    assert not h.virtual.program_known(VW) and not h.virtual.program_known(HT)
    vw.week_profile = week()
    vw.week_profile["Montag"] = []
    assert not h.virtual.program_known(VW)
    vw.week_profile = week()
    assert h.virtual.program_known(VW) and h.virtual.program_known(HT)   # a member asks its room


@pytest.mark.parametrize("address", [VW, HT])
async def test_auto_without_program_is_refused(hub, address):
    h, cul, rec = hub; vw = room(h)
    rec.updates.clear()
    with pytest.raises(FrameError) as err:
        h.set_temperature(address, None, Mode.AUTO)
    assert err.value.key == "virtual_no_program"
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0) and rec.updates == []
    await asyncio.sleep(0.05)
    assert sent(cul) == []


async def test_auto_with_program_is_taken(hub):
    h, cul, _ = hub; vw = room(h)
    await h.set_week_profile(VW, {day: POINTS for day in range(7)})
    assert vw.mode is Mode.MANUAL                                              # writing changes no mode
    h.set_temperature(VW, None, Mode.AUTO)
    assert (vw.mode, vw.target) == (Mode.AUTO, 21.0)


async def test_auto_reported_by_a_thermostat_without_program_is_answered_and_corrected(hub, caplog):
    h, cul, _ = hub; vw = room(h)
    caplog.set_level(logging.INFO)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "00"))          # Auto button at HT
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul)[0] == f"Zf0E090202111111{HT:06X}000118042A"               # its own mode, the room's 21,0
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0)
    await until(lambda: len(setpoints(cul, HT)) == 1)
    assert setpoints(cul, HT)[0].endswith("006A")                              # group 0, MANUAL 21,0
    assert setpoints(cul, HT2) == []                                           # only the reporting one
    assert len([r for r in caplog.records if "no week program" in r.getMessage()]) == 1


async def test_auto_reported_with_program_is_taken(hub):
    h, cul, _ = hub; vw = room(h)
    vw.week_profile = week()
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "00"))
    await until(lambda: len(fast(cul)) == 1)
    assert vw.mode is Mode.AUTO and vw.target == 21.0


async def test_first_link_of_an_auto_thermostat_without_program_makes_the_room_manual(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    ht.target, ht.mode = 19.5, Mode.AUTO
    h.link(HT, VW)
    assert (vw.mode, vw.target) == (Mode.MANUAL, 19.5)
    await until(lambda: len(sent(cul)) == 1)
    ack(cul, HT)                                                               # the link
    await until(lambda: len(setpoints(cul, HT)) == 1)
    assert setpoints(cul, HT)[0].endswith("67")                                # MANUAL 19,5 (0x40|39)
    assert setpoints(cul, HT)[0][22:24] == "00"                                # addressed, group 0


async def test_first_link_at_window_temperature_takes_the_comfort_value(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    ht.target, ht.mode, ht.last_comfort = 12.0, Mode.AUTO, 20.5
    h.link(HT, VW)
    assert (vw.mode, vw.target) == (Mode.MANUAL, 20.5)


async def test_first_link_of_an_auto_thermostat_with_program_stays_auto(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    ht.target, ht.mode, ht.week_profile = 21.0, Mode.AUTO, week()
    h.link(HT, VW)
    assert vw.mode is Mode.AUTO


async def test_writing_the_program_clears_a_running_override(hub):
    h, cul, _ = hub; vw = room(h)
    vw.week_profile, vw.mode = week(), Mode.AUTO
    h.set_temperature(VW, 23.0, Mode.AUTO)
    assert vw.override_target == 23.0
    other = [ProfilePoint(18.0, 24 * 60)]
    await h.set_week_profile(VW, {day: other for day in range(7)})
    assert vw.override_target is None and vw.override_until is None
    assert (vw.mode, vw.target) == (Mode.AUTO, 18.0)


# --- F4: end of an away period ---


async def test_away_without_program_returns_to_the_manual_target_before(hub):
    h, cul, _ = hub; vw = room(h, group=5)
    for mate in (h.devices[HT], h.devices[HT2]):
        mate.target, mate.mode = 21.0, Mode.MANUAL
    h.set_temperature(VW, 16.0, Mode.TEMPORARY, datetime(2026, 10, 9, 12, 30))
    assert (vw.resume_mode, vw.resume_target) == (Mode.MANUAL, 21.0)
    h.set_temperature(VW, 15.0, Mode.TEMPORARY, datetime(2026, 10, 9, 13, 30))   # replaced: kept
    assert (vw.resume_mode, vw.resume_target) == (Mode.MANUAL, 21.0)
    for address in (HT, HT2):
        await until(lambda a=address: len(setpoints(cul, a)) == 1)
        ack(cul, address)
    await until(lambda: not h.devices[HT].has_pending and not h.devices[HT2].has_pending)
    before = {a: len(setpoints(cul, a)) for a in (HT, HT2)}
    h._local_now.t = datetime(2026, 10, 9, 14, 0)
    h.virtual.tick()
    assert (vw.mode, vw.target, vw.until) == (Mode.MANUAL, 21.0, None)
    assert (vw.resume_mode, vw.resume_target) == (None, None)
    for address in (HT, HT2):
        await until(lambda a=address: len(setpoints(cul, a)) == before[a] + 1)
        assert setpoints(cul, address)[-1].endswith("6A")                     # MANUAL 21,0
        ack(cul, address)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    assert temps(cul)[0].endswith("2ADC")                                      # 21,0


async def test_away_over_auto_with_program_returns_to_auto_without_setpoints(hub):
    h, cul, _ = hub; vw = room(h, group=5)
    vw.week_profile, vw.mode = week(), Mode.AUTO
    h.virtual.tick()
    h.set_temperature(VW, 16.0, Mode.TEMPORARY, datetime(2026, 10, 9, 12, 30))
    assert vw.resume_mode is Mode.AUTO
    for address in (HT, HT2):
        await until(lambda a=address: len(setpoints(cul, a)) == 1)
        ack(cul, address)
    await until(lambda: not h.devices[HT].has_pending and not h.devices[HT2].has_pending)
    count = len(sent(cul))
    h._local_now.t = datetime(2026, 10, 9, 13, 0)
    h.virtual.tick()
    assert (vw.mode, vw.target) == (Mode.AUTO, 21.0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    assert temps(cul)[0].endswith("2ADC")
    await asyncio.sleep(0.1)
    assert [l for l in sent(cul)[count:] if l[8:10] == "40"] == []


async def test_away_reported_by_a_thermostat_remembers_the_state_before(hub):
    h, cul, _ = hub; vw = room(h)
    until_hex = encode_until(datetime(2026, 10, 9, 18, 0)).hex()
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "A0" + until_hex))  # TEMPORARY 16,0
    await until(lambda: vw.mode is Mode.TEMPORARY)
    assert (vw.resume_mode, vw.resume_target) == (Mode.MANUAL, 21.0)


async def test_away_without_anything_to_return_to_takes_the_comfort_value(hub):
    h, cul, _ = hub; vw = room(h)
    vw.mode, vw.target, vw.until = Mode.TEMPORARY, 16.0, datetime(2026, 10, 9, 11, 0)   # from an older store
    h.virtual.tick()
    assert (vw.mode, vw.target) == (Mode.MANUAL, vw.config["komfort"])


async def test_resume_fields_survive_a_restart(hub):
    h, cul, _ = hub; vw = room(h)
    h.set_temperature(VW, 16.0, Mode.TEMPORARY, datetime(2026, 10, 9, 12, 30))
    again = MaxDevice.from_dict(vw.to_dict())
    assert (again.resume_mode, again.resume_target) == (Mode.MANUAL, 21.0)
    old = vw.to_dict()
    del old["resume_mode"], old["resume_target"]                               # stored before 0.10.0's fix
    assert MaxDevice.from_dict(old).resume_mode is None


async def test_auto_button_during_away_without_program_ends_the_away_period(hub):
    h, cul, _ = hub; vw = room(h)
    h.set_temperature(VW, 16.0, Mode.TEMPORARY, datetime(2026, 10, 9, 18, 0))
    for address in (HT, HT2):
        await until(lambda a=address: len(setpoints(cul, a)) == 1)
        ack(cul, address)
    await until(lambda: not h.devices[HT].has_pending and not h.devices[HT2].has_pending)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "00"))          # Auto-Taste an HT
    await until(lambda: len(fast(cul)) == 1)
    assert (vw.mode, vw.target, vw.until) == (Mode.MANUAL, 21.0, None)
    for address in (HT, HT2):
        await until(lambda a=address: len(setpoints(cul, a)) == 2)
        assert setpoints(cul, address)[-1].endswith("6A")                     # MANUAL 21,0, nicht wieder Abwesend
