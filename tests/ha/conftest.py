"""Fixtures for the HA layer."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eq3_max.const import CONF_ADDRESS, CONF_DEVICES, CONF_PORT, DOMAIN
from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.hub import ResetResult
from custom_components.eq3_max.protocol.messages import DeviceType, normalize_temperature

HT = 0xA1B005
FK = 0xA1B00B
PB = 0xA1B001
WT = 0x1590B4


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeHub:
    last: FakeHub | None = None

    def __init__(
        self, port, address, devices, *, on_update, on_button, on_device_added, on_problem, radios=(), brake=False, **_kw
    ):
        self.port = port
        self.address = address
        self.devices = {d.address: d for d in devices}
        self.on_update = on_update
        self.on_button = on_button
        self.on_device_added = on_device_added
        self.on_problem = on_problem
        self.brake = brake
        self.connected = True
        self.version = "V 1.66 nanoCUL868"
        self.airtime_last_hour = 0.0
        self.queue_length = 0
        self.commands = []
        self.pairing = None
        self.started = False
        self.raw_history = {}
        self.resets = []
        self.reset_result = ResetResult.ACKED
        self.reset_error = None
        self.kwargs = _kw
        self.radios = list(radios)
        # Per module: connected (main is "" and follows self.connected).
        self.radio_connected = {r.id: True for r in self.radios}
        self.radio_heard = {}
        FakeHub.last = self

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    def set_temperature(self, address, temperature, mode, until=None):
        if temperature is not None:
            temperature = normalize_temperature(temperature)
        self.commands.append((address, temperature, mode) if until is None else (address, temperature, mode, until))
        self.devices[address].set_pending(temperature, mode, until)
        self.on_update(self.devices[address])

    def set_config(self, address, key, value):
        dev = self.devices[address]
        kind = dev.stage_config(key, value)
        self.commands.append(("config", address, key, value))
        self.on_update(dev)
        return kind

    def set_config_set(self, address, kind, values):
        dev = self.devices[address]
        assumed = dev.stage_config_set(kind, values)
        # One whole set = one telegram.
        self.commands.append(("config_set", address, kind, dict(dev.pending_config[kind])))
        self.on_update(dev)
        return assumed

    def ack_config(self, address, kind):
        """Simulate the device acknowledging the pending set of this kind."""
        dev = self.devices[address]
        dev.commit_config(kind, dict(dev.pending_config[kind]))
        self.on_update(dev)

    async def factory_reset(self, address):
        self.resets.append(address)
        if self.reset_error is not None:
            raise self.reset_error
        if self.reset_result is ResetResult.ACKED:
            dev = self.devices.pop(address)
            for other in self.devices.values():
                if other.forget_partner(dev.serial):
                    self.on_update(other)
        return self.reset_result

    def link(self, a, b):
        self._change_link("link", a, b, "add")

    def unlink(self, a, b):
        self._change_link("unlink", a, b, "remove")

    def _change_link(self, name, a, b, op):
        from custom_components.eq3_max.protocol.hub import plan_link

        for target, partner in plan_link(self.devices, a, b, op):
            state = "wartet auf Ger\u00e4t" if target.is_sleeper else "ausstehend"
            target.set_link_op(partner.serial, partner.address, partner.device_type, op, state)
        self.commands.append((name, a, b))
        self.on_update(self.devices[a])
        self.on_update(self.devices[b])

    def heard_since(self, radio, wall_time):
        # Main: any device telegram; extra modules: set radio_heard[id] in the test.
        if radio == "":
            return any((d.last_seen or 0) > wall_time for d in self.devices.values())
        return self.radio_heard.get(radio, 0) > wall_time

    @property
    def any_connected(self):
        return self.connected or any(self.radio_connected.values())

    def reachable(self, address):
        radio = self.devices[address].radio
        return self.radio_connected.get(radio, self.connected) if radio else self.connected

    @property
    def radio_ids(self):
        return ["", *(r.id for r in self.radios)]

    def radio_status(self):
        main = {"id": "", "target": self.port, "connected": self.connected, "version": self.version,
                "airtime": self.airtime_last_hour, "queue": self.queue_length}
        return [main, *({"id": r.id, "target": r.port, "connected": self.radio_connected[r.id],
                         "version": "V 1.26.08 a-culfw CUBE", "airtime": 0.0, "queue": 0} for r in self.radios)]

    def set_radio(self, address, radio):
        from custom_components.eq3_max.protocol.messages import FrameError

        if radio not in self.radio_ids:
            raise FrameError(f"unknown radio module {radio!r}")
        self.devices[address].radio = radio
        self.commands.append(("radio", address, radio))
        self.on_update(self.devices[address])

    def open_pairing(self, seconds=60):
        self.pairing = seconds

    @property
    def pairing_remaining(self):
        return float(self.pairing or 0)


@pytest.fixture
def fake_hub():
    FakeHub.last = None
    with patch("custom_components.eq3_max.coordinator.MaxHub", FakeHub):
        yield FakeHub


def identity_devices():
    return [
        MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten").identity_dict(),
        MaxDevice(FK, "NEQ9000010", DeviceType.SHUTTER_CONTACT, name="fk-schlafzimmer").identity_dict(),
        MaxDevice(PB, "KEQ9000001", DeviceType.PUSH_BUTTON, name="taster").identity_dict(),
        MaxDevice(WT, "NEQ9000011", DeviceType.WALL_THERMOSTAT, name="wt-wohnzimmer").identity_dict(),
    ]


@pytest.fixture
def entry():
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="C0FFEE",
        title="eQ-3 MAX! C0FFEE",
        data={CONF_PORT: "/dev/serial/by-path/usb-0:13", CONF_ADDRESS: "C0FFEE", CONF_DEVICES: identity_devices()},
    )


@pytest.fixture
async def setup_entry(hass, entry, fake_hub):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
