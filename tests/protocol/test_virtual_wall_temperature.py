"""Virtual wall thermostat: the room temperature (0x42) with its fixed interval, timer,
window changes at once, reserve, expiry and limited drop, and the group id a thermostat
gets when it joins the room."""

import asyncio
import contextlib
import logging
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol import virtual, virtual_wall
from custom_components.eq3_max.protocol.devices import WEEKDAYS
from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.hub import MaxHub, RadioSpec
from custom_components.eq3_max.protocol.messages import DeviceType, FrameError, Mode, MsgType
from custom_components.eq3_max.protocol.scheduler import BUDGET_S

from .fakes import FakeClock, FakeCul, line, until
from .hubkit import CENTRAL, FK, HT, HT2, HT3, VC, VW, devices, linked_contact, room, sent, thermostat

VW2 = 0x333333


def idle(h, address):
    return h._scheduler_for(address).pending() == []


def use_clock(h):
    """Hub wall clock the test moves on (the fixture's stands still)."""
    clock = FakeClock(1_700_000_000.0)
    h._now = clock
    return clock


def brake_on(h):
    """The option "limit airtime to 36 s": the hub and its schedulers brake."""
    h._brake = True
    for radio in h._radios.values():
        radio.scheduler._brake = True


def temps(cul):
    return [l for l in sent(cul) if l[8:10] == "42"]


def on_air(cul):
    """What went out in order: "42" for a room temperature, else the addressee; the
    retries of one command count once."""
    order = []
    for l in sent(cul):
        item = "42" if l[8:10] == "42" else l[16:22]
        if not order or order[-1] != item or item == "42":
            order.append(item)
    return order


def ack(cul, sent_line, src):
    cul.feed(line(int(sent_line[4:6], 16), 0x02, MsgType.ACK, src, VW, 0, "0119002A"))


async def test_first_value_goes_to_the_group(hub):
    h, cul, _ = hub; room(h, group=5)
    h.virtual.set_measured(VW, 22.04)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:] == "0442111111000000052ADC"      # Flags 04, an 000000, Gruppe 05, Soll 21,0 Ist 22,0
    await until(lambda: h.devices[VW].sent_at is not None)
    assert h.devices[VW].sent_measured == 22.0 and h.devices[VW].measured == 22.0


async def test_no_group_yet_sends_addressed_round_robin(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:16] == "0042111111"                                   # adressiert, Flags 00
    assert sent(cul)[0][16:22] == f"{HT:06X}"
    ack(cul, sent(cul)[0], HT)
    await until(lambda: h.devices[VW].sent_at == clock.t)
    clock.t += virtual_wall.WT_INTERVAL_S / 2; h.virtual.tick()                # zwei Thermostate: halbes Intervall
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][16:22] == f"{HT2:06X}"                                  # reihum: jetzt das andere


async def test_unconfirmed_group_of_one_thermostat_means_addressed(hub):
    h, cul, _ = hub; room(h, group=5)
    h.devices[HT2].group, h.devices[HT2].pending_group = 0, 5                   # noch nicht quittiert
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:10] == "0042"


async def test_addressed_without_answer_sets_nothing_and_the_next_one_goes_elsewhere(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(sent(cul)) == 1)
    await until(lambda: not h.virtual._temps)                                   # keine Quittung, ein Versuch
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1 and h.devices[VW].sent_at is None
    clock.t += 149; h.virtual.tick(); await asyncio.sleep(0.05)
    assert len(sent(cul)) == 1                                                 # Versuch zählt für den Takt
    clock.t += 1; h.virtual.tick()
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][16:22] == f"{HT2:06X}"


async def test_fixed_interval(hub):                                            # Feldtest: fest 5 min
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(sent(cul)) == 1)
    await until(lambda: h.devices[VW].sent_at is not None)
    for value in (22.5, 25.0, 19.2):                                           # keine Änderung schickt früher
        clock.t += 60; h.virtual.set_measured(VW, value)
    clock.t += 119; h.virtual.tick(); await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1                                                 # 299 s: nichts
    clock.t += 1; h.virtual.tick(); await until(lambda: len(sent(cul)) == 2)   # 300 s
    await until(lambda: h.devices[VW].sent_at == clock.t)
    clock.t += 300; h.virtual.tick(); await until(lambda: len(sent(cul)) == 3)  # gleicher Wert: trotzdem


async def test_the_next_telegram_goes_on_time_without_a_tick(hub, monkeypatch):
    """The room's own timer, not the hub's 60 s tick, sends it (field test: 608 and 660 s
    instead of 600)."""
    monkeypatch.setattr(virtual_wall, "WT_INTERVAL_S", 0.3)
    h, cul, _ = hub; loop = asyncio.get_running_loop(); h._now = loop.time; room(h, group=5)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    first = loop.time()
    await until(lambda: len(temps(cul)) == 2)
    assert 0.25 <= loop.time() - first < 0.45                                  # pünktlich, ohne tick()
    await until(lambda: len(temps(cul)) == 3)                                  # und so weiter


async def test_one_telegram_per_room_on_the_way(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    thermostat(h, 0x150001)
    h.set_temperature(0x150001, 19.0, Mode.MANUAL)                            # belegt den Funk
    h.virtual.set_measured(VW, 22.0)
    for value in (22.5, 23.0):
        clock.t += 1000; h.virtual.set_measured(VW, value); h.virtual.tick()
    pending = [p for p in h._scheduler_for(HT).pending() if p["key"] == f"vwt:{VW}"]
    assert len(pending) == 1
    await until(lambda: len(temps(cul)) == 1)
    await asyncio.sleep(0.1)
    assert temps(cul)[0].endswith("2ADC")                                     # der zuerst gebaute, kein zweiter
    assert len(temps(cul)) == 1


async def test_a_telegram_that_waited_too_long_is_built_anew(hub):
    h, cul, _ = hub; room(h, group=5)
    thermostat(h, 0x150001)
    h.set_temperature(0x150001, 19.0, Mode.MANUAL)
    h.virtual.set_measured(VW, 22.0)
    old = h.virtual._temps[VW]
    old.deadline = h._scheduler_for(HT).now() - 1                              # 2 min gewartet
    h.virtual.set_measured(VW, 23.0)
    assert h.virtual._temps[VW] is not old
    await until(lambda: len(temps(cul)) == 1)
    await asyncio.sleep(0.1)
    assert [l[-4:] for l in temps(cul)] == ["2AE6"]                            # nur der neue, 23,0


async def test_drop_is_stepped_down(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 25.0); await until(lambda: len(sent(cul)) == 1)
    await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += 300; h.virtual.set_measured(VW, 17.0); await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1].endswith("2AF0")                                       # 24,0 statt 17,0
    await until(lambda: h.devices[VW].sent_measured == 24.0)
    clock.t += 300; h.virtual.tick(); await until(lambda: len(sent(cul)) == 3)
    assert sent(cul)[2].endswith("2AE6")                                       # 23,0


async def test_a_limited_drop_continues_at_the_next_regular_telegram(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 25.0); await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += 300; h.virtual.set_measured(VW, 23.9)                           # 1,1 tiefer: 24,0
    await until(lambda: h.devices[VW].sent_measured == 24.0)
    clock.t += 300; h.virtual.tick()                                           # 23,9 zu 24,0: nur 0,1
    await until(lambda: len(sent(cul)) == 3)
    assert sent(cul)[2].endswith("2AEF")                                       # 23,9


async def test_rise_is_not_limited(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 17.0); await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += 300; h.virtual.set_measured(VW, 25.0)
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1].endswith("2AFA")


async def test_first_value_after_a_pause_starts_from_the_thermostats_own_reading(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.devices[HT].measured, h.devices[HT].measured_at = 22.0, clock.t
    h.virtual.set_measured(VW, 17.0); await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("2AD2")                                       # 21,0


async def test_after_a_pause_a_newer_reading_counts_not_the_value_sent_last(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 25.0); await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += virtual_wall.WT_PAUSE_S
    h.devices[HT].measured, h.devices[HT].measured_at = 19.0, clock.t - 10     # eigener Fühler
    h.virtual.set_measured(VW, 17.0); await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1].endswith("2AB4")                                       # 18,0


async def test_open_window_puts_the_window_temperature_into_the_telegram(hub):
    h, cul, _ = hub; room(h, group=5); linked_contact(h, to=VW)
    h.virtual.set_window(VC, True); h.virtual.set_measured(VW, 22.0)
    await until(lambda: any("0442" in l for l in sent(cul)))
    assert [l for l in sent(cul) if "0442" in l][0].endswith("18DC")           # 12,0 °C


async def test_auto_mode_takes_the_target_from_the_program(hub):
    h, cul, _ = hub; room(h, group=5)
    vw = h.devices[VW]; vw.mode = Mode.AUTO
    vw.week_profile = {day: [{"temperature": 17.0, "until": "24:00"}] for day in WEEKDAYS}
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("22DC")


async def test_auto_mode_without_program_takes_the_target(hub):
    h, cul, _ = hub; room(h, group=5)
    h.devices[VW].mode = Mode.AUTO
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("2ADC")


async def test_boost_sends_the_normal_target(hub):
    h, cul, _ = hub; room(h, group=5)
    h.devices[VW].mode = Mode.BOOST
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("2ADC")


async def test_no_usable_target_no_telegram(hub):
    h, cul, _ = hub; room(h, group=5)
    for target in (None, 31.0, 4.0):
        h.devices[VW].target = target
        h.virtual.set_measured(VW, 22.0); h.virtual.tick()
    await asyncio.sleep(0.1)
    assert sent(cul) == []


async def test_without_the_brake_option_no_reserve_is_kept(hub):
    """F8: the reserve follows the option to limit the airtime; without it the stick decides."""
    h, cul, _ = hub; room(h, group=5)
    h._scheduler_for(HT).book_airtime(BUDGET_S - 5.0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)                                  # geht trotz Stundenrechnung


async def test_a_telegram_into_the_reserve_expires_and_counts_as_nothing(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5); brake_on(h)
    h._scheduler_for(HT).book_airtime(BUDGET_S - 5.0)                          # Reserve unterschritten
    h.virtual.set_measured(VW, 22.0); await asyncio.sleep(0.2)
    assert sent(cul) == [] and h.devices[VW].sent_at is None
    assert not h.virtual._temps                                                # verfallen: der nächste darf
    clock.t += 60; h.virtual.tick(); await asyncio.sleep(0.2)
    assert sent(cul) == []


async def answer_setpoints(cul):
    """Acknowledge every 0x40 at once, as a thermostat would."""
    answered = 0
    while True:
        lines = [l for l in sent(cul) if l[8:10] == "40"]
        for l in lines[answered:]:
            cul.feed(line(int(l[4:6], 16), 0x02, MsgType.ACK, int(l[16:22], 16), CENTRAL, 0, "0119002A"))
        answered = len(lines)
        await asyncio.sleep(0.001)


async def commands_waiting(h, cul, count):
    """`count` set commands to thermostats outside the room: the first on air, the others
    waiting behind it. Returns their addresses."""
    others = [thermostat(h, 0x150001 + n).address for n in range(count)]
    for address in others:
        h.set_temperature(address, 19.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 2)                                   # der erste ist in der Luft
    return others


async def test_starved_room_goes_ahead_of_waiting_commands(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 22.0); await until(lambda: h.devices[VW].sent_at is not None)
    others = await commands_waiting(h, cul, 4)
    clock.t += virtual_wall.WT_STARVED_S
    h.virtual.tick()                                                           # drei warten noch
    responder = asyncio.create_task(answer_setpoints(cul))
    try:
        await until(lambda: len(on_air(cul)) == 6)
    finally:
        responder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await responder
    assert on_air(cul) == ["42", f"{others[0]:06X}", "42", *(f"{a:06X}" for a in others[1:])]


async def test_a_room_that_is_not_starved_waits_behind_commands(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    h.virtual.set_measured(VW, 22.0); await until(lambda: h.devices[VW].sent_at is not None)
    others = await commands_waiting(h, cul, 2)
    clock.t += virtual_wall.WT_INTERVAL_S
    h.virtual.tick()
    responder = asyncio.create_task(answer_setpoints(cul))
    try:
        await until(lambda: len(on_air(cul)) == 4)
    finally:
        responder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await responder
    assert on_air(cul) == ["42", *(f"{a:06X}" for a in others), "42"]


async def test_out_of_range_source_is_not_sent(hub):                            # Review Focus 1
    h, cul, rec = hub; room(h, group=5)
    for value in (None, -5.0, 60.0, float("nan")):
        h.virtual.set_measured(VW, value)
        assert h.devices[VW].source_ok is False and h.devices[VW].measured is None
    await asyncio.sleep(0.1); assert sent(cul) == []


async def test_a_waiting_telegram_is_dropped_when_the_source_fails(hub):
    h, cul, _ = hub; room(h, group=5)
    thermostat(h, 0x150001)
    h.set_temperature(0x150001, 19.0, Mode.MANUAL)                            # belegt den Funk
    h.virtual.set_measured(VW, 22.0)
    h.virtual.set_measured(VW, None)
    await until(lambda: idle(h, HT), timeout=3)
    assert temps(cul) == []


async def test_set_measured_notifies_only_on_a_change(hub):
    h, cul, rec = hub; room(h, group=5)
    h.virtual.set_measured(VW, 22.01)
    h.virtual.set_measured(VW, 22.04)                                          # gerundet gleich
    assert rec.updates.count(h.devices[VW]) == 1
    h.virtual.set_measured(VW, None)
    assert rec.updates.count(h.devices[VW]) == 2


async def test_removing_wall_thermostat_sends_nothing(hub):
    h, cul, _ = hub; room(h, group=5)
    h.devices[VW].removing = True
    h.virtual.set_measured(VW, 22.0); h.virtual.tick()
    await asyncio.sleep(0.1); assert sent(cul) == []


async def test_room_without_confirmed_thermostat_sends_nothing(hub):
    h, cul, _ = hub; vw = room(h, mates=(), group=5)
    vw.links.append(h.devices[HT].serial)                                      # nur unsere Seite
    h.virtual.set_measured(VW, 22.0)
    await asyncio.sleep(0.1); assert sent(cul) == []


async def test_two_rooms_on_one_module(hub):                                    # Review Focus 5
    h, cul, _ = hub; room(h, group=5); room(h, wall=VW2, mates=(HT3,), group=6)
    h.virtual.set_measured(VW, 22.0); h.virtual.set_measured(VW2, 19.0)
    await until(lambda: len(sent(cul)) == 2)
    assert {l[22:24] for l in sent(cul)} == {"05", "06"}                        # Gruppen-Byte


async def test_link_gives_the_thermostat_the_room_group(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(HT, VW); await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: any(l[8:10] == "22" for l in sent(cul)))               # SetGroupId folgt
    group = h.devices[HT].pending_group
    assert group and h.devices[VW].group == group                              # das virtuelle ohne Funk
    assert all(l[16:22] != f"{VW:06X}" for l in sent(cul))
    assert group not in {d.group for d in h.devices.values() if d.address not in (HT, VW)}


async def test_link_takes_the_group_of_another_room_thermostat(hub):
    h, cul, _ = hub; room(h, mates=(HT2,), group=7)
    h.link(HT, VW); await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: any(l[8:10] == "22" for l in sent(cul)))
    assert h.devices[HT].pending_group == 7
    assert [l for l in sent(cul) if l[8:10] == "22"][0].endswith("07")


async def test_link_keeps_the_thermostats_own_group(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.devices[HT].group = 9
    h.link(HT, VW); await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: h.devices[VW].group == 9)
    await asyncio.sleep(0.1)
    assert not any(l[8:10] in ("22", "23") for l in sent(cul))                # kein Funk für die Gruppe


async def test_an_unanswered_attempt_counts_for_the_rate_limit(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, mates=(HT,), group=0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    await until(lambda: not h.virtual._temps)                                  # keine Quittung
    for _ in range(4):                                                         # 60, 120, 180, 240 s
        clock.t += 60; h.virtual.tick(); await asyncio.sleep(0.05)
    assert len(temps(cul)) == 1 and h.devices[VW].sent_at is None
    clock.t += 60; h.virtual.tick()                                            # 300 s
    await until(lambda: len(temps(cul)) == 2)
    await until(lambda: not h.virtual._temps)
    for _ in range(4):
        clock.t += 60; h.virtual.tick(); await asyncio.sleep(0.05)
    assert len(temps(cul)) == 2


async def test_an_expired_telegram_is_no_attempt(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5); brake_on(h)
    scheduler = h._scheduler_for(HT)
    scheduler.book_airtime(BUDGET_S - 5.0)                                     # Reserve: verfällt
    h.virtual.set_measured(VW, 22.0); await until(lambda: not h.virtual._temps)
    scheduler._airtime.clear()
    clock.t += 60; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 1)                                  # gleich beim nächsten Takt


# --- Fix round 1 ---


async def answering(cul, coro):
    """Run `coro` while every 0x40 is acknowledged at once."""
    responder = asyncio.create_task(answer_setpoints(cul))
    try:
        return await coro
    finally:
        responder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await responder


async def test_failing_attempts_do_not_jump_ahead_every_time(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, mates=(HT,), group=0)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    ack(cul, temps(cul)[0], HT)                                                # einmal zugestellt
    await until(lambda: h.devices[VW].sent_at == clock.t)
    clock.t += 600; h.virtual.tick()                                           # Versuch ohne Quittung
    await until(lambda: len(temps(cul)) == 2)
    await until(lambda: not h.virtual._temps)
    clock.t += 300                                                             # 900 s seit der Zustellung
    others = await commands_waiting(h, cul, 4)
    h.virtual.tick()                                                           # zuletzt versucht vor 300 s
    await answering(cul, until(lambda: len(on_air(cul)) == 7))
    assert on_air(cul)[2:] == [*(f"{a:06X}" for a in others), "42"]           # wartet hinten


async def test_addressed_form_reaches_every_thermostat_within_the_interval(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=0)
    start = clock.t
    times = {HT: [], HT2: []}
    h.virtual.set_measured(VW, 22.0)
    for _ in range(31):                                                        # 30 min in Minutenschritten
        await asyncio.sleep(0.02)
        for l in temps(cul)[sum(map(len, times.values())):]:
            dst = int(l[16:22], 16)
            times[dst].append(clock.t)
            ack(cul, l, dst)
        await until(lambda: not h.virtual._temps)
        clock.t += 60; h.virtual.tick()
    for got in times.values():
        gaps = [b - a for a, b in zip([start, *got], got)]
        assert got and max(gaps) <= virtual_wall.WT_INTERVAL_S + 60, gaps
    assert len(temps(cul)) <= 31 * 60 // (virtual_wall.WT_INTERVAL_S / 2) + 1


async def test_room_group_with_differing_groups_is_logged(hub, caplog):
    h, cul, _ = hub; room(h, mates=(HT2, HT3), group=7)
    h.devices[HT3].group = 8
    caplog.set_level(logging.WARNING)
    h.link(HT, VW); await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: h.devices[HT].pending_group is not None)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING and "group" in r.getMessage()]
    assert len(warnings) == 1 and "7" in warnings[0] and "8" in warnings[0]


# Two modules: main (USB) and "og"; with network=True "og" is a network module.

OG_HT = 0xA1B007
OG_HT2 = 0xA1B013


def _network(open_fn):
    async def _open(target):
        return await open_fn(target)

    _open.network = True
    return _open


@pytest.fixture
async def modules(request):
    network = getattr(request, "param", False)
    main, og = FakeCul(), FakeCul("V 1.26.08 a-culfw CUBE")
    h = MaxHub(
        "/dev/serial/by-path/eg", CENTRAL, [
            *devices(),
            MaxDevice(OG_HT, "MEQ9000003", DeviceType.HEATING_THERMOSTAT, name="ht-og", radio="og"),
            MaxDevice(OG_HT2, "MEQ9000024", DeviceType.HEATING_THERMOSTAT, name="ht-og2", radio="og"),
        ],
        on_update=lambda d: None, on_button=lambda d, t: None, on_device_added=lambda d: None,
        on_problem=lambda *a: None, open_connection=main.open, ack_timeout=0.05,
        radios=[RadioSpec("og", "192.0.2.60:2323", _network(og.open) if network else og.open)],
        now=lambda: 1_700_000_000.0, local_now=lambda: datetime(2026, 10, 9, 12, 0),
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, main, og
    await h.stop()


async def test_group_telegram_goes_through_the_thermostats_module(modules):
    h, main, og = modules; room(h, mates=(OG_HT, OG_HT2), group=5)            # WT selbst am Hauptmodul
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(og)) == 1)
    assert temps(og)[0][6:] == "0442111111000000052ADC" and temps(main) == []


async def test_thermostats_on_different_modules_get_it_addressed_each_through_its_own(modules):
    h, main, og = modules; clock = use_clock(h); room(h, mates=(HT, OG_HT), group=5)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(main)) == 1)
    assert temps(main)[0][6:22] == f"0042111111{HT:06X}"
    ack(main, temps(main)[0], HT)
    await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += virtual_wall.WT_INTERVAL_S / 2; h.virtual.tick()
    await until(lambda: len(temps(og)) == 1)
    assert temps(og)[0][6:22] == f"0042111111{OG_HT:06X}"


@pytest.mark.parametrize("modules", [True], indirect=True)
async def test_no_link_of_a_thermostat_on_a_network_module(modules):
    h, main, og = modules
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    with pytest.raises(FrameError) as err:
        h.link(OG_HT, VW)
    assert err.value.key == "virtual_network_radio"
    with pytest.raises(FrameError):
        h.link(VW, OG_HT)
    assert h.devices[VW].links == [] and h.devices[OG_HT].pending_links == []
    await asyncio.sleep(0.05)
    assert sent(main) == [] and sent(og) == []


@pytest.mark.parametrize("modules", [True], indirect=True)
async def test_no_move_of_a_linked_thermostat_to_a_network_module(modules):
    h, main, og = modules; room(h, mates=(HT,))
    with pytest.raises(FrameError) as err:
        h.set_radio(HT, "og")
    assert err.value.key == "virtual_network_radio" and h.devices[HT].radio == ""
    h.set_radio(thermostat(h, HT2).address, "og")                             # ohne virtuelles WT erlaubt
    assert h.devices[HT2].radio == "og"


async def test_a_room_temperature_refused_by_lovf_costs_nothing_and_is_built_anew(hub, caplog):
    """The group telegram expects no acknowledgement: a LOVF right after it means it never
    went out - no airtime, no sent_at, no attempt; built anew after the back-off, with one
    INFO line per back-off."""
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    caplog.set_level(logging.INFO)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: len(temps(cul)) == 1)
    cul.feed("LOVF")
    await until(lambda: not h.virtual._temps)
    assert h.devices[VW].sent_at is None and h.airtime_last_hour == 0
    assert VW not in h.virtual._attempted_at
    clock.t += virtual_wall.WT_LOVF_BACKOFF_S - 1
    h.virtual.tick(); h.virtual.set_measured(VW, 22.5); await asyncio.sleep(0.1)
    assert len(temps(cul)) == 1                                                # Pause nach LOVF
    lovf = [r for r in caplog.records if "LOVF" in r.getMessage() and r.levelno >= logging.INFO]
    assert len(lovf) == 1 and "again in 60 s" in lovf[0].getMessage()
    clock.t += 1; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 2)
    await until(lambda: h.devices[VW].sent_at is not None)


# --- F2: a window change goes out at once ---


async def window_room(h, group=5, mates=(HT,)):
    room(h, mates=mates, group=group); vc = linked_contact(h, to=VW)
    vc.window_open = False
    return vc


async def test_window_opened_goes_out_at_once_with_the_window_temperature(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    h, cul, _ = hub; clock = use_clock(h); await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    await until(lambda: h.devices[VW].sent_at is not None)
    clock.t += 30                                                              # Intervall läuft noch
    h.virtual.set_window(VC, True)
    await until(lambda: len(temps(cul)) == 2)
    assert temps(cul)[1].endswith("18DC")                                      # 12,0 Fenster-auf
    await until(lambda: not h.virtual._temps)
    clock.t += virtual_wall.WT_WINDOW_GAP_S
    h.virtual.set_window(VC, False)
    await until(lambda: len(temps(cul)) == 3)
    assert temps(cul)[2].endswith("2ADC")                                      # 21,0 wieder normal
    await until(lambda: not h.virtual._temps)
    clock.t += virtual_wall.WT_INTERVAL_S - 1; h.virtual.tick(); await asyncio.sleep(0.05)
    assert len(temps(cul)) == 3                                                # Takt beginnt neu
    clock.t += 1; h.virtual.tick(); await until(lambda: len(temps(cul)) == 4)


async def test_a_second_window_change_within_a_minute_goes_when_it_is_over(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    monkeypatch.setattr(virtual_wall, "WT_WINDOW_GAP_S", 1.0)
    h, cul, _ = hub; loop = asyncio.get_running_loop(); h._now = loop.time; await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    opened = loop.time()
    h.virtual.set_window(VC, True)
    await until(lambda: len(temps(cul)) == 2)
    await until(lambda: not h.virtual._temps)
    h.virtual.set_window(VC, False)
    await asyncio.sleep(0.3)
    assert len(temps(cul)) == 2                                                # innerhalb der Minute: wartet
    await until(lambda: len(temps(cul)) == 3)
    assert loop.time() - opened >= 0.95 and temps(cul)[2].endswith("2ADC")


async def test_a_window_change_replaces_a_waiting_telegram(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    h, cul, _ = hub; await window_room(h)
    thermostat(h, 0x150001)
    h.set_temperature(0x150001, 19.0, Mode.MANUAL)                            # belegt den Funk
    h.virtual.set_measured(VW, 22.0)
    old = h.virtual._temps[VW]
    h.virtual.set_window(VC, True)
    await until(lambda: h.virtual._temps.get(VW) not in (None, old))
    await until(lambda: len(temps(cul)) == 1)
    await asyncio.sleep(0.1)
    assert [l[-4:] for l in temps(cul)] == ["18DC"]                            # nur der neue


async def test_addressed_a_window_change_reaches_every_thermostat(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    h, cul, _ = hub; clock = use_clock(h); await window_room(h, group=0, mates=(HT, HT2))
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    ack(cul, temps(cul)[0], HT)
    await until(lambda: not h.virtual._temps)
    clock.t += 10
    h.virtual.set_window(VC, True)
    await until(lambda: len(temps(cul)) == 2)
    ack(cul, temps(cul)[1], int(temps(cul)[1][16:22], 16))
    await until(lambda: len(temps(cul)) == 3)                                  # gleich danach das andere
    assert {temps(cul)[1][16:22], temps(cul)[2][16:22]} == {f"{HT:06X}", f"{HT2:06X}"}
    assert temps(cul)[1].endswith("18DC") and temps(cul)[2].endswith("18DC")


async def test_a_real_contacts_change_goes_out_at_once(hub):
    h, cul, _ = hub; clock = use_clock(h); room(h, mates=(HT,), group=5)
    fk = h.devices[FK]
    fk.links.append(h.devices[VW].serial); h.devices[VW].links.append(fk.serial)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    await until(lambda: not h.virtual._temps)
    clock.t += 30
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, VW, 0, "12"))    # offen
    await until(lambda: len(temps(cul)) == 2)
    assert temps(cul)[1].endswith("18DC")


# --- Fix round: window telegram limits, restart cadence, LOVF log, timers ---


async def test_a_window_flip_while_the_window_telegram_is_on_air_waits_for_the_gap(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    monkeypatch.setattr(virtual_wall, "WT_WINDOW_GAP_S", 1.0)
    h, cul, _ = hub; loop = asyncio.get_running_loop(); h._now = loop.time; await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    await until(lambda: not h.virtual._temps)
    opened = loop.time()
    h.virtual.set_window(VC, True)
    await until(lambda: len(temps(cul)) == 2)                                  # "offen" in der Luft (LOVF-Wartezeit)
    assert h.virtual._temps[VW].first_sent_at is not None
    h.virtual.set_window(VC, False)                                            # zu, während es noch sendet
    await asyncio.sleep(0.6)
    assert len(temps(cul)) == 2                                                # nicht gleich hinterher
    await until(lambda: len(temps(cul)) == 3, timeout=3)
    assert loop.time() - opened >= 0.95 and temps(cul)[2].endswith("2ADC")


async def test_immediate_window_telegrams_have_an_hourly_budget(hub, monkeypatch, caplog):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    monkeypatch.setattr(virtual_wall, "WT_WINDOW_GAP_S", 0.0)
    monkeypatch.setattr(virtual_wall, "WT_WINDOW_HOUR_MAX", 2)
    caplog.set_level(logging.WARNING)
    h, cul, _ = hub; clock = use_clock(h); await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    await until(lambda: not h.virtual._temps)
    for count, state in ((2, True), (3, False)):
        clock.t += 1
        h.virtual.set_window(VC, state)
        await until(lambda c=count: len(temps(cul)) == c)
        await until(lambda: not h.virtual._temps)
    for state in (True, False, True):                                         # Budget erschöpft
        clock.t += 1
        h.virtual.set_window(VC, state)
        await asyncio.sleep(0.1)
    assert len(temps(cul)) == 3
    assert len([r for r in caplog.records if "within the hour" in r.getMessage()]) == 1
    clock.t += virtual_wall.WT_INTERVAL_S; h.virtual.tick()                   # der reguläre trägt es
    await until(lambda: len(temps(cul)) == 4)
    assert temps(cul)[3].endswith("18DC")


async def test_a_window_change_keeps_the_lovf_back_off(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    h, cul, _ = hub; clock = use_clock(h); await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    cul.feed("LOVF")
    await until(lambda: VW in h.virtual._retry_at)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.2)
    assert len(temps(cul)) == 1                                                # Pause gilt weiter
    clock.t += virtual_wall.WT_LOVF_BACKOFF_S; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 2)
    assert temps(cul)[1].endswith("18DC")


async def test_after_a_restart_a_recent_telegram_sets_the_cadence(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = room(h, group=5)
    vw.sent_at, vw.sent_measured = clock.t - 100, 22.0                         # aus dem Store
    h.virtual.set_measured(VW, 22.0); await asyncio.sleep(0.1)
    assert temps(cul) == []
    clock.t += 199; h.virtual.tick(); await asyncio.sleep(0.05)
    assert temps(cul) == []
    clock.t += 1; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 1)


async def test_lovf_is_logged_once_until_a_telegram_goes_out(hub, caplog):
    h, cul, _ = hub; clock = use_clock(h); room(h, group=5)
    caplog.set_level(logging.INFO)
    h.virtual.set_measured(VW, 22.0)
    for count in (1, 2):
        await until(lambda c=count: len(temps(cul)) == c)
        cul.feed("LOVF")
        await until(lambda: VW in h.virtual._retry_at and not h.virtual._temps)
        clock.t += virtual_wall.WT_LOVF_BACKOFF_S; h.virtual.tick()
    await until(lambda: len(temps(cul)) == 3)
    assert len([r for r in caplog.records if "LOVF" in r.getMessage() and r.levelno >= logging.INFO]) == 1


async def test_room_timers_end_with_stop_unlink_and_removal(hub, monkeypatch):
    """No callback after stop(), after the last thermostat left, or after removal: with the
    times shortened, nothing more goes out once they are due."""
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    monkeypatch.setattr(virtual_wall, "WT_INTERVAL_S", 0.2)
    monkeypatch.setattr(virtual_wall, "WT_WINDOW_GAP_S", 0.2)
    h, cul, _ = hub; loop = asyncio.get_running_loop(); h._now = loop.time
    vc = await window_room(h)
    h.virtual.set_measured(VW, 22.0); await until(lambda: len(temps(cul)) == 1)
    h.virtual.set_window(VC, True); h.virtual.set_window(VC, False)
    await asyncio.sleep(0.05)
    for action in ("unlink", "remove", "stop"):
        if action == "unlink":
            ht = h.devices[HT]
            ht.links.remove(h.devices[VW].serial)
            h.virtual.link_committed(ht, h.devices[VW].serial, "remove")
        elif action == "remove":
            room(h, wall=VW2, mates=(HT2,), group=6)
            h.virtual.set_measured(VW2, 21.0); await until(lambda: VW2 in h.virtual._wall_timers or h.virtual._temps.get(VW2))
            h.virtual.remove(VW2, force=True)
            assert VW2 not in h.virtual._wall_timers and VW2 not in h.virtual._window_timers
        else:
            h.virtual.stop()
            assert not h.virtual._wall_timers and not h.virtual._window_timers and not h.virtual._gap_timers
    assert VW not in h.virtual._wall_timers
    everything = lambda: [l for l in cul.all_written + cul.written if l.startswith("Zs") and l[8:10] in ("42", "30")]
    count = len(everything())
    await asyncio.sleep(0.6)
    assert len(everything()) == count


async def test_after_a_restart_an_addressed_room_reaches_every_thermostat_in_time(hub):
    h, cul, _ = hub; clock = use_clock(h); vw = room(h, group=0)               # zwei Thermostate, adressiert
    vw.sent_at, vw.sent_measured = clock.t - 1, 22.0                           # 1 s vor dem Neustart
    start = clock.t
    h.virtual.set_measured(VW, 22.0)
    reached = set()
    while clock.t - start <= virtual_wall.WT_INTERVAL_S:
        await asyncio.sleep(0.01)
        for l in temps(cul):
            dst = int(l[16:22], 16)
            if dst not in reached:
                reached.add(dst)
                ack(cul, l, dst)
        await until(lambda: not h.virtual._temps)
        clock.t += 10; h.virtual.tick()
    assert reached == {HT, HT2}
