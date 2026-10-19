"""Sidebar panel "eQ-3 MAX!": static module and panel registration.

One panel per HA instance: registered with the first loaded entry, removed when
the last one unloads. The static path cannot be unregistered and stays.

Manifest: http and websocket_api are dependencies (static path, commands);
frontend and panel_custom only after_dependencies (JSON has no comments, so
the reason is noted here). Registering a panel only writes hass.data and needs
no set-up frontend; a hard dependency would make every setup (and the tests,
which lack the hass_frontend package) set up the whole frontend.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.loader import async_get_integration

from .const import DOMAIN, PANEL_URL_PATH, SIGNAL_PANEL_UPDATE

__all__ = ["PANEL_URL_PATH", "async_register_panel", "async_unregister_panel"]

FRONTEND_DIR = Path(__file__).parent / "frontend"
MODULE_FILE = "eq3-max-panel.js"
STATIC_URL = f"/{DOMAIN}_static"
WEBCOMPONENT = "eq3-max-panel"
DATA_PANEL = f"{DOMAIN}_panel"


def _module_hash() -> str:
    return hashlib.sha256((FRONTEND_DIR / MODULE_FILE).read_bytes()).hexdigest()[:8]


async def async_register_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data.setdefault(
        DATA_PANEL, {"entries": set(), "static": False, "registered": False, "lock": asyncio.Lock()}
    )
    async with data["lock"]:
        if not data["registered"]:
            await _async_register(hass, data)
        # Counted only once the panel exists: a failed setup must not keep it alive.
        data["entries"].add(entry.entry_id)
    async_dispatcher_send(hass, SIGNAL_PANEL_UPDATE)


async def _async_register(hass: HomeAssistant, data: dict) -> None:
    if not data["static"]:
        # The module URL carries a content hash: long caching is safe.
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=True)]
        )
        data["static"] = True
    version = (await async_get_integration(hass, DOMAIN)).version
    # Version plus content hash: browsers load a changed module right away.
    digest = await hass.async_add_executor_job(_module_hash)
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title="eQ-3 MAX!",
        sidebar_icon="mdi:radiator",
        module_url=f"{STATIC_URL}/{MODULE_FILE}?v={version}-{digest}",
        require_admin=True,
    )
    data["registered"] = True


@callback
def async_unregister_panel(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data.get(DATA_PANEL)
    if data is None:
        return
    data["entries"].discard(entry.entry_id)
    async_dispatcher_send(hass, SIGNAL_PANEL_UPDATE)
    if data["entries"] or not data["registered"]:
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    data["registered"] = False
