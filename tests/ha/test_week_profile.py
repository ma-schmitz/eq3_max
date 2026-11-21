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
        ([{"temperature": 20, "until": "06:07"}, {"temperature": 21}], "5-minute steps"),
        ([{"temperature": 20, "until": "22:00"}, {"temperature": 21, "until": "08:00"}], "must increase"),
        ([{"temperature": 20}, {"temperature": 21}], "End time missing"),
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
    with pytest.raises(ServiceValidationError, match="only thermostats"):
        await call(hass, "set_week_profile", {"device_id": device_id(hass, FK_S), "weekday": "Montag", "profile": PROFILE})
    with pytest.raises(Exception, match="Blursday|weekday|Wochentag"):
        await call(hass, "set_week_profile", {"device_id": device_id(hass, HT_S), "weekday": "Blursday", "profile": PROFILE})
    assert hub.week_profiles == []


async def test_set_week_profile_radio_failure_becomes_home_assistant_error(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.week_profile_error = "ht-bad-unten: week program Monday not acknowledged (no_ack)"
    with pytest.raises(HomeAssistantError, match="not acknowledged"):
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
    with pytest.raises(ServiceValidationError, match="No week program is stored"):
        await call(hass, "copy_week_profile", {"device_id": device_id(hass, HT_S), "target_device_id": device_id(hass, WT_S)})
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    with pytest.raises(ServiceValidationError, match="to itself"):
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


async def test_set_week_profile_has_no_deadline_of_its_own(hass, setup_entry, fake_hub, monkeypatch):
    """With an empty airtime budget a whole week takes far longer than ten minutes;
    the write must not be given up half way by a deadline of the service."""
    import asyncio

    from custom_components.eq3_max import services

    monkeypatch.setattr(services, "WEEK_PROFILE_TIMEOUT_S", 0.01, raising=False)
    hub = fake_hub.last
    release = asyncio.Event()
    original = hub.set_week_profile

    async def slow(address, days, **kwargs):
        await release.wait()
        return await original(address, days, **kwargs)

    hub.set_week_profile = slow
    task = asyncio.ensure_future(
        services.async_set_week_profile(hass, [device_id(hass, HT_S)], ["Montag"], [{"temperature": 21}])
    )
    await asyncio.sleep(0.1)
    assert not task.done()
    release.set()
    await task
    assert len(hub.week_profiles) == 1


async def test_set_week_profile_takes_the_selectors_lower_case_days(hass, setup_entry, fake_hub):
    """The selector in services.yaml sends lower-case keys ("montag"); English works too."""
    hub = fake_hub.last
    await call(hass, "set_week_profile", {"device_id": device_id(hass, HT_S), "weekday": ["montag", "friday"], "profile": PROFILE})
    assert hub.week_profiles == [(HT, {2: POINTS, 6: POINTS})]


# --- several targets of one room: each thermostat is written once ---

HT2 = 0xA1B006
VWT = 0x111111
HT2_S, VWT_S = "MEQ9000025", "VIRT111111"


def _virtual_room_entry():
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    items = [
        MaxDevice(HT, HT_S, DeviceType.HEATING_THERMOSTAT, name="ht-buero1").identity_dict(),
        MaxDevice(HT2, HT2_S, DeviceType.HEATING_THERMOSTAT, name="ht-buero2").identity_dict(),
        MaxDevice(
            VWT, VWT_S, DeviceType.WALL_THERMOSTAT, name="buero", virtual=True, source="sensor.buero"
        ).identity_dict(),
    ]
    return MockConfigEntry(
        domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
        data={CONF_PORT: "/dev/serial/by-path/usb-0:13", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: items},
    )


def _link(hub, wall, *mates):
    for mate in mates:
        hub.devices[wall].links.append(hub.devices[mate].serial)
        hub.devices[mate].links.append(hub.devices[wall].serial)


async def _setup_virtual_room(hass, fake_hub):
    entry = _virtual_room_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    _link(hub, VWT, HT, HT2)
    return hub


async def test_writing_a_whole_virtual_room_writes_each_thermostat_once(hass, fake_hub):
    """The panel's area tick selects the wall thermostat and its radiators: the
    radiators get the program as its room mates, not a second time."""
    hub = await _setup_virtual_room(hass, fake_hub)
    ids = [device_id(hass, s) for s in (VWT_S, HT_S, HT2_S)]
    await call(hass, "set_week_profile", {"device_id": ids, "weekday": "Montag", "profile": PROFILE})
    assert sorted(hub.profile_writes) == sorted([HT, HT2])
    for address in (VWT, HT, HT2):
        assert hub.devices[address].week_profile["Montag"][1] == {"temperature": 21.0, "until": "22:00"}


async def test_copy_into_a_virtual_room_writes_each_thermostat_once_and_not_the_source(hass, fake_hub):
    hub = await _setup_virtual_room(hass, fake_hub)
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    await call(
        hass, "copy_week_profile",
        {"device_id": device_id(hass, HT_S), "target_device_id": [device_id(hass, VWT_S), device_id(hass, HT2_S)]},
    )
    assert hub.profile_writes == [HT2]  # HT2 as mate of the wall thermostat; the source stays as it is
    assert hub.devices[HT2].week_profile == hub.devices[VWT].week_profile == hub.devices[HT].week_profile


async def test_writing_a_whole_real_room_writes_each_thermostat_once(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    _link(hub, WT, HT)
    ids = [device_id(hass, s) for s in (WT_S, HT_S)]
    await call(hass, "set_week_profile", {"device_id": ids, "weekday": "Montag", "profile": PROFILE})
    assert sorted(hub.profile_writes) == sorted([HT, WT])
    hub.profile_writes.clear()
    await call(hass, "set_week_profile", {"device_id": ids[::-1], "weekday": "Montag", "profile": PROFILE})
    assert sorted(hub.profile_writes) == sorted([HT, WT])


# --- a target written as a room mate is still checked, waited for, and may fail the call ---

HT3, WT2 = 0xA1B012, 0xA1B014
HT3_S, WT2_S = "MEQ9000026", "NEQ9000027"


def _real_entry(*extra):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    items = [
        MaxDevice(WT, WT_S, DeviceType.WALL_THERMOSTAT, name="wt-wohnzimmer").identity_dict(),
        MaxDevice(HT, HT_S, DeviceType.HEATING_THERMOSTAT, name="ht-wohnzimmer1").identity_dict(),
        MaxDevice(HT2, HT2_S, DeviceType.HEATING_THERMOSTAT, name="ht-wohnzimmer2").identity_dict(),
        *(item.identity_dict() for item in extra),
    ]
    return MockConfigEntry(
        domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
        data={CONF_PORT: "/dev/serial/by-path/usb-0:13", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: items},
    )


async def _setup_real_room(hass, fake_hub, *extra):
    entry = _real_entry(*extra)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    _link(hub, WT, HT, HT2)
    return hub


async def test_a_target_written_as_room_mate_that_refuses_fails_the_call(hass, fake_hub):
    hub = await _setup_real_room(hass, fake_hub)
    hub.profile_refuse = {HT2}
    ids = [device_id(hass, s) for s in (WT_S, HT2_S)]
    with pytest.raises(HomeAssistantError, match="ht-wohnzimmer2"):
        await call(hass, "set_week_profile", {"device_id": ids, "weekday": "Montag", "profile": PROFILE})
    assert hub.profile_waited == [HT2]
    assert HT2 not in hub.profile_writes  # not written a second time


async def test_copy_to_a_room_mate_that_refuses_fails_the_call(hass, fake_hub):
    hub = await _setup_real_room(hass, fake_hub)
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 19.0, "until": "24:00"}]}
    hub.profile_refuse = {HT2}
    with pytest.raises(HomeAssistantError, match="ht-wohnzimmer2"):
        await call(
            hass, "copy_week_profile",
            {"device_id": device_id(hass, HT_S), "target_device_id": [device_id(hass, WT_S), device_id(hass, HT2_S)]},
        )
    assert hub.profile_writes == [WT]  # the source is not written, HT2 refused as room mate


async def test_the_call_returns_only_after_a_target_written_as_room_mate_is_done(hass, fake_hub):
    import asyncio

    from custom_components.eq3_max import services

    hub = await _setup_real_room(hass, fake_hub)
    hub.profile_gate = asyncio.Event()
    task = asyncio.ensure_future(
        services.async_set_week_profile(hass, [device_id(hass, WT_S), device_id(hass, HT2_S)], ["Montag"], PROFILE)
    )
    await asyncio.sleep(0.05)
    assert not task.done() and sorted(hub.profile_writes) == sorted([WT, HT, HT2])
    hub.profile_gate.set()
    devices = await asyncio.wait_for(task, 1.0)
    assert hub.profile_waited == [HT2] and [d.address for d in devices] == [WT, HT2]


async def test_a_target_written_as_room_mate_on_a_disconnected_module_is_refused(hass, fake_hub):
    hub = await _setup_real_room(hass, fake_hub)
    hub.devices[HT2].radio = "cube"
    hub.radio_connected["cube"] = False
    ids = [device_id(hass, s) for s in (WT_S, HT2_S)]
    with pytest.raises(HomeAssistantError, match="ht-wohnzimmer2"):
        await call(hass, "set_week_profile", {"device_id": ids, "weekday": "Montag", "profile": PROFILE})


async def test_a_target_is_not_skipped_when_the_earlier_one_only_joined_a_running_write(hass, fake_hub):
    """Overlapping rooms: HT2 is linked to WT and WT2, HT3 to WT2 only. HT2 is still being
    written with the same days as a mate of another call: joining that does not reach
    HT3, so HT3 is written itself."""
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    hub = await _setup_real_room(
        hass, fake_hub,
        MaxDevice(WT2, WT2_S, DeviceType.WALL_THERMOSTAT, name="wt-esszimmer"),
        MaxDevice(HT3, HT3_S, DeviceType.HEATING_THERMOSTAT, name="ht-esszimmer"),
    )
    _link(hub, WT2, HT2, HT3)
    hub.profile_running[HT2] = {2: POINTS}
    await call(
        hass, "set_week_profile",
        {"device_id": [device_id(hass, HT2_S), device_id(hass, HT3_S)], "weekday": "Montag", "profile": PROFILE},
    )
    assert HT3 in hub.profile_writes
    assert hub.devices[HT3].week_profile["Montag"][1] == {"temperature": 21.0, "until": "22:00"}
