"""Base entity for eq3_max."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONFIGURATION_URL, DOMAIN, signal_update
from .coordinator import MaxCulCoordinator
from .migration import unique_id
from .protocol.devices import MaxDevice
from .protocol.messages import DeviceType
from .radios import radio_names

# Model names are not translated by Home Assistant: English, as the HA convention is.
MODELS = {
    DeviceType.HEATING_THERMOSTAT: "Radiator thermostat",
    DeviceType.HEATING_THERMOSTAT_PLUS: "Radiator thermostat+",
    DeviceType.WALL_THERMOSTAT: "Wall thermostat+",
    DeviceType.SHUTTER_CONTACT: "Window contact",
    DeviceType.PUSH_BUTTON: "Eco button",
    DeviceType.CUBE: "Cube",
}


class MaxCulEntity(Entity):
    """The name is the device's name plus the entity's own, translated by Home Assistant
    (strings.json, section entity; `label` only says whether there is one: the main
    entity carries the device's name alone). The entity_id does not follow the language:
    the migration registers it from the device name and the key."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: MaxCulCoordinator, device: MaxDevice, key: str, label: str | None) -> None:
        self.coordinator = coordinator
        self._address = device.address
        self._attr_unique_id = unique_id(device.serial, key)
        base = device.name or device.serial
        if label is None:
            self._attr_name = None
        else:
            self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.serial)},
            manufacturer="eQ-3",
            model=MODELS[device.device_type],
            name=base,
            sw_version=device.firmware or None,
            serial_number=device.serial,
            hw_version=f"RF {device.address:06X}",
            configuration_url=CONFIGURATION_URL,
        )

    @property
    def device(self) -> MaxDevice:
        assert self.coordinator.hub is not None
        return self.coordinator.hub.devices[self._address]

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_update(self.coordinator.entry.entry_id), self._handle_update)
        )

    @callback
    def _handle_update(self, address: int | None) -> None:
        # None is a hub-level update (connection, airtime, queue); device entities
        # show nothing of that and keep their state when the stick is gone.
        if address == self._address:
            self.async_write_ha_state()


class MaxCulHubEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _platform_domain: str

    def __init__(self, coordinator: MaxCulCoordinator, key: str, name: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address_hex}_{key}"
        # Fixed entity_id instead of one slugified from the hub device name.
        self.entity_id = f"{self._platform_domain}.{DOMAIN}_{key}"
        # Name from the translations (strings.json, entity.<platform>.<key>); `name` is
        # the German one, kept for reading the code.
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.address_hex)})

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_update(self.coordinator.entry.entry_id), self._handle_update)
        )

    @callback
    def _handle_update(self, address: int | None) -> None:
        if address is None:
            self.async_write_ha_state()

    def _per_radio(self, field: str) -> dict[str, Any]:
        """One value per radio module by name; empty with only the main module."""
        names = radio_names(self.coordinator.entry.data)
        if len(names) < 2:
            return {}
        return {names.get(s["id"], s["id"]): s[field] for s in self.coordinator.hub.radio_status()}
