import json

from custom_components.eq3_max.homegear_import import (
    device_type_for_model,
    devices_from_export,
    export_from_homegear,
    load_export,
    save_export,
)
from custom_components.eq3_max.protocol.messages import DeviceType, Mode


class FakeProxy:
    def listDevices(self):
        return [
            {"ADDRESS": "MEQ9000007", "TYPE": "BC-RT-TRX-CyN", "FIRMWARE": "1.0", "RF_ADDRESS": 10596357},
            {"ADDRESS": "MEQ9000007:1", "TYPE": "CLIMATE"},
            {"ADDRESS": "NEQ9000010", "TYPE": "BC-SC-Rd-WM-2", "FIRMWARE": "1.0", "RF_ADDRESS": 10596361},
            {"ADDRESS": "KEQ9000001", "TYPE": "BC-PB-2-WM", "FIRMWARE": "1.3", "RF_ADDRESS": 10596353},
            {"ADDRESS": "NEQ9000011", "TYPE": "BC-TC-C-WM-2", "FIRMWARE": "1.0", "RF_ADDRESS": 10596359},
            {"ADDRESS": "XYZ0000001", "TYPE": "HM-UNKNOWN", "FIRMWARE": "1.0", "RF_ADDRESS": 1},
        ]

    def getParamset(self, address, key):
        assert key == "VALUES"
        if address == "MEQ9000007:1":
            return {"ACTUAL_TEMPERATURE": 18.8, "SET_TEMPERATURE": 21.0, "VALVE_STATE": 0, "CONTROL_MODE": 1}
        if address == "MEQ9000007:0":
            return {"LOWBAT": False, "RSSI_DEVICE": -57}
        if address == "NEQ9000010:1":
            return {"STATE": False}
        return {}


def test_model_mapping():
    assert device_type_for_model("BC-RT-TRX-CyN") is DeviceType.HEATING_THERMOSTAT
    assert device_type_for_model("BC-TC-C-WM-2") is DeviceType.WALL_THERMOSTAT
    assert device_type_for_model("BC-SC-Rd-WM-2") is DeviceType.SHUTTER_CONTACT
    assert device_type_for_model("BC-PB-2-WM") is DeviceType.PUSH_BUTTON
    assert device_type_for_model("HM-UNKNOWN") is None


def test_export_skips_channels_and_unknown_models():
    data = export_from_homegear(FakeProxy())
    assert data["version"] == 1
    serials = [d["serial"] for d in data["devices"]]
    assert serials == ["MEQ9000007", "NEQ9000010", "KEQ9000001", "NEQ9000011"]
    ht = data["devices"][0]
    assert ht["address"] == 0xA1B005 and ht["device_type"] == 1 and ht["group"] == 0
    assert ht["values"]["SET_TEMPERATURE"] == 21.0
    assert ht["values"]["LOWBAT"] is False


def test_devices_from_export_carries_last_values():
    devs = devices_from_export(export_from_homegear(FakeProxy()))
    ht = devs[0]
    assert (ht.target, ht.measured, ht.valve, ht.mode, ht.battery_low) == (21.0, 18.8, 0, Mode.MANUAL, False)
    assert devs[1].window_open is False
    assert ht.name == "MEQ9000007"


def test_save_and_load_roundtrip(tmp_path):
    data = export_from_homegear(FakeProxy())
    path = tmp_path / "export.json"
    save_export(data, str(path))
    assert load_export(str(path)) == data
    assert json.loads(path.read_text())["devices"][0]["serial"] == "MEQ9000007"


# --- Fix: Namen nach Uebernahme ---

class FakeProxyWithNames(FakeProxy):
    def getMetadata(self, serial, key):
        assert key == "NAME"
        if serial == "MEQ9000007":
            return "ht-bad-unten"
        if serial == "NEQ9000010":
            raise RuntimeError("Fault -2: no metadata")
        if serial == "KEQ9000001":
            return ""
        return 5


def test_export_takes_homegear_name_metadata():
    names = [d["name"] for d in export_from_homegear(FakeProxyWithNames())["devices"]]
    assert names == ["ht-bad-unten", "NEQ9000010", "KEQ9000001", "NEQ9000011"]


def test_export_without_metadata_support_keeps_serial():
    names = [d["name"] for d in export_from_homegear(FakeProxy())["devices"]]
    assert names == ["MEQ9000007", "NEQ9000010", "KEQ9000001", "NEQ9000011"]


def test_devices_from_export_seeds_window_open_temperature():
    data = export_from_homegear(FakeProxy())
    data["devices"][0]["values"]["WINDOW_OPEN_TEMPERATURE"] = 10.0
    devs = devices_from_export(data)
    assert devs[0].window_open_temperature == 10.0
    assert devs[1].window_open_temperature == 12.0


# --- Block 2: Geraetekonfiguration aus dem Export ---

from custom_components.eq3_max.protocol.devices import FACTORY_CONFIG  # noqa: E402

# Werte wie im echten Homegear-Export (VALUES-Paramset).
REAL_HT_VALUES = {
    "COMFORT_TEMPERATURE": 21.5, "ECO_TEMPERATURE": 16.5, "MAX_TEMPERATURE": 30.5,
    "TEMPERATURE_OFFSET": 7, "WINDOW_OPEN_TEMPERATURE": 12.0, "BOOST_POSITION": 80,
    "BOOST_TIME_PERIOD": 1, "DECALCIFICATION_WEEKDAY": 0, "DECALCIFICATION_TIME": 660,
}


def _export(device_type, values):
    return {"version": 1, "devices": [
        {"serial": "MEQ9000007", "address": 10596357, "device_type": device_type, "name": "ht", "values": values},
    ]}


def test_import_maps_real_homegear_config_values():
    dev = devices_from_export(_export(1, REAL_HT_VALUES))[0]
    assert dev.config == {
        "komfort": 21.5, "eco": 16.5, "maximal": 30.5, "minimal": 4.5, "offset": 0.0,
        "fenster_temperatur": 12.0, "fenster_dauer": 15, "boost_dauer": 5, "boost_ventil": 80,
        "entkalkung_tag": "Samstag", "entkalkung_stunde": 11, "ventil_max": 100, "ventil_offset": 0,
    }
    homegear = {"komfort", "eco", "maximal", "offset", "fenster_temperatur", "boost_dauer", "boost_ventil",
                "entkalkung_tag", "entkalkung_stunde"}
    assert {k for k, v in dev.config_source.items() if v == "homegear"} == homegear
    assert {k for k, v in dev.config_source.items() if v == "werksvorgabe"} == {
        "minimal", "fenster_dauer", "ventil_max", "ventil_offset"}


def test_import_offset_and_boost_index_tables():
    for index, offset in ((0, -3.5), (7, 0.0), (9, 1.0), (14, 3.5)):
        dev = devices_from_export(_export(1, {"TEMPERATURE_OFFSET": index}))[0]
        assert dev.config["offset"] == offset
    for index, minutes in ((0, 0), (1, 5), (6, 30), (7, 60)):
        dev = devices_from_export(_export(1, {"BOOST_TIME_PERIOD": index}))[0]
        assert dev.config["boost_dauer"] == minutes
    dev = devices_from_export(_export(1, {"DECALCIFICATION_WEEKDAY": 6, "DECALCIFICATION_TIME": 0}))[0]
    assert (dev.config["entkalkung_tag"], dev.config["entkalkung_stunde"]) == ("Freitag", 0)


def test_import_wall_thermostat_has_only_temperature_config():
    dev = devices_from_export(_export(3, REAL_HT_VALUES))[0]
    assert set(dev.config) == {"komfort", "eco", "maximal", "minimal", "offset", "fenster_temperatur", "fenster_dauer"}
    assert dev.config["komfort"] == 21.5 and dev.config_source["komfort"] == "homegear"


def test_import_without_config_values_assumes_factory_defaults():
    dev = devices_from_export(_export(1, {}))[0]
    assert dev.config == FACTORY_CONFIG
    assert set(dev.config_source.values()) == {"werksvorgabe"}


def test_import_invalid_config_value_falls_back_to_factory_default():
    dev = devices_from_export(_export(1, {"TEMPERATURE_OFFSET": 20, "BOOST_TIME_PERIOD": 9,
                                          "COMFORT_TEMPERATURE": 40.0, "DECALCIFICATION_WEEKDAY": 7}))[0]
    for key in ("offset", "boost_dauer", "komfort", "entkalkung_tag"):
        assert dev.config[key] == FACTORY_CONFIG[key] and dev.config_source[key] == "werksvorgabe"


def test_import_shutter_contact_has_no_config():
    dev = devices_from_export(_export(4, REAL_HT_VALUES))[0]
    assert dev.config == {} and dev.config_source == {}


# --- Block 3: Verknuepfungen aus Homegear (getLinks) ---

class FakeProxyWithLinks(FakeProxy):
    def __init__(self):
        self.calls = []

    def getLinks(self, serial, flags):
        self.calls.append((serial, flags))
        if serial == "MEQ9000007":
            return [
                {"SENDER": "NEQ9000010:1", "RECEIVER": "MEQ9000007:1"},
                {"SENDER": "MEQ9000007:1", "RECEIVER": "NEQ9000011:1"},
                {"SENDER": "NEQ9000011:1", "RECEIVER": "MEQ9000007:1"},
            ]
        if serial == "NEQ9000010":
            return [{"SENDER": "NEQ9000010:1", "RECEIVER": "MEQ9000007:1"}]
        if serial == "KEQ9000001":
            raise RuntimeError("Fault -2: unknown method")
        return []


def test_export_reads_links_via_getlinks():
    proxy = FakeProxyWithLinks()
    data = export_from_homegear(proxy)
    links = {d["serial"]: d["links"] for d in data["devices"]}
    assert links == {
        "MEQ9000007": ["NEQ9000010", "NEQ9000011"],
        "NEQ9000010": ["MEQ9000007"],
        "KEQ9000001": [],
        "NEQ9000011": [],
    }
    assert ("MEQ9000007", 0) in proxy.calls


def test_export_without_getlinks_support_has_no_links():
    data = export_from_homegear(FakeProxy())
    assert all(d["links"] == [] for d in data["devices"])


def test_devices_from_export_carries_links():
    devs = devices_from_export(export_from_homegear(FakeProxyWithLinks()))
    assert devs[0].links == ["NEQ9000010", "NEQ9000011"]
    assert devs[1].links == ["MEQ9000007"]
    data = _export(1, {})
    data["devices"][0]["links"] = ["NEQ9000010", "NEQ9000010", "MEQ9000007"]
    assert devices_from_export(data)[0].links == ["NEQ9000010"]
    assert devices_from_export(_export(1, {}))[0].links == []
