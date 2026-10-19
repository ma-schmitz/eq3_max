"""Binary sensors for eq3_max."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .entity import MaxCulEntity, MaxCulHubEntity
from .migration import specs_for


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [MaxConnectedSensor(coordinator)]
    for device in coordinator.hub.devices.values():
        for spec in specs_for(device):
            if spec.domain != "binary_sensor":
                continue
            cls = {"lowbat": MaxLowBat, "funkfehler": MaxRfError, "gesperrt": MaxLocked, "state": MaxWindow}[spec.key]
            entities.append(cls(coordinator, device))
    async_add_entities(entities)


class MaxLowBat(MaxCulEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "lowbat", "Batterie")

    @property
    def is_on(self) -> bool | None:
        return self.device.battery_low


class MaxRfError(MaxCulEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "funkfehler", "Funkfehler")

    @property
    def is_on(self) -> bool:
        return bool(self.device.rf_error) or self.device.command_failed or bool(self.device.config_failed)


class MaxLocked(MaxCulEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lock"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "gesperrt", "gesperrt")

    @property
    def is_on(self) -> bool | None:
        return self.device.locked


class MaxWindow(MaxCulEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "state", "Fenster")

    @property
    def is_on(self) -> bool | None:
        return self.device.window_open


class MaxConnectedSensor(MaxCulHubEntity, BinarySensorEntity):
    _platform_domain = "binary_sensor"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "verbunden", "Verbunden")

    @property
    def is_on(self) -> bool:
        return self.coordinator.hub.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        per_radio = self._per_radio("connected")
        return {"funkmodule": per_radio} if per_radio else None
