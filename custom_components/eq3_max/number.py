"""Configuration values of MAX! thermostats as numbers."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .config_defs import RANGES, range_text
from .config_entity import MaxConfigEntity
from .migration import specs_for


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MaxConfigNumber(coordinator, device, spec.key)
        for device in coordinator.hub.devices.values()
        for spec in specs_for(device)
        if spec.domain == "number"
    )


class MaxConfigNumber(MaxConfigEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, device, key: str) -> None:
        super().__init__(coordinator, device, key)
        rng = RANGES[key]
        self._attr_native_min_value = rng.low
        self._attr_native_max_value = rng.high
        self._attr_native_step = rng.step
        self._attr_native_unit_of_measurement = rng.unit
        self._attr_device_class = rng.device_class
        if rng.icon is not None:
            self._attr_icon = rng.icon

    def _invalid_text(self) -> str:
        return range_text(self._key)

    @property
    def native_value(self) -> float | None:
        return self.config_value

    async def async_set_native_value(self, value: float) -> None:
        self._set(value)
