"""HA layer of virtual devices: source, availability, entities, removal."""

from __future__ import annotations

import pytest
from homeassistant.components.climate import ATTR_HVAC_ACTION
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT, DOMAIN, signal_update
from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.messages import DeviceType, Mode
from custom_components.eq3_max.virtual_source import read_temperature, read_window

from .conftest import HT, FakeHub

VSC = 0x222222
VWT = 0x111111


def virtual_items():
    return [
        MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten").identity_dict(),
        MaxDevice(
            VSC, "VIRT222222", DeviceType.SHUTTER_CONTACT, name="fenster-kueche", virtual=True, source="binary_sensor.kueche"
        ).identity_dict(),
        MaxDevice(
            VWT, "VIRT111111", DeviceType.WALL_THERMOSTAT, name="buero", virtual=True, source="sensor.buero"
        ).identity_dict(),
    ]


def make_entry(**extra):
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="C0FFEE",
        title="eQ-3 MAX! C0FFEE",
        data={CONF_PORT: "/dev/serial/by-path/usb-0:13", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: virtual_items(), **extra},
    )


@pytest.fixture
def virtual_entry():
    return make_entry()


async def setup_entry(hass, entry, fake_hub):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def entity_id(hass, domain, uid):
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, uid)


def item(entry, address):
    return next((i for i in entry.data[CONF_DEVICES] if i["address"] == address), None)


# --- source ---


async def test_source_values_reach_the_hub(hass, virtual_entry, fake_hub):
    hass.states.async_set("binary_sensor.kueche", "on")
    hass.states.async_set("sensor.buero", "21.4", {"unit_of_measurement": "°C", "device_class": "temperature"})
    await setup_entry(hass, virtual_entry, fake_hub)
    assert ("set_window", VSC, True) in FakeHub.last.commands
    assert ("set_measured", VWT, 21.4) in FakeHub.last.commands
    hass.states.async_set("binary_sensor.kueche", "off")
    await hass.async_block_till_done()
    assert FakeHub.last.commands[-1] == ("set_window", VSC, False)
    hass.states.async_set("sensor.buero", "22.0", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert FakeHub.last.commands[-1] == ("set_measured", VWT, 22.0)


@pytest.mark.parametrize("state", ["unavailable", "unknown", "abc", "nan", "inf"])
async def test_unreadable_source_is_none(hass, virtual_entry, fake_hub, state):
    hass.states.async_set("sensor.buero", state)
    hass.states.async_set("binary_sensor.kueche", state)
    await setup_entry(hass, virtual_entry, fake_hub)
    assert ("set_measured", VWT, None) in FakeHub.last.commands
    assert ("set_window", VSC, None) in FakeHub.last.commands


async def test_missing_source_is_none_until_it_appears(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    assert ("set_window", VSC, None) in FakeHub.last.commands
    assert ("set_measured", VWT, None) in FakeHub.last.commands
    hass.states.async_set("binary_sensor.kueche", "on")
    await hass.async_block_till_done()
    assert FakeHub.last.commands[-1] == ("set_window", VSC, True)


async def test_fahrenheit_is_converted(hass):
    hass.states.async_set("sensor.f", "71.6", {"unit_of_measurement": "°F"})
    assert read_temperature(hass, "sensor.f") == pytest.approx(22.0)
    hass.states.async_set("sensor.k", "295.15", {"unit_of_measurement": "K"})
    assert read_temperature(hass, "sensor.k") == pytest.approx(22.0)
    hass.states.async_set("sensor.c", "-3.5", {"unit_of_measurement": "°C"})
    assert read_temperature(hass, "sensor.c") == -3.5
    assert read_temperature(hass, "sensor.missing") is None


async def test_read_window(hass):
    for state, expected in (("on", True), ("off", False), ("unavailable", None), ("unknown", None), ("open", None)):
        hass.states.async_set("binary_sensor.w", state)
        assert read_window(hass, "binary_sensor.w") is expected
    assert read_window(hass, "binary_sensor.missing") is None


async def test_removing_device_gets_no_pushes(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    hub.devices[VSC].removing = True
    count = len(hub.commands)
    hass.states.async_set("binary_sensor.kueche", "on")
    await hass.async_block_till_done()
    assert hub.commands[count:] == []


async def test_listening_ends_with_the_entry(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    assert await hass.config_entries.async_unload(virtual_entry.entry_id)
    count = len(hub.commands)
    hass.states.async_set("binary_sensor.kueche", "on")
    await hass.async_block_till_done()
    assert hub.commands[count:] == []


async def test_changing_the_source_writes_the_entry_and_listens_to_the_new_one(hass, virtual_entry, fake_hub):
    hass.states.async_set("binary_sensor.flur", "on")
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    coordinator = virtual_entry.runtime_data
    coordinator.async_set_virtual_source(VSC, "binary_sensor.flur")
    await hass.async_block_till_done()
    assert hub.devices[VSC].source == "binary_sensor.flur"
    assert item(virtual_entry, VSC)["source"] == "binary_sensor.flur"
    assert hub.commands[-1] == ("set_window", VSC, True)
    count = len(hub.commands)
    hass.states.async_set("binary_sensor.kueche", "on")
    await hass.async_block_till_done()
    assert hub.commands[count:] == []
    hass.states.async_set("binary_sensor.flur", "off")
    await hass.async_block_till_done()
    assert hub.commands[-1] == ("set_window", VSC, False)
    # No reload: the same hub and coordinator.
    assert FakeHub.last is hub and virtual_entry.runtime_data is coordinator


async def test_source_of_a_real_device_cannot_be_set(hass, virtual_entry, fake_hub):
    from custom_components.eq3_max.protocol.messages import FrameError

    await setup_entry(hass, virtual_entry, fake_hub)
    with pytest.raises(FrameError) as err:
        virtual_entry.runtime_data.async_set_virtual_source(HT, "binary_sensor.flur")
    assert err.value.key == "not_virtual"


async def test_removing_reaches_the_entry_and_survives_a_reload(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    assert "removing" not in item(virtual_entry, VSC)
    hub.devices[VSC].removing = True
    hub.on_update(hub.devices[VSC])
    await hass.async_block_till_done()
    assert item(virtual_entry, VSC)["removing"] is True
    assert FakeHub.last is hub  # written without a reload
    assert await hass.config_entries.async_reload(virtual_entry.entry_id)
    await hass.async_block_till_done()
    assert FakeHub.last is not hub and FakeHub.last.devices[VSC].removing is True


async def test_real_device_entry_item_has_no_virtual_keys(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    hub.devices[HT].links = ["VIRT222222"]
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    assert not {"virtual", "source", "removing"} & set(item(virtual_entry, HT))


# --- entities ---


async def test_virtual_devices_have_no_battery_rssi_or_radio_error(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    ids = [e.unique_id for e in er.async_entries_for_config_entry(er.async_get(hass), virtual_entry.entry_id)]
    virt = sorted(i for i in ids if i.startswith("VIRT"))
    assert not [i for i in virt if i.rsplit("_", 1)[1] in ("lowbat", "rssi", "funkfehler", "gesperrt", "gemeldet", "funkmodul")]
    assert "VIRT222222_state" in ids and "VIRT222222_verknuepfungen" in ids
    assert [i for i in virt if i.startswith("VIRT222222")] == ["VIRT222222_state", "VIRT222222_verknuepfungen"]
    assert "VIRT111111_verknuepfungen" in ids and "VIRT111111_komfort" in ids
    assert hass.states.get("climate.buero") is not None


async def test_entities_unavailable_while_the_source_is_missing(hass, virtual_entry, fake_hub):
    hass.states.async_set("binary_sensor.kueche", "on")
    await setup_entry(hass, virtual_entry, fake_hub)
    window = entity_id(hass, "binary_sensor", "VIRT222222_state")
    links = entity_id(hass, "sensor", "VIRT222222_verknuepfungen")
    assert hass.states.get(window).state == "on"
    dev = FakeHub.last.devices[VSC]
    dev.source_ok = False
    async_dispatcher_send(hass, signal_update(virtual_entry.entry_id), dev.address)
    await hass.async_block_till_done()
    assert hass.states.get(window).state == "unavailable"
    # Only what shows the source's value: links stay readable.
    assert hass.states.get(links).state != "unavailable"
    hass.states.async_set("binary_sensor.kueche", "off")
    await hass.async_block_till_done()
    assert hass.states.get(window).state == "off"


async def test_virtual_wall_thermostat_climate(hass, virtual_entry, fake_hub):
    hass.states.async_set("sensor.buero", "20.5", {"unit_of_measurement": "°C"})
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    st = hass.states.get("climate.buero")
    assert st.attributes["current_temperature"] == 20.5
    assert st.attributes.get(ATTR_HVAC_ACTION) is None
    await hass.services.async_call(
        "climate", "set_temperature", {ATTR_ENTITY_ID: "climate.buero", ATTR_TEMPERATURE: 19.0}, blocking=True
    )
    assert hub.commands[-1] == (VWT, 19.0, Mode.MANUAL)
    hass.states.async_set("sensor.buero", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get("climate.buero").state == "unavailable"
    # Settings and links stay usable without a working sensor.
    for domain, uid in (("number", "VIRT111111_komfort"), ("sensor", "VIRT111111_verknuepfungen")):
        assert hass.states.get(entity_id(hass, domain, uid)).state != "unavailable", uid


async def test_entities_of_a_device_gone_from_the_hub_are_unavailable(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    platform_entities = [
        e for e in hass.data["entity_components"]["number"].entities if e.unique_id == "VIRT111111_komfort"
    ]
    del FakeHub.last.devices[VWT]
    assert platform_entities and platform_entities[0].available is False


async def test_virtual_device_has_no_radio_to_address(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "VIRT111111")})
    for service in ("set_time", "factory_reset"):
        with pytest.raises(HomeAssistantError) as err:
            await hass.services.async_call(DOMAIN, service, {"device_id": device.id}, blocking=True)
        assert err.value.translation_key == "virtual_no_radio"


async def test_device_page_names_the_virtual_models(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    dev_reg = dr.async_get(hass)
    contact = dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT222222")})
    wall = dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT111111")})
    assert (contact.manufacturer, contact.model) == ("eQ-3", "Virtual window contact")
    assert (wall.manufacturer, wall.model) == ("eQ-3", "Virtual wall thermostat")
    assert contact.hw_version == "RF 222222"


async def test_no_radio_select_for_virtual_devices(hass, fake_hub):
    entry = make_entry(radios=[{"id": "r2", "name": "OG", "connection": "network", "host": "192.0.2.60", "port": 2323}])
    await setup_entry(hass, entry, fake_hub)
    assert entity_id(hass, "select", "MEQ9000007_funkmodul") is not None
    assert entity_id(hass, "select", "VIRT222222_funkmodul") is None
    assert entity_id(hass, "select", "VIRT111111_funkmodul") is None


# --- removal ---


async def test_device_page_removes_a_virtual_device_without_reload(hass, virtual_entry, fake_hub):
    from custom_components.eq3_max import async_remove_config_entry_device

    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    window = entity_id(hass, "binary_sensor", "VIRT222222_state")
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT222222")})
    assert await async_remove_config_entry_device(hass, virtual_entry, device) is True
    await hass.async_block_till_done()
    assert ("remove_virtual", VSC, False) in hub.commands
    assert item(virtual_entry, VSC) is None
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT222222")}) is None
    assert entity_id(hass, "binary_sensor", "VIRT222222_state") is None
    assert hass.states.get(window) is None
    assert FakeHub.last is hub and virtual_entry.state is ConfigEntryState.LOADED
    # Its source is no longer listened to.
    count = len(hub.commands)
    hass.states.async_set("binary_sensor.kueche", "on")
    await hass.async_block_till_done()
    assert hub.commands[count:] == []


async def test_device_page_remove_waits_for_the_partners(hass, virtual_entry, fake_hub):
    from custom_components.eq3_max import async_remove_config_entry_device

    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    hub.virtual.remove_result = False
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT111111")})
    assert await async_remove_config_entry_device(hass, virtual_entry, device) is False
    await hass.async_block_till_done()
    assert item(virtual_entry, VWT)["removing"] is True
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT111111")}) is not None
    # The last partner acknowledged: the hub reports it gone.
    hub.virtual.finish_removal(VWT)
    await hass.async_block_till_done()
    assert item(virtual_entry, VWT) is None
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "VIRT111111")}) is None
    assert hass.states.get("climate.buero") is None
    assert FakeHub.last is hub


async def test_virtual_device_is_forgotten_while_the_entry_is_not_loaded(hass, virtual_entry, fake_hub):
    from custom_components.eq3_max import async_remove_config_entry_device

    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "VIRT222222")})
    assert await hass.config_entries.async_unload(virtual_entry.entry_id)
    assert await async_remove_config_entry_device(hass, virtual_entry, device) is True
    assert item(virtual_entry, VSC) is None and item(virtual_entry, VWT) is not None
    assert not [c for c in hub.commands if c[0] == "remove_virtual"]


# --- device store ---


async def test_store_keeps_what_was_delivered_and_adopted(hass, virtual_entry, fake_hub):
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    contact, wall = hub.devices[VSC], hub.devices[VWT]
    contact.delivered["MEQ9000007"] = True
    hub.on_update(contact)
    wall.target, wall.mode = 19.5, Mode.AUTO
    hub.on_update(wall)
    await hass.async_block_till_done()
    saved = virtual_entry.runtime_data._data_to_save()["devices"]
    assert saved[str(VSC)]["delivered"] == {"MEQ9000007": True}
    assert saved[str(VWT)]["target"] == 19.5


async def test_a_silent_temperature_source_counts_as_unavailable(hass, virtual_entry, fake_hub, freezer):
    """A sensor with a dead battery often keeps its last value: after three hours without
    a report it counts as unavailable, noticed without a state change."""
    freezer.move_to("2026-10-09T10:00:00+00:00")
    hass.states.async_set("sensor.buero", "21.4", {"unit_of_measurement": "°C"})
    await setup_entry(hass, virtual_entry, fake_hub)
    assert FakeHub.last.commands[-1] == ("set_measured", VWT, 21.4) or ("set_measured", VWT, 21.4) in FakeHub.last.commands
    freezer.move_to("2026-10-09T12:59:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert read_temperature(hass, "sensor.buero") == 21.4
    hass.states.async_set("sensor.buero", "21.4", {"unit_of_measurement": "°C"})   # reported again, same value
    freezer.move_to("2026-10-09T15:58:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert read_temperature(hass, "sensor.buero") == 21.4
    FakeHub.last.commands.clear()
    freezer.move_to("2026-10-09T16:01:00+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert read_temperature(hass, "sensor.buero") is None
    assert ("set_measured", VWT, None) in FakeHub.last.commands


# --- Automatic mode needs a known week program ---


async def test_wall_without_program_offers_no_automatic_mode(hass, virtual_entry, fake_hub):
    from homeassistant.components.climate import HVACMode
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.eq3_max.protocol.devices import WEEKDAYS

    hass.states.async_set("sensor.buero", "20.5", {"unit_of_measurement": "°C"})
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    assert hass.states.get("climate.buero").attributes["hvac_modes"] == [HVACMode.HEAT, HVACMode.OFF]
    assert HVACMode.AUTO in hass.states.get("climate.ht_bad_unten").attributes["hvac_modes"]   # real: unchanged
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "climate", "set_hvac_mode", {ATTR_ENTITY_ID: "climate.buero", "hvac_mode": "auto"}, blocking=True
        )
    assert err.value.translation_key == "not_valid_hvac_mode"                  # not offered: HA refuses
    assert not any(Mode.AUTO in c for c in hub.commands if isinstance(c, tuple))
    hub.devices[VWT].week_profile = {day: [{"temperature": 19.0, "until": "24:00"}] for day in WEEKDAYS}
    hub.on_update(hub.devices[VWT])
    await hass.async_block_till_done()
    assert HVACMode.AUTO in hass.states.get("climate.buero").attributes["hvac_modes"]


async def test_a_stored_module_of_a_virtual_device_is_not_shown(hass, fake_hub, hass_ws_client):
    """F9: a virtual device has no module of its own; one stored earlier ("r2") is ignored."""
    items = virtual_items()
    items[2]["radio"] = "r2"
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
        data={CONF_PORT: "/dev/serial/by-path/usb-0:13", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: items,
              "radios": [{"id": "r2", "name": "OG", "connection": "network", "host": "192.0.2.60", "port": 2323}]},
    )
    await setup_entry(hass, entry, fake_hub)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "eq3_max/overview"})
    reply = await client.receive_json()
    devs = {d["serial"]: d for d in reply["result"]["entries"][0]["devices"]}
    assert devs["VIRT111111"]["radio"] == ""


async def test_room_without_program_sends_setpoints_manual_even_if_a_member_reports_auto(
    hass, virtual_entry, fake_hub
):
    """Without a known week program the room has no automatic mode: a setpoint (or the
    comfort/eco preset) from a member thermostat that momentarily reports AUTO goes out
    manual, never as an error. An explicit request for AUTO still fails."""
    from homeassistant.exceptions import ServiceValidationError

    hass.states.async_set("sensor.buero", "20.5", {"unit_of_measurement": "°C"})
    await setup_entry(hass, virtual_entry, fake_hub)
    hub = FakeHub.last
    ht, wall = hub.devices[HT], hub.devices[VWT]
    ht.links, wall.links = [wall.serial], [ht.serial]
    ht.config["komfort"], ht.config["eco"] = 21.5, 16.5
    ht.target, ht.mode = 19.0, Mode.AUTO
    hub.on_update(ht)
    await hass.async_block_till_done()
    e = "climate.ht_bad_unten"
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: e, ATTR_TEMPERATURE: 22.0}, blocking=True)
    assert hub.commands[-1] == (HT, 22.0, Mode.MANUAL)
    ht.clear_pending()
    for preset, value in (("comfort", 21.5), ("eco", 16.5)):
        await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: e, "preset_mode": preset}, blocking=True)
        assert hub.commands[-1] == (HT, value, Mode.MANUAL)
        ht.clear_pending()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "climate", "set_temperature", {ATTR_ENTITY_ID: e, ATTR_TEMPERATURE: 22.0, "hvac_mode": "auto"}, blocking=True
        )
    assert err.value.translation_key == "virtual_no_program"
