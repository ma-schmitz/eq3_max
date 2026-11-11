"""Services of eq3_max: set_away, factory_reset, link, unlink, set_week_profile, copy_week_profile, set_time."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import service

from .errors import failed, invalid, translated
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
ATTR_FORCE = "force"
UNLINK_SCHEMA = LINK_SCHEMA.extend({vol.Optional(ATTR_FORCE, default=False): cv.boolean})
SERVICE_SET_WEEK_PROFILE = "set_week_profile"
SERVICE_COPY_WEEK_PROFILE = "copy_week_profile"
SERVICE_SET_TIME = "set_time"
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


SET_TIME_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): vol.All(cv.ensure_list, [cv.string])})


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
    hass.services.async_register(DOMAIN, SERVICE_UNLINK, _async_unlink, schema=UNLINK_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_WEEK_PROFILE, _async_set_week_profile, schema=SET_WEEK_PROFILE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_COPY_WEEK_PROFILE, _async_copy_week_profile, schema=COPY_WEEK_PROFILE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_TIME, _async_set_time, schema=SET_TIME_SCHEMA)


async def _async_factory_reset(call: ServiceCall) -> None:
    from .coordinator import async_forget_device  # noqa: PLC0415

    hass = call.hass
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(call.data[ATTR_DEVICE_ID])
    if device is None:
        raise invalid("device_id_unknown")
    # A device belongs to one config entry (DeviceEntry.config_entries goes away in HA 2027.10).
    entry = hass.config_entries.async_get_entry(device.config_entry_id) if device.config_entry_id else None
    if entry is not None and (entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED):
        entry = None
    if entry is None:
        raise invalid("device_not_loaded")
    coordinator = entry.runtime_data
    serials = {value for domain, value in device.identifiers if domain == DOMAIN}
    if coordinator.address_hex in serials:
        raise invalid("hub_cannot_reset")
    hub = coordinator.hub
    max_device = next((d for d in hub.devices.values() if d.serial in serials), None)
    if max_device is None:
        raise invalid("device_unknown")
    if not hub.reachable(max_device.address):
        raise failed("not_connected")
    try:
        result = await hub.factory_reset(max_device.address)
    except FrameError as err:
        raise translated(err) from err
    except KeyError as err:
        raise failed("device_unknown") from err
    if result is ResetResult.NOT_SENT:
        raise failed("reset_not_sent")
    if result is not ResetResult.ACKED:
        raise failed("reset_not_acknowledged")
    async_forget_device(hass, entry, max_device.serial)
    dev_reg.async_update_device(device.id, remove_config_entry_id=entry.entry_id)


def resolve_max_device(hass: HomeAssistant, device_id: str, hub_key: str = "hub_cannot_link"):
    """(config entry, MaxDevice) of a device registry id; translated
    ServiceValidationError otherwise. hub_key is the error for the hub device itself."""
    device = dr.async_get(hass).async_get(device_id)
    if device is None:
        raise invalid("device_id_unknown")
    # A device belongs to one config entry (DeviceEntry.config_entries goes away in HA 2027.10).
    entry = hass.config_entries.async_get_entry(device.config_entry_id) if device.config_entry_id else None
    if entry is not None and (entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED):
        entry = None
    if entry is None:
        raise invalid("device_not_loaded")
    coordinator = entry.runtime_data
    serials = {value for domain, value in device.identifiers if domain == DOMAIN}
    if coordinator.address_hex in serials:
        raise invalid(hub_key)
    max_device = next((d for d in coordinator.hub.devices.values() if d.serial in serials), None)
    if max_device is None:
        raise invalid("device_unknown")
    return entry, max_device


async def _async_link(call: ServiceCall) -> None:
    change_link(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_PARTNER_DEVICE_ID], unlink=False)


async def _async_unlink(call: ServiceCall) -> None:
    change_link(
        call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_PARTNER_DEVICE_ID], unlink=True,
        force=call.data.get(ATTR_FORCE, False),
    )


def change_link(
    hass: HomeAssistant, device_id: str, partner_device_id: str, *, unlink: bool, force: bool = False
) -> None:
    """Queue the link change and return; the devices acknowledge later (sensor
    <basis>_verknuepfungen and the panel show the progress). Used by the services
    and the panel; ServiceValidationError with German text on invalid input."""
    entry, device = resolve_max_device(hass, device_id)
    partner_entry, partner = resolve_max_device(hass, partner_device_id)
    if partner_entry.entry_id != entry.entry_id:
        raise invalid("different_radio_modules")
    hub = entry.runtime_data.hub
    try:
        if unlink and force:
            # One direction only: the partner is removed from `device`, known or not.
            hub.unlink(device.address, partner.address, force=True)
        elif unlink:
            hub.unlink(device.address, partner.address)
        else:
            hub.link(device.address, partner.address)
    except FrameError as err:
        raise translated(err, ServiceValidationError) from err


# --- Week profiles ---


def parse_profile(raw: list[dict[str, Any]]) -> list[ProfilePoint]:
    """One day's points from the service input; ServiceValidationError (German) for
    anything the device would not take. The last point may omit its end (24:00)."""
    if not 1 <= len(raw) <= WEEK_PROFILE_POINTS:
        raise invalid("profile_point_count", max=WEEK_PROFILE_POINTS, count=len(raw))
    points: list[ProfilePoint] = []
    for index, item in enumerate(raw, 1):
        temperature = float(item[ATTR_TEMPERATURE])
        if not OFF_TEMPERATURE <= temperature <= MAX_TEMPERATURE or (temperature * 2) % 1:
            raise invalid("profile_temperature_invalid", low=OFF_TEMPERATURE, high=MAX_TEMPERATURE, value=temperature)
        raw_until = item.get(ATTR_UNTIL)
        if raw_until is None:
            if index != len(raw):
                raise invalid("profile_until_missing", index=index)
            until = DAY_END_MINUTES
        else:
            try:
                until = parse_until(raw_until)
            except ValueError:
                raise invalid("profile_until_invalid", value=raw_until) from None
        if until % 5:
            raise invalid("profile_until_step", value=format_until(until))
        if points and until <= points[-1].until:
            raise invalid("profile_until_order")
        points.append(ProfilePoint(temperature, until))
    if points[-1].until != DAY_END_MINUTES:
        raise invalid("profile_last_point")
    return points


def _thermostat_for_profile(hass: HomeAssistant, device_id: str):
    entry, device = resolve_max_device(hass, device_id, hub_key="hub_no_week_profile")
    if not device.is_climate:
        raise invalid("no_week_profile", name=device.name or device.serial)
    return entry, device


async def write_week_profile(
    hub: MaxHub, device: MaxDevice, plan: dict[int, list[ProfilePoint]], language: str | None = None
) -> None:
    """Send the days to the device and wait for the acknowledgements; HomeAssistantError
    (translated, weekday in `language`) when the stick is away, the device refuses or stays silent. No deadline:
    up to 14 telegrams per device, and with an empty airtime budget (brake, or culfw
    answering LOVF) each one waits minutes. The hub keeps writing if the caller goes away."""
    name = device.name or device.serial
    if not hub.reachable(device.address):
        raise failed("device_not_connected", name=name)
    try:
        await hub.set_week_profile(device.address, plan)
    except FrameError as err:
        raise translated(err, language=language) from err


# Weekdays in the service: German (as stored) or English, any case; "alle"/"all".
_DAY_NAMES = {
    **{name.lower(): index for index, name in enumerate(WEEKDAYS)},
    **{name: index for index, name in enumerate(
        ("saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday")
    )},
}
_ALL_NAMES = {ALL_DAYS, "all"}


def _day_index(name: str) -> int | None:
    return _DAY_NAMES.get(str(name).strip().lower())


def _days_from_names(names: list[str]) -> list[int]:
    if any(str(n).strip().lower() in _ALL_NAMES for n in names):
        return list(range(len(WEEKDAYS)))
    unknown = [str(n) for n in names if _day_index(n) is None]
    if unknown:
        raise invalid("weekday_unknown", days=", ".join(unknown))
    return sorted({_day_index(n) for n in names})


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
    for name, profile in days.items():
        if str(name).strip().lower() in _ALL_NAMES or _day_index(name) is None:
            raise invalid("weekday_unknown", days=name)
        plan[_day_index(name)] = parse_profile(profile)
    return await _async_write_plan(hass, device_ids, plan)


async def _async_write_plan(
    hass: HomeAssistant, device_ids: list[str], plan: dict[int, list[ProfilePoint]]
) -> list[MaxDevice]:
    if not plan:
        raise invalid("weekday_missing")
    targets = [_thermostat_for_profile(hass, device_id) for device_id in device_ids]
    for entry, device in targets:
        await write_week_profile(entry.runtime_data.hub, device, plan, hass.config.language)
    return [device for _, device in targets]


async def async_copy_week_profile(hass: HomeAssistant, device_id: str, target_ids: list[str]) -> list[MaxDevice]:
    """Copy the stored profile of one thermostat to others; returns the targets written."""
    entry, source = _thermostat_for_profile(hass, device_id)
    if not source.week_profile:
        raise invalid("week_profile_not_stored", name=source.name or source.serial)
    plan = {
        WEEKDAYS.index(day): [ProfilePoint(float(p[ATTR_TEMPERATURE]), parse_until(p[ATTR_UNTIL])) for p in points]
        for day, points in source.week_profile.items()
    }
    targets = []
    for target_id in target_ids:
        target_entry, target = _thermostat_for_profile(hass, target_id)
        if target.serial == source.serial:
            raise invalid("copy_to_self")
        if target_entry.entry_id != entry.entry_id:
            raise invalid("different_radio_modules")
        targets.append((target_entry, target))
    if not targets:
        raise invalid("copy_no_target")
    for target_entry, target in targets:
        await write_week_profile(target_entry.runtime_data.hub, target, plan, hass.config.language)
    return [target for _, target in targets]


async def _async_set_week_profile(call: ServiceCall) -> None:
    await async_set_week_profile(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_WEEKDAY], call.data[ATTR_PROFILE])


async def async_set_time(hass: HomeAssistant, device_ids: list[str]) -> list[MaxDevice]:
    """Set the clock of the given thermostats to Home Assistant's local time, one after
    the other, waiting for each acknowledgement; returns the devices set."""
    targets = [
        resolve_max_device(hass, device_id, hub_key="hub_no_clock") for device_id in device_ids
    ]
    for entry, device in targets:
        hub = entry.runtime_data.hub
        if not hub.reachable(device.address):
            raise failed("device_not_connected", name=device.name or device.serial)
        try:
            await hub.set_time(device.address)
        except FrameError as err:
            raise translated(err) from err
    return [device for _, device in targets]


async def _async_set_time(call: ServiceCall) -> None:
    await async_set_time(call.hass, call.data[ATTR_DEVICE_ID])


async def _async_copy_week_profile(call: ServiceCall) -> None:
    await async_copy_week_profile(call.hass, call.data[ATTR_DEVICE_ID], call.data[ATTR_TARGET_DEVICE_ID])
