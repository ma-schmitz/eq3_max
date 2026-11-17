"""Entity registry: our own entries, and the takeover from the predecessors homematic and
max_cul. Entries of other integrations are only read here; they change hands in
async_take_over alone, which runs once an admin confirmed the repair listing them."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import CONF_DEVICES, DOMAIN
from .protocol.devices import CONFIG_TEMP_KEYS, CONFIG_VALVE_KEYS, MaxDevice
from .protocol.messages import DeviceType

_LOGGER = logging.getLogger(__name__)
LEGACY_DOMAIN = "max_cul"
# Whose entities can be taken over. Never anything else: a template entity on the entity ID
# we would like is the user's own and keeps its place (ours gets a suffix).
PREDECESSOR_PLATFORMS = ("homematic", LEGACY_DOMAIN)
# Integrations that must not be loaded while we take over (they hold the entities or the stick).
BLOCKING_INTEGRATIONS = ("homematic", LEGACY_DOMAIN)
TAKEOVER_ISSUE = "takeover"


def takeover_issue_id(entry_id: str) -> str:
    return f"{TAKEOVER_ISSUE}_{entry_id}"


class MigrationBlocked(Exception):
    """A predecessor integration is still loaded."""

    def __init__(self, integration: str) -> None:
        super().__init__(f"{integration} integration is still loaded")
        self.integration = integration


@dataclass(frozen=True)
class EntitySpec:
    domain: str
    key: str
    old_suffix: str | None


@dataclass(frozen=True)
class Takeover:
    """A predecessor's registry entry and the entity of ours that would take its place."""

    old_id: str
    platform: str
    device: MaxDevice
    spec: EntitySpec


_DIAG = [
    EntitySpec("binary_sensor", "lowbat", "_LOWBAT"),
    EntitySpec("sensor", "rssi", None),
    EntitySpec("sensor", "verknuepfungen", None),
]
_CLIMATE_DIAG = [
    EntitySpec("binary_sensor", "funkfehler", None),
    EntitySpec("binary_sensor", "gesperrt", None),
    EntitySpec("sensor", "zuletzt_gemeldet", None),
]

# Device configuration: select for the value lists, number for the rest.
SELECT_CONFIG_KEYS = ("boost_dauer", "entkalkung_tag", "anzeige")


def _config_specs(keys: tuple[str, ...]) -> list[EntitySpec]:
    return [EntitySpec("select" if key in SELECT_CONFIG_KEYS else "number", key, None) for key in keys]


def specs_for(device: MaxDevice) -> list[EntitySpec]:
    if device.is_heating_thermostat:
        return [
            EntitySpec("climate", "climate", ""), EntitySpec("sensor", "ventil", None), *_DIAG, *_CLIMATE_DIAG,
            *_config_specs(CONFIG_TEMP_KEYS + CONFIG_VALVE_KEYS),
            # Poll the measured temperature (the device reports it only on its own changes).
            EntitySpec("select", "ist_abfragen", None),
        ]
    if device.device_type is DeviceType.WALL_THERMOSTAT:
        # device.config_keys: the temperatures and, of the valve set, the boost duration.
        return [EntitySpec("climate", "climate", ""), *_DIAG, *_CLIMATE_DIAG, *_config_specs(device.config_keys)]
    if device.device_type is DeviceType.SHUTTER_CONTACT:
        return [EntitySpec("binary_sensor", "state", "_STATE"), *_DIAG]
    if device.device_type is DeviceType.PUSH_BUTTON:
        return [EntitySpec("event", "event", None), *_DIAG]
    if device.device_type is DeviceType.PLUG_ADAPTER:
        # Not supported yet: only that it is there and how well it is heard (mains, no battery).
        return [EntitySpec("sensor", "rssi", None), EntitySpec("sensor", "zuletzt_gemeldet", None)]
    return []


def unique_id(serial: str, key: str) -> str:
    return f"{serial}_{key}"


def _object_id(entity_id: str) -> str:
    return entity_id.split(".", 1)[1]


def _strip(entity_id: str, strip: str) -> str:
    object_id = _object_id(entity_id)
    return object_id[: -len(strip)] if strip and object_id.endswith(strip) else object_id


def _base(reg: er.EntityRegistry, device: MaxDevice) -> str:
    # Predecessors first: as long as they are there, they sit on the entity IDs the user
    # knows (ours carry a suffix next to them). Once they are gone, entities added later
    # (e.g. the configuration) follow our own entity IDs.
    own_keys = (
        ("climate", "climate", ""),
        ("binary_sensor", "state", "_state"),
        ("binary_sensor", "lowbat", "_lowbat"),
        ("event", "event", ""),
    )
    for domain, key, strip in own_keys:
        entity_id = reg.async_get_entity_id(domain, LEGACY_DOMAIN, unique_id(device.serial, key))
        if entity_id:
            return _strip(entity_id, strip)
    for domain, suffix, strip in (
        ("climate", "", ""),
        ("binary_sensor", "_STATE", "_state"),
        ("binary_sensor", "_LOWBAT", "_lowbat"),
    ):
        entity_id = reg.async_get_entity_id(domain, "homematic", device.serial + suffix)
        if entity_id:
            return _strip(entity_id, strip)
    for domain, key, strip in own_keys:
        entity_id = reg.async_get_entity_id(domain, DOMAIN, unique_id(device.serial, key))
        if entity_id:
            return _strip(entity_id, strip)
    return slugify(device.name or device.serial)


def _area_id(hass: HomeAssistant, old_entry: er.RegistryEntry) -> str | None:
    """Area of the old entity; for max_cul also the area of its device (homematic had none)."""
    if old_entry.area_id or old_entry.platform != LEGACY_DOMAIN or old_entry.device_id is None:
        return old_entry.area_id
    device = dr.async_get(hass).async_get(old_entry.device_id)
    return device.area_id if device is not None else None


_NAME_SUFFIXES = (" STATE", " LOWBAT", " Ventil", " Fenster")


def _needs_name(device: MaxDevice) -> bool:
    return not device.name or device.name == device.serial


def _predecessor_name(device: MaxDevice, old_entry: er.RegistryEntry) -> str | None:
    """Device name from a predecessor entity: its user name, else its original name."""
    for raw in (old_entry.name, old_entry.original_name):
        if not raw:
            continue
        name = raw.strip()
        for suffix in _NAME_SUFFIXES:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()
                break
        if name and name != device.serial:
            return name
    return None


@callback
def _persist_names(hass: HomeAssistant, entry: ConfigEntry, names: dict[str, str]) -> None:
    items = [
        {**item, "name": names[item["serial"]]} if item.get("serial") in names else item
        for item in entry.data[CONF_DEVICES]
    ]
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICES: items})


def _suggested(base: str, spec: EntitySpec) -> str:
    if spec.key in ("climate", "event"):
        return base
    return f"{base}_{spec.key}"


def _predecessor(reg: er.EntityRegistry, device: MaxDevice, spec: EntitySpec, base: str) -> str | None:
    """Entity ID of the predecessor's entry for this entity of ours, if there is one."""
    uid = unique_id(device.serial, spec.key)
    old_id = reg.async_get_entity_id(spec.domain, LEGACY_DOMAIN, uid)
    if old_id is None and spec.old_suffix is not None:
        old_id = reg.async_get_entity_id(spec.domain, "homematic", device.serial + spec.old_suffix)
    if old_id is None:
        target = f"{spec.domain}.{_suggested(base, spec)}"
        existing = reg.async_get(target)
        if existing is not None and existing.platform in PREDECESSOR_PLATFORMS:
            old_id = target
    return old_id


@callback
def async_find_takeovers(hass: HomeAssistant, devices: list[MaxDevice]) -> list[Takeover]:
    """Predecessor entries our entities could take over. Reads the registry, changes nothing."""
    reg = er.async_get(hass)
    found: list[Takeover] = []
    for device in devices:
        base = _base(reg, device)
        for spec in specs_for(device):
            old_id = _predecessor(reg, device, spec, base)
            if old_id is not None:
                found.append(Takeover(old_id, reg.async_get(old_id).platform, device, spec))
    return found


def _check_not_blocked(hass: HomeAssistant) -> None:
    for integration in BLOCKING_INTEGRATIONS:
        if integration in hass.config.components:
            raise MigrationBlocked(integration)


@callback
def async_prepare_entities(hass: HomeAssistant, entry: ConfigEntry, devices: list[MaxDevice]) -> list[Takeover]:
    """Create the registry entries of our entities (entity IDs follow the device's base) and
    return what could be taken over from predecessors. Entries of other integrations stay as
    they are: where one sits on the entity ID we would like, ours gets a suffix."""
    _check_not_blocked(hass)
    reg = er.async_get(hass)
    for device in devices:
        base = _base(reg, device)
        for spec in specs_for(device):
            uid = unique_id(device.serial, spec.key)
            if reg.async_get_entity_id(spec.domain, DOMAIN, uid):
                continue
            reg.async_get_or_create(
                spec.domain, DOMAIN, uid, suggested_object_id=_suggested(base, spec), config_entry=entry
            )
    return async_find_takeovers(hass, devices)


@callback
def async_take_over(hass: HomeAssistant, entry: ConfigEntry, devices: list[MaxDevice]) -> list[Takeover]:
    """The admin confirmed: remove the predecessors' entries and give our entities their
    entity ID, area, name, icon, aliases, labels, options and the user's disabled/hidden
    flags. The caller reloads the entry afterwards (device names may have changed)."""
    _check_not_blocked(hass)
    reg = er.async_get(hass)
    names: dict[str, str] = {}
    done: list[Takeover] = []
    for takeover in async_find_takeovers(hass, devices):
        device, spec, old_id = takeover.device, takeover.spec, takeover.old_id
        old_entry = reg.async_get(old_id)
        if old_entry is None:
            continue
        keep = {
            "area_id": _area_id(hass, old_entry),
            "name": old_entry.name,
            "icon": old_entry.icon,
            "aliases": set(old_entry.aliases) or None,
            "labels": set(old_entry.labels) or None,
            "disabled_by": (
                er.RegistryEntryDisabler.USER if old_entry.disabled_by is er.RegistryEntryDisabler.USER else None
            ),
            "hidden_by": er.RegistryEntryHider.USER if old_entry.hidden_by is er.RegistryEntryHider.USER else None,
        }
        old_options = {k: dict(v) for k, v in old_entry.options.items()}
        if _needs_name(device):
            # Homegear has no names: the serial is no name, the predecessor knows better.
            name = _predecessor_name(device, old_entry)
            if name is not None:
                device.name = name
                names[device.serial] = name
        _LOGGER.info("Taking over %s (%s) as %s_%s", old_id, old_entry.platform, device.serial, spec.key)
        uid = unique_id(device.serial, spec.key)
        own_id = reg.async_get_entity_id(spec.domain, DOMAIN, uid)
        reg.async_remove(old_id)
        if own_id is None:
            own_id = reg.async_get_or_create(
                spec.domain, DOMAIN, uid, suggested_object_id=_object_id(old_id), config_entry=entry
            ).entity_id
        changes = {k: v for k, v in keep.items() if v is not None}
        if own_id != old_id:
            changes["new_entity_id"] = old_id
        if changes:
            reg.async_update_entity(own_id, **changes)
        for domain_key, value in old_options.items():
            reg.async_update_entity_options(old_id, domain_key, value)
        done.append(takeover)
    if names:
        _LOGGER.info("Device names taken from predecessors: %s", names)
        _persist_names(hass, entry, names)
    return done
