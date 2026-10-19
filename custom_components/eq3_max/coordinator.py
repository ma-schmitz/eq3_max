"""Bridge between MaxHub and Home Assistant."""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .connection import connection_target, connection_type, hub_connection
from .const import (
    CONF_ADDRESS,
    CONF_BRAKE,
    CONF_DEVICES,
    CONFIGURATION_URL,
    CONNECTION_NETWORK,
    DOMAIN,
    SIGNAL_PANEL_UPDATE,
    STORAGE_VERSION,
    signal_button,
    signal_update,
)
from .protocol.devices import CONFIG_ENTRY_KEYS, IDENTITY_KEYS, MaxDevice
from .protocol.hub import MAIN_RADIO, MaxHub, RadioSpec
from .radios import extra_radios, radio_identifier, radio_items, radio_names

_LOGGER = logging.getLogger(__name__)
_SEVERITY = {"port_lost": ir.IssueSeverity.ERROR, "stick_deaf": ir.IssueSeverity.ERROR}
HUB_REFRESH = timedelta(seconds=60)


def issue_id(kind: str, radio: str) -> str:
    """Repair issue per module; the main module keeps the plain id."""
    return kind if radio == MAIN_RADIO else f"{kind}_{radio}"


@callback
def async_forget_device(hass: HomeAssistant, entry: ConfigEntry, serial: str) -> bool:
    """Drop a device from the entry (no radio); a loaded entry reloads without it."""
    items = entry.data[CONF_DEVICES]
    remaining = [item for item in items if item.get("serial") != serial]
    if len(remaining) == len(items):
        return False
    hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_DEVICES: remaining})
    if entry.state is ConfigEntryState.LOADED:
        hass.config_entries.async_schedule_reload(entry.entry_id)
    return True


class MaxCulCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.address_hex: str = entry.data[CONF_ADDRESS]
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.devices.{entry.entry_id}")
        self.hub: MaxHub | None = None
        # Wall-clock time of the last "stick_deaf" per module ("" = main).
        self._deaf_since: dict[str, float] = {}
        # Options the running hub was built with; the update listener reloads only on change.
        self.options: dict[str, Any] = dict(entry.options)
        self._unsub_refresh: Callable[[], None] | None = None
        self._hub_device_id: str | None = None
        # Device registry ids of the radio modules ("" = main).
        self._radio_device_ids: dict[str, str] = {}

    def identity_devices(self) -> list[MaxDevice]:
        return [MaxDevice.from_dict(d) for d in self.entry.data[CONF_DEVICES]]

    async def async_start(self) -> None:
        stored = ((await self._store.async_load()) or {}).get("devices", {})
        devices = []
        for item in self.entry.data[CONF_DEVICES]:
            # Entry item = identity + configuration + imported snapshot; stored state is
            # newer than the snapshot, identity and configuration from the entry win
            # (configuration per value: old entries have none or only a legacy field).
            identity = {key: item[key] for key in IDENTITY_KEYS if key in item and key not in CONFIG_ENTRY_KEYS}
            state = stored.get(str(item["address"]), {})
            try:
                dev = MaxDevice.from_dict({**item, **state, **identity})
                entry_dev = MaxDevice.from_dict(item)
                dev.config.update(entry_dev.config)
                dev.config_source.update(entry_dev.config_source)
            except (KeyError, ValueError, TypeError, AttributeError):
                _LOGGER.warning("Ignoring unreadable stored state for device %s", item.get("serial"))
                dev = MaxDevice.from_dict(item)
            # Old entries carry no configuration: assume factory settings.
            dev.ensure_config_defaults()
            # RSSI of modules removed meanwhile.
            known = {item["id"] for item in radio_items(self.entry.data)}
            dev.rssi_by_radio = {k: v for k, v in dev.rssi_by_radio.items() if k in known}
            devices.append(dev)
        target, opener = hub_connection(self.entry.data)
        # USB passes no opener: the transport keeps its serial default.
        connection_kwargs = {} if opener is None else {"open_connection": opener}
        radios = []
        for item in extra_radios(self.entry.data):
            radio_target, radio_opener = hub_connection(item)
            radios.append(RadioSpec(item["id"], radio_target, radio_opener))
        self.hub = MaxHub(
            target,
            int(self.address_hex, 16),
            devices,
            on_update=self._on_update,
            on_button=self._on_button,
            on_device_added=self._on_device_added,
            on_problem=self._on_problem,
            radios=radios,
            brake=self.entry.options.get(CONF_BRAKE, False),
            # MAX! end times and the time reply follow HA's local time, not the OS zone.
            local_now=lambda: dt_util.now().replace(tzinfo=None),
            **connection_kwargs,
        )
        hub_device = dr.async_get(self.hass).async_get_or_create(
            config_entry_id=self.entry.entry_id,
            identifiers={(DOMAIN, self.address_hex)},
            manufacturer="busware / culfw",
            model="culfw (Netzwerk)" if connection_type(self.entry.data) == CONNECTION_NETWORK else "nanoCUL868",
            name="eQ-3 MAX! Funkmodul",
            configuration_url=CONFIGURATION_URL,
        )
        self._hub_device_id = hub_device.id
        self._radio_device_ids = {MAIN_RADIO: hub_device.id}
        dev_reg = dr.async_get(self.hass)
        for item in extra_radios(self.entry.data):
            radio_device = dev_reg.async_get_or_create(
                config_entry_id=self.entry.entry_id,
                identifiers={(DOMAIN, radio_identifier(self.address_hex, item["id"]))},
                manufacturer="busware / culfw",
                model="culfw (Netzwerk)" if connection_type(item) == CONNECTION_NETWORK else "nanoCUL868",
                name=f"eQ-3 MAX! Funkmodul {item['name']}",
                via_device=(DOMAIN, self.address_hex),
                configuration_url=CONFIGURATION_URL,
            )
            self._radio_device_ids[item["id"]] = radio_device.id
        await self.hub.start()
        # Airtime and queue age without radio traffic; refresh the hub entities.
        self._unsub_refresh = async_track_time_interval(self.hass, self._refresh, HUB_REFRESH)

    @callback
    def async_link_devices(self) -> None:
        """Point every device of the entry at its radio module (via_device_id)."""
        if self._hub_device_id is None:
            return
        dev_reg = dr.async_get(self.hass)
        radio_of = {item["serial"]: item.get("radio", MAIN_RADIO) for item in self.entry.data[CONF_DEVICES] if item.get("serial")}
        # DeviceInfo does not rename existing devices: names from the entry data win
        # unless the user renamed the device.
        names = {
            item["serial"]: item.get("name") for item in self.entry.data[CONF_DEVICES] if item.get("serial")
        }
        radio_device_ids = set(self._radio_device_ids.values())
        for device in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            if device.id in radio_device_ids:
                continue
            changes: dict[str, Any] = {}
            serial = next((ident for domain, ident in device.identifiers if domain == DOMAIN), None)
            via = self._radio_device_ids.get(radio_of.get(serial, MAIN_RADIO), self._hub_device_id)
            if device.via_device_id != via:
                changes["via_device_id"] = via
            name = names.get(serial)
            if name and device.name_by_user is None and device.name != name:
                changes["name"] = name
            if changes:
                dev_reg.async_update_device(device.id, **changes)

    @callback
    def _refresh(self, _now: Any) -> None:
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id), None)
        async_dispatcher_send(self.hass, SIGNAL_PANEL_UPDATE)

    async def async_stop(self) -> None:
        if self._unsub_refresh is not None:
            self._unsub_refresh()
            self._unsub_refresh = None
        if self.hub is not None:
            try:
                await self.hub.stop()
            finally:
                await self._store.async_save(self._data_to_save())

    def _data_to_save(self) -> dict[str, Any]:
        assert self.hub is not None
        return {"devices": {str(a): d.to_dict() for a, d in self.hub.devices.items()}}

    @callback
    def _on_update(self, device: MaxDevice | None) -> None:
        if self.hub is None:
            return
        if device is None:
            for status in self.hub.radio_status():
                if status["connected"]:
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id("port_lost", status["id"]))
        if device is not None:
            # Only a telegram on the deaf module itself clears its issue: the others
            # usually hear the same devices.
            for radio, since in list(self._deaf_since.items()):
                if self.hub.heard_since(radio, since):
                    del self._deaf_since[radio]
                    ir.async_delete_issue(self.hass, DOMAIN, issue_id("stick_deaf", radio))
            self._store.async_delay_save(self._data_to_save, 10)
            self._sync_entry_config(device)
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id), None if device is None else device.address)
        async_dispatcher_send(self.hass, SIGNAL_PANEL_UPDATE)

    @callback
    def _sync_entry_config(self, device: MaxDevice) -> None:
        """Keep the device's configuration (not the pending one) and its acknowledged
        links (not the pending operations) in the entry item."""
        items = self.entry.data[CONF_DEVICES]
        for index, item in enumerate(items):
            if item.get("address") != device.address:
                continue
            updated = dict(item)
            # Contacts and buttons have no configuration.
            if device.config_keys and not all(item.get(key) == getattr(device, key) for key in CONFIG_ENTRY_KEYS):
                updated.update({key: dict(getattr(device, key)) for key in CONFIG_ENTRY_KEYS})
                updated.pop("window_open_temperature", None)
            if device.links or "links" in item:
                updated["links"] = list(device.links)
            # A module removed in the options is gone from the entry before the reload:
            # never write its id back.
            if (device.radio or "radio" in item) and device.radio in radio_names(self.entry.data):
                updated["radio"] = device.radio
            if updated == item:
                return
            new_items = [*items[:index], updated, *items[index + 1 :]]
            self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, CONF_DEVICES: new_items})
            return

    @callback
    def _on_button(self, device: MaxDevice, event_type: str) -> None:
        async_dispatcher_send(self.hass, signal_button(self.entry.entry_id), device.address, event_type)

    @callback
    def _on_device_added(self, device: MaxDevice) -> None:
        # Called by the hub after the PairPong completed, so the reload cannot cut it short.
        devices = [*self.entry.data[CONF_DEVICES], device.identity_dict()]
        self.hass.config_entries.async_update_entry(self.entry, data={**self.entry.data, CONF_DEVICES: devices})
        self.hass.config_entries.async_schedule_reload(self.entry.entry_id)

    @callback
    def async_set_radio(self, address: int, radio: str) -> None:
        """Commands to this device go through another module (no radio traffic)."""
        assert self.hub is not None
        self.hub.set_radio(address, radio)
        dev = self.hub.devices[address]
        self._sync_entry_config(dev)
        via = self._radio_device_ids.get(radio)
        dev_reg = dr.async_get(self.hass)
        for device in dr.async_entries_for_config_entry(dev_reg, self.entry.entry_id):
            if (DOMAIN, dev.serial) in device.identifiers and via is not None and device.via_device_id != via:
                dev_reg.async_update_device(device.id, via_device_id=via)

    @callback
    def _on_problem(self, kind: str, radio: str = MAIN_RADIO) -> None:
        if kind == "stick_deaf":
            self._deaf_since[radio] = time.time()
        item = next((i for i in radio_items(self.entry.data) if i["id"] == radio), radio_items(self.entry.data)[0])
        placeholders = {"target": connection_target(item)} if kind == "port_lost" else None
        ir.async_create_issue(
            self.hass, DOMAIN, issue_id(kind, radio), is_fixable=False,
            severity=_SEVERITY.get(kind, ir.IssueSeverity.WARNING), translation_key=kind,
            translation_placeholders=placeholders,
        )
