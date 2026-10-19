import asyncio
from datetime import datetime

import pytest

from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.hub import MaxHub, ResetResult
from custom_components.eq3_max.protocol.messages import DeviceType, FrameError, Mode, MsgType

from .fakes import FakeCul, line, until

CENTRAL = 0xC0FFEE
LOCAL_NOW = datetime(2026, 10, 9, 12, 0)


class LocalClock:
    """Naive local wall clock for the hub (HA time in production)."""

    def __init__(self, t: datetime = LOCAL_NOW) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t
HT = 0xA1B005
FK = 0xA1B00B
PB = 0xA1B001
WT = 0x1590B4


def devices():
    return [
        MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten"),
        MaxDevice(FK, "NEQ9000010", DeviceType.SHUTTER_CONTACT, name="fk-schlafzimmer"),
        MaxDevice(PB, "KEQ9000001", DeviceType.PUSH_BUTTON, name="taster"),
        MaxDevice(WT, "NEQ9000011", DeviceType.WALL_THERMOSTAT, name="wt-wohnzimmer"),
    ]


class Recorder:
    def __init__(self):
        self.updates = []
        self.buttons = []
        self.added = []
        self.problems = []


@pytest.fixture
async def hub():
    cul = FakeCul()
    rec = Recorder()
    h = MaxHub(
        "/dev/serial/by-path/x", CENTRAL, devices(),
        on_update=rec.updates.append,
        on_button=lambda d, t: rec.buttons.append((d.address, t)),
        on_device_added=rec.added.append,
        on_problem=rec.problems.append,
        open_connection=cul.open,
        ack_timeout=0.05,
        now=lambda: 1_700_000_000.0,
        local_now=LocalClock(),
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, cul, rec
    await h.stop()


def sent(cul):
    return [l for l in cul.written if l.startswith("Zs")]


async def heard_other_after_first_send(cul):
    """Another device's frame arrives after the first attempt: the stick still
    receives, so an unacknowledged command does not trigger the fast reopen."""
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))


async def test_set_temperature_sends_and_ack_updates_state(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    assert h.devices[HT].has_pending
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs0B010040C0FFEEA1B005006A"
    cul.feed(line(1, 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
    await until(lambda: h.devices[HT].target == 21.0)
    d = h.devices[HT]
    assert not d.has_pending and d.valve == 48 and d.rssi == -42.5
    assert d.last_seen == 1_700_000_000.0


async def test_failed_command_marks_device_and_is_resent_on_next_status(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await heard_other_after_first_send(cul)
    await until(lambda: h.devices[HT].command_failed, timeout=1.0)
    assert len(sent(cul)) == 4
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
    await until(lambda: len(sent(cul)) == 5)


async def test_thermostat_state_updates_measured(hub):
    h, cul, rec = hub
    cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE"))
    await until(lambda: h.devices[HT].measured == 19.0)
    assert rec.updates[-1] is h.devices[HT]


async def test_shutter_contact(hub):
    h, cul, rec = hub
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
    await until(lambda: h.devices[FK].window_open is True)


async def test_button_event(hub):
    h, cul, rec = hub
    cul.feed(line(9, 0x06, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "1000"))
    await until(lambda: rec.buttons == [(PB, "eco")])


async def test_repeated_button_frame_fires_once(hub):
    h, cul, rec = hub
    frame = line(9, 0x06, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "1001")
    cul.feed(frame)
    cul.feed(frame)
    cul.feed(line(10, 0x06, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "1001"))
    await until(lambda: len(rec.buttons) == 2)
    await asyncio.sleep(0.02)
    assert rec.buttons == [(PB, "auto"), (PB, "auto")]


async def test_wall_thermostat_control_to_heating_thermostat(hub):
    h, cul, rec = hub
    cul.feed(line(3, 0x04, MsgType.WALL_THERMOSTAT_CONTROL, WT, HT, 0, "2AD2"))
    await until(lambda: h.devices[WT].measured == 21.0)


async def test_time_request_is_answered(hub):
    h, cul, rec = hub
    cul.feed(line(4, 0x0A, MsgType.TIME_INFORMATION, HT, CENTRAL, 0, ""))
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][8:10] == "03"
    assert sent(cul)[0][6:8] == "04"


async def test_pairing_only_when_window_open(hub):
    h, cul, rec = hub
    ping = line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, 0, 0, "100100" + b"ABC1234567".hex())
    cul.feed(ping)
    await asyncio.sleep(0.02)
    assert rec.added == [] and sent(cul) == []
    h.open_pairing(60)
    cul.feed(ping)
    # The pong goes out first; the new device is reported once it completed.
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0][8:10] == "01"
    assert h.devices[0x123ABC].device_type is DeviceType.HEATING_THERMOSTAT
    await until(lambda: len(rec.added) == 1, timeout=1.0)
    assert rec.added[0].serial == "ABC1234567"


async def test_repairing_after_battery_change_keeps_device(hub):
    h, cul, rec = hub
    h.devices[HT].target = 20.0
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, HT, CENTRAL, 0, "100100" + b"MEQ9000007".hex()))
    await until(lambda: len(sent(cul)) == 1)
    assert rec.added == [] and h.devices[HT].target == 20.0


async def test_frames_from_unknown_or_own_address_are_ignored(hub):
    h, cul, rec = hub
    cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, 0xAAAAAA, CENTRAL, 0, "19302A00BE"))
    cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, CENTRAL, HT, 0, "19302A00BE"))
    await asyncio.sleep(0.02)
    assert [u for u in rec.updates if u is not None] == []


async def test_garbage_lines_are_ignored(hub):
    h, cul, rec = hub
    for junk in ("Z0E", "ZXYZ", "Z0EF20202A1B005C0FFEE00011930", "V 1.66", line(1, 0, 0x60, HT, CENTRAL, 0, "19")):
        cul.feed(junk)
    cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE"))
    await until(lambda: h.devices[HT].measured == 19.0)


async def test_pending_command_is_resent_after_start():
    cul = FakeCul()
    devs = devices()
    devs[0].set_pending(22.0, Mode.MANUAL)
    h = MaxHub("/dev/x", CENTRAL, devs, on_update=lambda d: None, on_button=lambda d, t: None,
               on_device_added=lambda d: None, on_problem=lambda k: None,
               open_connection=cul.open, ack_timeout=0.05)
    await h.start()
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("6C")
    await h.stop()


# --- fix round 1 ---

def _make(cul, **over):
    kwargs = dict(
        on_update=lambda d: None, on_button=lambda d, t: None,
        on_device_added=lambda d: None, on_problem=lambda k: None,
        open_connection=cul.open, ack_timeout=0.05, now=lambda: 1_700_000_000.0,
        local_now=LocalClock(),
    )
    kwargs.update(over)
    return MaxHub("/dev/x", CENTRAL, devices(), **kwargs)


async def test_wall_thermostat_failed_command_is_resent_on_next_status(hub):
    h, cul, rec = hub
    h.set_temperature(WT, 21.0, Mode.MANUAL)
    await heard_other_after_first_send(cul)
    await until(lambda: h.devices[WT].command_failed, timeout=1.0)
    assert len(sent(cul)) == 4
    cul.feed(line(9, 0x04, MsgType.WALL_THERMOSTAT_STATE, WT, CENTRAL, 0, "010028"))
    await until(lambda: len(sent(cul)) == 5)


async def test_failed_command_not_resent_when_status_shows_target_reached(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await heard_other_after_first_send(cul)
    await until(lambda: h.devices[HT].command_failed, timeout=1.0)
    assert len(sent(cul)) == 4
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE"))
    await until(lambda: not h.devices[HT].has_pending)
    await asyncio.sleep(0.02)
    assert len(sent(cul)) == 4 and not h.devices[HT].command_failed


async def test_nak_marks_command_failed_after_one_send(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(1, 0x02, MsgType.ACK, HT, CENTRAL, 0, "81"))
    await until(lambda: h.devices[HT].command_failed)
    assert len(sent(cul)) == 1


@pytest.mark.parametrize("temperature,mode", [(21.0, Mode.TEMPORARY), (None, Mode.MANUAL)])
async def test_set_temperature_rejects_invalid_without_pending(hub, temperature, mode):
    h, cul, rec = hub
    with pytest.raises(FrameError):
        h.set_temperature(HT, temperature, mode)
    assert not h.devices[HT].has_pending
    await asyncio.sleep(0.02)
    assert sent(cul) == []


async def test_raising_button_callback_does_not_stop_frame_handling():
    cul = FakeCul()

    def boom(d, t):
        raise RuntimeError("boom")

    h = _make(cul, on_button=boom)
    await h.start()
    await until(lambda: h.connected)
    try:
        cul.feed(line(9, 0x06, MsgType.PUSH_BUTTON_STATE, PB, CENTRAL, 0, "8001"))
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
        await until(lambda: h.devices[FK].window_open is True)
        assert h.devices[PB].battery_low is True
    finally:
        await h.stop()


async def test_raising_device_added_callback_still_sends_pong():
    cul = FakeCul()

    def boom(d):
        raise RuntimeError("boom")

    h = _make(cul, on_device_added=boom)
    await h.start()
    await until(lambda: h.connected)
    try:
        h.open_pairing(60)
        cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, 0, 0, "100100" + b"ABC1234567".hex()))
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0][8:10] == "01"
    finally:
        await h.stop()


async def test_repairing_under_new_address_rekeys_and_notifies(hub):
    h, cul, rec = hub
    new = 0xA1B006
    dev = h.devices[HT]
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, new, CENTRAL, 0, "100100" + b"MEQ9000007".hex()))
    await until(lambda: len(sent(cul)) == 1)
    assert HT not in h.devices and h.devices[new] is dev and dev.address == new
    assert dev in rec.updates
    assert sent(cul)[0][16:22] == "A1B006"


async def test_pair_ping_to_own_address_from_unknown_device_is_accepted(hub):
    h, cul, rec = hub
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, CENTRAL, 0, "100100" + b"ABC1234567".hex()))
    await until(lambda: len(sent(cul)) == 1)
    await until(lambda: len(rec.added) == 1, timeout=1.0)


async def test_pair_ping_to_foreign_central_is_ignored(hub):
    h, cul, rec = hub
    h.open_pairing(60)
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, 0xAABBCC, 0, "100100" + b"ABC1234567".hex()))
    await asyncio.sleep(0.02)
    assert rec.added == [] and sent(cul) == []


# --- final fix wave ---

def _counter(sent_line):
    return int(sent_line[4:6], 16)


@pytest.mark.parametrize(("temperature", "expected", "tail"), [(20.8, 21.0, "6A"), (20.25, 20.5, "69")])
async def test_pending_stores_the_normalized_temperature(hub, temperature, expected, tail):
    h, cul, rec = hub
    h.set_temperature(HT, temperature, Mode.MANUAL)
    assert h.devices[HT].pending_target == expected
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith(tail)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "011930" + f"{int(expected * 2):02X}"))
    await until(lambda: not h.devices[HT].has_pending)


async def test_ok_ack_clears_pending_even_if_status_shows_other_target(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    # The ack confirms the command but already carries an older target (18.0).
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01193024"))
    await until(lambda: not h.devices[HT].has_pending)
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302400BE"))
    await until(lambda: h.devices[HT].measured == 19.0)
    await asyncio.sleep(0.02)
    assert not h.devices[HT].has_pending and not h.devices[HT].command_failed
    assert len(sent(cul)) == 1


async def test_ok_ack_for_superseded_command_keeps_newer_pending(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    h.set_temperature(HT, 22.0, Mode.MANUAL)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
    await until(lambda: len(sent(cul)) == 2)
    assert h.devices[HT].pending_target == 22.0


async def test_failed_command_keeps_pending(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "81"))
    await until(lambda: h.devices[HT].command_failed)
    assert h.devices[HT].has_pending and h.devices[HT].pending_target == 21.0


async def test_commands_before_connect_are_sent_after_connect_without_failing():
    cul = FakeCul()
    cul.fail_open = True
    h = _make(cul, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await asyncio.sleep(0.3)
        assert not h.devices[HT].command_failed and h.devices[HT].has_pending
        cul.fail_open = False
        await until(lambda: len(sent(cul)) == 1)
        cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
        await until(lambda: not h.devices[HT].has_pending)
        assert not h.devices[HT].command_failed
    finally:
        await h.stop()


async def test_failed_pending_command_is_resent_after_reconnect():
    cul = FakeCul()
    h = _make(cul, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await heard_other_after_first_send(cul)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        assert len(sent(cul)) == 4 and cul.opened == 1
        cul.unplug()
        await until(lambda: cul.opened == 2 and h.connected)
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0].endswith("6A")
        assert not h.devices[HT].command_failed
    finally:
        await h.stop()


async def test_wall_thermostat_set_temperature_to_ht_is_overheard(hub):
    h, cul, rec = hub
    h.devices[WT].set_pending(18.0, Mode.MANUAL)
    h.devices[WT].command_failed = True
    cul.feed(line(3, 0x04, MsgType.SET_TEMPERATURE, WT, HT, 0, "64"))
    await until(lambda: h.devices[WT].target == 18.0)
    wt = h.devices[WT]
    assert wt.mode is Mode.MANUAL and not wt.has_pending and not wt.command_failed
    await asyncio.sleep(0.02)
    assert sent(cul) == []


async def test_set_temperature_from_heating_thermostat_is_not_applied(hub):
    h, cul, rec = hub
    cul.feed(line(3, 0x04, MsgType.SET_TEMPERATURE, HT, WT, 0, "64"))
    await asyncio.sleep(0.02)
    assert h.devices[HT].target is None and h.devices[HT].mode is None


async def test_new_device_is_reported_only_after_pong_completed(hub):
    h, cul, rec = hub
    at_callback = []
    h._on_device_added = lambda d: at_callback.append((d.serial, len(sent(cul))))
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, CENTRAL, 0, "100100" + b"ABC1234567".hex()))
    await until(lambda: len(sent(cul)) == 1)
    assert at_callback == []
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, 0x123ABC, CENTRAL, 0, "00"))
    await until(lambda: at_callback == [("ABC1234567", 1)])


async def test_new_device_is_reported_even_if_pong_unacknowledged(hub):
    h, cul, rec = hub
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, CENTRAL, 0, "100100" + b"ABC1234567".hex()))
    await until(lambda: len(rec.added) == 1, timeout=1.0)
    assert len(sent(cul)) == 4


async def test_raw_history_keeps_last_ten_lines_per_known_device(hub):
    h, cul, rec = hub
    lines = [line(i, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE") for i in range(12)]
    for text in lines:
        cul.feed(text)
    cul.feed(line(1, 0x04, MsgType.THERMOSTAT_STATE, 0xAAAAAA, CENTRAL, 0, "19302A00BE"))
    cul.feed("ZXYZ")
    await until(lambda: len(h.raw_history.get(HT, ())) == 10 and h.devices[HT].last_seen is not None)
    await asyncio.sleep(0.02)
    assert list(h.raw_history[HT]) == lines[2:]
    assert 0xAAAAAA not in h.raw_history


# --- Block 1: temporaer (Urlaub) und Werksreset ---

async def test_set_temperature_temporary_puts_until_into_frame(hub):
    from datetime import datetime

    h, cul, rec = hub
    h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    d = h.devices[HT]
    assert d.pending_mode is Mode.TEMPORARY and d.pending_until == datetime(2026, 10, 10, 14, 30)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs0E010040C0FFEEA1B00500A4AA1A1D"
    # Status meldet temporaer mit 18 Grad -> ausstehend erledigt, Ende uebernommen
    cul.feed(line(1, 0x02, MsgType.ACK, HT, CENTRAL, 0, "011A3024AA1A1D"))
    await until(lambda: not h.devices[HT].has_pending)
    assert d.mode is Mode.TEMPORARY and d.target == 18.0 and d.until == datetime(2026, 10, 10, 14, 30)


async def test_set_temperature_until_in_past_is_rejected(hub):
    from datetime import datetime

    h, cul, rec = hub
    # Hub-Ortszeit steht auf 09.10.2026 12:00
    with pytest.raises(FrameError):
        h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2023, 1, 1, 0, 0))
    assert not h.devices[HT].has_pending
    await asyncio.sleep(0.02)
    assert sent(cul) == []


async def test_pending_temporary_is_resent_with_until_after_start():
    from datetime import datetime

    cul = FakeCul()
    devs = devices()
    devs[0].set_pending(18.0, Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    h = MaxHub(
        "/dev/x", CENTRAL, devs, on_update=lambda d: None, on_button=lambda d, t: None,
        on_device_added=lambda d: None, on_problem=lambda k: None, open_connection=cul.open,
        ack_timeout=0.05, now=lambda: 1_700_000_000.0, local_now=LocalClock(),
    )
    await h.start()
    try:
        await until(lambda: len(sent(cul)) >= 1)
        assert sent(cul)[0].endswith("00A4AA1A1D")
    finally:
        await h.stop()


async def test_factory_reset_acked_removes_device(hub):
    h, cul, rec = hub
    task = asyncio.create_task(h.factory_reset(HT))
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs0A0100F0C0FFEEA1B00500"
    cul.feed(line(1, 0x02, MsgType.ACK, HT, CENTRAL, 0, "00"))
    assert await asyncio.wait_for(task, 1) is ResetResult.ACKED
    assert HT not in h.devices


async def test_factory_reset_without_ack_keeps_device(hub):
    h, cul, rec = hub
    assert await asyncio.wait_for(h.factory_reset(HT), 2) is ResetResult.UNACKED
    assert HT in h.devices
    assert len(sent(cul)) == 4


async def test_overheard_wall_thermostat_temporary_carries_until(hub):
    from datetime import datetime

    h, cul, rec = hub
    cul.feed(line(3, 0x04, MsgType.SET_TEMPERATURE, WT, HT, 0, "A4AA1A1D"))
    await until(lambda: h.devices[WT].mode is Mode.TEMPORARY)
    assert h.devices[WT].until == datetime(2026, 10, 10, 14, 30) and h.devices[WT].target == 18.0
    cul.feed(line(4, 0x04, MsgType.SET_TEMPERATURE, WT, HT, 0, "64"))
    await until(lambda: h.devices[WT].mode is Mode.MANUAL)
    assert h.devices[WT].until is None



# --- Block 1, Fix-Runde 1 ---

U0 = datetime(2026, 10, 10, 14, 30)  # Ende, das das Geraet schon kennt
U1 = datetime(2026, 10, 11, 9, 0)  # neues Ende, gleiche Temperatur
U2 = datetime(2026, 10, 12, 9, 0)


def _temporary_state(until_dt):
    from custom_components.eq3_max.protocol.messages import encode_until

    return "1A3024" + encode_until(until_dt).hex().upper()


async def _device_in_temporary(h, cul, until_dt=U0):
    cul.feed(line(0x50, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, _temporary_state(until_dt)))
    await until(lambda: h.devices[HT].until == until_dt)


async def test_i2_same_temperature_new_until_not_cleared_by_status_without_new_until(hub):
    h, cul, rec = hub
    await _device_in_temporary(h, cul)
    h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=U1)
    await until(lambda: len(sent(cul)) == 1)
    # Kurzer Status (3 Byte) und Status mit altem Ende: beide nicht erledigt
    cul.feed(line(0x51, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "1A3024"))
    cul.feed(line(0x52, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, _temporary_state(U0)))
    await asyncio.sleep(0.02)
    assert h.devices[HT].has_pending and h.devices[HT].pending_until == U1
    cul.feed(line(0x53, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, _temporary_state(U1)))
    await until(lambda: not h.devices[HT].has_pending)


async def test_i2_ok_ack_of_that_command_clears(hub):
    h, cul, rec = hub
    await _device_in_temporary(h, cul)
    h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=U1)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "011A3024"))
    await until(lambda: not h.devices[HT].has_pending)
    # Kurze Quittung loescht das bekannte Ende nicht (I1)
    assert h.devices[HT].until == U0


async def test_i2_stale_ack_does_not_clear_newer_pending(hub):
    h, cul, rec = hub
    await _device_in_temporary(h, cul)
    h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=U1)
    await until(lambda: len(sent(cul)) == 1)
    first = _counter(sent(cul)[0])
    h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=U2)
    cul.feed(line(first, 0x02, MsgType.ACK, HT, CENTRAL, 0, "011A3024"))
    await until(lambda: len(sent(cul)) == 2)
    assert h.devices[HT].has_pending and h.devices[HT].pending_until == U2


async def test_i4_expired_pending_after_start_is_dropped():
    cul = FakeCul()
    updates = []
    devs = devices()
    devs[0].set_pending(18.0, Mode.TEMPORARY, until=datetime(2026, 10, 9, 11, 30))
    h = MaxHub(
        "/dev/x", CENTRAL, devs, on_update=updates.append, on_button=lambda d, t: None,
        on_device_added=lambda d: None, on_problem=lambda k: None, open_connection=cul.open,
        ack_timeout=0.05, now=lambda: 1_700_000_000.0, local_now=LocalClock(),
    )
    await h.start()
    try:
        await until(lambda: h.connected)
        await asyncio.sleep(0.05)
        assert not h.devices[HT].has_pending
        assert h.devices[HT] in updates
        assert sent(cul) == []
    finally:
        await h.stop()


async def test_i4_expired_pending_after_reconnect_is_dropped():
    cul = FakeCul()
    clock = LocalClock()
    h = _make(cul, local_now=clock, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 9, 12, 30))
        await heard_other_after_first_send(cul)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        assert cul.opened == 1
        clock.t = datetime(2026, 10, 9, 12, 31)
        cul.unplug()
        await until(lambda: cul.opened == 2 and h.connected)
        await asyncio.sleep(0.05)
        assert not h.devices[HT].has_pending
        assert sent(cul) == []
    finally:
        await h.stop()


async def test_i4_queued_command_expiring_while_offline_is_not_sent():
    cul = FakeCul()
    cul.fail_open = True
    clock = LocalClock()
    h = _make(cul, local_now=clock, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    try:
        h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 9, 12, 30))
        await asyncio.sleep(0.05)
        clock.t = datetime(2026, 10, 9, 12, 30)
        cul.fail_open = False
        await until(lambda: not h.devices[HT].has_pending)
        await asyncio.sleep(0.05)
        assert sent(cul) == []
        assert not h.devices[HT].command_failed
    finally:
        await h.stop()


async def test_m5_time_reply_uses_injected_local_clock(hub):
    h, cul, rec = hub
    h._local_now.t = datetime(2026, 10, 9, 14, 17, 12)
    cul.feed(line(4, 0x0A, MsgType.TIME_INFORMATION, HT, CENTRAL, 0, ""))
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0].endswith("1A090E918C")


async def test_m5_future_check_uses_local_clock(hub):
    h, cul, rec = hub
    h._local_now.t = datetime(2026, 10, 10, 14, 30)
    with pytest.raises(FrameError):
        h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))


async def test_i3_reset_not_sent_when_window_passes_offline():
    cul = FakeCul()
    cul.fail_open = True
    h = _make(cul, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    try:
        result = await asyncio.wait_for(h.factory_reset(HT, send_window=0.05, margin=0.05), 2)
        assert result is ResetResult.NOT_SENT
        assert HT in h.devices
        cul.fail_open = False
        await until(lambda: h.connected)
        await asyncio.sleep(0.1)
        assert sent(cul) == []
    finally:
        await h.stop()


async def test_i3_stop_during_reset_resolves_without_hang(hub):
    h, cul, rec = hub
    task = asyncio.create_task(h.factory_reset(HT))
    await until(lambda: len(sent(cul)) == 1)
    await h.stop()
    result = await asyncio.wait_for(task, 1)
    assert result is ResetResult.UNACKED
    assert HT in h.devices


async def test_m7_successful_reset_drops_queued_set_commands(hub):
    h, cul, rec = hub
    task = asyncio.create_task(h.factory_reset(HT))
    await until(lambda: len(sent(cul)) == 1)
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    assert h.queue_length == 1
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "00"))
    assert await asyncio.wait_for(task, 1) is ResetResult.ACKED
    assert h.queue_length == 0
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 1


async def test_m8_concurrent_reset_and_unknown_device_are_refused(hub):
    h, cul, rec = hub
    task = asyncio.create_task(h.factory_reset(HT))
    await until(lambda: len(sent(cul)) == 1)
    with pytest.raises(FrameError):
        await h.factory_reset(HT)
    with pytest.raises(FrameError):
        await h.factory_reset(0x123456)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "00"))
    assert await asyncio.wait_for(task, 1) is ResetResult.ACKED


# --- Fix: heat nach away/boost ---

async def test_overheard_wall_thermostat_manual_set_updates_last_comfort(hub):
    h, cul, rec = hub
    cul.feed(line(3, 0x04, MsgType.SET_TEMPERATURE, WT, HT, 0, "6A"))  # manual 21.0
    await until(lambda: h.devices[WT].last_comfort == 21.0)
    cul.feed(line(4, 0x04, MsgType.SET_TEMPERATURE, WT, HT, 0, "49"))  # manual 4.5
    await until(lambda: h.devices[WT].target == 4.5)
    assert h.devices[WT].last_comfort == 21.0


# --- Fix: schnelles Wiederoeffnen bei tauben Stick ---

def _count_reopens(h):
    calls = []
    orig = h._transport.request_reopen

    def wrapped():
        calls.append(1)
        return orig()

    h._transport.request_reopen = wrapped
    return calls


async def test_failed_command_without_rx_reopens_at_once_and_resends(caplog):
    cul = FakeCul()
    problems = []
    h = _make(cul, on_problem=problems.append)
    await h.start()
    await until(lambda: h.connected)
    reopens = _count_reopens(h)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        assert reopens == [1]
        assert "CUL empfaengt nach dem Senden nichts mehr - Port wird neu geoeffnet" in caplog.text
        assert len([l for l in cul.all_written if l.startswith("Zs")]) == 4
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0].endswith("6A")
        cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
        await until(lambda: not h.devices[HT].has_pending)
        await asyncio.sleep(0.1)
        assert reopens == [1] and cul.opened == 2
        assert problems == []
    finally:
        await h.stop()


async def test_unreachable_device_gets_one_fast_reopen_per_quiet_episode():
    cul = FakeCul()
    problems = []
    h = _make(cul, on_problem=problems.append)
    await h.start()
    await until(lambda: h.connected)
    reopens = _count_reopens(h)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        # The resend after the reconnect fails as well, then the set is retried twice more.
        for _ in range(3):
            await until(lambda: h.devices[HT].command_failed, timeout=1.0)
            await asyncio.sleep(0.02)
            h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        await asyncio.sleep(0.05)
        assert cul.opened == 2
        assert len(reopens) >= 2  # requested again, but ignored
        assert problems == []
        # Another device is heard: the stick works, HT itself is unreachable. Its
        # commands no longer reopen the port until HT is heard again.
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
        await until(lambda: h.devices[FK].window_open is False)
        h.set_temperature(HT, 22.0, Mode.MANUAL)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        await asyncio.sleep(0.05)
        assert cul.opened == 2
        assert problems == []
    finally:
        await h.stop()


async def test_unacked_time_reply_and_pong_do_not_reopen(hub):
    h, cul, rec = hub
    reopens = _count_reopens(h)
    cul.feed(line(4, 0x0A, MsgType.TIME_INFORMATION, HT, CENTRAL, 0, ""))
    cul.feed(line(0, 0x04, MsgType.PAIR_PING, 0x123ABC, CENTRAL, 0, "100100" + b"ABC1234567".hex()))
    await until(lambda: len(rec.added) == 1, timeout=1.0)
    await until(lambda: len(sent(cul)) == 8, timeout=1.0)
    await asyncio.sleep(0.05)
    assert reopens == [] and cul.opened == 1


async def test_unacked_factory_reset_without_rx_reopens():
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    reopens = _count_reopens(h)
    try:
        result = await h.factory_reset(HT, send_window=1.0, margin=0.5)
        assert result is ResetResult.UNACKED
        await until(lambda: reopens == [1], timeout=1.0)
    finally:
        await h.stop()


async def test_failed_command_with_other_frames_received_does_not_reopen(hub):
    h, cul, rec = hub
    reopens = _count_reopens(h)
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
    await until(lambda: h.devices[HT].command_failed, timeout=1.0)
    await asyncio.sleep(0.05)
    assert reopens == [] and cul.opened == 1 and h.connected


async def test_nak_does_not_reopen(hub):
    h, cul, rec = hub
    reopens = _count_reopens(h)
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "81"))
    await until(lambda: h.devices[HT].command_failed)
    await asyncio.sleep(0.05)
    assert reopens == [] and cul.opened == 1


async def test_expired_command_does_not_reopen():
    cul = FakeCul()
    clock = LocalClock()
    h = _make(cul, local_now=clock)
    await h.start()
    await until(lambda: h.connected)
    reopens = _count_reopens(h)
    try:
        h.set_temperature(HT, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 9, 12, 30))
        await until(lambda: len(sent(cul)) == 1)
        clock.t = datetime(2026, 10, 9, 12, 31)
        await until(lambda: not h.devices[HT].has_pending, timeout=1.0)
        await asyncio.sleep(0.05)
        assert reopens == [] and cul.opened == 1
    finally:
        await h.stop()


# --- Block 2: Geraetekonfiguration ---

FACTORY_TEMP_PAYLOAD = "2A223D09071803"


def cfg_sent(cul, msg_type):
    # "Zs" + len(2) + counter(2) + flags(2) + type(2)
    return [l for l in sent(cul) if l[8:10] == f"{msg_type:02X}"]


async def test_devices_get_factory_config_at_start(hub):
    h, cul, rec = hub
    assert h.devices[HT].config["komfort"] == 21.0
    assert h.devices[HT].config_source["entkalkung_tag"] == "werksvorgabe"
    assert "boost_dauer" not in h.devices[WT].config
    assert h.devices[FK].config == {}


async def test_set_config_sends_whole_temperature_set_and_ack_commits(hub):
    h, cul, rec = hub
    h.devices[HT].config["eco"] = 16.0
    h.devices[HT].config_source["eco"] = "homegear"
    h.set_config(HT, "komfort", 22.5)
    dev = h.devices[HT]
    assert dev.pending_config["temp"]["komfort"] == 22.5 and dev.config["komfort"] == 21.0
    assert dev in rec.updates
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs" + "110100" + "11C0FFEEA1B00500" + "2D203D09071803"
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: not dev.pending_config)
    assert dev.config["komfort"] == 22.5 and dev.config["eco"] == 16.0
    assert dev.config_source["komfort"] == "gesetzt" and dev.config_source["eco"] == "gesetzt"
    assert dev.config_source["boost_dauer"] == "werksvorgabe"


async def test_set_config_valve_goes_to_heating_thermostat_only(hub):
    h, cul, rec = hub
    h.set_config(HT, "entkalkung_tag", "Mittwoch")
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs" + "0E0100" + "12C0FFEEA1B00500" + "308CFF00"
    with pytest.raises(FrameError):
        h.set_config(WT, "boost_dauer", 10)
    assert "valve" not in h.devices[WT].pending_config


async def test_set_config_wall_thermostat_temperatures(hub):
    h, cul, rec = hub
    h.set_config(WT, "offset", -1.0)
    await until(lambda: len(sent(cul)) == 1)
    assert sent(cul)[0] == "Zs" + "110100" + "11C0FFEE1590B400" + "2A223D09051803"


async def test_set_config_invalid_sends_nothing(hub):
    h, cul, rec = hub
    with pytest.raises(FrameError):
        h.set_config(HT, "komfort", 31.0)
    with pytest.raises(FrameError):
        h.set_config(FK, "komfort", 21.0)
    await asyncio.sleep(0.05)
    assert sent(cul) == [] and h.devices[HT].pending_config == {}


async def test_rapid_config_changes_newest_wins(hub):
    h, cul, rec = hub
    h.set_config(HT, "komfort", 22.0)
    h.set_config(HT, "eco", 16.0)
    h.set_config(HT, "komfort", 23.0)
    await until(lambda: len(sent(cul)) == 1)
    await asyncio.sleep(0.02)
    assert len(sent(cul)) == 1
    assert sent(cul)[0].endswith("2E203D09071803")
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: not h.devices[HT].pending_config)
    assert (h.devices[HT].config["komfort"], h.devices[HT].config["eco"]) == (23.0, 16.0)


async def test_ack_of_older_config_set_keeps_newer_pending(hub):
    h, cul, rec = hub
    h.set_config(HT, "komfort", 22.0)
    await until(lambda: len(sent(cul)) == 1)
    h.set_config(HT, "komfort", 23.0)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: h.devices[HT].config["komfort"] == 22.0)
    assert h.devices[HT].pending_config["temp"]["komfort"] == 23.0
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1].endswith("2E223D09071803")


async def test_unacked_config_is_marked_failed_and_resent_on_next_status(hub):
    h, cul, rec = hub
    h.set_config(HT, "komfort", 22.0)
    await heard_other_after_first_send(cul)
    await until(lambda: h.devices[HT].config_failed, timeout=1.0)
    assert len(sent(cul)) == 4
    dev = h.devices[HT]
    assert dev.pending_config["temp"]["komfort"] == 22.0 and dev.config["komfort"] == 21.0
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
    await until(lambda: len(sent(cul)) == 5)
    assert sent(cul)[4].endswith("2C223D09071803") and not dev.config_failed
    cul.feed(line(_counter(sent(cul)[4]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: dev.config["komfort"] == 22.0)
    assert dev.pending_config == {} and dev.config_source["komfort"] == "gesetzt"


async def test_nak_keeps_config_pending(hub):
    h, cul, rec = hub
    h.set_config(HT, "komfort", 22.0)
    await until(lambda: len(sent(cul)) == 1)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "81"))
    await until(lambda: h.devices[HT].config_failed)
    assert h.devices[HT].config["komfort"] == 21.0 and "temp" in h.devices[HT].pending_config


async def test_pending_config_is_resent_after_start():
    cul = FakeCul()
    devs = devices()
    devs[0].ensure_config_defaults()
    devs[0].stage_config("komfort", 22.0)
    devs[0].stage_config("boost_dauer", 10)
    h = MaxHub("/dev/x", CENTRAL, devs, on_update=lambda d: None, on_button=lambda d, t: None,
               on_device_added=lambda d: None, on_problem=lambda k: None,
               open_connection=cul.open, ack_timeout=0.05)
    await h.start()
    try:
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0].endswith("2C223D09071803")
        cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
        await until(lambda: len(sent(cul)) == 2)
        assert sent(cul)[1].endswith("500CFF00")
    finally:
        await h.stop()


async def test_failed_config_is_resent_after_reconnect():
    cul = FakeCul()
    h = _make(cul, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_config(HT, "komfort", 22.0)
        await heard_other_after_first_send(cul)
        await until(lambda: h.devices[HT].config_failed, timeout=1.0)
        cul.unplug()
        await until(lambda: cul.opened == 2 and h.connected)
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0].endswith("2C223D09071803")
        assert not h.devices[HT].config_failed
    finally:
        await h.stop()


async def test_unacked_config_without_rx_reopens_stick():
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    reopens = _count_reopens(h)
    try:
        h.set_config(HT, "komfort", 22.0)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        assert reopens == [1]
        await until(lambda: len(sent(cul)) == 1)
        assert sent(cul)[0].endswith("2C223D09071803")
    finally:
        await h.stop()


async def test_newly_paired_device_gets_factory_config(hub):
    h, cul, rec = hub
    h.open_pairing()
    ping = "10" + "01" + "00" + "MEQ0000001".encode().hex().upper()
    cul.feed(line(1, 0x00, MsgType.PAIR_PING, 0x123456, 0, 0, ping))
    await until(lambda: 0x123456 in h.devices)
    dev = h.devices[0x123456]
    assert dev.config["ventil_max"] == 100 and dev.config_source["ventil_max"] == "werksvorgabe"


async def test_successful_reset_drops_queued_config(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    task = asyncio.create_task(h.factory_reset(WT))
    await until(lambda: len(sent(cul)) == 1)
    h.set_config(WT, "komfort", 22.0)
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
    await until(lambda: len(sent(cul)) == 2)
    cul.feed(line(_counter(sent(cul)[1]), 0x02, MsgType.ACK, WT, CENTRAL, 0, "00"))
    assert await task is ResetResult.ACKED
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 2


# --- Block 2, Fix-Runde 1 ---

async def test_failed_temp_set_survives_valve_change_and_ack(hub):
    h, cul, rec = hub
    dev = h.devices[HT]
    h.set_config(HT, "komfort", 22.0)
    await heard_other_after_first_send(cul)
    await until(lambda: dev.config_failed == ["temp"], timeout=1.0)
    h.set_config(HT, "boost_dauer", 10)
    await until(lambda: len(sent(cul)) == 5)
    assert sent(cul)[4].endswith("500CFF00")
    cul.feed(line(_counter(sent(cul)[4]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: "valve" not in dev.pending_config)
    assert dev.config_failed == ["temp"] and dev.pending_config["temp"]["komfort"] == 22.0
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
    await until(lambda: len(sent(cul)) == 6)
    assert sent(cul)[5].endswith("2C223D09071803") and dev.config_failed == []


async def test_sending_assumed_factory_values_logs_warning(hub, caplog):
    h, cul, rec = hub
    dev = h.devices[HT]
    for key in ("komfort", "eco", "maximal", "offset", "fenster_temperatur"):
        dev.config_source[key] = "homegear"
    h.set_config(HT, "komfort", 22.0)
    assert "Sende angenommene Werksvorgaben mit: minimal, fenster_dauer" in caplog.text
    caplog.clear()
    for key in ("minimal", "fenster_dauer"):
        dev.config_source[key] = "gesetzt"
    h.set_config(HT, "eco", 16.0)
    assert "Werksvorgaben" not in caplog.text


# --- Block 3: Verknuepfungen ---

from custom_components.eq3_max.protocol.hub import link_status  # noqa: E402

HT_S, FK_S, PB_S, WT_S = "MEQ9000007", "NEQ9000010", "KEQ9000001", "NEQ9000011"
WAIT_FK = "wartet auf Fensterkontakt \u2013 bitte Fenster einmal \u00f6ffnen und schlie\u00dfen"


def link_frame(dst, partner, partner_type, msg_type=0x20):
    """Sent line without the counter: Zs/Zf + length, then flags..payload."""
    return f"0E??00{msg_type:02X}C0FFEE{dst:06X}00{partner:06X}{partner_type:02X}"


def matches(sent_line, expected):
    body = sent_line[2:]
    return body[:2] + body[4:] == expected[:2] + expected[4:]


def fast(cul):
    return [l for l in cul.written if l.startswith("Zf")]


def ack(cul, src, sent_line, ok=True):
    cul.feed(line(_counter(sent_line), 0x02, MsgType.ACK, src, CENTRAL, 0, "00" if ok else "80"))


async def test_link_ht_wt_sends_both_directions_and_pair_completes_after_both_acks(hub):
    h, cul, rec = hub
    h.link(HT, WT)
    st = link_status(h.devices, h.devices[HT])
    assert st.partners == [] and st.pending == [(WT_S, "ausstehend")]
    await until(lambda: len(sent(cul)) == 1)
    assert matches(sent(cul)[0], link_frame(HT, WT, 3))
    ack(cul, HT, sent(cul)[0])
    await until(lambda: h.devices[HT].links == [WT_S])
    assert h.devices[WT].links == []
    assert link_status(h.devices, h.devices[HT]).partners == []
    assert link_status(h.devices, h.devices[WT]).pending == [(HT_S, "ausstehend")]
    await until(lambda: len(sent(cul)) == 2)
    assert matches(sent(cul)[1], link_frame(WT, HT, 1))
    ack(cul, WT, sent(cul)[1])
    await until(lambda: h.devices[WT].links == [HT_S])
    for a, b in ((HT, WT_S), (WT, HT_S)):
        st = link_status(h.devices, h.devices[a])
        assert st.partners == [b] and st.pending == []
    assert h.devices[HT].pending_links == [] and h.devices[WT].pending_links == []
    assert h.devices[HT] in rec.updates and h.devices[WT] in rec.updates


async def test_link_contact_ht_side_now_contact_side_after_its_next_telegram_with_zf(hub):
    h, cul, rec = hub
    h.link(FK, HT)
    await until(lambda: len(sent(cul)) == 1)
    assert matches(sent(cul)[0], link_frame(HT, FK, 4))
    assert h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t"
    ack(cul, HT, sent(cul)[0])
    await until(lambda: h.devices[HT].links == [FK_S])
    await asyncio.sleep(0.05)
    assert fast(cul) == [] and len(sent(cul)) == 1
    assert link_status(h.devices, h.devices[HT]).pending == [(FK_S, WAIT_FK)]
    assert link_status(h.devices, h.devices[FK]).pending == [(HT_S, WAIT_FK)]
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
    await until(lambda: len(fast(cul)) == 1)
    assert matches(fast(cul)[0], link_frame(FK, HT, 1))
    assert h.devices[FK].link_op(HT_S)["state"] == "ausstehend"
    ack(cul, FK, fast(cul)[0])
    await until(lambda: h.devices[FK].links == [HT_S])
    assert link_status(h.devices, h.devices[FK]).partners == [HT_S]
    assert len(sent(cul)) == 1


async def test_deferred_link_survives_restart_and_goes_out_after_contact_telegram():
    devs = devices()
    devs[1].set_link_op(HT_S, HT, DeviceType.HEATING_THERMOSTAT, "add", "ausstehend")  # on air at shutdown
    devs = [MaxDevice.from_dict(d.to_dict()) for d in devs]
    cul = FakeCul()
    h = MaxHub("/dev/x", CENTRAL, devs, on_update=lambda d: None, on_button=lambda d, t: None,
               on_device_added=lambda d: None, on_problem=lambda k: None,
               open_connection=cul.open, ack_timeout=0.05, now=lambda: 1_700_000_000.0)
    await h.start()
    try:
        await until(lambda: h.connected)
        await asyncio.sleep(0.05)
        assert sent(cul) == [] and fast(cul) == []
        assert h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t"
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
        await until(lambda: len(fast(cul)) == 1)
        assert matches(fast(cul)[0], link_frame(FK, HT, 1))
    finally:
        await h.stop()


async def test_pending_thermostat_link_is_sent_after_start():
    devs = devices()
    devs[0].set_link_op(WT_S, WT, DeviceType.WALL_THERMOSTAT, "add", "fehlgeschlagen")
    cul = FakeCul()
    h = _make(cul)
    h.devices[HT].pending_links = devs[0].pending_links
    await h.start()
    try:
        await until(lambda: len(sent(cul)) == 1)
        assert matches(sent(cul)[0], link_frame(HT, WT, 3))
        assert h.devices[HT].link_op(WT_S)["state"] == "ausstehend"
    finally:
        await h.stop()


async def test_unlink_is_symmetric(hub):
    h, cul, rec = hub
    h.devices[HT].links = [FK_S]
    h.devices[FK].links = [HT_S]
    h.unlink(HT, FK)
    await until(lambda: len(sent(cul)) == 1)
    assert matches(sent(cul)[0], link_frame(HT, FK, 4, 0x21))
    ack(cul, HT, sent(cul)[0])
    await until(lambda: h.devices[HT].links == [])
    assert h.devices[FK].links == [HT_S]
    assert link_status(h.devices, h.devices[HT]).pending == [(FK_S, WAIT_FK)]
    cul.feed(line(8, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
    await until(lambda: len(fast(cul)) == 1)
    assert matches(fast(cul)[0], link_frame(FK, HT, 1, 0x21))
    ack(cul, FK, fast(cul)[0])
    await until(lambda: h.devices[FK].links == [])
    assert link_status(h.devices, h.devices[FK]) == link_status(h.devices, h.devices[HT])
    assert link_status(h.devices, h.devices[FK]).pending == []


async def test_disallowed_self_and_duplicate_links_are_rejected(hub):
    h, cul, rec = hub
    with pytest.raises(FrameError, match="nicht verkn\u00fcpfen"):
        h.link(FK, PB)
    with pytest.raises(FrameError, match="sich selbst"):
        h.link(HT, HT)
    with pytest.raises(FrameError, match="nicht bekannt"):
        h.link(HT, 0x123456)
    h.devices[HT].links = [WT_S]
    h.devices[WT].links = [HT_S]
    with pytest.raises(FrameError, match="bereits verkn\u00fcpft"):
        h.link(WT, HT)
    with pytest.raises(FrameError, match="nicht verkn\u00fcpft"):
        h.unlink(HT, FK)
    h.link(HT, FK)
    with pytest.raises(FrameError, match="bereits beauftragt"):
        h.link(FK, HT)
    await asyncio.sleep(0.05)
    assert len(sent(cul)) == 1  # only the HT side of HT-FK
    assert h.devices[PB].pending_links == [] and h.devices[WT].pending_links == []


async def test_half_link_sends_only_the_missing_direction(hub):
    h, cul, rec = hub
    h.devices[FK].links = [HT_S]
    assert link_status(h.devices, h.devices[HT]).pending == [(FK_S, "einseitig")]
    h.link(HT, FK)
    await until(lambda: len(sent(cul)) == 1)
    assert h.devices[FK].pending_links == []
    ack(cul, HT, sent(cul)[0])
    await until(lambda: link_status(h.devices, h.devices[HT]).partners == [FK_S])


async def test_unlinking_a_never_sent_contact_link_just_drops_it(hub):
    h, cul, rec = hub
    h.link(HT, FK)
    await until(lambda: len(sent(cul)) == 1)
    ack(cul, HT, sent(cul)[0])
    await until(lambda: h.devices[HT].links == [FK_S])
    h.unlink(HT, FK)
    assert h.devices[FK].pending_links == []
    await until(lambda: len(sent(cul)) == 2)
    assert matches(sent(cul)[1], link_frame(HT, FK, 4, 0x21))


async def test_failed_link_is_retried_on_next_status(hub):
    h, cul, rec = hub
    h.link(HT, WT)
    await heard_other_after_first_send(cul)
    await until(lambda: h.devices[HT].link_op(WT_S)["state"] == "fehlgeschlagen", timeout=1.0)
    assert link_status(h.devices, h.devices[WT]).pending == [(HT_S, "fehlgeschlagen")]
    await until(lambda: len(sent(cul)) == 5)  # 4 attempts to HT, then the WT side
    assert matches(sent(cul)[4], link_frame(WT, HT, 1))
    ack(cul, WT, sent(cul)[4])
    await until(lambda: h.devices[WT].links == [HT_S])
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
    await until(lambda: len(sent(cul)) == 6)
    assert matches(sent(cul)[5], link_frame(HT, WT, 3))
    ack(cul, HT, sent(cul)[5])
    await until(lambda: link_status(h.devices, h.devices[HT]).partners == [WT_S])


async def test_failed_contact_link_waits_for_next_contact_telegram(hub):
    h, cul, rec = hub
    h.devices[HT].links = [FK_S]
    h.link(FK, HT)
    cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "12"))
    await until(lambda: len(fast(cul)) == 1)
    # Fix round 1: a missed fast send goes back to waiting (not failed).
    await until(lambda: h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t", timeout=1.5)
    n = len(fast(cul))
    cul.feed(line(9, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
    await until(lambda: len(fast(cul)) == n + 1)


async def test_failed_link_is_resent_after_reconnect():
    cul = FakeCul()
    h = _make(cul, transport_kwargs={"reconnect_delay": 0.01})
    await h.start()
    await until(lambda: h.connected)
    try:
        h.devices[WT].links = [HT_S]
        h.link(HT, WT)
        await heard_other_after_first_send(cul)
        await until(lambda: h.devices[HT].link_op(WT_S)["state"] == "fehlgeschlagen", timeout=1.0)
        cul.unplug()
        await until(lambda: cul.opened == 2 and h.connected)
        await until(lambda: len(sent(cul)) == 1)
        assert matches(sent(cul)[0], link_frame(HT, WT, 3))
    finally:
        await h.stop()


async def test_factory_reset_clears_links_and_pending_link_ops(hub):
    h, cul, rec = hub
    h.devices[HT].links = [FK_S, WT_S]
    h.devices[WT].links = [HT_S]
    h.devices[FK].links = [HT_S]
    h.link(WT, FK)  # WT side queued, FK side deferred
    task = asyncio.create_task(h.factory_reset(FK))
    await until(lambda: len(sent(cul)) == 1)
    ack(cul, WT, sent(cul)[0])  # WT acks its AddLinkPartner(FK)
    await until(lambda: len(sent(cul)) == 2)
    assert sent(cul)[1][8:10] == "F0"
    ack(cul, FK, sent(cul)[1])
    assert await asyncio.wait_for(task, 1) is ResetResult.ACKED
    assert h.devices[HT].links == [WT_S]
    assert h.devices[WT].links == [HT_S]
    assert h.devices[HT] in rec.updates
    # Fix round 1: the former partners get RemoveLinkPartner(FK), shown as pending.
    for dev in (h.devices[HT], h.devices[WT]):
        assert dev.link_op(FK_S)["op"] == "remove"
        assert (FK_S, "ausstehend") in link_status(h.devices, dev).pending
    await until(lambda: len(sent(cul)) == 3)
    assert matches(sent(cul)[2], link_frame(HT, FK, 4, 0x21))
    ack(cul, HT, sent(cul)[2])
    await until(lambda: len(sent(cul)) == 4)
    assert matches(sent(cul)[3], link_frame(WT, FK, 4, 0x21))
    ack(cul, WT, sent(cul)[3])
    await until(lambda: h.devices[WT].pending_links == [])
    assert h.devices[HT].pending_links == []
    assert link_status(h.devices, h.devices[WT]).pending == []
    assert fast(cul) == []


async def test_factory_reset_drops_queued_link_commands_to_the_reset_device(hub):
    h, cul, rec = hub
    h.set_temperature(HT, 21.0, Mode.MANUAL)
    task = asyncio.create_task(h.factory_reset(WT))
    await until(lambda: len(sent(cul)) == 1)
    h.link(WT, HT)  # both directions queued behind the reset
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "0119302A"))
    await until(lambda: len(sent(cul)) == 2)
    ack(cul, WT, sent(cul)[1])
    assert await task is ResetResult.ACKED
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 2
    assert h.devices[HT].pending_links == []


# --- Block 3, Fix-Runde 1 ---

def _fast_hub(cul, **over):
    kwargs = dict(fast_ack_timeout=0.1)
    kwargs.update(over)
    return _make(cul, **kwargs)


def to_us(counter, payload="10"):
    return line(counter, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, payload)


async def _started(h, cul):
    await h.start()
    await until(lambda: h.connected)
    h.devices[HT].links = [FK_S]
    h.link(FK, HT)  # only the contact side is missing


async def test_fast_send_blocked_behind_zs_expires_and_waits_again_without_airtime():
    cul = FakeCul()
    h = _fast_hub(cul, ack_timeout=0.2)
    await _started(h, cul)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: len(sent(cul)) == 1)
        cul.feed(to_us(7))
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == "ausstehend")
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t", timeout=2.0)
        await until(lambda: len(sent(cul)) == 4, timeout=2.0)  # the set command's attempts
        await asyncio.sleep(0.1)
        assert fast(cul) == [] and all(l[8:10] == "40" for l in sent(cul))
        assert h._fast_misses == {}  # nothing went on air: no miss counted
    finally:
        await h.stop()


async def test_fast_no_ack_waits_again_without_retries_then_zs_on_third_attempt():
    cul = FakeCul()
    h = _fast_hub(cul)
    await _started(h, cul)
    waiting = "wartet auf Ger\u00e4t"
    try:
        cul.feed(to_us(7))
        await until(lambda: len(fast(cul)) == 1)
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == waiting)
        await asyncio.sleep(0.15)
        assert len(fast(cul)) == 1 and sent(cul) == []  # one attempt, no retries
        cul.feed(to_us(8))
        await until(lambda: len(fast(cul)) == 2)
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == waiting)
        cul.feed(to_us(9))
        await until(lambda: len(sent(cul)) == 1)
        assert matches(sent(cul)[0], link_frame(FK, HT, 1)) and len(fast(cul)) == 2
        ack(cul, FK, sent(cul)[0])
        await until(lambda: h.devices[FK].links == [HT_S])
        assert h._fast_misses == {}
    finally:
        await h.stop()


async def test_contact_frame_to_its_thermostat_does_not_trigger():
    cul = FakeCul()
    h = _fast_hub(cul)
    await _started(h, cul)
    try:
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, HT, 0, "12"))
        await until(lambda: h.devices[FK].window_open is True)
        await asyncio.sleep(0.2)
        assert fast(cul) == [] and h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t"
    finally:
        await h.stop()


async def test_frame_to_us_triggers_after_debounce_and_burst_flushes_once():
    cul = FakeCul()
    h = _fast_hub(cul)
    await _started(h, cul)
    flushes = []
    orig = h._flush_sleeper

    def counting(dev):
        flushes.append(dev.address)
        orig(dev)

    h._flush_sleeper = counting
    try:
        for counter in (7, 8, 9):
            cul.feed(to_us(counter))
            await asyncio.sleep(0.03)
        assert flushes == [] and fast(cul) == []
        await until(lambda: len(fast(cul)) == 1)
        await asyncio.sleep(0.1)
        assert flushes == [FK]
    finally:
        await h.stop()


async def test_nak_on_link_is_terminal_until_a_new_request(hub):
    h, cul, rec = hub
    h.link(HT, WT)
    await until(lambda: len(sent(cul)) == 1)
    ack(cul, HT, sent(cul)[0], ok=False)
    rejected = "fehlgeschlagen (abgelehnt)"
    await until(lambda: h.devices[HT].link_op(WT_S)["state"] == rejected)
    assert link_status(h.devices, h.devices[HT]).pending == [(WT_S, rejected)]
    await until(lambda: len(sent(cul)) == 2)  # the WT side
    ack(cul, WT, sent(cul)[1])
    await until(lambda: h.devices[WT].links == [HT_S])
    cul.feed(line(9, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
    await asyncio.sleep(0.1)
    assert len(sent(cul)) == 2  # no automatic resend
    h.link(HT, WT)
    await until(lambda: len(sent(cul)) == 3)
    assert matches(sent(cul)[2], link_frame(HT, WT, 3))


async def test_nak_on_fast_contact_link_is_terminal():
    cul = FakeCul()
    h = _fast_hub(cul)
    await _started(h, cul)
    try:
        cul.feed(to_us(7))
        await until(lambda: len(fast(cul)) == 1)
        ack(cul, FK, fast(cul)[0], ok=False)
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == "fehlgeschlagen (abgelehnt)")
        cul.feed(to_us(8))
        await asyncio.sleep(0.2)
        assert len(fast(cul)) == 1 and sent(cul) == []
    finally:
        await h.stop()


async def test_factory_reset_unlinks_former_partners_sleepers_deferred(hub):
    h, cul, rec = hub
    h.devices[HT].links = [FK_S, WT_S]
    h.devices[FK].links = [HT_S]
    h.devices[WT].links = [HT_S]
    task = asyncio.create_task(h.factory_reset(HT))
    await until(lambda: len(sent(cul)) == 1)
    ack(cul, HT, sent(cul)[0])
    assert await asyncio.wait_for(task, 1) is ResetResult.ACKED
    assert h.devices[FK].links == [] and h.devices[WT].links == []
    assert h.devices[FK].link_op(HT_S) == {
        "partner": HT_S, "address": HT, "device_type": 1, "op": "remove", "state": "wartet auf Ger\u00e4t",
    }
    assert link_status(h.devices, h.devices[FK]).pending == [(HT_S, WAIT_FK)]
    await until(lambda: len(sent(cul)) == 2)
    assert matches(sent(cul)[1], link_frame(WT, HT, 1, 0x21))
    assert fast(cul) == []
    cul.feed(to_us(7))
    await until(lambda: len(fast(cul)) == 1)
    assert matches(fast(cul)[0], link_frame(FK, HT, 1, 0x21))


async def test_push_button_waiting_text(hub):
    h, cul, rec = hub
    h.link(PB, WT)
    assert link_status(h.devices, h.devices[WT]).pending == [
        (PB_S, "wartet auf Eco-Taster \u2013 bitte Taster einmal dr\u00fccken (oder Anlerntaste)")
    ]


async def test_zs_fallback_to_contact_without_ack_never_reopens_stick():
    cul = FakeCul()
    h = _fast_hub(cul)
    await _started(h, cul)
    reopens = _count_reopens(h)
    try:
        h._fast_misses[(FK, HT_S)] = 2  # two unheard Zf sends before
        cul.feed(to_us(7))
        await until(lambda: len(sent(cul)) == 1)
        assert matches(sent(cul)[0], link_frame(FK, HT, 1))
        # no ack, nothing received: all attempts run out
        await until(lambda: h.devices[FK].link_op(HT_S)["state"] == "wartet auf Ger\u00e4t", timeout=2.0)
        await asyncio.sleep(0.1)
        assert reopens == [] and cul.opened == 1
    finally:
        await h.stop()


async def test_set_config_set_sends_exactly_one_frame_for_several_values(hub):
    h, cul, rec = hub
    assumed = h.set_config_set(HT, "temp", {"komfort": 22.5, "eco": 16.0, "fenster_dauer": 20})
    assert assumed == ["maximal", "minimal", "offset", "fenster_temperatur"]
    dev = h.devices[HT]
    assert dev in rec.updates
    await until(lambda: len(sent(cul)) == 1)
    await asyncio.sleep(0.03)
    assert len(sent(cul)) == 1
    assert sent(cul)[0] == "Zs" + "110100" + "11C0FFEEA1B00500" + "2D203D09071804"
    cul.feed(line(_counter(sent(cul)[0]), 0x02, MsgType.ACK, HT, CENTRAL, 0, "01"))
    await until(lambda: not dev.pending_config)
    assert (dev.config["komfort"], dev.config["eco"], dev.config["fenster_dauer"]) == (22.5, 16.0, 20)


async def test_set_config_set_invalid_sends_nothing(hub):
    h, cul, rec = hub
    with pytest.raises(FrameError):
        h.set_config_set(HT, "temp", {"komfort": 22.5, "eco": 99})
    with pytest.raises(FrameError):
        h.set_config_set(0x123456, "temp", {"komfort": 22.5})
    await asyncio.sleep(0.05)
    assert sent(cul) == [] and h.devices[HT].pending_config == {}


async def test_pairing_remaining():
    clock = {"t": 1000.0}
    h = MaxHub(
        "/dev/x", CENTRAL, devices(), on_update=lambda d: None, on_button=lambda d, t: None,
        on_device_added=lambda d: None, on_problem=lambda k: None, now=lambda: clock["t"],
    )
    assert h.pairing_remaining == 0
    h.open_pairing(60)
    clock["t"] += 15.5
    assert h.pairing_remaining == 44.5
    clock["t"] += 100
    assert h.pairing_remaining == 0


async def test_factory_log_lists_only_values_going_along(hub, caplog):
    h, cul, rec = hub
    caplog.set_level("WARNING")
    assumed = h.set_config_set(HT, "temp", {"komfort": 22.5, "eco": 16.0})
    logs = [r.getMessage() for r in caplog.records if "Werksvorgaben" in r.getMessage()]
    assert logs and logs[-1].endswith(": " + ", ".join(assumed))
    assert "komfort" not in logs[-1] and "eco" not in logs[-1]
    caplog.clear()
    h.set_config(HT, "boost_dauer", 10)
    logs = [r.getMessage() for r in caplog.records if "Werksvorgaben" in r.getMessage()]
    assert logs[-1].endswith(": boost_ventil, entkalkung_tag, entkalkung_stunde, ventil_max, ventil_offset")



# --- one unreachable device must not reopen the stick again and again ---


def _all_sent(cul):
    """Zs lines of all connections so far (all_written holds only the closed ones)."""
    return [l for l in cul.all_written + cul.written if l.startswith("Zs")]


async def test_unreachable_device_does_not_reopen_once_the_stick_proved_it_hears(caplog):
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        # After the reopen the stick hears another device: it was never deaf.
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
        await until(lambda: h.devices[FK].window_open is False)
        assert h.silent_devices == [HT]
        caplog.clear()
        h.set_temperature(HT, 22.0, Mode.MANUAL)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        await asyncio.sleep(0.05)
        assert cul.opened == 2
        assert "neu geoeffnet" not in caplog.text
        # HT is heard again: it is no longer silent, a later failure may reopen once more.
        cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302A00BE"))
        await until(lambda: h.silent_devices == [])
    finally:
        await h.stop()


async def test_failed_command_of_silent_device_is_not_resent_on_reconnect():
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
        await until(lambda: h.silent_devices == [HT])
        before = len(_all_sent(cul))
        # A reconnect (e.g. the watchdog) must not fire the silent device's command again.
        h._transport.request_reopen = lambda: False
        h._on_connection(True)
        await asyncio.sleep(0.1)
        assert len(_all_sent(cul)) == before
        # Its next status (still 20.0 instead of 21.0) brings the command out again.
        cul.feed(line(5, 0x04, MsgType.THERMOSTAT_STATE, HT, CENTRAL, 0, "19302800BE"))
        await until(lambda: len(_all_sent(cul)) > before)
    finally:
        await h.stop()


async def test_other_device_still_reopens_a_really_deaf_stick():
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        cul.feed(line(7, 0x06, MsgType.SHUTTER_CONTACT_STATE, FK, CENTRAL, 0, "10"))
        await until(lambda: h.silent_devices == [HT])
        # A different, reachable device fails while nothing comes in: that is the stick.
        h.set_temperature(WT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 3 and h.connected, timeout=1.0)
    finally:
        await h.stop()


async def test_reopen_warning_only_when_the_port_is_really_reopened(caplog):
    cul = FakeCul()
    h = _make(cul)
    await h.start()
    await until(lambda: h.connected)
    try:
        h.set_temperature(HT, 21.0, Mode.MANUAL)
        await until(lambda: cul.opened == 2 and h.connected, timeout=1.0)
        assert caplog.text.count("neu geoeffnet") == 1
        caplog.clear()
        # Same quiet episode: the transport refuses a second fast reopen.
        await until(lambda: h.devices[HT].command_failed, timeout=1.0)
        await asyncio.sleep(0.02)
        h.set_temperature(HT, 21.5, Mode.MANUAL)
        await until(lambda: h.devices[HT].command_failed and h.devices[HT].pending_target == 21.5, timeout=1.0)
        await asyncio.sleep(0.05)
        assert cul.opened == 2
        assert "neu geoeffnet" not in caplog.text
    finally:
        await h.stop()
