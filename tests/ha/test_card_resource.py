"""Thermostat card: shipped with the integration, entered as a dashboard resource."""

from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.helpers import issue_registry as ir

from custom_components.eq3_max.card import (
    CARD_URL,
    DATA_CARD,
    ISSUE_FOREIGN_CARD,
    async_card_url,
    async_register_card,
    async_unregister_card,
)
from custom_components.eq3_max.const import DOMAIN

ROOT = Path(__file__).resolve().parents[2] / "custom_components" / "eq3_max"
MANIFEST_VERSION = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["version"]
HACS_URL = "/hacsfiles/eq3-max-thermostat-card/eq3-max-thermostat-card.js?hacstag=123"


class Resources:
    """What the integration uses of Home Assistant's resource collection."""

    def __init__(self, items=()):
        self.items = [dict(item) for item in items]
        self.loaded = False
        self._next = 1

    async def async_get_info(self):
        self.loaded = True
        return {"resources": len(self.items)}

    def async_items(self):
        return [dict(item) for item in self.items]

    async def async_create_item(self, data):
        assert self.loaded
        item = {"id": f"neu{self._next}", "type": data["res_type"], "url": data["url"]}
        self._next += 1
        self.items.append(item)
        return item

    async def async_update_item(self, item_id, updates):
        item = next(i for i in self.items if i["id"] == item_id)
        item["url"] = updates["url"]
        return item

    async def async_delete_item(self, item_id):
        self.items = [i for i in self.items if i["id"] != item_id]


@pytest.fixture
def lovelace(hass):
    def install(items=(), mode="storage"):
        resources = Resources(items)
        hass.data["lovelace"] = SimpleNamespace(resource_mode=mode, resources=resources)
        return resources

    return install


def test_card_version_matches_the_integration():
    source = (ROOT / "frontend" / "eq3-max-thermostat-card.js").read_text(encoding="utf-8")
    assert re.search(r'^export const VERSION = "([^"]+)";', source, re.M).group(1) == MANIFEST_VERSION


async def test_card_is_served(hass, setup_entry, fake_hub, hass_client):
    client = await hass_client()
    url = await async_card_url(hass)
    assert url.startswith(f"/eq3_max_static/eq3-max-thermostat-card.js?v={MANIFEST_VERSION}-")
    response = await client.get(url)
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]
    assert 'customElements.define("eq3-max-thermostat-card"' in await response.text()


async def test_resource_is_entered_once(hass, lovelace):
    resources = lovelace([{"id": "a", "type": "module", "url": "/local/other-card.js"}])
    await async_register_card(hass)
    url = await async_card_url(hass)
    assert [i["url"] for i in resources.items] == ["/local/other-card.js", url]
    assert resources.items[1]["type"] == "module"
    hass.data.pop(DATA_CARD)
    await async_register_card(hass)
    assert len(resources.items) == 2


async def test_resource_of_an_older_version_is_updated_in_place(hass, lovelace):
    resources = lovelace(
        [
            {"id": "alt", "type": "module", "url": f"{CARD_URL}?v=0.10.9-00000000"},
            {"id": "doppelt", "type": "module", "url": f"{CARD_URL}?v=0.10.8-11111111"},
        ]
    )
    await async_register_card(hass)
    assert resources.items == [{"id": "alt", "type": "module", "url": await async_card_url(hass)}]


async def test_separately_installed_card_wins_and_raises_a_repair(hass, lovelace):
    resources = lovelace(
        [
            {"id": "hacs", "type": "module", "url": HACS_URL},
            {"id": "unsere", "type": "module", "url": f"{CARD_URL}?v=0.10.9-00000000"},
        ]
    )
    await async_register_card(hass)
    assert [i["id"] for i in resources.items] == ["hacs"]
    issue = ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_FOREIGN_CARD)
    assert issue is not None and issue.translation_placeholders == {"url": HACS_URL}
    # The copy is gone after a restart: ours is entered, the repair goes.
    resources.items = []
    hass.data.pop(DATA_CARD)
    await async_register_card(hass)
    assert [i["url"] for i in resources.items] == [await async_card_url(hass)]
    assert ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_FOREIGN_CARD) is None


async def test_yaml_resources_get_an_extra_module(hass, lovelace):
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    hass.data[DATA_EXTRA_MODULE_URL] = set()
    resources = lovelace(mode="yaml")
    await async_register_card(hass)
    assert resources.items == []
    assert hass.data[DATA_EXTRA_MODULE_URL] == {await async_card_url(hass)}


async def test_yaml_resources_listing_the_card_stay_alone(hass, lovelace):
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    hass.data[DATA_EXTRA_MODULE_URL] = set()
    lovelace([{"type": "module", "url": "/local/eq3-max-thermostat-card.js"}], mode="yaml")
    await async_register_card(hass)
    assert hass.data[DATA_EXTRA_MODULE_URL] == set()


async def test_without_dashboards_nothing_happens(hass):
    await async_register_card(hass)
    assert DATA_CARD not in hass.data


async def test_setup_enters_the_card_and_removal_takes_it_out(hass, entry, fake_hub, lovelace):
    resources = lovelace()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert [i["url"] for i in resources.items] == [await async_card_url(hass)]
    # Unloading (reload, restart) keeps it; removing the last entry takes it out.
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(resources.items) == 1
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert resources.items == []


async def test_a_failing_resource_store_does_not_stop_the_setup(hass, entry, fake_hub, lovelace):
    resources = lovelace()

    async def kaputt():
        raise RuntimeError("Speicher kaputt")

    resources.async_get_info = kaputt
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert resources.items == []


async def test_unregister_without_dashboards(hass):
    await async_unregister_card(hass)


async def test_real_resource_collection(hass, entry, fake_hub):
    """Against Home Assistant's own collection: enter, update in place, remove."""
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "lovelace", {})
    resources = hass.data["lovelace"].resources
    await resources.async_create_item({"res_type": "module", "url": f"{CARD_URL}?v=0.10.9-00000000"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    items = resources.async_items()
    assert [(i["type"], i["url"]) for i in items] == [("module", await async_card_url(hass))]
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert resources.async_items() == []
