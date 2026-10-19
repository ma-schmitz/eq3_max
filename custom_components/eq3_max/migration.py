"""Take over entity registry entries from the predecessors homematic and max_cul."""

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
REPLACEABLE_PLATFORMS = ("homematic", "template", LEGACY_DOMAIN)
# Integrations that must not be loaded while we take over (they hold the entities or the stick).
BLOCKING_INTEGRATIONS = ("homematic", LEGACY_DOMAIN)


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
SELECT_CONFIG_KEYS = ("boost_dauer", "entkalkung_tag")


def _config_specs(keys: tuple[str, ...]) -> list[EntitySpec]:
    return [EntitySpec("select" if key in SELECT_CONFIG_KEYS else "number", key, None) for key in keys]


def specs_for(device: MaxDevice) -> list[EntitySpec]:
    if device.is_heating_thermostat:
        return [
            EntitySpec("climate", "climate", ""), EntitySpec("sensor", "ventil", None), *_DIAG, *_CLIMATE_DIAG,
            *_config_specs(CONFIG_TEMP_KEYS + CONFIG_VALVE_KEYS),
        ]
    if device.device_type is DeviceType.WALL_THERMOSTAT:
        return [EntitySpec("climate", "climate", ""), *_DIAG, *_CLIMATE_DIAG, *_config_specs(CONFIG_TEMP_KEYS)]
    if device.device_type is DeviceType.SHUTTER_CONTACT:
        return [EntitySpec("binary_sensor", "state", "_STATE"), *_DIAG]
    if device.device_type is DeviceType.PUSH_BUTTON:
        return [EntitySpec("event", "event", None), *_DIAG]
    return []


def unique_id(serial: str, key: str) -> str:
    return f"{serial}_{key}"


def _object_id(entity_id: str) -> str:
    return entity_id.split(".", 1)[1]


def _base(reg: er.EntityRegistry, device: MaxDevice) -> str:
    # Own entities first: after the takeover the predecessors are gone, entities
    # added later (e.g. the configuration) follow the existing entity_ids.
    for platform in (DOMAIN, LEGACY_DOMAIN):
        for domain, key, strip in (
            ("climate", "climate", ""),
            ("binary_sensor", "state", "_state"),
            ("binary_sensor", "lowbat", "_lowbat"),
            ("event", "event", ""),
        ):
            entity_id = reg.async_get_entity_id(domain, platform, unique_id(device.serial, key))
            if entity_id:
                object_id = _object_id(entity_id)
                return object_id[: -len(strip)] if strip and object_id.endswith(strip) else object_id
    for domain, suffix, strip in (
        ("climate", "", ""),
        ("binary_sensor", "_STATE", "_state"),
        ("binary_sensor", "_LOWBAT", "_lowbat"),
    ):
        entity_id = reg.async_get_entity_id(domain, "homematic", device.serial + suffix)
        if entity_id:
            object_id = _object_id(entity_id)
            return object_id[: -len(strip)] if strip and object_id.endswith(strip) else object_id
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


@callback
def async_migrate_entities(hass: HomeAssistant, entry: ConfigEntry, devices: list[MaxDevice]) -> None:
    for integration in BLOCKING_INTEGRATIONS:
        if integration in hass.config.components:
            raise MigrationBlocked(integration)
    reg = er.async_get(hass)
    names: dict[str, str] = {}
    for device in devices:
        base = _base(reg, device)
        for spec in specs_for(device):
            uid = unique_id(device.serial, spec.key)
            if reg.async_get_entity_id(spec.domain, DOMAIN, uid):
                continue
            target = f"{spec.domain}.{_suggested(base, spec)}"
            old_id = reg.async_get_entity_id(spec.domain, LEGACY_DOMAIN, uid)
            if old_id is None and spec.old_suffix is not None:
                old_id = reg.async_get_entity_id(spec.domain, "homematic", device.serial + spec.old_suffix)
            if old_id is None:
                existing = reg.async_get(target)
                if existing is not None and existing.platform in REPLACEABLE_PLATFORMS:
                    old_id = target
            keep: dict = {}
            old_options: dict = {}
            if old_id is not None:
                old_entry = reg.async_get(old_id)
                keep = {
                    "area_id": _area_id(hass, old_entry),
                    "name": old_entry.name,
                    "icon": old_entry.icon,
                    "aliases": set(old_entry.aliases) or None,
                    "labels": set(old_entry.labels) or None,
                    "disabled_by": (
                        er.RegistryEntryDisabler.USER
                        if old_entry.disabled_by is er.RegistryEntryDisabler.USER
                        else None
                    ),
                    "hidden_by": (
                        er.RegistryEntryHider.USER if old_entry.hidden_by is er.RegistryEntryHider.USER else None
                    ),
                }
                old_options = {k: dict(v) for k, v in old_entry.options.items()}
                if _needs_name(device):
                    # Homegear has no names: the serial is no name, the predecessor knows better.
                    name = _predecessor_name(device, old_entry)
                    if name is not None:
                        device.name = name
                        names[device.serial] = name
                _LOGGER.info(
                    "Taking over %s (%s) as %s_%s", old_id, old_entry.platform, device.serial, spec.key
                )
                target = old_id
                reg.async_remove(old_id)
            elif reg.async_get(target) is not None:
                _LOGGER.warning("%s is owned by another integration, eq3_max gets a suffix", target)
            new = reg.async_get_or_create(
                spec.domain, DOMAIN, uid, suggested_object_id=_object_id(target), config_entry=entry
            )
            changes = {k: v for k, v in keep.items() if v is not None}
            if changes:
                reg.async_update_entity(new.entity_id, **changes)
            for domain_key, value in old_options.items():
                reg.async_update_entity_options(new.entity_id, domain_key, value)
    if names:
        _LOGGER.info("Device names taken from predecessors: %s", names)
        _persist_names(hass, entry, names)
