"""Thermostat card: shipped with the integration and entered as a dashboard resource.

The card (frontend/eq3-max-thermostat-card.js) is served from the integration's static
path (panel.py). With dashboard resources kept in storage (the default) it is entered
there, its URL carrying version and content hash, and updated in place on a new version.
With resources kept in YAML nothing can be entered: the module is then handed to the
frontend as an extra module, which loads it on every page.

A copy installed on its own (earlier: an own HACS repository) wins: two modules defining
the same element would leave the older one in place by chance. Ours is then not entered,
and a repair says so.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).parent / "frontend"
CARD_FILE = "eq3-max-thermostat-card.js"
CARD_URL = f"/{DOMAIN}_static/{CARD_FILE}"
ISSUE_FOREIGN_CARD = "card_installed_separately"
DATA_CARD = f"{DOMAIN}_card"
LOVELACE = "lovelace"
MODE_STORAGE = "storage"


def _card_hash() -> str:
    return hashlib.sha256((FRONTEND_DIR / CARD_FILE).read_bytes()).hexdigest()[:8]


async def async_card_url(hass: HomeAssistant) -> str:
    version = (await async_get_integration(hass, DOMAIN)).version
    digest = await hass.async_add_executor_job(_card_hash)
    return f"{CARD_URL}?v={version}-{digest}"


def _path(url: str) -> str:
    return url.split("?", 1)[0]


def _is_ours(item: dict[str, Any]) -> bool:
    return _path(item.get("url", "")) == CARD_URL


def _is_foreign(item: dict[str, Any]) -> bool:
    return _path(item.get("url", "")).endswith(f"/{CARD_FILE}") and not _is_ours(item)


async def async_register_card(hass: HomeAssistant) -> None:
    """Enter the card as a dashboard resource. Runs with every setup of an entry: after
    a separately installed copy was removed, reloading the integration is enough."""
    url = await async_card_url(hass)
    lovelace = hass.data.get(LOVELACE)
    resources = getattr(lovelace, "resources", None)
    if resources is None:
        # No dashboards set up (tests, a stripped-down instance): nothing to enter.
        return
    if getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        _register_extra_module(hass, resources, url)
        hass.data[DATA_CARD] = True
        return
    # Loads the collection where the frontend has not asked for it yet.
    await resources.async_get_info()
    items = list(resources.async_items())
    own = [item for item in items if _is_ours(item)]
    foreign = [item for item in items if _is_foreign(item)]
    if foreign:
        for item in own:
            await resources.async_delete_item(item["id"])
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_FOREIGN_CARD,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_FOREIGN_CARD,
            translation_placeholders={"url": foreign[0]["url"]},
        )
        hass.data[DATA_CARD] = True
        return
    ir.async_delete_issue(hass, DOMAIN, ISSUE_FOREIGN_CARD)
    if not own:
        await resources.async_create_item({"res_type": "module", "url": url})
    else:
        if own[0]["url"] != url:
            await resources.async_update_item(own[0]["id"], {"res_type": "module", "url": url})
        for item in own[1:]:
            await resources.async_delete_item(item["id"])
    hass.data[DATA_CARD] = True


def _register_extra_module(hass: HomeAssistant, resources: Any, url: str) -> None:
    """Resources in YAML: we cannot enter one. Hand the module to the frontend instead,
    unless configuration.yaml already lists the card."""
    from homeassistant.components import frontend  # noqa: PLC0415

    if any(_path(item.get("url", "")).endswith(f"/{CARD_FILE}") for item in resources.async_items() or []):
        return
    try:
        frontend.add_extra_js_url(hass, url)
    except KeyError:
        # Frontend not set up: there is no page that could show a card.
        _LOGGER.debug("Frontend not set up, thermostat card not registered")


async def async_unregister_card(hass: HomeAssistant) -> None:
    """The integration is removed for good: take our resource out again."""
    hass.data.pop(DATA_CARD, None)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_FOREIGN_CARD)
    lovelace = hass.data.get(LOVELACE)
    resources = getattr(lovelace, "resources", None)
    if resources is None or getattr(lovelace, "resource_mode", None) != MODE_STORAGE:
        return
    await resources.async_get_info()
    for item in [item for item in resources.async_items() if _is_ours(item)]:
        await resources.async_delete_item(item["id"])
