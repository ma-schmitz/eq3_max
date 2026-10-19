"""WebSocket commands of the panel (eq3_max/...)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.eq3_max.const import DOMAIN

from .conftest import FK, HT, PB, WT

SERIALS = {HT: "MEQ9000007", FK: "NEQ9000010", PB: "KEQ9000001", WT: "NEQ9000011"}


def device_id(hass, address):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, SERIALS[address])}).id


async def call(client, **msg):
    await client.send_json_auto_id(msg)
    return await client.receive_json()


async def overview(client):
    reply = await call(client, type="eq3_max/overview")
    assert reply["success"], reply
    return reply["result"]


def by_serial(section):
    return {d["serial"]: d for d in section["devices"]}


@pytest.mark.parametrize(
    "msg",
    [
        {"type": "eq3_max/overview"},
        {"type": "eq3_max/subscribe"},
        {"type": "eq3_max/link", "device_id": "x", "partner_device_id": "y"},
        {"type": "eq3_max/unlink", "device_id": "x", "partner_device_id": "y"},
        {"type": "eq3_max/pair", "entry_id": "x"},
        {"type": "eq3_max/set_config", "device_id": "x", "kind": "temp", "values": {"komfort": 21}},
    ],
)
async def test_commands_require_admin(hass, setup_entry, fake_hub, hass_ws_client, hass_read_only_access_token, msg):
    client = await hass_ws_client(hass, hass_read_only_access_token)
    reply = await call(client, **msg)
    assert not reply["success"] and reply["error"]["code"] == "unauthorized"
    assert fake_hub.last.commands == [] and fake_hub.last.pairing is None


async def test_overview_hub_section(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.airtime_last_hour = 12.345
    hub.queue_length = 2
    hub.pairing = 42
    client = await hass_ws_client(hass)
    result = await overview(client)
    assert len(result["entries"]) == 1
    section = result["entries"][0]
    assert section["entry_id"] == setup_entry.entry_id and section["loaded"] is True
    assert section["title"] == "eQ-3 MAX! C0FFEE"
    hub_info = section["hub"]
    assert hub_info["connected"] is True
    assert hub_info["connection"] == "usb" and hub_info["target"] == "/dev/serial/by-path/usb-0:13"
    assert hub_info["address"] == "C0FFEE" and hub_info["version"].startswith("V 1.66")
    assert hub_info["airtime"] == 12.3 and hub_info["airtime_limit"] == 36
    assert hub_info["queue"] == 2 and hub_info["pairing_remaining"] == 42
    hub_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")})
    assert hub_info["device_id"] == hub_device.id
    assert {d["serial"] for d in section["devices"]} == set(SERIALS.values())


async def test_overview_devices_states_areas_entities(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    bad = ar.async_get(hass).async_create("Bad")
    dr.async_get(hass).async_update_device(device_id(hass, HT), area_id=bad.id)
    dev = hub.devices[HT]
    dev.target, dev.measured, dev.valve, dev.rssi, dev.last_seen = 21.0, 19.5, 35, -61.5, 1_760_000_000.0
    dev.battery_low, dev.rf_error = False, True
    from custom_components.eq3_max.protocol.messages import Mode

    dev.mode = Mode.MANUAL
    hub.devices[FK].window_open = True
    hub.on_update(dev)
    hub.on_update(hub.devices[FK])
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    devices = by_serial((await overview(client))["entries"][0])

    ht = devices["MEQ9000007"]
    assert ht["device_id"] == device_id(hass, HT) and ht["address"] == "A1B005"
    assert ht["name"] == "ht-bad-unten" and ht["type"] == "heating_thermostat"
    assert ht["type_name"] == "Heizk\u00f6rperthermostat"
    assert ht["area_id"] == bad.id and ht["area_name"] == "Bad"
    assert ht["entity_id"] == "climate.ht_bad_unten" and ht["sleeper"] is False
    state = ht["state"]
    assert (state["target"], state["measured"], state["valve"], state["rssi"]) == (21.0, 19.5, 35, -61.5)
    assert state["mode"] == "manual" and state["hvac"] == "heat" and state["preset"] == "none"
    assert state["last_seen"] == 1_760_000_000.0 and state["rf_error"] is True and state["battery_low"] is False
    assert state["command_failed"] is False and state["config_failed"] == []
    assert ht["pending"] is False

    fk = devices["NEQ9000010"]
    assert fk["type"] == "shutter_contact" and fk["sleeper"] is True
    assert fk["area_id"] is None and fk["area_name"] is None
    assert fk["entity_id"] == "binary_sensor.fk_schlafzimmer_state"
    assert fk["state"]["window_open"] is True and fk["config"] == []
    assert devices["KEQ9000001"]["type"] == "push_button"
    assert devices["KEQ9000001"]["entity_id"] == "event.taster"
    assert devices["NEQ9000011"]["entity_id"] == "climate.wt_wohnzimmer"


async def test_overview_config_sets_with_metadata(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.devices[HT].config["eco"] = 16.5
    hub.devices[HT].config_source["eco"] = "homegear"
    hub.set_config(HT, "komfort", 22.0)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    devices = by_serial((await overview(client))["entries"][0])
    ht = devices["MEQ9000007"]
    assert ht["pending"] is True
    assert [s["kind"] for s in ht["config"]] == ["temp", "valve"]
    temp, valve = ht["config"]
    assert temp["title"] == "Temperaturen" and temp["pending"] is True and temp["failed"] is False
    values = {v["key"]: v for v in temp["values"]}
    assert list(values) == ["komfort", "eco", "maximal", "minimal", "offset", "fenster_temperatur", "fenster_dauer"]
    assert values["komfort"] == {
        "key": "komfort", "label": "Komforttemperatur", "type": "number", "min": 4.5, "max": 30.5,
        "step": 0.5, "unit": "\u00b0C", "value": 21.0, "source": "werksvorgabe", "pending": 22.0,
    }
    assert values["eco"]["source"] == "homegear" and values["eco"]["pending"] is None
    assert values["fenster_dauer"]["step"] == 5 and values["fenster_dauer"]["unit"] == "min"
    vvalues = {v["key"]: v for v in valve["values"]}
    assert valve["title"] == "Ventil" and valve["pending"] is False
    assert vvalues["boost_dauer"]["type"] == "select" and vvalues["boost_dauer"]["value"] == 5
    assert {"value": 60, "label": "60 min"} in vvalues["boost_dauer"]["options"]
    assert vvalues["entkalkung_tag"]["value"] == "Samstag"
    wt = devices["NEQ9000011"]
    assert [s["kind"] for s in wt["config"]] == ["temp"]
    assert devices["KEQ9000001"]["config"] == []


async def test_overview_links_and_candidates(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.devices[HT].links = ["NEQ9000011"]
    hub.devices[WT].links = ["MEQ9000007"]
    hub.link(FK, HT)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    devices = by_serial((await overview(client))["entries"][0])
    ht = devices["MEQ9000007"]
    assert ht["links"]["partners"] == [{"serial": "NEQ9000011", "name": "wt-wohnzimmer", "device_id": device_id(hass, WT)}]
    [pending] = ht["links"]["pending"]
    assert pending["serial"] == "NEQ9000010" and pending["name"] == "fk-schlafzimmer"
    assert pending["device_id"] == device_id(hass, FK)
    assert pending["state"] == "waiting" and pending["op"] == "add"
    assert pending["text"].startswith("wartet auf Fensterkontakt")
    # Already linked (WT) or already requested (FK): only the eco button is left.
    assert [c["serial"] for c in ht["candidates"]] == ["KEQ9000001"]
    assert ht["candidates"][0] == {"serial": "KEQ9000001", "name": "taster", "device_id": device_id(hass, PB)}
    # Contacts and buttons link only to thermostats.
    assert {c["serial"] for c in devices["KEQ9000001"]["candidates"]} == {"MEQ9000007", "NEQ9000011"}
    assert {c["serial"] for c in devices["NEQ9000010"]["candidates"]} == {"NEQ9000011"}


async def test_subscribe_pushes_debounced_until_unsubscribed(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/subscribe")
    assert reply["success"]
    sub_id = reply["id"]
    for _ in range(3):
        hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    event = await client.receive_json()
    assert event["id"] == sub_id and event["type"] == "event" and event["event"] == {"type": "update"}

    reply = await call(client, type="unsubscribe_events", subscription=sub_id)
    assert reply["success"]
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    # The next message is the reply to this ping, no further update event.
    reply = await call(client, type="ping")
    assert reply["type"] == "pong"


async def test_link_and_unlink_delegate(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/link", device_id=device_id(hass, HT), partner_device_id=device_id(hass, WT))
    assert reply["success"], reply
    assert hub.commands == [("link", HT, WT)]
    hub.devices[HT].links, hub.devices[WT].links = ["NEQ9000011"], ["MEQ9000007"]
    hub.devices[HT].pending_links, hub.devices[WT].pending_links = [], []
    reply = await call(client, type="eq3_max/unlink", device_id=device_id(hass, HT), partner_device_id=device_id(hass, WT))
    assert reply["success"], reply
    assert hub.commands[-1] == ("unlink", HT, WT)


@pytest.mark.parametrize(
    "partner,text",
    [
        (FK, "Eco-Taster und Fensterkontakt lassen sich nicht verkn\u00fcpfen"),
        ("unknown", "Unbekanntes Ger\u00e4t"),
        ("hub", "Das Funkmodul selbst kann nicht verkn\u00fcpft werden"),
        (PB, "Ein Ger\u00e4t kann nicht mit sich selbst verkn\u00fcpft werden"),
    ],
)
async def test_link_rejects_invalid_with_german_error(hass, setup_entry, fake_hub, hass_ws_client, partner, text):
    client = await hass_ws_client(hass)
    if partner == "unknown":
        partner_id = "nope"
    elif partner == "hub":
        partner_id = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")}).id
    else:
        partner_id = device_id(hass, partner)
    reply = await call(client, type="eq3_max/link", device_id=device_id(hass, PB), partner_device_id=partner_id)
    assert not reply["success"]
    assert reply["error"]["message"] == text
    assert fake_hub.last.commands == []


async def test_unlink_not_linked_german_error(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/unlink", device_id=device_id(hass, HT), partner_device_id=device_id(hass, WT))
    assert not reply["success"] and reply["error"]["message"] == "Ger\u00e4te sind nicht verkn\u00fcpft"


async def test_pair_opens_pairing(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/pair", entry_id=setup_entry.entry_id)
    assert reply["success"] and reply["result"] == {"seconds": 60}
    assert fake_hub.last.pairing == 60


async def test_pair_rejects_unknown_entry_and_disconnected_hub(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/pair", entry_id="nope")
    assert not reply["success"] and reply["error"]["message"] == "Funkmodul nicht gefunden oder nicht geladen"
    fake_hub.last.connected = False
    reply = await call(client, type="eq3_max/pair", entry_id=setup_entry.entry_id)
    assert not reply["success"] and reply["error"]["message"] == "Funkmodul nicht verbunden"
    assert fake_hub.last.pairing is None


async def test_set_config_sends_one_set_and_returns_factory_keys(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(
        client, type="eq3_max/set_config", device_id=device_id(hass, HT), kind="temp",
        values={"komfort": 22.5, "eco": "16", "fenster_dauer": 20},
    )
    assert reply["success"], reply
    assert reply["result"] == {"factory_keys": ["maximal", "minimal", "offset", "fenster_temperatur"]}
    [command] = hub.commands
    assert command[:3] == ("config_set", HT, "temp")
    assert command[3]["komfort"] == 22.5 and command[3]["eco"] == 16.0 and command[3]["fenster_dauer"] == 20

    reply = await call(
        client, type="eq3_max/set_config", device_id=device_id(hass, HT), kind="valve",
        values={"boost_dauer": "10 min", "entkalkung_tag": "Mittwoch"},
    )
    assert reply["success"], reply
    assert hub.commands[-1][3]["boost_dauer"] == 10 and hub.commands[-1][3]["entkalkung_tag"] == "Mittwoch"


@pytest.mark.parametrize(
    "address,kind,values,text",
    [
        (HT, "temp", {"komfort": 22.3}, "Komforttemperatur: Wert muss zwischen 4,5 und 30,5 in Schritten von 0,5 liegen"),
        (HT, "temp", {"boost_dauer": 10}, "Boost-Dauer geh\u00f6rt nicht zum Satz Temperaturen"),
        (HT, "temp", {}, "Keine Werte angegeben"),
        (WT, "valve", {"boost_dauer": 10}, "Ventil-Einstellungen gibt es nur bei Heizk\u00f6rperthermostaten"),
        (FK, "temp", {"komfort": 21.0}, "Dieses Ger\u00e4t hat keine Konfiguration"),
        (HT, "temp", {"bogus": 1}, "Unbekannter Konfigurationswert: bogus"),
    ],
)
async def test_set_config_rejects_invalid_with_german_error(
    hass, setup_entry, fake_hub, hass_ws_client, address, kind, values, text
):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=device_id(hass, address), kind=kind, values=values)
    assert not reply["success"]
    assert reply["error"]["message"] == text
    assert fake_hub.last.commands == [] and fake_hub.last.devices[address].pending_config == {}


async def test_set_config_rejects_bad_kind_by_schema(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=device_id(hass, HT), kind="x", values={"a": 1})
    assert not reply["success"] and reply["error"]["code"] == "invalid_format"


async def test_overview_lists_entry_not_loaded(hass, setup_entry, fake_hub, hass_ws_client):
    await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    [section] = (await overview(client))["entries"]
    assert section["loaded"] is False and section["devices"] == [] and section["hub"] is None
    assert section["state"] == "not_loaded"


async def test_unsubscribe_cancels_scheduled_push(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/subscribe")
    sub_id = reply["id"]
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    # Debounce timer is running; unsubscribing must cancel it.
    reply = await call(client, type="unsubscribe_events", subscription=sub_id)
    assert reply["success"]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    reply = await call(client, type="ping")
    assert reply["type"] == "pong"


@pytest.fixture
def foreign_device_id(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    other = MockConfigEntry(domain="other_integration")
    other.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={("other_integration", "x1")}).id


async def test_link_rejects_device_of_other_integration(hass, setup_entry, fake_hub, hass_ws_client, foreign_device_id):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/link", device_id=device_id(hass, HT), partner_device_id=foreign_device_id)
    assert not reply["success"]
    assert reply["error"]["message"] == "Ger\u00e4t geh\u00f6rt zu keiner geladenen eQ-3-MAX!-Integration"
    assert fake_hub.last.commands == []


async def test_set_config_rejects_device_of_other_integration(
    hass, setup_entry, fake_hub, hass_ws_client, foreign_device_id
):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=foreign_device_id, kind="temp", values={"komfort": 21})
    assert not reply["success"]
    assert reply["error"]["message"] == "Ger\u00e4t geh\u00f6rt zu keiner geladenen eQ-3-MAX!-Integration"
    assert fake_hub.last.commands == []


async def test_set_config_protocol_error_german_without_detail(hass, setup_entry, fake_hub, hass_ws_client, caplog):
    from custom_components.eq3_max.protocol.messages import FrameError

    hub = fake_hub.last

    def boom(address, kind, values):
        raise FrameError("comfort must be 4.5..30.5")

    hub.set_config_set = boom
    caplog.set_level("DEBUG", logger="custom_components.eq3_max.websocket_api")
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=device_id(hass, HT), kind="temp", values={"komfort": 21})
    assert not reply["success"] and reply["error"]["message"] == "Ung\u00fcltiger Wert"
    assert "comfort must be" in caplog.text
