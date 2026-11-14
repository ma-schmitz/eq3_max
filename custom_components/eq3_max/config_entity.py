"""Shared base of the configuration entities (number and select)."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError

from .config_defs import CONFIG_LABELS
from .errors import invalid
from .permissions import async_check_allowed
from .entity import MaxCulEntity
from .protocol.messages import FrameError

__all__ = ["CONFIG_LABELS", "MaxConfigEntity"]


class MaxConfigEntity(MaxCulEntity):
    """Shows the last acknowledged value; a sent but unacknowledged one is `ausstehend`."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, device, key: str) -> None:
        super().__init__(coordinator, device, key, CONFIG_LABELS[key])
        self._key = key

    @property
    def config_value(self) -> Any:
        return self.device.config.get(self._key)

    def _display(self, value: Any) -> Any:
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        pending = self.device.pending_value(self._key)
        return {
            "ausstehend": None if pending is None else self._display(pending),
            "quelle": self.device.config_source.get(self._key),
        }

    def _invalid(self, value: Any) -> ServiceValidationError:
        """The translated error for a value the device does not take."""
        return invalid("invalid_value")

    async def _async_set(self, value: Any) -> None:
        assert self.coordinator.hub is not None
        await async_check_allowed(self.hass, self.coordinator.entry, self._context, "config")
        try:
            self.coordinator.hub.set_config(self._address, self._key, value)
        except FrameError as err:
            raise self._invalid(value) from err
