"""MaxHub: ties transport, scheduler and device model together."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .devices import (
    KIND_TEMP,
    CONFIG_KINDS,
    DISPLAY_MEASURED,
    KIND_DISPLAY,
    KIND_VALVE,
    LINK_ADD,
    LINK_FAILED,
    LINK_PENDING,
    LINK_REJECTED,
    LINK_REMOVE,
    LINK_WAITING,
    ROOM_CONFIG_KEYS,
    WEEKDAYS,
    MaxDevice,
    config_kind,
)
from .messages import (
    DeviceType,
    Frame,
    MAX_TEMPERATURE,
    FrameError,
    Mode,
    MsgType,
    ProfilePoint,
    WEEK_PROFILE_DAYS,
    build_add_link_partner,
    build_config_temperatures,
    build_config_valve,
    build_config_week_profile,
    build_pair_pong,
    build_remove_group_id,
    build_remove_link_partner,
    build_set_display,
    build_set_group_id,
    build_reset,
    build_set_temperature,
    build_wake_up,
    build_time_information,
    decode_ack,
    decode_frame,
    decode_pair_ping,
    decode_push_button_state,
    decode_set_temperature,
    decode_shutter_contact_state,
    decode_thermostat_state,
    decode_time_information,
    decode_until,
    decode_wall_thermostat_control,
    decode_wall_thermostat_state,
    encode_frame,
    encode_week_profile_day,
    format_until,
    link_allowed,
    normalize_temperature,
    parse_until,
)
from .scheduler import (
    LOVF_RETRY_S,
    PREAMBLE_S,
    PRIO_COMMAND,
    PRIO_REPLY,
    Command,
    Outcome,
    RadioScheduler,
    airtime,
)
from .transport import TRACE, CulTransport

_LOGGER = logging.getLogger(__name__)
# A device repeats an unacknowledged telegram with the same counter, the push button
# observed up to 12 s after the first try (13.11.2026). A new press always gets a new
# counter, so a generous window cannot swallow one; too short a window let a late
# repeat toggle the light back.
DUPLICATE_WINDOW_S = 30.0
RAW_HISTORY_LEN = 10
RESET_SEND_WINDOW_S = 30.0
# Polling the measured temperature of radiator thermostats (minutes, 0 = off). They report
# it only in their own status, about a minute after a target change (measured 14.11.2026):
# the target goes up by 0.5, and back once the status came (or after POKE_TIMEOUT_S; devices
# took 19 s to a little over 3 min on 14.11.2026).
POLL_CHOICES = (0, 15, 30, 60, 120, 240)
POLL_TICK_S = 60.0
POKE_TIMEOUT_S = 300.0
RESET_MARGIN_S = 5.0
# Sleepers: send to them only while they listen after their telegram to us.
SLEEPER_DEBOUNCE_S = 0.08
FAST_DEADLINE_S = 0.3
FAST_ACK_TIMEOUT_S = 0.5


# What a link waiting for a sleeping device shows, by the sleeper's type.
LINK_WAITING_TEXT = {
    DeviceType.SHUTTER_CONTACT: "wartet auf Fensterkontakt \u2013 bitte Fenster einmal \u00f6ffnen und schlie\u00dfen",
    DeviceType.PUSH_BUTTON: "wartet auf Eco-Taster \u2013 bitte Taster einmal dr\u00fccken (oder Anlerntaste)",
}
# Only one device of the pair has the other in its links and nothing is pending.
LINK_ONE_SIDED = "einseitig"
_TYPE_NAMES = {
    DeviceType.CUBE: "Cube",
    DeviceType.HEATING_THERMOSTAT: "Heizk\u00f6rperthermostat",
    DeviceType.HEATING_THERMOSTAT_PLUS: "Heizk\u00f6rperthermostat",
    DeviceType.WALL_THERMOSTAT: "Wandthermostat",
    DeviceType.SHUTTER_CONTACT: "Fensterkontakt",
    DeviceType.PUSH_BUTTON: "Eco-Taster",
    DeviceType.PLUG_ADAPTER: "Zwischenstecker",
}


@dataclass(frozen=True)
class LinkStatus:
    """Links of one device as a pair view: complete pairs and the rest with a state."""

    partners: list[str] = field(default_factory=list)  # serials, both directions acknowledged
    pending: list[tuple[str, str]] = field(default_factory=list)  # (partner serial, state)


def _devices_by_serial(devices: dict[int, MaxDevice] | Iterable[MaxDevice]) -> dict[str, MaxDevice]:
    values = devices.values() if isinstance(devices, dict) else devices
    return {d.serial: d for d in values}


def room_of(devices: dict[int, MaxDevice], dev: MaxDevice) -> list[MaxDevice]:
    """The other thermostats of the device's room: those linked with it through a
    wall thermostat (the wall thermostat itself, and its radiators)."""
    by_serial = _devices_by_serial(devices)

    def partners(device: MaxDevice) -> list[MaxDevice]:
        found = [by_serial[s] for s in device.links if s in by_serial]
        # A half link counts as well.
        found += [d for d in devices.values() if device.serial in d.links and d not in found]
        return [d for d in found if d.is_climate]

    room: list[MaxDevice] = []
    walls = [dev] if dev.device_type is DeviceType.WALL_THERMOSTAT else [
        d for d in partners(dev) if d.device_type is DeviceType.WALL_THERMOSTAT
    ]
    for wall in walls:
        for member in (wall, *partners(wall)):
            if member is not dev and member not in room:
                room.append(member)
    return room


def link_status(devices: dict[int, MaxDevice] | Iterable[MaxDevice], dev: MaxDevice) -> LinkStatus:
    """A pair counts once both directions are acknowledged; pending operations of
    either side show as the pair's state (fehlgeschlagen before wartet before ausstehend)."""
    by_serial = _devices_by_serial(devices)
    serials: list[str] = [*dev.links, *(op["partner"] for op in dev.pending_links)]
    for other in by_serial.values():
        if other is not dev and (dev.serial in other.links or other.link_op(dev.serial) is not None):
            serials.append(other.serial)
    partners: list[str] = []
    pending: list[tuple[str, str]] = []
    for serial in dict.fromkeys(serials):
        other = by_serial.get(serial)
        ops = [(dev, dev.link_op(serial))]
        if other is not None:
            ops.append((other, other.link_op(dev.serial)))
        ops = [(owner, op) for owner, op in ops if op is not None]
        if ops:
            states = [op["state"] for _, op in ops]
            if LINK_REJECTED in states:
                state = LINK_REJECTED
            elif LINK_FAILED in states:
                state = LINK_FAILED
            elif LINK_WAITING in states:
                sleeper = next(owner for owner, op in ops if op["state"] == LINK_WAITING)
                state = LINK_WAITING_TEXT.get(sleeper.device_type, LINK_WAITING)
            else:
                state = LINK_PENDING
            pending.append((serial, state))
            continue
        mine = serial in dev.links
        theirs = other is None or dev.serial in other.links
        if mine and theirs:
            partners.append(serial)
        else:
            pending.append((serial, LINK_ONE_SIDED))
    return LinkStatus(partners, pending)


def plan_link(
    devices: dict[int, MaxDevice], a: int, b: int, op: str
) -> list[tuple[MaxDevice, MaxDevice]]:
    """Directions (device, partner) a link/unlink of a and b has to change; raises
    FrameError (German text) for unknown devices, self links, disallowed pairs and
    when there is nothing to do."""
    dev_a, dev_b = devices.get(a), devices.get(b)
    if dev_a is None or dev_b is None:
        raise FrameError("device not known to the radio module", key="device_unknown")
    if dev_a is dev_b or dev_a.serial == dev_b.serial:
        raise FrameError("a device cannot be linked with itself", key="link_self")
    if not link_allowed(dev_a.device_type, dev_b.device_type):
        raise FrameError(
            f"{dev_a.device_type.name} and {dev_b.device_type.name} cannot be linked", key="link_not_allowed"
        )
    directions = []
    queued = False
    for target, partner in ((dev_a, dev_b), (dev_b, dev_a)):
        current = target.link_op(partner.serial)
        if current is None:
            needed = (partner.serial in target.links) != (op == LINK_ADD)
        elif current["op"] != op:
            needed = True
        else:
            # Same operation already pending: only a failed one is sent again.
            needed = current["state"] in (LINK_FAILED, LINK_REJECTED)
            queued = queued or not needed
        if needed:
            directions.append((target, partner))
    if not directions:
        if queued:
            if op == LINK_ADD:
                raise FrameError("link already requested", key="link_already_requested")
            raise FrameError("removal already requested", key="unlink_already_requested")
        if op == LINK_ADD:
            raise FrameError("devices already linked", key="already_linked")
        raise FrameError("devices not linked", key="not_linked")
    return directions


class ResetResult(Enum):
    ACKED = "acked"
    UNACKED = "unacked"  # sent at least once, no ack: the device may be reset anyway
    NOT_SENT = "not_sent"


MAIN_RADIO = ""
# A telegram heard by a second module within this time is the same transmission.
CROSS_RADIO_WINDOW_S = 1.0
WEEKDAYS_EN = ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _day(day: int) -> dict[str, str]:
    """Weekday placeholders of a translated error: one per language."""
    return {"day": WEEKDAYS_EN[day], "day_en": WEEKDAYS_EN[day], "day_de": WEEKDAYS[day]}

# Telegrams to the central that the sender wants acknowledged: window contact state,
# a wall thermostat's set command, push button state (what culfw's "Za" answered).
# Status reports (0x60/0x70) are never acknowledged (as in FHEM and Homegear).
ACKNOWLEDGED_TYPES = frozenset(
    {int(MsgType.SHUTTER_CONTACT_STATE), int(MsgType.SET_TEMPERATURE), int(MsgType.PUSH_BUTTON_STATE)}
)
# Another module's copy of the same transmission arrives within this time and must not
# be answered a second time; a repeat by the device comes seconds later and is.
ACK_GUARD_S = 0.5
# A device telling a time further off than this gets ours, at most once per pause.
TIME_TOLERANCE_S = 60.0
TIME_CORRECTION_PAUSE_S = 600.0


@dataclass(frozen=True)
class RadioSpec:
    """One more radio module: id, target (serial path or host:port) and opener."""

    id: str
    port: str
    open_connection: Callable[..., Any] | None = None


class _Radio:
    def __init__(self, radio_id: str, port: str) -> None:
        self.id = radio_id
        self.port = port
        self.transport: CulTransport
        self.scheduler: RadioScheduler
        self.task: asyncio.Task | None = None


class MaxHub:
    def __init__(
        self,
        port: str,
        address: int,
        devices: Iterable[MaxDevice],
        *,
        on_update: Callable[[MaxDevice | None], None],
        on_button: Callable[[MaxDevice, str], None],
        on_device_added: Callable[[MaxDevice], None],
        on_problem: Callable[[str], None],
        open_connection: Callable[..., Any] | None = None,
        radios: Iterable[RadioSpec] = (),
        brake: bool = False,
        ack_timeout: float = 3.0,
        now: Callable[[], float] = time.time,
        local_now: Callable[[], datetime] = datetime.now,
        transport_kwargs: dict[str, Any] | None = None,
        sleeper_debounce: float = SLEEPER_DEBOUNCE_S,
        fast_deadline: float = FAST_DEADLINE_S,
        fast_ack_timeout: float = FAST_ACK_TIMEOUT_S,
        lovf_delay: float = LOVF_RETRY_S,
        poll_tick: float = POLL_TICK_S,
    ) -> None:
        self.address = address
        self.devices: dict[int, MaxDevice] = {d.address: d for d in devices}
        for dev in self.devices.values():
            dev.ensure_config_defaults()
        self._on_update = on_update
        self._on_button = on_button
        self._on_device_added = on_device_added
        self._now = now
        # Naive local wall clock: MAX! end times and the time reply use it.
        self._local_now = local_now
        self._ack_timeout = ack_timeout
        self._resets: dict[int, asyncio.Future[bool]] = {}
        self._pairing_until = 0.0
        # Module that answers new devices while pairing is open (None: whichever hears them).
        self.pairing_radio: str | None = None
        self._recent: dict[tuple[int, int, int], float] = {}
        self.raw_history: dict[int, deque[str]] = {}
        self._on_problem = on_problem
        self._brake = brake
        self._lovf_delay = lovf_delay
        self._poll_tick = poll_tick
        self._poll_task: asyncio.Task | None = None
        # Running pokes by address: the real target/mode, the poke's deadline.
        self._pokes: dict[int, dict[str, Any]] = {}
        # Week profile writes in progress by device address; they outlive their caller.
        self._profile_jobs: dict[int, asyncio.Task[None]] = {}
        # What each running write is writing: the same days asked for again join it.
        self._profile_plans: dict[int, dict[int, list[bytes]]] = {}
        self._transport_kwargs = dict(transport_kwargs or {})
        self._counter = 0
        # Who acknowledges telegrams to the central. With a USB main module the hub does
        # (its answer is on the line within a millisecond). A network module's lines
        # arrive 80-160 ms late, too late for a window contact, so there the firmware
        # keeps answering by itself ("Za", 20 ms after the telegram), as up to 0.6.x.
        self._firmware_ack = bool(getattr(open_connection, "network", False))
        # Main module first: it answers for everything the device assignment does not cover.
        self._radios: dict[str, _Radio] = {}
        for spec in (RadioSpec(MAIN_RADIO, port, open_connection), *radios):
            if spec.id in self._radios:
                raise ValueError(f"duplicate radio module id {spec.id!r}")
            self._radios[spec.id] = self._make_radio(spec)
        # "Stick deaf" or "device unreachable"? A device whose unacked command reopened a
        # module is a suspect; once that module hears anyone else, the stick was fine and
        # the device is silent: its commands no longer reopen the port until it is heard.
        self._suspects: dict[int, str] = {}
        self._silent: set[int] = set()
        # Cross-module duplicates: (src, counter, type, payload) -> (radio id, time).
        self._heard: dict[tuple[int, int, int, int, bytes], tuple[str, float]] = {}
        # (sender, counter, type) -> monotonic time of our acknowledgement.
        self._acknowledged: dict[tuple[int, int, int], float] = {}
        self._ack_guard = ACK_GUARD_S
        self._time_corrected: dict[int, float] = {}
        self._sleeper_debounce = sleeper_debounce
        self._fast_deadline = fast_deadline
        self._fast_ack_timeout = fast_ack_timeout
        self._flush_handles: dict[int, asyncio.TimerHandle] = {}
        # Unheard fast sends per (device address, partner serial) in a row.

    # --- radio modules ---------------------------------------------------------

    def _make_radio(self, spec: RadioSpec) -> _Radio:
        kwargs = dict(self._transport_kwargs)
        if spec.open_connection is not None:
            kwargs["open_connection"] = spec.open_connection
        radio = _Radio(spec.id, spec.port)

        def on_problem(kind: str) -> None:
            # The main module keeps the one-argument call of the single-module hub.
            if spec.id == MAIN_RADIO:
                self._on_problem(kind)
            else:
                self._on_problem(kind, spec.id)

        radio.transport = CulTransport(
            spec.port,
            self.address,
            # Exactly one answer per telegram. Extra modules never answer in firmware;
            # the main module does only when it is a network module (see _acknowledge).
            auto_ack=spec.id == MAIN_RADIO and self._firmware_ack,
            on_frame=lambda text: self._on_line(text, spec.id),
            on_lovf=lambda: radio.scheduler.on_lovf(),
            on_connection=self._on_connection,
            on_problem=on_problem,
            **kwargs,
        )
        radio.scheduler = RadioScheduler(
            radio.transport.write_line,
            ack_timeout=self._ack_timeout,
            brake=self._brake,
            lovf_delay=self._lovf_delay,
            on_change=lambda: self._notify(None),
            wait_ready=radio.transport.wait_connected,
            on_finished=lambda cmd: self._command_finished(cmd, radio),
            # Same clock as the transport: first send and last receive are compared.
            clock=radio.transport.clock,
            next_counter=self._next_counter,
            air_lock=self._shared_air_lock(),
        )
        return radio

    def _shared_air_lock(self) -> asyncio.Lock:
        """One lock for all modules: one transmission (and its acknowledgement) at a time."""
        lock = getattr(self, "_air_lock", None)
        if lock is None:
            lock = self._air_lock = asyncio.Lock()
        return lock

    def _next_counter(self) -> int:
        self._counter = (self._counter + 1) & 0xFF
        return self._counter

    def heard_since(self, radio_id: str, wall_time: float) -> bool:
        """The module received a telegram after this wall-clock time (time.time())."""
        radio = self._radios.get(radio_id)
        if radio is None or radio.transport.last_frame_rx is None:
            return False
        age = radio.transport.clock() - radio.transport.last_frame_rx
        return time.time() - age > wall_time

    @property
    def _transport(self) -> CulTransport:
        """Transport of the main module."""
        return self._radios[MAIN_RADIO].transport

    @property
    def _scheduler(self) -> RadioScheduler:
        """Scheduler of the main module."""
        return self._radios[MAIN_RADIO].scheduler

    @property
    def radio_ids(self) -> list[str]:
        return list(self._radios)

    def radio_status(self) -> list[dict[str, Any]]:
        """Per module: id, target, connected, version, airtime, queue, waiting_budget
        (a command is held back for airtime; main first)."""
        return [
            {
                "id": radio.id,
                "target": radio.port,
                "connected": radio.transport.connected,
                "version": radio.transport.version,
                "airtime": radio.scheduler.airtime_last_hour,
                "queue": radio.scheduler.queue_length,
                "waiting_budget": radio.scheduler.waiting_for_budget,
            }
            for radio in self._radios.values()
        ]

    def _radio_of(self, dev: MaxDevice | None) -> _Radio:
        # A device assigned to a module that is gone falls back to the main module.
        if dev is None:
            return self._radios[MAIN_RADIO]
        return self._radios.get(dev.radio) or self._radios[MAIN_RADIO]

    def _scheduler_for(self, address: int) -> RadioScheduler:
        return self._radio_of(self.devices.get(address)).scheduler

    def _submit(self, cmd: Command) -> None:
        self._scheduler_for(cmd.dst).submit(cmd)

    def _cancel_key(self, key: str) -> None:
        for radio in self._radios.values():
            radio.scheduler.cancel_key(key)

    def set_radio(self, address: int, radio_id: str) -> None:
        """Send to this device through another module from now on. Nothing goes on air:
        all modules share the central address, the device does not notice."""
        dev = self.devices[address]
        if radio_id not in self._radios:
            raise FrameError(f"unknown radio module {radio_id!r}")
        old = self._radio_of(dev)
        dev.radio = radio_id
        # The RSSI entity follows the module that now sends to the device.
        dev.rssi = dev.rssi_by_radio.get(radio_id, dev.rssi)
        new = self._radio_of(dev)
        if new is not old:
            for cmd in old.scheduler.take_dst(address):
                new.scheduler.submit(cmd)
            _LOGGER.info("MAX! %s (%s): now on radio module %s", dev.name or dev.serial, dev.serial, radio_id or "main")
        self._notify(dev)

    @property
    def connected(self) -> bool:
        return all(radio.transport.connected for radio in self._radios.values())

    @property
    def any_connected(self) -> bool:
        return any(radio.transport.connected for radio in self._radios.values())

    def radio_is_connected(self, radio_id: str) -> bool:
        radio = self._radios.get(radio_id)
        return radio is not None and radio.transport.connected

    def reachable(self, address: int) -> bool:
        """The module that sends to this device is connected."""
        return self._radio_of(self.devices.get(address)).transport.connected

    @property
    def version(self) -> str | None:
        return self._radios[MAIN_RADIO].transport.version

    @property
    def airtime_last_hour(self) -> float:
        """The busiest module: the 1 % limit applies to each transmitter."""
        return max(radio.scheduler.airtime_last_hour for radio in self._radios.values())

    @property
    def queue_length(self) -> int:
        return sum(radio.scheduler.queue_length for radio in self._radios.values())

    async def start(self) -> None:
        for radio in self._radios.values():
            await radio.transport.start()
            radio.task = asyncio.create_task(radio.scheduler.run())
        for dev in self.devices.values():
            if dev.has_pending:
                # Going out now: a "failed" mark from the store would make the first
                # connect send it a second time.
                dev.command_failed = False
                self._submit_pending(dev)
            self._submit_pending_config(dev)
            if dev.pending_group is not None:
                dev.group_failed = False
                self._submit_group(dev)
            self._start_links(dev)
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_tick)
            try:
                self._poll_check()
            except Exception:  # noqa: BLE001 - keep polling
                _LOGGER.exception("polling the measured temperature failed")

    async def stop(self) -> None:
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
        for handle in self._flush_handles.values():
            handle.cancel()
        self._flush_handles.clear()
        for future in self._resets.values():
            if not future.done():
                future.set_result(False)
        for job in list(self._profile_jobs.values()):
            job.cancel()
            with contextlib.suppress(asyncio.CancelledError, FrameError):
                await job
        for radio in self._radios.values():
            if radio.task is not None:
                radio.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await radio.task
                radio.task = None
        for radio in self._radios.values():
            await radio.transport.stop()

    def set_temperature(
        self, address: int, temperature: float | None, mode: Mode, until: datetime | None = None
    ) -> None:
        """Queue a set command; mode TEMPORARY needs `until` (naive local, on :00/:30)."""
        dev = self.devices[address]
        self._pokes.pop(address, None)  # the user's command wins over a running poke
        # Validate first: a command the builder rejects must not leave pending state behind.
        build_set_temperature(0, self.address, dev.address, dev.group, temperature, mode, until)
        if until is not None and until <= self._local_now():
            raise FrameError(f"end time {until.isoformat()} is not in the future")
        if temperature is not None:
            # Pending must hold exactly what goes on air, or it never clears.
            temperature = normalize_temperature(temperature)
        dev.set_pending(temperature, mode, until)
        self._notify(dev)
        self._submit_set(dev, temperature, mode, until)

    # --- Measured temperature of radiator thermostats ---

    def set_poll(self, address: int, minutes: int) -> None:
        """How often (minutes, 0 = never) to make a radiator thermostat report its measured
        temperature when it does not by itself. Each poke is two set commands."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        if not dev.is_heating_thermostat:
            raise FrameError(f"{dev.device_type.name} reports its temperature by itself")
        if minutes not in POLL_CHOICES:
            raise FrameError(f"poll interval must be one of {POLL_CHOICES}, got {minutes}")
        dev.poll_minutes = minutes
        if not minutes:
            self._pokes.pop(address, None)
        self._notify(dev)

    def _poll_check(self) -> None:
        now = self._now()
        for dev in list(self.devices.values()):
            poke = self._pokes.get(dev.address)
            if poke is not None:
                if now >= poke["deadline"]:
                    _LOGGER.info("MAX! %s (%s): no status after the poke, target back", dev.name or dev.serial, dev.serial)
                    self._finish_poke(dev)
                continue
            if not dev.poll_minutes or not dev.is_heating_thermostat:
                continue
            interval = dev.poll_minutes * 60
            if dev.measured_at is not None and now - dev.measured_at < interval:
                continue
            if dev.last_poke is not None and now - dev.last_poke < interval:
                continue
            if (
                dev.mode not in (Mode.MANUAL, Mode.AUTO)
                or dev.target is None
                or dev.has_pending
                or dev.week_profile_writing
                or (dev.mode is Mode.MANUAL and dev.target == dev.window_open_temperature)
                or not self.reachable(dev.address)
                or self._scheduler_for(dev.address).waiting_for_budget
            ):
                continue
            self._poke(dev, now)

    def _poke(self, dev: MaxDevice, now: float) -> None:
        target = dev.target
        assert target is not None
        poke_target = target + 0.5 if target + 0.5 <= MAX_TEMPERATURE else target - 0.5
        self._pokes[dev.address] = {"target": target, "mode": dev.mode, "deadline": now + POKE_TIMEOUT_S}
        dev.last_poke = now
        _LOGGER.debug("MAX! %s (%s): poke %.1f for the measured temperature", dev.name or dev.serial, dev.serial, poke_target)
        address = dev.address
        self._submit(
            Command(
                dst=address,
                # Without the group: only this device.
                build=lambda c: build_set_temperature(c, self.address, address, 0, poke_target, Mode.MANUAL, None),
                key=f"set:{address}",
                deaf_probe=True,
            )
        )

    def _finish_poke(self, dev: MaxDevice) -> None:
        poke = self._pokes.pop(dev.address, None)
        if poke is None:
            return
        dev.target, dev.mode = poke["target"], poke["mode"]
        if poke["mode"] is Mode.AUTO:
            dev.set_pending(None, Mode.AUTO, None)
            self._submit_set(dev, None, Mode.AUTO, group=0)
        else:
            dev.set_pending(poke["target"], Mode.MANUAL, None)
            self._submit_set(dev, poke["target"], Mode.MANUAL, group=0)
        self._notify(dev)

    def set_config(self, address: int, key: str, value: Any) -> None:
        """Change one configuration value. Devices only take whole sets: the set with
        the other values (stored or still pending) is queued; it becomes the stored
        configuration once the device acknowledges it."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        kind = dev.stage_config(key, value)
        self._notify(dev)
        self._submit_config(dev, kind, dict(dev.pending_config[kind]), dev.assumed_factory(kind, (key,)))
        self._share_with_room(dev, (key,))

    def room_of(self, dev: MaxDevice) -> list[MaxDevice]:
        """The other thermostats of the device's room (see room_of)."""
        return room_of(self.devices, dev)

    def _share_with_room(self, dev: MaxDevice, keys: Iterable[str]) -> None:
        """Give the room's other thermostats the values a room shares. A boost started
        at the wall thermostat runs by its countdown, each radiator by its own, and the
        same goes for comfort/eco, the window settings and the decalcification: the eQ-3
        software writes them per room. Everything else on the mates stays as it is; one
        telegram per mate and set."""
        shared = [key for key in keys if key in ROOM_CONFIG_KEYS]
        if not shared:
            return
        for mate in self.room_of(dev):
            changed: dict[str, list[str]] = {}
            for key in shared:
                if key not in mate.config_keys:
                    continue
                value = dev.pending_value(key)
                if value is None:
                    value = dev.config.get(key)
                current = mate.pending_value(key)
                if current is None:
                    current = mate.config.get(key)
                if current == value:
                    continue
                try:
                    kind = mate.stage_config(key, value)
                except FrameError as err:
                    # E.g. a comfort temperature outside this device's own limits.
                    _LOGGER.warning(
                        "MAX! %s (%s): %s of %s not taken over: %s", mate.name or mate.serial, mate.serial, key,
                        dev.name or dev.serial, err,
                    )
                    continue
                changed.setdefault(kind, []).append(key)
            for kind, changed_keys in changed.items():
                _LOGGER.info(
                    "MAX! %s (%s): %s follow %s (same room)", mate.name or mate.serial, mate.serial,
                    ", ".join(changed_keys), dev.name or dev.serial,
                )
                self._notify(mate)
                self._submit_config(
                    mate, kind, dict(mate.pending_config[kind]), mate.assumed_factory(kind, changed_keys)
                )

    async def _await_command(self, cmd: Command) -> Outcome:
        """Submit and wait for the command's outcome."""
        done: asyncio.Future[Outcome] = asyncio.get_running_loop().create_future()

        def finish(_ok: bool) -> None:
            if not done.done():
                done.set_result(cmd.outcome or Outcome.NOT_SENT)

        cmd.on_done = finish
        self._submit(cmd)
        return await done

    async def set_week_profile(self, address: int, days: Mapping[int, Sequence[ProfilePoint]]) -> None:
        """Write whole days of the week profile (0 = Saturday ... 6 = Friday) to a
        thermostat: one telegram per part, acknowledged one after the other. The stored
        profile follows each acknowledged day; `week_profile_writing` lists the days still
        to come. There is no deadline: with an empty airtime budget a week takes a long
        time. The write belongs to the hub and goes on when the caller is cancelled.
        Raises FrameError (German) when the device refuses or stays silent (the remaining
        days are then not sent, `week_profile_error` keeps the reason) or the hub stops."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError("device not known to the radio module", key="device_unknown")
        if not dev.is_climate:
            raise FrameError("only thermostats have a week program", key="no_week_profile", name=dev.name or dev.serial)
        encoded: dict[int, list[bytes]] = {}
        for day, points in days.items():
            if not 0 <= day < WEEK_PROFILE_DAYS:
                raise FrameError(f"weekday must be 0 (Saturday) to 6 (Friday), got {day}", key="weekday_invalid", day=day)
            try:
                encoded[day] = encode_week_profile_day(points)
            except ValueError as err:
                raise FrameError(f"{WEEKDAYS_EN[day]}: {err}", key="week_profile_day_invalid", detail=err, **_day(day)) from err
        name = dev.name or dev.serial
        job = self._profile_jobs.get(address)
        if job is not None and self._profile_plans.get(address) != encoded:
            raise FrameError(f"{name}: a week program is being written", key="week_profile_busy", name=name)
        if job is None:
            job = self._start_profile_job(dev, encoded, days)
            # The room shares its program: the wall thermostat and its radiators switch
            # each by their own copy. Mates are written alongside; a mate that is busy
            # with other days keeps those.
            for mate in self.room_of(dev):
                if mate.address not in self._profile_jobs:
                    _LOGGER.info(
                        "MAX! %s (%s): week profile follows %s (same room)", mate.name or mate.serial,
                        mate.serial, name,
                    )
                    mate_job = self._start_profile_job(mate, encoded, days)
                    # Nobody waits for it: it reports its failure itself.
                    mate_job.add_done_callback(lambda done: done.cancelled() or done.exception())
                elif self._profile_plans.get(mate.address) != encoded:
                    _LOGGER.warning(
                        "MAX! %s (%s): busy with another week profile, does not follow %s",
                        mate.name or mate.serial, mate.serial, name,
                    )
        # Else: the same days are being written already (as a room mate): wait for that.
        try:
            await asyncio.shield(job)
        except asyncio.CancelledError:
            if job.cancelled():
                raise FrameError(
                    f"{name}: week program aborted, the radio module was stopped", key="week_profile_aborted", name=name
                ) from None
            # Nobody may be left to fetch the outcome; the job reports failures itself.
            job.add_done_callback(lambda done: done.cancelled() or done.exception())
            raise

    def _start_profile_job(
        self, dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]]
    ) -> asyncio.Task[None]:
        dev.week_profile_error = None
        dev.week_profile_writing = [WEEKDAYS[day] for day in sorted(encoded)]
        self._notify(dev)
        job = asyncio.create_task(self._write_week_profile(dev, encoded, days))
        self._profile_jobs[dev.address] = job
        self._profile_plans[dev.address] = encoded
        return job

    async def _write_week_profile(
        self, dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]]
    ) -> None:
        address = dev.address
        name = dev.name or dev.serial
        try:
            for day in sorted(encoded):
                for part, words in enumerate(encoded[day]):
                    outcome = await self._await_command(
                        Command(
                            dst=address,
                            build=lambda c, d=day, p=part, w=words: build_config_week_profile(
                                c, self.address, address, day=d, part=p, words=w
                            ),
                            key=f"wp:{address}:{day}:{part}",
                            deaf_probe=True,
                        )
                    )
                    if outcome is Outcome.NAK:
                        raise FrameError(
                            f"{name}: week program {WEEKDAYS_EN[day]} refused", key="week_profile_rejected",
                            name=name, **_day(day),
                        )
                    if outcome is not Outcome.ACKED:
                        raise FrameError(
                            f"{name}: week program {WEEKDAYS_EN[day]} not acknowledged ({outcome.value})",
                            key="week_profile_not_acknowledged", name=name, outcome=outcome.value, **_day(day),
                        )
                dev.week_profile[WEEKDAYS[day]] = [
                    {"temperature": point.temperature, "until": format_until(point.until)} for point in days[day]
                ]
                dev.week_profile_writing = [d for d in dev.week_profile_writing if d != WEEKDAYS[day]]
                _LOGGER.info("MAX! %s (%s): week profile %s acknowledged", name, dev.serial, WEEKDAYS[day])
                self._notify(dev)
        except FrameError as err:
            # For the panel: the reason as translation key plus the days not written.
            dev.week_profile_error = {
                "message": str(err),
                "key": err.key,
                "placeholders": dict(err.placeholders),
                "missing": list(dev.week_profile_writing),
            }
            _LOGGER.warning(
                "MAX! %s (%s): %s; not written: %s", name, dev.serial, err, ", ".join(dev.week_profile_writing)
            )
            raise
        finally:
            self._profile_jobs.pop(address, None)
            self._profile_plans.pop(address, None)
            if dev.week_profile_writing:
                dev.week_profile_writing = []
                self._notify(dev)

    def set_config_set(self, address: int, kind: str, values: dict[str, Any]) -> list[str]:
        """Change several values of one set: one telegram with the whole set. Returns
        the keys sent along as assumed factory settings."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        assumed = dev.stage_config_set(kind, values)
        self._notify(dev)
        self._submit_config(dev, kind, dict(dev.pending_config[kind]), assumed)
        self._share_with_room(dev, values)
        return assumed

    def _submit_pending_config(self, dev: MaxDevice, kinds: Iterable[str] | None = None) -> None:
        for kind in list(dev.pending_config if kinds is None else kinds):
            dev.clear_config_failed(kind)
            self._submit_config(dev, kind, dict(dev.pending_config[kind]))

    def _submit_config(
        self, dev: MaxDevice, kind: str, values: dict[str, Any], assumed: list[str] | None = None
    ) -> None:
        # Resends (start, reconnect, failed) report what still goes along unchanged.
        if assumed is None:
            assumed = dev.assumed_factory(kind)
        if assumed:
            # The device takes whole sets only: unknown values go out as assumed factory settings.
            _LOGGER.warning(
                "MAX! %s (%s): sending assumed factory values along: %s",
                dev.name or dev.serial, dev.serial, ", ".join(assumed),
            )
        if kind == KIND_TEMP:
            cfg = dev.temperature_config(values)
            builder: Callable[[int], Frame] = lambda c: build_config_temperatures(c, self.address, dev.address, cfg)
            key = f"cfg_temp:{dev.address}"
        elif kind == KIND_DISPLAY:
            actual = values["anzeige"] == DISPLAY_MEASURED
            builder = lambda c: build_set_display(c, self.address, dev.address, actual)
            key = f"cfg_display:{dev.address}"
        else:
            vcfg = dev.valve_config(values)
            builder = lambda c: build_config_valve(c, self.address, dev.address, vcfg)
            key = f"cfg_valve:{dev.address}"
        self._submit(
            Command(
                dst=dev.address,
                build=builder,
                key=key,
                on_done=lambda ok: self._config_done(dev, kind, values, ok),
                deaf_probe=True,
            )
        )

    def _config_done(self, dev: MaxDevice, kind: str, values: dict[str, Any], ok: bool) -> None:
        if ok:
            dev.commit_config(kind, values)
            _LOGGER.info("MAX! %s (%s): configuration %s acknowledged", dev.name or dev.serial, dev.serial, kind)
            self._notify(dev)
            return
        if dev.pending_config.get(kind) == values:
            _LOGGER.warning(
                "MAX! %s (%s): configuration %s not acknowledged", dev.name or dev.serial, dev.serial, kind
            )
            dev.mark_config_failed(kind)
            self._notify(dev)

    def link(self, a: int, b: int) -> None:
        """Link two devices: each gets AddLinkPartner with the other (acknowledged
        separately). Sleeping devices get theirs after their next telegram."""
        self._change_link(a, b, LINK_ADD)

    def unlink(self, a: int, b: int, *, force: bool = False) -> None:
        """Remove the link in both directions (RemoveLinkPartner).

        `force` removes partner b from device a only, whether or not the integration
        knows that link: for leftovers a device still carries (moved or swapped
        thermostats), which make it retry and report radio errors. The other device
        gets nothing."""
        if not force:
            self._change_link(a, b, LINK_REMOVE)
            return
        target, partner = self.devices.get(a), self.devices.get(b)
        if target is None or partner is None:
            raise FrameError("device not known to the radio module", key="device_unknown")
        if target is partner or target.serial == partner.serial:
            raise FrameError("a device cannot be linked with itself", key="link_self")
        if not link_allowed(target.device_type, partner.device_type):
            raise FrameError(
                f"{target.device_type.name} and {partner.device_type.name} cannot be linked", key="link_not_allowed"
            )
        current = target.link_op(partner.serial)
        if current is not None and current["op"] == LINK_REMOVE and current["state"] not in (LINK_FAILED, LINK_REJECTED):
            raise FrameError("removal already requested", key="unlink_already_requested")
        self._queue_link(target, partner.serial, partner.address, partner.device_type, LINK_REMOVE)
        self._notify(target)
        self._notify(partner)

    def _change_link(self, a: int, b: int, op: str) -> None:
        for target, partner in plan_link(self.devices, a, b, op):
            current = target.link_op(partner.serial)
            if (
                op == LINK_REMOVE
                and current is not None
                and current["op"] == LINK_ADD
                and current["state"] == LINK_WAITING
                and partner.serial not in target.links
            ):
                # Never went on air: forgetting it is enough.
                target.drop_link_op(partner.serial)
                continue
            self._queue_link(target, partner.serial, partner.address, partner.device_type, op)
        self._notify(self.devices[a])
        self._notify(self.devices[b])

    def _queue_link(self, target: MaxDevice, serial: str, address: int, device_type: DeviceType, op: str) -> None:
        """Thermostats get the operation now; sleepers after their next telegram."""
        if target.is_sleeper:
            # A command for an older operation must not go out any more.
            self._cancel_key(self._link_key(target, address))
            target.set_link_op(serial, address, device_type, op, LINK_WAITING)
            _LOGGER.info(
                "MAX! %s (%s): link change with %s waits for the device's next telegram",
                target.name or target.serial, target.serial, serial,
            )
        else:
            entry = target.set_link_op(serial, address, device_type, op, LINK_PENDING)
            self._submit_link(target, entry)

    @staticmethod
    def _link_key(dev: MaxDevice, partner_address: int) -> str:
        return f"link:{dev.address}:{partner_address}"

    def _start_links(self, dev: MaxDevice) -> None:
        # Refused removals of partners that are no known links (forced ones, from before
        # they were dropped right away): nothing is outstanding there.
        dev.pending_links = [
            op for op in dev.pending_links
            if not (op["op"] == LINK_REMOVE and op["state"] == LINK_REJECTED and op["partner"] not in dev.links)
        ]
        if dev.is_sleeper:
            # Whatever was on air at shutdown waits for the device again.
            for entry in dev.pending_links:
                if entry["state"] == LINK_PENDING:
                    entry["state"] = LINK_WAITING
            return
        for entry in list(dev.pending_links):
            if entry["state"] != LINK_REJECTED:
                self._submit_link(dev, entry)

    # --- Wake-up ---

    def wake_up(self, address: int) -> None:
        """Send WakeUp (0xF1): the device listens for a while after it. Not used on its
        own yet; whether it makes series (week program) more reliable is to be measured."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        if not dev.is_climate:
            raise FrameError(f"{dev.device_type.name} is not woken up")
        name = dev.name or dev.serial

        def done(ok: bool) -> None:
            _LOGGER.info("MAX! %s (%s): wake-up %s", name, dev.serial, "acknowledged" if ok else "not acknowledged")

        self._submit(
            Command(
                dst=dev.address,
                build=lambda c: build_wake_up(c, self.address, dev.address),
                key=f"wake:{dev.address}",
                on_done=done,
                deaf_probe=True,
            )
        )

    # --- Group id ---

    def set_group(self, address: int, group: int) -> None:
        """Give a thermostat a group id (1..255) or remove it (0). The new id counts once
        the device acknowledged it; until then it is pending, without an answer it is
        sent again with the device's next status."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        if not dev.is_climate:
            raise FrameError(f"{dev.device_type.name} takes no group id")
        if not 0 <= group <= 255:
            raise FrameError(f"group id must be 0..255, got {group}")
        dev.pending_group = group
        dev.group_failed = False
        self._notify(dev)
        self._submit_group(dev)

    def free_group(self, devices: Iterable[MaxDevice]) -> int:
        """Group id for these devices: one they all have (or are getting) already, else
        the smallest id no other device uses."""
        devices = list(devices)
        ids = {d.pending_group if d.pending_group is not None else d.group for d in devices}
        if len(ids) == 1 and 0 not in ids:
            return ids.pop()
        used = {
            d.pending_group if d.pending_group is not None else d.group
            for d in self.devices.values()
            if d not in devices
        }
        group = next((n for n in range(1, 256) if n not in used), None)
        if group is None:
            raise FrameError("no free group id")
        return group

    def set_room_group(self, address: int) -> list[MaxDevice]:
        """Give the device and the thermostats of its room one common group id."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        room = [dev, *self.room_of(dev)]
        group = self.free_group(room)
        for member in room:
            if (member.pending_group if member.pending_group is not None else member.group) != group:
                self.set_group(member.address, group)
        # The devices do not report their group: one left from Cube/Homegear times with
        # this id would follow the room. The other thermostats lose it once (RemoveGroupId).
        for other in self.devices.values():
            if other in room or not other.is_climate:
                continue
            if (other.pending_group if other.pending_group is not None else other.group) == 0:
                self.set_group(other.address, 0)
        return room

    def _submit_group(self, dev: MaxDevice) -> None:
        group = dev.pending_group
        if group is None:
            return
        if group:
            builder: Callable[[int], Frame] = lambda c: build_set_group_id(c, self.address, dev.address, group)
        else:
            builder = lambda c: build_remove_group_id(c, self.address, dev.address)
        self._submit(
            Command(
                dst=dev.address,
                build=builder,
                key=f"group:{dev.address}",
                on_done=lambda ok: self._group_done(dev, group, ok),
                deaf_probe=True,
            )
        )

    def _group_done(self, dev: MaxDevice, group: int, ok: bool) -> None:
        if dev.pending_group != group:
            return  # a newer request replaced this one
        name = dev.name or dev.serial
        if ok:
            dev.group = group
            dev.pending_group = None
            dev.group_failed = False
            _LOGGER.info("MAX! %s (%s): group id %s acknowledged", name, dev.serial, group or "removed")
        else:
            dev.group_failed = True
            _LOGGER.warning("MAX! %s (%s): group id %s not acknowledged", name, dev.serial, group or "removal")
        self._notify(dev)

    def _resubmit_failed_group(self, dev: MaxDevice) -> None:
        if dev.group_failed and dev.pending_group is not None:
            dev.group_failed = False
            self._submit_group(dev)

    def _resubmit_failed_links(self, dev: MaxDevice) -> None:
        for entry in dev.failed_link_ops():
            self._submit_link(dev, entry)

    def _schedule_flush(self, dev: MaxDevice) -> None:
        """Debounce: flush once the sleeper's burst of telegrams to us is over."""
        handle = self._flush_handles.pop(dev.address, None)
        if handle is not None:
            handle.cancel()
        self._flush_handles[dev.address] = asyncio.get_running_loop().call_later(
            self._sleeper_debounce, self._flush_due, dev.address
        )

    def _flush_due(self, address: int) -> None:
        self._flush_handles.pop(address, None)
        dev = self.devices.get(address)
        if dev is not None:
            self._flush_sleeper(dev)

    def _abandon_fast_attempts(self, dev: MaxDevice) -> None:
        """Give up fast link attempts for a sleeper that just transmitted (queued ones
        and the one on air): the next flush after its burst sends afresh."""
        scheduler = self._scheduler_for(dev.address)
        for entry in dev.pending_links:
            if entry["state"] != LINK_PENDING:
                continue
            key = self._link_key(dev, entry["address"])
            if scheduler.cancel_key(key) or scheduler.abandon_inflight(key):
                entry["state"] = LINK_WAITING
                TRACE.info("sleeper %06X transmits: fast attempt %s given up", dev.address, key)

    def _flush_sleeper(self, dev: MaxDevice) -> None:
        """The sleeper just talked and listens briefly: send what waits for it, fast (Zf,
        no preamble). Never with the 1 s wake-up preamble: a contact listens only for a
        moment after its own telegram, a Zs frame arrives after that moment every time
        (twelve unheard Zs attempts on 09.11.2026) and blocks the next chances meanwhile."""
        for entry in list(dev.pending_links):
            if entry["state"] in (LINK_WAITING, LINK_FAILED):
                self._submit_link(dev, entry, awake=True, fast=True)

    def _submit_link(
        self, dev: MaxDevice, entry: dict[str, Any], *, awake: bool = False, fast: bool = False
    ) -> None:
        partner, op = entry["partner"], entry["op"]
        partner_address, partner_type = entry["address"], DeviceType(entry["device_type"])
        builder = build_add_link_partner if op == LINK_ADD else build_remove_link_partner
        entry["state"] = LINK_PENDING
        cmd = Command(
            dst=dev.address,
            build=lambda c: builder(c, self.address, dev.address, partner_address, partner_type),
            key=self._link_key(dev, partner_address),
            # A sleeper listens only for a moment after its telegram: next in line.
            priority=PRIO_REPLY if awake else PRIO_COMMAND,
            # Only always-listening devices are deaf probes: a sleeper that missed
            # its window says nothing about the stick.
            deaf_probe=not dev.is_sleeper,
            fast=fast,
        )
        if fast:
            # Only worth sending while the device still listens: one attempt, short wait.
            cmd.deadline = self._scheduler_for(dev.address).now() + self._fast_deadline
            cmd.retries = 0
            cmd.ack_timeout = self._fast_ack_timeout
        cmd.on_done = lambda _ok: self._link_done(dev, partner, op, cmd)
        self._submit(cmd)

    def _link_done(self, dev: MaxDevice, partner: str, op: str, cmd: Command) -> None:
        name = dev.name or dev.serial
        if cmd.outcome is Outcome.ACKED:
            dev.commit_link(partner, op)
            _LOGGER.info("MAX! %s (%s): link %s %s acknowledged", name, dev.serial, op, partner)
            self._notify_pair(dev, partner)
            return
        current = dev.link_op(partner)
        if current is None or current["op"] != op:
            return
        if cmd.outcome is Outcome.NAK and op == LINK_REMOVE and partner not in dev.links:
            # A forced removal of a partner we do not know of either: the device does
            # not carry it, there is nothing left to do.
            dev.drop_link_op(partner)
            _LOGGER.info("MAX! %s (%s): no partner %s to remove (refused)", name, dev.serial, partner)
        elif cmd.outcome is Outcome.NAK:
            # The device refused: no automatic resend, only a new request.
            dev.set_link_state(partner, op, LINK_REJECTED)
            _LOGGER.warning("MAX! %s (%s): link %s %s rejected", name, dev.serial, op, partner)
        elif dev.is_sleeper:
            # Asleep again (or never reached): the next telegram is the next chance.
            dev.set_link_state(partner, op, LINK_WAITING)
            _LOGGER.info(
                "MAX! %s (%s): link %s %s not acknowledged (%s), waiting for the next telegram",
                name, dev.serial, op, partner, cmd.outcome.value if cmd.outcome else "?",
            )
        else:
            dev.fail_link(partner, op)
            _LOGGER.warning("MAX! %s (%s): link %s %s not acknowledged", name, dev.serial, op, partner)
        self._notify_pair(dev, partner)

    def _notify_pair(self, dev: MaxDevice, partner: str) -> None:
        self._notify(dev)
        other = _devices_by_serial(self.devices).get(partner)
        if other is not None and other is not dev:
            self._notify(other)

    async def factory_reset(
        self, address: int, *, send_window: float = RESET_SEND_WINDOW_S, margin: float = RESET_MARGIN_S
    ) -> ResetResult:
        """Send a factory reset; on an ack the device is dropped from the hub.

        The reset goes on air only within `send_window` seconds; the call never waits
        longer than send_window + ack timeout + margin, and hub.stop() ends it.
        """
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        if address in self._resets:
            raise FrameError("factory reset already running", key="reset_running")
        done: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        unlinked: list[MaxDevice] = []

        def on_done(ok: bool) -> None:
            if done.done():
                return
            if ok:
                # Synchronously, before the scheduler picks the next command: queued
                # set commands for the reset device must not go out any more.
                if self.devices.get(dev.address) is dev:
                    del self.devices[dev.address]
                for prefix in ("set", "cfg_temp", "cfg_valve"):
                    self._cancel_key(f"{prefix}:{dev.address}")
                for entry in dev.pending_links:
                    self._cancel_key(self._link_key(dev, entry["address"]))
                # The reset device is gone: drop it from what the others show and have
                # pending. Partners that have it in their radio link table get a
                # RemoveLinkPartner (address/type captured from the removed device).
                for other in self.devices.values():
                    had_link = dev.serial in other.links
                    if other.forget_partner(dev.serial):
                        self._cancel_key(self._link_key(other, dev.address))
                        unlinked.append(other)
                    if had_link:
                        self._queue_link(other, dev.serial, dev.address, dev.device_type, LINK_REMOVE)
            done.set_result(ok)

        cmd = Command(
            dst=dev.address,
            build=lambda c: build_reset(c, self.address, dev.address),
            # No key: a reset must never be replaced silently, on_done must run.
            on_done=on_done,
            deaf_probe=True,
            deadline=self._scheduler_for(dev.address).now() + send_window,
        )
        self._resets[address] = done
        self._submit(cmd)
        try:
            async with asyncio.timeout(send_window + self._ack_timeout + margin):
                ok = await done
        except TimeoutError:
            ok = False
        finally:
            self._resets.pop(address, None)
        if not ok:
            return ResetResult.UNACKED if cmd.sent else ResetResult.NOT_SENT
        _LOGGER.warning("MAX! %s (%s): factory reset acknowledged", dev.name or dev.serial, dev.serial)
        for other in unlinked:
            self._notify(other)
        self._notify(None)
        return ResetResult.ACKED

    def open_pairing(self, seconds: float = 60, radio: str | None = None) -> None:
        """Accept new devices for `seconds`. With `radio` only that module answers them
        and they are assigned to it (pair a device on the floor that module covers)."""
        if radio is not None and radio not in self._radios:
            raise FrameError(f"unknown radio module {radio!r}", key="radio_unknown", name=radio)
        self.pairing_radio = radio
        self._pairing_until = self._now() + seconds

    @property
    def pairing_remaining(self) -> float:
        """Seconds the pairing window stays open (0 when closed)."""
        return max(0.0, self._pairing_until - self._now())

    def _expired(self, mode: Mode | None, until: datetime | None) -> bool:
        return mode is Mode.TEMPORARY and (until is None or until <= self._local_now())

    def _drop_expired(self, dev: MaxDevice) -> None:
        _LOGGER.info(
            "MAX! %s (%s): end time %s passed, temporary command dropped",
            dev.name or dev.serial, dev.serial, dev.pending_until,
        )
        dev.clear_pending()
        self._notify(dev)

    def _submit_pending(self, dev: MaxDevice) -> None:
        if self._expired(dev.pending_mode, dev.pending_until):
            self._drop_expired(dev)
            return
        self._submit_set(dev, dev.pending_target, dev.pending_mode, dev.pending_until)

    def _submit_set(
        self, dev: MaxDevice, temperature: float | None, mode: Mode | None, until: datetime | None = None,
        group: int | None = None,
    ) -> None:
        if mode is None:
            return
        group = dev.group if group is None else group

        def build(counter: int) -> Frame:
            if self._expired(mode, until):
                raise FrameError(f"end time {until} passed")
            return build_set_temperature(counter, self.address, dev.address, group, temperature, mode, until)

        self._submit(
            Command(
                dst=dev.address,
                build=build,
                key=f"set:{dev.address}",
                on_done=lambda ok: self._command_done(dev, ok, temperature, mode, until),
                is_stale=(lambda: self._expired(mode, until)) if mode is Mode.TEMPORARY else None,
                deaf_probe=True,
            )
        )

    def _command_done(
        self, dev: MaxDevice, ok: bool, temperature: float | None, mode: Mode, until: datetime | None = None
    ) -> None:
        current = (
            dev.has_pending
            and dev.pending_mode is mode
            and dev.pending_target == temperature
            and dev.pending_until == until
        )
        if ok:
            # Acknowledged: the command is no longer pending, even if a later status
            # shows another target (e.g. changed at the device in between).
            if current:
                dev.clear_pending()
                self._notify(dev)
            return
        if current and self._expired(mode, until):
            self._drop_expired(dev)
            return
        if dev.has_pending:
            _LOGGER.warning("MAX! %s (%s): command not acknowledged", dev.name or dev.serial, dev.serial)
            dev.command_failed = True
            self._notify(dev)

    @property
    def silent_devices(self) -> list[int]:
        """Devices found unreachable (not the stick); cleared when they are heard."""
        return sorted(self._silent)

    def _note_heard(self, src: int, radio: str) -> None:
        if src == self.address:
            return
        if src in self._silent or src in self._suspects:
            self._silent.discard(src)
            self._suspects.pop(src, None)
            dev = self.devices.get(src)
            if dev is not None:
                _LOGGER.info("MAX! %s (%s): heard again", dev.name or dev.serial, dev.serial)
        for suspect, suspect_radio in list(self._suspects.items()):
            if suspect_radio == radio:
                # The module hears others: the suspect itself does not answer.
                del self._suspects[suspect]
                self._silent.add(suspect)
                dev = self.devices.get(suspect)
                _LOGGER.warning(
                    "MAX! %s: does not answer although the radio works - check the device (range, battery, \"InS\")",
                    suspect if dev is None else f"{dev.name or dev.serial} ({dev.serial})",
                )

    def _command_finished(self, cmd: Command, radio: _Radio) -> None:
        """A command sent but never acknowledged while nothing at all came in: the
        stick went deaf after sending. Reopen now instead of after the watchdog's
        silence timeout; pending commands go out again on the reconnect. A device
        already found silent says nothing about the stick."""
        if not cmd.deaf_probe or cmd.outcome is not Outcome.NO_ACK or cmd.first_sent_at is None:
            return
        if cmd.dst in self._silent:
            _LOGGER.debug("no ack from silent device %06X: not blaming the stick", cmd.dst)
            return
        last_rx = radio.transport.last_frame_rx
        if last_rx is not None and last_rx >= cmd.first_sent_at:
            return
        if radio.transport.request_reopen():
            _LOGGER.warning("CUL receives nothing after sending, reopening the port (%s)", radio.port)
            self._suspects[cmd.dst] = radio.id

    def _on_connection(self, connected: bool) -> None:
        if connected:
            # Commands that ran out of attempts (e.g. during the outage) go out again;
            # not to silent devices, they get theirs with their next status.
            for dev in self.devices.values():
                if dev.address in self._silent:
                    continue
                if dev.has_pending and dev.command_failed:
                    dev.command_failed = False
                    self._submit_pending(dev)
                if dev.failed_config_kinds():
                    self._submit_pending_config(dev, dev.failed_config_kinds())
                self._resubmit_failed_group(dev)
                if not dev.is_sleeper:
                    self._resubmit_failed_links(dev)
        self._notify(None)

    def _on_line(self, text: str, radio: str = MAIN_RADIO) -> None:
        try:
            frame = decode_frame(text)
        except FrameError as err:
            _LOGGER.debug("ignoring line: %s", err)
            return
        # First of all: the sender listens for its acknowledgement only for a moment.
        self._acknowledge(frame, radio)
        self._note_heard(frame.src, radio)
        if self._pairing_only_through_other(frame, radio):
            return
        if self._heard_elsewhere(frame, radio) and not self._pairing_through(frame, radio):
            return
        try:
            self._handle(frame, radio)
        except (FrameError, ValueError, IndexError) as err:
            _LOGGER.debug("cannot decode %s: %s", text, err)
        if frame.src in self.devices:
            history = self.raw_history.setdefault(frame.src, deque(maxlen=RAW_HISTORY_LEN))
            history.append(text)

    def _acknowledge(self, frame: Frame, radio_id: str) -> None:
        """Answer a telegram to the central: once, through the module that delivered it
        first (it hears the device), right away and without wake-up preamble.

        The hub does this instead of culfw's auto-ack ("Za"): with several modules each
        would answer at the same moment and jam the other, and the wall thermostat does
        not take culfw's form (flags 00). This is the form Homegear sent: flags 02, the
        telegram's counter, payload 00."""
        if frame.dst != self.address or frame.src == self.address:
            return
        kind = int(frame.msg_type)
        # A wall thermostat whose clock was set by hand passes its time on to the central
        # (with payload) and wants that acknowledged like a command; without an answer it
        # repeats three times and reports a radio error. An empty one is a request.
        time_told = kind == int(MsgType.TIME_INFORMATION) and bool(frame.payload)
        if not time_told and (kind not in ACKNOWLEDGED_TYPES or self._firmware_ack):
            # Not to be answered, or the main module's firmware answers it.
            return
        now = time.monotonic()
        self._acknowledged = {k: t for k, t in self._acknowledged.items() if now - t < self._ack_guard}
        key = (frame.src, frame.counter, int(frame.msg_type))
        if key in self._acknowledged:
            return
        radio = self._radios.get(radio_id)
        if radio is None or not radio.transport.connected:
            return
        self._acknowledged[key] = now
        ack = Frame(frame.counter, 0x02, MsgType.ACK, self.address, frame.src, 0, b"\x00")
        try:
            # Written here and now: processing the telegram (state changes, automations)
            # comes after, or a window contact has stopped listening by then.
            radio.transport.write_now("Zf" + encode_frame(ack))
        except ConnectionError as err:
            _LOGGER.debug("acknowledgement to %06X not sent: %s", ack.dst, err)
            return
        radio.scheduler.book_airtime(airtime(ack, fast=True))

    def _is_new_pairing(self, frame: Frame) -> bool:
        """A pairing request to nobody in particular while pairing through one module."""
        return (
            self.pairing_radio is not None
            and frame.msg_type == MsgType.PAIR_PING
            and frame.dst != self.address
            and self._now() < self._pairing_until
        )

    def _pairing_only_through_other(self, frame: Frame, radio: str) -> bool:
        """Pairing goes through another module: this copy of a request is not answered."""
        return self._is_new_pairing(frame) and radio != self.pairing_radio

    def _pairing_through(self, frame: Frame, radio: str) -> bool:
        """The chosen module's copy of a pairing request counts even if another module
        delivered the same transmission first."""
        return self._is_new_pairing(frame) and radio == self.pairing_radio

    def _notify(self, dev: MaxDevice | None) -> None:
        try:
            self._on_update(dev)
        except Exception:
            _LOGGER.exception("on_update callback failed")

    def _is_duplicate(self, frame: Frame) -> bool:
        now = self._now()
        self._recent = {k: t for k, t in self._recent.items() if now - t < DUPLICATE_WINDOW_S}
        key = (frame.src, frame.counter, frame.msg_type)
        if key in self._recent:
            return True
        self._recent[key] = now
        return False

    def _heard_elsewhere(self, frame: Frame, radio: str) -> bool:
        """Several modules hear one transmission: only the first copy is handled, the
        others only add their RSSI. A repeat on the same module is a new transmission."""
        if len(self._radios) < 2:
            return False
        now = self._now()
        self._heard = {k: v for k, v in self._heard.items() if now - v[1] < CROSS_RADIO_WINDOW_S}
        key = (frame.src, frame.dst, frame.counter, frame.msg_type, bytes(frame.payload))
        first = self._heard.get(key)
        if first is not None and first[0] != radio:
            dev = self.devices.get(frame.src)
            if dev is not None:
                self._note_rssi(dev, frame, radio)
                self._notify(dev)
            return True
        self._heard[key] = (radio, now)
        return False

    @staticmethod
    def _note_rssi(dev: MaxDevice, frame: Frame, radio: str) -> None:
        if frame.rssi is None:
            return
        dev.rssi_by_radio[radio] = frame.rssi
        # The RSSI entity shows what the module that sends to the device hears.
        if radio == dev.radio:
            dev.rssi = frame.rssi

    def _handle(self, frame: Frame, radio: str = MAIN_RADIO) -> None:
        if frame.src == self.address:
            return
        if frame.msg_type == MsgType.PAIR_PING:
            self._handle_pair(frame, radio)
            return
        dev = self.devices.get(frame.src)
        if dev is None:
            _LOGGER.debug("frame from unknown address %06X (type %02X) ignored", frame.src, frame.msg_type)
            return
        self._note_rssi(dev, frame, radio)
        dev.last_seen = self._now()
        kind = frame.msg_type
        if dev.device_type is DeviceType.PLUG_ADAPTER and kind != MsgType.ACK:
            # Not supported yet: its telegrams in the log, so a user can hand in a capture.
            _LOGGER.info(
                "MAX! %s (%s, plug adapter, not supported yet): type %02X to %06X payload %s",
                dev.name or dev.serial, dev.serial, kind, frame.dst, frame.payload.hex(),
            )
        status = True
        if kind == MsgType.ACK:
            ack = decode_ack(frame.payload)
            if frame.dst == self.address:
                for module in self._radios.values():
                    module.scheduler.on_ack(frame.src, frame.counter, ack.ok)
            status = bool(ack.state_payload)
            if status:
                self._apply_state(dev, ack.state_payload)
        elif kind == MsgType.THERMOSTAT_STATE and dev.is_heating_thermostat:
            dev.apply_thermostat_state(decode_thermostat_state(frame.payload))
        elif kind == MsgType.WALL_THERMOSTAT_STATE:
            dev.apply_wall_state(decode_wall_thermostat_state(frame.payload))
        elif kind == MsgType.WALL_THERMOSTAT_CONTROL:
            dev.apply_wall_state(decode_wall_thermostat_control(frame.payload))
        elif kind == MsgType.SHUTTER_CONTACT_STATE:
            dev.apply_shutter(decode_shutter_contact_state(frame.payload))
        elif kind == MsgType.SET_TEMPERATURE and dev.device_type is DeviceType.WALL_THERMOSTAT:
            # Overheard WT -> HT command: it carries the wall thermostat's mode and target.
            mode, target = decode_set_temperature(frame.payload)
            dev.mode = mode
            if target or mode is not Mode.AUTO:
                dev.target = target
            dev.note_comfort()
            if mode is not Mode.TEMPORARY:
                dev.until = None
            elif len(frame.payload) >= 4:
                try:
                    dev.until = decode_until(frame.payload[1:4])
                except FrameError:
                    dev.until = None
        elif kind == MsgType.PUSH_BUTTON_STATE:
            state = decode_push_button_state(frame.payload)
            dev.apply_button(state)
            if not self._is_duplicate(frame):
                self._safe(self._on_button, dev, "auto" if state.auto else "eco")
        elif kind == MsgType.TIME_INFORMATION:
            status = False
            if frame.dst == self.address and not frame.payload:
                self._reply_time(frame.src)
            elif frame.dst == self.address:
                self._check_told_time(dev, frame)
        else:
            status = False
            _LOGGER.debug("unhandled message type %02X from %06X", kind, frame.src)
        reported = False
        if kind == MsgType.THERMOSTAT_STATE and dev.is_heating_thermostat and len(frame.payload) >= 5:
            if decode_thermostat_state(frame.payload).measured is not None:
                dev.measured_at = self._now()
                reported = True
        poke = self._pokes.get(dev.address)
        if poke is not None:
            # The poke stays invisible: keep the real target and mode.
            dev.target, dev.mode = poke["target"], poke["mode"]
            if reported:
                self._finish_poke(dev)
        dev.clear_pending_if_reached()
        if status and dev.command_failed and dev.has_pending:
            dev.command_failed = False
            self._submit_pending(dev)
        if status and dev.failed_config_kinds():
            self._submit_pending_config(dev, dev.failed_config_kinds())
        if status:
            self._resubmit_failed_group(dev)
        if dev.is_sleeper:
            if not (kind == MsgType.ACK and frame.dst == self.address):
                # It transmits instead of listening: a fast attempt on air is moot.
                self._abandon_fast_attempts(dev)
            # A sleeper listens once its burst is over: the telegram to us, then one to
            # each partner (40-110 ms apart, trace of 09.11.2026) and their answers. Every
            # telegram from it restarts the debounce, so the flush lands after the last one;
            # a retry towards an unreachable partner is a chance of its own.
            if dev.pending_links:
                TRACE.info(
                    "sleeper %06X talked to %s (type %02X): flush of its link operations %.0f ms after its last telegram",
                    dev.address, "us" if frame.dst == self.address else f"{frame.dst:06X}", kind,
                    self._sleeper_debounce * 1000,
                )
            self._schedule_flush(dev)
        elif status:
            self._resubmit_failed_links(dev)
        partner = self.devices.get(frame.dst)
        if partner is not None and partner is not dev and partner.is_sleeper:
            # A partner's answer belongs to the sleeper's burst as well.
            self._schedule_flush(partner)
        self._notify(dev)

    @staticmethod
    def _safe(callback: Callable[..., Any], *args: Any) -> None:
        try:
            callback(*args)
        except Exception:
            _LOGGER.exception("callback failed")

    def _apply_state(self, dev: MaxDevice, payload: bytes) -> None:
        if dev.is_heating_thermostat:
            dev.apply_thermostat_state(decode_thermostat_state(payload))
        elif dev.device_type is DeviceType.WALL_THERMOSTAT:
            dev.apply_wall_state(decode_wall_thermostat_state(payload))
        elif dev.device_type is DeviceType.SHUTTER_CONTACT:
            dev.apply_shutter(decode_shutter_contact_state(payload))
        elif dev.device_type is DeviceType.PUSH_BUTTON:
            dev.apply_button(decode_push_button_state(payload))

    def _reply_time(self, dst: int) -> None:
        self._submit(
            Command(
                dst=dst,
                build=lambda c: build_time_information(c, self.address, dst, self._local_now()),
                priority=PRIO_REPLY,
                key=f"time:{dst}",
            )
        )

    async def set_time(self, address: int) -> None:
        """Set a thermostat's clock now and wait for its acknowledgement; FrameError
        (German) when it has no clock or stays silent. The telegram carries the time at
        which the device reads it: the data follow the 1 s wake-up preamble, and a repeat
        is built with the time of the repeat."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError("device not known to the radio module", key="device_unknown")
        if not dev.is_climate:
            raise FrameError("this device has no clock", key="no_clock")
        outcome = await self._await_command(
            Command(
                dst=address,
                build=lambda c: build_time_information(
                    c, self.address, address, self._local_now() + timedelta(seconds=PREAMBLE_S)
                ),
                key=f"time:{address}",
                fresh=True,
                deaf_probe=True,
            )
        )
        name = dev.name or dev.serial
        if outcome is not Outcome.ACKED:
            raise FrameError(
                f"{name}: clock not acknowledged ({outcome.value})", key="clock_not_acknowledged",
                name=name, outcome=outcome.value,
            )
        _LOGGER.info("MAX! %s (%s): clock set", name, dev.serial)

    def _restore(self, dev: MaxDevice) -> None:
        """Put back on a factory-reset device what the integration knows of it: its side
        of the links (the partners still carry theirs), both configuration sets, the
        setpoint and the stored week program. Runs once the device took the pong."""
        name = dev.name or dev.serial
        _LOGGER.warning("MAX! %s (%s): paired again after a factory reset, restoring it", name, dev.serial)
        by_serial = _devices_by_serial(self.devices)
        partners = [by_serial[s] for s in dev.links if s in by_serial]
        dev.links = []
        dev.pending_links = []
        for partner in partners:
            self._queue_link(dev, partner.serial, partner.address, partner.device_type, LINK_ADD)
        for kind in CONFIG_KINDS:
            if any(config_kind(key) == kind for key in dev.config_keys):
                values = dev.config_set(kind)
                if None in values.values():
                    continue  # never known (display not reported yet): nothing to put back
                dev.pending_config[kind] = values
                dev.clear_config_failed(kind)
        self._submit_pending_config(dev)
        if dev.group and dev.pending_group is None:
            # After the reset it has none: give it back the one it had.
            dev.pending_group = dev.group
            dev.group = 0
            self._submit_group(dev)
        target = dev.pending_target if dev.has_pending and dev.pending_target is not None else dev.target
        if (
            dev.is_climate
            and dev.mode is Mode.MANUAL
            and target is not None
            # The window-open temperature is no setpoint to keep: it was a passing state,
            # and a linked device would hand it on to its room.
            and target != dev.window_open_temperature
        ):
            # After the reset it runs its factory program in automatic mode.
            dev.set_pending(target, Mode.MANUAL, None)
            self._submit_set(dev, target, Mode.MANUAL, None)
        if dev.is_climate and dev.week_profile and dev.address not in self._profile_jobs:
            days: dict[int, list[ProfilePoint]] = {}
            encoded: dict[int, list[bytes]] = {}
            try:
                for day_name, points in dev.week_profile.items():
                    day = WEEKDAYS.index(day_name)
                    days[day] = [ProfilePoint(float(p["temperature"]), parse_until(p["until"])) for p in points]
                    encoded[day] = encode_week_profile_day(days[day])
            except (KeyError, ValueError) as err:
                _LOGGER.warning("MAX! %s (%s): stored week profile not usable: %s", name, dev.serial, err)
            else:
                job = self._start_profile_job(dev, encoded, days)
                job.add_done_callback(lambda done: done.cancelled() or done.exception())
        self._notify(dev)

    def _check_told_time(self, dev: MaxDevice, frame: Frame) -> None:
        """A device tells us its time (clock set by hand): if it is off, send ours. Its
        repeats of the telling and our own correction must not start another one."""
        try:
            told = decode_time_information(frame.payload)
        except FrameError as err:
            _LOGGER.debug("time from %06X not readable: %s", frame.src, err)
            return
        off = abs((told - self._local_now()).total_seconds())
        if off <= TIME_TOLERANCE_S:
            return
        now = time.monotonic()
        last = self._time_corrected.get(frame.src)
        if last is not None and now - last < TIME_CORRECTION_PAUSE_S:
            return
        self._time_corrected[frame.src] = now
        _LOGGER.info(
            "MAX! %s (%s): its clock is %.0f s off, sending the time", dev.name or dev.serial, dev.serial, off
        )
        self._reply_time(frame.src)

    def _handle_pair(self, frame: Frame, radio: str = MAIN_RADIO) -> None:
        ping = decode_pair_ping(frame.payload)
        known = self.devices.get(frame.src) or next(
            (d for d in self.devices.values() if d.serial == ping.serial), None
        )
        if known is not None and known.address == frame.src and known.serial != ping.serial:
            _LOGGER.warning(
                "pairing ping at %06X carries serial %s, expected %s", frame.src, ping.serial, known.serial
            )
        to_me = frame.dst == self.address
        if not to_me and frame.dst != 0:
            return
        # A ping addressed to us is accepted even from an unknown device and with the
        # pairing window closed: the device was paired to this central before.
        if not to_me and known is None and self._now() >= self._pairing_until:
            _LOGGER.info("pairing request from %s ignored, pairing window closed", ping.serial)
            return
        if known is None:
            dev = MaxDevice(
                address=frame.src, serial=ping.serial, device_type=ping.device_type,
                name=ping.serial, firmware=ping.firmware,
                # A new device stays on the module that heard its ping first.
                radio=radio,
            )
            # A freshly paired device runs on factory settings.
            dev.ensure_config_defaults()
            self.devices[dev.address] = dev
            added = dev
        else:
            added = None
            if known.address != frame.src:
                self.devices.pop(known.address, None)
                known.address = frame.src
                self.devices[known.address] = known
            known.firmware = ping.firmware
            self._notify(known)
        src = frame.src
        if to_me:
            # A device that restarted (new batteries) asks for the time and pings its
            # central right after. It is waiting for the pong now, not for the time: a
            # time reply still being repeated would keep the pong off the air for seconds.
            self._scheduler_for(src).abandon_key(f"time:{src}")

        # A device we know that pings nobody in particular has lost its central: it was
        # reset to factory settings (it keeps address and serial).
        was_reset = known is not None and not to_me

        def pong_done(ok: bool) -> None:
            if added is not None:
                # Report a new device only once the pong is off the air: the caller
                # reloads the integration, which must not cut the pairing short.
                self._safe(self._on_device_added, added)
            if ok and was_reset and src in self.devices:
                self._restore(self.devices[src])
            if ok and (to_me or was_reset) and src in self.devices:
                # Back in touch: now it listens, and its clock starts from nothing.
                self._reply_time(src)

        self._submit(
            Command(
                dst=src,
                build=lambda c: build_pair_pong(c, self.address, src),
                priority=PRIO_REPLY,
                key=f"pong:{src}",
                on_done=pong_done,
            )
        )
