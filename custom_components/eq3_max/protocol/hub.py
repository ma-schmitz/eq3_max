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
    build_ack,
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
    PairPing,
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
from .program import next_switch, override_over, program_target
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
from .virtual import Virtuals

_LOGGER = logging.getLogger(__name__)
# A push button repeats a press it got no acknowledgement for, with the same counter: up
# to 12 s later on 13.11.2026, 52 s later on 15.11.2026 (a 30 s window let that one toggle
# the office light back on). The same counter as its last press is that press for this long;
# a new press always brings a new counter (it wraps only after 256 presses).
BUTTON_REPEAT_WINDOW_S = 600.0
RAW_HISTORY_LEN = 10
RESET_SEND_WINDOW_S = 30.0
# Polling the measured temperature of radiator thermostats (minutes, 0 = off). They report
# it only in their own status, about a minute after a target change (measured 14.11.2026):
# the target goes up by 0.5, and back once the status came (or after POKE_TIMEOUT_S; devices
# took 19 s to a little over 3 min on 14.11.2026).
POLL_CHOICES = (0, 15, 30, 60, 120, 240)
# A sleeping device that did not take a link change after this many of its telegrams is
# given up ("fehlgeschlagen") until the user sends it again: otherwise every telegram of
# the device costs airtime forever (e.g. behind a firmware that acknowledges for us, #6).
SLEEPER_LINK_ROUNDS = 5
# Misses closer together than this belong to the same burst of the device (one round).
SLEEPER_ROUND_GAP_S = 3.0
POLL_TICK_S = 60.0
POKE_TIMEOUT_S = 300.0
# An unacknowledged setpoint in automatic mode holds only until the program's next switch
# point; without a known program it is not resent after this long.
AUTO_OVERRIDE_STALE_S = 900.0
# Polling pauses during a setpoint in automatic mode from Home Assistant at most this long
# (a missed report, or a switch point to the same value, would otherwise keep it going).
HA_OVERRIDE_PAUSE_MAX_S = 12 * 3600
RESET_MARGIN_S = 5.0
# Sleepers: send to them only while they listen after their telegram to us.
SLEEPER_DEBOUNCE_S = 0.08
FAST_DEADLINE_S = 0.3
FAST_ACK_TIMEOUT_S = 0.5
# How long a device that just took our pong listens for its configuration.
PAIRED_LISTEN_S = 5.0
# A series of telegrams to one thermostat (a week program): after a WakeUp (0xF1, payload
# 3F) the device listens for about 31 s, and telegrams within that time go out without
# the 1 s wake-up preamble. Counted on for WAKE_AWAKE_S (s, scheduler clock); the first
# telegram follows WAKE_SETTLE_S after the acknowledgement (FHEM lost the first one
# without a pause). Worth it from WAKE_MIN_TELEGRAMS on (the WakeUp costs a preamble).
# Off unless the hub is built with wake_series: on a radiator thermostat the WakeUp was
# acknowledged, but the telegram without preamble 0.3 s later stayed unanswered
# (22.11.2026); whether a longer pause helps is not measured yet.
WAKE_AWAKE_S = 25.0
WAKE_SETTLE_S = 0.3
WAKE_MIN_TELEGRAMS = 3
# A telegram without preamble is answered at once or not at all: one attempt, then the
# usual way. After this many series in a row with an unanswered one the device gets none
# any more (until a restart).
WAKE_FAST_ACK_TIMEOUT_S = 1.0
WAKE_GIVE_UP = 2
# Stored airtime this far (s) ahead of the clock still counts (rounding, small clock steps).
RESTORE_AHEAD_S = 60.0


# What a link waiting for a sleeping device shows, by the sleeper's type.
LINK_WAITING_TEXT = {
    DeviceType.SHUTTER_CONTACT: "wartet auf Fensterkontakt \u2013 bitte Anlerntaste kurz dr\u00fccken (oder Fenster \u00f6ffnen und schlie\u00dfen)",
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


@dataclass
class _Series:
    """Telegrams to one thermostat in a row (see WAKE_AWAKE_S): how many are left, until
    when (scheduler clock) the device listens, and how it went."""

    left: int
    enabled: bool
    awake_until: float = float("-inf")
    fast: int = 0
    failed: bool = False
    # `fast` at the last WakeUp: a WakeUp that brought none is not repeated.
    fast_at_wake: int = -1


@dataclass
class _ProfileFollowUp:
    """Days a room mate writes after its running week program: calls for the room that
    came while it was busy, merged per weekday (the latest wins)."""

    encoded: dict[int, list[bytes]] = field(default_factory=dict)
    days: dict[int, Sequence[ProfilePoint]] = field(default_factory=dict)
    task: asyncio.Task[None] | None = None


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


def _check_virtual_link(devices: dict[int, MaxDevice], dev_a: MaxDevice, dev_b: MaxDevice) -> None:
    """Additions a virtual device cannot take part in: one being removed takes no new
    partner, a virtual wall thermostat does not carry the eco button's function, and a
    thermostat follows one wall thermostat only.
    Pairs of real devices stay as they always were."""
    for dev in (dev_a, dev_b):
        if dev.virtual and dev.removing:
            raise FrameError(f"{dev.name or dev.serial} is being removed", key="virtual_removing")
    for wall, other in ((dev_a, dev_b), (dev_b, dev_a)):
        if wall.device_type is not DeviceType.WALL_THERMOSTAT:
            continue
        if wall.virtual and other.device_type is DeviceType.PUSH_BUTTON:
            raise FrameError("a virtual wall thermostat cannot be linked with an eco button", key="virtual_no_button")
        if not other.is_heating_thermostat:
            continue
        by_serial = _devices_by_serial(devices)
        # Its wall thermostats: acknowledged links and additions still on their way.
        serials = [*other.links, *(o["partner"] for o in other.pending_links if o["op"] == LINK_ADD)]
        for serial in serials:
            known = by_serial.get(serial)
            if (
                known is not None
                and known is not wall
                and known.device_type is DeviceType.WALL_THERMOSTAT
                and (known.virtual or wall.virtual)
            ):
                raise FrameError(
                    "the thermostat is already linked with another wall thermostat", key="link_second_wall"
                )


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
    if op == LINK_ADD:
        _check_virtual_link(devices, dev_a, dev_b)
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


def _no_radio(dev: MaxDevice) -> None:
    """A virtual device is the hub itself: never addressed by radio."""
    if dev.virtual:
        raise FrameError(f"{dev.name or dev.serial} is virtual, nothing to send", key="virtual_no_radio")


def _profile_day(points: Sequence[ProfilePoint]) -> list[dict[str, Any]]:
    """One day of the week profile as stored."""
    return [{"temperature": point.temperature, "until": format_until(point.until)} for point in points]


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
    def __init__(self, radio_id: str, port: str, network: bool = False) -> None:
        self.id = radio_id
        self.port = port
        # A network module (TCP): its lines arrive 80-160 ms late.
        self.network = network
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
        on_device_removed: Callable[[MaxDevice], None] = lambda dev: None,
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
        sleeper_round_gap: float = SLEEPER_ROUND_GAP_S,
        lovf_delay: float = LOVF_RETRY_S,
        poll_tick: float = POLL_TICK_S,
        lovf_wait: float | None = None,
        wake_series: bool = False,
        wake_settle: float = WAKE_SETTLE_S,
    ) -> None:
        self.address = address
        self.devices: dict[int, MaxDevice] = {d.address: d for d in devices}
        for dev in self.devices.values():
            dev.ensure_config_defaults()
        self._on_update = on_update
        self._on_button = on_button
        self._on_device_added = on_device_added
        self._on_device_removed = on_device_removed
        self.virtual = Virtuals(self)
        self._now = now
        # Naive local wall clock: MAX! end times and the time reply use it.
        self._local_now = local_now
        self._ack_timeout = ack_timeout
        self._resets: dict[int, asyncio.Future[bool]] = {}
        self._pairing_until = 0.0
        # Module that answers new devices while pairing is open (None: whichever hears them).
        self.pairing_radio: str | None = None
        # Devices that asked to pair while the window was open but are still paired to
        # another central (serial -> address, central); cleared on the next opening.
        self.pairing_foreign: dict[str, dict[str, int]] = {}
        # Last press per push button: (counter, time).
        self._last_press: dict[int, tuple[int, float]] = {}
        self.raw_history: dict[int, deque[str]] = {}
        self._on_problem = on_problem
        self._brake = brake
        self._lovf_delay = lovf_delay
        self._lovf_wait = lovf_wait
        self._poll_tick = poll_tick
        self._poll_task: asyncio.Task | None = None
        # Series without preamble after a WakeUp (week programs): on at all, the pause
        # after the WakeUp, and per device the series in a row that had an unanswered one.
        self._wake_series = wake_series
        self._wake_settle = wake_settle
        self._series_failed: dict[int, int] = {}
        # Running pokes by address: the real target/mode, the poke's deadline.
        self._pokes: dict[int, dict[str, Any]] = {}
        # Week profile writes in progress by device address; they outlive their caller.
        self._profile_jobs: dict[int, asyncio.Task[None]] = {}
        # Running writes that leave no day of their plan out (a forced call may join them).
        self._profile_full: set[int] = set()
        # What each running write is writing: the same days asked for again join it.
        self._profile_plans: dict[int, dict[int, list[bytes]]] = {}
        # Room mates busy with other days: what they write once their running write ends.
        self._profile_followups: dict[int, _ProfileFollowUp] = {}
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
        self._link_missed_at: dict[tuple[int, str], float] = {}
        self._sleeper_round_gap = sleeper_round_gap
        self._fast_ack_timeout = fast_ack_timeout
        self._flush_handles: dict[int, asyncio.TimerHandle] = {}
        # Unheard fast sends per (device address, partner serial) in a row.

    # --- radio modules ---------------------------------------------------------

    def _make_radio(self, spec: RadioSpec) -> _Radio:
        kwargs = dict(self._transport_kwargs)
        if spec.open_connection is not None:
            kwargs["open_connection"] = spec.open_connection
        radio = _Radio(spec.id, spec.port, bool(getattr(spec.open_connection, "network", False)))

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
            lovf_wait=self._lovf_wait,
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
        (a command is held back for airtime; main first), waiting_reason ("brake" or
        "module", see RadioScheduler.waiting_reason), pending (the command on air
        and the waiting ones, see RadioScheduler.pending)."""
        return [
            {
                "id": radio.id,
                "target": radio.port,
                "connected": radio.transport.connected,
                "version": radio.transport.version,
                "airtime": radio.scheduler.airtime_last_hour,
                "queue": radio.scheduler.queue_length,
                "waiting_budget": radio.scheduler.waiting_for_budget,
                "waiting_reason": radio.scheduler.waiting_reason,
                "pending": radio.scheduler.pending(),
            }
            for radio in self._radios.values()
        ]

    def _radio_of(self, dev: MaxDevice | None) -> _Radio:
        # A device assigned to a module that is gone falls back to the main module; a
        # virtual device has none of its own (a stored module is ignored).
        if dev is None or dev.virtual:
            return self._radios[MAIN_RADIO]
        return self._radios.get(dev.radio) or self._radios[MAIN_RADIO]

    def _scheduler_for(self, address: int) -> RadioScheduler:
        return self._radio_of(self.devices.get(address)).scheduler

    def _submit(self, cmd: Command, radio: str | None = None) -> None:
        """Queue on the module of the command's device, or on the given module (for a
        telegram to nobody in particular, 000000); a module that is gone falls back to
        the main module, as in _radio_of. A command to a virtual device is never sent: the
        last line of defence, every caller should have refused it before."""
        if self.virtual.is_virtual(cmd.dst):
            _LOGGER.error("MAX! command %s to virtual device %06X dropped, not sent", cmd.key, cmd.dst)
            cmd.outcome = Outcome.ERROR
            if cmd.on_done is not None:
                asyncio.get_running_loop().call_soon(cmd.on_done, False)
            return
        if radio is None:
            self._scheduler_for(cmd.dst).submit(cmd)
        else:
            (self._radios.get(radio) or self._radios[MAIN_RADIO]).scheduler.submit(cmd)

    def _cancel_key(self, key: str) -> None:
        for radio in self._radios.values():
            radio.scheduler.cancel_key(key)

    def set_radio(self, address: int, radio_id: str) -> None:
        """Send to this device through another module from now on. Nothing goes on air:
        all modules share the central address, the device does not notice."""
        dev = self.devices[address]
        _no_radio(dev)
        if radio_id not in self._radios:
            raise FrameError(f"unknown radio module {radio_id!r}")
        if any(
            wall.virtual and wall.device_type is DeviceType.WALL_THERMOSTAT and dev.serial in wall.links
            for wall in self.devices.values()
        ):
            self._check_wall_module(dev, radio_id)
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

    def radio_is_network(self, radio_id: str) -> bool:
        """The module is reached over the network (its lines arrive late)."""
        radio = self._radios.get(radio_id)
        return radio is not None and radio.network

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

    def airtime_state(self) -> dict[str, list[list[float]]]:
        """Per module the transmissions of the last hour as [wall-clock time, airtime]:
        stored, so that a restart does not start the hour's budget at zero."""
        now = time.time()
        return {
            radio.id: [[round(now - age, 1), round(cost, 3)] for age, cost in radio.scheduler.airtime_log()]
            for radio in self._radios.values()
        }

    def restore_airtime(self, state: Mapping[str, Any]) -> None:
        """Take over what airtime_state stored before a restart (modules gone since and
        unreadable entries are left out)."""
        now = time.time()
        for radio in self._radios.values():
            entries = state.get(radio.id)
            if not isinstance(entries, list):
                continue
            usable = [
                # Stored rounded: an entry of a moment ago may seem to lie ahead.
                (max(0.0, now - float(entry[0])), float(entry[1])) for entry in entries
                if isinstance(entry, list | tuple) and len(entry) == 2
                and all(isinstance(value, int | float) and not isinstance(value, bool) for value in entry)
                and now - entry[0] > -RESTORE_AHEAD_S  # further ahead: the clock was set back
            ]
            radio.scheduler.restore_airtime(usable)

    async def start(self) -> None:
        for radio in self._radios.values():
            await radio.transport.start()
            radio.task = asyncio.create_task(radio.scheduler.run())
        self._forget_unknown_partners()
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
        self.virtual.resume_removals()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while True:
            await asyncio.sleep(self._poll_tick)
            try:
                self._poll_check()
            except Exception:  # noqa: BLE001 - keep polling
                _LOGGER.exception("polling the measured temperature failed")
            try:
                self.virtual.tick()  # room temperature of virtual wall thermostats
            except Exception:  # noqa: BLE001 - keep polling
                _LOGGER.exception("room temperature of virtual wall thermostats failed")

    async def stop(self) -> None:
        self.virtual.stop()
        if self._poll_task is not None:
            self._poll_task.cancel()
            self._poll_task = None
        for handle in self._flush_handles.values():
            handle.cancel()
        self._flush_handles.clear()
        for future in self._resets.values():
            if not future.done():
                future.set_result(False)
        # Queued follow-ups first: they would start once their running write ends.
        followups = list(self._profile_followups.values())
        self._profile_followups.clear()
        for follow in followups:
            if follow.task is not None:
                follow.task.cancel()
                with contextlib.suppress(asyncio.CancelledError, FrameError):
                    await follow.task
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
        """Queue a set command; mode TEMPORARY needs `until` (naive local, on :00/:30).

        At a virtual wall thermostat, or a thermostat linked with one, it is a change of
        the room: the wall thermostat takes it and each of its thermostats gets it."""
        dev = self.devices[address]
        # Validate first: a command the builder rejects must not leave pending state behind.
        build_set_temperature(0, self.address, dev.address, dev.group, temperature, mode, until)
        if until is not None and until <= self._local_now():
            raise FrameError(f"end time {until.isoformat()} is not in the future")
        if temperature is not None:
            # Pending must hold exactly what goes on air, or it never clears.
            temperature = normalize_temperature(temperature)
        wall = dev if dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT else self.virtual.wall_of(dev)
        if wall is not None and mode is Mode.BOOST and wall is not dev:
            # A boost at one thermostat stays with it, as at its button: addressed, without
            # the room's group id (with it every thermostat of the room would boost).
            self._send_setpoint(dev, temperature, mode, until, group=0)
            return
        if wall is not None and mode is Mode.AUTO and not self.virtual.program_known(wall.address):
            # Every room temperature telegram sets the thermostats' target: automatic
            # mode needs the program's target at any time.
            raise FrameError(
                f"{wall.name or wall.serial}: no complete week program known", key="virtual_no_program"
            )
        if wall is not None:
            self.virtual.set_setpoint(wall, temperature, mode, until)
            return
        self._send_setpoint(dev, temperature, mode, until)

    def _send_setpoint(
        self, dev: MaxDevice, temperature: float | None, mode: Mode, until: datetime | None = None,
        group: int | None = None,
    ) -> None:
        self._pokes.pop(dev.address, None)  # the user's command wins over a running poke
        dev.ha_override_target = dev.ha_override_at = None  # a new command replaces it
        dev.set_pending(temperature, mode, until, queued=self._local_now())
        self._notify(dev)
        self._submit_set(dev, temperature, mode, until, group)

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
                # Its measured value is the virtual wall thermostat's own, echoed.
                or self.virtual.wall_of(dev) is not None
                # A setpoint from Home Assistant holds in automatic mode: a poke would
                # only put it at risk.
                or self._override_active(dev)
            ):
                continue
            self._poke(dev, now)

    def _poke(self, dev: MaxDevice, now: float) -> None:
        target = dev.target
        assert target is not None
        poke_target = target + 0.5 if target + 0.5 <= MAX_TEMPERATURE else target - 0.5
        self._pokes[dev.address] = {
            "target": target, "mode": dev.mode, "deadline": now + POKE_TIMEOUT_S, **self._auto_override(dev, target),
        }
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

    def _auto_override(self, dev: MaxDevice, target: float) -> dict[str, Any]:
        """Whether a device in automatic mode holds a setpoint changed meanwhile (from Home
        Assistant or at the handwheel; it differs from the stored week program) and until
        when: the poke has to give that back, not the program's value. An open window's
        temperature is no setpoint; without a stored program nothing is known. A target
        reported before a switch point that passed since is the old period's value."""
        if dev.mode is not Mode.AUTO or target == dev.window_open_temperature or dev.state_at is None:
            return {}
        week = self._program_of(dev)
        now = self._local_now()
        program = program_target(week, now)
        if program is None or program == target:
            return {}
        since_report = next_switch(week, dev.state_at)
        if since_report is not None and since_report <= now:
            return {}
        return {"override": True, "override_until": next_switch(week, now)}

    def _program_of(self, dev: MaxDevice) -> dict[str, list[dict[str, Any]]]:
        """The week program a device follows: in a virtual wall thermostat's room the
        room's (the wall thermostat's), otherwise its own."""
        wall = self.virtual.wall_of(dev)
        return (wall if wall is not None else dev).week_profile

    def _override_active(self, dev: MaxDevice) -> bool:
        """Whether an acknowledged setpoint in automatic mode from Home Assistant still
        holds: the device reports AUTO with it, (program known) the next switch point has
        not come, and at most HA_OVERRIDE_PAUSE_MAX_S have passed. Forgotten otherwise."""
        target, since = dev.ha_override_target, dev.ha_override_at
        if target is None:
            return False
        now = self._local_now()
        if (
            since is not None
            and dev.mode is Mode.AUTO
            and dev.target == target
            and (now - since).total_seconds() < HA_OVERRIDE_PAUSE_MAX_S
        ):
            week = self._program_of(dev)
            switch = next_switch(week, since) if program_target(week, since) is not None else None
            if switch is None or now < switch:
                return True
        dev.ha_override_target = dev.ha_override_at = None
        return False

    def _finish_poke(self, dev: MaxDevice) -> None:
        poke = self._pokes.pop(dev.address, None)
        if poke is None:
            return
        dev.target, dev.mode = poke["target"], poke["mode"]
        if poke["mode"] is Mode.AUTO:
            # Back to automatic mode; a setpoint changed meanwhile goes back with it (it
            # holds until the next switch point), unless that switch point passed meanwhile.
            ends = poke.get("override_until")
            keep = poke.get("override", False) and (ends is None or self._local_now() < ends)
            temperature = poke["target"] if keep else None
            dev.set_pending(temperature, Mode.AUTO, None, queued=self._local_now())
            self._submit_set(dev, temperature, Mode.AUTO, group=0, from_ha=False)
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
        if dev.virtual:
            self._commit_virtual_config(dev, kind)
        else:
            self._notify(dev)
            self._submit_config(dev, kind, dict(dev.pending_config[kind]), dev.assumed_factory(kind, (key,)))
        self._share_with_room(dev, (key,))

    def _commit_virtual_config(self, dev: MaxDevice, kind: str) -> None:
        """A virtual device holds its settings itself: staged is taken, nothing on air."""
        dev.commit_config(kind, dict(dev.pending_config[kind]))
        self._notify(dev)

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
                if mate.virtual:
                    self._commit_virtual_config(mate, kind)
                    continue
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

    async def set_week_profile(
        self, address: int, days: Mapping[int, Sequence[ProfilePoint]], *, exclude: Iterable[int] = (),
        force: bool = False,
    ) -> set[int]:
        """Write whole days of the week profile (0 = Saturday ... 6 = Friday) to a
        thermostat: one telegram per part, acknowledged one after the other. The stored
        profile follows each acknowledged day; `week_profile_writing` lists the days still
        to come. There is no deadline: with an empty airtime budget a week takes a long
        time. The write belongs to the hub and goes on when the caller is cancelled.
        Raises FrameError (German) when the device refuses or stays silent (the remaining
        days are then not sent, `week_profile_error` keeps the reason) or the hub stops.

        The room's other thermostats get the days too; one still busy with other days
        writes these after its running write. A virtual wall thermostat holds the days at
        once and returns when its room mates are through; a mate's failure stays at the
        mate (`week_profile_error`), it does not fail the call. Room mates in `exclude` are
        left as they are (a copy within a room does not write its source again).

        A day a device holds already (its acknowledged copy is the same, and no failed
        write left it in doubt) is not sent to it again, unless `force`: a week costs a
        telegram per day and device.

        Returns the addresses the call reached: the device, and the room mates it wrote,
        joined or queued. Joining a running write of the same days reaches the device only
        (that write's own call took care of the room)."""
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
        if (
            (job is not None and not self._joins(address, encoded, force))
            or address in self._profile_followups
        ):
            raise FrameError(f"{name}: a week program is being written", key="week_profile_busy", name=name)
        started = job is None
        if dev.virtual:
            self._store_week_profile(dev, encoded, days)
        elif job is None:
            todo = self._days_to_write(dev, encoded, days, force)
            if todo:
                job = self._start_profile_job(dev, todo, days, plan=encoded)
            else:
                _LOGGER.info("MAX! %s (%s): week profile unchanged, nothing sent", name, dev.serial)
        mate_writes: list[asyncio.Task[None]] = []
        reached = {address}
        if started:
            # The room shares its program: the wall thermostat and its radiators switch
            # each by their own copy. Mates are written alongside; a mate that is busy
            # with other days writes these after them.
            skip = set(exclude)
            for mate in self.room_of(dev):
                if mate.address in skip:
                    continue
                reached.add(mate.address)
                if mate.virtual:
                    self._store_week_profile(mate, encoded, days)
                    continue
                running = self._profile_jobs.get(mate.address)
                queued = self._profile_followups.get(mate.address)
                if running is None and queued is None:
                    todo = self._days_to_write(mate, encoded, days, force)
                    if not todo:
                        continue  # it holds these days already
                    _LOGGER.info(
                        "MAX! %s (%s): week profile follows %s (same room)", mate.name or mate.serial,
                        mate.serial, name,
                    )
                    mate_job = self._start_profile_job(mate, todo, days, plan=encoded)
                    # Nobody but a virtual wall thermostat waits for it: it reports its failure itself.
                    mate_job.add_done_callback(lambda done: done.cancelled() or done.exception())
                    mate_writes.append(mate_job)
                elif running is not None and queued is None and self._joins(mate.address, encoded, force):
                    mate_writes.append(running)  # the same days are being written already
                else:
                    _LOGGER.info(
                        "MAX! %s (%s): week profile follows %s after the running week program",
                        mate.name or mate.serial, mate.serial, name,
                    )
                    mate_writes.append(self._queue_week_profile(mate, encoded, days))
        if dev.virtual:
            # No radio of its own: the call ends when its room has the days, so calls one
            # after the other follow one another on the radiators too.
            if mate_writes:
                await asyncio.wait(mate_writes)
            return reached
        # Else: the same days are being written already (as a room mate): wait for that.
        if job is None:
            return reached
        try:
            await asyncio.shield(job)
            return reached
        except asyncio.CancelledError:
            if job.cancelled():
                raise FrameError(
                    f"{name}: week program aborted, the radio module was stopped", key="week_profile_aborted", name=name
                ) from None
            # Nobody may be left to fetch the outcome; the job reports failures itself.
            job.add_done_callback(lambda done: done.cancelled() or done.exception())
            raise

    def _joins(self, address: int, encoded: dict[int, list[bytes]], force: bool) -> bool:
        """Whether a call for these days is served by the device's running write: the same
        plan, and with `force` only if that write leaves no day out."""
        return self._profile_plans.get(address) == encoded and (not force or address in self._profile_full)

    @staticmethod
    def _days_to_write(
        dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]], force: bool
    ) -> dict[int, list[bytes]]:
        """The days the device does not hold yet: its stored copy is what it acknowledged.
        A day whose telegrams went out without its acknowledgement (a failed or aborted
        write, also before a restart) is in doubt and always goes out, as is one a failed
        write left open."""
        if force:
            return encoded
        doubt = set(dev.week_profile_doubt)
        if dev.week_profile_error is not None:
            doubt |= set(dev.week_profile_error["missing"])
        return {
            day: parts for day, parts in encoded.items()
            if WEEKDAYS[day] in doubt or dev.week_profile.get(WEEKDAYS[day]) != _profile_day(days[day])
        }

    async def wait_week_profile(self, address: int) -> None:
        """Return once the device has neither a running week program write nor one queued
        after it (success or failure alike: `week_profile_error` tells)."""
        while True:
            follow = self._profile_followups.get(address)
            pending = [
                task for task in (self._profile_jobs.get(address), follow.task if follow is not None else None)
                if task is not None
            ]
            if not pending:
                return
            await asyncio.wait(pending)

    def _store_week_profile(
        self, dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]]
    ) -> None:
        """Nothing to write: a virtual wall thermostat holds the program itself."""
        for day in sorted(encoded):
            dev.week_profile[WEEKDAYS[day]] = _profile_day(days[day])
        if dev.device_type is DeviceType.WALL_THERMOSTAT:
            self.virtual.program_written(dev)
        self._notify(dev)

    def _start_profile_job(
        self,
        dev: MaxDevice,
        encoded: dict[int, list[bytes]],
        days: Mapping[int, Sequence[ProfilePoint]],
        keep_error: bool = False,
        plan: dict[int, list[bytes]] | None = None,
    ) -> asyncio.Task[None]:
        """Write `encoded`; `plan` is what was asked for (more when days were left out as
        unchanged): the same call again joins this write."""
        if not keep_error:
            dev.week_profile_error = None
        dev.week_profile_writing = [WEEKDAYS[day] for day in sorted(encoded)]
        self._notify(dev)
        job = asyncio.create_task(self._write_week_profile(dev, encoded, days))
        self._profile_jobs[dev.address] = job
        self._profile_plans[dev.address] = encoded if plan is None else plan
        if plan is None or plan == encoded:
            self._profile_full.add(dev.address)
        else:
            self._profile_full.discard(dev.address)
        return job

    def _queue_week_profile(
        self, dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]]
    ) -> asyncio.Task[None]:
        """Days for a room mate busy with others: written after its running write,
        merged per weekday with what is queued already. Returns the follow-up's task."""
        follow = self._profile_followups.get(dev.address)
        if follow is None:
            follow = self._profile_followups[dev.address] = _ProfileFollowUp()
            follow.task = asyncio.create_task(
                self._write_week_profile_after(dev, follow, self._profile_jobs.get(dev.address))
            )
            follow.task.add_done_callback(lambda done: done.cancelled() or done.exception())
        follow.encoded.update(encoded)
        follow.days.update(days)
        waiting = {WEEKDAYS.index(day) for day in dev.week_profile_writing} | set(follow.encoded)
        dev.week_profile_writing = [WEEKDAYS[day] for day in sorted(waiting)]
        self._notify(dev)
        assert follow.task is not None
        return follow.task

    async def _write_week_profile_after(
        self, dev: MaxDevice, follow: _ProfileFollowUp, running: asyncio.Task[None] | None
    ) -> None:
        if running is not None:
            await asyncio.wait({running})  # its success or failure: the follow-up goes on
        if self._profile_followups.get(dev.address) is follow:
            del self._profile_followups[dev.address]
        # A failure of the running write stays shown until a write brings its days.
        await self._start_profile_job(dev, follow.encoded, follow.days, keep_error=True)

    async def _write_week_profile(
        self, dev: MaxDevice, encoded: dict[int, list[bytes]], days: Mapping[int, Sequence[ProfilePoint]]
    ) -> None:
        address = dev.address
        name = dev.name or dev.serial
        left = sorted(encoded)  # days of this write not yet acknowledged
        total = sum(len(parts) for parts in encoded.values())
        series = _Series(
            left=total,
            enabled=self._wake_series
            and total >= WAKE_MIN_TELEGRAMS
            and self._series_failed.get(address, 0) < WAKE_GIVE_UP
            and address not in self._silent,
        )
        try:
            for day in sorted(encoded):
                # From its first telegram until its acknowledgement nobody knows what the
                # device holds for this day.
                fresh_doubt = WEEKDAYS[day] not in dev.week_profile_doubt
                if fresh_doubt:
                    dev.week_profile_doubt.append(WEEKDAYS[day])
                    self._notify(dev)
                for part, words in enumerate(encoded[day]):
                    outcome = await self._series_send(
                        dev, series,
                        lambda d=day, p=part, w=words, **limits: Command(
                            dst=address,
                            build=lambda c: build_config_week_profile(c, self.address, address, day=d, part=p, words=w),
                            key=f"wp:{address}:{d}:{p}",
                            deaf_probe=True,
                            **limits,
                        ),
                    )
                    if outcome is Outcome.NAK and part == 0 and fresh_doubt:
                        # Refused at its first telegram: the device keeps the day it had.
                        dev.week_profile_doubt = [d for d in dev.week_profile_doubt if d != WEEKDAYS[day]]
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
                dev.week_profile[WEEKDAYS[day]] = _profile_day(days[day])
                dev.week_profile_doubt = [d for d in dev.week_profile_doubt if d != WEEKDAYS[day]]
                left.remove(day)
                follow = self._profile_followups.get(address)
                if follow is None or day not in follow.encoded:  # else it comes again
                    dev.week_profile_writing = [d for d in dev.week_profile_writing if d != WEEKDAYS[day]]
                error = dev.week_profile_error
                if error is not None and WEEKDAYS[day] in error["missing"]:
                    # A follow-up brought a day an earlier write left out.
                    missing = [d for d in error["missing"] if d != WEEKDAYS[day]]
                    dev.week_profile_error = {**error, "missing": missing} if missing else None
                _LOGGER.info("MAX! %s (%s): week profile %s acknowledged", name, dev.serial, WEEKDAYS[day])
                self._notify(dev)
        except FrameError as err:
            # For the panel: the reason as translation key plus the days not written.
            # A follow-up after a failed write keeps that write's missing days too (a
            # fresh start has cleared the error).
            earlier = dev.week_profile_error["missing"] if dev.week_profile_error is not None else []
            missing = [
                WEEKDAYS[day] for day in sorted({WEEKDAYS.index(d) for d in earlier} | set(left))
            ]
            dev.week_profile_error = {
                "message": str(err),
                "key": err.key,
                "placeholders": dict(err.placeholders),
                "missing": missing,
            }
            _LOGGER.warning("MAX! %s (%s): %s; not written: %s", name, dev.serial, err, ", ".join(missing))
            raise
        finally:
            self._series_over(dev, series, total)
            self._profile_jobs.pop(address, None)
            self._profile_plans.pop(address, None)
            self._profile_full.discard(address)
            follow = self._profile_followups.get(address)
            # What is queued is still to come.
            writing = [WEEKDAYS[day] for day in sorted(follow.encoded)] if follow is not None else []
            if dev.week_profile_writing != writing:
                dev.week_profile_writing = writing
                self._notify(dev)

    async def _series_send(self, dev: MaxDevice, series: _Series, make: Callable[..., Command]) -> Outcome:
        """One telegram of a series to a thermostat. While the series is worth it, a WakeUp
        first (the device then listens for a while), and the telegram without the 1 s
        wake-up preamble: one attempt, answered at once or not at all. Unanswered, it goes
        out again the usual way, and the rest of the series does too."""
        address = dev.address
        scheduler = self._scheduler_for(address)
        left, series.left = series.left, series.left - 1
        if series.enabled and series.fast == series.fast_at_wake:
            # The last WakeUp brought no telegram out in time (a slow queue, waiting for
            # airtime): another one would only add its preamble.
            series.enabled = False
        if series.enabled and scheduler.now() >= series.awake_until and left >= WAKE_MIN_TELEGRAMS:
            series.fast_at_wake = series.fast
            woke = await self._await_command(
                Command(
                    dst=address,
                    build=lambda c: build_wake_up(c, self.address, address),
                    key=f"wake:{address}:series",  # not wake_up()'s: that one would replace it
                    retries=1,
                )
            )
            if woke is Outcome.ACKED:
                series.awake_until = scheduler.now() + WAKE_AWAKE_S
                await asyncio.sleep(self._wake_settle)
            else:
                # The telegram itself tells whether the device is there. Unanswered on
                # air, the WakeUp counts against the device (not a module that was away).
                series.enabled = False
                series.failed = woke is Outcome.NO_ACK
        if series.enabled and scheduler.now() < series.awake_until:
            attempt = make(fast=True, retries=0, ack_timeout=WAKE_FAST_ACK_TIMEOUT_S, deadline=series.awake_until)
            # Unanswered, it says the device slept, not that the module is deaf.
            attempt.deaf_probe = False
            outcome = await self._await_command(attempt)
            if outcome in (Outcome.ACKED, Outcome.NAK):
                series.fast += 1
                return outcome
            # Expired: it waited behind others (or for airtime) until the device slept
            # again. No further WakeUp then, each would only add its preamble.
            # Only an attempt on air without an answer counts against the device, not a
            # module that did not take the line.
            series.enabled = False
            series.failed = outcome is Outcome.NO_ACK
        return await self._await_command(make())

    def _series_over(self, dev: MaxDevice, series: _Series, total: int) -> None:
        name = dev.name or dev.serial
        if series.failed:
            failed = self._series_failed[dev.address] = self._series_failed.get(dev.address, 0) + 1
            _LOGGER.info(
                "MAX! %s (%s): the WakeUp or a telegram without wake-up preamble stayed unanswered "
                "(%d of %d went without preamble)%s",
                name, dev.serial, series.fast, total,
                ", it gets none any more" if failed >= WAKE_GIVE_UP else "",
            )
        elif series.fast:
            self._series_failed.pop(dev.address, None)
            _LOGGER.info(
                "MAX! %s (%s): %d of %d telegrams went without wake-up preamble", name, dev.serial, series.fast, total
            )

    def set_config_set(self, address: int, kind: str, values: dict[str, Any]) -> list[str]:
        """Change several values of one set: one telegram with the whole set. Returns
        the keys sent along as assumed factory settings."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        assumed = dev.stage_config_set(kind, values)
        if dev.virtual:
            self._commit_virtual_config(dev, kind)
            assumed = []
        else:
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
        dev_a, dev_b = self.devices.get(a), self.devices.get(b)
        if dev_a is not None and dev_b is not None:
            for wall, other in ((dev_a, dev_b), (dev_b, dev_a)):
                if wall.virtual and wall.device_type is DeviceType.WALL_THERMOSTAT:
                    self._check_wall_module(other, self._radio_of(other).id)
        self._change_link(a, b, LINK_ADD)

    def _check_wall_module(self, dev: MaxDevice, radio_id: str) -> None:
        """A thermostat of a virtual wall thermostat stays off network modules: it waits
        for the wall thermostat's acknowledgement a few tens of milliseconds, a network
        module's line arrives 80-160 ms late."""
        if dev.is_heating_thermostat and self.radio_is_network(radio_id):
            raise FrameError(
                f"{dev.name or dev.serial} is on network module {radio_id!r}: no virtual wall thermostat there",
                key="virtual_network_radio",
            )

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
        entry = target.link_op(partner.serial)
        if entry is not None:
            entry["force"] = True  # a leftover: its acknowledgement changes nothing else
        self._notify(target)
        self._notify(partner)

    def cancel_link(self, address: int, partner_serial: str | None = None) -> list[str]:
        """Drop open link operations of a device without sending anything.

        With `partner_serial` only the operation for that partner, in both directions
        (the panel shows an operation stored on the partner at either device); without
        it every open operation of the device. The partner need not be known any more
        (deleted devices). Returns the partner serials whose operations were dropped."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}", key="device_unknown")
        partners = [partner_serial] if partner_serial else [op["partner"] for op in dev.pending_links]
        by_serial = {d.serial: d for d in self.devices.values()}
        dropped: list[str] = []
        for serial in partners:
            entry = dev.link_op(serial)
            if entry is not None:
                self._cancel_key(self._link_key(dev, entry["address"]))
                dev.drop_link_op(serial)
                dropped.append(serial)
            other = by_serial.get(serial)
            back = other.link_op(dev.serial) if other is not None else None
            if other is not None and back is not None:
                self._cancel_key(self._link_key(other, dev.address))
                other.drop_link_op(dev.serial)
                if serial not in dropped:
                    dropped.append(serial)
                self._notify(other)
        if partner_serial and not dropped:
            raise FrameError(
                f"no open link operation with {partner_serial}", key="link_op_unknown", serial=partner_serial
            )
        for serial in dropped:
            _LOGGER.info(
                "MAX! %s (%s): open link operation with %s cancelled, nothing sent",
                dev.name or dev.serial, dev.serial, serial,
            )
        self._notify(dev)
        # A virtual device being removed may be carried by nobody any more.
        self.virtual.check_removals()
        return dropped

    def _forget_unknown_partners(self) -> None:
        """What can never be settled with a device the integration no longer has (deleted on
        the device page): a link nothing is outstanding for (only the serial is known, there
        is no address to send a removal to), a removal the device refused, an addition.
        A removal still waiting stays: it carries the address and can complete, e.g. at a
        window contact after its partner was reset and then deleted."""
        known = {d.serial for d in self.devices.values()}
        for dev in self.devices.values():
            gone = {*dev.links, *(op["partner"] for op in dev.pending_links)} - known
            for serial in sorted(gone):
                op = dev.link_op(serial)
                if op is not None and op["op"] == LINK_REMOVE and op["state"] != LINK_REJECTED:
                    continue
                dev.forget_partner(serial)
                _LOGGER.info(
                    "MAX! %s (%s): partner %s is no longer known, link and open operation dropped",
                    dev.name or dev.serial, dev.serial, serial,
                )
        self.virtual.check_removals()

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
        """Thermostats get the operation now; sleepers after their next telegram; a virtual
        device is the hub itself and takes it at once, nothing goes on air for it."""
        if target.virtual:
            target.drop_link_op(serial)
            target.commit_link(serial, op)
            _LOGGER.info(
                "MAX! %s (%s): link %s %s taken at once (virtual)",
                target.name or target.serial, target.serial, op, serial,
            )
            self.virtual.link_committed(target, serial, op)
        elif target.is_sleeper:
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
        _no_radio(dev)
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
        if dev.virtual:
            dev.group, dev.pending_group, dev.group_failed = group, None, False
            self._notify(dev)
            return
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
            # Failed = given up after SLEEPER_LINK_ROUNDS; only a new request resends it.
            if entry["state"] == LINK_WAITING:
                self._submit_link(dev, entry, awake=True, fast=True)

    def _link_proven(self, dev: MaxDevice, partner_address: int) -> None:
        """The sleeper reports its state to this device, which only one carrying the link
        does: an addition still open counts as acknowledged. Its acknowledgement can get
        lost while the device took the link; the operation then waited or was given up for
        good although everything worked (#6, 17.11.2026)."""
        partner = self.devices.get(partner_address)
        if partner is None:
            return
        entry = dev.link_op(partner.serial)
        if entry is None or entry["op"] != LINK_ADD:
            return
        dev.commit_link(partner.serial, LINK_ADD)
        key = self._link_key(dev, partner_address)
        for radio in self._radios.values():
            radio.scheduler.abandon_key(key)
        self._link_missed_at.pop((dev.address, partner.serial), None)
        _LOGGER.info(
            "MAX! %s (%s): link add %s proven by its telegram to that device",
            dev.name or dev.serial, dev.serial, partner.serial,
        )
        self._notify_pair(dev, partner.serial)

    def _send_links_after_pong(self, dev: MaxDevice) -> None:
        """A device that just paired with us (new batteries, teach-in button) stays awake
        for a few seconds, waiting for its configuration. For a sleeper that is the one
        sure chance: a window contact without partners otherwise only ever talks to the
        central and goes back to sleep on its acknowledgement (#6)."""
        if not dev.is_sleeper:
            return
        # One link per press: after taking one the contact stopped listening and the next
        # went out nine times into the void (#6, 15.11.2026). The next press brings the
        # next one, or, now that it has a partner, the next window event.
        entry = next((e for e in dev.pending_links if e["state"] in (LINK_WAITING, LINK_FAILED)), None)
        if entry is not None:
            self._submit_link(dev, entry, awake=True, fast=True, window=PAIRED_LISTEN_S)

    def _submit_link(
        self,
        dev: MaxDevice,
        entry: dict[str, Any],
        *,
        awake: bool = False,
        fast: bool = False,
        window: float | None = None,
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
        if fast and window is not None:
            # Listening for a while (just paired): quick retries until it stops. One
            # attempt is not enough, a contact missed the first one (15.11.2026), and
            # the usual 3 s ack timeout would leave room for just one more.
            cmd.deadline = self._scheduler_for(dev.address).now() + window
            cmd.ack_timeout = self._fast_ack_timeout
            cmd.retries = int(window / self._fast_ack_timeout)
        elif fast:
            # Only worth sending while the device still listens: one attempt, short wait.
            cmd.deadline = self._scheduler_for(dev.address).now() + self._fast_deadline
            cmd.retries = 0
            cmd.ack_timeout = self._fast_ack_timeout
        cmd.on_done = lambda _ok: self._link_done(dev, partner, op, cmd, partner_address, partner_type)
        self._submit(cmd)

    def _link_done(
        self, dev: MaxDevice, partner: str, op: str, cmd: Command,
        partner_address: int | None = None, partner_type: DeviceType | None = None,
    ) -> None:
        try:
            if (
                cmd.outcome is Outcome.ACKED
                and op == LINK_ADD
                and partner_address is not None
                and partner_type is not None
                and partner in self.virtual.removed_serials
                and partner not in {d.serial for d in self.devices.values()}
            ):
                self._ghost_link(dev, partner, partner_address, partner_type)
                return
            self._settle_link(dev, partner, op, cmd)
        finally:
            # A virtual device being removed may be carried by nobody any more.
            self.virtual.check_removals()

    def _ghost_link(self, dev: MaxDevice, partner: str, address: int, device_type: DeviceType) -> None:
        """The device took a link with a partner that is gone meanwhile (a virtual device
        removed by force while the addition was on air): it really carries it, so it gets
        the removal; nothing is committed."""
        _LOGGER.warning(
            "MAX! %s (%s): took link with %s, which is gone meanwhile: removing it again",
            dev.name or dev.serial, dev.serial, partner,
        )
        self._queue_link(dev, partner, address, device_type, LINK_REMOVE)
        self._notify(dev)

    def _settle_link(self, dev: MaxDevice, partner: str, op: str, cmd: Command) -> None:
        name = dev.name or dev.serial
        if cmd.outcome is Outcome.ACKED:
            forced = bool((dev.link_op(partner) or {}).get("force"))
            dev.commit_link(partner, op)
            _LOGGER.info("MAX! %s (%s): link %s %s acknowledged", name, dev.serial, op, partner)
            self.virtual.link_committed(dev, partner, op, forced=forced)
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
            # Asleep again (or never reached): the next telegram is the next chance – up to
            # SLEEPER_LINK_ROUNDS rounds. A round is one burst of the device (one window
            # event): its retries and its telegrams to partners give several attempts within
            # a second, which counted singly ended two window events early (15.11.2026).
            # "Abandoned" (it transmitted instead of listening) is no round at all.
            now = self._scheduler_for(dev.address).now()
            key = (dev.address, partner)
            last = self._link_missed_at.get(key)
            if cmd.outcome is not Outcome.ABANDONED and (last is None or now - last > self._sleeper_round_gap):
                self._link_missed_at[key] = now
                current["misses"] = current.get("misses", 0) + 1
            if current.get("misses", 0) >= SLEEPER_LINK_ROUNDS:
                dev.set_link_state(partner, op, LINK_FAILED)
                _LOGGER.warning(
                    "MAX! %s (%s): link %s %s not acknowledged in %d rounds of the device, "
                    "given up (send it again from the eQ-3 MAX! page)",
                    name, dev.serial, op, partner, current["misses"],
                )
            else:
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
        _no_radio(dev)
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
        self.pairing_foreign = {}

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

    def _stale_override(self, dev: MaxDevice) -> bool:
        """A pending setpoint in automatic mode that is about to go out again holds only
        until the program's next switch point: once that passed since it was queued (or,
        without a known program, after AUTO_OVERRIDE_STALE_S) it would bring back a value
        the device has left behind. Without a queue time (older store) it counts as stale."""
        if dev.pending_mode is not Mode.AUTO or dev.pending_target is None:
            return False
        return self._override_stale(dev, dev.pending_queued)

    def _override_stale(self, dev: MaxDevice, queued: datetime | None) -> bool:
        if queued is None:
            return True
        return override_over(self._program_of(dev), queued, self._local_now(), AUTO_OVERRIDE_STALE_S)

    def _submit_pending(self, dev: MaxDevice) -> None:
        if self._expired(dev.pending_mode, dev.pending_until):
            self._drop_expired(dev)
            return
        if self._stale_override(dev):
            # Never sent silently away: the device may sit on another value (a poke's
            # manual one, or manual when the program was asked for). The program's.
            _LOGGER.info(
                "MAX! %s (%s): setpoint %.1f in automatic mode not acknowledged before its switch point "
                "(or within %d minutes): override replaced by plain automatic mode",
                dev.name or dev.serial, dev.serial, dev.pending_target, AUTO_OVERRIDE_STALE_S // 60,
            )
            dev.set_pending(None, Mode.AUTO, None, queued=self._local_now())
            self._notify(dev)
        # In a virtual wall thermostat's room the setpoint goes to this device only (as
        # the room sent it), not to whatever group id it still carries.
        group = 0 if self.virtual.wall_of(dev) is not None else None
        self._submit_set(dev, dev.pending_target, dev.pending_mode, dev.pending_until, group)

    def _submit_set(
        self, dev: MaxDevice, temperature: float | None, mode: Mode | None, until: datetime | None = None,
        group: int | None = None, *, from_ha: bool = True,
    ) -> None:
        if mode is None:
            return
        group = dev.group if group is None else group
        is_stale: Callable[[], bool] | None = None
        if mode is Mode.TEMPORARY:
            is_stale = lambda: self._expired(mode, until)  # noqa: E731
        elif mode is Mode.AUTO and temperature is not None:
            # Waiting in the queue (or for airtime) past the switch point: no override any more.
            queued = (
                dev.pending_queued
                if dev.pending_mode is mode and dev.pending_target == temperature
                else self._local_now()
            )
            is_stale = lambda: self._override_stale(dev, queued)  # noqa: E731

        def build(counter: int) -> Frame:
            if self._expired(mode, until):
                raise FrameError(f"end time {until} passed")
            return build_set_temperature(counter, self.address, dev.address, group, temperature, mode, until)

        self._submit(
            Command(
                dst=dev.address,
                build=build,
                key=f"set:{dev.address}",
                on_done=lambda ok: self._command_done(dev, ok, temperature, mode, until, from_ha),
                is_stale=is_stale,
                deaf_probe=True,
            )
        )

    def _command_done(
        self, dev: MaxDevice, ok: bool, temperature: float | None, mode: Mode, until: datetime | None = None,
        from_ha: bool = True,
    ) -> None:
        current = (
            dev.has_pending
            and dev.pending_mode is mode
            and dev.pending_target == temperature
            and dev.pending_until == until
        )
        if ok and from_ha and mode is Mode.AUTO and temperature is not None and (current or not dev.has_pending):
            # A setpoint in automatic mode from Home Assistant holds: polling pauses.
            dev.ha_override_target, dev.ha_override_at = temperature, self._local_now()
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
        if current and self._stale_override(dev):
            self._submit_pending(dev)  # replaced by plain automatic mode
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
            self.virtual.reconnected()  # undelivered window states: one attempt each
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
        telegram's counter, payload 00.

        A virtual device answers every telegram to it but acknowledgements, whatever the
        module: the firmware knows only the central's address."""
        virtual = self.virtual.get(frame.dst)
        if virtual is not None:
            if frame.msg_type == MsgType.ACK or frame.src == self.address or self.virtual.is_virtual(frame.src):
                return
        else:
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
        # The answer comes from whom the telegram went to (the central or a virtual device).
        payload = b"\x00" if virtual is None else self.virtual.ack_payload(virtual, frame)
        ack = build_ack(frame.counter, frame.dst, frame.src, payload)
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

    def _is_repeated_press(self, frame: Frame) -> bool:
        """A press the button sends again because it missed our acknowledgement."""
        now = self._now()
        last = self._last_press.get(frame.src)
        if last is not None and last[0] == frame.counter and now - last[1] < BUTTON_REPEAT_WINDOW_S:
            TRACE.info(
                "button %06X repeats press %02X after %.0f s (payload %s): not passed on",
                frame.src, frame.counter, now - last[1], bytes(frame.payload).hex(),
            )
            return True
        self._last_press[frame.src] = (frame.counter, now)
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
        # Our own transmissions, heard back through another module (also as a virtual device).
        if frame.src == self.address or self.virtual.is_virtual(frame.src):
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
            if frame.dst == self.address or self.virtual.is_virtual(frame.dst):
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
            dev.apply_shutter(decode_shutter_contact_state(frame.payload), now=self._now())
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
            if not self._is_repeated_press(frame):
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
        restoring = False
        if poke is not None:
            # The poke stays invisible: keep the real target and mode.
            dev.target, dev.mode = poke["target"], poke["mode"]
            if reported:
                self._finish_poke(dev)
                restoring = True
        if not restoring:
            # Right after the poke the device still sits on the poke's value: the restore
            # just queued stays pending until it is acknowledged (or resent).
            dev.clear_pending_if_reached()
        if status and dev.is_climate:
            dev.state_at = self._local_now()
            self._override_active(dev)  # another target or mode reported: forgotten
        if status and dev.command_failed and dev.has_pending:
            dev.command_failed = False
            self._submit_pending(dev)
        if status and dev.failed_config_kinds():
            self._submit_pending_config(dev, dev.failed_config_kinds())
        if status:
            self._resubmit_failed_group(dev)
        if dev.is_sleeper:
            if kind in (MsgType.SHUTTER_CONTACT_STATE, MsgType.PUSH_BUTTON_STATE) and frame.dst != self.address:
                self._link_proven(dev, frame.dst)
            if not (kind == MsgType.ACK and frame.dst == self.address):
                # It transmits instead of listening: a fast attempt on air is moot.
                self._abandon_fast_attempts(dev)
            # A sleeper listens once its burst is over: the telegram to us, then one to
            # each partner (40-110 ms apart, trace of 09.11.2026) and their answers. Every
            # telegram from it restarts the debounce, so the flush lands after the last one;
            # a retry towards an unreachable partner is a chance of its own.
            if dev.pending_links:
                TRACE.info(
                    "sleeper %06X talked to %s (type %02X): flush of its link operations (%s) %.0f ms after its last telegram",
                    dev.address, "us" if frame.dst == self.address else f"{frame.dst:06X}", kind,
                    ", ".join(f"{op['op']} {op['partner']}: {op['state']}" for op in dev.pending_links),
                    self._sleeper_debounce * 1000,
                )
            self._schedule_flush(dev)
        elif status:
            self._resubmit_failed_links(dev)
            self.virtual.partner_heard(dev)
        partner = self.devices.get(frame.dst)
        if partner is not None and partner is not dev and partner.is_sleeper:
            # A partner's answer belongs to the sleeper's burst as well.
            self._schedule_flush(partner)
        if partner is not None and partner.virtual:
            self.virtual.on_frame(frame)
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
            dev.apply_shutter(decode_shutter_contact_state(payload), now=self._now())
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
        _no_radio(dev)
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
        if dev.virtual:
            return  # never paired: nothing on air for it
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
        if dev.is_climate and dev.has_pending and dev.pending_mode is Mode.AUTO and dev.pending_target is not None:
            # A setpoint in automatic mode holds only until a switch point: the program.
            dev.set_pending(None, Mode.AUTO, None, queued=self._local_now())
            self._submit_set(dev, None, Mode.AUTO, None)
        elif (
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
        if (
            dev.is_climate
            and dev.week_profile
            and dev.address not in self._profile_jobs
            and dev.address not in self._profile_followups
        ):
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

    def _note_foreign_pairing(self, frame: Frame, ping: PairPing, known: MaxDevice | None) -> None:
        """A new device pings its old central while pairing is open: it still belongs
        there and is never answered. Say so once instead of staying silent. With the window
        closed nothing is said: the neighbours' MAX! devices ping their own central."""
        if known is not None or self._now() >= self._pairing_until or ping.serial in self.pairing_foreign:
            return
        self.pairing_foreign[ping.serial] = {"address": frame.src, "central": frame.dst}
        _LOGGER.warning(
            "MAX! %s (%06X) wants to pair but is still paired to the central %06X (this central: %06X); "
            "reset the device to factory settings and pair it again",
            ping.serial, frame.src, frame.dst, self.address,
        )
        self._notify(None)

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
            self._note_foreign_pairing(frame, ping, known)
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
                # Back in touch: now it listens. Links first (a sleeper listens only
                # for a few seconds), then the clock, which starts from nothing.
                back = self.devices[src]
                self._send_links_after_pong(back)
                if back.device_type is not DeviceType.SHUTTER_CONTACT:
                    # A window contact has no clock and never acknowledges the time.
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
