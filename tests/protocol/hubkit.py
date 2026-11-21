"""Shared hub test helpers: the four sample devices, recorder, clocks, sent lines, and
virtual rooms."""

from __future__ import annotations

from datetime import datetime

from custom_components.eq3_max.protocol.devices import MaxDevice
from custom_components.eq3_max.protocol.messages import DeviceType, Mode

CENTRAL = 0xC0FFEE
LOCAL_NOW = datetime(2026, 10, 9, 12, 0)
HT = 0xA1B005
FK = 0xA1B00B
PB = 0xA1B001
WT = 0x1590B4
HT2 = 0xA1B006
HT3 = 0xA1B012
VW = 0x111111
VC = 0x222222


class LocalClock:
    """Naive local wall clock for the hub (HA time in production)."""

    def __init__(self, t: datetime = LOCAL_NOW) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


def devices():
    return [
        MaxDevice(HT, "MEQ9000007", DeviceType.HEATING_THERMOSTAT, name="ht-bad-unten"),
        MaxDevice(FK, "NEQ9000010", DeviceType.SHUTTER_CONTACT, name="fk-schlafzimmer"),
        MaxDevice(PB, "KEQ9000001", DeviceType.PUSH_BUTTON, name="taster"),
        MaxDevice(WT, "NEQ9000011", DeviceType.WALL_THERMOSTAT, name="wt-wohnzimmer"),
    ]


class Recorder:
    def __init__(self):
        self.updates = []
        self.buttons = []
        self.added = []
        self.removed = []
        self.problems = []


def sent(cul):
    return [l for l in cul.written if l.startswith("Zs")]


def thermostat(h, address):
    if address not in h.devices:
        h.devices[address] = MaxDevice(
            address, f"MEQ{address:07X}", DeviceType.HEATING_THERMOSTAT, name=f"ht-{address:06X}"
        )
    return h.devices[address]


def room(h, mates=(HT, HT2), *, wall=VW, group=None):
    """A virtual wall thermostat linked on both sides with the mates, room at 21.0
    manual; with `group` every one of them has that (confirmed) group id."""
    vw = h.virtual.create(DeviceType.WALL_THERMOSTAT, "B", "sensor.b", address=wall)
    for address in mates:
        mate = thermostat(h, address)
        vw.links.append(mate.serial)
        mate.links.append(vw.serial)
        if group is not None:
            mate.group = group
    if group is not None:
        vw.group = group
    vw.target, vw.mode = 21.0, Mode.MANUAL
    return vw


def linked_contact(h, delivered=None, *, to=HT):
    """VC linked with `to` on both sides; optionally a state already delivered to it."""
    dev = h.virtual.create(DeviceType.SHUTTER_CONTACT, "F", "binary_sensor.f", address=VC)
    partner = h.devices[to]
    dev.links.append(partner.serial)
    partner.links.append(dev.serial)
    if delivered is not None:
        dev.delivered = {partner.serial: delivered}
    return dev
