"""Services of eq3_max: set_away, factory_reset, link, unlink, set_week_profile, copy_week_profile."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import service

from .const import DOMAIN
from .protocol.devices import WEEKDAYS, MaxDevice
from .protocol.hub import MaxHub, ResetResult
from .protocol.messages import (
    DAY_END_MINUTES,
    MAX_TEMPERATURE,
    OFF_TEMPERATURE,
    WEEK_PROFILE_POINTS,
    FrameError,
    ProfilePoint,
    format_until,
    parse_until,
)

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
SERVICE_SET_WEEK_PROFILE = "set_week_profile"
SERVICE_COPY_WEEK_PROFILE = "copy_week_profile"
ATTR_WEEKDAY = "weekday"
ATTR_PROFILE = "profile"
ATTR_TARGET_DEVICE_ID = "target_device_id"
ALL_DAYS = "alle"

POINT_SCHEMA = vol.Schema({vol.Required(ATTR_TEMPERATURE): vol.Coerce(float), vol.Optional(ATTR_UNTIL): vol.Any(cv.string, int)})
SET_WEEK_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(ATTR_WEEKDAY): vol.All(cv.ensure_list, [vol.In((*WEEKDAYS, ALL_DAYS))]),
        vol.Required(ATTR_PROFILE): vol.All(cv.ensure_list, [POINT_SCHEMA]),
    }
)
COPY_WEEK_PROFILE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_TARGET_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])}
)


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
    hass.services.async_register(DOMAIN, SERVICE_SET_WEEK_PROFILE, _async_set_week_profile, schema=SET_WEEK_PROFILE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_COPY_WEEK_PROFILE, _async_copy_week_profile, schema=COPY_WEEK_PROFILE_SCHEMA)


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


# --- Week profiles ---


def parse_profile(raw: list[dict[str, Any]]) -> list[ProfilePoint]:
    """One day's points from the service input; ServiceValidationError (German) for
    anything the device would not take. The last point may omit its end (24:00)."""
    if not 1 <= len(raw) <= WEEK_PROFILE_POINTS:
        raise ServiceValidationError(f"1 bis {WEEK_PROFILE_POINTS} Punkte je Tag, nicht {len(raw)}")
    points: list[ProfilePoint] = []
    for index, item in enumerate(raw, 1):
        temperature = float(item[ATTR_TEMPERATURE])
        if not OFF_TEMPERATURE <= temperature <= MAX_TEMPERATURE or (temperature * 2) % 1:
            raise ServiceValidationError(
                f"Temperatur muss {OFF_TEMPERATURE} bis {MAX_TEMPERATURE} \u00b0C in 0.5-Schritten sein, nicht {temperature}"
            )
        raw_until = item.get(ATTR_UNTIL)
        if raw_until is None:
            if index != len(raw):
                raise ServiceValidationError(f"Bis-Uhrzeit fehlt bei Punkt {index}")
            until = DAY_END_MINUTES
        else:
            try:
                until = parse_until(raw_until)
            except ValueError:
                raise ServiceValidationError(f"Bis-Uhrzeit muss hh:mm sein, nicht {raw_until!r}") from None
        if until % 5:
            raise ServiceValidationError(f"Bis-Uhrzeit muss in 5-Minuten-Schritten liegen, nicht {format_until(until)}")
        if points and until <= points[-1].until:
            raise ServiceValidationError("Bis-Uhrzeiten m\u00fcssen aufsteigend sein")
        points.append(ProfilePoint(temperature, until))
    if points[-1].until != DAY_END_MINUTES:
        raise ServiceValidationError("Der letzte Punkt muss bis 24:00 gelten")
    return points


def _thermostat_for_profile(hass: HomeAssistant, device_id: str):
    entry, device = resolve_max_device(hass, device_id, hub_text="Das Funkmodul selbst hat kein Wochenprogramm")
    if not device.is_climate:
        raise ServiceValidationError(f"{device.name or device.serial}: Nur Thermostate haben ein Wochenprogramm")
    return entry, device


async def write_week_profile(hub: MaxHub, device: MaxDevice, plan: dict[int, list[ProfilePoint]]) -> None:
    """Send the days to the device and wait for the acknowledgements; HomeAssistantError
    (German) when the stick is away, the device refuses or stays silent. No deadline:
    up to 14 telegrams per device, and with an empty airtime budget (brake, or culfw
    answering LOVF) each one waits minutes. The hub keeps writing if the caller goes away."""
    name = device.name or device.serial
    if not hub.reachable(device.address):
        raise HomeAssistantError(f"{name}: Funkmodul nicht verbunden")
    try:
        await hub.set_week_profile(device.address, plan)
    except FrameError as err:
        raise HomeAssistantError(str(err)) from err


def _days_from_names(names: list[str]) -> list[int]:
    if ALL_DAYS in names:
        return list(range(len(WEEKDAYS)))
    unknown = [n for n in names if n not in WEEKDAYS]
    if unknown:
        raise ServiceValidationError(f"Unbekannter Wochentag: {', '.join(unknown)}")
    return sorted({WEEKDAYS.index(n) for n in names})


async def async_set_week_profile(
    hass: HomeAssistant, device_ids: list[str], weekdays: list[str], profile: list[dict[str, Any]]
) -> list[MaxDevice]:
    """Write one profile to the given days of the given thermostats (services and the
    panel). Validation errors are ServiceValidationError, radio failures HomeAssistantError;
    returns the devices written."""
    points = parse_profile(profile)
    return await _async_write_plan(hass, device_ids, {day: points for day in _days_from_names(weekdays)})


async def async_set_week_profile_days(
    hass: HomeAssistant, device_ids: list[str], days: dict[str, list[dict[str, Any]]]
) -> list[MaxDevice]:
    """Like async_set_week_profile, with a profile of its own per weekday name: one
    write per thermostat (the panel's factory program differs on the weekend)."""
    plan = {}
    for index in _days_from_names([name for name in days if name != ALL_DAYS]):
        plan[index] = parse_profile(days[WEEKDAYS[index]])
    if ALL_DAYS in days:
        raise ServiceValidationError("Unbekannter Wochentag: alle")
    return await _async_write_plan(hass, device_ids, plan)


async def _async_write_plan(
    hass: HomeAssistant, device_ids: list[str], plan: dict[int, list[ProfilePoint]]
) -> list[MaxDevice]:
    if not plan:
        raise ServiceValidationError("Kein Wochentag angegeben")
    targets = [_thermostat_for_profile(hass, device_id) for device_id in device_ids]
    for entry, device in targets:
        await write_week_profile(entry.runtime_data.hub, device, plan)
    return [device for _, device in targets]


async def async_copy_week_profile(hass: HomeAssistant, device_id: str, target_ids: list[str]) -> list[MaxDevice]:
    """Copy the stored profile of one thermostat to others; returns the targets written."""
    entry, source = _thermostat_for_profile(hass, device_id)
    if not source.week_profile:
        raise ServiceValidationError(f"F\u00fcr {source.name or source.serial} ist kein Wochenprogramm gespeichert")
    plan = {
        WEEKDAYS.index(day): [ProfilePoint(float(p[ATTR_TEMPERATURE]), parse_until(p[ATTR_UNTIL])) for p in points]
        for day, points in source.week_profile.items()
    }
    targets = []
    for target_id in target_ids:
        target_entry, target = _thermostat_for_profile(hass, target_id)
        if target.serial == source.serial:
            raise ServiceValidationError("Ein Ger\u00e4t kann sein Wochenprogramm nicht auf sich selbst kopieren")
        if target_entry.entry_id != entry.entry_id:
            raise ServiceValidationError("Die Ger\u00e4te geh\u00f6ren zu verschiedenen Funkmodulen")
        targets.append((target_entry, target))
    if not targets:
        raise ServiceValidationError("Kein Zielger\u00e4t angegeben")
    for target_entry, target in targets:
        await write_week_profile(target_entry.runtime_data.hub, target, plan)
    return [target for _, target in targets]


async def _async_set_week_profile(call: ServiceCall) -> None:
    await async_set_week_profile(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_WEEKDAY], call.data[ATTR_PROFILE])


async def _async_copy_week_profile(call: ServiceCall) -> None:
    await async_copy_week_profile(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_TARGET_DEVICE_ID])
