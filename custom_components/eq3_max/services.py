"""Services of eq3_max: set_away, factory_reset, link and unlink."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import service

from .const import DOMAIN
from .protocol.hub import ResetResult
from .protocol.messages import MAX_TEMPERATURE, OFF_TEMPERATURE, FrameError

SERVICE_SET_AWAY = "set_away"
SERVICE_FACTORY_RESET = "factory_reset"
ATTR_UNTIL = "until"
ATTR_TEMPERATURE = "temperature"
ATTR_DEVICE_ID = "device_id"
ATTR_PARTNER_DEVICE_ID = "partner_device_id"
SERVICE_LINK = "link"
SERVICE_UNLINK = "unlink"

SET_AWAY_SCHEMA = {
    vol.Optional(ATTR_TEMPERATURE): vol.All(vol.Coerce(float), vol.Range(min=OFF_TEMPERATURE, max=MAX_TEMPERATURE)),
    vol.Required(ATTR_UNTIL): cv.datetime,
}
FACTORY_RESET_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})
LINK_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_PARTNER_DEVICE_ID): cv.string})


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_AWAY,
        entity_domain=CLIMATE_DOMAIN,
        schema=SET_AWAY_SCHEMA,
        func="async_set_away",
    )
    hass.services.async_register(DOMAIN, SERVICE_FACTORY_RESET, _async_factory_reset, schema=FACTORY_RESET_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_LINK, _async_link, schema=LINK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_UNLINK, _async_unlink, schema=LINK_SCHEMA)


async def _async_factory_reset(call: ServiceCall) -> None:
    from .coordinator import async_forget_device  # noqa: PLC0415

    hass = call.hass
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(call.data[ATTR_DEVICE_ID])
    if device is None:
        raise ServiceValidationError("Unbekanntes Ger\xe4t")
    entry = next(
        (
            e
            for e in (hass.config_entries.async_get_entry(i) for i in device.config_entries)
            if e is not None and e.domain == DOMAIN and e.state is ConfigEntryState.LOADED
        ),
        None,
    )
    if entry is None:
        raise ServiceValidationError("Ger\xe4t geh\xf6rt zu keiner geladenen eQ-3-MAX!-Integration")
    coordinator = entry.runtime_data
    serials = {value for domain, value in device.identifiers if domain == DOMAIN}
    if coordinator.address_hex in serials:
        raise ServiceValidationError("Das Funkmodul selbst kann nicht zur\xfcckgesetzt werden")
    hub = coordinator.hub
    max_device = next((d for d in hub.devices.values() if d.serial in serials), None)
    if max_device is None:
        raise ServiceValidationError("Ger\u00e4t ist dem Funkmodul nicht bekannt")
    if not hub.reachable(max_device.address):
        raise HomeAssistantError("Funkmodul nicht verbunden")
    try:
        result = await hub.factory_reset(max_device.address)
    except FrameError as err:
        raise HomeAssistantError(str(err)) from err
    except KeyError as err:
        raise HomeAssistantError("Ger\u00e4t ist dem Funkmodul nicht bekannt") from err
    if result is ResetResult.NOT_SENT:
        raise HomeAssistantError("Werksreset nicht gesendet")
    if result is not ResetResult.ACKED:
        raise HomeAssistantError(
            "Ger\u00e4t hat den Werksreset nicht quittiert \u2013 es wurde eventuell trotzdem zur\u00fcckgesetzt"
        )
    async_forget_device(hass, entry, max_device.serial)
    dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


def resolve_max_device(
    hass: HomeAssistant, device_id: str, hub_text: str = "Das Funkmodul selbst kann nicht verkn\u00fcpft werden"
):
    """(config entry, MaxDevice) of a device registry id; ServiceValidationError
    (German text) otherwise. hub_text is the error for the hub device itself."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise ServiceValidationError("Unbekanntes Ger\xe4t")
    entry = next(
        (
            e
            for e in (hass.config_entries.async_get_entry(i) for i in device.config_entries)
            if e is not None and e.domain == DOMAIN and e.state is ConfigEntryState.LOADED
        ),
        None,
    )
    if entry is None:
        raise ServiceValidationError("Ger\xe4t geh\xf6rt zu keiner geladenen eQ-3-MAX!-Integration")
    coordinator = entry.runtime_data
    serials = {value for domain, value in device.identifiers if domain == DOMAIN}
    if coordinator.address_hex in serials:
        raise ServiceValidationError(hub_text)
    max_device = next((d for d in coordinator.hub.devices.values() if d.serial in serials), None)
    if max_device is None:
        raise ServiceValidationError("Ger\u00e4t ist dem Funkmodul nicht bekannt")
    return entry, max_device


async def _async_link(call: ServiceCall) -> None:
    change_link(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_PARTNER_DEVICE_ID], unlink=False)


async def _async_unlink(call: ServiceCall) -> None:
    change_link(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_PARTNER_DEVICE_ID], unlink=True)


def change_link(hass: HomeAssistant, device_id: str, partner_device_id: str, *, unlink: bool) -> None:
    """Queue the link change and return; the devices acknowledge later (sensor
    <basis>_verknuepfungen and the panel show the progress). Used by the services
    and the panel; ServiceValidationError with German text on invalid input."""
    entry, device = resolve_max_device(hass, device_id)
    partner_entry, partner = resolve_max_device(hass, partner_device_id)
    if partner_entry.entry_id != entry.entry_id:
        raise ServiceValidationError("Die Ger\u00e4te geh\u00f6ren zu verschiedenen Funkmodulen")
    hub = entry.runtime_data.hub
    try:
        if unlink:
            hub.unlink(device.address, partner.address)
        else:
            hub.link(device.address, partner.address)
    except FrameError as err:
        raise ServiceValidationError(str(err)) from err
