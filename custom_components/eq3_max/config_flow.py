"""Config flow for eq3_max."""

from __future__ import annotations

import asyncio
import contextlib
import glob
import http.client
import os
import re
import xmlrpc.client
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import selector

from .connection import connection_target, connection_type
from .const import (
    CONF_ADDRESS,
    CONF_AWAY_HOURS,
    CONF_AWAY_TEMPERATURE,
    CONF_BRAKE,
    CONF_CONNECTION,
    CONF_DEVICES,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_RADIO_NEXT,
    CONF_RADIOS,
    CONNECTION_NETWORK,
    CONNECTION_USB,
    DEFAULT_ADDRESS,
    DEFAULT_AWAY_HOURS,
    DEFAULT_AWAY_TEMPERATURE,
    DEFAULT_NETWORK_PORT,
    DOMAIN,
    MAX_AWAY_HOURS,
    MIN_AWAY_HOURS,
)
from .radios import extra_radios, new_radio_id, next_radio_number, radio_identifier, radio_items, radio_names
from .homegear_import import devices_from_export, export_from_homegear, load_export
from .protocol.devices import MaxDevice
from .protocol.messages import MAX_TEMPERATURE, OFF_TEMPERATURE
from .protocol.transport import open_serial, open_tcp

_ADDRESS_RE = re.compile(r"^[0-9A-Fa-f]{6}$")
_COMMAND_STATE = (
    "pending_target", "pending_mode", "pending_until", "command_failed", "pending_config", "config_failed",
    "pending_links",
)
# Learnt at runtime and kept in the store, not part of the imported snapshot.
_RUNTIME_STATE = (*_COMMAND_STATE, "last_comfort", "rssi_by_radio")


def entry_item(device: MaxDevice) -> dict[str, Any]:
    """Identity plus the imported state snapshot, without command state."""
    data = device.to_dict()
    for key in _RUNTIME_STATE:
        data.pop(key, None)
    # An imported device starts on the main module (the default).
    if not data.get("radio"):
        data.pop("radio", None)
    return data


def list_serial_ports() -> dict[str, str]:
    return {p: f"{p} -> {os.path.realpath(p)}" for p in sorted(glob.glob("/dev/serial/by-path/*"))}


async def _probe(opening, *, attempts: int, timeout: float) -> bool:
    """True if culfw answers "V" with "V ..." (other lines before the answer are skipped)."""
    try:
        reader, writer = await opening
    except (OSError, TimeoutError, ValueError, UnicodeError):
        # UnicodeError/ValueError: unusable host name (e.g. "a..b").
        return False
    loop = asyncio.get_running_loop()
    try:
        for _ in range(attempts):
            writer.write(b"V\n")
            await writer.drain()
            deadline = loop.time() + timeout
            while (remaining := deadline - loop.time()) > 0:
                try:
                    raw = await asyncio.wait_for(reader.readline(), remaining)
                except TimeoutError:
                    break
                if not raw:
                    return False
                if raw.decode(errors="replace").strip().startswith("V "):
                    return True
        return False
    except OSError:
        return False
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def probe_cul(port: str) -> bool:
    return await _probe(open_serial(port), attempts=3, timeout=3)


async def probe_network(host: str, port: int, *, timeout: float = 5.0) -> bool:
    return await _probe(open_tcp(host, port), attempts=1, timeout=timeout)


def _usb_schema(ports: dict[str, str], default: str | None = None) -> vol.Schema:
    field = vol.In(ports) if ports else str
    key = vol.Required(CONF_PORT) if default is None else vol.Required(CONF_PORT, default=default)
    return vol.Schema({key: field})


def valid_host(host: str) -> bool:
    """Bare host name or IP address: not empty, no whitespace, no URL scheme or path."""
    return bool(host) and not any(ch.isspace() for ch in host) and "://" not in host and "/" not in host


def valid_port_path(port: str) -> bool:
    """Free-text serial port (no by-path entries found) must be a device path."""
    return port.startswith("/dev/")


def _network_schema(host: str = "", port: int = DEFAULT_NETWORK_PORT) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=host): str,
            vol.Required(CONF_PORT, default=port): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }
    )


class _TimeoutTransport(xmlrpc.client.Transport):
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = 10
        return conn


def read_homegear(host: str, port: int) -> list[MaxDevice]:
    proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}", transport=_TimeoutTransport())
    return devices_from_export(export_from_homegear(proxy))


class MaxCulConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        # Connection part of the entry data: connection type plus port path or host/port.
        self._connection: dict[str, Any] | None = None
        self._address: str | None = None
        self._devices: list[MaxDevice] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=[CONNECTION_USB, CONNECTION_NETWORK])

    async def async_step_usb(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            if not valid_port_path(port):
                errors["base"] = "invalid_port"
            elif await probe_cul(port):
                self._connection = {CONF_CONNECTION: CONNECTION_USB, CONF_PORT: port}
                return await self.async_step_address()
            else:
                errors["base"] = "cannot_connect"
        ports = await self.hass.async_add_executor_job(list_serial_ports)
        return self.async_show_form(step_id="usb", data_schema=_usb_schema(ports), errors=errors)

    async def async_step_network(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), int(user_input[CONF_PORT])
            if not valid_host(host):
                errors["base"] = "invalid_host"
            elif await probe_network(host, port):
                self._connection = {CONF_CONNECTION: CONNECTION_NETWORK, CONF_HOST: host, CONF_PORT: port}
                return await self.async_step_address()
            else:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="network", data_schema=_network_schema(), errors=errors)

    async def async_step_address(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            value = user_input[CONF_ADDRESS].strip()
            if _ADDRESS_RE.match(value):
                self._address = value.upper()
                await self.async_set_unique_id(self._address)
                self._abort_if_unique_id_configured()
                return await self.async_step_source()
            errors["base"] = "invalid_address"
        schema = vol.Schema({vol.Required(CONF_ADDRESS, default=DEFAULT_ADDRESS): str})
        return self.async_show_form(step_id="address", data_schema=schema, errors=errors)

    async def async_step_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            source = user_input["source"]
            if source == "json":
                return await self.async_step_json()
            if source == "homegear":
                return await self.async_step_homegear()
            return self._create()
        schema = vol.Schema({vol.Required("source", default="json"): vol.In({"json": "JSON", "homegear": "Homegear", "none": "-"})})
        return self.async_show_form(step_id="source", data_schema=schema)

    async def async_step_json(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await self.hass.async_add_executor_job(load_export, user_input["path"])
                self._devices = devices_from_export(data)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                errors["base"] = "cannot_read"
            else:
                return await self.async_step_confirm()
        schema = vol.Schema({vol.Required("path", default="/config/eq3_max_export.json"): str})
        return self.async_show_form(step_id="json", data_schema=schema, errors=errors)

    async def async_step_homegear(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._devices = await self.hass.async_add_executor_job(read_homegear, user_input["host"], user_input["port"])
            except (OSError, xmlrpc.client.Error, http.client.HTTPException):
                errors["base"] = "homegear_unreachable"
            else:
                return await self.async_step_confirm()
        schema = vol.Schema({vol.Required("host"): str, vol.Required("port", default=2001): int})
        return self.async_show_form(step_id="homegear", data_schema=schema, errors=errors)

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self._create()
        listing = "\n".join(f"- {d.serial} ({d.device_type.name}, {d.address:06X})" for d in self._devices)
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"count": str(len(self._devices)), "devices": listing},
        )

    def _create(self) -> ConfigFlowResult:
        assert self._connection is not None and self._address is not None
        return self.async_create_entry(
            title=f"eQ-3 MAX! {self._address}",
            data={**self._connection, CONF_ADDRESS: self._address, CONF_DEVICES: [entry_item(d) for d in self._devices]},
            # New entries keep the 1 % duty cycle (36 s per hour) from the start; existing
            # entries without the option keep running unbraked.
            options={CONF_BRAKE: True},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> MaxCulOptionsFlow:
        return MaxCulOptionsFlow()


class MaxCulOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=["settings", "connection", "radios"])

    # --- further radio modules (same central address) ---

    async def async_step_radios(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        options = ["radio_add_usb", "radio_add_network"]
        if extra_radios(self.config_entry.data):
            options.append("radio_remove")
        return self.async_show_menu(step_id="radios", menu_options=options)

    def _radio_name_error(self, name: str) -> str | None:
        if not name:
            return "name_missing"
        if name in radio_names(self.config_entry.data).values():
            return "name_taken"
        return None

    def _target_in_use(self, connection: dict[str, Any]) -> bool:
        target = connection_target(connection)
        return any(connection_target(item) == target for item in radio_items(self.config_entry.data))

    async def async_step_radio_add_usb(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        ports = await self.hass.async_add_executor_job(list_serial_ports)
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            port = user_input[CONF_PORT].strip()
            connection = {CONF_CONNECTION: CONNECTION_USB, CONF_PORT: port}
            if error := self._radio_name_error(name):
                errors["base"] = error
            elif not valid_port_path(port):
                errors["base"] = "invalid_port"
            elif self._target_in_use(connection):
                errors["base"] = "radio_in_use"
            elif await probe_cul(port):
                return self._add_radio(name, connection)
            else:
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required(CONF_NAME): str}).extend(_usb_schema(ports).schema)
        return self.async_show_form(step_id="radio_add_usb", data_schema=schema, errors=errors)

    async def async_step_radio_add_network(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            host, port = user_input[CONF_HOST].strip(), int(user_input[CONF_PORT])
            connection = {CONF_CONNECTION: CONNECTION_NETWORK, CONF_HOST: host, CONF_PORT: port}
            if error := self._radio_name_error(name):
                errors["base"] = error
            elif not valid_host(host):
                errors["base"] = "invalid_host"
            elif self._target_in_use(connection):
                errors["base"] = "radio_in_use"
            elif await probe_network(host, port):
                return self._add_radio(name, connection)
            else:
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required(CONF_NAME): str}).extend(_network_schema().schema)
        return self.async_show_form(step_id="radio_add_network", data_schema=schema, errors=errors)

    def _add_radio(self, name: str, connection: dict[str, Any]) -> ConfigFlowResult:
        entry = self.config_entry
        radio_id, next_number = new_radio_id(entry.data)
        item = {"id": radio_id, CONF_NAME: name, **connection}
        data = {**entry.data, CONF_RADIOS: [*extra_radios(entry.data), item], CONF_RADIO_NEXT: next_number}
        self.hass.config_entries.async_update_entry(entry, data=data)
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data=dict(entry.options))

    async def async_step_radio_remove(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        extras = extra_radios(entry.data)
        if not extras:
            return self.async_abort(reason="no_extra_radios")
        if user_input is not None:
            radio = user_input["radio"]
            # The running hub first: a telegram before the reload must not write the
            # removed module back into the entry.
            coordinator = getattr(entry, "runtime_data", None)
            hub = getattr(coordinator, "hub", None)
            if hub is not None:
                for dev in list(hub.devices.values()):
                    dev.rssi_by_radio.pop(radio, None)
                    if dev.radio == radio:
                        coordinator.async_set_radio(dev.address, "")
            # Its devices go back to the main module; the registry device goes.
            devices = [
                {**item, "radio": ""} if item.get("radio") == radio else item for item in entry.data[CONF_DEVICES]
            ]
            data = {
                **entry.data,
                CONF_DEVICES: devices,
                CONF_RADIOS: [item for item in extras if item["id"] != radio],
                # Keep the removed id used: stored state may still name it.
                CONF_RADIO_NEXT: next_radio_number(entry.data, radio),
            }
            self.hass.config_entries.async_update_entry(entry, data=data)
            for kind in ("port_lost", "stick_deaf"):
                ir.async_delete_issue(self.hass, DOMAIN, f"{kind}_{radio}")
            dev_reg = dr.async_get(self.hass)
            identifier = (DOMAIN, radio_identifier(entry.data[CONF_ADDRESS], radio))
            for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
                if identifier in device.identifiers:
                    dev_reg.async_remove_device(device.id)
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data=dict(entry.options))
        choices = {item["id"]: f"{item[CONF_NAME]} ({connection_target(item)})" for item in extras}
        return self.async_show_form(
            step_id="radio_remove", data_schema=vol.Schema({vol.Required("radio"): vol.In(choices)})
        )

    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="connection", menu_options=["connection_usb", "connection_network"])

    async def async_step_connection_usb(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            port = user_input[CONF_PORT].strip()
            connection = {CONF_CONNECTION: CONNECTION_USB, CONF_PORT: port}
            if not valid_port_path(port):
                errors["base"] = "invalid_port"
            elif self._is_current(connection) or await probe_cul(port):
                return self._apply_connection(connection)
            else:
                errors["base"] = "cannot_connect"
        data = self.config_entry.data
        current = data[CONF_PORT] if connection_type(data) == CONNECTION_USB else None
        ports = await self.hass.async_add_executor_job(list_serial_ports)
        if current is not None and ports and current not in ports:
            current = None
        return self.async_show_form(step_id="connection_usb", data_schema=_usb_schema(ports, current), errors=errors)

    async def async_step_connection_network(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host, port = user_input[CONF_HOST].strip(), int(user_input[CONF_PORT])
            connection = {CONF_CONNECTION: CONNECTION_NETWORK, CONF_HOST: host, CONF_PORT: port}
            if not valid_host(host):
                errors["base"] = "invalid_host"
            elif self._is_current(connection) or await probe_network(host, port):
                return self._apply_connection(connection)
            else:
                errors["base"] = "cannot_connect"
        data = self.config_entry.data
        if connection_type(data) == CONNECTION_NETWORK:
            schema = _network_schema(data[CONF_HOST], int(data[CONF_PORT]))
        else:
            schema = _network_schema()
        return self.async_show_form(step_id="connection_network", data_schema=schema, errors=errors)

    def _is_current(self, connection: dict[str, Any]) -> bool:
        """The target the running hub uses: it holds the port, so it cannot be probed."""
        data = self.config_entry.data
        return (connection_type(connection), connection_target(connection)) == (
            connection_type(data), connection_target(data),
        )

    def _apply_connection(self, connection: dict[str, Any]) -> ConfigFlowResult:
        """Write the connection into the entry data; reload only if the target changed.

        The update listener ignores data changes, so the reload is scheduled here.
        """
        entry = self.config_entry
        old = (connection_type(entry.data), connection_target(entry.data))
        data = {key: value for key, value in entry.data.items() if key not in (CONF_CONNECTION, CONF_HOST, CONF_PORT)}
        data.update(connection)
        self.hass.config_entries.async_update_entry(entry, data=data)
        if (connection_type(data), connection_target(data)) != old:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data=dict(entry.options))

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            data = dict(user_input)
            data[CONF_AWAY_TEMPERATURE] = float(data[CONF_AWAY_TEMPERATURE])
            data[CONF_AWAY_HOURS] = int(data[CONF_AWAY_HOURS])
            return self.async_create_entry(data=data)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_BRAKE, default=options.get(CONF_BRAKE, False)): bool,
                vol.Required(
                    CONF_AWAY_TEMPERATURE, default=options.get(CONF_AWAY_TEMPERATURE, DEFAULT_AWAY_TEMPERATURE)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=OFF_TEMPERATURE, max=MAX_TEMPERATURE, step=0.5,
                        unit_of_measurement="\u00b0C", mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_AWAY_HOURS, default=options.get(CONF_AWAY_HOURS, DEFAULT_AWAY_HOURS)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=MIN_AWAY_HOURS, max=MAX_AWAY_HOURS, step=1,
                        unit_of_measurement="h", mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)
