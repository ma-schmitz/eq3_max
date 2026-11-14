from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import ATTR_ENTITY_ID

from custom_components.eq3_max.protocol.messages import Mode

from .conftest import HT, WT

E = "climate.ht_bad_unten"


async def push(hass, hub, address, **values):
    dev = hub.devices[address]
    for k, v in values.items():
        setattr(dev, k, v)
    hub.on_update(dev)
    await hass.async_block_till_done()


async def test_state_and_attributes(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, measured=19.5, valve=48, mode=Mode.MANUAL)
    st = hass.states.get(E)
    assert st.state == HVACMode.HEAT
    assert st.attributes["temperature"] == 21.0
    assert st.attributes["current_temperature"] == 19.5
    assert st.attributes["valve"] == 48
    assert st.attributes["id"] == "MEQ9000007"
    assert st.attributes["hvac_action"] == HVACAction.HEATING
    assert st.attributes["ausstehend"] is None
    assert st.attributes["ausstehend_modus"] is None


async def test_off_is_manual_4_5(hass, setup_entry, fake_hub):
    await push(hass, fake_hub.last, HT, target=4.5, mode=Mode.MANUAL, valve=0)
    st = hass.states.get(E)
    assert st.state == HVACMode.OFF
    assert st.attributes["hvac_action"] == HVACAction.OFF


async def test_set_temperature_keeps_manual_and_shows_pending(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 21}, blocking=True)
    assert hub.commands == [(HT, 21.0, Mode.MANUAL)]
    st = hass.states.get(E)
    assert st.attributes["temperature"] == 18.0
    assert st.attributes["ausstehend"] == 21.0


async def test_hvac_modes(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "off"}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "auto"}, blocking=True)
    assert hub.commands == [(HT, 4.5, Mode.MANUAL), (HT, 21.0, Mode.MANUAL), (HT, None, Mode.AUTO)]


async def test_set_temperature_with_hvac_mode_off_in_one_call(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 19, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands == [(HT, 19.0, Mode.MANUAL)]


async def test_presets(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.BOOST)
    assert hass.states.get(E).attributes["preset_mode"] == "boost"
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "none"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_stays_available_when_stick_disconnected(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    hub.connected = False
    hub.on_update(None)
    await hass.async_block_till_done()
    assert hass.states.get(E).state == HVACMode.HEAT
    assert hass.states.get("binary_sensor.eq3_max_verbunden").state == "off"


async def test_wall_thermostat_has_no_valve(hass, setup_entry, fake_hub):
    await push(hass, fake_hub.last, WT, target=21.0, measured=21.2, mode=Mode.MANUAL)
    st = hass.states.get("climate.wt_wohnzimmer")
    assert st.state == HVACMode.HEAT and "valve" not in st.attributes


async def test_preset_away_uses_defaults_and_rounds_end(hass, setup_entry, fake_hub, freezer):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:17:12+00:00")  # 14:17:12 Ortszeit
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    assert hub.commands == [(HT, 18.0, Mode.TEMPORARY, datetime(2026, 10, 10, 14, 30))]


async def test_preset_away_uses_options_without_reload(hass, setup_entry, fake_hub, freezer):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:40:00+00:00")  # 14:40 Ortszeit
    hub = fake_hub.last
    hass.config_entries.async_update_entry(setup_entry, options={"brake": False, "away_temperature": 16.5, "away_hours": 48})
    await hass.async_block_till_done()
    assert fake_hub.last is hub  # Urlaubswerte brauchen keinen Neustart des Sticks
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    assert hub.commands == [(HT, 16.5, Mode.TEMPORARY, datetime(2026, 10, 11, 15, 0))]


async def test_attribute_bis_shows_reported_end(hass, setup_entry, fake_hub):
    from datetime import datetime

    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    assert hass.states.get(E).attributes["bis"] is None
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    st = hass.states.get(E)
    assert st.attributes["bis"] == "2026-10-10T14:30:00-07:00"  # Test-Zeitzone US/Pacific
    assert st.attributes["preset_mode"] == "away"


async def test_set_away_service(hass, setup_entry, fake_hub, freezer):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:00:00+00:00")
    hub = fake_hub.last
    await hass.services.async_call(
        "eq3_max", "set_away", {ATTR_ENTITY_ID: E, "temperature": 16, "until": "2026-10-12 08:10:00"}, blocking=True
    )
    await hass.services.async_call(
        "eq3_max", "set_away", {ATTR_ENTITY_ID: "climate.wt_wohnzimmer", "until": "2026-10-12 08:30:00"}, blocking=True
    )
    assert hub.commands == [
        (HT, 16.0, Mode.TEMPORARY, datetime(2026, 10, 12, 8, 30)),
        (WT, 18.0, Mode.TEMPORARY, datetime(2026, 10, 12, 8, 30)),
    ]


async def test_set_away_service_rejects_past_end(hass, setup_entry, fake_hub, freezer):
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:00:00+00:00")  # 14:00 Ortszeit
    hub = fake_hub.last
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("eq3_max", "set_away", {ATTR_ENTITY_ID: E, "until": "2026-10-09 13:30:00"}, blocking=True)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("eq3_max", "set_away", {ATTR_ENTITY_ID: E, "until": "2026-10-09 14:00:00"}, blocking=True)
    assert hub.commands == []


# --- final fix wave ---

async def test_set_hvac_mode_heat_keeps_queued_temperature(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 21}, blocking=True)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_set_preset_keeps_queued_temperature(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 21}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "boost"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.BOOST)


async def test_set_temperature_with_hvac_mode_auto_switches_to_auto(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 21, "hvac_mode": "auto"}, blocking=True)
    assert hub.commands == [(HT, None, Mode.AUTO)]


async def test_set_temperature_with_only_hvac_mode_delegates(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=19.0, mode=Mode.AUTO)
    ent = hass.data["climate"].get_entity(E)
    await ent.async_set_temperature(hvac_mode=HVACMode.HEAT)
    assert hub.commands == [(HT, 19.0, Mode.MANUAL)]


async def test_pending_attributes_show_target_and_mode(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 20.8}, blocking=True)
    st = hass.states.get(E)
    assert st.attributes["ausstehend"] == 21.0
    assert st.attributes["ausstehend_modus"] == "manual"
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "auto"}, blocking=True)
    st = hass.states.get(E)
    assert st.attributes["ausstehend"] is None and st.attributes["ausstehend_modus"] == "auto"
    hub.devices[HT].clear_pending()
    await push(hass, hub, HT)
    assert hass.states.get(E).attributes["ausstehend_modus"] is None



# --- Block 1, Fix-Runde 1 ---

async def test_m10_bis_carries_ha_local_offset(hass, setup_entry, fake_hub):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    hub = fake_hub.last
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    assert hass.states.get(E).attributes["bis"] == "2026-10-10T14:30:00+02:00"
    await push(hass, hub, HT, until=datetime(2026, 12, 24, 18, 0))
    assert hass.states.get(E).attributes["bis"] == "2026-12-24T18:00:00+01:00"


async def test_m6_future_time_within_rounding_is_accepted(hass, setup_entry, fake_hub, freezer):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:00:10+00:00")  # 14:00:10 Ortszeit
    hub = fake_hub.last
    await hass.services.async_call("eq3_max", "set_away", {ATTR_ENTITY_ID: E, "until": "2026-10-09 14:00:20"}, blocking=True)
    assert hub.commands == [(HT, 18.0, Mode.TEMPORARY, datetime(2026, 10, 9, 14, 30))]


async def test_m6_past_time_rejected_with_german_message(hass, setup_entry, fake_hub, freezer):
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:00:10+00:00")  # 14:00:10 Ortszeit
    hub = fake_hub.last
    with pytest.raises(ServiceValidationError) as exc:
        await hass.services.async_call("eq3_max", "set_away", {ATTR_ENTITY_ID: E, "until": "2026-10-09 13:59:30"}, blocking=True)
    assert exc.value.translation_key == "end_time_not_future"
    assert hub.commands == []


async def test_m9_away_does_not_replace_comfort_temperature(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 22}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    hub.devices[HT].clear_pending()
    await push(hass, hub, HT, target=4.5, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 22.0, Mode.MANUAL)


# --- Fix: heat nach away/boost stellt die Komforttemperatur her ---

async def _comfort_then(hass, hub, comfort, **report):
    await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": comfort}, blocking=True)
    hub.devices[HT].clear_pending()
    await push(hass, hub, HT, **report)


async def test_heat_after_away_restores_comfort(hass, setup_entry, fake_hub):
    from datetime import datetime

    hub = fake_hub.last
    await _comfort_then(hass, hub, 21, target=18.0, mode=Mode.TEMPORARY, until=datetime(2026, 10, 10, 14, 30))
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_heat_with_pending_away_restores_comfort(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 21, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    assert hub.commands[-1][2] is Mode.TEMPORARY
    await hass.services.async_call("climate", "turn_on", {ATTR_ENTITY_ID: E}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_preset_none_after_boost_restores_comfort(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 20.5, target=30.0, mode=Mode.BOOST)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "none"}, blocking=True)
    assert hub.commands[-1] == (HT, 20.5, Mode.MANUAL)


async def test_preset_none_after_away_restores_comfort(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 22, target=18.0, mode=Mode.TEMPORARY)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "none"}, blocking=True)
    assert hub.commands[-1] == (HT, 22.0, Mode.MANUAL)


async def test_manual_heat_keeps_current_target(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 21, target=19.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 19.0, Mode.MANUAL)


async def test_ha_manual_send_records_last_comfort_on_device(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 21.5, target=21.5, mode=Mode.MANUAL)
    assert hub.devices[HT].last_comfort == 21.5
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "off"}, blocking=True)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    assert hub.devices[HT].last_comfort == 21.5


async def test_heat_after_away_uses_stored_comfort_after_restart(hass, fake_hub, hass_storage):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT, DOMAIN
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    from .conftest import identity_devices

    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: identity_devices()})
    stored = MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten",
                       target=18.0, mode=Mode.TEMPORARY, last_comfort=21.0).to_dict()
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.devices.{entry.entry_id}",
        "data": {"devices": {str(HT): stored}},
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    assert hub.devices[HT].last_comfort == 21.0
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)



# --- Fix-Runde 1: letzte Komforttemperatur aus beiden Wegen ---

async def test_device_reported_manual_beats_older_ha_value(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.protocol.messages import decode_thermostat_state

    hub = fake_hub.last
    await _comfort_then(hass, hub, 20, target=20.0, mode=Mode.MANUAL)
    hub.devices[HT].apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302C")))  # manual 22.0
    await push(hass, hub, HT)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    hub.devices[HT].clear_pending()
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 22.0, Mode.MANUAL)


async def test_away_then_boost_then_none_restores_comfort(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await _comfort_then(hass, hub, 21, target=21.0, mode=Mode.MANUAL)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "away"}, blocking=True)
    hub.devices[HT].clear_pending()
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY)
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "boost"}, blocking=True)
    assert hub.commands[-1] == (HT, 18.0, Mode.BOOST)
    assert hub.devices[HT].last_comfort == 21.0
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "none"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_rejected_send_does_not_record_comfort(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    from custom_components.eq3_max.protocol.messages import FrameError

    hub = fake_hub.last
    await _comfort_then(hass, hub, 21, target=21.0, mode=Mode.MANUAL)

    def reject(*_a, **_kw):
        raise FrameError("rejected")

    hub.set_temperature = reject
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("climate", "set_temperature", {ATTR_ENTITY_ID: E, "temperature": 25}, blocking=True)
    assert hub.devices[HT].last_comfort == 21.0


# --- Block 2: Komfort-Rueckfall auf die Geraetekonfiguration ---

async def test_comfort_falls_back_to_config_komfort_then_default(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    dev = hub.devices[HT]
    assert dev.last_comfort is None
    dev.config["komfort"] = 22.5
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 22.5, Mode.MANUAL)
    # A remembered manual value still beats the configured comfort temperature.
    dev.clear_pending()
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY, last_comfort=20.0)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 20.0, Mode.MANUAL)
    # Without both the default applies.
    dev.clear_pending()
    dev.config.pop("komfort")
    await push(hass, hub, HT, target=18.0, mode=Mode.TEMPORARY, last_comfort=None)
    await hass.services.async_call("climate", "set_hvac_mode", {ATTR_ENTITY_ID: E, "hvac_mode": "heat"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.0, Mode.MANUAL)


async def test_native_temperature_members_without_deprecation(hass, setup_entry, fake_hub, caplog):
    """HA 2026.11 reads temperatures from native_* members and logs a deprecation for classes
    that only provide the old names (removal 2027.11). The old names stay as aliases for
    HA < 2026.11; with both present, HA 2026.11 stays quiet."""
    import logging

    from homeassistant.components.climate import ClimateEntity
    from homeassistant.const import UnitOfTemperature
    from homeassistant.helpers.entity_component import DATA_INSTANCES

    from custom_components.eq3_max.climate import MaxClimate

    await push(hass, fake_hub.last, HT, target=21.0, measured=19.5, mode=Mode.MANUAL)
    entity = hass.data[DATA_INSTANCES]["climate"].get_entity(E)
    assert entity.native_current_temperature == 19.5
    assert entity.native_target_temperature == 21.0
    assert entity._attr_native_temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.current_temperature == 19.5
    assert entity.target_temperature == 21.0
    if hasattr(ClimateEntity, "native_current_temperature"):  # HA >= 2026.11
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            type("MaxClimateProbe", (MaxClimate,), {})
        assert "deprecated" not in caplog.text


async def test_presets_comfort_and_eco(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    dev = hub.devices[HT]
    dev.config["komfort"], dev.config["eco"] = 21.5, 16.5
    await push(hass, hub, HT, target=19.0, mode=Mode.MANUAL)
    st = hass.states.get(E)
    assert {"comfort", "eco"} <= set(st.attributes["preset_modes"]) and st.attributes["preset_mode"] == "none"
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "comfort"}, blocking=True)
    assert hub.commands[-1] == (HT, 21.5, Mode.MANUAL) and dev.last_comfort == 21.5
    await hass.services.async_call("climate", "set_preset_mode", {ATTR_ENTITY_ID: E, "preset_mode": "eco"}, blocking=True)
    # Eco is no comfort value: heat after away/boost goes back to comfort, not eco.
    assert hub.commands[-1] == (HT, 16.5, Mode.MANUAL) and dev.last_comfort == 21.5
    await push(hass, hub, HT, target=16.5, mode=Mode.MANUAL)
    assert hass.states.get(E).attributes["preset_mode"] == "eco"
    await push(hass, hub, HT, target=21.5, mode=Mode.MANUAL)
    assert hass.states.get(E).attributes["preset_mode"] == "comfort"
    # The automatic program on the comfort value is no preset.
    await push(hass, hub, HT, target=21.5, mode=Mode.AUTO)
    assert hass.states.get(E).attributes["preset_mode"] == "none"


async def test_open_window_wins_over_eco_preset(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    dev = hub.devices[HT]
    dev.config["eco"] = dev.config["fenster_temperatur"] = 12.0
    await push(hass, hub, HT, target=12.0, mode=Mode.MANUAL)
    assert hass.states.get(E).attributes["preset_mode"] == "none"


async def test_wall_thermostat_comfort_preset(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.devices[WT].config["komfort"] = 22.0
    await hass.services.async_call(
        "climate", "set_preset_mode", {ATTR_ENTITY_ID: "climate.wt_wohnzimmer", "preset_mode": "comfort"}, blocking=True
    )
    assert hub.commands[-1] == (WT, 22.0, Mode.MANUAL)


# --- attributes for the thermostat card ---

from homeassistant.helpers import entity_registry as er  # noqa: E402

from custom_components.eq3_max.const import CONF_ALLOW_USER_WEEK_PROFILE, DOMAIN  # noqa: E402

from .conftest import FK  # noqa: E402

CARD_ATTRS = (
    "fenster", "raum", "wochenprogramm", "wochenprogramm_schreibt", "wochenprogramm_fehler",
    "einstellungen_frei", "wochenprogramm_frei",
)


def _fk_entity(hass):
    return er.async_get(hass).async_get_entity_id("binary_sensor", DOMAIN, "NEQ9000010_state")


async def test_card_attributes_defaults(hass, setup_entry, fake_hub):
    st = hass.states.get(E)
    assert st.attributes["fenster"] == [] and st.attributes["raum"] == []
    assert st.attributes["wochenprogramm"] == {} and st.attributes["wochenprogramm_schreibt"] == []
    assert st.attributes["wochenprogramm_fehler"] is None
    assert st.attributes["einstellungen_frei"] is True and st.attributes["wochenprogramm_frei"] is True


async def test_card_attributes_window_room_and_week(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    fk = _fk_entity(hass)
    assert fk is not None
    # FK linked to the wall thermostat only; the radiator is in the wall thermostat's room.
    hub.devices[WT].links = ["MEQ9000007", "NEQ9000010"]
    hub.devices[HT].links = ["NEQ9000011"]
    hub.devices[FK].links = ["NEQ9000011"]  # a link counts once both sides acknowledged it
    hub.devices[HT].week_profile = {"Montag": [{"temperature": 17.0, "until": "24:00"}]}
    hub.devices[HT].week_profile_writing = ["Dienstag"]
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    st = hass.states.get(E)
    assert st.attributes["fenster"] == [fk]
    assert st.attributes["raum"] == ["climate.wt_wohnzimmer"]
    assert st.attributes["wochenprogramm"] == {"Montag": [{"temperature": 17.0, "until": "24:00"}]}
    assert st.attributes["wochenprogramm_schreibt"] == ["Dienstag"]
    await push(hass, hub, WT)
    assert hass.states.get("climate.wt_wohnzimmer").attributes["fenster"] == [fk]


async def test_card_attributes_not_recorded(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.climate import MaxClimate

    assert set(CARD_ATTRS) <= set(MaxClimate._unrecorded_attributes)


async def test_option_change_updates_flags_without_reload(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hass.config_entries.async_update_entry(setup_entry, options={**setup_entry.options, CONF_ALLOW_USER_WEEK_PROFILE: False})
    await hass.async_block_till_done()
    assert fake_hub.last is hub  # no reload
    assert hass.states.get(E).attributes["wochenprogramm_frei"] is False


async def test_week_program_change_reaches_the_state_machine(hass, setup_entry, fake_hub):
    """The hub changes dev.week_profile in place; the attribute must not share that
    object, or the new state equals the old one and the frontend gets no update."""
    hub = fake_hub.last
    await push(hass, hub, HT, target=21.0, mode=Mode.MANUAL)
    old = hass.states.get(E).attributes["wochenprogramm"]
    hub.devices[HT].week_profile["Montag"] = [{"temperature": 17.0, "until": "24:00"}]
    await push(hass, hub, HT)
    assert old == {}
    assert hass.states.get(E).attributes["wochenprogramm"] == {"Montag": [{"temperature": 17.0, "until": "24:00"}]}
