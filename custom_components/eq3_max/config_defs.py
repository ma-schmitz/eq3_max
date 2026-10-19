"""Device configuration values: labels, ranges and options in one table.

Used by the number/select entities and by the panel (websocket_api), so both
offer and check the same grid.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberDeviceClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime

from .protocol.devices import CONFIG_TEMP_KEYS, CONFIG_VALVE_KEYS, KIND_TEMP, KIND_VALVE, WEEKDAYS
from .protocol.messages import BOOST_DURATIONS, MAX_TEMPERATURE, OFF_TEMPERATURE, OFFSET_LIMIT

CONFIG_LABELS = {
    "komfort": "Komforttemperatur",
    "eco": "Eco-Temperatur",
    "maximal": "Maximaltemperatur",
    "minimal": "Minimaltemperatur",
    "offset": "Temperatur-Offset",
    "fenster_temperatur": "Fenster-auf-Temperatur",
    "fenster_dauer": "Fenster-auf-Dauer",
    "boost_dauer": "Boost-Dauer",
    "boost_ventil": "Boost-Ventilstellung",
    "entkalkung_tag": "Entkalkung Tag",
    "entkalkung_stunde": "Entkalkung Stunde",
    "ventil_max": "Ventil maximal",
    "ventil_offset": "Ventil-Offset",
}
SET_TITLES = {KIND_TEMP: "Temperaturen", KIND_VALVE: "Ventil"}
SET_KEYS = {KIND_TEMP: CONFIG_TEMP_KEYS, KIND_VALVE: CONFIG_VALVE_KEYS}


@dataclass(frozen=True)
class Range:
    low: float
    high: float
    step: float
    unit: str | None
    device_class: NumberDeviceClass | None = None
    icon: str | None = None


_TEMP = Range(OFF_TEMPERATURE, MAX_TEMPERATURE, 0.5, UnitOfTemperature.CELSIUS, NumberDeviceClass.TEMPERATURE)
RANGES = {
    "komfort": _TEMP,
    "eco": _TEMP,
    "maximal": _TEMP,
    "minimal": _TEMP,
    # A temperature difference: no device class, HA must not convert it like a temperature.
    "offset": Range(-OFFSET_LIMIT, OFFSET_LIMIT, 0.5, UnitOfTemperature.KELVIN, icon="mdi:thermometer-plus"),
    "fenster_temperatur": _TEMP,
    "fenster_dauer": Range(0, 60, 5, UnitOfTime.MINUTES, icon="mdi:window-open-variant"),
    "boost_ventil": Range(0, 100, 5, PERCENTAGE, icon="mdi:valve-open"),
    "entkalkung_stunde": Range(0, 23, 1, None, icon="mdi:clock-outline"),
    "ventil_max": Range(0, 100, 1, PERCENTAGE, icon="mdi:valve"),
    "ventil_offset": Range(0, 100, 1, PERCENTAGE, icon="mdi:valve"),
}
# Select values (as stored) and their option texts.
OPTION_VALUES: dict[str, list[tuple[Any, str]]] = {
    "boost_dauer": [(minutes, f"{minutes} min") for minutes in BOOST_DURATIONS],
    "entkalkung_tag": [(day, day) for day in WEEKDAYS],
}
OPTIONS = {key: [text for _value, text in items] for key, items in OPTION_VALUES.items()}
ICONS = {"boost_dauer": "mdi:timer-outline", "entkalkung_tag": "mdi:calendar-week"}


def de_number(number: float) -> str:
    """German number text: 4,5 / 60 / -3,5."""
    return f"{number:g}".replace(".", ",")


def range_text(key: str) -> str:
    rng = RANGES[key]
    return (
        f"Wert muss zwischen {de_number(rng.low)} und {de_number(rng.high)} "
        f"in Schritten von {de_number(rng.step)} liegen"
    )


def config_meta(key: str) -> dict[str, Any]:
    """Input description of a config value for the panel."""
    meta: dict[str, Any] = {"key": key, "label": CONFIG_LABELS[key]}
    if key in OPTION_VALUES:
        meta["type"] = "select"
        meta["options"] = [{"value": value, "label": text} for value, text in OPTION_VALUES[key]]
        return meta
    rng = RANGES[key]
    meta.update({"type": "number", "min": rng.low, "max": rng.high, "step": rng.step, "unit": rng.unit})
    return meta


def validate_config_value(key: str, value: Any) -> Any:
    """The value on the integration's grid; ValueError with a German text otherwise."""
    label = CONFIG_LABELS.get(key)
    if label is None:
        raise ValueError(f"Unbekannter Konfigurationswert: {key}")
    if key in OPTION_VALUES:
        for option, text in OPTION_VALUES[key]:
            if value == option or value == text:
                return option
        raise ValueError(f"{label}: Ung\u00fcltige Auswahl ({value})")
    rng = RANGES[key]
    if isinstance(value, bool):
        raise ValueError(f"{label}: {range_text(key)}")
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError(f"{label}: keine Zahl ({value})") from err
    steps = (number - rng.low) / rng.step
    if not rng.low <= number <= rng.high or abs(steps - round(steps)) > 1e-9:
        raise ValueError(f"{label}: {range_text(key)}")
    return number if isinstance(rng.step, float) else int(round(number))
