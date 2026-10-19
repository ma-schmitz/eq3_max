from homeassistant.config_entries import ConfigEntryState

from custom_components.eq3_max.const import DOMAIN

from .conftest import HT


async def test_setup_starts_hub_and_unload_stops(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    assert hub.started and hub.address == 0xC0FFEE and hub.port.endswith("usb-0:13")
    assert set(hub.devices) >= {HT}
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    assert not hub.started
    assert setup_entry.state is ConfigEntryState.NOT_LOADED


async def test_state_is_restored_from_store(hass, entry, fake_hub, hass_storage):
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.devices.{entry.entry_id}",
        "data": {"devices": {str(HT): {"address": HT, "serial": "MEQ9000007", "device_type": 1, "target": 21.0, "measured": 19.5, "valve": 30}}},
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    dev = fake_hub.last.devices[HT]
    assert (dev.target, dev.measured, dev.valve, dev.name) == (21.0, 19.5, 30, "ht-bad-unten")


async def test_updates_are_saved(hass, setup_entry, fake_hub, hass_storage):
    hub = fake_hub.last
    hub.devices[HT].target = 22.5
    hub.on_update(hub.devices[HT])
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    stored = hass_storage[f"{DOMAIN}.devices.{setup_entry.entry_id}"]["data"]["devices"]
    assert stored[str(HT)]["target"] == 22.5


async def test_problem_creates_repair_issue(hass, setup_entry, fake_hub):
    from homeassistant.helpers import issue_registry as ir

    fake_hub.last.on_problem("stick_deaf")
    assert ir.async_get(hass).async_get_issue(DOMAIN, "stick_deaf") is not None


async def test_new_device_is_added_to_entry(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    created = []
    orig_init = fake_hub.__init__

    def counting(self, *a, **kw):
        created.append(1)
        orig_init(self, *a, **kw)

    fake_hub.__init__ = counting
    try:
        # The hub calls on_device_added only after the PairPong completed; the
        # coordinator then schedules exactly one reload itself (the data update
        # alone does not reload any more).
        fake_hub.last.on_device_added(MaxDevice(0x123ABC, "ABC1234567", DeviceType.HEATING_THERMOSTAT, name="ABC1234567"))
        await hass.async_block_till_done()
        serials = [d["serial"] for d in setup_entry.data["devices"]]
        assert "ABC1234567" in serials
        assert len(created) == 1
        assert 0x123ABC in fake_hub.last.devices
    finally:
        fake_hub.__init__ = orig_init


async def test_bad_stored_state_falls_back_to_identity(hass, entry, fake_hub, hass_storage):
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.devices.{entry.entry_id}",
        "data": {"devices": {str(HT): {"address": HT, "serial": "MEQ9000007", "device_type": 1, "mode": 99, "target": 21.0}}},
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    dev = fake_hub.last.devices[HT]
    assert dev.name == "ht-bad-unten"
    assert dev.target is None


async def test_setup_failure_stops_hub(hass, entry, fake_hub):
    from unittest.mock import patch

    entry.add_to_hass(hass)
    with patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=RuntimeError("boom")):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert fake_hub.last.started is False


async def test_stick_deaf_issue_survives_reconnect(hass, setup_entry, fake_hub):
    import time

    from homeassistant.helpers import issue_registry as ir

    hub = fake_hub.last
    hub.on_problem("stick_deaf")
    hub.on_update(None)
    reg = ir.async_get(hass)
    assert reg.async_get_issue(DOMAIN, "stick_deaf") is not None
    hub.devices[HT].last_seen = time.time() + 100
    hub.on_update(hub.devices[HT])
    assert reg.async_get_issue(DOMAIN, "stick_deaf") is None


# --- final fix wave ---

def _counting_hub(fake_hub):
    created = []
    orig_init = fake_hub.__init__

    def counting(self, *a, **kw):
        created.append(1)
        orig_init(self, *a, **kw)

    return created, orig_init, counting


async def test_data_only_update_does_not_reload(hass, setup_entry, fake_hub):
    created, orig_init, counting = _counting_hub(fake_hub)
    fake_hub.__init__ = counting
    try:
        hass.config_entries.async_update_entry(setup_entry, data={**setup_entry.data, "port": setup_entry.data["port"] + "x"})
        await hass.async_block_till_done()
        assert created == []
        hass.config_entries.async_update_entry(setup_entry, options={"brake": True})
        await hass.async_block_till_done()
        assert len(created) == 1
        assert fake_hub.last.brake is True
    finally:
        fake_hub.__init__ = orig_init


async def test_imported_snapshot_merged_with_store_identity_wins(hass, fake_hub, hass_storage):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType, Mode

    imported = MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten",
                         target=21.0, measured=19.8, valve=18, mode=Mode.MANUAL).to_dict()
    for key in ("pending_target", "pending_mode", "command_failed"):
        imported.pop(key)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: [imported]})
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.devices.{entry.entry_id}",
        "data": {"devices": {str(HT): {"address": HT, "serial": "MEQ9000007", "device_type": 1,
                                       "name": "stale-name", "valve": 40}}},
    }
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    dev = fake_hub.last.devices[HT]
    assert (dev.target, dev.measured, dev.valve, dev.mode) == (21.0, 19.8, 40, Mode.MANUAL)
    assert dev.name == "ht-bad-unten"


async def test_hub_entities_refresh_every_minute(hass, setup_entry, fake_hub):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    hub = fake_hub.last
    hub.airtime_last_hour = 5.0
    hub.on_update(None)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eq3_max_sendezeit_1h").state == "5.0"
    hub.airtime_last_hour = 0.0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.eq3_max_sendezeit_1h").state == "0.0"


async def test_device_entities_update_only_for_their_address(hass, setup_entry, fake_hub):
    hub = fake_hub.last
    dev = hub.devices[HT]
    dev.valve = 10
    hub.on_update(dev)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ht_bad_unten_ventil").state == "10"
    dev.valve = 20
    hub.on_update(None)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ht_bad_unten_ventil").state == "10"
    hub.on_update(dev)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ht_bad_unten_ventil").state == "20"


async def test_diagnostics_include_raw_history(hass, setup_entry, fake_hub):
    from collections import deque

    from custom_components.eq3_max.diagnostics import async_get_config_entry_diagnostics

    fake_hub.last.raw_history[HT] = deque(["Z0B0100600A1B005C0FFEE00"], maxlen=10)
    data = await async_get_config_entry_diagnostics(hass, setup_entry)
    assert data["raw_history"] == {str(HT): ["Z0B0100600A1B005C0FFEE00"]}


async def test_device_info_carries_rf_address_as_hw_version(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "MEQ9000007")})
    assert device.hw_version == "RF A1B005"
    assert device.connections == set()


async def test_devices_are_linked_to_hub_by_id(hass, entry, fake_hub, caplog):
    from homeassistant.helpers import device_registry as dr

    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    dev_reg = dr.async_get(hass)
    hub = dev_reg.async_get_device(identifiers={(DOMAIN, entry.data["address"])})
    assert hub is not None
    others = [d for d in dr.async_entries_for_config_entry(dev_reg, entry.entry_id) if d.id != hub.id]
    assert others
    assert all(d.via_device_id == hub.id for d in others)
    assert "deprecated `via_device`" not in caplog.text


async def test_device_info_has_no_deprecated_via_device(hass, setup_entry):
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers import entity_platform as ep

    infos = [e.device_info for p in ep.async_get_platforms(hass, DOMAIN) for e in p.entities.values() if e.device_info]
    assert infos
    assert all("via_device" not in info for info in infos)


# --- Block 1: Werksreset und Geraet loeschen ---

async def test_factory_reset_acked_removes_device(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")})
    hub = fake_hub.last
    await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": device.id}, blocking=True)
    await hass.async_block_till_done()
    assert hub.resets == [HT]
    assert "MEQ9000007" not in [d["serial"] for d in setup_entry.data["devices"]]
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")}) is None
    assert hass.states.get("climate.ht_bad_unten") is None
    # Neu geladen ohne das Geraet
    assert fake_hub.last is not hub and HT not in fake_hub.last.devices


async def test_factory_reset_without_ack_keeps_device(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")})
    hub = fake_hub.last
    from custom_components.eq3_max.protocol.hub import ResetResult

    hub.reset_result = ResetResult.UNACKED
    with pytest.raises(HomeAssistantError, match="nicht quittiert .* eventuell trotzdem zur\u00fcckgesetzt"):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": device.id}, blocking=True)
    await hass.async_block_till_done()
    assert "MEQ9000007" in [d["serial"] for d in setup_entry.data["devices"]]
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")}) is not None
    assert fake_hub.last is hub


async def test_factory_reset_refuses_hub_device(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import ServiceValidationError
    from homeassistant.helpers import device_registry as dr

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": device.id}, blocking=True)
    assert fake_hub.last.resets == []


async def test_remove_device_from_device_page_forgets_it(hass, setup_entry, fake_hub, hass_ws_client):
    from homeassistant.helpers import device_registry as dr
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "config", {})
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, "NEQ9000010")})
    hub = fake_hub.last
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "config/device_registry/remove_config_entry", "config_entry_id": setup_entry.entry_id, "device_id": device.id}
    )
    resp = await client.receive_json()
    assert resp["success"], resp
    await hass.async_block_till_done()
    assert "NEQ9000010" not in [d["serial"] for d in setup_entry.data["devices"]]
    assert dev_reg.async_get_device(identifiers={(DOMAIN, "NEQ9000010")}) is None
    assert hub.resets == []  # nur vergessen, kein Funk
    assert 0xA1B00B not in fake_hub.last.devices


async def test_remove_hub_device_is_refused(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    from custom_components.eq3_max import async_remove_config_entry_device

    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "C0FFEE")})
    assert await async_remove_config_entry_device(hass, setup_entry, device) is False
    assert len(setup_entry.data["devices"]) == 4


async def test_services_yaml_is_valid(hass, setup_entry):
    from homeassistant.helpers import service
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    desc = service._SERVICES_SCHEMA(service._load_services_file(integration))
    assert set(desc["set_away"]["fields"]) == {"temperature", "until"}
    assert desc["set_away"]["target"]["entity"][0]["integration"] == DOMAIN
    assert set(desc["factory_reset"]["fields"]) == {"device_id"}
    assert hass.services.has_service(DOMAIN, "set_away") and hass.services.has_service(DOMAIN, "factory_reset")



# --- Block 1, Fix-Runde 1 ---

def _ht_device_id(hass):
    from homeassistant.helpers import device_registry as dr

    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "MEQ9000007")}).id


async def test_i3_factory_reset_refused_when_stick_not_connected(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    hub = fake_hub.last
    hub.connected = False
    with pytest.raises(HomeAssistantError, match="Funkmodul nicht verbunden"):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": _ht_device_id(hass)}, blocking=True)
    assert hub.resets == []


async def test_i3_factory_reset_not_sent(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.eq3_max.protocol.hub import ResetResult

    hub = fake_hub.last
    hub.reset_result = ResetResult.NOT_SENT
    with pytest.raises(HomeAssistantError, match="^Werksreset nicht gesendet$"):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": _ht_device_id(hass)}, blocking=True)
    assert "MEQ9000007" in [d["serial"] for d in setup_entry.data["devices"]]


async def test_m8_factory_reset_already_running_or_device_gone(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import HomeAssistantError

    from custom_components.eq3_max.protocol.messages import FrameError

    hub = fake_hub.last
    hub.reset_error = FrameError("Werksreset l\u00e4uft bereits")
    with pytest.raises(HomeAssistantError, match="l\u00e4uft bereits"):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": _ht_device_id(hass)}, blocking=True)
    hub.reset_error = KeyError(HT)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": _ht_device_id(hass)}, blocking=True)
    assert "MEQ9000007" in [d["serial"] for d in setup_entry.data["devices"]]


async def test_m5_hub_gets_ha_local_clock(hass, setup_entry, fake_hub, freezer):
    from datetime import datetime

    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to("2026-10-09T12:17:12+00:00")
    assert fake_hub.last.kwargs["local_now"]() == datetime(2026, 10, 9, 14, 17, 12)


# --- Fix: Geraetenamen nach Uebernahme ---

async def test_device_registry_names_follow_entry_data(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    dev_reg = dr.async_get(hass)
    stale = dev_reg.async_get_device(identifiers={(DOMAIN, "MEQ9000007")})
    user = dev_reg.async_get_device(identifiers={(DOMAIN, "NEQ9000010")})
    # State after the Homegear import: registry names are serials.
    dev_reg.async_update_device(stale.id, name="MEQ9000007")
    dev_reg.async_update_device(user.id, name="NEQ9000010", name_by_user="Fenster Schlafzimmer")
    setup_entry.runtime_data.async_link_devices()
    assert dev_reg.async_get(stale.id).name == "ht-bad-unten"
    kept = dev_reg.async_get(user.id)
    assert kept.name == "NEQ9000010" and kept.name_by_user == "Fenster Schlafzimmer"
    hub = dev_reg.async_get_device(identifiers={(DOMAIN, setup_entry.data["address"])})
    assert hub.name == "eQ-3 MAX! Funkmodul"


# --- Block 2: Geraetekonfiguration ---

def _store(entry, devices):
    return {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.devices.{entry.entry_id}",
        "data": {"devices": devices},
    }


async def test_existing_entry_without_config_gets_factory_defaults(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.protocol.devices import CONFIG_TEMP_KEYS, FACTORY_CONFIG

    from .conftest import FK, WT

    hub = fake_hub.last
    assert hub.devices[HT].config == FACTORY_CONFIG
    assert set(hub.devices[HT].config_source.values()) == {"werksvorgabe"}
    assert set(hub.devices[WT].config) == set(CONFIG_TEMP_KEYS)
    assert hub.devices[FK].config == {}


async def test_legacy_entry_window_open_temperature_is_kept(hass, fake_hub):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT

    item = {"address": HT, "serial": "MEQ9000007", "device_type": 1, "name": "ht-bad-unten",
            "firmware": "", "group": 0, "window_open_temperature": 10.0}
    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: [item]})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    dev = fake_hub.last.devices[HT]
    assert dev.config["fenster_temperatur"] == 10.0 and dev.config_source["fenster_temperatur"] == "homegear"
    assert dev.config["komfort"] == 21.0 and dev.config_source["komfort"] == "werksvorgabe"


async def test_entry_config_wins_over_store_and_pending_comes_from_store(hass, fake_hub, hass_storage):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    dev = MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten")
    dev.ensure_config_defaults()
    dev.config["komfort"] = 22.0
    dev.config_source["komfort"] = "homegear"
    stored = MaxDevice.from_dict(dev.to_dict())
    stored.config["komfort"] = 19.0
    stored.stage_config("eco", 16.0)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="C0FFEE", title="eQ-3 MAX! C0FFEE",
                            data={CONF_PORT: "/dev/x", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: [dev.identity_dict()]})
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = _store(entry, {str(HT): stored.to_dict()})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    got = fake_hub.last.devices[HT]
    assert got.config["komfort"] == 22.0 and got.config_source["komfort"] == "homegear"
    assert got.pending_config["temp"]["eco"] == 16.0


async def test_store_config_used_when_entry_has_none(hass, entry, fake_hub, hass_storage):
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    stored = MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT)
    stored.ensure_config_defaults()
    stored.config["eco"] = 15.5
    stored.config_source["eco"] = "gesetzt"
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = _store(entry, {str(HT): stored.to_dict()})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    got = fake_hub.last.devices[HT]
    assert got.config["eco"] == 15.5 and got.config_source["eco"] == "gesetzt"


async def test_acknowledged_config_goes_into_entry_and_store(hass, setup_entry, fake_hub, hass_storage):
    hub = fake_hub.last
    hub.set_config(HT, "komfort", 22.5)
    await hass.async_block_till_done()
    item = next(i for i in setup_entry.data["devices"] if i["address"] == HT)
    assert item.get("config", {}).get("komfort") != 22.5
    assert "pending_config" not in item
    hub.ack_config(HT, "temp")
    await hass.async_block_till_done()
    item = next(i for i in setup_entry.data["devices"] if i["address"] == HT)
    assert item["config"]["komfort"] == 22.5 and item["config_source"]["komfort"] == "gesetzt"
    assert "pending_config" not in item and "config_failed" not in item
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    stored = hass_storage[f"{DOMAIN}.devices.{setup_entry.entry_id}"]["data"]["devices"][str(HT)]
    assert stored["config"]["komfort"] == 22.5 and stored["pending_config"] == {}


async def test_pending_config_is_stored_not_in_entry(hass, setup_entry, fake_hub, hass_storage):
    hub = fake_hub.last
    hub.set_config(HT, "eco", 16.0)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    stored = hass_storage[f"{DOMAIN}.devices.{setup_entry.entry_id}"]["data"]["devices"][str(HT)]
    assert stored["pending_config"]["temp"]["eco"] == 16.0
    for item in setup_entry.data["devices"]:
        assert "pending_config" not in item


async def test_paired_device_enters_entry_with_factory_config(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.protocol.devices import FACTORY_CONFIG, MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    dev = MaxDevice(0x123ABC, "ABC1234567", DeviceType.HEATING_THERMOSTAT, name="ABC1234567")
    dev.ensure_config_defaults()  # the hub does this on pairing
    fake_hub.last.on_device_added(dev)
    await hass.async_block_till_done()
    item = next(i for i in setup_entry.data["devices"] if i["serial"] == "ABC1234567")
    assert item["config"] == FACTORY_CONFIG
    assert set(item["config_source"].values()) == {"werksvorgabe"}


async def test_devices_without_config_keep_entry_item_clean(hass, entry, fake_hub):
    from custom_components.eq3_max.const import CONF_DEVICES

    from .conftest import FK, PB

    items = [{k: v for k, v in i.items() if k not in ("config", "config_source")} for i in entry.data[CONF_DEVICES]]
    entry = type(entry)(domain=DOMAIN, unique_id="C0FFEE", title=entry.title, data={**entry.data, CONF_DEVICES: items})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    for address in (FK, PB, HT):
        hub.on_update(hub.devices[address])
    await hass.async_block_till_done()
    got = {i["address"]: i for i in entry.data[CONF_DEVICES]}
    for address in (FK, PB):
        assert "config" not in got[address] and "config_source" not in got[address]
    assert got[HT]["config"]["komfort"] == 21.0


# --- Block 3: Verknuepfungen ---

async def test_acknowledged_links_go_into_entry_pending_only_into_store(hass, setup_entry, fake_hub, hass_storage):
    from .conftest import FK

    hub = fake_hub.last
    dev = hub.devices[HT]
    dev.set_link_op("NEQ9000010", FK, 4, "add", "ausstehend")
    hub.on_update(dev)
    await hass.async_block_till_done()
    item = next(i for i in setup_entry.data["devices"] if i["address"] == HT)
    assert item.get("links", []) == [] and "pending_links" not in item
    dev.commit_link("NEQ9000010", "add")
    hub.on_update(dev)
    await hass.async_block_till_done()
    item = next(i for i in setup_entry.data["devices"] if i["address"] == HT)
    assert item["links"] == ["NEQ9000010"] and "pending_links" not in item
    dev.set_link_op("NEQ9000011", 0x1590B4, 3, "add", "fehlgeschlagen")
    hub.on_update(dev)
    assert await hass.config_entries.async_unload(setup_entry.entry_id)
    stored = hass_storage[f"{DOMAIN}.devices.{setup_entry.entry_id}"]["data"]["devices"][str(HT)]
    assert stored["links"] == ["NEQ9000010"]
    assert stored["pending_links"][0]["partner"] == "NEQ9000011"


async def test_entry_links_win_over_store_and_pending_links_come_from_store(hass, entry, fake_hub, hass_storage):
    from custom_components.eq3_max.const import CONF_DEVICES
    from custom_components.eq3_max.protocol.devices import MaxDevice
    from custom_components.eq3_max.protocol.messages import DeviceType

    from .conftest import FK, WT

    items = [dict(i) for i in entry.data[CONF_DEVICES]]
    items[0]["links"] = ["NEQ9000011"]  # injected by the controller
    items[1].pop("links", None)  # entry item from before block 3
    entry = type(entry)(domain=DOMAIN, unique_id="C0FFEE", title=entry.title, data={**entry.data, CONF_DEVICES: items})
    stored_ht = MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT)
    stored_ht.links = ["NEQ9000010"]
    stored_fk = MaxDevice(FK, "NEQ9000010", DeviceType.SHUTTER_CONTACT)
    stored_fk.links = ["MEQ9000007"]
    stored_fk.set_link_op("NEQ9000011", WT, DeviceType.WALL_THERMOSTAT, "add", "wartet auf Ger\u00e4t")
    hass_storage[f"{DOMAIN}.devices.{entry.entry_id}"] = _store(
        entry, {str(HT): stored_ht.to_dict(), str(FK): stored_fk.to_dict()}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    hub = fake_hub.last
    assert hub.devices[HT].links == ["NEQ9000011"]
    # Old entry item without links: the store's links count.
    assert hub.devices[FK].links == ["MEQ9000007"]
    assert hub.devices[FK].link_op("NEQ9000011")["state"] == "wartet auf Ger\u00e4t"


async def test_factory_reset_removes_device_from_other_devices_links(hass, setup_entry, fake_hub):
    from homeassistant.helpers import device_registry as dr

    from .conftest import FK, WT

    hub = fake_hub.last
    hub.devices[HT].links = ["NEQ9000010", "NEQ9000011"]
    hub.devices[WT].links = ["MEQ9000007"]
    hub.devices[FK].links = ["MEQ9000007"]
    hub.devices[WT].set_link_op("NEQ9000010", FK, 4, "add", "ausstehend")
    hub.on_update(hub.devices[HT])
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "NEQ9000010")})
    await hass.services.async_call(DOMAIN, "factory_reset", {"device_id": device.id}, blocking=True)
    await hass.async_block_till_done()
    items = {i["serial"]: i for i in setup_entry.data["devices"]}
    assert "NEQ9000010" not in items
    assert items["MEQ9000007"]["links"] == ["NEQ9000011"]
    new_hub = fake_hub.last
    assert new_hub.devices[HT].links == ["NEQ9000011"]
    assert new_hub.devices[WT].pending_links == []


def _device_id(hass, serial):
    from homeassistant.helpers import device_registry as dr

    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, serial)}).id


async def test_link_and_unlink_services_queue_and_return(hass, setup_entry, fake_hub):
    from .conftest import FK, WT

    hub = fake_hub.last
    await hass.services.async_call(
        DOMAIN, "link",
        {"device_id": _device_id(hass, "MEQ9000007"), "partner_device_id": _device_id(hass, "NEQ9000010")},
        blocking=True,
    )
    assert hub.commands[-1] == ("link", HT, FK)
    assert hub.devices[HT].link_op("NEQ9000010")["state"] == "ausstehend"
    assert hub.devices[FK].link_op("MEQ9000007")["state"] == "wartet auf Ger\u00e4t"
    await hass.async_block_till_done()
    st = hass.states.get("sensor.fk_schlafzimmer_verknuepfungen")
    assert st.attributes["ausstehend"] == [
        "ht-bad-unten: wartet auf Fensterkontakt \u2013 bitte Fenster einmal \u00f6ffnen und schlie\u00dfen"
    ]
    hub.devices[HT].links = ["NEQ9000011"]
    hub.devices[WT].links = ["MEQ9000007"]
    await hass.services.async_call(
        DOMAIN, "unlink",
        {"device_id": _device_id(hass, "NEQ9000011"), "partner_device_id": _device_id(hass, "MEQ9000007")},
        blocking=True,
    )
    assert hub.commands[-1] == ("unlink", WT, HT)
    assert hub.devices[WT].link_op("MEQ9000007")["op"] == "remove"


async def test_link_services_reject_with_german_validation_errors(hass, setup_entry, fake_hub):
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    hub = fake_hub.last
    hub.devices[HT].links = ["NEQ9000011"]
    hub.devices[0x1590B4].links = ["MEQ9000007"]
    ht, fk, pb, wt = (_device_id(hass, s) for s in ("MEQ9000007", "NEQ9000010", "KEQ9000001", "NEQ9000011"))
    cases = [
        ("link", fk, pb, "Fensterkontakt und Eco-Taster lassen sich nicht verkn\u00fcpfen"),
        ("link", ht, ht, "nicht mit sich selbst"),
        ("link", ht, wt, "bereits verkn\u00fcpft"),
        ("unlink", ht, fk, "nicht verkn\u00fcpft"),
        ("link", ht, "nope", "Unbekanntes Ger\u00e4t"),
        ("link", ht, _device_id(hass, "C0FFEE"), "Funkmodul"),
    ]
    for action, a, b, message in cases:
        with pytest.raises(ServiceValidationError, match=message):
            await hass.services.async_call(DOMAIN, action, {"device_id": a, "partner_device_id": b}, blocking=True)
    assert hub.commands == []
    assert all(d.pending_links == [] for d in hub.devices.values())


async def test_link_services_in_services_yaml_with_device_selectors(hass, setup_entry):
    from homeassistant.helpers import service
    from homeassistant.loader import async_get_integration

    integration = await async_get_integration(hass, DOMAIN)
    desc = service._SERVICES_SCHEMA(service._load_services_file(integration))
    for name in ("link", "unlink"):
        fields = desc[name]["fields"]
        assert set(fields) == {"device_id", "partner_device_id"}
        for field in fields.values():
            assert field["required"] is True
            assert field["selector"]["device"]["integration"] == DOMAIN
        assert hass.services.has_service(DOMAIN, name)


def test_link_services_translated():
    import json
    from pathlib import Path

    base = Path(__file__).parents[2] / "custom_components" / DOMAIN
    for name in ("strings.json", "translations/en.json", "translations/de.json"):
        services = json.loads((base / name).read_text())["services"]
        for service_name in ("link", "unlink"):
            assert set(services[service_name]["fields"]) == {"device_id", "partner_device_id"}
    de = json.loads((base / "translations/de.json").read_text())["services"]
    assert de["link"]["name"] == "Verkn\u00fcpfen" and de["unlink"]["name"] == "Verkn\u00fcpfung l\u00f6sen"
