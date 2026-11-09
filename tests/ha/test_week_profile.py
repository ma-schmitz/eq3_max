"""Services set_week_profile and copy_week_profile."""

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.eq3_max.const import DOMAIN
from custom_components.eq3_max.protocol.messages import ProfilePoint

from .conftest import HT, WT

HT_S, WT_S, FK_S = "MEQ9000007", "NEQ9000011", "NEQ9000010"


def device_id(hass, serial):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, serial)}).id


async def call(hass, service, data):
    await hass.services.async_call(DOMAIN, service, data, blocking=True)
    await hass.async_block_till_done()


PROFILE = [
    {"temperature": 17, "until": "06:00"},
    {"temperature": 21.0, "until": "22:00"},
    {"temperature": 17},
]
POINTS = [ProfilePoint(17.0, 360), ProfilePoint(21.0, 1320), ProfilePoint(17.0, 1440)]


async def test_set_week_profile_writes_days_and_shows_up_in_state(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await call(hass, "set_week_profile", {"device_id": device_id(hass, HT_S), "weekday": ["Montag", "Freitag"], "profile": PROFILE})
    assert hub.week_profiles == [(HT, {2: POINTS, 6: POINTS})]
    assert hub.devices[HT].week_profile["Montag"][1] == {"temperature": 21.0, "until": "22:00"}
    assert hub.devices[HT].week_profile["Montag"][2]["until"] == "24:00"


async def test_set_week_profile_for_several_devices_and_all_days(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await call(
        hass,
        "set_week_profile",
        {"device_id": [device_id(hass, HT_S), device_id(hass, WT_S)], "weekday": "alle", "profile": [{"temperature": 20, "until": "24:00"}]},
    )
    assert [a for a, _ in hub.week_profiles] == [HT, WT]
    assert sorted(hub.week_profiles[0][1]) == [0, 1, 2, 3, 4, 5, 6]
    assert hub.week_profiles[1][1][0] == [ProfilePoint(20.0, 1440)]


@pytest.mark.parametrize(
    ("profile", "text"),
    [
        ([{"temperature": 20, "until": "6:00"}, {"temperature": 21, "until": "24:00"}], None),  # ok: h:mm
        ([{"temperature": 20, "until": "06:07"}, {"temperature": 21}], "5-Minuten"),
        ([{"temperature": 20, "until": "22:00"}, {"temperature": 21, "until": "08:00"}], "aufsteigend"),
        ([{"temperature": 20}, {"temperature": 21}], "Bis-Uhrzeit"),
        ([{"temperature": 20, "until": "22:00"}], "24:00"),
        ([{"temperature": 20, "until": "x"}], "hh:mm"),
        ([{"temperature": 3, "until": "24:00"}], "4.5"),
        ([{"temperature": 20.3, "until": "24:00"}], "0.5"),
        ([{"temperature": 20, "until": "01:00"}] * 13 + [{"temperature": 20}], "13"),
    ],
)
async def test_set_week_profile_validates_points_in_german(hass, setup_entry, fake_hub, profile, text):
    hub = fake_hub.last
    data = {"device_id": device_id(hass, HT_S), "weekday": "Montag", "profile": profile}
    if text is None:
        await call(hass, "set_week_profile", data)
        assert hub.week_profiles[0][1][2][0] == ProfilePoint(20.0, 360)
        return
    with pytest.raises((ServiceValidationError, HomeAssistantError), match=text):
        await call(hass, "set_week_profile", data)
    assert hub.week_profiles == []


async def test_set_week_profile_refuses_contacts_and_unknown_days(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    with pytest.raises(ServiceValidationError, match="Thermostat"):
        await call(hass, "set_week_profile", {"device_id": device_id(hass, FK_S), "weekday": "Montag", "profile": PROFILE})
    with pytest.raises(Exception, match="Blursday|weekday|Wochentag"):
        await call(hass, "set_week_profile", {"device_id": device_id(hass, HT_S), "weekday": "Blursday", "profile": PROFILE})
    assert hub.week_profiles == []


async def test_set_week_profile_radio_failure_becomes_home_assistant_error(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.week_profile_error = "ht-bad-unten: Wochenprogramm Montag nicht quittiert (no_ack)"
    with pytest.raises(HomeAssistantError, match="nicht quittiert"):
        await call(hass, "set_week_profile", {"device_id": device_id(hass, HT_S), "weekday": "Montag", "profile": PROFILE})


async def test_copy_week_profile_sends_the_stored_days_to_the_targets(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.devices[HT].week_profile = {
        "Montag": [{"temperature": 17.0, "until": "06:00"}, {"temperature": 21.0, "until": "22:00"}, {"temperature": 17.0, "until": "24:00"}],
        "Sonntag": [{"temperature": 19.0, "until": "24:00"}],
    }
    await call(hass, "copy_week_profile", {"device_id": device_id(hass, HT_S), "target_device_id": [device_id(hass, WT_S)]})
    assert hub.week_profiles == [(WT, {1: [ProfilePoint(19.0, 1440)], 2: POINTS})]
    assert hub.devices[WT].week_profile == hub.devices[HT].week_profile


async def test_copy_week_profile_needs_a_stored_profile_and_other_targets(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    with pytest.raises(ServiceValidationError, match="kein Wochenprogramm"):
        await call(hass, "copy_week_profile", {"device_id": device_id(hass, HT_S), "target_device_id": device_id(hass, WT_S)})
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    with pytest.raises(ServiceValidationError, match="selbst"):
        await call(hass, "copy_week_profile", {"device_id": device_id(hass, HT_S), "target_device_id": device_id(hass, HT_S)})
    assert hub.week_profiles == []


async def test_week_profile_is_part_of_the_panel_overview(hass, setup_entry, fake_hub, hass_ws_client):
    hub = fake_hub.last
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "eq3_max/overview"})
    msg = await client.receive_json()
    assert msg["success"]
    devices = {d["serial"]: d for d in msg["result"]["entries"][0]["devices"]}
    assert devices[HT_S]["week_profile"] == {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    assert devices[WT_S]["week_profile"] == {}
