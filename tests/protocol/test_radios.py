"""Several radio modules with one central address (like Homegear's interfaces)."""

import asyncio
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.hub import MAIN_RADIO, MaxHub, RadioSpec
from custom_components.eq3_max.protocol.messages import DeviceType, FrameError, Mode, MsgType

from .fakes import FakeClock, FakeCul, line, until

CENTRAL = 0xC0FFEE
HT = 0xA1B005
HT_UP = 0xA1B007
PB = 0xA1B001


def devices():
    return [
        MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-eg"),
        MaxDevice(HT_UP, "MEQ9000003", DeviceType.HEATING_THERMOSTAT, name="ht-og", radio="og"),
        MaxDevice(PB, "KEQ9000001", DeviceType.PUSH_BUTTON, name="taster"),
    ]


class Rec:
    def __init__(self):
        self.problems = []
        self.buttons = []
        self.added = []


@pytest.fixture
async def two():
    main, og = FakeCul(), FakeCul("V 1.26.08 a-culfw CUBE")
    rec = Rec()
    clock = FakeClock(1_700_000_000.0)
    h = MaxHub(
        "/dev/serial/by-path/eg", CENTRAL, devices(),
        on_update=lambda d: None,
        on_button=lambda d, t: rec.buttons.append((d.address, t)),
        on_device_added=rec.added.append,
        on_problem=lambda *args: rec.problems.append(args),
        open_connection=main.open,
        radios=[RadioSpec("og", "192.0.2.60:2323", og.open)],
        ack_timeout=0.05,
        now=clock,
        local_now=lambda: datetime(2026, 10, 19, 12, 0),
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, main, og, rec, clock
    await h.stop()


def sent(cul):
    return [l for l in cul.written if l.startswith("Zs")]


def ack_for(sent_line, src):
    return line(int(sent_line[4:6], 16), 0x02, MsgType.ACK, src, CENTRAL, 0, "0119302A")


async def test_every_module_gets_the_same_central_address(two):
    h, main, og, rec, _ = two
    assert "ZaC0FFEE" in main.written and "ZaC0FFEE" in og.written
    assert h.radio_ids == [MAIN_RADIO, "og"]
    status = h.radio_status()
    assert [s["id"] for s in status] == ["", "og"]
    assert status[1]["target"] == "192.0.2.60:2323" and status[1]["version"] == "V 1.26.08 a-culfw CUBE"


async def test_commands_go_through_the_assigned_module(two):
    h, main, og, rec, _ = two
    h.set_temperature(HT_UP, 21.0, Mode.MANUAL)
    h.set_temperature(HT, 20.0, Mode.MANUAL)
    await until(lambda: len(sent(og)) == 1 and len(sent(main)) == 1)
    assert sent(og)[0][16:22] == "A1B007" and sent(main)[0][16:22] == "A1B005"


async def test_ack_heard_by_the_other_module_completes_the_command(two):
    h, main, og, rec, _ = two
    h.set_temperature(HT_UP, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(og)) == 1)
    main.feed(ack_for(sent(og)[0], HT_UP))
    await until(lambda: not h.devices[HT_UP].has_pending)
    await asyncio.sleep(0.1)
    assert len(sent(og)) == 1


async def test_set_radio_moves_waiting_commands(two):
    h, main, og, rec, _ = two
    # The set command goes on air at once on main; the config set waits behind it.
    h.set_temperature(HT, 20.0, Mode.MANUAL)
    h.set_config_set(HT, "temp", {"komfort": 22.0})
    await until(lambda: len(sent(main)) == 1)
    h.set_radio(HT, "og")
    assert h.devices[HT].radio == "og"
    # The waiting config set (type 11) now goes out through the other module.
    await until(lambda: any(l[8:10] == "11" and l[16:22] == "A1B005" for l in sent(og)))
    assert not any(l[8:10] == "11" for l in sent(main))


async def test_set_radio_rejects_unknown_module(two):
    h, *_ = two
    with pytest.raises(FrameError):
        h.set_radio(HT, "keller")


async def test_device_on_a_removed_module_falls_back_to_main(two):
    h, main, og, rec, _ = two
    h.devices[HT].radio = "weg"
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(main)) == 1)


async def test_one_transmission_heard_twice_is_handled_once_with_rssi_per_module(two):
    h, main, og, rec, _ = two
    press = line(0x59, 0x02, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "0001", rssi="40")
    main.feed(press)
    og.feed(press[:-2] + "20")
    await until(lambda: set(h.devices[PB].rssi_by_radio) == {"", "og"})
    await asyncio.sleep(0.02)
    assert rec.buttons == [(PB, "auto")]
    assert h.devices[PB].rssi_by_radio[""] != h.devices[PB].rssi_by_radio["og"]
    # The RSSI entity shows the assigned (main) module.
    assert h.devices[PB].rssi == h.devices[PB].rssi_by_radio[""]


async def test_repeat_on_the_same_module_is_a_new_transmission(two):
    h, main, og, rec, _ = two
    press = line(0x59, 0x02, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "0001")
    main.feed(press)
    main.feed(press)
    await asyncio.sleep(0.05)
    # Same counter twice on one module: the existing button dedupe applies, the
    # cross-module filter does not swallow it.
    assert len(rec.buttons) == 1


async def test_copy_after_the_window_counts_again(two):
    h, main, og, rec, clock = two
    status = line(0x10, 0x04, MsgType.THERMOSTAT_STATE, HT_UP, CENTRAL, 0, "19302A00BE")
    main.feed(status)
    await until(lambda: "" in h.devices[HT_UP].rssi_by_radio)
    clock.t += 2
    og.feed(status)
    await until(lambda: "og" in h.devices[HT_UP].rssi_by_radio)


async def test_new_device_stays_on_the_module_that_heard_it(two):
    h, main, og, rec, _ = two
    h.open_pairing(60)
    og.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, 0, 0, "100100" + b"ABC1234567".hex()))
    await until(lambda: len(sent(og)) == 1)
    assert h.devices[0x123ABC].radio == "og" and sent(main) == []


async def test_problems_of_extra_modules_name_the_module(two):
    h, main, og, rec, _ = two
    h._radios["og"].transport._on_problem("port_lost")
    h._radios[""].transport._on_problem("stick_deaf")
    assert rec.problems == [("port_lost", "og"), ("stick_deaf",)]


async def test_airtime_is_the_busiest_module_and_queue_the_sum(two):
    h, main, og, rec, _ = two
    h.set_temperature(HT_UP, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(og)) == 1)
    assert h.airtime_last_hour == h.radio_status()[1]["airtime"] > 0
    assert h.radio_status()[0]["airtime"] == 0


async def test_connected_needs_every_module(two):
    h, main, og, rec, _ = two
    assert h.connected
    og.writer.close()
    await until(lambda: not h.connected)
    assert h.radio_status()[0]["connected"] and not h.radio_status()[1]["connected"]


async def test_reachable_follows_the_assigned_module(two):
    h, main, og, rec, _ = two
    og.writer.close()
    await until(lambda: not h.connected)
    assert h.any_connected
    assert h.reachable(HT) and not h.reachable(HT_UP)


async def test_set_radio_shows_the_rssi_of_the_new_module(two):
    h, *_ = two
    h.devices[HT].rssi_by_radio = {"": -85.0, "og": -62.0}
    h.devices[HT].rssi = -85.0
    h.set_radio(HT, "og")
    assert h.devices[HT].rssi == -62.0


async def test_modules_share_one_telegram_counter(two):
    h, main, og, rec, _ = two
    h.set_temperature(HT, 20.0, Mode.MANUAL)
    h.set_temperature(HT_UP, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(main)) == 1 and len(sent(og)) == 1)
    assert sent(main)[0][4:6] != sent(og)[0][4:6]


async def test_heard_since_is_per_module(two):
    import time

    h, main, og, rec, _ = two
    mark = time.time() - 1
    main.feed(line(0x10, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE"))
    await until(lambda: h.heard_since("", mark))
    assert not h.heard_since("og", mark)
