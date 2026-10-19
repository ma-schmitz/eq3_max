"""Shared base of the configuration entities (number and select)."""

from __future__ import annotations

from typing import Any

from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError

from .config_defs import CONFIG_LABELS
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

    def _invalid_text(self) -> str:
        return "Ung\u00fcltiger Wert"

    def _set(self, value: Any) -> None:
        assert self.coordinator.hub is not None
        try:
            self.coordinator.hub.set_config(self._address, self._key, value)
        except FrameError as err:
            raise ServiceValidationError(f"{self._invalid_text()} ({err})") from err
