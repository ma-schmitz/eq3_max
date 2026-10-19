"""Sidebar panel "eQ-3 MAX!": registration, static module, configuration_url."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.components.frontend import DATA_PANELS
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT, DOMAIN
from custom_components.eq3_max.panel import PANEL_URL_PATH
from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.messages import DeviceType


MANIFEST = Path(__file__).resolve().parents[2] / "custom_components" / "eq3_max" / "manifest.json"
MANIFEST_VERSION = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]


def panel(hass):
    return hass.data.get(DATA_PANELS, {}).get(PANEL_URL_PATH)


async def test_panel_registered_admin_only(hass, setup_entry, fake_hub):
    p = panel(hass)
    assert p is not None
    assert p.component_name == "custom"
    assert p.sidebar_title == "eQ-3 MAX!" and p.sidebar_icon == "mdi:radiator"
    assert p.require_admin is True
    custom = p.config["_panel_custom"]
    assert custom["name"] == "eq3-max-panel"
    assert custom["module_url"].startswith(f"/eq3_max_static/eq3-max-panel.js?v={MANIFEST_VERSION}-")
    assert custom["embed_iframe"] is False


async def test_static_module_is_served(hass, setup_entry, fake_hub, hass_client):
    client = await hass_client()
    url = panel(hass).config["_panel_custom"]["module_url"]
    response = await client.get(url)
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]
    body = await response.text()
    assert 'customElements.define("eq3-max-panel"' in body


async def test_panel_once_for_two_entries_and_removed_with_last(hass, setup_entry, fake_hub):
    second = MockConfigEntry(
        domain=DOMAIN,
        unique_id="ABCDEF",
        title="eQ-3 MAX! ABCDEF",
        data={CONF_PORT: "/dev/ttyACM1", CONF_ADDRESS: "ABCDEF", CONF_DEVICES: [MaxDevice(0x222222, "XEQ0000001", DeviceType.HEATING_THERMOSTAT, name="ht-zwei").identity_dict()]},
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is not None
    await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is not None
    await hass.config_entries.async_unload(second.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is None
    # Loading again registers it again (static path only once).
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is not None


async def test_reload_keeps_panel(hass, setup_entry, fake_hub):
    assert await hass.config_entries.async_reload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is not None


async def test_configuration_url_on_hub_and_devices(hass, setup_entry, fake_hub):
    reg = dr.async_get(hass)
    hub_device = reg.async_get_device(identifiers={(DOMAIN, "C0FFEE")})
    assert hub_device.configuration_url == "homeassistant://eq3-max"
    ht = reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")})
    assert ht.configuration_url == "homeassistant://eq3-max"


async def test_failed_registration_does_not_count_entry(hass, entry, fake_hub):
    from unittest.mock import patch

    from custom_components.eq3_max.panel import DATA_PANEL

    entry.add_to_hass(hass)
    with patch(
        "custom_components.eq3_max.panel.panel_custom.async_register_panel", side_effect=RuntimeError("kaputt")
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert panel(hass) is None
    assert hass.data[DATA_PANEL]["entries"] == set()
    assert fake_hub.last.started is False
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert panel(hass) is not None and hass.data[DATA_PANEL]["entries"] == {entry.entry_id}
