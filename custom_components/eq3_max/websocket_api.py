"""WebSocket commands of the panel "eQ-3 MAX!" (all admin only).

eq3_max/overview    hub, devices, areas, links and configuration of every entry
eq3_max/subscribe   event {"type": "update"} after changes (debounced)
eq3_max/link        link two devices (device registry ids)
eq3_max/unlink      remove a link
eq3_max/pair        open pairing for 60 s
eq3_max/set_config  one whole configuration set: one telegram
eq3_max/set_radio   radio module a device's commands go through (nothing on air)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_call_later

from .config_defs import CONFIG_LABELS, SET_KEYS, SET_TITLES, config_meta, validate_config_value
from .connection import connection_target, connection_type
from .const import CONF_ADDRESS, DOMAIN, SIGNAL_PANEL_UPDATE
from .registry_compat import find_device
from .migration import specs_for, unique_id
from .protocol.devices import (
    CONFIG_KINDS,
    LINK_ADD,
    LINK_FAILED,
    LINK_PENDING,
    LINK_REJECTED,
    WEEKDAYS,
    MaxDevice,
)
from .protocol.hub import LINK_ONE_SIDED, plan_link
from .protocol.hub import link_status as hub_link_status
from .protocol.messages import FACTORY_WEEK_PROFILE, DeviceType, FrameError, format_until
from .radios import describe, radio_items, radio_names, renamed
from .errors import failed, invalid, send_ws_error
from .services import (
    async_copy_week_profile,
    async_set_week_profile,
    async_set_time,
    async_set_week_profile_days,
    change_link,
    resolve_max_device,
)

_LOGGER = logging.getLogger(__name__)
PAIRING_SECONDS = 60
# Duty cycle: 1 % of an hour.
AIRTIME_LIMIT_S = 36
DEBOUNCE_S = 0.25
ERR_INVALID = "invalid"
ERR_FAILED = "failed"
TYPE_KEYS = {
    DeviceType.CUBE: "cube",
    DeviceType.HEATING_THERMOSTAT: "heating_thermostat",
    DeviceType.HEATING_THERMOSTAT_PLUS: "heating_thermostat",
    DeviceType.WALL_THERMOSTAT: "wall_thermostat",
    DeviceType.SHUTTER_CONTACT: "shutter_contact",
    DeviceType.PUSH_BUTTON: "push_button",
    DeviceType.PLUG_ADAPTER: "plug_adapter",
}
TYPE_NAMES = {
    DeviceType.CUBE: "Cube",
    DeviceType.HEATING_THERMOSTAT: "Heizk\u00f6rperthermostat",
    DeviceType.HEATING_THERMOSTAT_PLUS: "Heizk\u00f6rperthermostat+",
    DeviceType.WALL_THERMOSTAT: "Wandthermostat",
    DeviceType.SHUTTER_CONTACT: "Fensterkontakt",
    DeviceType.PUSH_BUTTON: "Eco-Taster",
    DeviceType.PLUG_ADAPTER: "Zwischenstecker (noch nicht unterst\u00fctzt)",
}


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    for command in (
        ws_overview, ws_subscribe, ws_link, ws_unlink, ws_pair, ws_set_config, ws_set_group, ws_set_poll, ws_set_radio,
        ws_set_week_profile, ws_copy_week_profile, ws_set_time, ws_rename_radio,
    ):
        websocket_api.async_register_command(hass, command)


# --- overview ---------------------------------------------------------------


def _link_state(state: str) -> str:
    if state == LINK_PENDING:
        return "pending"
    if state == LINK_FAILED:
        return "failed"
    if state == LINK_REJECTED:
        return "rejected"
    if state == LINK_ONE_SIDED:
        return "one_sided"
    return "waiting"


class _Context:
    """Registries and lookups for one overview."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.hub = entry.runtime_data.hub
        self.dev_reg = dr.async_get(hass)
        self.ent_reg = er.async_get(hass)
        self.area_reg = ar.async_get(hass)
        self.by_serial = {d.serial: d for d in self.hub.devices.values()}
        self.radio_names = radio_names(entry.data)

    def device_entry(self, serial: str) -> dr.DeviceEntry | None:
        return find_device(self.dev_reg, self.entry.entry_id, (DOMAIN, serial))

    def device_id(self, serial: str) -> str | None:
        device = self.device_entry(serial)
        return None if device is None else device.id

    def name(self, serial: str) -> str:
        device = self.device_entry(serial)
        if device is not None and device.name_by_user:
            return device.name_by_user
        dev = self.by_serial.get(serial)
        return serial if dev is None else (dev.name or dev.serial)

    def ref(self, serial: str) -> dict[str, Any]:
        return {"serial": serial, "name": self.name(serial), "device_id": self.device_id(serial)}

    def main_entity(self, dev: MaxDevice) -> str | None:
        specs = specs_for(dev)
        if not specs:
            return None
        return self.ent_reg.async_get_entity_id(specs[0].domain, DOMAIN, unique_id(dev.serial, specs[0].key))


def _state(ctx: _Context, dev: MaxDevice, entity_id: str | None) -> dict[str, Any]:
    ha_state = ctx.hass.states.get(entity_id) if entity_id else None
    climate = ha_state is not None and entity_id is not None and entity_id.startswith("climate.")
    return {
        "target": dev.target,
        "measured": dev.measured,
        "mode": None if dev.mode is None else dev.mode.name.lower(),
        "hvac": ha_state.state if climate else None,
        "preset": ha_state.attributes.get("preset_mode") if climate else None,
        "valve": dev.valve,
        "window_open": dev.window_open,
        "battery_low": dev.battery_low,
        "rf_error": dev.rf_error,
        "locked": dev.locked,
        "rssi": dev.rssi,
        "rssi_by_radio": dict(dev.rssi_by_radio),
        "last_seen": dev.last_seen,
        "command_failed": dev.command_failed,
        "config_failed": dev.failed_config_kinds(),
    }


def _links(ctx: _Context, dev: MaxDevice) -> dict[str, Any]:
    status = hub_link_status(ctx.hub.devices, dev)
    pending = []
    for serial, state in status.pending:
        op = dev.link_op(serial)
        other = ctx.by_serial.get(serial)
        if op is None and other is not None:
            op = other.link_op(dev.serial)
        pending.append(
            {**ctx.ref(serial), "state": _link_state(state), "text": state, "op": None if op is None else op["op"]}
        )
    return {"partners": [ctx.ref(serial) for serial in status.partners], "pending": pending}


def _candidates(ctx: _Context, dev: MaxDevice) -> list[dict[str, Any]]:
    """Devices a link with dev would be accepted for (same check as the link service)."""
    result = []
    for other in ctx.hub.devices.values():
        if other is dev:
            continue
        try:
            plan_link(ctx.hub.devices, dev.address, other.address, LINK_ADD)
        except FrameError:
            continue
        result.append(ctx.ref(other.serial))
    return sorted(result, key=lambda item: item["name"].lower())


def _pending_change(dev: MaxDevice, key: str) -> Any:
    """Pending value of a key, only where it differs from the stored one (the whole
    set is pending; the set itself carries that)."""
    value = dev.pending_value(key)
    return None if value is None or value == dev.config.get(key) else value


def _config(dev: MaxDevice) -> list[dict[str, Any]]:
    sets = []
    kinds = [kind for kind in CONFIG_KINDS if any(key in dev.config_keys for key in SET_KEYS[kind])]
    failed = dev.failed_config_kinds()
    for kind in kinds:
        values = [
            {
                **config_meta(key),
                "value": dev.config.get(key),
                "source": dev.config_source.get(key),
                "pending": _pending_change(dev, key),
            }
            for key in SET_KEYS[kind]
            # A wall thermostat uses only the boost duration of the valve set.
            if key in dev.config_keys
        ]
        sets.append(
            {
                "kind": kind,
                "title": SET_TITLES[kind],
                "pending": kind in dev.pending_config,
                "failed": kind in failed,
                "values": values,
            }
        )
    return sets


def _device(ctx: _Context, dev: MaxDevice) -> dict[str, Any]:
    device = ctx.device_entry(dev.serial)
    area_id = None if device is None else device.area_id
    area = None if area_id is None else ctx.area_reg.async_get_area(area_id)
    entity_id = ctx.main_entity(dev)
    links = _links(ctx, dev)
    return {
        "device_id": None if device is None else device.id,
        "serial": dev.serial,
        "address": f"{dev.address:06X}",
        "name": ctx.name(dev.serial),
        "type": TYPE_KEYS.get(dev.device_type, "unknown"),
        "type_name": TYPE_NAMES.get(dev.device_type, "Unbekannt"),
        "firmware": dev.firmware,
        "radio": dev.radio if dev.radio in ctx.radio_names else "",
        "area_id": area_id,
        "area_name": None if area is None else area.name,
        "entity_id": entity_id,
        "sleeper": dev.is_sleeper,
        "pending": bool(
            dev.has_pending or dev.pending_config or dev.pending_links or dev.pending_group is not None
            or dev.week_profile_writing
        ),
        "group": dev.group,
        "pending_group": dev.pending_group,
        "group_failed": dev.group_failed,
        "state": _state(ctx, dev, entity_id),
        "links": links,
        "candidates": _candidates(ctx, dev),
        "config": _config(dev),
        # Measured temperature polling: radiator thermostats only (None = not offered).
        "poll_minutes": dev.poll_minutes if dev.is_heating_thermostat else None,
        "week_profile": dev.week_profile,
        "week_profile_writing": list(dev.week_profile_writing),
        "week_profile_error": dev.week_profile_error,
    }


def _hub(ctx: _Context) -> dict[str, Any]:
    hub = ctx.hub
    data = ctx.entry.data
    hub_device = ctx.device_entry(data[CONF_ADDRESS])
    return {
        "address": data[CONF_ADDRESS],
        "device_id": None if hub_device is None else hub_device.id,
        "connected": hub.connected,
        "any_connected": hub.any_connected,
        "connection": connection_type(data),
        "target": connection_target(data),
        "version": hub.version,
        "airtime": round(hub.airtime_last_hour, 1),
        "airtime_limit": AIRTIME_LIMIT_S,
        "queue": hub.queue_length,
        "pairing_remaining": round(hub.pairing_remaining),
        "pairing_radio": getattr(hub, "pairing_radio", None),
        "radios": _radios(ctx),
    }


def _radios(ctx: _Context) -> list[dict[str, Any]]:
    status = {item["id"]: item for item in ctx.hub.radio_status()}
    result = []
    for item in radio_items(ctx.entry.data):
        st = status.get(item["id"], {})
        result.append(
            {
                "id": item["id"],
                "name": item["name"],
                **describe(item),
                "connected": bool(st.get("connected")),
                "version": st.get("version"),
                "airtime": round(st.get("airtime", 0.0), 1),
                "queue": st.get("queue", 0),
                # A command is held back: by the brake, or the stick refused it (LOVF).
                "waiting_budget": bool(st.get("waiting_budget")),
            }
        )
    return result


def build_overview(hass: HomeAssistant) -> dict[str, Any]:
    entries = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        section: dict[str, Any] = {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "state": entry.state.value,
            "loaded": False,
            "hub": None,
            "devices": [],
        }
        coordinator = getattr(entry, "runtime_data", None) if entry.state is ConfigEntryState.LOADED else None
        if coordinator is not None and coordinator.hub is not None:
            ctx = _Context(hass, entry)
            section["loaded"] = True
            section["hub"] = _hub(ctx)
            section["devices"] = sorted(
                (_device(ctx, dev) for dev in ctx.hub.devices.values()), key=lambda d: d["name"].lower()
            )
        entries.append(section)
    return {"entries": entries, "factory_week_profile": factory_week_profile()}


def factory_week_profile() -> dict[str, list[dict[str, Any]]]:
    """The factory program by weekday name, points as the services take them."""
    return {
        WEEKDAYS[day]: [{"temperature": p.temperature, "until": format_until(p.until)} for p in points]
        for day, points in FACTORY_WEEK_PROFILE.items()
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "eq3_max/overview"})
@callback
def ws_overview(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_result(msg["id"], build_overview(hass))


# --- subscribe --------------------------------------------------------------


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "eq3_max/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    msg_id = msg["id"]
    pending: list[Callable[[], None]] = []

    @callback
    def _send(_now: Any) -> None:
        pending.clear()
        connection.send_message(websocket_api.event_message(msg_id, {"type": "update"}))

    @callback
    def _changed(*_args: Any) -> None:
        # Bursts (one telegram notifies several devices) become one event.
        if not pending:
            pending.append(async_call_later(hass, DEBOUNCE_S, _send))

    unsub_dispatcher = async_dispatcher_connect(hass, SIGNAL_PANEL_UPDATE, _changed)

    @callback
    def _unsubscribe() -> None:
        unsub_dispatcher()
        for cancel in pending:
            cancel()
        pending.clear()

    connection.subscriptions[msg_id] = _unsubscribe
    connection.send_result(msg_id)


# --- actions ----------------------------------------------------------------


def _error(connection: websocket_api.ActiveConnection, msg: dict[str, Any], err: Exception) -> None:
    """A wrong request: the panel shows the translated text (translation key included)."""
    send_ws_error(connection, msg["id"], ERR_INVALID, err)


def _failure(connection: websocket_api.ActiveConnection, msg: dict[str, Any], err: Exception) -> None:
    """The radio or the device did not take it."""
    send_ws_error(connection, msg["id"], ERR_FAILED, err)


_LINK_SCHEMA = {vol.Required("device_id"): str, vol.Required("partner_device_id"): str}


def _ws_change_link(hass: HomeAssistant, connection, msg: dict[str, Any], *, unlink: bool) -> None:
    try:
        change_link(
            hass, msg["device_id"], msg["partner_device_id"], unlink=unlink, force=bool(msg.get("force")) and unlink
        )
    except HomeAssistantError as err:
        _error(connection, msg, err)
        return
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "eq3_max/link", **_LINK_SCHEMA})
@callback
def ws_link(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    _ws_change_link(hass, connection, msg, unlink=False)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "eq3_max/unlink", **_LINK_SCHEMA, vol.Optional("force", default=False): bool}
)
@callback
def ws_unlink(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    _ws_change_link(hass, connection, msg, unlink=True)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "eq3_max/pair", vol.Required("entry_id"): str, vol.Optional("radio"): str}
)
@callback
def ws_pair(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Open pairing for 60 s. With `radio` only that module answers new devices and they
    are assigned to it; without, whichever module hears them first."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        _error(connection, msg, invalid("hub_not_loaded"))
        return
    hub = entry.runtime_data.hub
    radio = msg.get("radio")
    if radio is not None and radio not in radio_names(entry.data):
        _error(connection, msg, invalid("radio_unknown", name=radio))
        return
    # Without a module pairing listens on every module: one connected module is enough.
    if not (hub.radio_is_connected(radio) if radio is not None else hub.any_connected):
        _failure(connection, msg, failed("not_connected"))
        return
    hub.open_pairing(PAIRING_SECONDS, radio=radio)
    connection.send_result(msg["id"], {"seconds": PAIRING_SECONDS})
    async_dispatcher_send(hass, SIGNAL_PANEL_UPDATE)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/rename_radio",
        vol.Required("entry_id"): str,
        vol.Required("radio"): str,
        vol.Required("name"): str,
    }
)
@callback
def ws_rename_radio(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """A name of its own for a module, the main one included (same as the options step);
    the integration reloads."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.state is not ConfigEntryState.LOADED:
        _error(connection, msg, invalid("hub_not_loaded"))
        return
    try:
        data = renamed(entry.data, msg["radio"], msg["name"])
    except ValueError as err:
        key = str(err)
        _error(connection, msg, invalid(key, name=msg["radio"]) if key == "radio_unknown" else invalid(f"radio_{key}"))
        return
    hass.config_entries.async_update_entry(entry, data=data)
    hass.config_entries.async_schedule_reload(entry.entry_id)
    connection.send_result(msg["id"], {"name": msg["name"].strip()})


def _validated_set(dev: MaxDevice, kind: str, values: dict[str, Any]) -> dict[str, Any]:
    """Values on the integration's grid; translated ServiceValidationError otherwise."""
    if not dev.config_keys:
        raise invalid("config_none")
    if not any(key in dev.config_keys for key in SET_KEYS[kind]):
        raise invalid("config_valve_only_radiator")
    if not values:
        raise invalid("config_no_values")
    result = {}
    for key, value in values.items():
        if key not in CONFIG_LABELS:
            raise invalid("config_key_unknown", key=key)
        if key not in SET_KEYS[kind]:
            raise invalid("config_key_wrong_set", key=key)
        if key not in dev.config_keys:
            raise invalid("config_key_not_on_device", key=key)
        result[key] = validate_config_value(key, value)
    return result


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/set_config",
        vol.Required("device_id"): str,
        vol.Required("kind"): vol.In(list(CONFIG_KINDS)),
        vol.Required("values"): dict,
    }
)
@callback
def ws_set_config(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        entry, dev = resolve_max_device(hass, msg["device_id"], "hub_no_config")
        values = _validated_set(dev, msg["kind"], msg["values"])
        factory_keys = entry.runtime_data.hub.set_config_set(dev.address, msg["kind"], values)
    except HomeAssistantError as err:
        _error(connection, msg, err)
        return
    except FrameError as err:
        # Values passed the table check; the protocol's (English) detail is for the log.
        _LOGGER.debug("set_config %s rejected by the protocol: %s", msg["kind"], err)
        _error(connection, msg, invalid("invalid_value"))
        return
    except ValueError as err:
        _error(connection, msg, err)
        return
    connection.send_result(msg["id"], {"factory_keys": factory_keys})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/set_poll",
        vol.Required("device_id"): str,
        vol.Required("minutes"): vol.In([0, 15, 30, 60, 120, 240]),
    }
)
@callback
def ws_set_poll(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        entry, dev = resolve_max_device(hass, msg["device_id"], "hub_no_config")
        if not dev.is_heating_thermostat:
            raise invalid("invalid_value")
        entry.runtime_data.hub.set_poll(dev.address, msg["minutes"])
    except HomeAssistantError as err:
        _error(connection, msg, err)
        return
    except FrameError:
        _error(connection, msg, invalid("invalid_value"))
        return
    connection.send_result(msg["id"], {"minutes": msg["minutes"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/set_group",
        vol.Required("device_id"): str,
        # 1..255 = this id, 0 = remove; "room": one free (or common) id for the whole room.
        vol.Optional("group"): vol.All(int, vol.Range(min=0, max=255)),
        vol.Optional("room", default=False): bool,
    }
)
@callback
def ws_set_group(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        entry, dev = resolve_max_device(hass, msg["device_id"], "hub_no_group")
        if not dev.is_climate:
            raise invalid("group_not_on_device")
        hub = entry.runtime_data.hub
        if msg["room"]:
            devices = hub.set_room_group(dev.address)
        elif "group" in msg:
            hub.set_group(dev.address, msg["group"])
            devices = [dev]
        else:
            raise invalid("invalid_value")
    except HomeAssistantError as err:
        _error(connection, msg, err)
        return
    except FrameError as err:
        _LOGGER.debug("set_group rejected: %s", err)
        _error(connection, msg, invalid("group_none_free"))
        return
    connection.send_result(
        msg["id"],
        {"devices": [d.serial for d in devices], "group": devices[0].pending_group if devices[0].pending_group is not None else devices[0].group},
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "eq3_max/set_radio", vol.Required("device_id"): str, vol.Required("radio"): str}
)
@callback
def ws_set_radio(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    try:
        entry, dev = resolve_max_device(hass, msg["device_id"], "hub_no_radio")
        if msg["radio"] not in radio_names(entry.data):
            raise invalid("radio_unknown", name=msg["radio"])
        entry.runtime_data.async_set_radio(dev.address, msg["radio"])
    except (HomeAssistantError, ValueError, FrameError) as err:
        _error(connection, msg, err)
        return
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/set_week_profile",
        vol.Required("device_id"): vol.All(cv.ensure_list, [str]),
        # Either weekday + profile (one profile for these days) or days (a profile per
        # weekday name); always one write per thermostat.
        vol.Optional("weekday"): vol.All(cv.ensure_list, [str]),
        vol.Optional("profile"): [dict],
        vol.Optional("days"): {str: [dict]},
    }
)
@websocket_api.async_response
async def ws_set_week_profile(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Write a week profile; waits for the acknowledgements (seconds, with an empty
    airtime budget many minutes). The write goes on when the page is closed; the overview
    carries its progress (week_profile_writing, week_profile_error)."""
    try:
        if "days" in msg:
            if "weekday" in msg or "profile" in msg:
                raise invalid("week_profile_request_invalid")
            devices = await async_set_week_profile_days(hass, msg["device_id"], msg["days"])
        elif "weekday" in msg and "profile" in msg:
            devices = await async_set_week_profile(hass, msg["device_id"], msg["weekday"], msg["profile"])
        else:
            raise invalid("week_profile_request_invalid")
    except (ServiceValidationError, ValueError) as err:
        _error(connection, msg, err)
        return
    except HomeAssistantError as err:
        _failure(connection, msg, err)
        return
    connection.send_result(msg["id"], {"week_profile": devices[0].week_profile if devices else {}})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "eq3_max/copy_week_profile",
        vol.Required("device_id"): str,
        vol.Required("target_device_id"): vol.All(cv.ensure_list, [str]),
    }
)
@websocket_api.async_response
async def ws_copy_week_profile(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    try:
        targets = await async_copy_week_profile(hass, msg["device_id"], msg["target_device_id"])
    except (ServiceValidationError, ValueError) as err:
        _error(connection, msg, err)
        return
    except HomeAssistantError as err:
        _failure(connection, msg, err)
        return
    connection.send_result(msg["id"], {"targets": [t.serial for t in targets]})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "eq3_max/set_time", vol.Required("device_id"): str})
@websocket_api.async_response
async def ws_set_time(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Set a thermostat's clock now; waits for its acknowledgement (seconds)."""
    try:
        await async_set_time(hass, [msg["device_id"]])
    except (ServiceValidationError, ValueError) as err:
        _error(connection, msg, err)
        return
    except HomeAssistantError as err:
        _failure(connection, msg, err)
        return
    connection.send_result(msg["id"])
