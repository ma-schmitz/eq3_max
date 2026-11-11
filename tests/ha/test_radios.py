"""Several radio modules in one entry (same central address)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT, DOMAIN

from .conftest import FK, HT, identity_devices

OG = {"id": "r2", "name": "Obergeschoss", "connection": "network", "host": "192.0.2.60", "port": 2323}


def _devices_with_og():
    items = identity_devices()
    for item in items:
        if item["address"] == HT:
            item["radio"] = "r2"
    return items


@pytest.fixture
async def two_radios(hass, fake_hub):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="C0FFEE",
        title="eQ-3 MAX! C0FFEE",
        data={
            CONF_PORT: "/dev/serial/by-path/usb-0:13",
            CONF_ADDRESS: "C0FFEE",
            CONF_DEVICES: _devices_with_og(),
            "radios": [OG],
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _device(hass, entry, identifier):
    for device in dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id):
        if (DOMAIN, identifier) in device.identifiers:
            return device
    return None


async def test_hub_gets_the_extra_module_and_devices_keep_theirs(hass, two_radios, fake_hub):
    hub = fake_hub.last
    assert [(r.id, r.port) for r in hub.radios] == [("r2", "192.0.2.60:2323")]
    assert callable(hub.radios[0].open_connection)
    assert hub.devices[HT].radio == "r2" and hub.devices[FK].radio == ""


async def test_each_module_is_a_device_and_devices_hang_below_theirs(hass, two_radios):
    main = _device(hass, two_radios, "C0FFEE")
    og = _device(hass, two_radios, "C0FFEE:r2")
    assert og is not None and og.name == "eQ-3 MAX! radio module Obergeschoss" and og.via_device_id == main.id
    assert _device(hass, two_radios, "MEQ9000007").via_device_id == og.id
    assert _device(hass, two_radios, "NEQ9000010").via_device_id == main.id


async def test_extra_module_is_created_without_deprecated_via_device(hass, two_radios, caplog):
    assert _device(hass, two_radios, "C0FFEE:r2") is not None
    # The entry is set up by the fixture, so the warning would sit in the setup phase.
    messages = [record.getMessage() for record in caplog.get_records("setup")]
    assert not [m for m in messages if "deprecated `via_device`" in m]


async def test_radio_select_switches_without_reload(hass, two_radios, fake_hub):
    hub = fake_hub.last
    state = hass.states.get("select.ht_bad_unten_funkmodul")
    assert state.state == "Obergeschoss"
    assert state.attributes["options"] == ["Main module", "Obergeschoss"]  # main module in the system language
    hub.devices[FK].rssi_by_radio = {"": -60.0, "r2": -80.5}
    hub.on_update(hub.devices[FK])
    await hass.async_block_till_done()
    attrs = hass.states.get("select.fk_schlafzimmer_funkmodul").attributes
    assert attrs["rssi_hauptmodul"] == -60.0 and attrs["rssi_obergeschoss"] == -80.5
    await hass.services.async_call(
        "select", "select_option", {"entity_id": "select.fk_schlafzimmer_funkmodul", "option": "Obergeschoss"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert ("radio", FK, "r2") in hub.commands
    assert fake_hub.last is hub
    assert next(i for i in two_radios.data[CONF_DEVICES] if i["address"] == FK)["radio"] == "r2"
    og = _device(hass, two_radios, "C0FFEE:r2")
    assert _device(hass, two_radios, "NEQ9000010").via_device_id == og.id
    assert hass.states.get("select.fk_schlafzimmer_funkmodul").state == "Obergeschoss"


async def test_single_module_has_no_radio_select(hass, setup_entry):
    assert hass.states.get("select.ht_bad_unten_funkmodul") is None
    assert "funkmodule" not in hass.states.get("binary_sensor.eq3_max_verbunden").attributes


async def test_hub_entities_show_each_module(hass, two_radios, fake_hub):
    fake_hub.last.radio_connected["r2"] = False
    fake_hub.last.on_update(None)
    await hass.async_block_till_done()
    attrs = hass.states.get("binary_sensor.eq3_max_verbunden").attributes
    assert attrs["funkmodule"] == {"Hauptmodul": True, "Obergeschoss": False}
    assert hass.states.get("sensor.eq3_max_sendezeit_1h").attributes["funkmodule"] == {
        "Hauptmodul": 0.0, "Obergeschoss": 0.0,
    }


async def test_problem_of_extra_module_is_its_own_repair_issue(hass, two_radios, fake_hub):
    fake_hub.last.on_problem("port_lost", "r2")
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "port_lost_r2")
    assert issue is not None and issue.translation_key == "port_lost"
    assert issue.translation_placeholders == {"target": "192.0.2.60:2323"}
    assert ir.async_get(hass).async_get_issue(DOMAIN, "port_lost") is None
    # Connected again: the issue goes.
    fake_hub.last.on_update(None)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "port_lost_r2") is None


async def test_radio_module_device_cannot_be_deleted(hass, two_radios):
    from custom_components.eq3_max import async_remove_config_entry_device

    og = _device(hass, two_radios, "C0FFEE:r2")
    assert await async_remove_config_entry_device(hass, two_radios, og) is False


# --- panel ---


async def test_overview_lists_modules_and_device_assignment(hass, two_radios, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "eq3_max/overview"})
    reply = await client.receive_json()
    section = reply["result"]["entries"][0]
    radios = section["hub"]["radios"]
    assert [(r["id"], r["name"], r["connection"], r["target"]) for r in radios] == [
        ("", "Hauptmodul", "usb", "/dev/serial/by-path/usb-0:13"),
        ("r2", "Obergeschoss", "network", "192.0.2.60:2323"),
    ]
    devices = {d["serial"]: d for d in section["devices"]}
    assert devices["MEQ9000007"]["radio"] == "r2" and devices["NEQ9000010"]["radio"] == ""


async def test_ws_set_radio(hass, two_radios, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    device_id = _device(hass, two_radios, "MEQ9000007").id
    await client.send_json_auto_id({"type": "eq3_max/set_radio", "device_id": device_id, "radio": ""})
    assert (await client.receive_json())["success"]
    assert fake_hub.last.devices[HT].radio == ""
    await client.send_json_auto_id({"type": "eq3_max/set_radio", "device_id": device_id, "radio": "keller"})
    reply = await client.receive_json()
    assert not reply["success"] and reply["error"]["translation_key"] == "radio_unknown"


async def test_ws_set_radio_requires_admin(hass, two_radios, fake_hub, hass_ws_client, hass_read_only_access_token):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    await client.send_json_auto_id({"type": "eq3_max/set_radio", "device_id": "x", "radio": ""})
    reply = await client.receive_json()
    assert reply["error"]["code"] == "unauthorized"


# --- options ---


async def _radios_menu(hass, entry):
    r = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radios"})


async def test_add_network_module(hass, setup_entry, fake_hub):
    r = await _radios_menu(hass, setup_entry)
    assert r["menu_options"] == ["radio_add_usb", "radio_search", "radio_add_network", "radio_rename"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_add_network"})
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True) as probe:
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], {"name": " Obergeschoss ", "host": "192.0.2.60", "port": 2323}
        )
        await hass.async_block_till_done()
    probe.assert_called_once_with("192.0.2.60", 2323)
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.data["radios"] == [OG]
    # Reloaded with the new module.
    assert [r.id for r in fake_hub.last.radios] == ["r2"]


async def test_add_module_rejects_taken_name_and_target(hass, two_radios):
    r = await _radios_menu(hass, two_radios)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_add_network"})
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"name": "Obergeschoss", "host": "192.0.2.61", "port": 2323}
    )
    assert r["errors"] == {"base": "name_taken"}
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"name": "Keller", "host": "192.0.2.60", "port": 2323}
    )
    assert r["errors"] == {"base": "radio_in_use"}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"name": "  ", "host": "x", "port": 2323})
    assert r["errors"] == {"base": "name_missing"}


async def test_add_usb_module_rejects_the_main_stick(hass, setup_entry):
    r = await _radios_menu(hass, setup_entry)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_add_usb"})
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"name": "Keller", "port": "/dev/serial/by-path/usb-0:13"}
    )
    assert r["errors"] == {"base": "radio_in_use"}


async def test_remove_module_moves_its_devices_to_main(hass, two_radios, fake_hub):
    r = await _radios_menu(hass, two_radios)
    assert "radio_remove" in r["menu_options"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_remove"})
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "r2"})
    await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert two_radios.data["radios"] == []
    assert next(i for i in two_radios.data[CONF_DEVICES] if i["address"] == HT)["radio"] == ""
    assert _device(hass, two_radios, "C0FFEE:r2") is None
    assert fake_hub.last.radios == [] and fake_hub.last.devices[HT].radio == ""
    # Back to one module: the module selects go for good.
    assert er.async_get(hass).async_get("select.ht_bad_unten_funkmodul") is None
    assert hass.states.get("select.ht_bad_unten_funkmodul") is None


async def test_pairing_and_reset_need_only_the_relevant_module(hass, two_radios, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.radio_connected["r2"] = False
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "eq3_max/pair", "entry_id": two_radios.entry_id})
    assert (await client.receive_json())["success"]
    from homeassistant.exceptions import HomeAssistantError

    ht = _device(hass, two_radios, "MEQ9000007").id
    with pytest.raises(HomeAssistantError, match="not connected"):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": ht}, blocking=True)
    fk = _device(hass, two_radios, "NEQ9000010").id
    await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": fk}, blocking=True)
    assert hub.resets == [FK]


async def test_deaf_extra_module_stays_reported_while_main_hears_devices(hass, two_radios, fake_hub):
    import time

    hub = fake_hub.last
    hub.on_problem("stick_deaf", "r2")
    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, "stick_deaf_r2") is not None
    # The main module hears a device: r2 is still deaf.
    hub.devices[FK].last_seen = time.time() + 100
    hub.on_update(hub.devices[FK])
    assert reg.async_get_issue(DOMAIN, "stick_deaf_r2") is not None
    hub.radio_heard["r2"] = time.time() + 100
    hub.on_update(hub.devices[FK])
    assert reg.async_get_issue(DOMAIN, "stick_deaf_r2") is None


async def test_remove_module_cleans_up_and_ids_are_not_reused(hass, two_radios, fake_hub):
    hub = fake_hub.last
    hub.on_problem("port_lost", "r2")
    hub.radio_connected["r2"] = False
    hub.devices[HT].rssi_by_radio = {"": -80.0, "r2": -60.0}
    r = await _radios_menu(hass, two_radios)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_remove"})
    await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "r2"})
    # Before the reload: a telegram must not write r2 back.
    hub.on_update(hub.devices[HT])
    assert next(i for i in two_radios.data[CONF_DEVICES] if i["address"] == HT)["radio"] == ""
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "port_lost_r2") is None
    assert "r2" not in fake_hub.last.devices[HT].rssi_by_radio
    # The next module gets a fresh id.
    r = await _radios_menu(hass, two_radios)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_add_network"})
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True):
        await hass.config_entries.options.async_configure(
            r["flow_id"], {"name": "Keller", "host": "192.0.2.61", "port": 2323}
        )
        await hass.async_block_till_done()
    assert [item["id"] for item in two_radios.data["radios"]] == ["r3"]


# --- names of the modules, the main module included ---


async def test_rename_the_main_module(hass, two_radios, fake_hub):
    r = await _radios_menu(hass, two_radios)
    assert "radio_rename" in r["menu_options"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_rename"})
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "radio_rename"
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "", "name": "  "})
    assert r["errors"] == {"base": "name_missing"}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "", "name": "Obergeschoss"})
    assert r["errors"] == {"base": "name_taken"}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "", "name": " EG "})
    await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert two_radios.data["main_name"] == "EG"
    main = _device(hass, two_radios, "C0FFEE")
    assert main.name == "eQ-3 MAX! radio module EG"
    state = hass.states.get("select.ht_bad_unten_funkmodul")
    assert state.attributes["options"] == ["EG", "Obergeschoss"]
    # The panel shows the chosen name as well.
    from custom_components.eq3_max.radios import radio_names

    assert radio_names(two_radios.data) == {"": "EG", "r2": "Obergeschoss"}


async def test_rename_an_extra_module_keeps_its_devices(hass, two_radios, fake_hub):
    r = await _radios_menu(hass, two_radios)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_rename"})
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "r2", "name": "OG"})
    await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert [item["name"] for item in two_radios.data["radios"]] == ["OG"]
    assert _device(hass, two_radios, "C0FFEE:r2").name == "eQ-3 MAX! radio module OG"
    assert _device(hass, two_radios, "MEQ9000007").via_device_id == _device(hass, two_radios, "C0FFEE:r2").id
    assert hass.states.get("select.ht_bad_unten_funkmodul").state == "OG"


async def test_single_module_can_be_named_too(hass, setup_entry, fake_hub):
    r = await _radios_menu(hass, setup_entry)
    assert "radio_rename" in r["menu_options"]
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_rename"})
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"radio": "", "name": "Keller"})
    await hass.async_block_till_done()
    assert setup_entry.data["main_name"] == "Keller"


async def test_ws_pair_through_a_chosen_module(hass, two_radios, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "eq3_max/pair", "entry_id": two_radios.entry_id, "radio": "r2"})
    reply = await client.receive_json()
    assert reply["success"] and hub.pairing == 60 and hub.pairing_radio == "r2"
    # That module must be connected; the others do not matter.
    hub.radio_connected["r2"] = False
    await client.send_json_auto_id({"type": "eq3_max/pair", "entry_id": two_radios.entry_id, "radio": "r2"})
    reply = await client.receive_json()
    assert not reply["success"] and reply["error"]["translation_key"] == "not_connected"
    await client.send_json_auto_id({"type": "eq3_max/pair", "entry_id": two_radios.entry_id, "radio": "keller"})
    reply = await client.receive_json()
    assert not reply["success"] and reply["error"]["translation_key"] == "radio_unknown"
    # Without a module: whichever hears the device.
    await client.send_json_auto_id({"type": "eq3_max/pair", "entry_id": two_radios.entry_id})
    reply = await client.receive_json()
    assert reply["success"] and hub.pairing_radio is None


async def test_overview_says_which_module_pairs(hass, two_radios, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.open_pairing(60, radio="r2")
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "eq3_max/overview"})
    section = (await client.receive_json())["result"]["entries"][0]
    assert section["hub"]["pairing_radio"] == "r2" and section["hub"]["pairing_remaining"] == 60


async def test_ws_rename_a_module_from_the_panel(hass, two_radios, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)

    async def rename(radio, name):
        await client.send_json_auto_id(
            {"type": "eq3_max/rename_radio", "entry_id": two_radios.entry_id, "radio": radio, "name": name}
        )
        return await client.receive_json()

    reply = await rename("", "  ")
    assert not reply["success"] and reply["error"]["translation_key"] == "radio_name_missing"
    reply = await rename("", "Obergeschoss")
    assert not reply["success"] and reply["error"]["translation_key"] == "radio_name_taken"
    reply = await rename("keller", "Keller")
    assert not reply["success"] and reply["error"]["translation_key"] == "radio_unknown"
    reply = await rename("", " EG ")
    assert reply["success"] and reply["result"] == {"name": "EG"}
    await hass.async_block_till_done()
    assert two_radios.data["main_name"] == "EG"
    assert _device(hass, two_radios, "C0FFEE").name == "eQ-3 MAX! radio module EG"
    reply = await rename("r2", "OG")
    assert reply["success"]
    await hass.async_block_till_done()
    assert [item["name"] for item in two_radios.data["radios"]] == ["OG"]
    assert hass.states.get("select.ht_bad_unten_funkmodul").attributes["options"] == ["EG", "OG"]
