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
        {"type": "eq3_max/rename_radio", "entry_id": "x", "radio": "", "name": "EG"},
        {"type": "eq3_max/set_config", "device_id": "x", "kind": "temp", "values": {"komfort": 21}},
        {"type": "eq3_max/set_week_profile", "device_id": "x", "weekday": ["Montag"], "profile": [{"temperature": 21}]},
        {"type": "eq3_max/copy_week_profile", "device_id": "x", "target_device_id": ["y"]},
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
    assert [s["kind"] for s in wt["config"]] == ["temp", "valve"]
    # Of the valve set a wall thermostat only has the boost duration.
    assert [v["key"] for v in wt["config"][1]["values"]] == ["boost_dauer"]
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
    "partner,key",
    [
        (FK, "link_not_allowed"),
        ("unknown", "device_id_unknown"),
        ("hub", "hub_cannot_link"),
        (PB, "link_self"),
    ],
)
async def test_link_rejects_invalid_with_translated_error(hass, setup_entry, fake_hub, hass_ws_client, partner, key):
    client = await hass_ws_client(hass)
    if partner == "unknown":
        partner_id = "nope"
    elif partner == "hub":
        partner_id = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")}).id
    else:
        partner_id = device_id(hass, partner)
    reply = await call(client, type="eq3_max/link", device_id=device_id(hass, PB), partner_device_id=partner_id)
    assert not reply["success"]
    # The panel shows the text for the key in the user's language.
    assert reply["error"]["translation_key"] == key and reply["error"]["translation_domain"] == DOMAIN
    assert fake_hub.last.commands == []


async def test_unlink_not_linked_german_error(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/unlink", device_id=device_id(hass, HT), partner_device_id=device_id(hass, WT))
    assert not reply["success"] and reply["error"]["translation_key"] == "not_linked"


async def test_pair_opens_pairing(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/pair", entry_id=setup_entry.entry_id)
    assert reply["success"] and reply["result"] == {"seconds": 60}
    assert fake_hub.last.pairing == 60


async def test_pair_rejects_unknown_entry_and_disconnected_hub(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/pair", entry_id="nope")
    assert not reply["success"] and reply["error"]["translation_key"] == "hub_not_loaded"
    fake_hub.last.connected = False
    reply = await call(client, type="eq3_max/pair", entry_id=setup_entry.entry_id)
    assert not reply["success"] and reply["error"]["translation_key"] == "not_connected"
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
    "address,kind,values,key",
    [
        (HT, "temp", {"komfort": 22.3}, "config_value_range"),
        (HT, "temp", {"boost_dauer": 10}, "config_key_wrong_set"),
        (HT, "temp", {}, "config_no_values"),
        (WT, "valve", {"ventil_max": 80}, "config_key_not_on_device"),
        (PB, "valve", {"boost_dauer": 10}, "config_none"),
        (FK, "temp", {"komfort": 21.0}, "config_none"),
        (HT, "temp", {"bogus": 1}, "config_key_unknown"),
    ],
)
async def test_set_config_rejects_invalid_with_translated_error(
    hass, setup_entry, fake_hub, hass_ws_client, address, kind, values, key
):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=device_id(hass, address), kind=kind, values=values)
    assert not reply["success"]
    # The panel shows the text for the key in the user's language.
    assert reply["error"]["translation_key"] == key and reply["error"]["translation_domain"] == DOMAIN
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
    assert reply["error"]["translation_key"] == "device_not_loaded"
    assert fake_hub.last.commands == []


async def test_set_config_rejects_device_of_other_integration(
    hass, setup_entry, fake_hub, hass_ws_client, foreign_device_id
):
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_config", device_id=foreign_device_id, kind="temp", values={"komfort": 21})
    assert not reply["success"]
    assert reply["error"]["translation_key"] == "device_not_loaded"
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
    assert not reply["success"] and reply["error"]["translation_key"] == "invalid_value"
    assert "comfort must be" in caplog.text


# --- Week profile ---


async def test_set_week_profile_over_websocket(hass, setup_entry, fake_hub, hass_ws_client):
    from custom_components.eq3_max.protocol.messages import ProfilePoint

    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(
        client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT), weekday=["Montag", "alle"],
        profile=[{"temperature": 17, "until": "06:00"}, {"temperature": 21}],
    )
    assert reply["success"], reply
    [(address, plan)] = hub.week_profiles
    assert address == HT and sorted(plan) == [0, 1, 2, 3, 4, 5, 6]
    assert plan[2] == [ProfilePoint(17.0, 360), ProfilePoint(21.0, 1440)]
    assert reply["result"]["week_profile"]["Montag"][0] == {"temperature": 17.0, "until": "06:00"}

    reply = await call(client, type="eq3_max/set_week_profile", device_id=device_id(hass, FK), weekday=["Montag"], profile=[{"temperature": 21}])
    assert not reply["success"] and reply["error"]["code"] == "invalid" and reply["error"]["translation_key"] == "no_week_profile"
    reply = await call(
        client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT), weekday=["Montag"],
        profile=[{"temperature": 21, "until": "06:07"}, {"temperature": 21}],
    )
    assert not reply["success"] and reply["error"]["translation_key"] == "profile_until_step"
    reply = await call(client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT), weekday=["Blursday"], profile=[{"temperature": 21}])
    assert not reply["success"] and reply["error"]["translation_key"] == "weekday_unknown"
    assert len(hub.week_profiles) == 1

    hub.week_profile_error = "ht-bad-unten: week program Monday not acknowledged (no_ack)"
    reply = await call(client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT), weekday=["Montag"], profile=[{"temperature": 21}])
    assert not reply["success"] and reply["error"]["code"] == "failed" and "not acknowledged" in reply["error"]["message"]


async def test_copy_week_profile_over_websocket(hass, setup_entry, fake_hub, hass_ws_client):
    from custom_components.eq3_max.protocol.messages import ProfilePoint

    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/copy_week_profile", device_id=device_id(hass, HT), target_device_id=[device_id(hass, WT)])
    assert not reply["success"] and reply["error"]["translation_key"] == "week_profile_not_stored"
    hub.devices[HT].week_profile = {"Sonntag": [{"temperature": 19.0, "until": "24:00"}]}
    reply = await call(client, type="eq3_max/copy_week_profile", device_id=device_id(hass, HT), target_device_id=[device_id(hass, WT)])
    assert reply["success"], reply
    assert hub.week_profiles == [(WT, {1: [ProfilePoint(19.0, 1440)]})]
    assert reply["result"]["targets"] == [SERIALS[WT]]


async def test_overview_carries_the_factory_week_profile(hass, setup_entry, fake_hub, hass_ws_client):
    client = await hass_ws_client(hass)
    result = await overview(client)
    factory = result["factory_week_profile"]
    assert list(factory) == ["Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
    assert factory["Sonntag"] == [{"temperature": 17.0, "until": "06:00"}, {"temperature": 21.0, "until": "22:00"}, {"temperature": 17.0, "until": "24:00"}]
    assert factory["Montag"][1] == {"temperature": 21.0, "until": "09:00"} and len(factory["Montag"]) == 5


async def test_set_week_profile_days_with_different_programs_is_one_write(hass, setup_entry, fake_hub, hass_ws_client):
    """The factory program differs between weekdays and weekend: one request and one
    write of the hub, so it does not depend on the page staying open in between."""
    from custom_components.eq3_max.protocol.messages import ProfilePoint

    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(
        client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT),
        days={
            "Montag": [{"temperature": 17, "until": "06:00"}, {"temperature": 21}],
            "Samstag": [{"temperature": 19}],
        },
    )
    assert reply["success"], reply
    [(address, plan)] = hub.week_profiles
    assert address == HT
    assert plan == {0: [ProfilePoint(19.0, 1440)], 2: [ProfilePoint(17.0, 360), ProfilePoint(21.0, 1440)]}

    for bad in (
        {"days": {"Blursday": [{"temperature": 21}]}},
        {"days": {}},
        {"days": {"Montag": [{"temperature": 21}]}, "weekday": ["Montag"], "profile": [{"temperature": 21}]},
        {"weekday": ["Montag"]},
        {},
    ):
        reply = await call(client, type="eq3_max/set_week_profile", device_id=device_id(hass, HT), **bad)
        assert not reply["success"], bad
    assert len(hub.week_profiles) == 1


async def test_overview_shows_a_running_week_profile_write_and_the_budget_wait(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    result = (await call(client, type="eq3_max/overview"))["result"]["entries"][0]
    dev = next(d for d in result["devices"] if d["serial"] == "MEQ9000007")
    assert dev["week_profile_writing"] == [] and dev["week_profile_error"] is None
    assert result["hub"]["radios"][0]["waiting_budget"] is False

    hub.devices[HT].week_profile_writing = ["Dienstag", "Mittwoch"]
    hub.devices[HT].week_profile_error = "abgelehnt"
    hub.waiting_budget = True
    result = (await call(client, type="eq3_max/overview"))["result"]["entries"][0]
    dev = next(d for d in result["devices"] if d["serial"] == "MEQ9000007")
    assert dev["week_profile_writing"] == ["Dienstag", "Mittwoch"] and dev["week_profile_error"] == "abgelehnt"
    assert dev["pending"] is True
    assert result["hub"]["radios"][0]["waiting_budget"] is True


async def test_forced_unlink_over_websocket_and_service(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(
        client, type="eq3_max/unlink", device_id=device_id(hass, WT), partner_device_id=device_id(hass, HT), force=True
    )
    assert reply["success"], reply
    assert hub.commands[-1] == ("unlink", WT, HT, "force")
    await hass.services.async_call(
        DOMAIN, "unlink", {"device_id": device_id(hass, FK), "partner_device_id": device_id(hass, HT), "force": True},
        blocking=True,
    )
    assert hub.commands[-1] == ("unlink", FK, HT, "force")


async def test_set_time_over_websocket_and_service(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    reply = await call(client, type="eq3_max/set_time", device_id=device_id(hass, WT))
    assert reply["success"], reply
    assert hub.commands[-1] == ("time", WT)
    await hass.services.async_call(DOMAIN, "set_time", {"device_id": [device_id(hass, HT), device_id(hass, WT)]}, blocking=True)
    assert hub.commands[-2:] == [("time", HT), ("time", WT)]
    reply = await call(client, type="eq3_max/set_time", device_id=device_id(hass, FK))
    assert not reply["success"] and reply["error"]["translation_key"] == "no_clock"
    hub.time_error = "wt-wohnzimmer: clock not acknowledged (no_ack)"
    reply = await call(client, type="eq3_max/set_time", device_id=device_id(hass, WT))
    assert not reply["success"] and "not acknowledged" in reply["error"]["message"]
