from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.eq3_max.const import DOMAIN


def old(reg, domain, platform, uid, object_id):
    return reg.async_get_or_create(domain, platform, uid, suggested_object_id=object_id)


def takeover_issue(hass, entry):
    return ir.async_get(hass).async_get_issue(DOMAIN, f"takeover_{entry.entry_id}")


async def set_up(hass, entry, *, takeover=True):
    """Set the entry up; with takeover the admin confirms the repair that lists the predecessors."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if takeover:
        await confirm_takeover(hass, entry)


async def confirm_takeover(hass, entry):
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "repairs", {})
    assert takeover_issue(hass, entry) is not None
    manager = hass.data["repairs"]["flow_manager"]
    result = await manager.async_init(DOMAIN, data={"issue_id": f"takeover_{entry.entry_id}"})
    assert result["type"] == "form" and result["step_id"] == "confirm", result
    result = await manager.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry", result
    await hass.async_block_till_done()
    return result


async def test_takes_over_entity_ids_area_and_name(hass, entry, fake_hub):
    reg = er.async_get(hass)
    area = ar.async_get(hass).async_create("Bad unten")
    climate = old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    reg.async_update_entity(climate.entity_id, area_id=area.id, name="Bad unten")
    old(reg, "binary_sensor", "homematic", "MEQ9000007_LOWBAT", "ht_bad_unten_lowbat")
    old(reg, "sensor", "template", "ht_bad_unten_ventil", "ht_bad_unten_ventil")
    old(reg, "binary_sensor", "homematic", "NEQ9000010_STATE", "fk_ht_schlafzimmer_state")
    old(reg, "binary_sensor", "homematic", "KEQ9000001_LOWBAT", "taster_lowbat")

    await set_up(hass, entry)

    new = reg.async_get("climate.ht_bad_unten")
    assert new.platform == DOMAIN and new.unique_id == "MEQ9000007_climate"
    assert new.area_id == area.id and new.name == "Bad unten"
    assert reg.async_get("binary_sensor.ht_bad_unten_lowbat").platform == DOMAIN
    # The user's own template entity keeps its place, ours gets a suffix.
    assert reg.async_get("sensor.ht_bad_unten_ventil").platform == "template"
    assert reg.async_get_entity_id("sensor", DOMAIN, "MEQ9000007_ventil") == "sensor.ht_bad_unten_ventil_2"
    assert reg.async_get("sensor.ht_bad_unten_rssi").platform == DOMAIN
    assert reg.async_get("binary_sensor.fk_ht_schlafzimmer_state").unique_id == "NEQ9000010_state"
    assert reg.async_get("event.taster").unique_id == "KEQ9000001_event"
    assert reg.async_get_entity_id("climate", "homematic", "MEQ9000007") is None


async def test_second_setup_does_not_duplicate(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    await set_up(hass, entry)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    ids = [e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id) if e.domain == "climate"]
    assert "climate.ht_bad_unten" in ids
    assert not any(i.endswith("_2") for i in ids)


async def test_blocked_while_homematic_loaded(hass, entry, fake_hub):
    hass.config.components.add("homematic")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, "homematic_active") is not None
    assert fake_hub.last is None or not fake_hub.last.started


async def test_new_device_without_predecessor_uses_name(hass, entry, fake_hub):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    assert reg.async_get("climate.ht_bad_unten") is not None
    assert reg.async_get("sensor.ht_bad_unten_ventil") is not None


async def test_carries_icon_aliases_labels_options_and_user_flags(hass, entry, fake_hub):
    from homeassistant.helpers import label_registry as lr

    reg = er.async_get(hass)
    label = lr.async_get(hass).async_create("Heizung")
    climate = old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    reg.async_update_entity(
        climate.entity_id,
        icon="mdi:radiator",
        aliases={"Badheizung"},
        labels={label.label_id},
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    reg.async_update_entity_options(climate.entity_id, "climate", {"foo": "bar"})
    lowbat = old(reg, "binary_sensor", "homematic", "MEQ9000007_LOWBAT", "ht_bad_unten_lowbat")
    reg.async_update_entity(lowbat.entity_id, disabled_by=er.RegistryEntryDisabler.INTEGRATION)
    await set_up(hass, entry)

    new = reg.async_get("climate.ht_bad_unten")
    assert new.platform == DOMAIN
    assert new.icon == "mdi:radiator"
    assert set(new.aliases) == {"Badheizung"}
    assert new.labels == {label.label_id}
    assert new.disabled_by is er.RegistryEntryDisabler.USER
    assert new.options["climate"] == {"foo": "bar"}
    assert reg.async_get("binary_sensor.ht_bad_unten_lowbat").disabled_by is None


async def test_user_hidden_carried(hass, entry, fake_hub):
    reg = er.async_get(hass)
    climate = old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    reg.async_update_entity(climate.entity_id, hidden_by=er.RegistryEntryHider.USER)
    old(reg, "binary_sensor", "homematic", "MEQ9000007_LOWBAT", "ht_bad_unten_lowbat")
    reg.async_update_entity("binary_sensor.ht_bad_unten_lowbat", hidden_by=er.RegistryEntryHider.INTEGRATION)
    await set_up(hass, entry)
    assert reg.async_get("climate.ht_bad_unten").hidden_by is er.RegistryEntryHider.USER
    assert reg.async_get("binary_sensor.ht_bad_unten_lowbat").hidden_by is None


async def test_wall_thermostat_taken_over(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "climate", "homematic", "NEQ9000011", "wt_wohnzimmer")
    await set_up(hass, entry)
    new = reg.async_get("climate.wt_wohnzimmer")
    assert new.platform == DOMAIN and new.unique_id == "NEQ9000011_climate"
    assert reg.async_get_entity_id("climate", "homematic", "NEQ9000011") is None


async def test_window_contact_lowbat_taken_over(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "binary_sensor", "homematic", "NEQ9000010_LOWBAT", "fk_ht_schlafzimmer_lowbat")
    await set_up(hass, entry)
    new = reg.async_get("binary_sensor.fk_ht_schlafzimmer_lowbat")
    assert new.platform == DOMAIN and new.unique_id == "NEQ9000010_lowbat"


def test_manifest_has_after_dependency_homematic():
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[2] / "custom_components/eq3_max/manifest.json").read_text())
    assert "homematic" in manifest["after_dependencies"]


def test_manifest_has_after_dependency_max_cul():
    import json
    from pathlib import Path

    manifest = json.loads((Path(__file__).parents[2] / "custom_components/eq3_max/manifest.json").read_text())
    assert "max_cul" in manifest["after_dependencies"]


def old_max_cul_entry(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    legacy = MockConfigEntry(domain="max_cul", unique_id="C0FFEE", title="MAX! CUL C0FFEE")
    legacy.add_to_hass(hass)
    return legacy


def old_mc(reg, legacy, domain, uid, object_id):
    return reg.async_get_or_create(domain, "max_cul", uid, suggested_object_id=object_id, config_entry=legacy)


async def test_takes_over_max_cul_predecessors(hass, entry, fake_hub):
    reg = er.async_get(hass)
    legacy = old_max_cul_entry(hass)
    areas = ar.async_get(hass)
    bad = areas.async_create("Bad unten")
    sz = areas.async_create("Schlafzimmer")
    flur = areas.async_create("Flur")
    climate = old_mc(reg, legacy, "climate", "MEQ9000007_climate", "ht_bad_unten")
    reg.async_update_entity(climate.entity_id, area_id=bad.id, name="Bad unten")
    ventil = old_mc(reg, legacy, "sensor", "MEQ9000007_ventil", "ht_bad_unten_ventil")
    reg.async_update_entity(ventil.entity_id, area_id=bad.id)
    taster = old_mc(reg, legacy, "event", "KEQ9000001_event", "taster")
    reg.async_update_entity(taster.entity_id, area_id=flur.id)
    state = old_mc(reg, legacy, "binary_sensor", "NEQ9000010_state", "fk_ht_schlafzimmer_state")
    reg.async_update_entity(state.entity_id, area_id=sz.id)

    await set_up(hass, entry)

    new = reg.async_get("climate.ht_bad_unten")
    assert new.platform == DOMAIN and new.unique_id == "MEQ9000007_climate"
    assert new.config_entry_id == entry.entry_id
    assert new.area_id == bad.id and new.name == "Bad unten"
    ventil = reg.async_get("sensor.ht_bad_unten_ventil")
    assert ventil.platform == DOMAIN and ventil.unique_id == "MEQ9000007_ventil" and ventil.area_id == bad.id
    taster = reg.async_get("event.taster")
    assert taster.platform == DOMAIN and taster.unique_id == "KEQ9000001_event" and taster.area_id == flur.id
    state = reg.async_get("binary_sensor.fk_ht_schlafzimmer_state")
    assert state.platform == DOMAIN and state.unique_id == "NEQ9000010_state" and state.area_id == sz.id
    for domain, uid in (
        ("climate", "MEQ9000007_climate"),
        ("sensor", "MEQ9000007_ventil"),
        ("event", "KEQ9000001_event"),
        ("binary_sensor", "NEQ9000010_state"),
    ):
        assert reg.async_get_entity_id(domain, "max_cul", uid) is None
    ids = [e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)]
    assert not any(i.endswith("_2") for i in ids)


async def test_base_from_max_cul_predecessors(hass, entry, fake_hub):
    # Object ids that differ from the device names: the missing entities follow the predecessor.
    reg = er.async_get(hass)
    legacy = old_max_cul_entry(hass)
    old_mc(reg, legacy, "climate", "MEQ9000007_climate", "ht_bad_eg")
    old_mc(reg, legacy, "binary_sensor", "NEQ9000010_state", "fk_sz_state")
    old_mc(reg, legacy, "event", "KEQ9000001_event", "eco_taster")
    old_mc(reg, legacy, "binary_sensor", "NEQ9000011_lowbat", "wt_wz_lowbat")

    await set_up(hass, entry)

    assert reg.async_get("climate.ht_bad_eg").platform == DOMAIN
    assert reg.async_get("sensor.ht_bad_eg_rssi").platform == DOMAIN
    assert reg.async_get("sensor.ht_bad_eg_ventil").platform == DOMAIN
    assert reg.async_get("binary_sensor.fk_sz_state").platform == DOMAIN
    assert reg.async_get("binary_sensor.fk_sz_lowbat").platform == DOMAIN
    assert reg.async_get("event.eco_taster").platform == DOMAIN
    assert reg.async_get("sensor.eco_taster_rssi").platform == DOMAIN
    assert reg.async_get("binary_sensor.wt_wz_lowbat").platform == DOMAIN
    assert reg.async_get("climate.wt_wz").platform == DOMAIN


async def test_old_hub_entities_do_not_block(hass, entry, fake_hub):
    reg = er.async_get(hass)
    legacy = old_max_cul_entry(hass)
    old_mc(reg, legacy, "binary_sensor", "C0FFEE_verbunden", "max_cul_verbunden")
    old_mc(reg, legacy, "sensor", "C0FFEE_sendezeit_1h", "max_cul_sendezeit_1h")
    old_mc(reg, legacy, "sensor", "C0FFEE_warteschlange", "max_cul_warteschlange")
    old_mc(reg, legacy, "button", "C0FFEE_anlernen", "max_cul_anlernen")

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    for entity_id in (
        "binary_sensor.eq3_max_verbunden",
        "sensor.eq3_max_sendezeit_1h",
        "sensor.eq3_max_warteschlange",
        "button.eq3_max_anlernen",
    ):
        new = reg.async_get(entity_id)
        assert new is not None and new.platform == DOMAIN, entity_id
        assert hass.states.get(entity_id) is not None
    assert reg.async_get("binary_sensor.max_cul_verbunden").platform == "max_cul"


async def test_blocked_while_max_cul_loaded(hass, entry, fake_hub):
    reg = er.async_get(hass)
    legacy = old_max_cul_entry(hass)
    old_mc(reg, legacy, "climate", "MEQ9000007_climate", "ht_bad_unten")
    hass.config.components.add("max_cul")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, "max_cul_active") is not None
    assert fake_hub.last is None or not fake_hub.last.started
    assert reg.async_get("climate.ht_bad_unten").platform == "max_cul"


async def test_max_cul_issue_cleared_after_successful_setup(hass, entry, fake_hub):
    hass.config.components.add("max_cul")
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    hass.config.components.remove("max_cul")
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, "max_cul_active") is None


def test_max_cul_issue_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    for path in (base / "strings.json", base / "translations/en.json", base / "translations/de.json"):
        issue = json.loads(path.read_text())["issues"]["max_cul_active"]
        assert issue["title"] and issue["description"], path


async def test_area_of_old_max_cul_device_carried(hass, entry, fake_hub):
    # max_cul had devices: an area set on the device (not the entity) must survive too.
    from homeassistant.helpers import device_registry as dr

    reg = er.async_get(hass)
    legacy = old_max_cul_entry(hass)
    bad = ar.async_get(hass).async_create("Bad unten")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=legacy.entry_id, identifiers={("max_cul", "MEQ9000007")}, name="ht-bad-unten"
    )
    dr.async_get(hass).async_update_device(device.id, area_id=bad.id)
    climate = old_mc(reg, legacy, "climate", "MEQ9000007_climate", "ht_bad_unten")
    reg.async_update_entity(climate.entity_id, device_id=device.id)

    await set_up(hass, entry)

    assert reg.async_get("climate.ht_bad_unten").area_id == bad.id


# --- Fix: Namen nach Uebernahme ---

async def test_serial_names_are_replaced_by_predecessor_names(hass, fake_hub):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    devices = [
        MaxDevice(0xA1B005, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="MEQ9000007").identity_dict(),
        MaxDevice(0xA1B00B, "NEQ9000010", DeviceType.SHUTTER_CONTACT, name="").identity_dict(),
        MaxDevice(0xA1B001, "KEQ9000001", DeviceType.PUSH_BUTTON, name="taster").identity_dict(),
        MaxDevice(0x1590B4, "NEQ9000011", DeviceType.WALL_THERMOSTAT, name="NEQ9000011").identity_dict(),
    ]
    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: devices})
    reg = er.async_get(hass)
    reg.async_get_or_create("climate", "homematic", "MEQ9000007", suggested_object_id="ht_bad_unten",
                            original_name="ht-bad-unten")
    reg.async_get_or_create("binary_sensor", "homematic", "NEQ9000010_STATE",
                            suggested_object_id="fk_ht_kueche_1_state", original_name="fk-ht-kueche-1 STATE")
    reg.async_get_or_create("binary_sensor", "homematic", "KEQ9000001_LOWBAT",
                            suggested_object_id="taster_lowbat", original_name="anderer-name LOWBAT")
    await set_up(hass, entry)
    names = {d["serial"]: d["name"] for d in entry.data[CONF_DEVICES]}
    assert names == {
        "MEQ9000007": "ht-bad-unten",
        "NEQ9000010": "fk-ht-kueche-1",
        "KEQ9000001": "taster",  # already a real name: kept
        "NEQ9000011": "NEQ9000011",  # no predecessor
    }
    assert fake_hub.last.devices[0xA1B005].name == "ht-bad-unten"
    assert hass.states.get("climate.ht_bad_unten").attributes["friendly_name"] == "ht-bad-unten"


async def test_predecessor_user_name_wins_over_original_name(hass, fake_hub):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    devices = [MaxDevice(0xA1B00B, "NEQ9000010", DeviceType.SHUTTER_CONTACT, name="NEQ9000010").identity_dict()]
    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: devices})
    reg = er.async_get(hass)
    old_fk = reg.async_get_or_create("binary_sensor", "homematic", "NEQ9000010_STATE",
                                     suggested_object_id="fk_state", original_name="NEQ9000010 STATE")
    reg.async_update_entity(old_fk.entity_id, name="fk-schlafzimmer Fenster")
    await set_up(hass, entry)
    assert entry.data[CONF_DEVICES][0]["name"] == "fk-schlafzimmer"


async def test_links_sensor_follows_device_base_for_all_types(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "binary_sensor", "homematic", "NEQ9000010_LOWBAT", "fk_ht_schlafzimmer_lowbat")
    old(reg, "climate", "homematic", "NEQ9000011", "wt_wohnzimmer_alt")
    await set_up(hass, entry)
    expected = {
        "MEQ9000007": "sensor.ht_bad_unten_verknuepfungen",
        "NEQ9000010": "sensor.fk_ht_schlafzimmer_verknuepfungen",
        "KEQ9000001": "sensor.taster_verknuepfungen",
        "NEQ9000011": "sensor.wt_wohnzimmer_alt_verknuepfungen",
    }
    for serial, entity_id in expected.items():
        assert reg.async_get_entity_id("sensor", DOMAIN, f"{serial}_verknuepfungen") == entity_id


def test_plug_adapter_gets_only_diagnostic_entities():
    from custom_components.eq3_max.migration import specs_for
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    plug = MaxDevice(0x123ABD, "PLG1234567", DeviceType.PLUG_ADAPTER)
    assert [(s.domain, s.key) for s in specs_for(plug)] == [("sensor", "rssi"), ("sensor", "zuletzt_gemeldet")]


# --- Takeover only after the admin confirmed it (HACS review, 17.11.2026) ---

async def test_setup_alone_leaves_predecessors_untouched_and_raises_a_repair(hass, entry, fake_hub):
    reg = er.async_get(hass)
    area = ar.async_get(hass).async_create("Bad unten")
    climate = old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    reg.async_update_entity(climate.entity_id, area_id=area.id, name="Bad unten")
    old(reg, "binary_sensor", "homematic", "NEQ9000010_STATE", "fk_ht_schlafzimmer_state")

    await set_up(hass, entry, takeover=False)

    kept = reg.async_get("climate.ht_bad_unten")
    assert kept.platform == "homematic" and kept.area_id == area.id and kept.name == "Bad unten"
    assert reg.async_get("binary_sensor.fk_ht_schlafzimmer_state").platform == "homematic"
    assert reg.async_get_entity_id("climate", DOMAIN, "MEQ9000007_climate") == "climate.ht_bad_unten_2"
    issue = takeover_issue(hass, entry)
    assert issue is not None and issue.is_fixable
    listed = issue.translation_placeholders["entities"]
    assert "climate.ht_bad_unten" in listed and "binary_sensor.fk_ht_schlafzimmer_state" in listed
    assert issue.translation_placeholders["count"] == "2"


async def test_no_predecessors_no_repair(hass, entry, fake_hub):
    await set_up(hass, entry, takeover=False)
    assert takeover_issue(hass, entry) is None


async def test_template_entities_are_never_listed_or_removed(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "sensor", "template", "ht_bad_unten_ventil", "ht_bad_unten_ventil")
    old(reg, "binary_sensor", "template", "fenster", "fk_schlafzimmer_state")
    await set_up(hass, entry, takeover=False)
    assert takeover_issue(hass, entry) is None
    assert reg.async_get("sensor.ht_bad_unten_ventil").platform == "template"
    assert reg.async_get("binary_sensor.fk_schlafzimmer_state").platform == "template"
    assert reg.async_get_entity_id("binary_sensor", DOMAIN, "NEQ9000010_state") == "binary_sensor.fk_schlafzimmer_state_2"


async def test_confirmed_takeover_renames_our_entity_and_clears_the_repair(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    await set_up(hass, entry, takeover=False)
    assert hass.states.get("climate.ht_bad_unten_2") is not None

    await confirm_takeover(hass, entry)

    assert reg.async_get("climate.ht_bad_unten").platform == DOMAIN
    assert reg.async_get("climate.ht_bad_unten_2") is None
    assert hass.states.get("climate.ht_bad_unten") is not None and hass.states.get("climate.ht_bad_unten_2") is None
    assert takeover_issue(hass, entry) is None
    assert entry.state is ConfigEntryState.LOADED
    # Nothing left to take over: a reload raises no new repair.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert takeover_issue(hass, entry) is None


async def test_predecessor_at_our_entity_id_with_another_unique_id_is_listed(hass, entry, fake_hub):
    reg = er.async_get(hass)
    old(reg, "sensor", "homematic", "irgendwas", "ht_bad_unten_ventil")
    await set_up(hass, entry, takeover=False)
    assert "sensor.ht_bad_unten_ventil" in takeover_issue(hass, entry).translation_placeholders["entities"]
    await confirm_takeover(hass, entry)
    assert reg.async_get("sensor.ht_bad_unten_ventil").platform == DOMAIN


async def test_takeover_is_refused_while_the_predecessor_is_loaded(hass, entry, fake_hub):
    from homeassistant.setup import async_setup_component

    reg = er.async_get(hass)
    old(reg, "climate", "homematic", "MEQ9000007", "ht_bad_unten")
    await set_up(hass, entry, takeover=False)
    hass.config.components.add("homematic")
    assert await async_setup_component(hass, "repairs", {})
    manager = hass.data["repairs"]["flow_manager"]
    result = await manager.async_init(DOMAIN, data={"issue_id": f"takeover_{entry.entry_id}"})
    result = await manager.async_configure(result["flow_id"], {})
    assert result["type"] == "abort" and result["reason"] == "predecessor_active"
    assert reg.async_get("climate.ht_bad_unten").platform == "homematic"
    assert takeover_issue(hass, entry) is not None


def test_takeover_repair_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components/eq3_max"
    for path in (base / "strings.json", base / "translations/en.json", base / "translations/de.json"):
        issue = json.loads(path.read_text())["issues"]["takeover"]
        step = issue["fix_flow"]["step"]["confirm"]
        assert issue["title"] and "{entities}" in step["description"], path
        assert issue["fix_flow"]["abort"]["predecessor_active"], path
