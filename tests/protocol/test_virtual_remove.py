"""Removing a virtual device in two steps: it keeps acknowledging until every real
partner acknowledged the unlink, then it is gone (or at once with force)."""

import asyncio
import contextlib

import pytest

from custom_components.eq3_max.protocol import virtual, virtual_wall
from custom_components.eq3_max.protocol.devices import LINK_PENDING, LINK_REMOVE, MaxDevice
from custom_components.eq3_max.protocol.hub import MaxHub
from custom_components.eq3_max.protocol.messages import DeviceType, FrameError, Mode, MsgType

from .fakes import FakeCul, line, until
from .hubkit import CENTRAL, HT, HT2, VC, VW, LocalClock, Recorder, devices, linked_contact, room, sent, thermostat


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.05)
    monkeypatch.setattr(virtual_wall, "WT_FORWARD_DELAY_S", 0.05)


def keys(h, address):
    return [p["key"] for p in h._scheduler_for(address).pending()]


def idle(h, address):
    return h._scheduler_for(address).pending() == []


def ack(cul, sent_line, src):
    cul.feed(line(int(sent_line[4:6], 16), 0x02, MsgType.ACK, src, CENTRAL, 0, "0119002A"))


def unlinks(cul, dst):
    return [l for l in sent(cul) if l[8:10] == "21" and l[16:22] == f"{dst:06X}"]


@contextlib.asynccontextmanager
async def started(devs):
    cul, rec = FakeCul(), Recorder()
    h = MaxHub(
        "/dev/serial/by-path/x", CENTRAL, devs,
        on_update=rec.updates.append, on_button=lambda d, t: None,
        on_device_added=rec.added.append, on_device_removed=rec.removed.append,
        on_problem=rec.problems.append, open_connection=cul.open, ack_timeout=0.05,
        now=lambda: 1_700_000_000.0, local_now=LocalClock(),
    )
    await h.start()
    await until(lambda: h.connected)
    try:
        yield h, cul, rec
    finally:
        await h.stop()


# --- from the brief ---


async def test_remove_waits_for_the_unlink_and_keeps_acknowledging(hub):
    h, cul, rec = hub; room(h, mates=(HT,))
    assert h.virtual.remove(VW) is False and h.devices[VW].removing
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][8:10] == "21"                                    # RemoveLinkPartner
    assert sent(cul)[0].endswith(f"21{CENTRAL:06X}{HT:06X}0011111103")
    cul.feed(line(3, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: any(l.startswith("Zf") for l in cul.written))    # still acknowledges
    assert VW in h.devices and rec.removed == []
    ack(cul, sent(cul)[0], HT)
    await until(lambda: VW not in h.devices)
    assert rec.removed[0].address == VW and h.devices[HT].links == []


async def test_removing_device_sends_no_temperature(hub):
    h, cul, _ = hub; room(h, group=5); h.virtual.remove(VW)
    before = len(sent(cul)); h.virtual.set_measured(VW, 22.0); await asyncio.sleep(0.1)
    assert not any("0442" in l for l in sent(cul)[before:])


async def test_force_removes_at_once(hub):
    h, cul, rec = hub; room(h, mates=(HT,))
    assert h.virtual.remove(VW, force=True) is True and VW not in h.devices
    assert [d.address for d in rec.removed] == [VW]
    # The thermostat may still know the address; the hub forgets the link (UI warns).
    assert h.devices[HT].links == [] and h.devices[HT].pending_links == []
    await asyncio.sleep(0.1)
    assert sent(cul) == []


async def test_forgotten_partner_does_not_block_removal(hub):            # Review Focus 3
    h, _, rec = hub; room(h, mates=(HT,)); h.virtual.remove(VW)
    del h.devices[HT]; h._forget_unknown_partners(); h.virtual.check_removals()
    assert VW not in h.devices and [d.address for d in rec.removed] == [VW]


# --- what "still carried" means (decision 3) ---


async def test_a_failed_unlink_keeps_the_device(hub):
    h, cul, rec = hub; room(h, mates=(HT,))
    h.virtual.remove(VW)
    await until(lambda: len(unlinks(cul, HT)) >= 1 and idle(h, HT), timeout=5)
    assert h.devices[HT].link_op("VIRT111111")["op"] == LINK_REMOVE         # failed, still there
    assert VW in h.devices and h.devices[VW].removing and rec.removed == []


async def test_a_pending_addition_counts_as_carried(hub):
    h, cul, rec = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(HT, VW)                                                         # AddLinkPartner on air
    await until(lambda: len(sent(cul)) == 1)
    assert h.virtual.remove(VW) is False                                   # it may have taken it
    await until(lambda: len(unlinks(cul, HT)) == 1)
    ack(cul, unlinks(cul, HT)[0], HT)
    await until(lambda: VW not in h.devices)
    assert [d.address for d in rec.removed] == [VW]


async def test_a_virtual_partner_is_unlinked_at_once(hub):
    h, cul, rec = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.link(VW, VC)
    assert h.virtual.remove(VC) is True
    assert VC not in h.devices and vw.links == [] and [d.address for d in rec.removed] == [VC]
    await asyncio.sleep(0.05)
    assert sent(cul) == []


async def test_a_one_sided_link_of_the_thermostat_is_removed_too(hub):
    h, cul, _ = hub
    h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    h.devices[HT].links.append("VIRT222222")                               # only the thermostat has it
    assert h.virtual.remove(VC) is False
    await until(lambda: len(unlinks(cul, HT)) == 1)
    assert unlinks(cul, HT)[0].endswith(f"{HT:06X}0022222204")
    ack(cul, unlinks(cul, HT)[0], HT)
    await until(lambda: VC not in h.devices)


# --- remove() itself (decisions 5 and 8) ---


async def test_remove_refuses_a_real_or_unknown_device(hub):
    h, _, _ = hub
    for address in (HT, 0x123456):
        with pytest.raises(FrameError) as err:
            h.virtual.remove(address)
        assert err.value.key == "not_virtual"


async def test_remove_again_only_checks(hub):
    h, cul, rec = hub; room(h, mates=(HT,))
    assert h.virtual.remove(VW) is False
    await until(lambda: len(unlinks(cul, HT)) == 1)
    assert h.virtual.remove(VW) is False
    assert keys(h, HT).count(f"link:{HT}:{VW}") <= 1                       # nothing queued twice
    ack(cul, unlinks(cul, HT)[0], HT)
    await until(lambda: VW not in h.devices)
    with pytest.raises(FrameError) as err:
        h.virtual.remove(VW)
    assert err.value.key == "not_virtual"


async def test_force_while_removing_drops_the_queued_unlinks(hub):
    h, cul, rec = hub; room(h)
    h.set_temperature(HT, 19.0, Mode.MANUAL)                               # keeps the module busy
    await until(lambda: len(sent(cul)) == 1)
    assert h.virtual.remove(VW) is False
    assert f"link:{HT2}:{VW}" in keys(h, HT2)
    assert h.virtual.remove(VW, force=True) is True
    assert f"link:{HT2}:{VW}" not in keys(h, HT2) and f"link:{HT}:{VW}" not in keys(h, HT)
    assert h.devices[HT].pending_links == [] and h.devices[HT2].pending_links == []
    assert "VIRT111111" not in h.devices[HT].links + h.devices[HT2].links
    await until(lambda: idle(h, HT) and idle(h, HT2), timeout=5)
    assert unlinks(cul, HT2) == []
    assert [d.address for d in rec.removed] == [VW]


async def test_device_removed_is_reported_once(hub):
    h, cul, rec = hub; room(h, mates=(HT,))
    h.virtual.remove(VW)
    await until(lambda: len(unlinks(cul, HT)) == 1)
    ack(cul, unlinks(cul, HT)[0], HT)
    await until(lambda: VW not in h.devices)
    h.virtual.check_removals(); h._forget_unknown_partners()
    cul.feed(line(3, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))              # no longer virtual
    await asyncio.sleep(0.05)
    assert not any(l.startswith("Zf") for l in cul.written)
    assert [d.address for d in rec.removed] == [VW]


# --- own transmissions stop, runtime state goes (decision 2) ---


async def test_a_debounced_window_state_does_not_go_out_after_removal(hub):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    h.virtual.set_window(VC, True)                                         # debounce running
    assert h.virtual.remove(VC, force=True) is True
    await asyncio.sleep(0.2)
    assert sent(cul) == [] and h.virtual._timers == {}


async def test_a_queued_window_state_is_dropped(hub):
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    h.set_temperature(HT, 19.0, Mode.MANUAL)                               # keeps the module busy
    await until(lambda: len(sent(cul)) == 1)
    h.virtual.set_window(VC, True)
    await until(lambda: f"vwin:{VC}:{HT}" in keys(h, HT))
    assert h.virtual.remove(VC) is False
    assert f"vwin:{VC}:{HT}" not in keys(h, HT) and h.virtual._sending == {}
    await until(lambda: idle(h, HT), timeout=5)
    assert not any(l[8:10] == "30" for l in sent(cul))


async def test_a_queued_room_temperature_is_dropped(hub):
    h, cul, _ = hub; room(h, mates=(HT,), group=5)
    h.set_temperature(HT, 19.0, Mode.MANUAL)                               # keeps the module busy
    await until(lambda: len(sent(cul)) == 1)
    h.virtual.set_measured(VW, 22.0)
    await until(lambda: f"vwt:{VW}" in keys(h, HT))
    h.virtual.remove(VW)
    assert f"vwt:{VW}" not in keys(h, HT) and h.virtual._temps == {}
    await until(lambda: idle(h, HT), timeout=5)
    assert not any(l[8:10] == "42" for l in sent(cul))


async def test_a_pending_forward_is_cancelled(hub):
    h, cul, _ = hub; room(h)
    cul.feed(line(9, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6B"))     # handwheel 21.5
    await until(lambda: VW in h.virtual._forwards)
    assert h.virtual.remove(VW, force=True) is True
    assert h.virtual._forwards == {}
    await asyncio.sleep(0.2)
    assert not any(l[8:10] == "40" for l in sent(cul))


# --- restart (decision 4) ---


def _removing_wall():
    return MaxDevice(
        VW, "VIRT111111", DeviceType.WALL_THERMOSTAT, name="B", virtual=True, source="sensor.b", removing=True
    )


async def ack_next_unlink(cul, acked):
    """Acknowledge the next RemoveLinkPartner on air not acknowledged yet; returns its addressee."""
    await until(lambda: any(l[8:10] == "21" and l[16:22] not in acked for l in sent(cul)))
    first = next(l for l in sent(cul) if l[8:10] == "21" and l[16:22] not in acked)
    acked.add(first[16:22])
    dst = int(first[16:22], 16)
    ack(cul, first, dst)
    return dst


async def test_a_removal_continues_after_a_restart():
    devs = devices()
    ht = devs[0]
    ht2 = MaxDevice(HT2, "MEQ9000023", DeviceType.HEATING_THERMOSTAT, name="ht-2")
    ht.links, ht2.links = ["VIRT111111"], ["VIRT111111"]
    ht.set_link_op("VIRT111111", VW, DeviceType.WALL_THERMOSTAT, LINK_REMOVE, LINK_PENDING)   # stored, in flight
    async with started([*devs, ht2, _removing_wall()]) as (h, cul, rec):
        assert keys(h, HT).count(f"link:{HT}:{VW}") == 1 and keys(h, HT2).count(f"link:{HT2}:{VW}") == 1
        acked = set()
        first = await ack_next_unlink(cul, acked)
        await asyncio.sleep(0.02)
        assert VW in h.devices and rec.removed == []                       # the other still carries it
        assert await ack_next_unlink(cul, acked) == ({HT, HT2} - {first}).pop()
        await until(lambda: VW not in h.devices)
        assert [d.address for d in rec.removed] == [VW]
        assert len({l[4:6] for l in unlinks(cul, HT)}) == 1                # one command to HT, not two


async def test_a_removal_nothing_carries_any_more_ends_on_start():
    async with started([*devices(), _removing_wall()]) as (h, cul, rec):
        assert VW not in h.devices and [d.address for d in rec.removed] == [VW]
        await asyncio.sleep(0.05)
        assert sent(cul) == []


# --- fix before review: no links to a removing device, cancel_link checks, window closed first ---


async def test_no_new_link_with_a_device_being_removed(hub):
    h, _, _ = hub; room(h, mates=(HT,)); h.virtual.remove(VW)
    thermostat(h, HT2)
    for a, b in ((HT2, VW), (VW, HT2)):
        with pytest.raises(FrameError) as err:
            h.link(a, b)
        assert err.value.key == "virtual_removing"
    assert h.devices[HT2].pending_links == [] and "MEQ9000023" not in h.devices[VW].links


async def test_cancelling_the_last_open_operation_ends_the_removal(hub):
    h, cul, rec = hub
    h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    h.link(HT, VW)                                                         # AddLinkPartner on air
    await until(lambda: len(sent(cul)) == 1)
    assert h.virtual.remove(VW) is False                                   # removal queued, not taken yet
    h.cancel_link(HT, "VIRT111111")
    assert VW not in h.devices and [d.address for d in rec.removed] == [VW]


async def test_cancelling_an_unlink_of_a_linked_thermostat_keeps_the_device(hub):
    h, _, rec = hub; room(h, mates=(HT,)); h.virtual.remove(VW)
    h.cancel_link(HT, "VIRT111111")
    assert VW in h.devices and h.devices[VW].removing and rec.removed == []   # HT still has the link


def ack_from(cul, sent_line, src, dst):
    cul.feed(line(int(sent_line[4:6], 16), 0x02, MsgType.ACK, src, dst, 0, "01190018"))


def open_contact(h, delivered):
    dev = linked_contact(h, delivered=delivered)
    dev.window_open = True
    return dev


async def test_a_contact_tells_closed_before_it_is_unlinked(hub):
    h, cul, rec = hub; dev = open_contact(h, True)
    assert h.virtual.remove(VC) is False
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][6:] == f"0630{VC:06X}{HT:06X}0010"                  # closed, to HT
    ack_from(cul, sent(cul)[0], HT, VC)
    await until(lambda: len(unlinks(cul, HT)) == 1)
    assert [l[8:10] for l in sent(cul)] == ["30", "21"]
    assert dev.delivered == {h.devices[HT].serial: False}
    ack(cul, unlinks(cul, HT)[0], HT)
    await until(lambda: VC not in h.devices)
    assert [d.address for d in rec.removed] == [VC]


async def test_a_contact_told_closed_sends_no_state(hub):
    h, cul, _ = hub; open_contact(h, False)
    h.virtual.remove(VC)
    await until(lambda: len(unlinks(cul, HT)) == 1)
    assert not any(l[8:10] == "30" for l in sent(cul))


async def test_an_unacknowledged_closed_does_not_hold_up_the_removal(hub, caplog):
    h, cul, rec = hub; open_contact(h, True)
    h.virtual.remove(VC)
    await until(lambda: len(unlinks(cul, HT)) == 1, timeout=5)
    assert any("MEQ9000007" in r.getMessage() and r.levelname == "WARNING" and "closed" in r.getMessage()
               for r in caplog.records)
    ack(cul, unlinks(cul, HT)[-1], HT)
    await until(lambda: VC not in h.devices)
    assert [d.address for d in rec.removed] == [VC]


async def test_force_sends_no_closed(hub):
    h, cul, _ = hub; open_contact(h, True)
    assert h.virtual.remove(VC, force=True) is True
    await asyncio.sleep(0.1)
    assert sent(cul) == []


async def test_an_open_on_air_is_followed_by_closed(hub):
    h, cul, _ = hub; linked_contact(h, delivered=False)
    h.virtual.set_window(VC, True)
    await until(lambda: len(sent(cul)) == 1)                               # "open" waits for its ack
    h.virtual.remove(VC)
    await until(lambda: len(unlinks(cul, HT)) >= 1, timeout=5)
    states = [l for l in sent(cul) if l[8:10] == "30"]
    assert states[-1].endswith("10") and sent(cul).index(states[-1]) < sent(cul).index(unlinks(cul, HT)[0])
