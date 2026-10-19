"""Connection type (USB or network) from the entry data: helper, setup, diagnostics, repair."""

import socket

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eq3_max.connection import connection_target, connection_type, hub_connection
from custom_components.eq3_max.const import DOMAIN

from .conftest import identity_devices

USB_PATH = "/dev/serial/by-path/usb-0:13"
NETWORK = {"connection": "network", "host": "192.0.2.50", "port": 2323}


def test_entry_without_connection_is_usb():
    data = {"port": USB_PATH, "address": "C0FFEE"}
    assert connection_type(data) == "usb"
    assert connection_target(data) == USB_PATH
    # USB keeps the transport's default opener (serial) untouched.
    assert hub_connection(data) == (USB_PATH, None)


def test_explicit_usb():
    data = {"connection": "usb", "port": USB_PATH}
    assert connection_type(data) == "usb"
    assert hub_connection(data) == (USB_PATH, None)


def test_network_target_and_opener():
    assert connection_type(NETWORK) == "network"
    assert connection_target(NETWORK) == "192.0.2.50:2323"
    target, opener = hub_connection(NETWORK)
    assert target == "192.0.2.50:2323"
    assert callable(opener)


@pytest.mark.usefixtures("socket_enabled")
async def test_network_opener_dials_host_and_port():
    import asyncio

    seen = []

    async def handle(reader, writer):
        seen.append(await reader.readline())
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        _target, opener = hub_connection({"connection": "network", "host": "127.0.0.1", "port": str(port)})
        reader, writer = await opener("ignored")
        writer.write(b"V\n")
        await writer.drain()
        assert writer.get_extra_info("socket").getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
        await reader.read()
        writer.close()
        assert seen == [b"V\n"]
    finally:
        server.close()
        await server.wait_closed()


def network_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="C0FFEE",
        title="eQ-3 MAX! C0FFEE",
        data={**NETWORK, "address": "C0FFEE", "devices": identity_devices()},
    )


async def test_usb_entry_without_connection_sets_up_with_serial(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    assert hub.started
    assert hub.port == USB_PATH
    assert "open_connection" not in hub.kwargs


async def test_network_entry_sets_up_with_tcp_opener(hass, fake_hub):
    entry = network_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    assert hub.started
    assert hub.port == "192.0.2.50:2323"
    assert callable(hub.kwargs["open_connection"])


async def test_diagnostics_usb_connection(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.diagnostics import async_get_config_entry_diagnostics

    data = await async_get_config_entry_diagnostics(hass, setup_entry)
    assert data["connection"] == {"type": "usb", "target": USB_PATH}


async def test_diagnostics_network_connection(hass, fake_hub):
    from custom_components.eq3_max.diagnostics import async_get_config_entry_diagnostics

    entry = network_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    data = await async_get_config_entry_diagnostics(hass, entry)
    assert data["connection"] == {"type": "network", "target": "192.0.2.50:2323"}


async def test_port_lost_issue_names_target(hass, fake_hub):
    from homeassistant.helpers import issue_registry as ir

    entry = network_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    fake_hub.last.on_problem("port_lost")
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "port_lost")
    assert issue.translation_placeholders == {"target": "192.0.2.50:2323"}


def test_port_lost_text_covers_both_connections():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    de = json.loads((base / "translations/de.json").read_text())["issues"]["port_lost"]
    assert de["title"] == "CUL nicht erreichbar"
    assert "{target}" in de["description"]
    for name in ("strings.json", "translations/en.json"):
        assert "{target}" in json.loads((base / name).read_text())["issues"]["port_lost"]["description"]
