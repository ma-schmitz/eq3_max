"""Values of the Home Assistant entities that feed virtual devices.

None means "not usable": the hub then marks the device's source as missing (its entities
become unavailable) and sends nothing for it. Range limits are the hub's job."""

from __future__ import annotations

import math

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

_WINDOW = {"on": True, "off": False}
# A temperature source that has not reported for this long (s) counts as unavailable: a
# sensor with a dead battery often keeps showing its last value.
SOURCE_MAX_AGE_S = 3 * 3600


def read_window(hass: HomeAssistant, entity_id: str) -> bool | None:
    """Window contact source: on = open, off = closed, anything else unusable."""
    state = hass.states.get(entity_id)
    return None if state is None else _WINDOW.get(state.state)


def read_temperature(hass: HomeAssistant, entity_id: str) -> float | None:
    """Wall thermostat source: the temperature in °C (°F and K converted); None when
    unusable or not reported for SOURCE_MAX_AGE_S."""
    state = hass.states.get(entity_id)
    if state is None:
        return None
    reported = getattr(state, "last_reported", None) or state.last_updated
    if (dt_util.utcnow() - reported).total_seconds() > SOURCE_MAX_AGE_S:
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    if unit in (UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.KELVIN):
        value = TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    return value
