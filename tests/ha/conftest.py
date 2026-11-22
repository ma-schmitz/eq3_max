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
        self, port, address, devices, *, on_update, on_button, on_device_added, on_problem,
        on_device_removed=lambda dev: None, radios=(), brake=False, **_kw
    ):
        self.port = port
        self.address = address
        self.devices = {d.address: d for d in devices}
        self.on_update = on_update
        self.on_button = on_button
        self.on_device_added = on_device_added
        self.on_problem = on_problem
        self.on_device_removed = on_device_removed
        self.brake = brake
        self.connected = True
        self.version = "V 1.66 nanoCUL868"
        self.airtime_last_hour = 0.0
        self.queue_length = 0
        self.commands = []
        self.pairing = None
        self.pairing_radio = None
        self.pairing_foreign = {}
        self.started = False
        self.raw_history = {}
        self.resets = []
        self.week_profiles = []
        self.profile_writes = []
        # Week program as the hub: writes still running by address (plan), mates that
        # refuse, and a gate wait_week_profile waits for (None = done at once).
        self.profile_running = {}
        self.profile_refuse = set()
        self.profile_gate = None
        self.profile_waited = []
        self.profile_forced = []
        self.airtime_stored = {"": [[1.0, 1.1]]}
        self.airtime_restored = None
        self.week_profile_error = None
        self.waiting_budget = False
        self.pending = []
        self.reset_result = ResetResult.ACKED
        self.reset_error = None
        self.kwargs = _kw
        self.radios = list(radios)
        # Per module: connected (main is "" and follows self.connected).
        self.radio_connected = {r.id: True for r in self.radios}
        self.radio_heard = {}
        self.virtual = FakeVirtuals(self)
        FakeHub.last = self

    def airtime_state(self):
        return self.airtime_stored

    def restore_airtime(self, state):
        self.airtime_restored = state

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    def set_temperature(self, address, temperature, mode, until=None):
        from custom_components.eq3_max.protocol.messages import FrameError, Mode

        dev = self.devices[address]
        in_room = (dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT) or any(
            w.virtual and w.device_type is DeviceType.WALL_THERMOSTAT and w.serial in dev.links
            for w in self.devices.values()
        )
        if mode is Mode.AUTO and in_room and not self.virtual.program_known(address):
            raise FrameError("no complete week program known", key="virtual_no_program")
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
        _no_radio(self.devices[address])
        self.resets.append(address)
        if self.reset_error is not None:
            raise self.reset_error
        if self.reset_result is ResetResult.ACKED:
            dev = self.devices.pop(address)
            for other in self.devices.values():
                if other.forget_partner(dev.serial):
                    self.on_update(other)
        return self.reset_result

    async def set_time(self, address):
        from custom_components.eq3_max.protocol.messages import FrameError

        _no_radio(self.devices[address])
        if not self.devices[address].is_climate:
            raise FrameError("this device has no clock", key="no_clock")
        if getattr(self, "time_error", None):
            raise FrameError(self.time_error)
        self.commands.append(("time", address))

    def room_of(self, dev):
        from custom_components.eq3_max.protocol.hub import room_of

        return room_of(self.devices, dev)

    async def set_week_profile(self, address, days, *, exclude=(), force=False):
        """As the hub: the room's other thermostats get the days too (but those in
        `exclude`); `profile_writes` lists every device written by radio."""
        self.profile_forced.append(force)
        from custom_components.eq3_max.protocol.devices import WEEKDAYS
        from custom_components.eq3_max.protocol.messages import FrameError, format_until

        if self.week_profile_error is not None:
            raise FrameError(self.week_profile_error)
        self.week_profiles.append((address, days))
        dev = self.devices[address]
        if self.profile_running.get(address) == days:
            return {address}  # joins the running write: its call took care of the room
        members = [dev, *(m for m in self.room_of(dev) if m.address not in exclude)]
        for member in members:
            if member.address in self.profile_refuse and member is not dev:
                day = min(days)
                member.week_profile_error = {
                    "message": f"{member.name}: week program {day} refused", "key": "week_profile_rejected",
                    "placeholders": {"name": member.name, "day": str(day), "day_de": WEEKDAYS[day], "day_en": str(day)},
                    "missing": [WEEKDAYS[d] for d in sorted(days)],
                }
                continue
            if not member.virtual:
                self.profile_writes.append(member.address)
            for day, points in days.items():
                member.week_profile[WEEKDAYS[day]] = [
                    {"temperature": p.temperature, "until": format_until(p.until)} for p in points
                ]
            self.on_update(member)
        return {m.address for m in members}

    async def wait_week_profile(self, address):
        if self.profile_gate is not None:
            await self.profile_gate.wait()
        self.profile_waited.append(address)

    def link(self, a, b):
        self._change_link("link", a, b, "add")

    def unlink(self, a, b, force=False):
        if force:
            self.commands.append(("unlink", a, b, "force"))
            return
        self._change_link("unlink", a, b, "remove")

    def cancel_link(self, address, partner_serial=None):
        from custom_components.eq3_max.protocol.messages import FrameError

        dev = self.devices[address]
        partners = [partner_serial] if partner_serial else [op["partner"] for op in dev.pending_links]
        dropped = [s for s in partners if dev.link_op(s) is not None]
        if partner_serial and not dropped:
            raise FrameError("no open link request", key="link_op_unknown", serial=partner_serial)
        for serial in dropped:
            dev.drop_link_op(serial)
        self.commands.append(("cancel_link", address, partner_serial))
        return dropped

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
                "airtime": self.airtime_last_hour, "queue": self.queue_length,
                "waiting_budget": self.waiting_budget, "pending": self.pending}
        return [main, *({"id": r.id, "target": r.port, "connected": self.radio_connected[r.id],
                         "version": "V 1.26.08 a-culfw CUBE", "airtime": 0.0, "queue": 0} for r in self.radios)]

    def set_group(self, address, group):
        dev = self.devices[address]
        dev.pending_group = group
        self.commands.append(("group", address, group))
        self.on_update(dev)

    def set_room_group(self, address):
        dev = self.devices[address]
        room = [dev] + [d for d in self.devices.values() if d is not dev and d.is_climate and (dev.serial in d.links or d.serial in dev.links)]
        for member in room:
            self.set_group(member.address, 7)
        return room

    def set_poll(self, address, minutes):
        from custom_components.eq3_max.protocol.messages import FrameError

        dev = self.devices[address]
        if not dev.is_heating_thermostat or minutes not in (0, 15, 30, 60, 120, 240):
            raise FrameError("no poll")
        dev.poll_minutes = minutes
        self.commands.append(("poll", address, minutes))
        self.on_update(dev)

    def set_radio(self, address, radio):
        from custom_components.eq3_max.protocol.messages import FrameError

        if radio not in self.radio_ids:
            raise FrameError(f"unknown radio module {radio!r}")
        _no_radio(self.devices[address])
        self.devices[address].radio = radio
        self.commands.append(("radio", address, radio))
        self.on_update(self.devices[address])

    def open_pairing(self, seconds=60, radio=None):
        from custom_components.eq3_max.protocol.messages import FrameError

        if radio is not None and radio not in self.radio_connected:
            raise FrameError(f"unknown radio module {radio!r}", key="radio_unknown", name=radio)
        self.pairing = seconds
        self.pairing_radio = radio

    def radio_is_connected(self, radio):
        return self.connected if radio == "" else self.radio_connected.get(radio, False)

    @property
    def pairing_remaining(self):
        return float(self.pairing or 0)


def _no_radio(dev):
    from custom_components.eq3_max.protocol.messages import FrameError

    if dev.virtual:
        raise FrameError(f"{dev.serial} is virtual, nothing to send", key="virtual_no_radio")


class FakeVirtuals:
    """hub.virtual: records its calls in the hub's `commands`."""

    def __init__(self, hub):
        self._hub = hub
        # What remove() answers: True = gone at once, False = being removed.
        self.remove_result = True
        self._next = 0x300000

    def create(self, device_type, name, source, radio="", *, address=None):
        hub = self._hub
        hub.commands.append(("create_virtual", device_type, name, source, radio))
        if address is None:
            self._next += 1
            address = self._next
        dev = MaxDevice(
            address, f"VIRT{address:06X}", device_type, name=name, radio=radio, virtual=True, source=source
        )
        dev.ensure_config_defaults()
        hub.devices[address] = dev
        hub.on_device_added(dev)
        return dev

    def get(self, address):
        dev = self._hub.devices.get(address)
        return dev if dev is not None and dev.virtual else None

    def is_virtual(self, address):
        return self.get(address) is not None

    def room_interval(self, wall):
        return 300.0 if self.room_form(wall) else None

    def room_form(self, wall):
        """As the hub: one confirmed group on one module = "group", else "addressed"."""
        mates = [
            d for d in self._hub.devices.values()
            if d.is_heating_thermostat and not d.virtual and wall.serial in d.links and d.serial in wall.links
        ]
        if not mates:
            return None
        groups, radios = {d.group for d in mates}, {d.radio for d in mates}
        return "group" if len(groups) == 1 and 0 not in groups and len(radios) == 1 else "addressed"

    def room_form_reason(self, wall):
        """As the hub: why the room temperature goes addressed."""
        if self.room_form(wall) != "addressed":
            return None
        mates = [
            d for d in self._hub.devices.values()
            if d.is_heating_thermostat and not d.virtual and wall.serial in d.links and d.serial in wall.links
        ]
        if len({d.radio for d in mates}) > 1:
            return "modules"
        if any(d.pending_group is not None for d in mates):
            return "pending"
        return "no_group"

    def in_room(self, address):
        """As the hub: a virtual wall thermostat or a member of its room."""
        dev = self._hub.devices.get(address)
        if dev is None:
            return False
        if dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT:
            return True
        return any(
            w.virtual and w.device_type is DeviceType.WALL_THERMOSTAT and w.serial in dev.links and dev.serial in w.links
            for w in self._hub.devices.values()
        )

    def program_known(self, address):
        """As the hub: the wall thermostat (or a member's) holds all seven days."""
        from custom_components.eq3_max.protocol.devices import WEEKDAYS

        dev = self._hub.devices.get(address)
        if dev is None:
            return False
        if not (dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT):
            dev = next(
                (
                    w for w in self._hub.devices.values()
                    if w.virtual and w.device_type is DeviceType.WALL_THERMOSTAT
                    and w.serial in dev.links and dev.serial in w.links
                ),
                None,
            )
        return dev is not None and all(dev.week_profile.get(day) for day in WEEKDAYS)

    def set_window(self, address, is_open):
        self._hub.commands.append(("set_window", address, is_open))
        dev = self._hub.devices[address]
        dev.source_ok = is_open is not None
        if is_open is not None:
            dev.window_open = is_open
        self._hub.on_update(dev)

    def set_measured(self, address, celsius):
        self._hub.commands.append(("set_measured", address, celsius))
        dev = self._hub.devices[address]
        dev.source_ok = celsius is not None
        dev.measured = celsius
        self._hub.on_update(dev)

    def remove(self, address, *, force=False):
        self._hub.commands.append(("remove_virtual", address, force))
        dev = self._hub.devices[address]
        dev.removing = True
        if force or self.remove_result:
            self.finish_removal(address)
            return True
        self._hub.on_update(dev)
        return False

    def finish_removal(self, address):
        """The last partner acknowledged the unlink: the device is gone."""
        dev = self._hub.devices.pop(address)
        self._hub.on_device_removed(dev)


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
