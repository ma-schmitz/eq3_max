"""Climate entities for MAX! thermostats."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import CONF_AWAY_HOURS, CONF_AWAY_TEMPERATURE, DEFAULT_AWAY_HOURS, DEFAULT_AWAY_TEMPERATURE
from .entity import MaxCulEntity
from .protocol.messages import (
    MAX_TEMPERATURE,
    OFF_TEMPERATURE,
    FrameError,
    Mode,
    normalize_temperature,
    round_until,
)

DEFAULT_ON_TEMPERATURE = 21.0


def _local_now() -> datetime:
    """HA local wall-clock time, naive (MAX! end times carry no zone)."""
    return dt_util.now().replace(tzinfo=None)


def _away_end(end: datetime) -> datetime:
    """Round the end time up to MAX! resolution; the rounded value must lie ahead."""
    rounded = round_until(end)
    if rounded <= _local_now():
        raise ServiceValidationError("Endzeit liegt nicht in der Zukunft")
    return rounded


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MaxClimate(coordinator, d) for d in coordinator.hub.devices.values() if d.is_climate
    )


class MaxClimate(MaxCulEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = OFF_TEMPERATURE
    _attr_max_temp = MAX_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NONE, PRESET_BOOST, PRESET_AWAY]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "climate", None)

    @property
    def current_temperature(self) -> float | None:
        return self.device.measured

    @property
    def target_temperature(self) -> float | None:
        return self.device.target

    @property
    def hvac_mode(self) -> HVACMode | None:
        mode = self.device.mode
        if mode is None:
            return None
        if mode is Mode.AUTO:
            return HVACMode.AUTO
        if mode is Mode.MANUAL and self.device.target == OFF_TEMPERATURE:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self.device.is_heating_thermostat:
            return None
        if self.hvac_mode is HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if (self.device.valve or 0) > 0 else HVACAction.IDLE

    @property
    def preset_mode(self) -> str:
        if self.device.mode is Mode.BOOST:
            return PRESET_BOOST
        if self.device.mode is Mode.TEMPORARY:
            return PRESET_AWAY
        return PRESET_NONE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = self.device
        attrs: dict[str, Any] = {
            "id": dev.serial,
            "ausstehend": dev.pending_target,
            "ausstehend_modus": None if dev.pending_mode is None else dev.pending_mode.name.lower(),
            "bis": None if dev.until is None else dev.until.replace(tzinfo=dt_util.get_default_time_zone()).isoformat(),
        }
        if self.device.is_heating_thermostat:
            attrs["valve"] = self.device.valve
        return attrs

    def _base_target(self) -> float | None:
        """Target a mode/preset change builds on: a queued command beats the report."""
        dev = self.device
        if dev.has_pending and dev.pending_target is not None:
            return dev.pending_target
        return dev.target

    def _base_mode(self) -> Mode | None:
        """Mode a mode/preset change starts from: a queued command beats the report."""
        dev = self.device
        return dev.pending_mode if dev.has_pending else dev.mode

    def _comfort(self) -> float:
        """Comfort temperature to return to: the last manual one (HA or device), else the
        configured comfort temperature, else the default."""
        if self.device.last_comfort is not None:
            return self.device.last_comfort
        configured = self.device.config.get("komfort")
        if configured is not None:
            return float(configured)
        return DEFAULT_ON_TEMPERATURE

    def _send(self, temperature: float | None, mode: Mode, until: datetime | None = None) -> None:
        assert self.coordinator.hub is not None
        try:
            self.coordinator.hub.set_temperature(self._address, temperature, mode, until=until)
        except FrameError as err:
            raise ServiceValidationError(str(err)) from err
        if mode is Mode.MANUAL and temperature is not None:
            # Only manual targets are comfort values (not boost, away or auto).
            sent = normalize_temperature(temperature)
            if sent > OFF_TEMPERATURE:
                self.device.last_comfort = sent

    def _away_temperature(self) -> float:
        return float(self.coordinator.entry.options.get(CONF_AWAY_TEMPERATURE, DEFAULT_AWAY_TEMPERATURE))

    async def async_set_away(self, until: datetime, temperature: float | None = None) -> None:
        """Service eq3_max.set_away: mode TEMPORARY until the given local time."""
        end = dt_util.as_local(until).replace(tzinfo=None) if until.tzinfo is not None else until
        self._send(self._away_temperature() if temperature is None else float(temperature), Mode.TEMPORARY, _away_end(end))

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        if hvac_mode in (HVACMode.OFF, HVACMode.AUTO) or (hvac_mode is not None and temperature is None):
            await self.async_set_hvac_mode(hvac_mode)
            return
        if temperature is None:
            return
        self._send(float(temperature), Mode.MANUAL)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            self._send(OFF_TEMPERATURE, Mode.MANUAL)
        elif hvac_mode == HVACMode.AUTO:
            self._send(None, Mode.AUTO)
        elif self._base_mode() in (Mode.TEMPORARY, Mode.BOOST):
            # Away/boost targets are no comfort values: heat returns to the last manual one.
            self._send(self._comfort(), Mode.MANUAL)
        else:
            current = self._base_target()
            target = current if current is not None and current > OFF_TEMPERATURE else self._comfort()
            self._send(target, Mode.MANUAL)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == PRESET_AWAY:
            hours = int(self.coordinator.entry.options.get(CONF_AWAY_HOURS, DEFAULT_AWAY_HOURS))
            self._send(self._away_temperature(), Mode.TEMPORARY, _away_end(_local_now() + timedelta(hours=hours)))
            return
        if preset_mode != PRESET_BOOST and self._base_mode() in (Mode.TEMPORARY, Mode.BOOST):
            self._send(self._comfort(), Mode.MANUAL)
            return
        current = self._base_target()
        target = current if current is not None else self._comfort()
        mode = Mode.BOOST if preset_mode == PRESET_BOOST else Mode.MANUAL
        self._send(target, mode)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT)
