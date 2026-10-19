"""Event entities for MAX! eco buttons."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import signal_button
from .entity import MaxCulEntity
from .protocol.messages import DeviceType


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MaxButtonEvent(coordinator, d)
        for d in coordinator.hub.devices.values()
        if d.device_type is DeviceType.PUSH_BUTTON
    )


class MaxButtonEvent(MaxCulEntity, EventEntity):
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["auto", "eco"]

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "event", None)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal_button(self.coordinator.entry.entry_id), self._handle_button)
        )

    @callback
    def _handle_button(self, address: int, event_type: str) -> None:
        if address == self._address:
            self._trigger_event(event_type)
            self.async_write_ha_state()
