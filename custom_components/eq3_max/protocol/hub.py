"""MaxHub: ties transport, scheduler and device model together."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from .devices import (
    KIND_TEMP,
    LINK_ADD,
    LINK_FAILED,
    LINK_PENDING,
    LINK_REJECTED,
    LINK_REMOVE,
    LINK_WAITING,
    MaxDevice,
)
from .messages import (
    DeviceType,
    Frame,
    FrameError,
    Mode,
    MsgType,
    build_add_link_partner,
    build_config_temperatures,
    build_config_valve,
    build_pair_pong,
    build_remove_link_partner,
    build_reset,
    build_set_temperature,
    build_time_information,
    decode_ack,
    decode_frame,
    decode_pair_ping,
    decode_push_button_state,
    decode_set_temperature,
    decode_shutter_contact_state,
    decode_thermostat_state,
    decode_until,
    decode_wall_thermostat_control,
    decode_wall_thermostat_state,
    link_allowed,
    normalize_temperature,
)
from .scheduler import PRIO_COMMAND, PRIO_REPLY, Command, Outcome, RadioScheduler
from .transport import CulTransport

_LOGGER = logging.getLogger(__name__)
DUPLICATE_WINDOW_S = 5.0
RAW_HISTORY_LEN = 10
RESET_SEND_WINDOW_S = 30.0
RESET_MARGIN_S = 5.0
# Sleepers: send to them only while they listen after their telegram to us.
SLEEPER_DEBOUNCE_S = 0.08
FAST_DEADLINE_S = 0.3
FAST_ACK_TIMEOUT_S = 0.5
FAST_MISSES_BEFORE_ZS = 2


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
}


@dataclass(frozen=True)
class LinkStatus:
    """Links of one device as a pair view: complete pairs and the rest with a state."""

    partners: list[str] = field(default_factory=list)  # serials, both directions acknowledged
    pending: list[tuple[str, str]] = field(default_factory=list)  # (partner serial, state)


def _devices_by_serial(devices: dict[int, MaxDevice] | Iterable[MaxDevice]) -> dict[str, MaxDevice]:
    values = devices.values() if isinstance(devices, dict) else devices
    return {d.serial: d for d in values}


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
        raise FrameError("Ger\u00e4t ist dem Funkmodul nicht bekannt")
    if dev_a is dev_b or dev_a.serial == dev_b.serial:
        raise FrameError("Ein Ger\u00e4t kann nicht mit sich selbst verkn\u00fcpft werden")
    if not link_allowed(dev_a.device_type, dev_b.device_type):
        raise FrameError(
            f"{_TYPE_NAMES[dev_a.device_type]} und {_TYPE_NAMES[dev_b.device_type]} "
            "lassen sich nicht verkn\u00fcpfen"
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
            raise FrameError(
                "Verkn\u00fcpfung ist bereits beauftragt" if op == LINK_ADD else "L\u00f6sen ist bereits beauftragt"
            )
        raise FrameError(
            "Ger\u00e4te sind bereits verkn\u00fcpft" if op == LINK_ADD else "Ger\u00e4te sind nicht verkn\u00fcpft"
        )
    return directions


class ResetResult(Enum):
    ACKED = "acked"
    UNACKED = "unacked"  # sent at least once, no ack: the device may be reset anyway
    NOT_SENT = "not_sent"


MAIN_RADIO = ""
# A telegram heard by a second module within this time is the same transmission.
CROSS_RADIO_WINDOW_S = 1.0


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
        self._recent: dict[tuple[int, int, int], float] = {}
        self.raw_history: dict[int, deque[str]] = {}
        self._on_problem = on_problem
        self._brake = brake
        self._transport_kwargs = dict(transport_kwargs or {})
        self._counter = 0
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
        self._heard: dict[tuple[int, int, int, bytes], tuple[str, float]] = {}
        self._sleeper_debounce = sleeper_debounce
        self._fast_deadline = fast_deadline
        self._fast_ack_timeout = fast_ack_timeout
        self._flush_handles: dict[int, asyncio.TimerHandle] = {}
        # Unheard fast sends per (device address, partner serial) in a row.
        self._fast_misses: dict[tuple[int, str], int] = {}

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
            on_change=lambda: self._notify(None),
            wait_ready=radio.transport.wait_connected,
            on_finished=lambda cmd: self._command_finished(cmd, radio),
            # Same clock as the transport: first send and last receive are compared.
            clock=radio.transport.clock,
            next_counter=self._next_counter,
        )
        return radio

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
        """Per module: id, target, connected, version, airtime, queue (main first)."""
        return [
            {
                "id": radio.id,
                "target": radio.port,
                "connected": radio.transport.connected,
                "version": radio.transport.version,
                "airtime": radio.scheduler.airtime_last_hour,
                "queue": radio.scheduler.queue_length,
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
            self._start_links(dev)

    async def stop(self) -> None:
        for handle in self._flush_handles.values():
            handle.cancel()
        self._flush_handles.clear()
        for future in self._resets.values():
            if not future.done():
                future.set_result(False)
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

    def set_config_set(self, address: int, kind: str, values: dict[str, Any]) -> list[str]:
        """Change several values of one set: one telegram with the whole set. Returns
        the keys sent along as assumed factory settings."""
        dev = self.devices.get(address)
        if dev is None:
            raise FrameError(f"unknown device {address:06X}")
        assumed = dev.stage_config_set(kind, values)
        self._notify(dev)
        self._submit_config(dev, kind, dict(dev.pending_config[kind]), assumed)
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
                "MAX! %s (%s): Sende angenommene Werksvorgaben mit: %s",
                dev.name or dev.serial, dev.serial, ", ".join(assumed),
            )
        if kind == KIND_TEMP:
            cfg = dev.temperature_config(values)
            builder: Callable[[int], Frame] = lambda c: build_config_temperatures(c, self.address, dev.address, cfg)
            key = f"cfg_temp:{dev.address}"
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

    def unlink(self, a: int, b: int) -> None:
        """Remove the link in both directions (RemoveLinkPartner)."""
        self._change_link(a, b, LINK_REMOVE)

    def _change_link(self, a: int, b: int, op: str) -> None:
        for target, partner in plan_link(self.devices, a, b, op):
            current = target.link_op(partner.serial)
            self._fast_misses.pop((target.address, partner.serial), None)
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
        if dev.is_sleeper:
            # Whatever was on air at shutdown waits for the device again.
            for entry in dev.pending_links:
                if entry["state"] == LINK_PENDING:
                    entry["state"] = LINK_WAITING
            return
        for entry in list(dev.pending_links):
            if entry["state"] != LINK_REJECTED:
                self._submit_link(dev, entry)

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

    def _flush_sleeper(self, dev: MaxDevice) -> None:
        """The sleeper just talked to us and listens briefly: send what waits for it.
        Fast (Zf, no preamble) first; after FAST_MISSES_BEFORE_ZS unheard fast sends of
        an operation with the preamble (Zs) like FHEM."""
        for entry in list(dev.pending_links):
            if entry["state"] in (LINK_WAITING, LINK_FAILED):
                misses = self._fast_misses.get((dev.address, entry["partner"]), 0)
                self._submit_link(dev, entry, awake=True, fast=misses < FAST_MISSES_BEFORE_ZS)

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
        key = (dev.address, partner)
        if cmd.outcome is Outcome.ACKED:
            dev.commit_link(partner, op)
            self._fast_misses.pop(key, None)
            _LOGGER.info("MAX! %s (%s): link %s %s acknowledged", name, dev.serial, op, partner)
            self._notify_pair(dev, partner)
            return
        current = dev.link_op(partner)
        if current is None or current["op"] != op:
            return
        if cmd.outcome is Outcome.NAK:
            # The device refused: no automatic resend, only a new request.
            dev.set_link_state(partner, op, LINK_REJECTED)
            self._fast_misses.pop(key, None)
            _LOGGER.warning("MAX! %s (%s): link %s %s rejected", name, dev.serial, op, partner)
        elif dev.is_sleeper:
            # Asleep again (or never reached): the next telegram is the next chance.
            dev.set_link_state(partner, op, LINK_WAITING)
            if cmd.fast and cmd.outcome is Outcome.NO_ACK:
                self._fast_misses[key] = self._fast_misses.get(key, 0) + 1
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
            raise FrameError("Werksreset l\u00e4uft bereits")
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
                self._fast_misses = {
                    k: v for k, v in self._fast_misses.items() if k[0] != dev.address and k[1] != dev.serial
                }
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

    def open_pairing(self, seconds: float = 60) -> None:
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
        self, dev: MaxDevice, temperature: float | None, mode: Mode | None, until: datetime | None = None
    ) -> None:
        if mode is None:
            return

        def build(counter: int) -> Frame:
            if self._expired(mode, until):
                raise FrameError(f"end time {until} passed")
            return build_set_temperature(counter, self.address, dev.address, dev.group, temperature, mode, until)

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
                    "MAX! %s: antwortet nicht, der Funk funktioniert aber - Geraet pruefen (Reichweite, Batterie, \"InS\")",
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
            _LOGGER.warning("CUL empfaengt nach dem Senden nichts mehr - Port wird neu geoeffnet (%s)", radio.port)
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
                if not dev.is_sleeper:
                    self._resubmit_failed_links(dev)
        self._notify(None)

    def _on_line(self, text: str, radio: str = MAIN_RADIO) -> None:
        try:
            frame = decode_frame(text)
        except FrameError as err:
            _LOGGER.debug("ignoring line: %s", err)
            return
        self._note_heard(frame.src, radio)
        if self._heard_elsewhere(frame, radio):
            return
        try:
            self._handle(frame, radio)
        except (FrameError, ValueError, IndexError) as err:
            _LOGGER.debug("cannot decode %s: %s", text, err)
        if frame.src in self.devices:
            history = self.raw_history.setdefault(frame.src, deque(maxlen=RAW_HISTORY_LEN))
            history.append(text)

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
        key = (frame.src, frame.counter, frame.msg_type, bytes(frame.payload))
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
        else:
            status = False
            _LOGGER.debug("unhandled message type %02X from %06X", kind, frame.src)
        dev.clear_pending_if_reached()
        if status and dev.command_failed and dev.has_pending:
            dev.command_failed = False
            self._submit_pending(dev)
        if status and dev.failed_config_kinds():
            self._submit_pending_config(dev, dev.failed_config_kinds())
        if dev.is_sleeper:
            # Only telegrams to us (status, acks) keep the sleeper listening for an
            # answer; not those to its linked thermostats.
            if frame.dst == self.address:
                self._schedule_flush(dev)
        elif status:
            self._resubmit_failed_links(dev)
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
        self._submit(
            Command(
                dst=src,
                build=lambda c: build_pair_pong(c, self.address, src),
                priority=PRIO_REPLY,
                key=f"pong:{src}",
                # Report a new device only once the pong is off the air: the caller
                # reloads the integration, which must not cut the pairing short.
                on_done=None if added is None else (lambda _ok: self._safe(self._on_device_added, added)),
            )
        )
