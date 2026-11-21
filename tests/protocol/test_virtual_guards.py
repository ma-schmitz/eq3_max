"""Safety nets around virtual devices: every telegram to one is acknowledged exactly once,
nothing is ever sent to one, and a link taken by a thermostat while its virtual partner
was removed by force is taken apart again."""

import asyncio
import logging
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.hub import MaxHub, RadioSpec
from custom_components.eq3_max.protocol.messages import DeviceType, Frame, FrameError, Mode, MsgType, ProfilePoint
from custom_components.eq3_max.protocol.scheduler import Command

from .fakes import FakeCul, line, until
from .hubkit import CENTRAL, FK, HT, VC, VW, devices, room, sent

VWHEX = f"{VW:06X}"


def acks(cul, src=VW):
    return [l for l in cul.written if l.startswith("Zf") and l[10:16] == f"{src:06X}"]


def to_virtual(cul, address=VW):
    """Lines written to a virtual address (as destination)."""
    return [l for l in cul.written if l[:2] in ("Zs", "Zf") and l[16:22] == f"{address:06X}"]


@pytest.fixture
async def two_modules():
    main, og = FakeCul(), FakeCul()
    h = MaxHub(
        "/dev/serial/by-path/eg", CENTRAL, devices(),
        on_update=lambda d: None, on_button=lambda d, t: None, on_device_added=lambda d: None,
        on_problem=lambda *a: None, open_connection=main.open, ack_timeout=0.05,
        radios=[RadioSpec("og", "/dev/serial/by-path/og", og.open)],
        now=lambda: 1_700_000_000.0, local_now=lambda: datetime(2026, 10, 9, 12, 0),
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, main, og
    await h.stop()


async def test_two_modules_hearing_one_telegram_acknowledge_it_once(two_modules):
    h, main, og = two_modules; room(h, mates=(HT,))
    telegram = line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03")
    main.feed(telegram)
    og.feed(telegram)
    await until(lambda: len(acks(main)) + len(acks(og)) >= 1)
    await asyncio.sleep(0.1)
    assert len(acks(main)) + len(acks(og)) == 1


async def test_a_telegram_of_an_unknown_sender_is_acknowledged(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, 0x154321, VW, 0, "03"))
    await until(lambda: len(acks(cul)) == 1)
    assert acks(cul)[0] == "Zf0E090202111111154321000119042A"


async def test_a_real_contacts_state_to_a_virtual_wall_is_acknowledged(hub):
    h, cul, _ = hub; room(h, mates=(HT,))                                      # FK is not linked
    cul.feed(line(3, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, VW, 0, "12"))
    await until(lambda: len(acks(cul)) == 1)
    assert acks(cul)[0][16:22] == f"{FK:06X}"


async def test_a_wall_being_removed_still_acknowledges_wake_up_and_setpoint(hub):
    h, cul, _ = hub; vw = room(h, mates=(HT,))
    assert h.virtual.remove(VW) is False                                       # waits for HT's removal
    assert vw.removing and h.devices.get(VW) is vw
    cul.feed(line(9, 0x04, MsgType.WAKE_UP, HT, VW, 0, "03"))
    await until(lambda: len(acks(cul)) == 1)
    cul.feed(line(10, 0x04, MsgType.SET_TEMPERATURE, HT, VW, 0, "6E"))        # manual 23,0
    await until(lambda: len(acks(cul)) == 2)
    assert acks(cul)[1] == f"Zf0E0A0202{VWHEX}{HT:06X}000119042E"             # answered with itself
    assert vw.target == 21.0


# --- Nothing is ever sent to a virtual address ---


async def test_submit_drops_a_command_to_a_virtual_device(hub, caplog):
    h, cul, _ = hub; room(h, mates=())
    done = []
    h._submit(Command(dst=VW, build=lambda c: Frame(c, 0, MsgType.WAKE_UP, CENTRAL, VW, 0, b"\x3f"), on_done=done.append))
    await until(lambda: done == [False])
    assert to_virtual(cul) == []
    assert any(r.levelno == logging.ERROR and VWHEX in r.getMessage() for r in caplog.records)


async def test_no_public_hub_method_sends_to_a_virtual_device(hub):
    h, cul, _ = hub; room(h, mates=(HT,))
    contact = h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    calls = [
        lambda: h.set_temperature(VW, 22.0, Mode.MANUAL),
        lambda: h.set_temperature(VW, 22.0, Mode.BOOST),
        lambda: h.set_config(VW, "komfort", 22.5),
        lambda: h.set_config_set(VW, "temp", {"eco": 16.5}),
        lambda: h.set_group(VW, 9),
        lambda: h.set_room_group(VW),
        lambda: h.set_poll(VW, 5),
        lambda: h.wake_up(VW),
        lambda: h.link(VC, VW),
        lambda: h.unlink(VC, VW),
        lambda: h.link(VC, HT),
        lambda: h.unlink(HT, VC, force=True),
        lambda: h.unlink(VW, HT, force=True),
        lambda: h.set_group(VC, 3),
    ]
    for call in calls:
        try:
            call()
        except FrameError:
            pass                                                              # refused is fine as well
    for coro in (
        h.set_week_profile(VW, {6: [ProfilePoint(19.0, 24 * 60)]}),
        h.set_time(VW),
        h.factory_reset(VW),
    ):
        try:
            await coro
        except FrameError:
            pass
    await asyncio.sleep(0.5)
    assert to_virtual(cul) == [] and to_virtual(cul, VC) == []
    assert contact.virtual


# --- A link taken while its virtual partner was removed by force ---


async def test_a_link_taken_after_a_forced_removal_is_taken_apart(hub):
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=VW)
    ht = h.devices[HT]
    h.link(HT, VW)
    await until(lambda: len(sent(cul)) == 1)
    adding = sent(cul)[0]
    assert adding[8:10] == "20"                                                # AddLinkPartner on air
    assert h.virtual.remove(VW, force=True) is True
    cul.feed(line(int(adding[4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))   # it took it
    await until(lambda: len(sent(cul)) >= 2)
    removal = sent(cul)[-1]
    assert removal[8:10] == "21" and removal[22:] == f"00{VWHEX}03"             # RemoveLinkPartner VW, type 3
    assert vw.serial not in ht.links
    cul.feed(line(int(removal[4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: ht.link_op(vw.serial) is None)
    assert vw.serial not in ht.links


async def test_a_real_partner_gone_meanwhile_sends_nothing_extra(hub):
    """Only virtual partners get the removal: without virtual devices nothing changes on air."""
    h, cul, _ = hub
    ht = h.devices[HT]
    h.link(HT, FK)
    await until(lambda: len(sent(cul)) == 1)
    adding = sent(cul)[0]
    del h.devices[FK]                                                          # deleted on the device page
    cul.feed(line(int(adding[4:6], 16), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119002A"))
    await until(lambda: "NEQ9000010" in ht.links)
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1


async def test_a_stored_module_of_a_virtual_device_is_ignored(hub):
    """F9: sends never go through a virtual device's own module, and none can be set."""
    h, cul, _ = hub
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", radio="whatever")
    assert vw.radio == ""
    vw.radio = "r2"                                                            # stored by an older version
    assert h._radio_of(vw).id == ""
    with pytest.raises(FrameError) as err:
        h.set_radio(vw.address, "")
    assert err.value.key == "virtual_no_radio"
