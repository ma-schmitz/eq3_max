"""Config and options flow: connection choice (USB stick or network CUL)."""

import asyncio
import socket
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eq3_max.config_flow import probe_network
from custom_components.eq3_max.const import DOMAIN

from .test_config_flow import PORT, patches

HOST = "192.0.2.50"


async def init(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_first_step_offers_usb_and_network(hass):
    r = await init(hass)
    assert r["type"] is FlowResultType.MENU
    assert r["step_id"] == "user"
    assert r["menu_options"] == ["usb", "network"]


async def test_network_flow_creates_entry_with_host_and_port(hass):
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True) as probe, patch(
        "custom_components.eq3_max.async_setup_entry", return_value=True
    ):
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network"})
        assert r["step_id"] == "network"
        defaults = {str(k): k.default() for k in r["data_schema"].schema}
        assert defaults["port"] == 2323
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": f" {HOST} ", "port": 2323})
        assert r["step_id"] == "address"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "none"})
    probe.assert_called_once_with(HOST, 2323)
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"] == {"connection": "network", "host": HOST, "port": 2323, "address": "C0FFEE", "devices": []}
    assert r["result"].unique_id == "C0FFEE"


async def test_network_probe_failure_shows_cannot_connect(hass):
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=False):
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": HOST, "port": 2323})
    assert r["step_id"] == "network"
    assert r["errors"] == {"base": "cannot_connect"}


async def test_usb_flow_stores_connection_usb(hass):
    p1, p2 = patches()
    with p1, p2, patch("custom_components.eq3_max.async_setup_entry", return_value=True):
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "usb"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": PORT})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "none"})
    assert r["data"]["connection"] == "usb"
    assert r["data"]["port"] == PORT
    assert "host" not in r["data"]


# --- probe against a local fake CUL ---


async def _server(answer: bool):
    async def handle(reader, writer):
        try:
            while raw := await reader.readline():
                if raw.strip() == b"V" and answer:
                    # Frames may come first: culfw keeps receiving between TCP sessions.
                    writer.write(b"Z0B0100600A1B005C0FFEE00\r\nV 1.26.08 a-culfw CUBE\r\n")
                    await writer.drain()
        except ConnectionError:
            pass
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


@pytest.mark.usefixtures("socket_enabled")
async def test_probe_network_ok():
    server, port = await _server(answer=True)
    try:
        assert await probe_network("127.0.0.1", port) is True
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.usefixtures("socket_enabled")
async def test_probe_network_silent_peer_fails():
    server, port = await _server(answer=False)
    try:
        assert await probe_network("127.0.0.1", port, timeout=0.05) is False
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.usefixtures("socket_enabled")
async def test_probe_network_refused_fails():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    assert await probe_network("127.0.0.1", port) is False


async def test_probe_network_connect_timeout_fails():
    with patch("custom_components.eq3_max.config_flow.open_tcp", AsyncMock(side_effect=TimeoutError)):
        assert await probe_network(HOST, 2323) is False


# --- options: change the connection ---


async def test_options_menu_offers_settings_and_connection(hass, entry):
    entry.add_to_hass(hass)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] is FlowResultType.MENU
    assert r["menu_options"] == ["settings", "connection", "radios"]


async def _to_connection(hass, entry, kind):
    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "connection"})
    assert r["type"] is FlowResultType.MENU
    assert r["menu_options"] == ["connection_usb", "connection_network"]
    return await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": f"connection_{kind}"})


def _count_hubs(fake_hub):
    created = []
    orig_init = fake_hub.__init__

    def counting(self, *a, **kw):
        created.append(1)
        orig_init(self, *a, **kw)

    fake_hub.__init__ = counting
    return created, orig_init


async def test_options_usb_to_network_updates_data_and_reloads(hass, setup_entry, fake_hub):
    created, orig_init = _count_hubs(fake_hub)
    try:
        hass.config_entries.async_update_entry(setup_entry, options={"brake": True, "away_temperature": 17.0, "away_hours": 12})
        await hass.async_block_till_done()
        created.clear()
        with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True) as probe:
            r = await _to_connection(hass, setup_entry, "network")
            assert r["step_id"] == "connection_network"
            r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": HOST, "port": 2323})
            await hass.async_block_till_done()
        probe.assert_called_once_with(HOST, 2323)
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert setup_entry.data["connection"] == "network"
        assert setup_entry.data["host"] == HOST
        assert setup_entry.data["port"] == 2323
        assert setup_entry.data["address"] == "C0FFEE"
        assert len(setup_entry.data["devices"]) == 4
        # The options stay as they were.
        assert setup_entry.options == {"brake": True, "away_temperature": 17.0, "away_hours": 12}
        assert len(created) == 1
        assert fake_hub.last.port == f"{HOST}:2323"
        assert callable(fake_hub.last.kwargs["open_connection"])
    finally:
        fake_hub.__init__ = orig_init


async def test_options_network_probe_failure_keeps_data(hass, setup_entry, fake_hub):
    before = dict(setup_entry.data)
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=False):
        r = await _to_connection(hass, setup_entry, "network")
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": HOST, "port": 2323})
    assert r["step_id"] == "connection_network"
    assert r["errors"] == {"base": "cannot_connect"}
    assert dict(setup_entry.data) == before


async def test_options_network_to_usb_drops_host_and_reloads(hass, fake_hub):
    from .test_connection import network_entry

    entry = network_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    created, orig_init = _count_hubs(fake_hub)
    try:
        p1, p2 = patches()
        with p1, p2:
            r = await _to_connection(hass, entry, "usb")
            assert r["step_id"] == "connection_usb"
            r = await hass.config_entries.options.async_configure(r["flow_id"], {"port": PORT})
            await hass.async_block_till_done()
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert entry.data["connection"] == "usb"
        assert entry.data["port"] == PORT
        assert "host" not in entry.data
        assert len(created) == 1
        assert fake_hub.last.port == PORT
        assert "open_connection" not in fake_hub.last.kwargs
    finally:
        fake_hub.__init__ = orig_init


async def test_options_network_form_defaults_to_current_target(hass, fake_hub):
    from .test_connection import network_entry

    entry = network_entry()
    entry.add_to_hass(hass)
    r = await _to_connection(hass, entry, "network")
    defaults = {str(k): k.default() for k in r["data_schema"].schema}
    assert defaults == {"host": HOST, "port": 2323}


async def test_options_unchanged_connection_does_not_reload(hass, setup_entry, fake_hub):
    created, orig_init = _count_hubs(fake_hub)
    try:
        current = setup_entry.data["port"]
        with patch(
            "custom_components.eq3_max.config_flow.list_serial_ports", return_value={PORT: PORT, current: current}
        ), patch("custom_components.eq3_max.config_flow.probe_cul", return_value=True):
            r = await _to_connection(hass, setup_entry, "usb")
            assert {str(k): k.default() for k in r["data_schema"].schema} == {"port": current}
            r = await hass.config_entries.options.async_configure(r["flow_id"], {"port": current})
            await hass.async_block_till_done()
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert setup_entry.data["connection"] == "usb"
        assert created == []
    finally:
        fake_hub.__init__ = orig_init


async def test_options_away_change_does_not_reload(hass, setup_entry, fake_hub):
    created, orig_init = _count_hubs(fake_hub)
    try:
        r = await hass.config_entries.options.async_init(setup_entry.entry_id)
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "settings"})
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], {"brake": False, "away_temperature": 16.0, "away_hours": 48}
        )
        await hass.async_block_till_done()
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert setup_entry.options["away_temperature"] == 16.0
        assert created == []
    finally:
        fake_hub.__init__ = orig_init


def test_connection_steps_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    for name in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((base / name).read_text())
        config, options = data["config"]["step"], data["options"]["step"]
        assert set(config["user"]["menu_options"]) == {"usb", "network"}
        assert set(config["network"]["data"]) == {"host", "port"}
        assert set(options["init"]["menu_options"]) == {"settings", "connection", "radios"}
        assert set(options["connection"]["menu_options"]) == {"connection_usb", "connection_network"}
        assert set(options["radios"]["menu_options"]) == {"radio_add_usb", "radio_add_network", "radio_remove"}
        assert set(options["radio_add_network"]["data"]) == {"name", "host", "port"}
        for key in ("name_missing", "name_taken", "radio_in_use"):
            assert data["options"]["error"][key]
        assert set(options["settings"]["data"]) == {"brake", "away_temperature", "away_hours"}
        assert "port" in options["connection_usb"]["data"]
        assert set(options["connection_network"]["data"]) == {"host", "port"}
        assert data["options"]["error"]["cannot_connect"]
    de = json.loads((base / "translations/de.json").read_text())
    assert de["config"]["step"]["user"]["menu_options"] == {"usb": "USB-Stick", "network": "Netzwerk (CUN, geflashter Cube)"}
    assert de["options"]["step"]["init"]["menu_options"]["connection"] == "Verbindung ändern"


# --- fix round 1 ---


async def test_options_unchanged_usb_target_is_not_probed(hass, setup_entry, fake_hub):
    created, orig_init = _count_hubs(fake_hub)
    current = setup_entry.data["port"]
    try:
        with patch(
            "custom_components.eq3_max.config_flow.list_serial_ports", return_value={PORT: PORT, current: current}
        ), patch("custom_components.eq3_max.config_flow.probe_cul", return_value=False) as probe:
            r = await _to_connection(hass, setup_entry, "usb")
            r = await hass.config_entries.options.async_configure(r["flow_id"], {"port": current})
            await hass.async_block_till_done()
        probe.assert_not_called()
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert created == []
    finally:
        fake_hub.__init__ = orig_init


async def test_options_unchanged_network_target_is_not_probed(hass, fake_hub):
    from .test_connection import network_entry

    entry = network_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    created, orig_init = _count_hubs(fake_hub)
    try:
        with patch("custom_components.eq3_max.config_flow.probe_network", return_value=False) as probe:
            r = await _to_connection(hass, entry, "network")
            r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": HOST, "port": 2323})
            await hass.async_block_till_done()
        probe.assert_not_called()
        assert r["type"] is FlowResultType.CREATE_ENTRY
        assert created == []
    finally:
        fake_hub.__init__ = orig_init


def test_options_connection_steps_hint_active_connection_not_probed():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    de = json.loads((base / "translations/de.json").read_text())["options"]["step"]
    for step in ("connection_usb", "connection_network"):
        assert "nicht geprüft" in de[step]["description"]
    for name in ("strings.json", "translations/en.json"):
        en = json.loads((base / name).read_text())["options"]["step"]
        for step in ("connection_usb", "connection_network"):
            assert "not probed" in en[step]["description"]


@pytest.mark.parametrize("exc", [ValueError("bad"), UnicodeError("label empty or too long")])
async def test_probe_network_bad_host_fails(exc):
    with patch("custom_components.eq3_max.config_flow.open_tcp", AsyncMock(side_effect=exc)):
        assert await probe_network("a..b", 2323) is False


@pytest.mark.parametrize("host", ["", "   ", "a b", "http://cube", "cube/x", "cube:2323/"])
async def test_network_invalid_host(hass, host):
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True) as probe:
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": host, "port": 2323})
    assert r["step_id"] == "network"
    assert r["errors"] == {"base": "invalid_host"}
    probe.assert_not_called()


async def test_options_network_invalid_host(hass, setup_entry, fake_hub):
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True) as probe:
        r = await _to_connection(hass, setup_entry, "network")
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": "http://cube", "port": 2323})
    assert r["errors"] == {"base": "invalid_host"}
    probe.assert_not_called()


async def test_usb_free_text_port_must_be_dev_path(hass):
    with patch("custom_components.eq3_max.config_flow.list_serial_ports", return_value={}), patch(
        "custom_components.eq3_max.config_flow.probe_cul", return_value=True
    ) as probe:
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "usb"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": "COM3"})
        assert r["errors"] == {"base": "invalid_port"}
        probe.assert_not_called()
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"port": "/dev/ttyUSB0"})
    assert r["step_id"] == "address"
    probe.assert_called_once_with("/dev/ttyUSB0")


async def test_options_usb_free_text_port_must_be_dev_path(hass, fake_hub):
    from .test_connection import network_entry

    entry = network_entry()
    entry.add_to_hass(hass)
    with patch("custom_components.eq3_max.config_flow.list_serial_ports", return_value={}), patch(
        "custom_components.eq3_max.config_flow.probe_cul", return_value=True
    ) as probe:
        r = await _to_connection(hass, entry, "usb")
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"port": "ttyUSB0"})
    assert r["errors"] == {"base": "invalid_port"}
    probe.assert_not_called()


def test_new_error_texts_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    for name in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((base / name).read_text())
        for section in ("config", "options"):
            assert data[section]["error"]["invalid_host"]
            assert data[section]["error"]["invalid_port"]
