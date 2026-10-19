from homeassistant.const import ATTR_ENTITY_ID

from .conftest import FK, HT, PB


async def push(hass, hub, address, **values):
    dev = hub.devices[address]
    for k, v in values.items():
        setattr(dev, k, v)
    hub.on_update(dev)
    await hass.async_block_till_done()


async def test_valve_rssi_lowbat_funkfehler(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    await push(hass, hub, HT, valve=35, rssi=-61.5, battery_low=True, rf_error=False, command_failed=True, locked=False, last_seen=1_760_000_000.0)
    assert hass.states.get("sensor.ht_bad_unten_ventil").state == "35"
    assert hass.states.get("sensor.ht_bad_unten_rssi").state == "-61.5"
    assert hass.states.get("binary_sensor.ht_bad_unten_lowbat").state == "on"
    assert hass.states.get("binary_sensor.ht_bad_unten_funkfehler").state == "on"
    assert hass.states.get("binary_sensor.ht_bad_unten_gesperrt").state == "off"
    assert hass.states.get("sensor.ht_bad_unten_zuletzt_gemeldet").state.startswith("2025-10-09")


async def test_window_contact(hass, setup_entry, fake_hub):
    await push(hass, fake_hub.last, FK, window_open=True)
    st = hass.states.get("binary_sensor.fk_schlafzimmer_state")
    assert st.state == "on" and st.attributes["device_class"] == "window"


async def test_button_event(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.on_button(hub.devices[PB], "eco")
    await hass.async_block_till_done()
    st = hass.states.get("event.taster")
    assert st.attributes["event_type"] == "eco"
    assert st.attributes["event_types"] == ["auto", "eco"]


async def test_hub_entities_and_pairing_button(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    hub.airtime_last_hour = 12.345
    hub.queue_length = 2
    hub.on_update(None)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eq3_max_sendezeit_1h").state == "12.3"
    assert hass.states.get("sensor.eq3_max_warteschlange").state == "2"
    assert hass.states.get("binary_sensor.eq3_max_verbunden").state == "on"
    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: "button.eq3_max_anlernen"}, blocking=True)
    assert hub.pairing == 60


async def test_hub_device_name(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    from custom_components.eq3_max.const import DOMAIN

    hub_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")})
    assert hub_device.name == "eQ-3 MAX! Funkmodul"
    assert hub_device.manufacturer == "busware / culfw"


async def test_diagnostics(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.diagnostics import async_get_config_entry_diagnostics

    data = await async_get_config_entry_diagnostics(hass, setup_entry)
    assert data["version"] == "V 1.66 nanoCUL868"
    assert data["devices"][str(HT)]["serial"] == "MEQ9000007"


# --- Block 3: Verknuepfungen ---

async def test_links_sensor_counts_complete_pairs_and_lists_pending(hass, setup_entry, fake_hub):
    from homeassistant.helpers import entity_registry as er

    from .conftest import WT

    hub = fake_hub.last
    st = hass.states.get("sensor.ht_bad_unten_verknuepfungen")
    assert st.state == "0" and st.attributes["partner"] == [] and st.attributes["ausstehend"] == []
    assert er.async_get(hass).async_get("sensor.ht_bad_unten_verknuepfungen").entity_category == "diagnostic"
    for entity_id in ("sensor.fk_schlafzimmer_verknuepfungen", "sensor.taster_verknuepfungen",
                      "sensor.wt_wohnzimmer_verknuepfungen"):
        assert hass.states.get(entity_id) is not None
    hub.devices[HT].links = ["NEQ9000011", "NEQ9000010"]
    hub.devices[WT].links = ["MEQ9000007"]
    hub.devices[FK].set_link_op("MEQ9000007", HT, 1, "add", "wartet auf Ger\u00e4t")
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    st = hass.states.get("sensor.ht_bad_unten_verknuepfungen")
    assert st.state == "1"
    assert st.attributes["partner"] == ["wt-wohnzimmer"]
    assert st.attributes["ausstehend"] == [
        "fk-schlafzimmer: wartet auf Fensterkontakt \u2013 bitte Fenster einmal \u00f6ffnen und schlie\u00dfen"
    ]
