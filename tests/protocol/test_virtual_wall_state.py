"""Virtual wall thermostat: what ends by itself (away period, a setpoint changed in
automatic mode, boost), setpoints it does not take, the first thermostat's state, and the
room's group id over the room's life."""

import asyncio
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol import virtual_wall
from custom_components.eq3_max.protocol.devices import LINK_ADD, WEEKDAYS, MaxDevice
from custom_components.eq3_max.protocol.messages import DeviceType, Mode, MsgType, ProfilePoint, encode_until

from .fakes import FakeClock, line, until
from .hubkit import CENTRAL, HT, HT2, VC, VW, WT, linked_contact, room, sent, thermostat

# Every day (LOCAL_NOW 09.10.2026 is a Friday): 17 until 06:00, 21 until 22:00, 17 until
# midnight. A whole week: automatic mode needs a known program.
FRIDAY = {day: [
    {"temperature": 17.0, "until": "06:00"},
    {"temperature": 21.0, "until": "22:00"},
    {"temperature": 17.0, "until": "24:00"},
] for day in WEEKDAYS}
OUTSIDE = 0x150001


@pytest.fixture(autouse=True)
def quick_forward(monkeypatch):
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", 0.05)


def fast(cul):
    return [l for l in cul.written if l.startswith("Zf")]


def temps(cul):
    return [l for l in sent(cul) if l[8:10] == "42"]


def ack_all(cul, dst, payload="0119002A"):
    last = next(l for l in reversed(sent(cul)) if l[16:22] == f"{dst:06X}")
    cul.feed(line(int(last[4:6], 16), 0x02, MsgType.ACK, dst, CENTRAL, 0, payload))


def use_clock(h):
    clock = FakeClock(1_700_000_000.0)
    h._now = clock
    return clock


def auto_room(h, **kwargs):
    vw = room(h, **kwargs)
    vw.mode, vw.week_profile = Mode.AUTO, {k: [dict(p) for p in v] for k, v in FRIDAY.items()}
    h.virtual.tick()
    return vw


# --- C1: an away period ends by itself ---


async def test_away_period_ends_and_the_room_follows_the_program_again(hub):
    h, cul, rec = hub; vw = room(h, group=5)
    vw.week_profile = {k: [dict(p) for p in v] for k, v in FRIDAY.items()}
    vw.mode, vw.target, vw.until = Mode.TEMPORARY, 16.0, datetime(2026, 10, 9, 12, 30)
    vw.resume_mode = Mode.AUTO                                                 # away began in automatic mode
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    assert temps(cul)[0].endswith("20DC")                                      # 16,0 while away
    h._local_now.t = datetime(2026, 10, 9, 13, 0)
    rec.updates.clear()
    h.virtual.tick()
    assert (vw.mode, vw.until, vw.target) == (Mode.AUTO, None, 21.0)
    assert vw in rec.updates


async def test_away_period_over_the_next_telegram_carries_the_program(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = room(h, group=5)
    vw.week_profile = {k: [dict(p) for p in v] for k, v in FRIDAY.items()}
    vw.mode, vw.target, vw.until = Mode.TEMPORARY, 16.0, datetime(2026, 10, 9, 12, 30)
    vw.resume_mode = Mode.AUTO                                                 # away began in automatic mode
    h._local_now.t = datetime(2026, 10, 9, 13, 0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    assert temps(cul)[0].endswith("2ADC")                                      # 21,0 from the program
    assert vw.mode is Mode.AUTO


async def test_away_ended_is_answered_with_automatic_and_reported_after_the_answer(hub):
    h, cul, rec = hub; vw = room(h)
    vw.week_profile = {k: [dict(p) for p in v] for k, v in FRIDAY.items()}
    vw.mode, vw.target, vw.until = Mode.TEMPORARY, 16.0, datetime(2026, 10, 9, 11, 30)
    vw.resume_mode = Mode.AUTO
    seen = []
    rec_update = h._on_update

    def watch(dev):
        if dev is vw:
            seen.append(len(fast(cul)))
        rec_update(dev)

    h._on_update = watch
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0E090202111111{HT:06X}000118042A"]                # AUTO, 21,0
    await until(lambda: seen != [])
    assert all(count == 1 for count in seen)                                   # only after the answer
    assert vw.mode is Mode.AUTO


# --- I1: automatic mode ---


async def test_handwheel_in_automatic_mode_holds_until_the_next_switch_point(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = auto_room(h, group=5)
    assert vw.target == 21.0
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "2E"))          # AUTO 23,0 at the handwheel
    await until(lambda: f"Zf0E090202111111{HT:06X}000118042E" in cul.written)
    assert (vw.mode, vw.target, vw.override_target) == (Mode.AUTO, 23.0, 23.0)
    assert vw.override_until == datetime(2026, 10, 9, 22, 0)
    await until(lambda: any(l[16:22] == f"{HT2:06X}" for l in sent(cul)))      # handed on to HT2
    ack_all(cul, HT2, "0118002E")
    await until(lambda: h.devices[HT2].pending_mode is None)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    assert temps(cul)[0].endswith("2EDC")                                      # 23,0, not the program's 21
    await until(lambda: vw.sent_at is not None)
    h._local_now.t = datetime(2026, 10, 9, 21, 59)
    clock.t += 600; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 2)
    assert temps(cul)[1].endswith("2EDC")                                      # still held
    await until(lambda: vw.sent_at == clock.t)
    h._local_now.t = datetime(2026, 10, 9, 22, 0)
    clock.t += 600; h.virtual.tick()
    assert vw.override_target is None and vw.target == 17.0
    await until(lambda: len(temps(cul)) == 3)
    assert temps(cul)[2].endswith("22DC")                                      # 17,0: the switch point


async def test_setpoint_from_home_assistant_in_automatic_mode_is_an_override(hub):
    h, cul, _ = hub; vw = auto_room(h)
    h.set_temperature(VW, 19.5, Mode.AUTO)
    assert (vw.target, vw.override_target, vw.override_until) == (19.5, 19.5, datetime(2026, 10, 9, 22, 0))
    h.set_temperature(VW, None, Mode.AUTO)                                     # back to the program
    assert (vw.target, vw.override_target) == (21.0, None)
    h.set_temperature(VW, 19.5, Mode.AUTO)
    h.set_temperature(VW, 18.0, Mode.MANUAL)
    assert vw.override_target is None and vw.override_until is None


async def test_switch_point_updates_the_wall_target(hub):
    h, cul, rec = hub; vw = auto_room(h)
    assert vw.target == 21.0
    rec.updates.clear()
    h._local_now.t = datetime(2026, 10, 9, 22, 0)
    h.virtual.tick()
    assert vw.target == 17.0 and vw in rec.updates
    rec.updates.clear()
    h.virtual.tick()
    assert vw not in rec.updates                                               # only on a change


async def test_override_survives_a_restart(hub):
    h, cul, _ = hub; vw = auto_room(h)
    h.set_temperature(VW, 19.5, Mode.AUTO)
    again = MaxDevice.from_dict(vw.to_dict())
    assert (again.override_target, again.override_until) == (19.5, datetime(2026, 10, 9, 22, 0))


# --- Boost ---


async def test_boost_from_home_assistant_at_the_wall_ends_with_the_rooms_boost_duration(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = room(h)
    h.set_temperature(VW, 21.0, Mode.BOOST)
    assert vw.mode is Mode.BOOST
    clock.t += 5 * 60 - 1; h.virtual.tick()
    assert vw.mode is Mode.BOOST
    clock.t += 1; h.virtual.tick()
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0)


async def test_boost_of_the_wall_ends_after_an_hour_at_the_latest(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = room(h)
    for address in (HT, HT2):
        h.devices[address].config["boost_dauer"] = 120
    h.set_temperature(VW, 21.0, Mode.BOOST)
    clock.t += 3599; h.virtual.tick()
    assert vw.mode is Mode.BOOST
    clock.t += 1; h.virtual.tick()
    assert vw.mode is Mode.MANUAL


# --- I8: a setpoint not taken is answered with itself ---


async def test_setpoint_to_a_removing_wall_is_answered_with_itself(hub):
    h, cul, _ = hub; vw = room(h)
    vw.removing = True
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6E"))          # manual 23,0
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0E090202111111{HT:06X}000119042E"]
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0)


async def test_setpoint_of_an_unknown_or_unlinked_thermostat_is_answered_with_itself(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,))
    thermostat(h, HT2)                                                         # known, not linked
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT2, VW, 0, "6E"))
    cul.feed(line(4, 0x04, MsgType.SET_TEMPERATURE, 0x154321, VW, 0, "AE" + encode_until(datetime(2026, 10, 10, 8)).hex()))
    await until(lambda: len(fast(cul)) == 2)
    assert fast(cul)[0] == f"Zf0E090202111111{HT2:06X}000119042E"
    assert fast(cul)[1] == "Zf0E04020211111115432100011A042E"                 # temporary 23,0
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0)


async def test_a_telegram_proves_an_open_link_addition(hub):
    h, cul, rec = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    vw.target, vw.mode = 21.0, Mode.MANUAL
    ht = h.devices[HT]
    h.link(HT, VW)                                                             # the wall's side at once
    assert ht.serial in vw.links and ht.link_op(vw.serial)["op"] == LINK_ADD
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))          # manual 21,5 from HT
    await until(lambda: f"Zf0E090202111111{HT:06X}000119042B" in cul.written)  # taken: new target
    await until(lambda: vw.serial in ht.links)
    assert ht.link_op(vw.serial) is None and vw.target == 21.5
    await until(lambda: ht.pending_group is not None)                         # it joined the room


async def test_wake_up_proves_an_open_link_addition(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    vw.target, vw.mode = 21.0, Mode.MANUAL
    ht = h.devices[HT]
    h.link(HT, VW)
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: vw.serial in ht.links)
    assert ht.link_op(vw.serial) is None


# --- I6: the first thermostat's state ---


async def test_a_configured_wall_keeps_its_program_and_settings_when_linked(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    await h.set_week_profile(VW, {6: [ProfilePoint(19.0, 24 * 60)]})          # Freitag
    h.set_config(VW, "komfort", 23.0)
    ht = h.devices[HT]
    ht.target, ht.mode = 20.0, Mode.MANUAL
    ht.week_profile = {"Freitag": [{"temperature": 17.0, "until": "24:00"}], "Montag": [{"temperature": 18.0, "until": "24:00"}]}
    ht.config["komfort"], ht.config["eco"] = 21.0, 16.0
    h.link(HT, VW)
    assert vw.week_profile["Freitag"] == [{"temperature": 19.0, "until": "24:00"}]
    assert vw.week_profile["Montag"] == [{"temperature": 18.0, "until": "24:00"}]   # an empty day takes it
    # The set the user saved (komfort with the others of its set) stays the wall's own.
    assert vw.config["komfort"] == 23.0 and vw.config["eco"] == 17.0
    assert (vw.mode, vw.target) == (Mode.MANUAL, 20.0)


async def test_an_empty_program_never_replaces_a_stored_one(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    vw.week_profile = {"Freitag": [{"temperature": 19.0, "until": "24:00"}]}
    ht = h.devices[HT]
    ht.target, ht.mode, ht.week_profile = 20.0, Mode.MANUAL, {}
    h.link(HT, VW)
    assert vw.week_profile == {"Freitag": [{"temperature": 19.0, "until": "24:00"}]}


async def test_relinking_a_one_radiator_room_keeps_the_walls_values(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,))
    ht = h.devices[HT]
    h.unlink(VW, HT)
    await until(lambda: len(sent(cul)) == 1)
    ack_all(cul, HT)
    await until(lambda: vw.serial not in ht.links)
    ht.target, ht.mode = 18.0, Mode.MANUAL
    h.link(HT, VW)
    assert (vw.mode, vw.target) == (Mode.MANUAL, 21.0)


async def test_a_thermostat_at_window_temperature_is_not_adopted_as_the_rooms_setpoint(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    ht.target, ht.mode, ht.last_comfort = 12.0, Mode.MANUAL, 20.5            # window open
    h.link(HT, VW)
    assert (vw.mode, vw.target) == (Mode.MANUAL, 20.5)


# Without any comfort value it would be automatic mode, which needs a known program:
# manual with the wall thermostat's own comfort value (factory 21.0).
@pytest.mark.parametrize(("comfort", "expected"), [(20.5, (Mode.MANUAL, 20.5)), (None, (Mode.MANUAL, 21.0))])
async def test_a_boosting_thermostat_is_not_adopted_as_boost(hub, comfort, expected):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    ht.target, ht.mode, ht.last_comfort = 30.5 if comfort is None else 21.0, Mode.BOOST, comfort
    if comfort is None:
        ht.target = None
    h.link(HT, VW)
    assert (vw.mode, vw.target) == expected


# --- I7: the room's group id ---


async def test_own_group_used_outside_the_room_is_not_kept(hub):
    h, cul, _ = hub; vw = room(h, mates=())
    h.devices[HT].group = 7
    thermostat(h, OUTSIDE).group = 7                                           # another room's id
    h.devices[HT].links.append(vw.serial); vw.links.append(h.devices[HT].serial)
    h.virtual.link_committed(h.devices[HT], vw.serial, LINK_ADD)
    assert h.devices[HT].pending_group not in (None, 7) and vw.group == h.devices[HT].pending_group


async def test_own_group_unused_outside_the_room_is_kept(hub):
    h, cul, _ = hub; vw = room(h, mates=())
    h.devices[HT].group = 7
    h.devices[HT].links.append(vw.serial); vw.links.append(h.devices[HT].serial)
    h.virtual.link_committed(h.devices[HT], vw.serial, LINK_ADD)
    assert h.devices[HT].pending_group is None and vw.group == 7


async def test_a_thermostat_leaving_the_virtual_room_loses_its_group_id(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,), group=5)
    h.unlink(VW, HT)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][8:10] == "21"                                         # RemoveLinkPartner
    ack_all(cul, HT)
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][8:10] == "23"                                         # RemoveGroupId, once
    assert h.devices[HT].pending_group == 0
    ack_all(cul, HT)
    await until(lambda: h.devices[HT].group == 0)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 2


async def test_a_thermostat_still_with_a_wall_thermostat_keeps_its_group_id(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,), group=5)
    h.devices[HT].links.append(h.devices[WT].serial)                         # a real wall thermostat too
    h.unlink(VW, HT)
    await until(lambda: len(sent(cul)) == 1)
    ack_all(cul, HT)
    await until(lambda: vw.serial not in h.devices[HT].links)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1 and h.devices[HT].group == 5


async def test_a_forced_unlink_does_not_touch_the_group_id(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,), group=5)
    h.unlink(HT, VW, force=True)
    await until(lambda: len(sent(cul)) == 1)
    ack_all(cul, HT)
    await until(lambda: vw.serial not in h.devices[HT].links)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1 and h.devices[HT].group == 5


async def test_room_form(hub):
    h, cul, _ = hub; vw = room(h, mates=(), group=5)
    assert h.virtual.room_form(vw) is None
    for address in (HT, HT2):
        mate = thermostat(h, address)
        mate.links.append(vw.serial); vw.links.append(mate.serial); mate.group = 5
    assert h.virtual.room_form(vw) == "group"
    h.devices[HT2].group = 0
    assert h.virtual.room_form(vw) == "addressed"


# --- Minors ---


async def test_no_poke_for_a_thermostat_of_a_virtual_room(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    ht = h.devices[HT]
    ht.poll_minutes, ht.target, ht.mode = 5, 21.0, Mode.MANUAL
    h._poll_check()
    await asyncio.sleep(0.05)
    assert sent(cul) == [] and HT not in h._pokes


async def test_a_reported_setpoint_drops_a_running_poke(hub):
    h, cul, _ = hub; room(h)
    h._pokes[HT] = {"target": 19.0, "mode": Mode.MANUAL, "deadline": h._now() + 60}
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: h.devices[HT].target == 21.5)
    assert HT not in h._pokes


async def test_a_virtual_contact_without_source_counts_as_closed(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,))
    vc = linked_contact(h, to=HT)
    vc.links.append(vw.serial); vw.links.append(vc.serial)
    vc.window_open = True
    assert h.virtual.window_open(VW)
    vc.source_ok = False
    assert not h.virtual.window_open(VW)


async def test_a_setpoint_after_stop_is_answered_but_arms_nothing(hub):
    """hub.stop() stops the virtual devices first; a telegram arriving before the
    transports are closed is still answered, but nothing is handed on any more."""
    h, cul, _ = hub; vw = room(h)
    h.virtual.stop()
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: f"Zf0E090202111111{HT:06X}000119042B" in cul.written)
    assert not h.virtual._forwards
    h.set_temperature(VW, 22.0, Mode.MANUAL)
    await asyncio.sleep(0.1)
    assert sent(cul) == []


async def test_room_form_reason(hub):
    h, cul, _ = hub; vw = room(h, group=5)
    assert h.virtual.room_form_reason(vw) is None                              # group
    h.devices[HT2].group = 0
    assert h.virtual.room_form_reason(vw) == "no_group"
    h.devices[HT2].pending_group = 5
    assert h.virtual.room_form_reason(vw) == "pending"
    h.devices[HT2].pending_group = None
    h.devices[HT2].radio = "elsewhere"
    h._radio_of = lambda dev: type("R", (), {"id": dev.radio})()
    assert h.virtual.room_form_reason(vw) == "modules"
