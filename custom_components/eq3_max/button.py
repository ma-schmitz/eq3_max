"""Pairing button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import MaxCulHubEntity

PAIRING_SECONDS = 60


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([MaxPairingButton(entry.runtime_data)])


class MaxPairingButton(MaxCulHubEntity, ButtonEntity):
    _platform_domain = "button"
    _attr_icon = "mdi:link-plus"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "anlernen", "Anlernen")

    async def async_press(self) -> None:
        self.coordinator.hub.open_pairing(PAIRING_SECONDS)
