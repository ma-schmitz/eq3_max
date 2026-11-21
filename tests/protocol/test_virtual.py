"""Virtual devices in the hub: created, acknowledged for, their acknowledgements delivered."""

import asyncio
import contextlib
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol import virtual, virtual_wall
from custom_components.eq3_max.protocol.devices import LINK_WAITING, WEEKDAYS, MaxDevice
from custom_components.eq3_max.protocol.hub import MaxHub, RadioSpec
from custom_components.eq3_max.protocol.messages import (
    DeviceType,
    FrameError,
    Mode,
    Frame,
    MsgType,
    ProfilePoint,
    build_shutter_contact_state,
    encode_until,
)
from custom_components.eq3_max.protocol.scheduler import Command, Outcome

from .fakes import FakeCul, line, until
from .hubkit import CENTRAL, FK, HT, HT2, HT3, PB, VC, VW, WT, devices, linked_contact, room, sent, thermostat



def fast(cul):
    return [l for l in cul.written if l.startswith("Zf")]


async def test_create_gives_serial_and_reports(hub):
    h, cul, rec = hub
    dev = h.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.buero")
    assert dev.virtual and dev.serial == f"VIRT{dev.address:06X}" and dev.address not in (0, CENTRAL)
    assert dev.name == "Büro" and dev.source == "sensor.buero"
    assert h.devices[dev.address] is dev and rec.added == [dev] and sent(cul) == []
    assert h.virtual.is_virtual(dev.address) and not h.virtual.is_virtual(HT)


async def test_create_rejects_other_types(hub):
    with pytest.raises(FrameError) as err:
        hub[0].virtual.create(DeviceType.PUSH_BUTTON, "x", "event.x")
    assert err.value.key == "virtual_type"


async def test_every_telegram_to_a_virtual_address_is_acknowledged(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.buero", address=VW)
    h.devices[VW].target, h.devices[VW].mode = 21.0, Mode.MANUAL
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: any(l.startswith("Zf") for l in cul.written))
    assert f"Zf0E090202111111{HT:06X}000119042A" in cul.written


async def test_wall_thermostat_without_target_acknowledges_like_a_contact(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.buero", address=VW)
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0B090202111111{HT:06X}0000"]


async def test_ack_once_per_telegram_but_again_for_a_repeat_counter(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    for _ in range(2):
        cul.feed(line(1, 0x04, MsgType.WAKE_UP, HT, VC, 0, "03"))
    await until(lambda: len(fast(cul)) >= 1)
    await asyncio.sleep(0.02)
    assert fast(cul) == [f"Zf0B010202222222{HT:06X}0000"]
    await asyncio.sleep(0.6)                        # ACK_GUARD_S vorbei: gleiche Nummer = neues Telegramm
    cul.feed(line(1, 0x04, MsgType.WAKE_UP, HT, VC, 0, "03"))
    await until(lambda: len(fast(cul)) == 2)


async def test_acks_to_a_virtual_address_are_not_answered(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    cul.feed(line(1, 0x02, MsgType.ACK, HT, VC, 0, "00"))
    await asyncio.sleep(0.05)
    assert fast(cul) == []


async def test_a_removing_device_is_still_acknowledged(hub):
    h, cul, _ = hub
    dev = h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    dev.removing = True
    cul.feed(line(1, 0x04, MsgType.WAKE_UP, HT, VC, 0, "03"))
    await until(lambda: len(fast(cul)) == 1)


async def test_acks_to_a_virtual_address_reach_the_scheduler(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    outcome = asyncio.create_task(
        h._await_command(Command(dst=HT, build=lambda c: build_shutter_contact_state(c, VC, HT, True)))
    )
    await until(lambda: len(sent(cul)) == 1)
    counter = int(sent(cul)[0][4:6], 16)
    cul.feed(line(counter, 0x02, MsgType.ACK, HT, VC, 0, "0119002A"))
    assert await outcome is Outcome.ACKED


async def test_submit_through_a_given_module():
    """A telegram to 000000 has no device to route by: it goes through the module named."""
    main, og = FakeCul(), FakeCul()
    h = MaxHub(
        "/dev/x", CENTRAL, devices(),
        on_update=lambda d: None, on_button=lambda d, t: None, on_device_added=lambda d: None,
        on_problem=lambda *a: None, open_connection=main.open, ack_timeout=0.05,
        radios=[RadioSpec("og", "192.0.2.60:2323", og.open)],
    )
    await h.start()
    await until(lambda: h.connected)
    try:
        h._submit(Command(dst=0, build=lambda c: build_shutter_contact_state(c, VC, 0, True), expects_ack=False), "og")
        await until(lambda: len(sent(og)) == 1)
        assert sent(main) == []
    finally:
        await h.stop()


# --- network main module: the firmware answers the central, the hub the virtual devices ---


def _network(open_fn):
    async def _open(target):
        return await open_fn(target)

    _open.network = True
    return _open


async def test_network_main_module_still_acknowledges_virtual_devices():
    cul = FakeCul("V 1.26.08 a-culfw CUBE")
    h = MaxHub(
        "192.0.2.60:2323", CENTRAL, devices(),
        on_update=lambda d: None, on_button=lambda d, t: None, on_device_added=lambda d: None,
        on_problem=lambda *a: None, open_connection=_network(cul.open), ack_timeout=0.05,
        transport_kwargs={"health_interval": 0},
    )
    await h.start()
    await until(lambda: h.connected)
    try:
        assert h.radio_is_network("") and not h.radio_is_network("og")
        wall = h.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.buero")   # no module of its own
        with pytest.raises(FrameError) as err:
            h.link(HT, wall.address)                                   # HT is on the network main module
        assert err.value.key == "virtual_network_radio"
        h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
        cul.feed(line(1, 0x04, MsgType.WAKE_UP, HT, VC, 0, "03"))
        await until(lambda: len(fast(cul)) == 1)
        assert fast(cul) == [f"Zf0B010202222222{HT:06X}0000"]
    finally:
        await h.stop()


async def test_usb_main_module_is_not_a_network_module(hub):
    assert not hub[0].radio_is_network("")


# --- Linking (task 5) ---

WT2 = 0x333333


async def test_link_real_thermostat_with_virtual_wall(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.b", address=VW)
    h.link(HT, VW)
    assert h.devices[HT].serial in h.devices[VW].links            # at once, nothing on air for it
    assert h.devices[VW].pending_links == []
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith(f"20{CENTRAL:06X}{HT:06X}0011111103")
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: "VIRT111111" in h.devices[HT].links)
    assert h.devices[HT].pending_links == []


async def test_link_real_thermostat_with_virtual_contact(hub):
    h, cul, rec = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.link(VC, HT)
    assert h.devices[HT].serial in h.devices[VC].links
    assert h.devices[VC] in rec.updates
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith(f"20{CENTRAL:06X}{HT:06X}0022222204")


async def test_real_contact_waits_for_its_telegram_the_virtual_side_does_not(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(FK, VW)
    assert h.devices[FK].serial in h.devices[VW].links
    assert h.devices[FK].link_op("VIRT111111")["state"] == LINK_WAITING
    await asyncio.sleep(0.05)
    assert sent(cul) == []


async def test_two_virtual_devices_link_without_radio(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.link(VW, VC)
    assert "VIRT222222" in h.devices[VW].links and "VIRT111111" in h.devices[VC].links
    assert h.devices[VW].pending_links == [] and h.devices[VC].pending_links == []
    await asyncio.sleep(0.05)
    assert sent(cul) == []


async def test_second_wall_thermostat_is_refused(hub):
    h, _, _ = hub
    h.devices[HT].links.append(h.devices[WT].serial)
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    with pytest.raises(FrameError) as err:
        h.link(HT, VW)
    assert err.value.key == "link_second_wall"
    with pytest.raises(FrameError) as err:
        h.link(VW, HT)
    assert err.value.key == "link_second_wall"


async def test_real_wall_thermostat_refused_next_to_a_virtual_one(hub):
    h, _, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(HT, VW)                          # still pending at the thermostat
    with pytest.raises(FrameError) as err:
        h.link(HT, WT)
    assert err.value.key == "link_second_wall"


async def test_second_real_wall_thermostat_is_left_as_before(hub):
    h, cul, _ = hub
    h.devices[HT].links.append(h.devices[WT].serial)
    h.devices[WT2] = MaxDevice(WT2, "NEQ0000002", DeviceType.WALL_THERMOSTAT, name="wt-2")
    h.link(HT, WT2)
    await until(lambda: len(sent(cul)) >= 1)


async def test_virtual_wall_refuses_eco_button(hub):
    h, _, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    for a, b in ((PB, VW), (VW, PB)):
        with pytest.raises(FrameError) as err:
            h.link(a, b)
        assert err.value.key == "virtual_no_button"


async def test_unlink_commits_the_virtual_side_at_once(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.devices[VW].links.append(h.devices[HT].serial)
    h.devices[HT].links.append("VIRT111111")
    h.unlink(HT, VW)
    assert h.devices[VW].links == [] and h.devices[VW].pending_links == []
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith(f"21{CENTRAL:06X}{HT:06X}0011111103")
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: h.devices[HT].links == [])


async def test_forced_unlink_of_a_virtual_device_sends_nothing(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.unlink(VW, HT, force=True)
    assert h.devices[VW].pending_links == []
    await asyncio.sleep(0.05)
    assert sent(cul) == []                                                     # the virtual side: nothing
    h.unlink(HT, VW, force=True)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith(f"21{CENTRAL:06X}{HT:06X}0011111103")


async def test_unknown_partners_of_virtual_devices_are_forgotten(hub):
    h, _, _ = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.devices[VW].links.extend([h.devices[HT].serial, "MEQ0000000"])
    h.devices[HT].links.append("VIRT111111")
    h._forget_unknown_partners()
    assert h.devices[VW].links == [h.devices[HT].serial]
    assert h.devices[HT].links == ["VIRT111111"]


async def test_telegrams_from_a_virtual_address_are_echoes(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    before = h.devices[VC].window_open
    cul.feed(line(5, 0x06, MsgType.SHUTTER_CONTACT_STATE, VC, HT, 0, "12"))
    cul.feed(line(6, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
    await until(lambda: h.devices[FK].window_open is True)
    assert h.devices[VC].window_open == before and h.devices[VC].last_seen is None


# --- Task 6: the virtual window contact sends its state ---

SC_DEBOUNCE_S = 0.05


@pytest.fixture
def quick_debounce(monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", SC_DEBOUNCE_S)


def idle(h, address):
    return h._scheduler_for(address).pending() == []


async def test_open_and_close_are_sent_and_remembered(hub, quick_debounce):
    h, cul, rec = hub
    linked_contact(h)
    h.virtual.set_window(VC, True)
    assert h.devices[VC].window_open is True and h.devices[VC].source_ok and h.devices[VC] in rec.updates
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:] == f"0630222222{HT:06X}0012"
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, VC, 0, "01190018"))
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True})
    h.virtual.set_window(VC, False)
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][6:] == f"0630222222{HT:06X}0010"


async def test_window_changed_at_only_on_a_real_change(hub, quick_debounce):
    h, _, _ = hub
    linked_contact(h, delivered=True)
    h._now = lambda: 100.0
    h.virtual.set_window(VC, True)
    assert h.devices[VC].window_changed_at is None                 # first value, no change
    h._now = lambda: 200.0
    h.virtual.set_window(VC, False)
    h._now = lambda: 300.0
    h.virtual.set_window(VC, False)
    assert h.devices[VC].window_changed_at == 200.0


async def test_flapping_sends_only_the_last_state(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    for state in (True, False) * 5:
        h.virtual.set_window(VC, state)
    await asyncio.sleep(SC_DEBOUNCE_S + 0.3)
    assert sent(cul) == []                                         # last state = delivered state


async def test_flapping_ends_in_one_telegram(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    for state in (True, False, True):
        h.virtual.set_window(VC, state)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:] == f"0630222222{HT:06X}0012"
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, VC, 0, "01190018"))
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True} and idle(h, HT))
    await asyncio.sleep(SC_DEBOUNCE_S + 0.1)
    assert len(sent(cul)) == 1


async def test_same_state_after_restart_sends_nothing(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=True)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.2)
    assert sent(cul) == []


async def test_changed_state_after_restart_is_sent(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=True)
    h.virtual.set_window(VC, False)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("10")


async def test_start_sends_nothing(quick_debounce):
    cul = FakeCul()
    devs = devices()
    contact = MaxDevice(VC, "VIRT222222", DeviceType.SHUTTER_CONTACT, virtual=True, source="binary_sensor.f")
    contact.links, contact.window_open = ["MEQ9000007"], True
    devs[0].links = ["VIRT222222"]
    h = MaxHub("/dev/x", CENTRAL, [*devs, contact], on_update=lambda d: None, on_button=lambda d, t: None,
               on_device_added=lambda d: None, on_problem=lambda k: None, open_connection=cul.open,
               ack_timeout=0.05)
    await h.start()
    await until(lambda: h.connected)
    await asyncio.sleep(SC_DEBOUNCE_S + 0.1)
    assert sent(cul) == []
    await h.stop()


async def test_unacknowledged_state_is_repeated_when_the_thermostat_is_heard(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h)
    h.virtual.set_window(VC, True)
    await until(lambda: len(sent(cul)) >= 1 and idle(h, HT), timeout=5)
    assert h.devices[VC].delivered == {}
    before = len(sent(cul))
    cul.feed(line(0, 0x04, MsgType.THERMOSTAT_STATE, HT, 0, 0, "19002A00DC"))
    await until(lambda: len(sent(cul)) > before)
    assert sent(cul)[-1][6:] == f"0630222222{HT:06X}0012"


async def test_ack_of_the_thermostat_does_not_trigger_a_second_send(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h)
    h.virtual.set_window(VC, True)
    await until(lambda: len(sent(cul)) == 1)
    # The acknowledgement carries the thermostat's state: a sign of life while ours is on air.
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, VC, 0, "01190018"))
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True} and idle(h, HT))
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1


async def test_unavailable_source_sends_nothing(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    h.virtual.set_window(VC, None)
    await asyncio.sleep(0.2)
    assert sent(cul) == [] and h.devices[VC].source_ok is False


async def test_source_gone_during_the_debounce_sends_nothing(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    h.virtual.set_window(VC, True)
    h.virtual.set_window(VC, None)
    await asyncio.sleep(0.2)
    assert sent(cul) == []
    cul.feed(line(0, 0x04, MsgType.THERMOSTAT_STATE, HT, 0, 0, "19002A00DC"))
    await asyncio.sleep(0.1)
    assert sent(cul) == []


async def test_one_sided_and_virtual_partners_get_nothing(hub, quick_debounce):
    h, cul, _ = hub
    dev = h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    dev.links.extend([h.devices[HT].serial, "VIRT111111"])         # HT has not confirmed
    h.devices[VW].links.append(dev.serial)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.2)
    assert sent(cul) == []


async def test_a_removing_contact_sends_nothing(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h).removing = True
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.2)
    assert sent(cul) == []


async def test_new_link_gets_the_current_state(hub, quick_debounce):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.1)
    h.link(VC, HT)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][6:] == f"0630222222{HT:06X}0012"


async def test_unknown_state_is_not_sent_to_a_new_link(hub, quick_debounce):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.link(VC, HT)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(int(sent(cul)[0][4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: "VIRT222222" in h.devices[HT].links)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1


async def test_stop_cancels_a_pending_debounce(hub, quick_debounce):
    h, cul, _ = hub
    linked_contact(h)
    h.virtual.set_window(VC, True)
    await h.stop()
    await asyncio.sleep(SC_DEBOUNCE_S + 0.1)
    assert sent(cul) == []


async def test_set_window_on_an_unknown_device_is_refused(hub):
    with pytest.raises(FrameError):
        hub[0].virtual.set_window(HT, True)


def ack_for(cul, index, payload="01190018"):
    return line(int(sent(cul)[index][4:6], 16), 0x02, MsgType.ACK, HT, VC, 0, payload)


async def test_close_while_open_is_on_air_is_sent_after_it(hub, monkeypatch):
    h, cul, _ = hub
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    linked_contact(h, delivered=False)
    h.virtual.set_window(VC, True)
    await until(lambda: len(sent(cul)) == 1)
    h.virtual.set_window(VC, False)                                # "open" still waits for its ack
    await asyncio.sleep(0.02)                                      # debounce of "closed" over
    cul.feed(ack_for(cul, 0))
    await until(lambda: any(l.endswith("10") for l in sent(cul)), timeout=3)
    closed = next(i for i, l in enumerate(sent(cul)) if l.endswith("10"))
    cul.feed(ack_for(cul, closed))
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: False} and idle(h, HT), timeout=3)
    assert h.devices[VC].window_open is False


async def failed_once(h, cul):
    linked_contact(h)
    h.virtual.set_window(VC, True)
    await until(lambda: len(sent(cul)) >= 1 and idle(h, HT), timeout=5)
    return len(sent(cul))


def heard(cul):
    cul.feed(line(0, 0x04, MsgType.THERMOSTAT_STATE, HT, 0, 0, "19002A00DC"))


async def test_repeat_once_per_five_minutes_with_a_single_attempt(hub, quick_debounce):
    h, cul, _ = hub
    h._now = lambda: 1000.0
    n = await failed_once(h, cul)
    assert n == 4                                                  # first send: normal retries
    heard(cul)
    await until(lambda: len(sent(cul)) == n + 1)
    await until(lambda: idle(h, HT))
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == n + 1                                 # repeat: one attempt
    h._now = lambda: 1000.0 + virtual.SC_REPEAT_MIN_S - 1
    heard(cul)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == n + 1                                 # within 300 s: nothing
    h._now = lambda: 1000.0 + virtual.SC_REPEAT_MIN_S + 1
    heard(cul)
    await until(lambda: len(sent(cul)) == n + 2)


async def test_three_failures_warn_once(hub, quick_debounce, caplog):
    h, cul, _ = hub
    t = [1000.0]
    h._now = lambda: t[0]
    await failed_once(h, cul)
    warnings = lambda: [r for r in caplog.records if r.levelname == "WARNING" and "window state" in r.getMessage()]
    for i in range(1, 4):
        t[0] = 1000.0 + i * (virtual.SC_REPEAT_MIN_S + 1)
        before = len(sent(cul))
        heard(cul)
        await until(lambda: len(sent(cul)) > before and idle(h, HT))
        await asyncio.sleep(0.02)
        assert len(warnings()) == (0 if i < 2 else 1)


async def test_delivery_resets_the_failure_count(hub, quick_debounce, caplog):
    h, cul, _ = hub
    t = [1000.0]
    h._now = lambda: t[0]
    await failed_once(h, cul)
    t[0] += virtual.SC_REPEAT_MIN_S + 1
    before = len(sent(cul))
    heard(cul)
    await until(lambda: len(sent(cul)) > before)
    cul.feed(ack_for(cul, -1))
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True} and idle(h, HT))
    h.virtual.set_window(VC, False)
    await until(lambda: idle(h, HT) and sent(cul)[-1].endswith("10"))
    await until(lambda: idle(h, HT))
    assert not [r for r in caplog.records if r.levelname == "WARNING" and "window state" in r.getMessage()]


async def test_close_while_open_waits_in_the_queue_replaces_it(hub, monkeypatch):
    h, cul, _ = hub
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)
    linked_contact(h, delivered=False)
    h.set_temperature(HT, 21.0, Mode.MANUAL)                       # keeps the module busy
    await until(lambda: len(sent(cul)) == 1)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.03)                                      # "open" queued behind it
    h.virtual.set_window(VC, False)
    await asyncio.sleep(0.03)
    await until(lambda: any(l[8:10] == "30" for l in sent(cul)), timeout=3)
    contact = [l for l in sent(cul) if l[8:10] == "30"]
    assert contact and all(l.endswith("10") for l in contact)       # "open" never went on air


# --- Task 7: the virtual wall thermostat keeps its room's setpoint ---

WT_FORWARD_DELAY_S = 0.05


@pytest.fixture(autouse=True)
def quick_forward(monkeypatch):
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", WT_FORWARD_DELAY_S)


def set_to(cul, dst, payload):
    """Addressed 0x40 from the central, flags 00, to dst."""
    return [l for l in sent(cul) if l[6:] == f"0040{CENTRAL:06X}{dst:06X}00{payload}"]


def ack_all(cul, dst, payload="0119002A"):
    """Acknowledge the last telegram to dst (payload: its state, manual 21.0)."""
    last = next(l for l in reversed(sent(cul)) if l[16:22] == f"{dst:06X}")
    cul.feed(line(int(last[4:6], 16), 0x02, MsgType.ACK, dst, CENTRAL, 0, payload))


async def test_handwheel_change_is_adopted_acknowledged_with_new_target_and_forwarded(hub):
    h, cul, _ = hub; room(h)
    h.devices[HT2].group = 5                                                    # group=0: still flags 00
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))          # manuell 21,5
    await until(lambda: h.devices[VW].target == 21.5)
    assert f"Zf0E090202111111{HT:06X}000119042B" in cul.written                # Quittung mit neuem Soll
    await until(lambda: len(sent(cul)) == 1, timeout=WT_FORWARD_DELAY_S + 2)
    assert sent(cul)[0][6:] == f"0040{CENTRAL:06X}{HT2:06X}006B"               # nur an das andere, Flags 00
    assert h.devices[VW].mode is Mode.MANUAL
    assert h.devices[HT2].pending_target == 21.5


async def test_setpoint_on_virtual_wall_goes_to_every_thermostat(hub):
    h, cul, _ = hub; room(h)
    h.set_temperature(VW, 19.0, Mode.MANUAL)
    assert h.devices[VW].target == 19.0 and h.devices[VW].pending_target is None
    assert h.devices[HT].pending_target == 19.0 and h.devices[HT2].pending_target == 19.0
    await until(lambda: len(sent(cul)) >= 1)
    first = HT if set_to(cul, HT, "66") else HT2
    ack_all(cul, first)
    other = HT2 if first == HT else HT
    await until(lambda: set_to(cul, other, "66"))


async def test_setpoint_on_a_member_is_a_room_change(hub):
    h, cul, _ = hub; room(h)
    h.set_temperature(HT, 19.0, Mode.MANUAL)
    assert h.devices[VW].target == 19.0
    assert h.devices[HT].pending_target == 19.0 and h.devices[HT2].pending_target == 19.0


async def test_temporary_setpoint_carries_its_end_time_to_the_room(hub):
    h, cul, _ = hub; room(h)
    end = datetime(2026, 10, 10, 18, 30)
    h.set_temperature(HT2, 22.0, Mode.TEMPORARY, end)
    vw = h.devices[VW]
    assert (vw.target, vw.mode, vw.until) == (22.0, Mode.TEMPORARY, end)
    assert h.devices[HT].pending_until == end


async def test_poke_bypasses_the_room(hub):
    h, cul, _ = hub; room(h)
    h.devices[HT].target, h.devices[HT].mode = 21.0, Mode.MANUAL
    h._poke(h.devices[HT], 1_700_000_000.0)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][16:22] == f"{HT:06X}"
    assert h.devices[VW].target == 21.0 and h.devices[HT2].pending_target is None


async def test_first_link_adopts_from_the_thermostat(hub):
    h, cul, _ = hub
    h.devices[HT].target, h.devices[HT].mode = 20.5, Mode.AUTO
    # A whole week (automatic mode needs a known program).
    h.devices[HT].week_profile = {day: [{"temperature": 17.0, "until": "24:00"}] for day in WEEKDAYS}
    h.devices[HT].config["komfort"] = 22.0
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(HT, VW)
    vw = h.devices[VW]
    assert (vw.target, vw.mode, vw.week_profile, vw.config["komfort"]) == (17.0, Mode.AUTO, h.devices[HT].week_profile, 22.0)
    assert vw.week_profile is not h.devices[HT].week_profile


async def test_next_link_gets_the_room_setpoint_after_its_acknowledgement(hub):
    h, cul, _ = hub
    room(h, mates=(HT,))
    ht2 = thermostat(h, HT2)
    ht2.target, ht2.mode = 18.0, Mode.MANUAL
    h.link(HT2, VW)
    assert h.devices[VW].target == 21.0                                         # not the first: nothing adopted
    await until(lambda: len(sent(cul)) >= 1)
    assert sent(cul)[0][8:10] == "20"
    ack_all(cul, HT2, "01190024")                                               # still at 18.0
    await until(lambda: set_to(cul, HT2, "6A"))
    assert not set_to(cul, HT, "6A")


async def test_next_link_with_the_room_setpoint_already_gets_nothing(hub):
    h, cul, _ = hub
    room(h, mates=(HT,))
    ht2 = thermostat(h, HT2)
    ht2.target, ht2.mode = 21.0, Mode.MANUAL
    h.link(HT2, VW)
    await until(lambda: len(sent(cul)) >= 1)
    ack_all(cul, HT2)
    await until(lambda: h.devices[VW].serial in ht2.links)
    await asyncio.sleep(0.05)
    assert all(l[8:10] in ("20", "22") for l in sent(cul))  # link, group id; no 0x40


async def test_virtual_wall_never_gets_radio_commands(hub):
    h, cul, _ = hub; room(h, mates=())
    h.set_config(VW, "komfort", 22.5); h.set_group(VW, 3)
    await asyncio.sleep(0.1)
    assert sent(cul) == [] and h.devices[VW].config["komfort"] == 22.5 and h.devices[VW].group == 3
    assert h.devices[VW].pending_config == {} and h.devices[VW].pending_group is None


async def test_config_of_the_virtual_wall_is_shared_with_the_room(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    h.set_config_set(VW, "temp", {"komfort": 22.5, "eco": 16.0})
    assert h.devices[VW].config["eco"] == 16.0 and h.devices[VW].pending_config == {}
    await until(lambda: len(sent(cul)) >= 1)
    assert {l[16:22] for l in sent(cul)} == {f"{HT:06X}"}
    assert h.devices[HT].pending_config["temp"]["komfort"] == 22.5


async def test_week_profile_of_the_virtual_wall_is_stored_and_written_to_the_room(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    task = asyncio.create_task(h.set_week_profile(VW, {2: [ProfilePoint(17.0, 1440)]}))
    await until(lambda: len(sent(cul)) >= 1)
    assert h.devices[VW].week_profile == {"Montag": [{"temperature": 17.0, "until": "24:00"}]}
    assert {l[16:22] for l in sent(cul)} == {f"{HT:06X}"}
    assert h.devices[HT].week_profile_writing == ["Montag"]
    assert not task.done()  # the call ends when the room has the days
    ack_all(cul, HT)
    await asyncio.wait_for(task, 1.0)
    assert h.devices[HT].week_profile == h.devices[VW].week_profile


async def test_changes_at_a_member_reach_the_virtual_wall_without_radio(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    h.set_config(HT, "komfort", 22.5)
    assert h.devices[VW].config["komfort"] == 22.5 and h.devices[VW].pending_config == {}
    task = asyncio.create_task(h.set_week_profile(HT, {2: [ProfilePoint(17.0, 1440)]}))
    assert h.devices[VW].week_profile == {}
    await until(lambda: h.devices[VW].week_profile == {"Montag": [{"temperature": 17.0, "until": "24:00"}]})
    h.set_room_group(HT)
    assert h.devices[VW].group == h.devices[HT].pending_group != 0
    await asyncio.sleep(0.1)
    assert all(l[16:22] == f"{HT:06X}" for l in sent(cul))
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def test_restore_skips_a_virtual_device(hub):
    h, cul, _ = hub; room(h)
    h._restore(h.devices[VW])
    await asyncio.sleep(0.05)
    assert sent(cul) == [] and h.devices[VW].links == [h.devices[HT].serial, h.devices[HT2].serial]


async def test_boost_at_a_thermostat_is_acknowledged_but_not_forwarded(hub):
    """Measured 20.11.2026: the real wall thermostat answers 0x1B and keeps the boost to itself.
    Only that thermostat boosts: the room (the wall thermostat's entity) keeps its mode."""
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "EA"))          # Boost, 21,0
    await until(lambda: f"Zf0E090202111111{HT:06X}00011B042A" in cul.written)
    await until(lambda: h.devices[HT].mode is Mode.BOOST)
    assert h.devices[VW].mode is Mode.MANUAL and h.devices[VW].target == 21.0
    cul.feed(line(10, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6A"))         # boost over: manual 21,0
    await until(lambda: h.devices[HT].mode is Mode.MANUAL)
    assert h.devices[VW].mode is Mode.MANUAL
    assert f"Zf0E0A0202111111{HT:06X}000119042A" in cul.written
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert sent(cul) == []


async def test_unchanged_setpoint_is_not_forwarded(hub):
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6A"))          # manuell 21,0 = Raum
    await until(lambda: len(fast(cul)) == 1)
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert sent(cul) == []


async def test_repeated_setpoint_telegram_is_taken_once(hub):
    h, cul, rec = hub; room(h)
    for _ in range(2):
        cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: len(sent(cul)) == 1, timeout=WT_FORWARD_DELAY_S + 2)
    ack_all(cul, HT2)
    await until(lambda: idle(h, HT2))
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert len(fast(cul)) == 1 and len(sent(cul)) == 1


async def test_ack_payload_never_raises(hub, monkeypatch):
    h, cul, _ = hub; vw = room(h)
    vw.target = 31.0                                                            # outside 4.5..30.5
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0B090202111111{HT:06X}0000"]
    vw.target = 21.0

    def broken(*_args):
        raise ValueError("broken")

    monkeypatch.setattr(virtual_wall, "encode_wall_ack", broken)
    cul.feed(line(10, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: len(fast(cul)) == 2)
    assert fast(cul)[1] == f"Zf0B0A0202111111{HT:06X}0000"


async def test_setpoint_below_off_is_acknowledged_but_not_taken(hub):
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "44"))          # manuell 2,0
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0E090202111111{HT:06X}000119042A"]
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert h.devices[VW].target == 21.0 and sent(cul) == []


async def test_setpoint_from_a_device_not_linked_on_both_sides_changes_nothing(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT2,))
    vw.links.append(h.devices[HT].serial)                                        # one-sided: HT does not carry VW
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    thermostat(h, HT3).links.append(vw.serial)                                   # the other way round
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT3, VW, 0, "6B"))
    await until(lambda: len(fast(cul)) == 2)
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert vw.target == 21.0 and sent(cul) == []


async def test_one_sided_mates_get_nothing(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,))
    vw.links.append(thermostat(h, HT2).serial)                                   # HT2 has not acknowledged yet
    h.set_temperature(VW, 19.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) >= 1)
    await asyncio.sleep(0.1)
    assert {l[16:22] for l in sent(cul)} == {f"{HT:06X}"}
    assert h.devices[HT2].pending_target is None


async def test_a_removing_wall_thermostat_acknowledges_but_takes_nothing(hub):
    h, cul, _ = hub; vw = room(h)
    vw.removing = True
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: len(fast(cul)) == 1)
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert vw.target == 21.0 and sent(cul) == []
    h.set_temperature(HT, 19.0, Mode.MANUAL)                                   # no room any more: only HT
    assert vw.target == 21.0 and h.devices[HT2].pending_target is None


async def test_window_state_of_linked_contacts(hub):
    h, cul, _ = hub; vw = room(h)
    vw.links.append(h.devices[FK].serial)
    h.devices[FK].links.append(vw.serial)
    assert h.virtual.window_open(VW) is False
    cul.feed(line(3, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, VW, 0, "12"))
    await until(lambda: h.virtual.window_open(VW))
    assert f"Zf0E030202111111{FK:06X}000119042A" in cul.written
    cul.feed(line(4, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, VW, 0, "10"))
    await until(lambda: not h.virtual.window_open(VW))
    vc = h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.link(VC, VW)
    h.virtual.set_window(VC, True)
    assert h.virtual.window_open(VW) is True


async def test_stop_cancels_a_pending_forward(hub):
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: h.devices[VW].target == 21.5)
    h.virtual.stop()
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert sent(cul) == []


async def test_setpoint_from_home_assistant_replaces_a_pending_forward(hub):
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: h.devices[VW].target == 21.5)
    h.set_temperature(VW, 19.0, Mode.MANUAL)
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.2)
    assert not set_to(cul, HT2, "6B")


# --- Task 7, fix round 1 ---


async def test_home_assistant_hears_of_a_reported_setpoint_after_the_acknowledgement(hub):
    h, cul, _ = hub; room(h)
    ack = f"Zf0E090202111111{HT:06X}000119042B"
    seen = []
    h._on_update = lambda dev: seen.append((dev.address if dev else None, ack in cul.written))
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: (VW, True) in seen)
    assert all(written for address, written in seen if address in (VW, HT))


async def test_reported_setpoint_replaces_the_senders_pending_one(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    ht = h.devices[HT]
    ht.set_pending(19.0, Mode.MANUAL)
    ht.command_failed = True
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))
    await until(lambda: ht.target == 21.5)
    assert ht.mode is Mode.MANUAL and not ht.has_pending and not ht.command_failed
    cul.feed(line(10, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19002B00DC"))
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert not set_to(cul, HT, "66") and sent(cul) == []


async def test_temporary_without_end_time_is_answered_but_not_taken(hub):
    """It would end at once (an away period ends at its end time): the answer carries it,
    so the thermostat is satisfied; the room stays as it was."""
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "AC"))          # temporär 22,0, keine Endzeit
    await until(lambda: len(fast(cul)) == 1)
    assert fast(cul) == [f"Zf0E090202111111{HT:06X}00011A042C"]
    vw = h.devices[VW]
    assert (vw.mode, vw.target, vw.until) == (Mode.MANUAL, 21.0, None)
    await asyncio.sleep(WT_FORWARD_DELAY_S + 0.1)
    assert sent(cul) == []


async def test_expired_temporary_is_not_forwarded(hub, monkeypatch):
    h, cul, _ = hub; room(h)
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", 0.2)
    end = datetime(2026, 10, 9, 12, 30)
    vw = h.devices[VW]
    h.virtual._take_setpoint(vw, Frame(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, bytes([0x80 | 44]) + encode_until(end)))
    assert vw.until == end
    h._local_now.t = datetime(2026, 10, 9, 13, 0)
    await asyncio.sleep(0.3)
    assert sent(cul) == [] and h.devices[HT2].pending_mode is None


async def test_expired_temporary_is_not_given_to_a_new_link(hub):
    h, cul, _ = hub
    vw = room(h, mates=(HT,))
    vw.mode, vw.until = Mode.TEMPORARY, datetime(2026, 10, 9, 11, 30)          # already over
    ht2 = thermostat(h, HT2)
    ht2.target, ht2.mode = 18.0, Mode.MANUAL
    h.link(HT2, VW)
    await until(lambda: len(sent(cul)) >= 1)
    ack_all(cul, HT2, "01190024")
    await until(lambda: vw.serial in ht2.links)
    await asyncio.sleep(0.05)
    assert all(l[8:10] in ("20", "22") for l in sent(cul)) and ht2.pending_mode is None  # link, group id; no 0x40


async def test_a_boosting_room_does_not_boost_a_new_link(hub):
    h, cul, _ = hub
    vw = room(h, mates=(HT,))
    vw.mode = Mode.BOOST
    ht2 = thermostat(h, HT2)
    ht2.target, ht2.mode = 18.0, Mode.MANUAL
    h.link(HT2, VW)
    await until(lambda: len(sent(cul)) >= 1)
    ack_all(cul, HT2, "01190024")
    await until(lambda: vw.serial in ht2.links)
    await asyncio.sleep(0.05)
    assert all(l[8:10] in ("20", "22") for l in sent(cul))  # link, group id; no 0x40


async def test_a_boosting_thermostat_is_left_out_of_a_pending_forward(hub, monkeypatch):
    h, cul, _ = hub; room(h, mates=(HT, HT2, HT3))
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", 0.2)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))          # 21,5 for the room
    await until(lambda: h.devices[VW].target == 21.5)
    cul.feed(line(3, 0x04, MsgType.SET_TEMPERATURE, HT2, VW, 0, "EB"))         # HT2 boosts meanwhile
    await until(lambda: h.devices[HT2].mode is Mode.BOOST)
    await until(lambda: len(sent(cul)) >= 1, timeout=2)
    await asyncio.sleep(0.1)
    assert {l[16:22] for l in sent(cul)} == {f"{HT3:06X}"}


async def test_boost_from_home_assistant_at_a_member_stays_with_it(hub):
    h, cul, _ = hub; room(h)
    for address in (HT, HT2):
        h.devices[address].group = 5                                           # grouped room
    h.set_temperature(HT, 21.0, Mode.BOOST)
    assert h.devices[HT].pending_mode is Mode.BOOST
    assert h.devices[VW].mode is Mode.MANUAL and h.devices[HT2].pending_mode is None
    await until(lambda: len(sent(cul)) >= 1)
    assert {l[16:22] for l in sent(cul)} == {f"{HT:06X}"}
    assert all(l[6:8] == "00" and l[22:24] == "00" for l in sent(cul))         # addressed, no group flag


async def test_boost_from_home_assistant_at_the_wall_boosts_the_room(hub):
    h, cul, _ = hub; room(h)
    h.set_temperature(VW, 21.0, Mode.BOOST)
    assert h.devices[VW].mode is Mode.BOOST
    assert h.devices[HT].pending_mode is Mode.BOOST and h.devices[HT2].pending_mode is Mode.BOOST


async def test_no_radio_commands_for_a_virtual_device(hub):
    h, cul, _ = hub; room(h, mates=())
    with pytest.raises(FrameError) as err:
        await h.set_time(VW)
    assert err.value.key == "virtual_no_radio"
    with pytest.raises(FrameError) as err:
        h.wake_up(VW)
    assert err.value.key == "virtual_no_radio"
    with pytest.raises(FrameError) as err:
        await h.factory_reset(VW)
    assert err.value.key == "virtual_no_radio"
    await asyncio.sleep(0.05)
    assert sent(cul) == [] and VW in h.devices
