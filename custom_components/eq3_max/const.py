"""Constants for eq3_max."""

from __future__ import annotations

DOMAIN = "eq3_max"
CONF_PORT = "port"
CONF_HOST = "host"
CONF_CONNECTION = "connection"
CONNECTION_USB = "usb"
CONNECTION_NETWORK = "network"
DEFAULT_NETWORK_PORT = 2323
CONF_ADDRESS = "address"
CONF_DEVICES = "devices"
CONF_BRAKE = "brake"
# More radio modules (same central address): list of {"id", "name", connection keys}.
CONF_RADIOS = "radios"
CONF_NAME = "name"
# Number of the next extra module id (ids are never reused).
CONF_RADIO_NEXT = "radio_next"
MAIN_RADIO_NAME = "Hauptmodul"
CONF_AWAY_TEMPERATURE = "away_temperature"
CONF_AWAY_HOURS = "away_hours"
DEFAULT_AWAY_TEMPERATURE = 18.0
DEFAULT_AWAY_HOURS = 24
MIN_AWAY_HOURS = 1
MAX_AWAY_HOURS = 720
# Options the running hub is built with (with default); only these need a reload.
RELOAD_OPTIONS = {CONF_BRAKE: False}
DEFAULT_ADDRESS = "C0FFEE"
STORAGE_VERSION = 1
# Sidebar panel (frontend_url_path) and what the hub device links to.
PANEL_URL_PATH = "eq3-max"
CONFIGURATION_URL = f"homeassistant://{PANEL_URL_PATH}"
# Any change of any entry (devices, hub, entry loaded/unloaded): the panel refreshes.
SIGNAL_PANEL_UPDATE = f"{DOMAIN}_panel_update"
PLATFORMS = ["climate", "sensor", "binary_sensor", "event", "button", "number", "select"]


def signal_update(entry_id: str) -> str:
    return f"{DOMAIN}_update_{entry_id}"


def signal_button(entry_id: str) -> str:
    return f"{DOMAIN}_button_{entry_id}"
