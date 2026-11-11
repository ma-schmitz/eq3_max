"""Search for culfw modules on the local network (flashed Cube, CUN): TCP 2323, answer to "V"."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.eq3_max.const import DOMAIN
from custom_components.eq3_max.discovery import Found, candidate_hosts, probe_version, scan

CUBE = Found("192.0.2.60", 2323, "V 1.26.08 a-culfw CUBE")
CUN = Found("192.0.2.77", 2323, "V 1.67 CUNX")
SEARCH = "custom_components.eq3_max.config_flow.async_search_network"


def adapter(address, prefix, *, enabled=True):
    return {"name": "eth0", "index": 1, "enabled": enabled, "auto": True, "default": True, "ipv6": [],
            "ipv4": [{"address": address, "network_prefix": prefix}]}


# --- which addresses are asked ---


def test_candidates_are_the_own_subnet_without_the_own_address():
    hosts = candidate_hosts([adapter("192.0.2.84", 24)])
    assert len(hosts) == 253
    assert hosts[0] == "192.0.2.1" and hosts[-1] == "192.0.2.254"
    assert "192.0.2.84" not in hosts


def test_candidates_of_a_large_network_are_cut_to_the_24_around_the_own_address():
    hosts = candidate_hosts([adapter("10.1.7.20", 8)])
    assert len(hosts) == 253 and hosts[0] == "10.1.7.1" and "10.1.7.20" not in hosts


def test_candidates_skip_disabled_adapters_loopback_and_link_local_and_merge_duplicates():
    hosts = candidate_hosts([
        adapter("10.20.30.108", 24),
        adapter("10.20.30.109", 24),
        adapter("172.30.32.1", 23, enabled=False),
        adapter("127.0.0.1", 8),
        adapter("169.254.3.4", 16),
    ])
    assert len(hosts) == 252 and all(h.startswith("10.20.30.") for h in hosts)


def test_candidates_of_a_small_network():
    assert candidate_hosts([adapter("10.20.40.2", 30)]) == ["10.20.40.1"]


# --- asking one address ---


async def _server(answer: bytes | None):
    async def handle(reader, writer):
        try:
            while raw := await reader.readline():
                if raw.strip() == b"V" and answer is not None:
                    writer.write(answer)
                    await writer.drain()
        except ConnectionError:
            pass
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


@pytest.mark.usefixtures("socket_enabled")
async def test_probe_version_returns_the_answer_and_skips_frames():
    server, port = await _server(b"Z0B0100600A1B005C0FFEE00\r\nV 1.26.08 a-culfw CUBE\r\n")
    try:
        assert await probe_version("127.0.0.1", port) == "V 1.26.08 a-culfw CUBE"
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.usefixtures("socket_enabled")
async def test_probe_version_none_for_silent_and_foreign_peers():
    for answer in (None, b"HTTP/1.1 400 Bad Request\r\n"):
        server, port = await _server(answer)
        try:
            assert await probe_version("127.0.0.1", port, answer_timeout=0.05) is None
        finally:
            server.close()
            await server.wait_closed()


# --- asking many ---


async def test_scan_returns_answers_sorted_by_address_and_skips_known_targets():
    asked = []
    running = peak = 0

    async def fake_probe(host, port):
        nonlocal running, peak
        asked.append(host)
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.001)
        running -= 1
        return {"192.0.2.77": CUN.version, "192.0.2.9": "V 1.66 nanoCUL868", "192.0.2.60": CUBE.version}.get(host)

    hosts = [f"192.0.2.{n}" for n in range(1, 255)]
    found = await scan(hosts, 2323, skip={"192.0.2.9:2323"}, probe=fake_probe, concurrency=20)
    assert found == [CUBE, CUN]
    assert "192.0.2.9" not in asked  # a module in use is not even connected to
    assert len(asked) == 253 and peak <= 20


async def test_scan_survives_a_failing_probe():
    async def fake_probe(host, port):
        if host == "192.0.2.2":
            raise OSError("boom")
        return CUBE.version if host == "192.0.2.60" else None

    assert await scan(["192.0.2.2", "192.0.2.60"], 2323, probe=fake_probe) == [CUBE]


# --- set-up ---


async def init(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_setup_search_lists_the_modules_and_takes_the_chosen_one(hass):
    with patch(SEARCH, return_value=[CUBE, CUN]) as search, patch(
        "custom_components.eq3_max.async_setup_entry", return_value=True
    ):
        r = await init(hass)
        assert r["menu_options"] == ["usb", "network_search", "network"]
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network_search"})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "network_search"
        options = r["data_schema"].schema["module"].container
        assert options == {
            "192.0.2.60:2323": "192.0.2.60 – V 1.26.08 a-culfw CUBE",
            "192.0.2.77:2323": "192.0.2.77 – V 1.67 CUNX",
        }
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"module": "192.0.2.60:2323"})
        assert r["step_id"] == "address"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "none"})
    search.assert_called_once()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["connection"] == "network" and r["data"]["host"] == "192.0.2.60" and r["data"]["port"] == 2323


async def test_setup_search_without_a_hit_offers_search_again_or_manual_entry(hass):
    with patch(SEARCH, return_value=[]):
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network_search"})
    assert r["type"] is FlowResultType.MENU and r["step_id"] == "network_none"
    assert r["menu_options"] == ["network_search", "network"]


async def test_setup_search_skips_modules_of_existing_entries(hass, setup_entry, fake_hub):
    hass.config_entries.async_update_entry(
        setup_entry,
        data={**setup_entry.data, "radios": [{"id": "r2", "name": "OG", "connection": "network", "host": "192.0.2.60", "port": 2323}]},
    )
    with patch(SEARCH, return_value=[CUN]) as search:
        r = await init(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "network_search"})
    assert search.call_args.kwargs["skip"] == {"192.0.2.60:2323"}
    assert list(r["data_schema"].schema["module"].container) == ["192.0.2.77:2323"]


# --- options: further module, changed connection ---


async def _options(hass, entry, *steps):
    r = await hass.config_entries.options.async_init(entry.entry_id)
    for step in steps:
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": step})
    return r


async def test_add_a_found_module_as_further_radio_module(hass, setup_entry, fake_hub):
    r = await _options(hass, setup_entry, "radios")
    assert r["menu_options"] == ["radio_add_usb", "radio_search", "radio_add_network", "radio_rename"]
    with patch(SEARCH, return_value=[CUBE]):
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "radio_search"})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "radio_search"
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"name": "  ", "module": "192.0.2.60:2323"})
        assert r["errors"] == {"base": "name_missing"}
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], {"name": " Obergeschoss ", "module": "192.0.2.60:2323"}
        )
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.data["radios"] == [
        {"id": "r2", "name": "Obergeschoss", "connection": "network", "host": "192.0.2.60", "port": 2323}
    ]
    assert [radio.id for radio in fake_hub.last.radios] == ["r2"]


async def test_radio_search_without_a_hit(hass, setup_entry, fake_hub):
    with patch(SEARCH, return_value=[]):
        r = await _options(hass, setup_entry, "radios", "radio_search")
    assert r["type"] is FlowResultType.MENU and r["step_id"] == "radio_none"
    assert r["menu_options"] == ["radio_search", "radio_add_network"]


async def test_change_the_connection_to_a_found_module(hass, setup_entry, fake_hub):
    r = await _options(hass, setup_entry, "connection")
    assert r["menu_options"] == ["connection_usb", "connection_search", "connection_network"]
    with patch(SEARCH, return_value=[CUBE]):
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "connection_search"})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "connection_search"
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"module": "192.0.2.60:2323"})
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.data["connection"] == "network"
    assert setup_entry.data["host"] == "192.0.2.60" and setup_entry.data["port"] == 2323


async def test_connection_search_without_a_hit(hass, setup_entry, fake_hub):
    with patch(SEARCH, return_value=[]):
        r = await _options(hass, setup_entry, "connection", "connection_search")
    assert r["type"] is FlowResultType.MENU and r["step_id"] == "connection_none"
    assert r["menu_options"] == ["connection_search", "connection_network"]


# --- the search itself, with Home Assistant's adapters ---


async def test_search_asks_the_subnets_of_the_enabled_adapters(hass):
    from custom_components.eq3_max import discovery

    seen = {}

    async def fake_scan(hosts, port, *, skip=frozenset(), **_kw):
        seen.update(hosts=hosts, port=port, skip=skip)
        return [CUBE]

    with patch.object(discovery, "scan", fake_scan), patch.object(
        discovery.network, "async_get_adapters", return_value=[adapter("192.0.2.84", 24)]
    ):
        found = await discovery.async_search_network(hass, skip={"192.0.2.5:2323"})
    assert found == [CUBE]
    assert len(seen["hosts"]) == 253 and seen["port"] == 2323 and seen["skip"] == {"192.0.2.5:2323"}


# --- found by Home Assistant itself: a-culfw gives the Cube a MAC address 00:80:41:xx:xx:xx ---

PROBE = "custom_components.eq3_max.config_flow.probe_version"


def dhcp_info(ip="192.0.2.138", mac="008041123456"):
    from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

    return DhcpServiceInfo(ip=ip, hostname="", macaddress=mac)


async def discovered(hass, **kw):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_DHCP}, data=dhcp_info(**kw)
    )


def test_manifest_asks_for_the_a_culfw_mac_prefix():
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[2] / "custom_components/eq3_max/manifest.json").read_text())
    assert manifest["dhcp"] == [{"macaddress": "008041*"}]
    assert "network" in manifest["dependencies"]


async def test_discovered_cube_without_an_entry_becomes_a_new_central(hass):
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe") as probe, patch(
        "custom_components.eq3_max.async_setup_entry", return_value=True
    ):
        r = await discovered(hass)
        probe.assert_called_once_with("192.0.2.138", 2323)
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "discovered_new"
        assert r["description_placeholders"] == {"host": "192.0.2.138", "version": "V 1.26.08 a-culfw CUBe"}
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
        assert r["step_id"] == "address"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "C0FFEE"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"source": "none"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert r["data"]["connection"] == "network" and r["data"]["host"] == "192.0.2.138" and r["data"]["port"] == 2323
    assert r["data"]["mac"] == "00:80:41:12:34:56"


async def test_discovered_address_that_is_no_culfw_is_dropped(hass):
    with patch(PROBE, return_value=None):
        r = await discovered(hass)
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "not_culfw"


async def test_discovered_module_already_in_use_is_dropped_without_connecting(hass, setup_entry, fake_hub):
    hass.config_entries.async_update_entry(
        setup_entry,
        data={**setup_entry.data, "radios": [{"id": "r2", "name": "OG", "connection": "network", "host": "192.0.2.138", "port": 2323}]},
    )
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe") as probe:
        r = await discovered(hass)
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "already_configured"
    probe.assert_not_called()


async def test_same_cube_is_offered_only_once(hass):
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe"):
        await discovered(hass)
        r = await discovered(hass)
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "already_in_progress"


async def test_discovered_cube_can_join_an_existing_entry_as_further_module(hass, setup_entry, fake_hub):
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe"):
        r = await discovered(hass)
        assert r["type"] is FlowResultType.MENU and r["step_id"] == "discovered"
        assert r["menu_options"] == ["discovered_add", "discovered_new"]
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "discovered_add"})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "discovered_add"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": " "})
        assert r["errors"] == {"base": "name_missing"}
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "Obergeschoss"})
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "radio_added"
    assert setup_entry.data["radios"] == [
        {"id": "r2", "name": "Obergeschoss", "connection": "network", "host": "192.0.2.138", "port": 2323,
         "mac": "00:80:41:12:34:56"}
    ]
    assert [radio.id for radio in fake_hub.last.radios] == ["r2"]


async def test_discovered_cube_as_own_central_next_to_an_existing_entry(hass, setup_entry, fake_hub):
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe"):
        r = await discovered(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "discovered_new"})
        assert r["type"] is FlowResultType.FORM and r["step_id"] == "discovered_new"
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["step_id"] == "address"


def test_discovery_steps_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    for name in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((base / name).read_text())["config"]
        assert set(data["step"]["discovered"]["menu_options"]) == {"discovered_add", "discovered_new"}
        assert "{host}" in data["step"]["discovered"]["description"]
        assert "{host}" in data["step"]["discovered_new"]["description"]
        assert set(data["step"]["discovered_add"]["data"]) == {"name", "entry"}
        for reason in ("not_culfw", "radio_added", "already_in_progress"):
            assert data["abort"][reason]
        for error in ("name_missing", "name_taken"):
            assert data["error"][error]
        assert "{host}" in data["flow_title"]


async def test_known_cube_with_a_new_address_is_followed(hass, setup_entry, fake_hub):
    """The Cube takes its address from DHCP: when it changes, the module's host follows."""
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe"):
        r = await discovered(hass)
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"next_step_id": "discovered_add"})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"name": "Obergeschoss"})
        await hass.async_block_till_done()
        r = await discovered(hass, ip="192.0.2.150")
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "already_configured"
    [radio] = setup_entry.data["radios"]
    assert radio["host"] == "192.0.2.150" and radio["name"] == "Obergeschoss"
    assert fake_hub.last.radios[0].port == "192.0.2.150:2323"


async def test_changing_the_connection_by_hand_forgets_the_remembered_mac(hass, setup_entry, fake_hub):
    """Otherwise a later address change of the old Cube would redirect the new connection."""
    hass.config_entries.async_update_entry(
        setup_entry, data={**setup_entry.data, "connection": "network", "host": "192.0.2.138", "port": 2323,
                           "mac": "00:80:41:12:34:56"},
    )
    await hass.async_block_till_done()
    r = await _options(hass, setup_entry, "connection", "connection_network")
    with patch("custom_components.eq3_max.config_flow.probe_network", return_value=True):
        r = await hass.config_entries.options.async_configure(r["flow_id"], {"host": "192.0.2.77", "port": 2323})
        await hass.async_block_till_done()
    assert r["type"] is FlowResultType.CREATE_ENTRY
    assert setup_entry.data["host"] == "192.0.2.77" and "mac" not in setup_entry.data
    with patch(PROBE, return_value="V 1.26.08 a-culfw CUBe"):
        r = await discovered(hass, ip="192.0.2.150")
    assert r["type"] is FlowResultType.MENU  # offered as a new find, nothing redirected
    assert setup_entry.data["host"] == "192.0.2.77"
