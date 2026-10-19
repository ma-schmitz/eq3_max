"""Block 2: Geraetekonfiguration als number/select-Entitaeten."""

import pytest
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.eq3_max.const import DOMAIN

from .conftest import HT, WT

TEMP_NUMBERS = ("komfort", "eco", "maximal", "minimal", "offset", "fenster_temperatur", "fenster_dauer")
VALVE_NUMBERS = ("boost_ventil", "entkalkung_stunde", "ventil_max", "ventil_offset")
VALVE_SELECTS = ("boost_dauer", "entkalkung_tag")


async def test_heating_thermostat_has_all_config_entities(hass, setup_entry, fake_hub):
    reg = er.async_get(hass)
    for key in TEMP_NUMBERS + VALVE_NUMBERS:
        entry = reg.async_get(f"number.ht_bad_unten_{key}")
        assert entry is not None and entry.unique_id == f"MEQ9000007_{key}", key
        assert entry.entity_category is er.EntityCategory.CONFIG
    for key in VALVE_SELECTS:
        entry = reg.async_get(f"select.ht_bad_unten_{key}")
        assert entry is not None and entry.unique_id == f"MEQ9000007_{key}", key
        assert entry.entity_category is er.EntityCategory.CONFIG


async def test_wall_thermostat_has_only_temperature_config(hass, setup_entry, fake_hub):
    reg = er.async_get(hass)
    for key in TEMP_NUMBERS:
        assert reg.async_get(f"number.wt_wohnzimmer_{key}") is not None, key
    for key in VALVE_NUMBERS:
        assert reg.async_get(f"number.wt_wohnzimmer_{key}") is None, key
    for key in VALVE_SELECTS:
        assert reg.async_get(f"select.wt_wohnzimmer_{key}") is None, key
    numbers = [e for e in er.async_entries_for_config_entry(reg, setup_entry.entry_id) if e.domain == "number"]
    assert len(numbers) == 7 + 11  # WT + HT; no contact or button


async def test_factory_values_with_source_and_ranges(hass, setup_entry, fake_hub):
    st = hass.states.get("number.ht_bad_unten_komfort")
    assert st.state == "21.0"
    assert st.attributes["quelle"] == "werksvorgabe" and st.attributes["ausstehend"] is None
    assert (st.attributes["min"], st.attributes["max"], st.attributes["step"]) == (4.5, 30.5, 0.5)
    assert st.attributes["friendly_name"] == "ht-bad-unten Komforttemperatur"
    off = hass.states.get("number.ht_bad_unten_offset")
    assert off.state == "0.0" and (off.attributes["min"], off.attributes["max"]) == (-3.5, 3.5)
    dur = hass.states.get("number.ht_bad_unten_fenster_dauer")
    assert dur.state == "15" and (dur.attributes["min"], dur.attributes["max"], dur.attributes["step"]) == (0, 60, 5)
    assert hass.states.get("number.ht_bad_unten_boost_ventil").attributes["step"] == 5
    assert hass.states.get("number.ht_bad_unten_entkalkung_stunde").state == "12"
    assert hass.states.get("number.ht_bad_unten_ventil_max").state == "100"
    boost = hass.states.get("select.ht_bad_unten_boost_dauer")
    assert boost.state == "5 min"
    assert boost.attributes["options"] == ["0 min", "5 min", "10 min", "15 min", "20 min", "25 min", "30 min", "60 min"]
    day = hass.states.get("select.ht_bad_unten_entkalkung_tag")
    assert day.state == "Samstag"
    assert day.attributes["options"] == ["Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]


async def test_number_set_value_goes_to_hub_and_shows_pending(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_komfort", "value": 22.5}, blocking=True
    )
    assert hub.commands[-1] == ("config", HT, "komfort", 22.5)
    st = hass.states.get("number.ht_bad_unten_komfort")
    assert st.state == "21.0" and st.attributes["ausstehend"] == 22.5
    assert st.attributes["quelle"] == "werksvorgabe"
    hub.ack_config(HT, "temp")
    await hass.async_block_till_done()
    st = hass.states.get("number.ht_bad_unten_komfort")
    assert st.state == "22.5" and st.attributes["ausstehend"] is None and st.attributes["quelle"] == "gesetzt"


async def test_changing_one_value_keeps_the_others(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.devices[HT].config["eco"] = 16.0
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_maximal", "value": 25}, blocking=True
    )
    assert hub.devices[HT].pending_config["temp"]["eco"] == 16.0
    assert hub.devices[HT].pending_config["temp"]["maximal"] == 25.0


async def test_select_sets_valve_values(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await hass.services.async_call(
        "select", "select_option", {ATTR_ENTITY_ID: "select.ht_bad_unten_entkalkung_tag", "option": "Mittwoch"},
        blocking=True,
    )
    await hass.services.async_call(
        "select", "select_option", {ATTR_ENTITY_ID: "select.ht_bad_unten_boost_dauer", "option": "10 min"}, blocking=True
    )
    assert hub.commands[-2:] == [("config", HT, "entkalkung_tag", "Mittwoch"), ("config", HT, "boost_dauer", 10)]
    st = hass.states.get("select.ht_bad_unten_boost_dauer")
    assert st.state == "5 min" and st.attributes["ausstehend"] == "10 min"
    assert hass.states.get("select.ht_bad_unten_entkalkung_tag").attributes["ausstehend"] == "Mittwoch"
    hub.ack_config(HT, "valve")
    await hass.async_block_till_done()
    assert hass.states.get("select.ht_bad_unten_boost_dauer").state == "10 min"
    assert hub.devices[HT].config["boost_dauer"] == 10
    assert hass.states.get("select.ht_bad_unten_entkalkung_tag").state == "Mittwoch"
    assert hass.states.get("select.ht_bad_unten_entkalkung_tag").attributes["quelle"] == "gesetzt"


async def test_wall_thermostat_number_sets_temperature_config(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await hass.services.async_call(
        "number", "set_value", {ATTR_ENTITY_ID: "number.wt_wohnzimmer_offset", "value": -1.5}, blocking=True
    )
    assert hub.commands[-1] == ("config", WT, "offset", -1.5)
    assert hass.states.get("number.wt_wohnzimmer_offset").attributes["ausstehend"] == -1.5


async def test_invalid_value_is_rejected(hass, setup_entry, fake_hub):
    with pytest.raises(ServiceValidationError, match="Wert muss zwischen 4,5 und 30,5 in Schritten von 0,5 liegen"):
        await hass.services.async_call(
            "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_komfort", "value": 21.3}, blocking=True
        )
    with pytest.raises(ServiceValidationError, match="Wert muss zwischen 0 und 60 in Schritten von 5 liegen"):
        await hass.services.async_call(
            "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_fenster_dauer", "value": 7}, blocking=True
        )
    assert fake_hub.last.devices[HT].pending_config == {}


async def test_rf_error_sensor_shows_failed_config(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.set_config(HT, "komfort", 22.0)
    hub.devices[HT].config_failed = ["temp"]
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.ht_bad_unten_funkfehler").state == "on"


async def test_config_entities_registered_for_existing_install(hass, entry, fake_hub):
    """An install from before block 2: its own entities exist, the predecessors are gone."""
    reg = er.async_get(hass)
    reg.async_get_or_create("climate", DOMAIN, "MEQ9000007_climate", suggested_object_id="bad_unten_heizung")
    reg.async_get_or_create("climate", DOMAIN, "NEQ9000011_climate", suggested_object_id="wt_wohnzimmer")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert reg.async_get("number.bad_unten_heizung_komfort").unique_id == "MEQ9000007_komfort"
    assert reg.async_get("select.bad_unten_heizung_entkalkung_tag").unique_id == "MEQ9000007_entkalkung_tag"
    assert reg.async_get("number.wt_wohnzimmer_eco").unique_id == "NEQ9000011_eco"
    assert hass.states.get("number.bad_unten_heizung_komfort").state == "21.0"
