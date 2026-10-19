"""Configuration values of MAX! heating thermostats as selects, and the radio module
of every device (only with more than one module)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .config_defs import ICONS, OPTIONS
from .config_entity import MaxConfigEntity
from .entity import MaxCulEntity
from .const import DOMAIN
from .migration import specs_for, unique_id
from .protocol.messages import FrameError
from .radios import radio_names


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        MaxConfigSelect(coordinator, device, spec.key)
        for device in coordinator.hub.devices.values()
        for spec in specs_for(device)
        if spec.domain == "select"
    ]
    if len(radio_names(entry.data)) > 1:
        entities.extend(MaxRadioSelect(coordinator, device) for device in coordinator.hub.devices.values())
    else:
        # Back to a single module: the module selects of before go.
        ent_reg = er.async_get(hass)
        for device in coordinator.hub.devices.values():
            entity_id = ent_reg.async_get_entity_id("select", DOMAIN, unique_id(device.serial, "funkmodul"))
            if entity_id is not None:
                ent_reg.async_remove(entity_id)
    async_add_entities(entities)


class MaxRadioSelect(MaxCulEntity, SelectEntity):
    """Radio module the commands to the device go through; changing it sends nothing."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:radio-tower"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator, device, "funkmodul", "Funkmodul")
        self._names = radio_names(coordinator.entry.data)
        self._attr_options = list(self._names.values())

    @property
    def current_option(self) -> str | None:
        return self._names.get(self.device.radio, self._names[""])

    @property
    def extra_state_attributes(self) -> dict[str, float | None]:
        """RSSI per module: which module hears the device best."""
        return {f"rssi_{slugify(name)}": self.device.rssi_by_radio.get(radio) for radio, name in self._names.items()}

    async def async_select_option(self, option: str) -> None:
        radio = next((radio for radio, name in self._names.items() if name == option), None)
        if radio is None:
            raise ServiceValidationError(f"Unbekanntes Funkmodul: {option}")
        try:
            self.coordinator.async_set_radio(self._address, radio)
        except FrameError as err:
            raise ServiceValidationError(str(err)) from err


class MaxConfigSelect(MaxConfigEntity, SelectEntity):
    def __init__(self, coordinator, device, key: str) -> None:
        super().__init__(coordinator, device, key)
        self._attr_options = OPTIONS[key]
        self._attr_icon = ICONS[key]

    def _display(self, value: Any) -> str:
        return f"{value} min" if self._key == "boost_dauer" else str(value)

    def _invalid_text(self) -> str:
        return "Ung\u00fcltige Auswahl"

    @property
    def current_option(self) -> str | None:
        value = self.config_value
        return None if value is None else self._display(value)

    async def async_select_option(self, option: str) -> None:
        if self._key == "boost_dauer":
            try:
                value: Any = int(option.removesuffix(" min"))
            except ValueError as err:
                raise ServiceValidationError(f"Ung\u00fcltige Auswahl: {option}") from err
        else:
            value = option
        self._set(value)
