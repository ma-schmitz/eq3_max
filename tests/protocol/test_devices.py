from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.messages import (
    DeviceType,
    Mode,
    decode_push_button_state,
    decode_shutter_contact_state,
    decode_thermostat_state,
    decode_wall_thermostat_control,
)


def ht():
    return MaxDevice(address=0xA1B005, serial="MEQ9000007", device_type=DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten")


def test_apply_thermostat_state_keeps_old_measured_when_missing():
    d = ht()
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A00BE")))
    assert (d.mode, d.valve, d.target, d.measured) == (Mode.MANUAL, 48, 21.0, 19.0)
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("990005")))
    assert d.measured == 19.0
    assert d.battery_low is True and d.valve == 0 and d.target == 2.5


def test_pending_cleared_when_reached():
    d = ht()
    d.set_pending(21.0, Mode.MANUAL)
    assert d.has_pending
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193028")))
    d.clear_pending_if_reached()
    assert d.has_pending
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A")))
    d.clear_pending_if_reached()
    assert not d.has_pending and d.command_failed is False


def test_pending_auto_without_temperature():
    d = ht()
    d.set_pending(None, Mode.AUTO)
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("18302A")))
    d.clear_pending_if_reached()
    assert not d.has_pending


def test_wall_control_updates_target_and_measured():
    d = MaxDevice(address=1, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT)
    d.apply_wall_state(decode_wall_thermostat_control(bytes.fromhex("2AD2")))
    assert (d.target, d.measured) == (21.0, 21.0)
    assert d.is_climate and not d.is_heating_thermostat


def test_shutter_and_button():
    fk = MaxDevice(address=2, serial="NEQ9000010", device_type=DeviceType.SHUTTER_CONTACT)
    fk.apply_shutter(decode_shutter_contact_state(b"\x92"))
    assert fk.window_open is True and fk.battery_low is True
    pb = MaxDevice(address=3, serial="KEQ9000001", device_type=DeviceType.PUSH_BUTTON)
    pb.apply_button(decode_push_button_state(bytes.fromhex("4001")))
    assert pb.rf_error is True


def test_dict_roundtrip_including_pending():
    d = ht()
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A00BE")))
    d.set_pending(22.0, Mode.MANUAL)
    d.rssi = -60.5
    again = MaxDevice.from_dict(d.to_dict())
    assert again == d
    assert again.device_type is DeviceType.HEATING_THERMOSTAT and again.pending_mode is Mode.MANUAL


def test_identity_dict_has_no_state():
    ident = ht().identity_dict()
    assert ident == {
        "address": 0xA1B005, "serial": "MEQ9000007", "device_type": 1,
        "name": "ht-bad-unten", "firmware": "", "group": 0, "config": {}, "config_source": {},
        "links": [], "radio": "",
    }


# --- Block 1: temporaer (Urlaub) ---

def test_until_from_temporary_state_and_cleared_otherwise():
    from datetime import datetime

    from custom_components.eq3_max.protocol.messages import encode_until

    d = ht()
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024") + encode_until(datetime(2026, 10, 10, 14, 30))))
    assert d.mode is Mode.TEMPORARY and d.until == datetime(2026, 10, 10, 14, 30)
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A00BE")))
    assert d.until is None


def test_wall_state_until():
    from datetime import datetime

    from custom_components.eq3_max.protocol.messages import decode_wall_thermostat_state, encode_until

    d = MaxDevice(address=1, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT)
    d.apply_wall_state(decode_wall_thermostat_state(bytes([0x1A, 0, 0x24]) + encode_until(datetime(2026, 12, 31, 23, 30)) + b"\xd2"))
    assert d.until == datetime(2026, 12, 31, 23, 30)
    d.apply_wall_state(decode_wall_thermostat_state(bytes.fromhex("19002A000000D2")))
    assert d.until is None


def test_dict_roundtrip_with_until():
    from datetime import datetime

    d = ht()
    d.mode = Mode.TEMPORARY
    d.until = datetime(2026, 10, 10, 14, 30)
    d.set_pending(18.0, Mode.TEMPORARY, until=datetime(2026, 10, 11, 9, 0))
    data = d.to_dict()
    assert data["until"] == "2026-10-10T14:30:00"
    assert data["pending_until"] == "2026-10-11T09:00:00"
    import json

    json.dumps(data)
    assert MaxDevice.from_dict(data) == d
    assert MaxDevice.from_dict(ht().to_dict()).until is None


def test_clear_pending_clears_pending_until():
    from datetime import datetime

    d = ht()
    d.set_pending(18.0, Mode.TEMPORARY, until=datetime(2026, 10, 11, 9, 0))
    d.clear_pending()
    assert d.pending_until is None



# --- Block 1, Fix-Runde 1 ---

def test_i1_short_state_keeps_known_until():
    from datetime import datetime

    from custom_components.eq3_max.protocol.messages import decode_wall_thermostat_state, encode_until

    end = datetime(2026, 10, 10, 14, 30)
    d = ht()
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024") + encode_until(end)))
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024")))
    assert d.until == end
    wt = MaxDevice(address=1, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT)
    wt.apply_wall_state(decode_wall_thermostat_state(bytes([0x1A, 0, 0x24]) + encode_until(end) + b"\xd2"))
    wt.apply_wall_state(decode_wall_thermostat_state(bytes.fromhex("1A0024")))
    assert wt.until == end
    wt.apply_wall_state(decode_wall_thermostat_state(bytes.fromhex("190024")))
    assert wt.until is None


def test_i2_pending_temporary_needs_matching_until():
    from datetime import datetime

    from custom_components.eq3_max.protocol.messages import encode_until

    old, new = datetime(2026, 10, 10, 14, 30), datetime(2026, 10, 11, 9, 0)
    d = ht()
    d.set_pending(18.0, Mode.TEMPORARY, until=new)
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024") + encode_until(old)))
    d.clear_pending_if_reached()
    assert d.has_pending
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024")))
    d.clear_pending_if_reached()
    assert d.has_pending
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024") + encode_until(new)))
    d.clear_pending_if_reached()
    assert not d.has_pending


# --- Fix: heat nach away/boost ---

def test_last_comfort_follows_manual_reports_above_off():
    d = ht()
    assert d.last_comfort is None
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A")))  # manual 21.0
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193009")))  # manual 4.5 = off
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1A3024")))  # temporary 18.0
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("1B303C")))  # boost 30.0
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("182826")))  # auto 19.0
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193027")))  # manual 19.5
    assert d.last_comfort == 19.5


def test_last_comfort_from_wall_state():
    from custom_components.eq3_max.protocol.messages import decode_wall_thermostat_state

    wt = MaxDevice(address=1, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT)
    wt.apply_wall_state(decode_wall_thermostat_state(bytes.fromhex("19002A000000D2")))
    assert wt.last_comfort == 21.0
    wt.apply_wall_state(decode_wall_thermostat_control(bytes.fromhex("24D2")))  # no mode bits
    assert wt.last_comfort == 21.0


def test_last_comfort_survives_dict_roundtrip_and_is_optional():
    d = ht()
    d.last_comfort = 21.5
    again = MaxDevice.from_dict(d.to_dict())
    assert again.last_comfort == 21.5
    data = ht().to_dict()
    data.pop("last_comfort")
    assert MaxDevice.from_dict(data).last_comfort is None


# --- Fix-Runde 1: Fenster-auf-Temperatur ist keine Komforttemperatur ---

def test_window_open_temperature_report_is_not_comfort():
    d = ht()
    assert d.window_open_temperature == 12.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A")))  # manual 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193018")))  # manual 12.0 = window open
    assert d.target == 12.0 and d.last_comfort == 21.0
    d.window_open_temperature = 10.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193018")))
    assert d.last_comfort == 12.0


def test_window_open_temperature_is_identity_and_persists():
    d = ht()
    d.window_open_temperature = 10.0
    assert d.identity_dict()["config"]["fenster_temperatur"] == 10.0
    assert MaxDevice.from_dict(d.to_dict()).window_open_temperature == 10.0


# --- Block 2: Geraetekonfiguration ---

import pytest  # noqa: E402

from custom_components.eq3_max.protocol.devices import (  # noqa: E402
    CONFIG_TEMP_KEYS,
    CONFIG_VALVE_KEYS,
    FACTORY_CONFIG,
    IDENTITY_KEYS,
    WEEKDAYS,
)
from custom_components.eq3_max.protocol.messages import (  # noqa: E402
    FrameError,
    TemperatureConfig,
    ValveConfig,
)


def wt():
    return MaxDevice(address=0x1590B4, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT, name="wt")


def test_factory_config_values():
    assert FACTORY_CONFIG == {
        "komfort": 21.0, "eco": 17.0, "maximal": 30.5, "minimal": 4.5, "offset": 0.0,
        "fenster_temperatur": 12.0, "fenster_dauer": 15, "boost_dauer": 5, "boost_ventil": 80,
        "entkalkung_tag": "Samstag", "entkalkung_stunde": 12, "ventil_max": 100, "ventil_offset": 0,
    }
    assert WEEKDAYS == ("Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag")


def test_config_keys_per_device_type():
    assert ht().config_keys == CONFIG_TEMP_KEYS + CONFIG_VALVE_KEYS
    assert wt().config_keys == CONFIG_TEMP_KEYS
    fk = MaxDevice(1, "X", DeviceType.SHUTTER_CONTACT)
    assert fk.config_keys == ()


def test_ensure_config_defaults_marks_werksvorgabe_and_keeps_known():
    d = ht()
    d.config = {"komfort": 22.0}
    d.config_source = {"komfort": "homegear"}
    d.ensure_config_defaults()
    assert d.config == {**FACTORY_CONFIG, "komfort": 22.0}
    assert d.config_source["komfort"] == "homegear"
    assert {d.config_source[k] for k in FACTORY_CONFIG if k != "komfort"} == {"werksvorgabe"}
    w = wt()
    w.ensure_config_defaults()
    assert set(w.config) == set(CONFIG_TEMP_KEYS) and set(w.config_source) == set(CONFIG_TEMP_KEYS)


def test_stage_config_builds_whole_set_keeping_other_values():
    d = ht()
    d.ensure_config_defaults()
    d.config["eco"] = 16.5
    assert d.stage_config("komfort", 22.5) == "temp"
    assert d.pending_config["temp"] == {
        "komfort": 22.5, "eco": 16.5, "maximal": 30.5, "minimal": 4.5, "offset": 0.0,
        "fenster_temperatur": 12.0, "fenster_dauer": 15,
    }
    assert d.config["komfort"] == 21.0  # stored value stays until acknowledged
    assert d.pending_value("komfort") == 22.5 and d.pending_value("boost_dauer") is None
    assert d.temperature_config(d.pending_config["temp"]) == TemperatureConfig(22.5, 16.5, 30.5, 4.5, 0.0, 12.0, 15)


def test_stage_config_newest_wins_and_accumulates():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("komfort", 22.0)
    d.stage_config("eco", 16.0)
    d.stage_config("komfort", 23.0)
    assert d.pending_config["temp"]["komfort"] == 23.0 and d.pending_config["temp"]["eco"] == 16.0


def test_stage_config_valve_set_and_types():
    d = ht()
    d.ensure_config_defaults()
    assert d.stage_config("boost_dauer", "10") == "valve"
    d.stage_config("entkalkung_tag", "Mittwoch")
    d.stage_config("ventil_max", 90.0)
    assert d.pending_config["valve"] == {
        "boost_dauer": 10, "boost_ventil": 80, "entkalkung_tag": "Mittwoch", "entkalkung_stunde": 12,
        "ventil_max": 90, "ventil_offset": 0,
    }
    assert isinstance(d.pending_config["valve"]["ventil_max"], int)
    assert d.valve_config(d.pending_config["valve"]) == ValveConfig(10, 80, 4, 12, 90, 0)


@pytest.mark.parametrize(
    "key,value",
    [
        ("komfort", 31.0), ("offset", 4.0), ("fenster_dauer", 7), ("boost_dauer", "45"),
        ("boost_ventil", 82), ("entkalkung_tag", "Sonnabend"), ("entkalkung_stunde", 24),
        ("ventil_max", 100.5), ("ventil_offset", -1), ("unbekannt", 1),
    ],
)
def test_stage_config_rejects_invalid_without_pending(key, value):
    d = ht()
    d.ensure_config_defaults()
    with pytest.raises(FrameError):
        d.stage_config(key, value)
    assert d.pending_config == {}


def test_wall_thermostat_has_no_valve_config():
    w = wt()
    w.ensure_config_defaults()
    with pytest.raises(FrameError):
        w.stage_config("boost_dauer", 10)


def test_commit_config_sets_source_gesetzt_and_clears_matching_pending():
    d = ht()
    d.ensure_config_defaults()
    d.config_source["eco"] = "homegear"
    d.stage_config("komfort", 22.0)
    sent = dict(d.pending_config["temp"])
    d.config_failed = ["temp"]
    d.commit_config("temp", sent)
    assert d.config["komfort"] == 22.0 and d.pending_config == {} and d.config_failed == []
    assert {d.config_source[k] for k in CONFIG_TEMP_KEYS} == {"gesetzt"}
    assert d.config_source["boost_dauer"] == "werksvorgabe"


def test_commit_of_older_set_keeps_newer_pending():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("komfort", 22.0)
    older = dict(d.pending_config["temp"])
    d.stage_config("komfort", 23.0)
    d.commit_config("temp", older)
    assert d.config["komfort"] == 22.0 and d.pending_config["temp"]["komfort"] == 23.0


def test_config_survives_dict_roundtrip_and_identity_has_config():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("eco", 16.0)
    again = MaxDevice.from_dict(d.to_dict())
    assert again == d
    ident = d.identity_dict()
    assert ident["config"] == d.config and ident["config_source"] == d.config_source
    assert "pending_config" not in ident and "window_open_temperature" not in IDENTITY_KEYS


def test_window_open_temperature_is_fenster_temperatur():
    d = ht()
    d.ensure_config_defaults()
    d.config["fenster_temperatur"] = 10.0
    assert d.window_open_temperature == 10.0
    d.window_open_temperature = 9.0
    assert d.config["fenster_temperatur"] == 9.0


def test_note_comfort_uses_fenster_temperatur():
    d = ht()
    d.ensure_config_defaults()
    d.config["fenster_temperatur"] = 15.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19302A")))  # manual 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("19301E")))  # manual 15.0 = window
    assert d.last_comfort == 21.0
    d.apply_thermostat_state(decode_thermostat_state(bytes.fromhex("193018")))  # manual 12.0
    assert d.last_comfort == 12.0


def test_legacy_window_open_temperature_becomes_config():
    data = ht().to_dict()
    data.pop("config")
    data.pop("config_source")
    data["window_open_temperature"] = 10.0
    d = MaxDevice.from_dict(data)
    assert d.config == {"fenster_temperatur": 10.0}
    assert d.config_source == {"fenster_temperatur": "homegear"}
    data["window_open_temperature"] = 12.0
    d = MaxDevice.from_dict(data)
    assert d.config_source == {"fenster_temperatur": "werksvorgabe"}


# --- Block 2, Fix-Runde 1: Fehlschlag je Satz ---

def test_config_failed_is_kept_per_set():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("komfort", 22.0)
    d.config_failed = ["temp"]
    d.stage_config("boost_dauer", 10)
    assert d.config_failed == ["temp"]
    d.commit_config("valve", dict(d.pending_config["valve"]))
    assert d.config_failed == ["temp"] and "temp" in d.pending_config
    d.stage_config("eco", 16.0)
    assert d.config_failed == []


def test_legacy_bool_config_failed_is_converted():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("komfort", 22.0)
    data = d.to_dict()
    data["config_failed"] = True
    assert MaxDevice.from_dict(data).config_failed == ["temp"]
    data["config_failed"] = False
    assert MaxDevice.from_dict(data).config_failed == []


# --- Block 3: Verknuepfungen ---

from custom_components.eq3_max.protocol.devices import (  # noqa: E402
    LINK_ADD,
    LINK_FAILED,
    LINK_PENDING,
    LINK_REMOVE,
    LINK_WAITING,
)


def fk():
    return MaxDevice(address=0xA1B00B, serial="NEQ9000010", device_type=DeviceType.SHUTTER_CONTACT, name="fk")


def test_sleepers_are_contacts_and_buttons():
    pb = MaxDevice(address=3, serial="KEQ9000001", device_type=DeviceType.PUSH_BUTTON)
    assert fk().is_sleeper and pb.is_sleeper
    assert not ht().is_sleeper and not wt().is_sleeper


def test_link_op_is_one_per_partner_newest_wins():
    d = ht()
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_ADD, LINK_PENDING)
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_REMOVE, LINK_PENDING)
    assert len(d.pending_links) == 1
    assert d.link_op("NEQ9000010")["op"] == LINK_REMOVE
    assert d.link_op("XXX") is None


def test_commit_link_adds_and_removes_partner_and_clears_matching_op():
    d = ht()
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_ADD, LINK_PENDING)
    d.commit_link("NEQ9000010", LINK_ADD)
    assert d.links == ["NEQ9000010"] and d.pending_links == []
    d.commit_link("NEQ9000010", LINK_ADD)
    assert d.links == ["NEQ9000010"]
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_REMOVE, LINK_PENDING)
    d.commit_link("NEQ9000010", LINK_ADD)  # stale ack of the older add keeps the newer remove
    assert d.link_op("NEQ9000010")["op"] == LINK_REMOVE
    d.commit_link("NEQ9000010", LINK_REMOVE)
    assert d.links == [] and d.pending_links == []


def test_fail_link_marks_only_matching_op():
    d = ht()
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_ADD, LINK_PENDING)
    d.fail_link("NEQ9000010", LINK_REMOVE)
    assert d.link_op("NEQ9000010")["state"] == LINK_PENDING
    d.fail_link("NEQ9000010", LINK_ADD)
    assert d.link_op("NEQ9000010")["state"] == LINK_FAILED
    assert d.failed_link_ops() == [d.link_op("NEQ9000010")]


def test_forget_partner_drops_link_and_op():
    d = ht()
    d.links = ["NEQ9000010", "NEQ9000011"]
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_REMOVE, LINK_FAILED)
    assert d.forget_partner("NEQ9000010") is True
    assert d.links == ["NEQ9000011"] and d.pending_links == []
    assert d.forget_partner("NEQ9000010") is False


def test_links_and_pending_links_survive_dict_roundtrip():
    d = fk()
    d.links = ["MEQ9000007"]
    d.set_link_op("NEQ9000011", 0x1590B4, DeviceType.WALL_THERMOSTAT, LINK_ADD, LINK_WAITING)
    again = MaxDevice.from_dict(d.to_dict())
    assert again == d
    assert again.link_op("NEQ9000011") == {
        "partner": "NEQ9000011", "address": 0x1590B4, "device_type": 3, "op": "add", "state": "wartet auf Ger\u00e4t",
    }
    ident = d.identity_dict()
    assert ident["links"] == ["MEQ9000007"] and "pending_links" not in ident


def test_old_dicts_without_links_load_empty():
    data = ht().to_dict()
    del data["links"], data["pending_links"]
    d = MaxDevice.from_dict(data)
    assert d.links == [] and d.pending_links == []


def test_from_dict_drops_unreadable_link_ops_and_duplicate_links():
    data = fk().to_dict()
    data["links"] = ["MEQ9000007", "MEQ9000007", "NEQ9000010", ""]
    data["pending_links"] = [
        {"partner": "A", "address": 1, "device_type": 1, "op": "add", "state": "ausstehend"},
        {"partner": "B", "op": "bogus"},
        "junk",
    ]
    d = MaxDevice.from_dict(data)
    assert d.links == ["MEQ9000007"]
    assert [op["partner"] for op in d.pending_links] == ["A"]


def test_rejected_link_op_is_not_a_failed_one_and_survives_roundtrip():
    from custom_components.eq3_max.protocol.devices import LINK_REJECTED

    d = ht()
    d.set_link_op("NEQ9000010", 0xA1B00B, DeviceType.SHUTTER_CONTACT, LINK_ADD, LINK_PENDING)
    d.set_link_state("NEQ9000010", LINK_REMOVE, LINK_REJECTED)  # other op: ignored
    assert d.link_op("NEQ9000010")["state"] == LINK_PENDING
    d.set_link_state("NEQ9000010", LINK_ADD, LINK_REJECTED)
    assert LINK_REJECTED == "fehlgeschlagen (abgelehnt)"
    assert d.link_op("NEQ9000010")["state"] == LINK_REJECTED and d.failed_link_ops() == []
    assert MaxDevice.from_dict(d.to_dict()).link_op("NEQ9000010")["state"] == LINK_REJECTED


def test_stage_config_set_changes_several_values_at_once():
    d = ht()
    d.ensure_config_defaults()
    d.config["eco"] = 16.5
    d.config_source["eco"] = "homegear"
    assumed = d.stage_config_set("temp", {"komfort": "22.5", "fenster_dauer": 20.0})
    assert d.pending_config["temp"] == {
        "komfort": 22.5, "eco": 16.5, "maximal": 30.5, "minimal": 4.5, "offset": 0.0,
        "fenster_temperatur": 12.0, "fenster_dauer": 20,
    }
    assert isinstance(d.pending_config["temp"]["fenster_dauer"], int)
    # Factory values that go along unchanged (not those set now, not homegear ones).
    assert assumed == ["maximal", "minimal", "offset", "fenster_temperatur"]


def test_stage_config_set_builds_on_pending_set():
    d = ht()
    d.ensure_config_defaults()
    d.stage_config("maximal", 28.0)
    assumed = d.stage_config_set("temp", {"komfort": 22.0})
    assert d.pending_config["temp"]["maximal"] == 28.0
    assert "maximal" not in assumed and "komfort" not in assumed


@pytest.mark.parametrize(
    "kind,values",
    [
        ("temp", {}),
        ("temp", {"komfort": 22.0, "eco": 31.0}),
        ("temp", {"komfort": 22.0, "boost_dauer": 10}),
        ("valve", {"komfort": 22.0}),
        ("bogus", {"komfort": 22.0}),
    ],
)
def test_stage_config_set_rejects_invalid_without_pending(kind, values):
    d = ht()
    d.ensure_config_defaults()
    d.mark_config_failed("temp")
    with pytest.raises(FrameError):
        d.stage_config_set(kind, values)
    assert d.pending_config == {} and d.config_failed == ["temp"]


def test_stage_config_set_valve_not_on_wall_thermostat():
    d = MaxDevice(address=0x1590B4, serial="NEQ9000011", device_type=DeviceType.WALL_THERMOSTAT)
    d.ensure_config_defaults()
    with pytest.raises(FrameError):
        d.stage_config_set("valve", {"boost_dauer": 10})
    assert d.stage_config_set("temp", {"offset": -1.0})
    assert d.pending_config["temp"]["offset"] == -1.0
