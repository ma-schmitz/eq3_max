"""MAX! telegrams: framing, payloads, encoding.

Field layout follows FHEM 14_CUL_MAX.pm / 10_MAX.pm.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum

OFF_TEMPERATURE = 4.5
MAX_TEMPERATURE = 30.5


def normalize_temperature(temperature: float) -> float:
    """Round half-up to 0.5 degC and clamp to what a MAX! thermostat accepts."""
    rounded = math.floor(temperature * 2 + 0.5) / 2
    return min(max(rounded, OFF_TEMPERATURE), MAX_TEMPERATURE)


class MsgType(IntEnum):
    PAIR_PING = 0x00
    PAIR_PONG = 0x01
    ACK = 0x02
    TIME_INFORMATION = 0x03
    CONFIG_TEMPERATURES = 0x11
    CONFIG_VALVE = 0x12
    ADD_LINK_PARTNER = 0x20
    REMOVE_LINK_PARTNER = 0x21
    SHUTTER_CONTACT_STATE = 0x30
    SET_TEMPERATURE = 0x40
    WALL_THERMOSTAT_CONTROL = 0x42
    PUSH_BUTTON_STATE = 0x50
    THERMOSTAT_STATE = 0x60
    WALL_THERMOSTAT_STATE = 0x70
    RESET = 0xF0


class Mode(IntEnum):
    AUTO = 0
    MANUAL = 1
    TEMPORARY = 2
    BOOST = 3


class DeviceType(IntEnum):
    CUBE = 0
    HEATING_THERMOSTAT = 1
    HEATING_THERMOSTAT_PLUS = 2
    WALL_THERMOSTAT = 3
    SHUTTER_CONTACT = 4
    PUSH_BUTTON = 5


class FrameError(ValueError):
    """Line is not a valid MAX! telegram."""


def round_until(dt: datetime) -> datetime:
    """Round up to the next :00 or :30 (MAX! end-time resolution); never earlier than dt."""
    if dt.second or dt.microsecond:
        dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if dt.minute in (0, 30):
        return dt
    if dt.minute < 30:
        return dt.replace(minute=30)
    return dt.replace(minute=0) + timedelta(hours=1)


def encode_until(end: datetime) -> bytes:
    """End time of mode TEMPORARY as 3 bytes (FHEM 10_MAX.pm layout), naive local time."""
    if end.minute not in (0, 30):
        raise FrameError(f"end time must be on :00 or :30, got {end:%H:%M}")
    year = end.year - 2000
    if not 0 <= year <= 0x3F:
        raise FrameError(f"end year out of range: {end.year}")
    return bytes(
        [
            ((end.month & 0x0E) << 4) | end.day,
            ((end.month & 0x01) << 7) | year,
            end.hour * 2 + (1 if end.minute == 30 else 0),
        ]
    )


def decode_until(raw: bytes) -> datetime:
    if len(raw) != 3:
        raise FrameError(f"end time must be 3 bytes: {raw.hex()}")
    b1, b2, b3 = raw
    t = b3 & 0x3F
    try:
        return datetime(
            2000 + (b2 & 0x3F),
            ((b1 & 0xE0) >> 4) | (b2 >> 7),
            b1 & 0x1F,
            t // 2,
            30 if t % 2 else 0,
        )
    except ValueError as err:
        raise FrameError(f"end time out of range: {raw.hex()}") from err


def _until_or_none(raw: bytes) -> datetime | None:
    # A broken end time must not cost the rest of the status telegram.
    try:
        return decode_until(raw)
    except FrameError:
        return None


@dataclass(frozen=True)
class Frame:
    counter: int
    flags: int
    msg_type: int
    src: int
    dst: int
    group: int
    payload: bytes
    rssi: float | None = None


def rssi_to_dbm(raw: int) -> float:
    """culfw RSSI byte to dBm."""
    return (raw - 256) / 2 - 74 if raw >= 128 else raw / 2 - 74


def decode_frame(line: str) -> Frame:
    """Decode a culfw line 'Z<len><...>[<rssi>]'."""
    if not line.startswith("Z") or len(line) < 23:
        raise FrameError(f"not a MAX! telegram: {line!r}")
    try:
        raw = bytes.fromhex(line[1:])
    except ValueError as err:
        raise FrameError(f"not hex: {line!r}") from err
    length = raw[0]
    rssi: float | None = None
    if len(raw) == length + 2:
        rssi = rssi_to_dbm(raw[-1])
        raw = raw[:-1]
    elif len(raw) != length + 1:
        raise FrameError(f"length mismatch: {line!r}")
    if length < 10:
        raise FrameError(f"too short: {line!r}")
    return Frame(
        counter=raw[1],
        flags=raw[2],
        msg_type=raw[3],
        src=int.from_bytes(raw[4:7], "big"),
        dst=int.from_bytes(raw[7:10], "big"),
        group=raw[10],
        payload=bytes(raw[11:]),
        rssi=rssi,
    )


def encode_frame(frame: Frame) -> str:
    """Encode a frame as hex (without 'Z'/'Zs')."""
    body = (
        bytes([frame.counter & 0xFF, frame.flags & 0xFF, frame.msg_type & 0xFF])
        + frame.src.to_bytes(3, "big")
        + frame.dst.to_bytes(3, "big")
        + bytes([frame.group & 0xFF])
        + frame.payload
    )
    return (bytes([len(body)]) + body).hex().upper()


@dataclass(frozen=True)
class StatusBits:
    mode: Mode
    dst_active: bool
    gateway: bool
    locked: bool
    rf_error: bool
    battery_low: bool


def decode_status_bits(b: int) -> StatusBits:
    return StatusBits(
        mode=Mode(b & 0x03),
        dst_active=bool(b & 0x08),
        gateway=bool(b & 0x10),
        locked=bool(b & 0x20),
        rf_error=bool(b & 0x40),
        battery_low=bool(b & 0x80),
    )


@dataclass(frozen=True)
class ThermostatState:
    bits: StatusBits
    valve: int
    target: float
    measured: float | None
    until: datetime | None = None


def decode_thermostat_state(p: bytes) -> ThermostatState:
    if len(p) < 3:
        raise FrameError(f"thermostat state too short: {p.hex()}")
    bits = decode_status_bits(p[0])
    measured: float | None = None
    if len(p) >= 5 and bits.mode is not Mode.TEMPORARY:
        value = (((p[3] & 0x01) << 8) + p[4]) / 10
        if value >= 1:
            measured = value
    until: datetime | None = None
    if len(p) >= 6 and bits.mode is Mode.TEMPORARY:
        until = _until_or_none(p[3:6])
    return ThermostatState(bits=bits, valve=p[1], target=(p[2] & 0x7F) / 2, measured=measured, until=until)


@dataclass(frozen=True)
class WallThermostatState:
    bits: StatusBits | None
    target: float
    measured: float | None
    until: datetime | None = None


def decode_wall_thermostat_state(p: bytes) -> WallThermostatState:
    if len(p) < 3:
        raise FrameError(f"wall thermostat state too short: {p.hex()}")
    desired_raw = p[2]
    bits = decode_status_bits(p[0])
    measured: float | None = None
    value: float | None = None
    until: datetime | None = None
    if len(p) >= 7:
        # FHEM: null1/null2 (bytes 3 and 5) non-zero -> bytes 3..5 are the end time
        # (MAX_ParseDateTime(null1, heaterTemperature, null2)); measured stays in byte 6.
        if p[3] and p[5]:
            until = _until_or_none(p[3:6])
        value = (((desired_raw & 0x80) << 1) + p[6]) / 10
    elif len(p) >= 5 and bits.mode is not Mode.TEMPORARY:
        # 5-byte layout (seen in the 2026-10-09 capture): measured in bytes 3/4
        # like the HT status; Homegear reads it the same way.
        # High bit (p[3] & 1) by analogy to the HT layout; unverified above 25.5 C.
        value = (((p[3] & 0x01) << 8) + p[4]) / 10
    if value is not None and value >= 1:
        measured = value
    return WallThermostatState(bits=bits, target=(desired_raw & 0x7F) / 2, measured=measured, until=until)


def decode_wall_thermostat_control(p: bytes) -> WallThermostatState:
    if len(p) != 2:
        raise FrameError(f"wall thermostat control must be 2 bytes: {p.hex()}")
    value = (((p[0] & 0x80) << 1) + p[1]) / 10
    return WallThermostatState(bits=None, target=(p[0] & 0x7F) / 2, measured=value if value >= 1 else None)


@dataclass(frozen=True)
class ShutterContactState:
    is_open: bool
    rf_error: bool
    battery_low: bool


def decode_shutter_contact_state(p: bytes) -> ShutterContactState:
    if len(p) < 1:
        raise FrameError("shutter contact state empty")
    b = p[0]
    return ShutterContactState(
        is_open=(b & 0x03) != 0, rf_error=bool(b & 0x40), battery_low=bool(b & 0x80)
    )


@dataclass(frozen=True)
class PushButtonState:
    auto: bool
    rf_error: bool
    battery_low: bool


def decode_push_button_state(p: bytes) -> PushButtonState:
    if len(p) < 2:
        raise FrameError(f"push button state too short: {p.hex()}")
    return PushButtonState(
        auto=bool(p[1] & 0x01), rf_error=bool(p[0] & 0x40), battery_low=bool(p[0] & 0x80)
    )


@dataclass(frozen=True)
class PairPing:
    firmware: str
    device_type: DeviceType
    serial: str


def decode_pair_ping(p: bytes) -> PairPing:
    if len(p) < 4:
        raise FrameError(f"pair ping too short: {p.hex()}")
    try:
        device_type = DeviceType(p[1])
    except ValueError as err:
        raise FrameError(f"unknown device type {p[1]:#04x}: {p.hex()}") from err
    return PairPing(
        firmware=f"{p[0] >> 4}.{p[0] & 0x0F}",
        device_type=device_type,
        serial=p[3:].decode("ascii", errors="replace"),
    )


@dataclass(frozen=True)
class Ack:
    ok: bool
    state_payload: bytes


def decode_ack(p: bytes) -> Ack:
    if len(p) < 1:
        raise FrameError("ack without payload")
    return Ack(ok=not (p[0] & 0x80), state_payload=bytes(p[1:]))


def decode_set_temperature(p: bytes) -> tuple[Mode, float]:
    if len(p) < 1:
        raise FrameError("set temperature without payload")
    return Mode(p[0] >> 6), (p[0] & 0x3F) / 2


def decode_time_information(p: bytes) -> datetime:
    if len(p) < 5:
        raise FrameError(f"time information too short: {p.hex()}")
    month = ((p[3] >> 6) << 2) | (p[4] >> 6)
    try:
        return datetime(p[0] + 2000, month, p[1], p[2] & 0x1F, p[3] & 0x3F, p[4] & 0x3F)
    except ValueError as err:
        raise FrameError(f"time information out of range: {p.hex()}") from err


def build_set_temperature(
    counter: int,
    src: int,
    dst: int,
    group: int,
    temperature: float | None,
    mode: Mode,
    until: datetime | None = None,
) -> Frame:
    if mode is Mode.TEMPORARY and until is None:
        raise FrameError("mode TEMPORARY needs an end time")
    if mode is not Mode.TEMPORARY and until is not None:
        raise FrameError(f"end time only with mode TEMPORARY, got {mode.name}")
    if temperature is None:
        if mode is not Mode.AUTO:
            raise FrameError(f"temperature None requires mode AUTO, got {mode.name}")
        value = 0
    else:
        value = int(normalize_temperature(temperature) * 2) & 0x3F
    return Frame(
        counter=counter & 0xFF,
        flags=0x04 if group else 0x00,
        msg_type=MsgType.SET_TEMPERATURE,
        src=src,
        dst=dst,
        group=group,
        payload=bytes([value | (int(mode) << 6)]) + (b"" if until is None else encode_until(until)),
    )


def build_reset(counter: int, src: int, dst: int) -> Frame:
    """Factory reset: the device forgets its pairing and settings."""
    return Frame(counter & 0xFF, 0x00, MsgType.RESET, src, dst, 0, b"")


def build_pair_pong(counter: int, src: int, dst: int) -> Frame:
    return Frame(counter & 0xFF, 0x00, MsgType.PAIR_PONG, src, dst, 0, b"\x00")


def build_time_information(counter: int, src: int, dst: int, now: datetime) -> Frame:
    payload = bytes(
        [
            now.year - 2000,
            now.day,
            now.hour,
            now.minute | ((now.month & 0x0C) << 4),
            now.second | ((now.month & 0x03) << 6),
        ]
    )
    return Frame(counter & 0xFF, 0x04, MsgType.TIME_INFORMATION, src, dst, 0, payload)


# --- Device configuration (FHEM 10_MAX.pm: ConfigTemperatures 0x11, ConfigValve 0x12) ---

OFFSET_LIMIT = 3.5
MAX_WINDOW_OPEN_DURATION = 60
# Boost duration in minutes by its 3-bit code.
BOOST_DURATIONS = (0, 5, 10, 15, 20, 25, 30, 60)
# Decalcification weekday index: 0 = Saturday ... 6 = Friday.
DECALC_DAYS = 7


@dataclass(frozen=True)
class TemperatureConfig:
    comfort: float
    eco: float
    max_temperature: float
    min_temperature: float
    offset: float
    window_open_temperature: float
    window_open_duration: int  # minutes


@dataclass(frozen=True)
class ValveConfig:
    boost_duration: int  # minutes, one of BOOST_DURATIONS
    boost_valve: int  # percent, multiple of 5
    decalc_day: int  # 0 = Saturday ... 6 = Friday
    decalc_hour: int
    max_valve: int  # percent
    valve_offset: int  # percent


def _half_steps(value: float, low: float, high: float, name: str) -> int:
    """value as a count of 0.5 steps; must lie in [low, high] on a 0.5 grid."""
    steps = value * 2
    if not low <= value <= high or steps != int(steps):
        raise FrameError(f"{name} must be {low}..{high} in 0.5 steps, got {value}")
    return int(steps)


def _int_in(value: int, low: int, high: int, name: str, step: int = 1) -> int:
    if isinstance(value, bool) or int(value) != value or not low <= value <= high or int(value) % step:
        raise FrameError(f"{name} must be {low}..{high} in steps of {step}, got {value}")
    return int(value)


def encode_config_temperatures(cfg: TemperatureConfig) -> bytes:
    temps = [
        _half_steps(t, OFF_TEMPERATURE, MAX_TEMPERATURE, name)
        for t, name in (
            (cfg.comfort, "comfort"),
            (cfg.eco, "eco"),
            (cfg.max_temperature, "max temperature"),
            (cfg.min_temperature, "min temperature"),
        )
    ]
    offset = _half_steps(cfg.offset, -OFFSET_LIMIT, OFFSET_LIMIT, "offset") + int(OFFSET_LIMIT * 2)
    window = _half_steps(cfg.window_open_temperature, OFF_TEMPERATURE, MAX_TEMPERATURE, "window open temperature")
    duration = _int_in(cfg.window_open_duration, 0, MAX_WINDOW_OPEN_DURATION, "window open duration", 5)
    return bytes([*temps, offset, window, duration // 5])


def decode_config_temperatures(p: bytes) -> TemperatureConfig:
    if len(p) != 7:
        raise FrameError(f"config temperatures must be 7 bytes: {p.hex()}")
    cfg = TemperatureConfig(
        comfort=p[0] / 2,
        eco=p[1] / 2,
        max_temperature=p[2] / 2,
        min_temperature=p[3] / 2,
        offset=p[4] / 2 - OFFSET_LIMIT,
        window_open_temperature=p[5] / 2,
        window_open_duration=p[6] * 5,
    )
    encode_config_temperatures(cfg)  # range check
    return cfg


def encode_config_valve(cfg: ValveConfig) -> bytes:
    if cfg.boost_duration not in BOOST_DURATIONS or isinstance(cfg.boost_duration, bool):
        raise FrameError(f"boost duration must be one of {BOOST_DURATIONS}, got {cfg.boost_duration}")
    code = BOOST_DURATIONS.index(cfg.boost_duration)
    boost_valve = _int_in(cfg.boost_valve, 0, 100, "boost valve", 5)
    day = _int_in(cfg.decalc_day, 0, DECALC_DAYS - 1, "decalcification day")
    hour = _int_in(cfg.decalc_hour, 0, 23, "decalcification hour")
    max_valve = _int_in(cfg.max_valve, 0, 100, "max valve")
    valve_offset = _int_in(cfg.valve_offset, 0, 100, "valve offset")
    return bytes(
        [
            (code << 5) | (boost_valve // 5),
            (day << 5) | hour,
            max_valve * 255 // 100,
            valve_offset * 255 // 100,
        ]
    )


def decode_config_valve(p: bytes) -> ValveConfig:
    if len(p) != 4:
        raise FrameError(f"config valve must be 4 bytes: {p.hex()}")
    cfg = ValveConfig(
        boost_duration=BOOST_DURATIONS[p[0] >> 5],
        boost_valve=(p[0] & 0x1F) * 5,
        decalc_day=p[1] >> 5,
        decalc_hour=p[1] & 0x1F,
        max_valve=round(p[2] * 100 / 255),
        valve_offset=round(p[3] * 100 / 255),
    )
    encode_config_valve(cfg)  # range check
    return cfg


def build_config_temperatures(counter: int, src: int, dst: int, cfg: TemperatureConfig) -> Frame:
    return Frame(counter & 0xFF, 0x00, MsgType.CONFIG_TEMPERATURES, src, dst, 0, encode_config_temperatures(cfg))


def build_config_valve(counter: int, src: int, dst: int, cfg: ValveConfig) -> Frame:
    return Frame(counter & 0xFF, 0x00, MsgType.CONFIG_VALVE, src, dst, 0, encode_config_valve(cfg))


# --- Links between devices (FHEM 10_MAX.pm associate/deassociate: 0x20 AddLinkPartner,
# 0x21 RemoveLinkPartner; payload = partner address (3 bytes) + partner device type) ---

_THERMOSTATS = (DeviceType.HEATING_THERMOSTAT, DeviceType.HEATING_THERMOSTAT_PLUS)
# Partner kinds a device of the key kind can be linked with (HT-HT as FHEM allows it).
_LINKABLE: dict[str, tuple[str, ...]] = {
    "ht": ("ht", "wt", "sc", "pb"),
    "wt": ("ht", "sc", "pb"),
    "sc": ("ht", "wt"),
    "pb": ("ht", "wt"),
}


def _link_kind(device_type: DeviceType) -> str | None:
    if device_type in _THERMOSTATS:
        return "ht"
    return {
        DeviceType.WALL_THERMOSTAT: "wt",
        DeviceType.SHUTTER_CONTACT: "sc",
        DeviceType.PUSH_BUTTON: "pb",
    }.get(device_type)


def link_allowed(a: DeviceType, b: DeviceType) -> bool:
    """Whether devices of these types can be linked (in both directions)."""
    kind_a, kind_b = _link_kind(a), _link_kind(b)
    return kind_a is not None and kind_b is not None and kind_b in _LINKABLE[kind_a]


@dataclass(frozen=True)
class LinkPartner:
    address: int
    device_type: DeviceType


def encode_link_partner(partner: int, partner_type: DeviceType) -> bytes:
    if not 0 <= partner <= 0xFFFFFF:
        raise FrameError(f"partner address out of range: {partner:#x}")
    return partner.to_bytes(3, "big") + bytes([int(DeviceType(partner_type))])


def decode_link_partner(p: bytes) -> LinkPartner:
    if len(p) != 4:
        raise FrameError(f"link partner must be 4 bytes: {p.hex()}")
    try:
        device_type = DeviceType(p[3])
    except ValueError as err:
        raise FrameError(f"unknown partner device type {p[3]:#04x}: {p.hex()}") from err
    return LinkPartner(int.from_bytes(p[:3], "big"), device_type)


def build_add_link_partner(counter: int, src: int, dst: int, partner: int, partner_type: DeviceType) -> Frame:
    """Tell dst to accept/send telegrams of partner (one direction of a link)."""
    return Frame(
        counter & 0xFF, 0x00, MsgType.ADD_LINK_PARTNER, src, dst, 0, encode_link_partner(partner, partner_type)
    )


def build_remove_link_partner(counter: int, src: int, dst: int, partner: int, partner_type: DeviceType) -> Frame:
    return Frame(
        counter & 0xFF, 0x00, MsgType.REMOVE_LINK_PARTNER, src, dst, 0, encode_link_partner(partner, partner_type)
    )
