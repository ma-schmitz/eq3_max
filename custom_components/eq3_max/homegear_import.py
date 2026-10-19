"""Export the MAX! device list from Homegear and turn it into MaxDevice objects.

HA-free: also used by tools/homegear_export.py.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .protocol.devices import (
    FACTORY_CONFIG,
    SOURCE_HOMEGEAR,
    WEEKDAYS,
    MaxDevice,
    config_kind,
    normalize_config_value,
)
from .protocol.messages import BOOST_DURATIONS, DeviceType, FrameError, Mode

_MODEL_PREFIXES = (
    ("BC-RT-TRX", DeviceType.HEATING_THERMOSTAT),
    ("BC-TC-C-WM", DeviceType.WALL_THERMOSTAT),
    ("BC-SC-Rd-WM", DeviceType.SHUTTER_CONTACT),
    ("BC-PB-2-WM", DeviceType.PUSH_BUTTON),
)


def device_type_for_model(model: str) -> DeviceType | None:
    for prefix, device_type in _MODEL_PREFIXES:
        if model.startswith(prefix):
            return device_type
    return None


def _values(proxy: Any, serial: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for channel in (0, 1):
        try:
            values.update(proxy.getParamset(f"{serial}:{channel}", "VALUES") or {})
        except Exception:  # noqa: BLE001 - Homegear raises xmlrpc faults for missing channels
            continue
    return values


def _name(proxy: Any, serial: str) -> str:
    """Homegear keeps device names as metadata; listDevices has none."""
    try:
        name = proxy.getMetadata(serial, "NAME")
    except Exception:  # noqa: BLE001 - xmlrpc fault when unset, AttributeError on old proxies
        return serial
    return name.strip() if isinstance(name, str) and name.strip() else serial


def _partner_serials(own: str, raw: Any) -> list[str]:
    """Partner serials from link entries (dicts with SENDER/RECEIVER "SERIAL:channel"
    or plain strings); deduplicated, own serial excluded."""
    found: list[str] = []
    if isinstance(raw, (str, dict)):
        raw = [raw]
    for entry in raw or []:
        if isinstance(entry, dict):
            candidates = [entry.get("SENDER"), entry.get("RECEIVER")]
        else:
            candidates = [entry]
        for value in candidates:
            if isinstance(value, str):
                serial = value.split(":", 1)[0].strip()
                if serial and serial != own:
                    found.append(serial)
    return list(dict.fromkeys(found))


def _links(proxy: Any, serial: str) -> list[str]:
    try:
        return _partner_serials(serial, proxy.getLinks(serial, 0))
    except Exception:  # noqa: BLE001 - xmlrpc fault, AttributeError on old proxies
        return []


def export_from_homegear(proxy: Any) -> dict[str, Any]:
    devices = []
    for entry in proxy.listDevices():
        serial = entry.get("ADDRESS", "")
        if not serial or ":" in serial:
            continue
        device_type = device_type_for_model(entry.get("TYPE", ""))
        if device_type is None:
            continue
        devices.append(
            {
                "serial": serial,
                "address": int(entry["RF_ADDRESS"]),
                "model": entry.get("TYPE", ""),
                "device_type": int(device_type),
                "firmware": entry.get("FIRMWARE", ""),
                "name": _name(proxy, serial),
                "group": 0,
                "values": _values(proxy, serial),
                "links": _links(proxy, serial),
            }
        )
    return {"version": 1, "devices": devices}


def _index(table: tuple) -> Callable[[Any], Any]:
    def convert(raw: Any) -> Any:
        index = int(raw)
        if not 0 <= index < len(table):
            raise FrameError(f"index {raw} out of range")
        return table[index]

    return convert


# Homegear VALUES key -> (config key, conversion). Keys Homegear does not export
# (window open duration, max valve, valve offset) stay at the factory setting.
_CONFIG_IMPORT: dict[str, tuple[str, Callable[[Any], Any]]] = {
    "COMFORT_TEMPERATURE": ("komfort", float),
    "ECO_TEMPERATURE": ("eco", float),
    "MAX_TEMPERATURE": ("maximal", float),
    "MIN_TEMPERATURE": ("minimal", float),
    # Homegear stores the offset as index: offset_K = index / 2 - 3.5.
    "TEMPERATURE_OFFSET": ("offset", lambda raw: int(raw) / 2 - 3.5),
    "WINDOW_OPEN_TEMPERATURE": ("fenster_temperatur", float),
    "BOOST_POSITION": ("boost_ventil", int),
    "BOOST_TIME_PERIOD": ("boost_dauer", _index(BOOST_DURATIONS)),
    "DECALCIFICATION_WEEKDAY": ("entkalkung_tag", _index(WEEKDAYS)),
    # Minutes since midnight.
    "DECALCIFICATION_TIME": ("entkalkung_stunde", lambda raw: int(raw) // 60),
}


def _import_config(dev: MaxDevice, values: dict[str, Any]) -> None:
    """Take the configuration Homegear knows; the rest is assumed factory setting."""
    keys = dev.config_keys
    for hg_key, (key, convert) in _CONFIG_IMPORT.items():
        if key not in keys or hg_key not in values:
            continue
        try:
            value = normalize_config_value(key, convert(values[hg_key]))
            kind = config_kind(key)
            # Range check of the single value inside an otherwise valid set.
            probe = {k: FACTORY_CONFIG[k] for k in dev.config_set(kind)}
            dev.encode_config(kind, {**probe, key: value})
        except (FrameError, TypeError, ValueError):
            continue
        dev.config[key] = value
        dev.config_source[key] = SOURCE_HOMEGEAR
    dev.ensure_config_defaults()


def devices_from_export(data: dict[str, Any]) -> list[MaxDevice]:
    result = []
    for item in data["devices"]:
        dev = MaxDevice(
            address=int(item["address"]),
            serial=item["serial"],
            device_type=DeviceType(item["device_type"]),
            name=item.get("name") or item["serial"],
            firmware=item.get("firmware", ""),
            group=int(item.get("group", 0)),
        )
        values = item.get("values", {})
        if "SET_TEMPERATURE" in values:
            dev.target = float(values["SET_TEMPERATURE"])
        if "ACTUAL_TEMPERATURE" in values:
            dev.measured = float(values["ACTUAL_TEMPERATURE"])
        if "VALVE_STATE" in values:
            dev.valve = int(values["VALVE_STATE"])
        if "CONTROL_MODE" in values:
            dev.mode = Mode(int(values["CONTROL_MODE"]))
        _import_config(dev, values)
        dev.links = _partner_serials(dev.serial, item.get("links") or [])
        if "LOWBAT" in values:
            dev.battery_low = bool(values["LOWBAT"])
        if dev.device_type is DeviceType.SHUTTER_CONTACT and "STATE" in values:
            dev.window_open = bool(values["STATE"])
        result.append(dev)
    return result


def load_export(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_export(data: dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
