import json
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eq3_max.const import DOMAIN
from custom_components.eq3_max.protocol.devices import FACTORY_CONFIG

PORT = "/dev/serial/by-path/pci-0000:00:14.0-usb-0:13:1.0-port0"
EXPORT = {
    "version": 1,
    "devices": [
        {"serial": "MEQ9000007", "address": 10596357, "model": "BC-RT-TRX-CyN", "device_type": 1,
         "firmware": "1.0", "name": "MEQ9000007", "group": 1, "values": {"SET_TEMPERATURE": 21.0}},
    ],
}


def patches(probe=True):
    return (
        patch("custom_components.eq3_max.config_flow.list_serial_ports", return_value={PORT: PORT}),
        patch("custom_components.eq3_max.config_flow.probe_cul", return_value=probe),
    )


async def start(hass):
    """Start the flow and choose the USB stick (the first step is the connection menu)."""
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    return await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "usb"})


async def open_options(hass, entry):
    """Open the options and choose the settings form (init is a menu)."""
    r = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "settings"})


async def test_full_flow_with_json(hass, tmp_path):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(EXPORT))
    p1, p2 = patches()
    with p1, p2, patch("custom_components.eq3_max.async_setup_entry", return_value=True):
        r = await start(hass)
        assert r["step_id"] == "usb"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        assert r["step_id"] == "address"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "c0ffee"})
        assert r["step_id"] == "source"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "json"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"path": str(path)})
        assert r["step_id"] == "confirm"
        assert r["description_placeholders"]["count"] == "1"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["title"] == "eQ-3 MAX! C0FFEE"
    assert r["data"]["address"] == "C0FFEE"
    # New entries start with the airtime brake on (1 % duty cycle).
    assert r["result"].options == {"brake": True}
    assert r["data"]["port"] == PORT
    # Identity plus the imported Homegear snapshot; no pending command state.
    assert r["data"]["devices"][0] == {
        "address": 10596357, "serial": "MEQ9000007", "device_type": 1,
        "name": "MEQ9000007", "firmware": "1.0", "group": 1,
        "target": 21.0, "measured": None, "valve": None, "mode": None, "until": None,
        "battery_low": None, "rf_error": None, "locked": None, "window_open": None,
        "rssi": None, "last_seen": None,
        # Nothing of the configuration in the export: factory settings assumed.
        "config": FACTORY_CONFIG, "config_source": {key: "werksvorgabe" for key in FACTORY_CONFIG},
        # Links from the export (none here); pending link operations stay out.
        "links": [],
    }
    assert r["result"].unique_id == "C0FFEE"


async def test_port_without_culfw_shows_error(hass):
    p1, p2 = patches(probe=False)
    with p1, p2:
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
    assert r["errors"] == {"base": "cannot_connect"}


async def test_invalid_address(hass):
    p1, p2 = patches()
    with p1, p2:
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "XYZ"})
    assert r["errors"] == {"base": "invalid_address"}


async def test_unreadable_json(hass, tmp_path):
    p1, p2 = patches()
    with p1, p2:
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "json"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"path": str(tmp_path / "missing.json")})
    assert r["errors"] == {"base": "cannot_read"}


async def test_no_import_creates_empty_entry(hass):
    p1, p2 = patches()
    with p1, p2, patch("custom_components.eq3_max.async_setup_entry", return_value=True):
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "none"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["devices"] == []


async def test_homegear_import(hass):
    from custom_components.eq3_max.homegear_import import devices_from_export

    p1, p2 = patches()
    with p1, p2, patch(
        "custom_components.eq3_max.config_flow.read_homegear", return_value=devices_from_export(EXPORT)
    ), patch("custom_components.eq3_max.async_setup_entry", return_value=True):
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "homegear"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "192.0.2.2", "port": 2001})
        assert r["step_id"] == "confirm"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY


async def test_options_brake(hass, entry):
    entry.add_to_hass(hass)
    r = await open_options(hass, entry)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"brake": True})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"brake": True, "away_temperature": 18.0, "away_hours": 24}


async def test_options_away_defaults_and_values(hass, entry):
    entry.add_to_hass(hass)
    r = await open_options(hass, entry)
    defaults = {str(k): k.default() for k in r["data_schema"].schema}
    assert defaults == {"brake": False, "away_temperature": 18.0, "away_hours": 24}
    r = await hass.config_entries.options.async_configure(
        r["flow_id"], {"brake": False, "away_temperature": 16.5, "away_hours": 72}
    )
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"brake": False, "away_temperature": 16.5, "away_hours": 72}
    assert isinstance(entry.options["away_hours"], int)
    r = await open_options(hass, entry)
    assert {str(k): k.default() for k in r["data_schema"].schema}["away_hours"] == 72


async def test_options_away_out_of_range(hass, entry):
    import pytest
    from homeassistant.data_entry_flow import InvalidData

    entry.add_to_hass(hass)
    for bad in ({"away_temperature": 31.0}, {"away_hours": 0}, {"away_hours": 721}):
        r = await open_options(hass, entry)
        with pytest.raises(InvalidData):
            await hass.config_entries.options.async_configure(r["flow_id"], {"brake": False, **bad})


async def test_json_with_wrong_structure(hass, tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"version": 1, "devices": [42]}))
    p1, p2 = patches()
    with p1, p2:
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "json"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"path": str(path)})
    assert r["errors"] == {"base": "cannot_read"}


# --- final fix wave ---

FULL_EXPORT = {
    "version": 1,
    "devices": [
        {"serial": "MEQ9000007", "address": 10596357, "model": "BC-RT-TRX-CyN", "device_type": 1,
         "firmware": "1.0", "name": "MEQ9000007", "group": 0,
         "values": {"SET_TEMPERATURE": 21.0, "CONTROL_MODE": 1, "ACTUAL_TEMPERATURE": 19.8,
                    "VALVE_STATE": 18, "LOWBAT": False}},
        {"serial": "NEQ9000020", "address": 1577854, "model": "BC-SC-Rd-WM-2", "device_type": 4,
         "firmware": "1.0", "name": "NEQ9000020", "group": 0, "values": {"STATE": True, "LOWBAT": False}},
    ],
}


async def test_imported_values_are_shown_after_setup(hass, tmp_path, fake_hub):
    path = tmp_path / "export.json"
    path.write_text(json.dumps(FULL_EXPORT))
    p1, p2 = patches()
    with p1, p2:
        r = await start(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "json"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"path": str(path)})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    for item in r["data"]["devices"]:
        assert not {"pending_target", "pending_mode", "command_failed"} & set(item)
    st = hass.states.get("climate.meq9000007")
    assert st.state == "heat"
    assert st.attributes["temperature"] == 21.0
    assert st.attributes["current_temperature"] == 19.8
    assert hass.states.get("sensor.meq9000007_ventil").state == "18"
    assert hass.states.get("binary_sensor.meq9000007_lowbat").state == "off"
    assert hass.states.get("binary_sensor.neq9000020_state").state == "on"
