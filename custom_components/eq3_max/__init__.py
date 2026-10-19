"""eQ-3 MAX! integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import PLATFORMS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.device_registry import DeviceEntry

ACTIVE_PLATFORMS = PLATFORMS


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    from .services import async_setup_services  # noqa: PLC0415
    from .websocket_api import async_register_commands  # noqa: PLC0415

    async_setup_services(hass)
    async_register_commands(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady  # noqa: PLC0415
    from homeassistant.helpers import issue_registry as ir  # noqa: PLC0415

    from .const import DOMAIN  # noqa: PLC0415
    from .coordinator import MaxCulCoordinator  # noqa: PLC0415
    from .migration import BLOCKING_INTEGRATIONS, MigrationBlocked, async_migrate_entities  # noqa: PLC0415
    from .panel import async_register_panel  # noqa: PLC0415

    coordinator = MaxCulCoordinator(hass, entry)
    try:
        async_migrate_entities(hass, entry, coordinator.identity_devices())
    except MigrationBlocked as err:
        issue_id = f"{err.integration}_active"
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=issue_id,
        )
        raise ConfigEntryError(str(err)) from err
    for integration in BLOCKING_INTEGRATIONS:
        ir.async_delete_issue(hass, DOMAIN, f"{integration}_active")
    try:
        await coordinator.async_start()
    except (OSError, ConnectionError) as err:
        raise ConfigEntryNotReady(f"CUL stick not ready: {err}") from err
    try:
        entry.runtime_data = coordinator
        entry.async_on_unload(entry.add_update_listener(_async_reload))
        await hass.config_entries.async_forward_entry_setups(entry, ACTIVE_PLATFORMS)
        coordinator.async_link_devices()
        await async_register_panel(hass, entry)
    except Exception:
        await coordinator.async_stop()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .panel import async_unregister_panel  # noqa: PLC0415

    ok = await hass.config_entries.async_unload_platforms(entry, ACTIVE_PLATFORMS)
    if ok:
        async_unregister_panel(hass, entry)
        await entry.runtime_data.async_stop()
    return ok


async def async_remove_config_entry_device(hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry) -> bool:
    """Device page "delete": forget the device (no radio); never a radio module."""
    from .const import CONF_ADDRESS, DOMAIN  # noqa: PLC0415
    from .coordinator import async_forget_device  # noqa: PLC0415

    serials = {value for domain, value in device_entry.identifiers if domain == DOMAIN}
    # Radio modules (main: the address, extra: "address:id") go via the options.
    if any(serial == entry.data[CONF_ADDRESS] or serial.startswith(f"{entry.data[CONF_ADDRESS]}:") for serial in serials):
        return False
    for serial in serials:
        async_forget_device(hass, entry, serial)
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    # Data changes (new device) schedule their own reload from the coordinator once
    # the PairPong is off the air; here only changed options the hub is built with
    # trigger a reload (away values are read at call time).
    from .const import RELOAD_OPTIONS  # noqa: PLC0415

    old = entry.runtime_data.options
    if all(entry.options.get(key, default) == old.get(key, default) for key, default in RELOAD_OPTIONS.items()):
        return
    await hass.config_entries.async_reload(entry.entry_id)
