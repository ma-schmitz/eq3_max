"""Sensors for eq3_max."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory, UnitOfTime

from .entity import MaxCulEntity, MaxCulHubEntity
from .migration import specs_for
from .protocol.hub import link_status


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        MaxAirtimeSensor(coordinator),
        MaxQueueSensor(coordinator),
    ]
    for device in coordinator.hub.devices.values():
        keys = {s.key for s in specs_for(device) if s.domain == "sensor"}
        if "ventil" in keys:
            entities.append(MaxValveSensor(coordinator, device))
        if "rssi" in keys:
            entities.append(MaxRssiSensor(coordinator, device))
        if "zuletzt_gemeldet" in keys:
            entities.append(MaxLastSeenSensor(coordinator, device))
        if "verknuepfungen" in keys:
            entities.append(MaxLinksSensor(coordinator, device))
    async_add_entities(entities)


class MaxValveSensor(MaxCulEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:valve"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "ventil", "Ventil")

    @property
    def native_value(self) -> int | None:
        return self.device.valve


class MaxRssiSensor(MaxCulEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "rssi", "RSSI")

    @property
    def native_value(self) -> float | None:
        return self.device.rssi


class MaxLastSeenSensor(MaxCulEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "zuletzt_gemeldet", "zuletzt gemeldet")

    @property
    def native_value(self) -> datetime | None:
        ts = self.device.last_seen
        return None if ts is None else datetime.fromtimestamp(ts, UTC)


class MaxLinksSensor(MaxCulEntity, SensorEntity):
    """Number of complete links (both directions acknowledged); partners and pending
    link operations as attributes."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:link-variant"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "verknuepfungen", "Verkn\u00fcpfungen")

    def _name(self, serial: str) -> str:
        dev = next((d for d in self.coordinator.hub.devices.values() if d.serial == serial), None)
        return serial if dev is None else (dev.name or dev.serial)

    @property
    def native_value(self) -> int:
        return len(link_status(self.coordinator.hub.devices, self.device).partners)

    @property
    def extra_state_attributes(self) -> dict[str, list[str]]:
        status = link_status(self.coordinator.hub.devices, self.device)
        return {
            "partner": [self._name(serial) for serial in status.partners],
            "ausstehend": [f"{self._name(serial)}: {state}" for serial, state in status.pending],
        }


class MaxAirtimeSensor(MaxCulHubEntity, SensorEntity):
    _platform_domain = "sensor"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:radio-tower"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "sendezeit_1h", "Sendezeit 1h")

    @property
    def native_value(self) -> float:
        # The busiest module: the 1 % limit applies to each transmitter.
        return round(self.coordinator.hub.airtime_last_hour, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        per_radio = {name: round(value, 1) for name, value in self._per_radio("airtime").items()}
        return {"funkmodule": per_radio} if per_radio else None


class MaxQueueSensor(MaxCulHubEntity, SensorEntity):
    _platform_domain = "sensor"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:tray-full"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "warteschlange", "Warteschlange")

    @property
    def native_value(self) -> int:
        return self.coordinator.hub.queue_length

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        per_radio = self._per_radio("queue")
        return {"funkmodule": per_radio} if per_radio else None
