from datetime import datetime

import pytest

from custom_components.eq3_max.protocol.messages import (
    DeviceType,
    Frame,
    FrameError,
    Mode,
    MsgType,
    build_pair_pong,
    build_set_temperature,
    build_time_information,
    decode_ack,
    decode_frame,
    decode_pair_ping,
    decode_push_button_state,
    decode_set_temperature,
    decode_shutter_contact_state,
    decode_status_bits,
    decode_thermostat_state,
    decode_time_information,
    decode_wall_thermostat_control,
    decode_wall_thermostat_state,
    build_reset,
    decode_until,
    encode_frame,
    encode_until,
    normalize_temperature,
    round_until,
    rssi_to_dbm,
)

CENTRAL = 0xC0FFEE
BAD_UNTEN = 0xA1B005

# Echte Telegramme aus dem Homegear-Log vom 14.09.2026 16:48:59/16:49:00
REAL_SENT = "0BF20540C0FFEEA1B0050149"
REAL_ACK = "Z0EF20202A1B005C0FFEE0001193009"


def test_decode_real_ack_from_homegear_log():
    frame = decode_frame(REAL_ACK)
    assert frame == Frame(
        counter=0xF2, flags=0x02, msg_type=MsgType.ACK, src=BAD_UNTEN,
        dst=CENTRAL, group=0, payload=bytes.fromhex("01193009"), rssi=None,
    )
    ack = decode_ack(frame.payload)
    assert ack.ok is True
    state = decode_thermostat_state(ack.state_payload)
    assert state.bits.mode is Mode.MANUAL
    assert state.valve == 48
    assert state.target == 4.5
    assert state.measured is None


def test_encode_real_sent_frame_roundtrip():
    frame = decode_frame("Z" + REAL_SENT)
    assert frame.flags == 0x05 and frame.group == 0x01
    assert decode_set_temperature(frame.payload) == (Mode.MANUAL, 4.5)
    assert encode_frame(frame) == REAL_SENT


def test_rssi_byte_is_split_off_and_converted():
    frame = decode_frame(REAL_ACK + "3F")
    assert frame.rssi == -42.5
    assert encode_frame(frame) == REAL_ACK[1:]


def test_rssi_to_dbm_negative_branch():
    assert rssi_to_dbm(0x3F) == -42.5
    assert rssi_to_dbm(200) == -102.0


@pytest.mark.parametrize("line", ["", "V 1.66", "Z0E", "Z0EF2XX", "Z0EF20202A1B005C0FFEE00011930"])
def test_bad_lines_raise_frame_error(line):
    with pytest.raises(FrameError):
        decode_frame(line)


def test_status_bits_each_bit():
    assert decode_status_bits(0x00).mode is Mode.AUTO
    assert decode_status_bits(0x03).mode is Mode.BOOST
    assert decode_status_bits(0x08).dst_active is True
    assert decode_status_bits(0x10).gateway is True
    assert decode_status_bits(0x20).locked is True
    assert decode_status_bits(0x40).rf_error is True
    assert decode_status_bits(0x80).battery_low is True
    bits = decode_status_bits(0x80)
    assert (bits.locked, bits.rf_error, bits.dst_active) == (False, False, False)


def test_thermostat_state_with_measured_temperature():
    state = decode_thermostat_state(bytes.fromhex("19302A00BE"))
    assert state.target == 21.0
    assert state.measured == 19.0


def test_thermostat_state_measured_above_25_5():
    state = decode_thermostat_state(bytes.fromhex("19302A0104"))
    assert state.measured == 26.0


def test_temporary_mode_has_no_measured_temperature():
    state = decode_thermostat_state(bytes.fromhex("1A302A9D0B1E"))
    assert state.bits.mode is Mode.TEMPORARY
    assert state.measured is None


def test_thermostat_state_ignores_implausible_measured():
    assert decode_thermostat_state(bytes.fromhex("19302A0003")).measured is None


def test_wall_thermostat_state_full():
    st = decode_wall_thermostat_state(bytes.fromhex("19002A000000D2"))
    assert st.bits.mode is Mode.MANUAL
    assert st.target == 21.0
    assert st.measured == 21.0


def test_wall_thermostat_state_short_has_no_measured():
    st = decode_wall_thermostat_state(bytes.fromhex("19002A"))
    assert st.target == 21.0 and st.measured is None


def test_wall_thermostat_control():
    st = decode_wall_thermostat_control(bytes.fromhex("2AD2"))
    assert st.bits is None and st.target == 21.0 and st.measured == 21.0


def test_shutter_contact_open_closed():
    assert decode_shutter_contact_state(b"\x12").is_open is True
    closed = decode_shutter_contact_state(b"\x90")
    assert closed.is_open is False and closed.battery_low is True


def test_push_button_auto_and_eco():
    assert decode_push_button_state(bytes.fromhex("1001")).auto is True
    assert decode_push_button_state(bytes.fromhex("1000")).auto is False


def test_pair_ping():
    payload = bytes.fromhex("100100") + b"ABC1234567"
    ping = decode_pair_ping(payload)
    assert ping.firmware == "1.0"
    assert ping.device_type is DeviceType.HEATING_THERMOSTAT
    assert ping.serial == "ABC1234567"


def test_pair_ping_unknown_device_type_raises_frame_error():
    payload = bytes.fromhex("100900") + b"ABC1234567"
    with pytest.raises(FrameError):
        decode_pair_ping(payload)


def test_time_information_out_of_range_raises_frame_error():
    with pytest.raises(FrameError):
        decode_time_information(bytes.fromhex("1A090E2531"))


def test_set_temperature_temporary_mode_without_until_rejected():
    with pytest.raises(FrameError):
        build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, 21.0, Mode.TEMPORARY)


def test_set_temperature_until_only_with_temporary():
    with pytest.raises(FrameError):
        build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, 21.0, Mode.MANUAL, until=datetime(2026, 10, 10, 14, 30))


def test_set_temperature_temporary_with_until():
    f = build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, 18.0, Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    # 18.0 -> 0x24 | mode 2 << 6 = 0xA4; Okt = 0b1010: b1 = 0xA0|10, b2 = 0x00|26, b3 = 29
    assert f.payload == bytes([0xA4, 0xAA, 0x1A, 0x1D])
    assert encode_frame(f) == "0E010040C0FFEEA1B00500A4AA1A1D"


def test_set_temperature_none_requires_auto_mode():
    with pytest.raises(FrameError):
        build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, None, Mode.MANUAL)


def test_ack_nak_bit():
    assert decode_ack(b"\x81").ok is False
    assert decode_ack(b"\x01").state_payload == b""


def test_build_set_temperature_manual_no_group():
    frame = build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, 21.0, Mode.MANUAL)
    assert encode_frame(frame) == "0B010040C0FFEEA1B005006A"


def test_build_set_temperature_group_sets_flag_04():
    frame = build_set_temperature(1, CENTRAL, BAD_UNTEN, 1, 21.0, Mode.MANUAL)
    assert frame.flags == 0x04 and frame.group == 1


@pytest.mark.parametrize(
    ("temp", "expected"),
    [(3.0, 4.5), (31.0, 30.5), (20.74, 20.5), (20.76, 21.0)],
)
def test_build_set_temperature_clamps_and_rounds(temp, expected):
    frame = build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, temp, Mode.MANUAL)
    assert decode_set_temperature(frame.payload) == (Mode.MANUAL, expected)


def test_build_set_temperature_auto_without_temperature():
    frame = build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, None, Mode.AUTO)
    assert frame.payload == b"\x00"


def test_counter_wraps_modulo_256():
    frame = build_set_temperature(256, CENTRAL, BAD_UNTEN, 0, 21.0, Mode.MANUAL)
    assert frame.counter == 0
    assert len(encode_frame(frame)) == 24


def test_build_pair_pong():
    assert encode_frame(build_pair_pong(7, CENTRAL, BAD_UNTEN)) == "0B070001C0FFEEA1B0050000"


def test_time_information_roundtrip():
    now = datetime(2026, 10, 9, 14, 37, 12)
    frame = build_time_information(3, CENTRAL, BAD_UNTEN, now)
    assert frame.flags == 0x04 and frame.msg_type == MsgType.TIME_INFORMATION
    assert decode_time_information(frame.payload) == now


# --- final fix wave ---

@pytest.mark.parametrize(
    ("temp", "expected"),
    [(20.8, 21.0), (20.25, 20.5), (20.75, 21.0), (20.7, 20.5), (21.0, 21.0), (3.0, 4.5), (35.0, 30.5)],
)
def test_normalize_temperature_half_up_and_clamped(temp, expected):
    assert normalize_temperature(temp) == expected


def test_build_set_temperature_rounds_quarter_half_up():
    frame = build_set_temperature(1, CENTRAL, BAD_UNTEN, 0, 20.25, Mode.MANUAL)
    assert decode_set_temperature(frame.payload) == (Mode.MANUAL, 20.5)


def test_wall_thermostat_state_ignores_implausible_measured():
    assert decode_wall_thermostat_state(bytes.fromhex("19002A00000003")).measured is None


def test_wall_thermostat_control_ignores_implausible_measured():
    assert decode_wall_thermostat_control(bytes.fromhex("2A05")).measured is None


def test_wall_thermostat_state_five_bytes_has_measured():
    # Echter Mitschnitt 09.10.2026 13:50:41 (WT NEQ9000011), Homegear las
    # ACTUAL_TEMPERATURE = 0x00D8 = 21.6 aus Byte 3/4.
    frame = decode_frame("Z0F8C0470A1B0070000000059042B00D841")
    st = decode_wall_thermostat_state(frame.payload)
    assert st.target == 21.5
    assert st.measured == 21.6
    assert st.bits.rf_error is True


def test_wall_thermostat_state_five_bytes_temporary_has_no_measured():
    assert decode_wall_thermostat_state(bytes.fromhex("1A042B00D8")).measured is None


# --- Block 1: temporaer (Urlaub) und Werksreset ---

@pytest.mark.parametrize(
    "end",
    [
        datetime(2026, 1, 1, 0, 0),
        datetime(2026, 2, 28, 12, 30),
        datetime(2028, 2, 29, 7, 0),
        datetime(2026, 7, 31, 23, 30),
        datetime(2026, 12, 31, 23, 30),
        datetime(2026, 8, 15, 0, 30),
        datetime(2063, 11, 30, 18, 0),
    ],
)
def test_until_roundtrip(end):
    raw = encode_until(end)
    assert len(raw) == 3
    assert decode_until(raw) == end


def test_until_layout_like_fhem():
    # Dez = 0b1100: (12 & 0x0E) << 4 = 0xC0, Bit 0 = 0 -> b2 ohne 0x80
    assert encode_until(datetime(2026, 12, 31, 23, 30)) == bytes([0xDF, 0x1A, 47])
    # Jan = 0b0001: nur das Monatsbit in b2
    assert encode_until(datetime(2026, 1, 5, 6, 0)) == bytes([0x05, 0x9A, 12])
    # Jul = 0b0111
    assert encode_until(datetime(2026, 7, 31, 23, 30)) == bytes([0x7F, 0x9A, 47])


@pytest.mark.parametrize("end", [datetime(2026, 1, 1, 10, 15), datetime(1999, 1, 1, 10, 0), datetime(2064, 1, 1, 10, 0)])
def test_encode_until_rejects_unencodable(end):
    with pytest.raises(FrameError):
        encode_until(end)


@pytest.mark.parametrize("raw", ["001A1D", "DF1A30", "3F1A00", "AA1A3F", "051A00"])
def test_decode_until_invalid_date_raises(raw):
    # Tag 0, Stunde 24, 31. Februar, Stunde 31, Monat 0
    with pytest.raises(FrameError):
        decode_until(bytes.fromhex(raw))


@pytest.mark.parametrize(
    "value,expected",
    [
        (datetime(2026, 10, 9, 14, 17, 12), datetime(2026, 10, 9, 14, 30)),
        (datetime(2026, 10, 9, 14, 30, 0), datetime(2026, 10, 9, 14, 30)),
        (datetime(2026, 10, 9, 14, 30, 59), datetime(2026, 10, 9, 15, 0)),
        (datetime(2026, 10, 9, 14, 30, 0, 1), datetime(2026, 10, 9, 15, 0)),
        (datetime(2026, 10, 9, 14, 29, 30), datetime(2026, 10, 9, 14, 30)),
        (datetime(2026, 10, 9, 14, 31), datetime(2026, 10, 9, 15, 0)),
        (datetime(2026, 10, 9, 14, 0, 30), datetime(2026, 10, 9, 14, 30)),
        (datetime(2026, 10, 9, 23, 30, 1), datetime(2026, 10, 10, 0, 0)),
        (datetime(2026, 12, 31, 23, 45), datetime(2027, 1, 1, 0, 0)),
    ],
)
def test_round_until_rounds_up_to_half_hour(value, expected):
    assert round_until(value) == expected


def test_thermostat_state_temporary_carries_until():
    # Mitschnitt-Layout: Modus temporaer, Bytes 3..5 = Ende 29.08.2011 15:00
    state = decode_thermostat_state(bytes.fromhex("1A302A9D0B1E"))
    assert state.until == datetime(2011, 8, 29, 15, 0)
    st2 = decode_thermostat_state(bytes.fromhex("1A302A") + encode_until(datetime(2026, 10, 10, 14, 30)))
    assert st2.until == datetime(2026, 10, 10, 14, 30) and st2.measured is None


def test_thermostat_state_manual_has_no_until():
    assert decode_thermostat_state(bytes.fromhex("19302A00BE00")).until is None


def test_thermostat_state_temporary_invalid_until_keeps_rest():
    state = decode_thermostat_state(bytes.fromhex("1A302A001A1D"))
    assert state.until is None and state.target == 21.0 and state.valve == 48


def test_wall_thermostat_state_seven_bytes_with_until():
    until = encode_until(datetime(2026, 10, 10, 14, 30))
    st = decode_wall_thermostat_state(bytes([0x1A, 0x00, 0x24]) + until + bytes([0xD2]))
    assert st.until == datetime(2026, 10, 10, 14, 30)
    assert st.target == 18.0
    # Gemessen kommt weiter aus Byte 6, nicht aus Byte 4 (dort steckt das Jahr).
    assert st.measured == 21.0


def test_wall_thermostat_state_seven_bytes_without_until():
    st = decode_wall_thermostat_state(bytes.fromhex("19002A000000D2"))
    assert st.until is None and st.measured == 21.0


def test_build_reset():
    f = build_reset(0x105, CENTRAL, BAD_UNTEN)
    assert (f.counter, f.flags, f.msg_type, f.group, f.payload) == (0x05, 0x00, 0xF0, 0, b"")
    assert encode_frame(f) == "0A0500F0C0FFEEA1B00500"


# --- Block 2: Geraetekonfiguration (0x11 ConfigTemperatures, 0x12 ConfigValve) ---

from custom_components.eq3_max.protocol.messages import (  # noqa: E402
    BOOST_DURATIONS,
    TemperatureConfig,
    ValveConfig,
    build_config_temperatures,
    build_config_valve,
    decode_config_temperatures,
    decode_config_valve,
    encode_config_temperatures,
    encode_config_valve,
)

FACTORY_TEMPS = TemperatureConfig(
    comfort=21.0, eco=17.0, max_temperature=30.5, min_temperature=4.5,
    offset=0.0, window_open_temperature=12.0, window_open_duration=15,
)
FACTORY_VALVE = ValveConfig(
    boost_duration=5, boost_valve=80, decalc_day=0, decalc_hour=12, max_valve=100, valve_offset=0,
)


def test_config_temperatures_factory_payload():
    assert encode_config_temperatures(FACTORY_TEMPS).hex().upper() == "2A223D09071803"
    assert decode_config_temperatures(bytes.fromhex("2A223D09071803")) == FACTORY_TEMPS


def test_config_temperatures_boundaries_roundtrip():
    low = TemperatureConfig(4.5, 4.5, 4.5, 4.5, -3.5, 4.5, 0)
    high = TemperatureConfig(30.5, 30.5, 30.5, 30.5, 3.5, 30.5, 60)
    assert encode_config_temperatures(low) == bytes([9, 9, 9, 9, 0, 9, 0])
    assert encode_config_temperatures(high) == bytes([61, 61, 61, 61, 14, 61, 12])
    for cfg in (low, high):
        assert decode_config_temperatures(encode_config_temperatures(cfg)) == cfg


@pytest.mark.parametrize(
    "change",
    [
        {"comfort": 4.0}, {"eco": 31.0}, {"max_temperature": 21.25}, {"min_temperature": 0.0},
        {"offset": -4.0}, {"offset": 4.0}, {"offset": 0.25}, {"window_open_temperature": 31.0},
        {"window_open_duration": -5}, {"window_open_duration": 65}, {"window_open_duration": 7},
    ],
)
def test_config_temperatures_rejects_out_of_range(change):
    from dataclasses import replace

    with pytest.raises(FrameError):
        encode_config_temperatures(replace(FACTORY_TEMPS, **change))


def test_config_temperatures_decode_rejects_bad_payload():
    with pytest.raises(FrameError):
        decode_config_temperatures(bytes.fromhex("2A223D090718"))  # 6 bytes
    with pytest.raises(FrameError):
        decode_config_temperatures(bytes.fromhex("08223D09071803"))  # comfort 4.0
    with pytest.raises(FrameError):
        decode_config_temperatures(bytes.fromhex("2A223D090F1803"))  # offset +4.0
    with pytest.raises(FrameError):
        decode_config_temperatures(bytes.fromhex("2A223D0907180D"))  # 65 min


def test_build_config_temperatures_frame():
    f = build_config_temperatures(0x107, CENTRAL, BAD_UNTEN, FACTORY_TEMPS)
    assert (f.counter, f.flags, f.msg_type, f.group) == (0x07, 0x00, 0x11, 0)
    assert encode_frame(f) == "110700" + "11C0FFEEA1B00500" + "2A223D09071803"


def test_config_valve_factory_payload():
    assert encode_config_valve(FACTORY_VALVE).hex().upper() == "300CFF00"
    assert decode_config_valve(bytes.fromhex("300CFF00")) == FACTORY_VALVE


def test_config_valve_boost_duration_codes():
    assert BOOST_DURATIONS == (0, 5, 10, 15, 20, 25, 30, 60)
    from dataclasses import replace

    for code, minutes in enumerate(BOOST_DURATIONS):
        cfg = replace(FACTORY_VALVE, boost_duration=minutes, boost_valve=0)
        assert encode_config_valve(cfg)[0] == code << 5
        assert decode_config_valve(encode_config_valve(cfg)) == cfg


def test_config_valve_boundaries_roundtrip():
    low = ValveConfig(0, 0, 0, 0, 0, 0)
    high = ValveConfig(60, 100, 6, 23, 100, 100)
    assert encode_config_valve(low) == bytes([0, 0, 0, 0])
    assert encode_config_valve(high) == bytes([(7 << 5) | 20, (6 << 5) | 23, 255, 255])
    for cfg in (low, high):
        assert decode_config_valve(encode_config_valve(cfg)) == cfg


def test_config_valve_percent_roundtrip_all_values():
    from dataclasses import replace

    for pct in range(101):
        cfg = replace(FACTORY_VALVE, max_valve=pct, valve_offset=pct)
        raw = encode_config_valve(cfg)
        assert raw[2] == int(pct * 255 / 100) == raw[3]
        assert decode_config_valve(raw) == cfg


@pytest.mark.parametrize(
    "change",
    [
        {"boost_duration": 7}, {"boost_duration": 45}, {"boost_valve": 3}, {"boost_valve": 105},
        {"boost_valve": -5}, {"decalc_day": 7}, {"decalc_day": -1}, {"decalc_hour": 24},
        {"max_valve": 101}, {"max_valve": -1}, {"valve_offset": 101},
    ],
)
def test_config_valve_rejects_out_of_range(change):
    from dataclasses import replace

    with pytest.raises(FrameError):
        encode_config_valve(replace(FACTORY_VALVE, **change))


def test_config_valve_decode_rejects_bad_payload():
    with pytest.raises(FrameError):
        decode_config_valve(bytes.fromhex("300CFF"))
    with pytest.raises(FrameError):
        decode_config_valve(bytes.fromhex("350CFF00"))  # boost valve 105 %
    with pytest.raises(FrameError):
        decode_config_valve(bytes.fromhex("30E0FF00"))  # weekday 7
    with pytest.raises(FrameError):
        decode_config_valve(bytes.fromhex("3018FF00"))  # hour 24


def test_build_config_valve_frame():
    f = build_config_valve(0x01, CENTRAL, BAD_UNTEN, FACTORY_VALVE)
    assert (f.counter, f.flags, f.msg_type, f.group) == (0x01, 0x00, 0x12, 0)
    assert encode_frame(f) == "0E0100" + "12C0FFEEA1B00500" + "300CFF00"


# --- Block 3: Verknuepfungen (FHEM 10_MAX.pm associate/deassociate) ---

from custom_components.eq3_max.protocol.messages import (  # noqa: E402
    LinkPartner,
    build_add_link_partner,
    build_remove_link_partner,
    decode_link_partner,
    link_allowed,
)

FK_ADDR = 0xA1B00B


def test_add_link_partner_encodes_partner_address_and_type():
    f = build_add_link_partner(0x101, CENTRAL, BAD_UNTEN, FK_ADDR, DeviceType.SHUTTER_CONTACT)
    assert (f.counter, f.flags, f.group, f.msg_type) == (0x01, 0x00, 0x00, MsgType.ADD_LINK_PARTNER)
    assert MsgType.ADD_LINK_PARTNER == 0x20
    assert encode_frame(f) == "0E010020C0FFEEA1B00500A1B00B04"


def test_remove_link_partner_encodes_partner_address_and_type():
    f = build_remove_link_partner(5, CENTRAL, FK_ADDR, BAD_UNTEN, DeviceType.HEATING_THERMOSTAT)
    assert MsgType.REMOVE_LINK_PARTNER == 0x21
    assert encode_frame(f) == "0E050021C0FFEEA1B00B00A1B00501"


def test_link_partner_roundtrip_through_decode_frame():
    f = build_add_link_partner(7, CENTRAL, BAD_UNTEN, 0x1590B4, DeviceType.WALL_THERMOSTAT)
    decoded = decode_frame("Z" + encode_frame(f))
    assert decoded.msg_type == MsgType.ADD_LINK_PARTNER
    assert decode_link_partner(decoded.payload) == LinkPartner(0x1590B4, DeviceType.WALL_THERMOSTAT)


def test_decode_link_partner_rejects_bad_payloads():
    with pytest.raises(FrameError):
        decode_link_partner(bytes.fromhex("A1B00B"))
    with pytest.raises(FrameError):
        decode_link_partner(bytes.fromhex("A1B00B09"))


def test_link_partner_builder_rejects_bad_address():
    with pytest.raises(FrameError):
        build_add_link_partner(1, CENTRAL, BAD_UNTEN, 0x1000000, DeviceType.SHUTTER_CONTACT)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (DeviceType.SHUTTER_CONTACT, DeviceType.HEATING_THERMOSTAT),
        (DeviceType.SHUTTER_CONTACT, DeviceType.HEATING_THERMOSTAT_PLUS),
        (DeviceType.SHUTTER_CONTACT, DeviceType.WALL_THERMOSTAT),
        (DeviceType.WALL_THERMOSTAT, DeviceType.HEATING_THERMOSTAT),
        (DeviceType.HEATING_THERMOSTAT, DeviceType.HEATING_THERMOSTAT),
        (DeviceType.PUSH_BUTTON, DeviceType.HEATING_THERMOSTAT),
        (DeviceType.PUSH_BUTTON, DeviceType.WALL_THERMOSTAT),
    ],
)
def test_link_allowed_pairs_both_ways(a, b):
    assert link_allowed(a, b) and link_allowed(b, a)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (DeviceType.SHUTTER_CONTACT, DeviceType.SHUTTER_CONTACT),
        (DeviceType.SHUTTER_CONTACT, DeviceType.PUSH_BUTTON),
        (DeviceType.PUSH_BUTTON, DeviceType.PUSH_BUTTON),
        (DeviceType.WALL_THERMOSTAT, DeviceType.WALL_THERMOSTAT),
        (DeviceType.CUBE, DeviceType.HEATING_THERMOSTAT),
    ],
)
def test_link_disallowed_pairs(a, b):
    assert not link_allowed(a, b) and not link_allowed(b, a)
