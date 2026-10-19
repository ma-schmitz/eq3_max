"""Device model: last known state per MAX! device."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from typing import Any

from .messages import (
    OFF_TEMPERATURE,
    DeviceType,
    FrameError,
    Mode,
    PushButtonState,
    ShutterContactState,
    StatusBits,
    TemperatureConfig,
    ThermostatState,
    ValveConfig,
    WallThermostatState,
    encode_config_temperatures,
    encode_config_valve,
)

_DATETIME_KEYS = ("until", "pending_until")
# Kept in the config entry; the entry wins over the store. config/config_source
# only when non-empty (old entries have none).
# links (partner serials) only when present (old entries have none).
IDENTITY_KEYS = (
    "address", "serial", "device_type", "name", "firmware", "group", "config", "config_source", "links", "radio",
)
CONFIG_ENTRY_KEYS = ("config", "config_source")
DEFAULT_WINDOW_OPEN_TEMPERATURE = 12.0

# Device configuration (0x11 ConfigTemperatures: HT and WT; 0x12 ConfigValve: HT only).
KIND_TEMP = "temp"
KIND_VALVE = "valve"
CONFIG_TEMP_KEYS = ("komfort", "eco", "maximal", "minimal", "offset", "fenster_temperatur", "fenster_dauer")
CONFIG_VALVE_KEYS = (
    "boost_dauer", "boost_ventil", "entkalkung_tag", "entkalkung_stunde", "ventil_max", "ventil_offset",
)
# Decalcification weekday by MAX! index (0 = Saturday).
WEEKDAYS = ("Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag")
# Factory settings after pairing (FHEM 10_MAX.pm).
FACTORY_CONFIG: dict[str, Any] = {
    "komfort": 21.0,
    "eco": 17.0,
    "maximal": 30.5,
    "minimal": 4.5,
    "offset": 0.0,
    "fenster_temperatur": DEFAULT_WINDOW_OPEN_TEMPERATURE,
    "fenster_dauer": 15,
    "boost_dauer": 5,
    "boost_ventil": 80,
    "entkalkung_tag": "Samstag",
    "entkalkung_stunde": 12,
    "ventil_max": 100,
    "ventil_offset": 0,
}
SOURCE_HOMEGEAR = "homegear"
SOURCE_FACTORY = "werksvorgabe"
SOURCE_SET = "gesetzt"
# Links: one pending operation per partner (direction "this device gets the partner").
LINK_ADD = "add"
LINK_REMOVE = "remove"
LINK_PENDING = "ausstehend"  # queued or on air
LINK_WAITING = "wartet auf Ger\u00e4t"  # sleeping device: sent after its next telegram
LINK_FAILED = "fehlgeschlagen"  # no ack: resent automatically
LINK_REJECTED = "fehlgeschlagen (abgelehnt)"  # NAK: only a new request sends it again
_LINK_OPS = (LINK_ADD, LINK_REMOVE)
_LINK_STATES = (LINK_PENDING, LINK_WAITING, LINK_FAILED, LINK_REJECTED)
_FLOAT_KEYS = ("komfort", "eco", "maximal", "minimal", "offset", "fenster_temperatur")


def config_kind(key: str) -> str:
    if key in CONFIG_TEMP_KEYS:
        return KIND_TEMP
    if key in CONFIG_VALVE_KEYS:
        return KIND_VALVE
    raise FrameError(f"unknown config key {key!r}")


def normalize_config_value(key: str, value: Any) -> Any:
    """Type a config value (float, int minutes/percent/hour, weekday name); range is
    checked when the whole set is encoded."""
    config_kind(key)
    if key == "entkalkung_tag":
        if value not in WEEKDAYS:
            raise FrameError(f"decalcification day must be one of {WEEKDAYS}, got {value!r}")
        return value
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise FrameError(f"{key}: not a number: {value!r}") from err
    if key in _FLOAT_KEYS:
        return number
    if number != int(number):
        raise FrameError(f"{key}: must be a whole number, got {value!r}")
    return int(number)


@dataclass
class MaxDevice:
    address: int
    serial: str
    device_type: DeviceType
    name: str = ""
    firmware: str = ""
    group: int = 0
    target: float | None = None
    measured: float | None = None
    valve: int | None = None
    mode: Mode | None = None
    until: datetime | None = None
    battery_low: bool | None = None
    rf_error: bool | None = None
    locked: bool | None = None
    window_open: bool | None = None
    rssi: float | None = None
    last_seen: float | None = None
    pending_target: float | None = None
    pending_mode: Mode | None = None
    pending_until: datetime | None = None
    command_failed: bool = False
    # Last manual target above "off": the comfort value heat returns to after away/boost.
    last_comfort: float | None = None
    # Last acknowledged (or imported/assumed) configuration and where each value came from.
    config: dict[str, Any] = field(default_factory=dict)
    config_source: dict[str, str] = field(default_factory=dict)
    # Whole config sets sent but not yet acknowledged, by kind ("temp"/"valve").
    pending_config: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Kinds whose pending set ran out of attempts (resent on the next status).
    config_failed: list[str] = field(default_factory=list)
    # Serials of link partners this device acknowledged (one direction of each link).
    links: list[str] = field(default_factory=list)
    # Link operations not acknowledged yet: dicts with partner (serial), address,
    # device_type, op (add/remove) and state (ausstehend/wartet auf Geraet/fehlgeschlagen).
    pending_links: list[dict[str, Any]] = field(default_factory=list)
    # Radio module the commands to this device go through ("" = the main module).
    radio: str = ""
    # Last RSSI per radio module that heard the device ("" = the main module).
    rssi_by_radio: dict[str, float] = field(default_factory=dict)

    @property
    def is_heating_thermostat(self) -> bool:
        return self.device_type in (DeviceType.HEATING_THERMOSTAT, DeviceType.HEATING_THERMOSTAT_PLUS)

    @property
    def is_climate(self) -> bool:
        return self.is_heating_thermostat or self.device_type is DeviceType.WALL_THERMOSTAT

    @property
    def is_sleeper(self) -> bool:
        """Battery devices that only listen right after they sent something."""
        return self.device_type in (DeviceType.SHUTTER_CONTACT, DeviceType.PUSH_BUTTON)

    @property
    def has_pending(self) -> bool:
        return self.pending_mode is not None

    @property
    def window_open_temperature(self) -> float:
        """Target a thermostat reports (still MANUAL) while a linked window is open."""
        return self.config.get("fenster_temperatur", DEFAULT_WINDOW_OPEN_TEMPERATURE)

    @window_open_temperature.setter
    def window_open_temperature(self, value: float) -> None:
        self.config["fenster_temperatur"] = value

    @property
    def config_keys(self) -> tuple[str, ...]:
        if self.is_heating_thermostat:
            return CONFIG_TEMP_KEYS + CONFIG_VALVE_KEYS
        if self.device_type is DeviceType.WALL_THERMOSTAT:
            return CONFIG_TEMP_KEYS
        return ()

    def ensure_config_defaults(self) -> None:
        """Assume factory settings for every config value not known yet."""
        for key in self.config_keys:
            if key not in self.config:
                self.config[key] = FACTORY_CONFIG[key]
                self.config_source[key] = SOURCE_FACTORY
            self.config_source.setdefault(key, SOURCE_FACTORY)

    def config_set(self, kind: str) -> dict[str, Any]:
        """The whole set a change builds on: a pending set beats the stored one."""
        if kind in self.pending_config:
            return dict(self.pending_config[kind])
        keys = CONFIG_TEMP_KEYS if kind == KIND_TEMP else CONFIG_VALVE_KEYS
        return {key: self.config.get(key, FACTORY_CONFIG[key]) for key in keys}

    @staticmethod
    def temperature_config(values: dict[str, Any]) -> TemperatureConfig:
        return TemperatureConfig(
            comfort=values["komfort"],
            eco=values["eco"],
            max_temperature=values["maximal"],
            min_temperature=values["minimal"],
            offset=values["offset"],
            window_open_temperature=values["fenster_temperatur"],
            window_open_duration=values["fenster_dauer"],
        )

    @staticmethod
    def valve_config(values: dict[str, Any]) -> ValveConfig:
        day = values["entkalkung_tag"]
        if day not in WEEKDAYS:
            raise FrameError(f"decalcification day must be one of {WEEKDAYS}, got {day!r}")
        return ValveConfig(
            boost_duration=values["boost_dauer"],
            boost_valve=values["boost_ventil"],
            decalc_day=WEEKDAYS.index(day),
            decalc_hour=values["entkalkung_stunde"],
            max_valve=values["ventil_max"],
            valve_offset=values["ventil_offset"],
        )

    def encode_config(self, kind: str, values: dict[str, Any]) -> bytes:
        """Payload of a whole set; raises FrameError on invalid values."""
        if kind == KIND_TEMP:
            return encode_config_temperatures(self.temperature_config(values))
        return encode_config_valve(self.valve_config(values))

    def stage_config(self, key: str, value: Any) -> str:
        """Change one value: the whole set (other values as stored or pending) becomes
        pending. Returns the kind; raises FrameError without side effects."""
        if key not in self.config_keys:
            raise FrameError(f"{key!r} is no config value of {self.device_type.name}")
        kind = config_kind(key)
        values = self.config_set(kind)
        values[key] = normalize_config_value(key, value)
        self.encode_config(kind, values)
        self.pending_config[kind] = values
        # Only this set is new; another set's failure stays until it is resent.
        self.clear_config_failed(kind)
        return kind

    def stage_config_set(self, kind: str, values: dict[str, Any]) -> list[str]:
        """Change several values of one set at once: the whole set becomes pending.
        Returns the keys that go along as assumed factory settings (unchanged and
        never acknowledged); raises FrameError without side effects."""
        if kind not in (KIND_TEMP, KIND_VALVE):
            raise FrameError(f"unknown config set {kind!r}")
        if not values:
            raise FrameError("no config values given")
        for key in values:
            if key not in self.config_keys or config_kind(key) != kind:
                raise FrameError(f"{key!r} is no {kind} config value of {self.device_type.name}")
        staged = self.config_set(kind)
        for key, value in values.items():
            staged[key] = normalize_config_value(key, value)
        self.encode_config(kind, staged)
        self.pending_config[kind] = staged
        self.clear_config_failed(kind)
        return self.assumed_factory(kind, values)

    def assumed_factory(self, kind: str, changed: Iterable[str] = ()) -> list[str]:
        """Keys of the pending (or stored) set that go out as assumed factory settings:
        never acknowledged, not changed now (`changed`) and not changed by an earlier
        unacknowledged request."""
        changed = set(changed)
        values = self.config_set(kind)
        return [
            key
            for key, value in values.items()
            if key not in changed
            and self.config_source.get(key) == SOURCE_FACTORY
            and value == self.config.get(key, FACTORY_CONFIG[key])
        ]

    def mark_config_failed(self, kind: str) -> None:
        if kind not in self.config_failed:
            self.config_failed = sorted([*self.config_failed, kind])

    def clear_config_failed(self, kind: str) -> None:
        self.config_failed = [k for k in self.config_failed if k != kind]

    def failed_config_kinds(self) -> list[str]:
        """Failed sets that are still pending."""
        return [kind for kind in self.config_failed if kind in self.pending_config]

    def pending_value(self, key: str) -> Any:
        pending = self.pending_config.get(config_kind(key))
        return None if pending is None else pending.get(key)

    def commit_config(self, kind: str, values: dict[str, Any]) -> None:
        """An acknowledged set is what the device has now."""
        for key, value in values.items():
            self.config[key] = value
            self.config_source[key] = SOURCE_SET
        if self.pending_config.get(kind) == values:
            del self.pending_config[kind]
            self.clear_config_failed(kind)

    def link_op(self, partner: str) -> dict[str, Any] | None:
        return next((op for op in self.pending_links if op["partner"] == partner), None)

    def set_link_op(self, partner: str, address: int, device_type: DeviceType, op: str, state: str) -> dict[str, Any]:
        """Queue a link operation for a partner; replaces an older one for that partner."""
        if op not in _LINK_OPS or state not in _LINK_STATES:
            raise FrameError(f"bad link operation {op!r}/{state!r}")
        entry = {"partner": partner, "address": address, "device_type": int(device_type), "op": op, "state": state}
        self.pending_links = [o for o in self.pending_links if o["partner"] != partner] + [entry]
        return entry

    def drop_link_op(self, partner: str) -> None:
        self.pending_links = [o for o in self.pending_links if o["partner"] != partner]

    def commit_link(self, partner: str, op: str) -> None:
        """The device acknowledged adding/removing this partner."""
        if op == LINK_ADD and partner not in self.links:
            self.links = [*self.links, partner]
        elif op == LINK_REMOVE:
            self.links = [s for s in self.links if s != partner]
        current = self.link_op(partner)
        if current is not None and current["op"] == op:
            self.drop_link_op(partner)

    def fail_link(self, partner: str, op: str) -> None:
        self.set_link_state(partner, op, LINK_FAILED)

    def set_link_state(self, partner: str, op: str, state: str) -> None:
        """New state for the pending operation of this partner, if it is still this op."""
        current = self.link_op(partner)
        if current is not None and current["op"] == op:
            current["state"] = state

    def failed_link_ops(self) -> list[dict[str, Any]]:
        return [op for op in self.pending_links if op["state"] == LINK_FAILED]

    def forget_partner(self, partner: str) -> bool:
        """Drop a partner from the links and its pending operation; True if anything changed."""
        changed = partner in self.links or self.link_op(partner) is not None
        self.links = [s for s in self.links if s != partner]
        self.drop_link_op(partner)
        return changed

    def note_comfort(self) -> None:
        """Remember the current target as comfort value if it is a manual one above off."""
        if self.mode is not Mode.MANUAL or self.target is None or self.target <= OFF_TEMPERATURE:
            return
        if self.target == self.window_open_temperature:
            return  # window open, not a comfort value
        self.last_comfort = self.target

    def _apply_bits(self, bits: StatusBits) -> None:
        self.mode = bits.mode
        self.battery_low = bits.battery_low
        self.rf_error = bits.rf_error
        self.locked = bits.locked

    def _apply_until(self, until: datetime | None) -> None:
        # Short states (e.g. 3-byte acks) carry no end time: keep the known one.
        if self.mode is not Mode.TEMPORARY:
            self.until = None
        elif until is not None:
            self.until = until

    def apply_thermostat_state(self, st: ThermostatState) -> None:
        self._apply_bits(st.bits)
        self.valve = st.valve
        self.target = st.target
        self._apply_until(st.until)
        self.note_comfort()
        if st.measured is not None:
            self.measured = st.measured

    def apply_wall_state(self, st: WallThermostatState) -> None:
        if st.bits is not None:
            self._apply_bits(st.bits)
            self._apply_until(st.until)
        self.target = st.target
        if st.bits is not None:
            self.note_comfort()
        if st.measured is not None:
            self.measured = st.measured

    def apply_shutter(self, st: ShutterContactState) -> None:
        self.window_open = st.is_open
        self.rf_error = st.rf_error
        self.battery_low = st.battery_low

    def apply_button(self, st: PushButtonState) -> None:
        self.rf_error = st.rf_error
        self.battery_low = st.battery_low

    def set_pending(self, target: float | None, mode: Mode, until: datetime | None = None) -> None:
        self.pending_target = target
        self.pending_mode = mode
        self.pending_until = until
        self.command_failed = False

    def clear_pending(self) -> None:
        self.pending_target = None
        self.pending_mode = None
        self.pending_until = None
        self.command_failed = False

    def clear_pending_if_reached(self) -> None:
        if self.pending_mode is None or self.mode is not self.pending_mode:
            return
        if self.pending_target is not None and self.target != self.pending_target:
            return
        if self.pending_mode is Mode.TEMPORARY and self.until != self.pending_until:
            return
        self.clear_pending()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["device_type"] = int(self.device_type)
        data["mode"] = None if self.mode is None else int(self.mode)
        data["pending_mode"] = None if self.pending_mode is None else int(self.pending_mode)
        for key in _DATETIME_KEYS:
            value = getattr(self, key)
            data[key] = None if value is None else value.isoformat()
        return data

    def identity_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        return {key: data[key] for key in IDENTITY_KEYS}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MaxDevice:
        known = {f.name for f in fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        for key in ("config", "config_source"):
            values[key] = dict(values.get(key) or {})
        values["pending_config"] = {k: dict(v) for k, v in (values.get("pending_config") or {}).items()}
        failed = values.get("config_failed")
        if isinstance(failed, bool):
            # Before fix round 1 one flag covered all pending sets.
            failed = sorted(values["pending_config"]) if failed else []
        values["config_failed"] = [k for k in (failed or []) if k in (KIND_TEMP, KIND_VALVE)]
        own = values.get("serial")
        values["links"] = list(dict.fromkeys(s for s in (values.get("links") or []) if s and s != own))
        values["pending_links"] = [_link_op_from_dict(op) for op in (values.get("pending_links") or [])]
        values["pending_links"] = [op for op in values["pending_links"] if op is not None]
        legacy = data.get("window_open_temperature")
        if legacy is not None and "fenster_temperatur" not in values["config"]:
            # Before block 2 the window open temperature was a field of its own; it came
            # from Homegear (WINDOW_OPEN_TEMPERATURE) or was the 12.0 default.
            values["config"]["fenster_temperatur"] = float(legacy)
            values["config_source"]["fenster_temperatur"] = (
                SOURCE_FACTORY if float(legacy) == DEFAULT_WINDOW_OPEN_TEMPERATURE else SOURCE_HOMEGEAR
            )
        values["device_type"] = DeviceType(values["device_type"])
        values["radio"] = str(values.get("radio") or "")
        values["rssi_by_radio"] = {str(k): float(v) for k, v in (values.get("rssi_by_radio") or {}).items()}
        for key in ("mode", "pending_mode"):
            if values.get(key) is not None:
                values[key] = Mode(values[key])
        for key in _DATETIME_KEYS:
            if values.get(key) is not None:
                values[key] = datetime.fromisoformat(values[key])
        return cls(**values)


def _link_op_from_dict(data: Any) -> dict[str, Any] | None:
    try:
        op = {
            "partner": str(data["partner"]),
            "address": int(data["address"]),
            "device_type": int(DeviceType(data["device_type"])),
            "op": data["op"],
            "state": data["state"],
        }
    except (KeyError, TypeError, ValueError):
        return None
    if op["op"] not in _LINK_OPS or op["state"] not in _LINK_STATES:
        return None
    return op
