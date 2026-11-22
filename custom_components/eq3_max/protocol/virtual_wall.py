"""The virtual wall thermostat: it keeps its room's setpoint in step with the linked
radiator thermostats, answers them like the real one, and knows the room's windows.

Mixed into virtual.Virtuals, the one object the hub talks to."""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .devices import CONFIG_VIRTUAL_WALL_KEYS, LINK_ADD, LINK_REMOVE, SOURCE_FACTORY, WEEKDAYS, MaxDevice
from .messages import (
    MAX_TEMPERATURE,
    OFF_TEMPERATURE,
    DeviceType,
    Frame,
    FrameError,
    Mode,
    MsgType,
    build_wall_thermostat_control,
    decode_set_temperature,
    decode_until,
    encode_wall_ack,
)
from .program import next_switch, program_target
from .scheduler import PRIO_BACKGROUND, PRIO_REPLY, Command, Outcome

if TYPE_CHECKING:
    from .hub import MaxHub
    from .scheduler import RadioScheduler

_LOGGER = logging.getLogger(__name__)

# A setpoint a thermostat reported goes to the room's other thermostats this much later (s);
# the real wall thermostat waits about 24 s.
WT_FORWARD_DELAY_S = 3.0

# The room temperature (0x42) goes out every WT_INTERVAL_S (s, hub wall clock), on time by
# a timer of its own; addressed, each thermostat gets one that often. A thermostat waits
# just under 10 min for its wall thermostat, then regulates on its own sensor (measured
# 20.11.2026; a real wall thermostat sends every 3 min).
WT_INTERVAL_S = 300.0
# A telegram costs about 1.1 s of airtime, twelve an hour 13 s: two rooms fit into a
# module's 36 s an hour with room for commands, three do not. Up to WT_FULL_RATE telegrams
# per WT_INTERVAL_S and module go at that cadence; with more, every room of the module
# slows in proportion (three rooms: every 450 s), to WT_INTERVAL_MAX_S at most: a
# thermostat waits just under 10 min, the rest is margin. Beyond that the airtime no
# longer fits and telegrams are left out (reserve, LOVF) as before.
WT_FULL_RATE = 2
WT_INTERVAL_MAX_S = 480.0
# A change of the room's window state goes out at once, at most once per WT_WINDOW_GAP_S
# (s); a change within it goes when it is over.
WT_WINDOW_GAP_S = 60.0
# At most this many window telegrams sent at once per room and rolling hour (s); beyond
# it a change goes with the next regular telegram.
WT_WINDOW_HOUR_MAX = 12
WT_WINDOW_HOUR_S = 3600.0
# A fall of 8 degrees between two telegrams set off a thermostat's window detection
# (20.11.2026): per telegram the value falls by this much at most.
WT_DROP_STEP = 1.0
# A room without a telegram for this long goes ahead of the waiting commands (once).
WT_STARVED_S = 420.0
# Airtime of the hour (s) the telegram leaves to commands (only with the hub's option to
# limit the airtime to 36 s, `brake`), and how long it may wait to go out (s, scheduler
# clock) before it is dropped and built anew.
WT_RESERVE_S = 10.0
WT_EXPIRE_S = 120.0
# A telegram that did not go out for the reserve, or that the stick refused (LOVF), is
# built anew after this long (s).
WT_RESERVE_RETRY_S = 60.0
WT_LOVF_BACKOFF_S = 60.0
# After this long without a telegram (s) the drop is limited against the thermostats' own
# reading: they went back to their sensor.
WT_PAUSE_S = 600.0
# A room's timer never fires sooner than this (s): no busy loop on clock differences.
WT_TIMER_MIN_S = 0.05
# What a 0x42 can carry (degrees C); outside it the source counts as unavailable.
MEASURED_MIN, MEASURED_MAX = 0.0, 51.0
# A boost set at the wall thermostat ends with the room's boost duration, after this
# long (s) at the latest.
WT_BOOST_MAX_S = 3600.0


class WallThermostats:
    """Wall thermostat part of Virtuals (which provides _hub and get)."""

    _hub: MaxHub

    if TYPE_CHECKING:

        def get(self, address: int) -> MaxDevice | None: ...

        def link_committed(self, dev: MaxDevice, partner_serial: str, op: str, *, forced: bool = False) -> None: ...

    def _init_walls(self) -> None:
        # Wall thermostat address -> timer handing a reported setpoint on to the room, and
        # the thermostats it leaves out (the reporting one, any that boosts meanwhile).
        self._forwards: dict[int, tuple[asyncio.TimerHandle, set[int]]] = {}
        # Wall thermostat address -> the setpoint taken with the last answer, for on_frame:
        # (sender, counter, mode, target, until).
        self._reports: dict[int, tuple[int, int, Mode, float | None, datetime | None]] = {}
        # Wall thermostat address -> its temperature telegram queued or on air, and the
        # scheduler it went to (its clock is the deadline's).
        self._temps: dict[int, Command] = {}
        self._temp_schedulers: dict[int, RadioScheduler] = {}
        # Wall thermostat address -> {thermostat address: hub time an addressed telegram
        # last went on air to it} (round robin while the group is not confirmed).
        self._turns: dict[int, dict[int, float]] = {}
        # Wall thermostat address -> hub time since which it could send (for the first one).
        self._eligible_since: dict[int, float] = {}
        # Wall thermostat address -> hub time its last telegram went on air, delivered or
        # not: the next one waits the room's interval (an unreachable thermostat must not
        # cost an attempt per tick).
        self._attempted_at: dict[int, float] = {}
        # Wall thermostat address -> timer for its next telegram (the hub's 60 s tick is
        # only the safety net), and hub time before which none is built (reserve, LOVF).
        self._wall_timers: dict[int, asyncio.TimerHandle] = {}
        self._retry_at: dict[int, float] = {}
        # Window state: the one the last telegram was built with, hub time of the last
        # change sent at once, the timer for a change within the gap, and the thermostats
        # still owed a telegram with the new state (0: the group).
        self._window_last: dict[int, bool] = {}
        self._window_at: dict[int, float] = {}
        self._window_timers: dict[int, asyncio.TimerHandle] = {}
        self._window_owed: dict[int, set[int]] = {}
        # Wall thermostat address -> hub times its immediate window telegrams went on air
        # (last hour); rooms whose hourly budget bites (warned once until it recovers).
        self._window_air: dict[int, list[float]] = {}
        self._window_over: set[int] = set()
        # Rooms whose LOVF back-off was logged (once until a telegram goes out again).
        self._lovf_logged: set[int] = set()
        # Radio module -> the cadence its rooms were last sent at (logged on a change).
        self._cadences: dict[str, float] = {}
        # Wall thermostat address -> hub time its boost began and the state it returns to.
        self._boosts: dict[int, tuple[float, tuple[Mode | None, float | None, datetime | None]]] = {}
        # Wall thermostats changed while answering (an away period ended): Home Assistant
        # hears of it after the answer.
        self._unnotified: set[int] = set()
        # (wall thermostat, thermostat): its telegram proved an open link addition; settled
        # after the answer.
        self._proofs: set[tuple[int, int]] = set()
        # (wall thermostat, thermostat) -> timer putting a thermostat that reported
        # automatic mode without a known program back to the room's setpoint.
        self._corrections: dict[tuple[int, int], asyncio.TimerHandle] = {}
        # Wall thermostats whose away period ended into manual mode while answering: their
        # thermostats get the setpoint after the answer.
        self._resume_sends: set[int] = set()
        # No timers and no commands any more (the hub stops).
        self._stopped = False

    def _stop_walls(self) -> None:
        self._stopped = True
        for handle, _skip in self._forwards.values():
            handle.cancel()
        self._forwards.clear()
        for handle in self._corrections.values():
            handle.cancel()
        self._corrections.clear()
        self._resume_sends.clear()
        for handle in [*self._wall_timers.values(), *self._window_timers.values()]:
            handle.cancel()
        self._wall_timers.clear()
        self._window_timers.clear()
        self._reports.clear()
        self._temps.clear()
        self._temp_schedulers.clear()

    def _forget_wall(self, address: int) -> None:
        """Drop the runtime state of a wall thermostat (it is being removed)."""
        if self._temps.pop(address, None) is not None:
            self._hub._cancel_key(f"vwt:{address}")
        for state in (
            self._temp_schedulers, self._turns, self._attempted_at, self._eligible_since, self._boosts,
            self._retry_at, self._window_last, self._window_at, self._window_owed, self._window_air,
        ):
            state.pop(address, None)
        self._window_over.discard(address)
        self._lovf_logged.discard(address)
        self._cancel_room_timers(address)

    def _cancel_room_timers(self, address: int) -> None:
        for timers in (self._wall_timers, self._window_timers):
            handle = timers.pop(address, None)
            if handle is not None:
                handle.cancel()
        self._unnotified.discard(address)
        self._resume_sends.discard(address)
        for pair in [p for p in self._corrections if p[0] == address]:
            self._corrections.pop(pair).cancel()
        self._proofs = {pair for pair in self._proofs if pair[0] != address}

    def program_known(self, address: int) -> bool:
        """Whether the virtual wall thermostat (or the one whose room this thermostat
        belongs to) holds a week program for all seven days: only then is automatic mode
        possible, since every 0x42 sets the thermostats' target."""
        dev = self._hub.devices.get(address)
        if dev is None:
            return False
        wall = dev if dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT else self.wall_of(dev)
        return wall is not None and self._program_known(wall)

    def in_room(self, address: int) -> bool:
        """Whether the device is a virtual wall thermostat or belongs to the room of one."""
        dev = self._hub.devices.get(address)
        if dev is None:
            return False
        return (dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT) or self.wall_of(dev) is not None

    @staticmethod
    def _program_known(wall: MaxDevice) -> bool:
        return all(isinstance(wall.week_profile.get(day), list) and wall.week_profile[day] for day in WEEKDAYS)

    def program_written(self, wall: MaxDevice) -> None:
        """The wall thermostat's week program was written: a setpoint changed meanwhile in
        automatic mode no longer holds; the mode stays. The caller notifies."""
        wall.override_target = wall.override_until = None
        self._refresh(wall)

    def _after_refresh(self, wall: MaxDevice) -> None:
        """What an ended away period still owes the room once nothing is being answered:
        back in manual mode, every thermostat gets the setpoint (they went to automatic
        mode by themselves)."""
        if wall.address not in self._resume_sends:
            return
        self._resume_sends.discard(wall.address)
        if self._stopped or wall.removing or wall.mode is not Mode.MANUAL or wall.target is None:
            return
        self._send_to_room(wall, wall.target, Mode.MANUAL, None)

    @staticmethod
    def _linked(dev: MaxDevice, other: MaxDevice) -> bool:
        """Linked on both sides (a real device's side once it acknowledged)."""
        return other.serial in dev.links and dev.serial in other.links

    def _wall_ack_payload(self, dev: MaxDevice, frame: Frame) -> bytes:
        """A setpoint is taken first, so the answer carries it; one not taken is answered
        with itself (the thermostat is satisfied, the room unchanged). Without a usable
        target the answer is that of a contact. Nothing here may call Home Assistant."""
        if self._refresh(dev):
            self._unnotified.add(dev.address)
        sender = self._hub.devices.get(frame.src)
        if sender is not None and frame.msg_type in (MsgType.SET_TEMPERATURE, MsgType.WAKE_UP):
            self._note_proof(dev, sender)
        answer = None
        if frame.msg_type == MsgType.SET_TEMPERATURE:
            answer = self._take_setpoint(dev, frame)
        mode, target = answer if answer is not None else (dev.mode or Mode.AUTO, dev.target)
        if target is None or not OFF_TEMPERATURE <= target <= MAX_TEMPERATURE:
            target = dev.target
        if target is not None and OFF_TEMPERATURE <= target <= MAX_TEMPERATURE:
            return encode_wall_ack(mode, target)
        return b"\x00"

    def _note_proof(self, wall: MaxDevice, sender: MaxDevice) -> None:
        """A thermostat that talks to the wall thermostat while its link addition is open
        carries the link (its acknowledgement got lost)."""
        entry = sender.link_op(wall.serial)
        if (
            sender.is_heating_thermostat
            and not wall.removing
            and sender.serial in wall.links
            and wall.serial not in sender.links
            and entry is not None
            and entry["op"] == LINK_ADD
        ):
            self._proofs.add((wall.address, sender.address))

    def _member(self, wall: MaxDevice, sender: MaxDevice) -> bool:
        """Linked on both sides, or proven so by this very telegram."""
        return self._linked(wall, sender) or (wall.address, sender.address) in self._proofs

    def _wall_frame(self, dev: MaxDevice, sender: MaxDevice, frame: Frame) -> None:
        """After the answer: a proven link is settled, a setpoint taken with it becomes the
        reporting thermostat's own as well, a linked contact's state reaches the wall
        thermostat."""
        if (dev.address, sender.address) in self._proofs:
            self._proofs.discard((dev.address, sender.address))
            self._hub._link_proven(sender, dev.address)
            self.link_committed(sender, dev.serial, LINK_ADD)
        if dev.address in self._unnotified:
            self._unnotified.discard(dev.address)
            self._hub._notify(dev)
        self._after_refresh(dev)
        if frame.msg_type == MsgType.SET_TEMPERATURE:
            report = self._reports.get(dev.address)
            if report is None or report[:2] != (frame.src, frame.counter):
                return  # not taken (not linked, removing, unusable) or a repeat
            del self._reports[dev.address]
            _src, _counter, mode, target, until = report
            # What it reports is newer than anything still pending for it, a poke included
            # (its end would put back the old target).
            self._hub._cancel_key(f"set:{sender.address}")
            self._hub._pokes.pop(sender.address, None)
            sender.clear_pending()
            sender.mode = mode
            if target is not None:
                sender.target = target
            sender.until = until
            self._hub._notify(dev)
            self._hub._notify(sender)
        elif frame.msg_type == MsgType.SHUTTER_CONTACT_STATE and self._linked(dev, sender):
            # The hub stored the contact's state with the contact.
            self._hub._notify(dev)
            self.window_changed(dev)

    # --- Room temperature (0x42) ---

    def set_measured(self, address: int, celsius: float | None) -> None:
        """New value of the wall thermostat's source (None: unavailable). Cheap: Home
        Assistant may call it every second."""
        dev = self.get(address)
        if dev is None or dev.device_type is not DeviceType.WALL_THERMOSTAT:
            raise FrameError(f"no virtual wall thermostat at {address:06X}", key="device_unknown")
        before = (dev.measured, dev.source_ok)
        if celsius is None or not MEASURED_MIN <= celsius <= MEASURED_MAX:
            dev.source_ok, dev.measured = False, None
            if self._temps.pop(address, None) is not None:
                self._temp_schedulers.pop(address, None)
                self._hub._cancel_key(f"vwt:{address}")  # a waiting one goes no more
        else:
            dev.source_ok, dev.measured = True, round(celsius, 1)
        if (dev.measured, dev.source_ok) != before:
            self._hub._notify(dev)
        if dev.source_ok:
            self.tick()

    def tick(self) -> None:
        """Queue the room temperature for every wall thermostat that is due (from the
        hub's periodic tick, the safety net, and with every new source value)."""
        if self._stopped:
            return
        now = self._hub._now()
        for wall in self._walls():
            self._tick_one(wall, now)

    def _tick_one(self, wall: MaxDevice, now: float) -> None:
        try:
            if self._refresh(wall) or wall.address in self._unnotified:
                self._unnotified.discard(wall.address)
                self._hub._notify(wall)
            self._after_refresh(wall)
            self._tick_wall(wall, now)
        except Exception:  # noqa: BLE001 - one room must not stop the others
            _LOGGER.exception("MAX! %s (%s): room temperature", wall.name or wall.serial, wall.serial)

    def _arm(self, address: int, delay: float) -> None:
        """The room's timer for its next telegram (replaces an armed one)."""
        old = self._wall_timers.pop(address, None)
        if old is not None:
            old.cancel()
        if self._stopped:
            return
        self._wall_timers[address] = asyncio.get_running_loop().call_later(
            max(delay, WT_TIMER_MIN_S), self._timer_fired, address
        )

    def _timer_fired(self, address: int) -> None:
        self._wall_timers.pop(address, None)
        wall = self.get(address)
        if wall is None or self._stopped or wall.device_type is not DeviceType.WALL_THERMOSTAT:
            return
        self._tick_one(wall, self._hub._now())

    def _wake(self, address: int) -> None:
        """Look at the room again once the current callback is over (not while a
        scheduler or an answer is still busy)."""
        self._arm(address, 0.0)

    def _tick_wall(self, wall: MaxDevice, now: float) -> None:
        address = wall.address
        mates = self._mates(wall)
        if self._stopped or wall.removing or not wall.source_ok or wall.measured is None or not mates:
            self._eligible_since.pop(address, None)
            if not mates:
                self._cancel_room_timers(address)  # nobody left to send to
            return
        since = self._eligible_since.setdefault(address, now)
        pending = self._temps.get(address)
        if pending is not None:
            if pending.first_sent_at is not None or pending.deadline is None:
                return  # its outcome looks at the room again
            scheduler = self._temp_schedulers.get(address)
            if scheduler is not None and scheduler.now() < pending.deadline:
                self._arm(address, pending.deadline - scheduler.now())
                return
            # Waited past its expiry behind other commands and never went out: dropped,
            # the next one is built anew (it may now go ahead as a starved room).
            self._hub._cancel_key(pending.key or "")
            del self._temps[address]
            self._temp_schedulers.pop(address, None)
        retry_at = self._retry_at.get(address)
        if retry_at is not None and now < retry_at:
            self._arm(address, retry_at - now)
            return
        group, module = self._room_group(mates)
        cadence = self._cadence(mates)
        # Addressed, each thermostat needs one every cadence: the room sends N times as
        # often, round robin.
        interval = cadence if group else cadence / len(mates)
        attempted_at = self._attempted_at.get(address)
        if attempted_at is None and wall.sent_at is not None and 0 <= now - wall.sent_at < cadence:
            # After a restart: delivered a moment ago, the next is due on the usual cadence
            # (addressed: after interval = cadence / N, so the round robin reaches every
            # thermostat within the cadence of that telegram).
            attempted_at = self._attempted_at[address] = wall.sent_at
        owed = self._window_owed.get(address)
        if owed and not group:
            owed &= {mate.address for mate in mates}  # one that left the room is owed nothing
        if not owed and attempted_at is not None and now - attempted_at < interval:
            self._arm(address, attempted_at + interval - now)
            return
        measured, sent_at = wall.measured, wall.sent_at
        reference = self._reference(wall, mates, now)
        value = measured
        if reference is not None and measured < reference - WT_DROP_STEP:
            value = round(reference - WT_DROP_STEP, 1)
        target = self._room_target(wall)
        if target is None or not OFF_TEMPERATURE <= target <= MAX_TEMPERATURE:
            return
        # Goes ahead of waiting commands once: not again while attempts go on air
        # without an answer (sent_at stays, attempted_at moves).
        starved_after = cadence + (WT_STARVED_S - WT_INTERVAL_S)  # the margin over a slower cadence too
        starved = (
            (sent_at is not None and now - sent_at >= starved_after)
            or (sent_at is None and now - since > starved_after)
        ) and (attempted_at is None or now - attempted_at >= starved_after)
        if group:
            dst, radio = 0, module
            scheduler = self._hub._radio_of(mates[0]).scheduler
        else:
            turns = self._turns.get(address, {})
            candidates = [mate for mate in mates if mate.address in owed] if owed else mates
            dst = min(candidates, key=lambda mate: turns.get(mate.address, float("-inf"))).address
            radio = None
            scheduler = self._hub._scheduler_for(dst)
        window = self.window_open(address)
        self._window_last[address] = window
        cmd = Command(
            dst=dst,
            build=lambda counter: build_wall_thermostat_control(counter, address, dst, group, target, value),
            priority=PRIO_REPLY if starved else PRIO_BACKGROUND,
            key=f"vwt:{address}",
            expects_ack=not group,
            retries=None if group else 0,
            # The airtime kept free for commands follows the option "limit airtime to
            # 36 s" (brake); without it the stick decides (LOVF ends the telegram).
            reserve=WT_RESERVE_S if self._hub._brake else 0.0,
            expire_on_lovf=True,
        )
        cmd.deadline = scheduler.now() + WT_EXPIRE_S
        immediate = bool(owed)
        cmd.on_done = lambda _ok: self._temp_done(address, cmd, value, window, scheduler, immediate)
        self._temps[address] = cmd
        self._temp_schedulers[address] = scheduler
        self._hub._submit(cmd, radio)
        self._arm(address, WT_EXPIRE_S)  # rebuilt at its expiry if it waits that long

    def window_changed(self, wall: MaxDevice) -> None:
        """The room's window state may have changed (a linked contact): a changed state
        goes out at once, at most once per WT_WINDOW_GAP_S, in place of a telegram that
        still waits; it counts as the room's telegram."""
        address = wall.address
        if self._stopped or wall.removing or address in self._window_timers:
            return  # the gap's timer looks at the latest state
        if self._window_last.get(address) == self.window_open(address):
            return  # the telegram built last carries it (or the owed ones still go)
        now = self._hub._now()
        aired = [t for t in self._window_air.get(address, []) if now - t < WT_WINDOW_HOUR_S]
        self._window_air[address] = aired
        if len(aired) >= WT_WINDOW_HOUR_MAX:
            # A flapping source must not drain the stick: the next regular telegram
            # carries the window state.
            if address not in self._window_over:
                self._window_over.add(address)
                _LOGGER.warning(
                    "MAX! %s (%s): %d window changes sent at once within the hour, further ones go "
                    "with the regular room temperature", wall.name or wall.serial, wall.serial, WT_WINDOW_HOUR_MAX,
                )
            return
        self._window_over.discard(address)
        last = self._window_at.get(address)
        if last is not None and now - last < WT_WINDOW_GAP_S:
            self._window_timers[address] = asyncio.get_running_loop().call_later(
                WT_WINDOW_GAP_S - (now - last), self._window_gap_over, address
            )
            return
        self._window_at[address] = now
        mates = self._mates(wall)
        # Every thermostat gets the new state (addressed one after the other; the group
        # telegram serves them all).
        self._window_owed[address] = {mate.address for mate in mates}
        pending = self._temps.get(address)
        if pending is not None and pending.first_sent_at is None:
            # Still waiting with the old target: replaced (one per room on the way).
            self._hub._cancel_key(pending.key or "")
            del self._temps[address]
            self._temp_schedulers.pop(address, None)
        self._wake(address)  # a back-off (LOVF, reserve) still holds

    def _window_gap_over(self, address: int) -> None:
        self._window_timers.pop(address, None)
        wall = self.get(address)
        if wall is not None:
            self.window_changed(wall)

    def _module_load(self, module: str) -> int:
        """Room temperature telegrams per cadence through this module: one per room that
        goes to its group, one per thermostat of a room that goes addressed. Rooms that
        cannot send now (no source, being removed) do not count."""
        load = 0
        for wall in self._walls():
            if wall.removing or not wall.source_ok or wall.measured is None:
                continue
            mates = self._mates(wall)
            if not mates:
                continue
            group, group_module = self._room_group(mates)
            if group:
                load += group_module == module
            else:
                load += sum(1 for mate in mates if self._hub._radio_of(mate).id == module)
        return load

    def _cadence(self, mates: list[MaxDevice]) -> float:
        """How often (s) each thermostat of this room gets its telegram: WT_INTERVAL_S
        while its module carries no more than WT_FULL_RATE of them, slower in proportion
        beyond (the busiest module of the room counts), WT_INTERVAL_MAX_S at most."""
        cadence = WT_INTERVAL_S
        for module in {self._hub._radio_of(mate).id for mate in mates}:
            load = self._module_load(module)
            module_cadence = min(WT_INTERVAL_MAX_S, WT_INTERVAL_S * max(1.0, load / WT_FULL_RATE))
            if self._cadences.get(module, WT_INTERVAL_S) != module_cadence:
                _LOGGER.info(
                    "MAX! radio module %s: %d room temperature telegrams per round, sent every %.0f s%s",
                    module or "main", load, module_cadence,
                    " (more do not fit into the airtime: use a further radio module)"
                    if WT_INTERVAL_S * load / WT_FULL_RATE > WT_INTERVAL_MAX_S else "",
                )
            self._cadences[module] = module_cadence
            cadence = max(cadence, module_cadence)
        return cadence

    def room_interval(self, wall: MaxDevice) -> float | None:
        """Seconds between two room temperature telegrams to each thermostat of the room;
        None without a confirmed thermostat."""
        mates = self._mates(wall)
        return self._cadence(mates) if mates else None

    def _room_group(self, mates: list[MaxDevice]) -> tuple[int, str]:
        """One telegram to the group if every thermostat has the same confirmed group and
        sits on the same module: it goes through that module, whatever the wall
        thermostat's own. Otherwise (group 0) addressed, one at a time, each through its
        module."""
        groups = {mate.group for mate in mates}
        modules = {self._hub._radio_of(mate).id for mate in mates}
        if len(groups) == 1 and len(modules) == 1:
            return groups.pop(), modules.pop()
        return 0, ""

    def room_form(self, wall: MaxDevice) -> str | None:
        """How the room temperature reaches the thermostats: "group" (one telegram),
        "addressed" (one per thermostat in turn), None without a confirmed thermostat."""
        mates = self._mates(wall)
        if not mates:
            return None
        return "group" if self._room_group(mates)[0] else "addressed"

    def room_form_reason(self, wall: MaxDevice) -> str | None:
        """Why the room temperature goes addressed: "modules" (the thermostats sit on
        different radio modules, a group cannot help), "pending" (a group id is on its
        way), "no_group"; None when it goes to the group or there is no thermostat."""
        mates = self._mates(wall)
        if not mates or self._room_group(mates)[0]:
            return None
        if len({self._hub._radio_of(mate).id for mate in mates}) > 1:
            return "modules"
        if any(mate.pending_group is not None for mate in mates):
            return "pending"
        return "no_group"

    def _reference(self, wall: MaxDevice, mates: list[MaxDevice], now: float) -> float | None:
        """What a drop is limited against: the value sent last; after a pause the
        thermostats' own reading if it is newer."""
        sent_at = wall.sent_at
        if sent_at is not None and now - sent_at < WT_PAUSE_S:
            return wall.sent_measured
        readings = [
            (mate.measured_at, mate.measured) for mate in mates
            if mate.measured is not None and mate.measured_at is not None
        ]
        if readings:
            measured_at, measured = max(readings)
            if sent_at is None or measured_at >= sent_at:
                return measured
        return wall.sent_measured

    def _room_target(self, wall: MaxDevice) -> float | None:
        """Target in the telegram: the window temperature while a window is open,
        otherwise the room's (in boost its normal one: the telegram carries no mode)."""
        if self.window_open(wall.address):
            return wall.window_open_temperature
        return self._effective_target(wall)

    def _effective_target(self, wall: MaxDevice) -> float | None:
        """In automatic mode a setpoint changed meanwhile, else the week program's;
        otherwise (and without a program) the wall thermostat's own."""
        if wall.mode is Mode.AUTO:
            if wall.override_target is not None:
                return wall.override_target
            target = program_target(wall.week_profile, self._hub._local_now())
            if target is not None:
                return target
        return wall.target

    def _refresh(self, wall: MaxDevice) -> bool:
        """What ends by itself, as at a real wall thermostat: a boost after its duration,
        an away period at its end (back to the state before it), a setpoint changed in
        automatic mode at the program's next switch point; in automatic mode the target
        follows the program. Never notifies nor sends (it runs while answering); True if
        anything changed."""
        hub = self._hub
        before = (wall.mode, wall.target, wall.until, wall.override_target, wall.override_until)
        name = wall.name or wall.serial
        if wall.mode is Mode.BOOST:
            started, previous = self._boosts.setdefault(wall.address, (hub._now(), (Mode.AUTO, wall.target, None)))
            if hub._now() - started >= self._boost_seconds(wall):
                del self._boosts[wall.address]
                wall.mode, target, wall.until = previous
                if target is not None:
                    wall.target = target
                if wall.mode is Mode.AUTO and not self._program_known(wall):
                    wall.mode = Mode.MANUAL  # automatic mode needs a known program
                _LOGGER.info("MAX! %s (%s): boost ended", name, wall.serial)
        if hub._expired(wall.mode, wall.until):
            self._end_away(wall)
        if wall.override_target is not None and (
            wall.mode not in (Mode.AUTO, Mode.BOOST)
            or (wall.override_until is not None and hub._local_now() >= wall.override_until)
        ):
            wall.override_target = wall.override_until = None
        if wall.mode is Mode.AUTO:
            target = self._effective_target(wall)
            if target is not None:
                wall.target = target
        return before != (wall.mode, wall.target, wall.until, wall.override_target, wall.override_until)

    def _end_away(self, wall: MaxDevice) -> None:
        """Back to what applied before the away period: automatic mode if it was and the
        program is known (the thermostats return to it by themselves), else manual mode
        with the target before it, else the comfort value; then the thermostats get it."""
        name = wall.name or wall.serial
        resume_mode, resume_target = wall.resume_mode, wall.resume_target
        wall.resume_mode = wall.resume_target = None
        wall.until = None
        wall.override_target = wall.override_until = None
        if resume_mode is Mode.AUTO and self._program_known(wall):
            wall.mode = Mode.AUTO
            _LOGGER.info("MAX! %s (%s): away period ended, back to automatic", name, wall.serial)
            return
        target = resume_target
        if target is None and isinstance(wall.config.get("komfort"), int | float):
            target = float(wall.config["komfort"])
        wall.mode = Mode.MANUAL
        if target is not None:
            wall.target = target
        _LOGGER.info(
            "MAX! %s (%s): away period ended, back to manual %s", name, wall.serial,
            "-" if wall.target is None else f"{wall.target:.1f}",
        )
        self._resume_sends.add(wall.address)

    def _boost_seconds(self, wall: MaxDevice) -> float:
        """The room's boost duration (its thermostats' setting), WT_BOOST_MAX_S at most."""
        minutes = [
            mate.config.get("boost_dauer") for mate in self._mates(wall)
            if isinstance(mate.config.get("boost_dauer"), int | float)
        ]
        return min(WT_BOOST_MAX_S, 60.0 * max(minutes, default=5))

    def _temp_done(
        self, address: int, cmd: Command, value: float, window: bool, scheduler: RadioScheduler,
        immediate: bool = False,
    ) -> None:
        if self._temps.get(address) is cmd:
            del self._temps[address]
            self._temp_schedulers.pop(address, None)
        wall = self.get(address)
        if wall is None:
            return
        now = self._hub._now()
        name = wall.name or wall.serial
        if cmd.first_sent_at is not None:
            # On air, answered or not: counts for the interval from when it went out, and
            # the next addressed one goes to another thermostat. One never written
            # (reserve, expiry) does not.
            aired = now - max(0.0, scheduler.now() - cmd.first_sent_at)
            self._attempted_at[address] = aired
            if cmd.dst:
                self._turns.setdefault(address, {})[cmd.dst] = aired
            self._lovf_logged.discard(address)
            if immediate:
                self._window_air.setdefault(address, []).append(aired)
            owed = self._window_owed.get(address)
            if owed is not None and window == self.window_open(address):
                if cmd.dst:
                    owed.discard(cmd.dst)
                else:
                    owed.clear()  # the group telegram reached them all
                if not owed:
                    del self._window_owed[address]
            elif owed is not None and immediate:
                # The window changed again while this window telegram was on air: the new
                # state is a change of its own, under the gap and the hourly budget. (After
                # a regular one the owed change simply goes now.)
                del self._window_owed[address]
                self.window_changed(wall)
        elif cmd.lovf:
            # The stick's own budget is empty: not again before the back-off (logged once
            # until a telegram goes out again).
            self._retry_at[address] = now + WT_LOVF_BACKOFF_S
            if address not in self._lovf_logged:
                self._lovf_logged.add(address)
                _LOGGER.info(
                    "MAX! %s (%s): room temperature refused by the radio module (LOVF), again in %.0f s",
                    name, wall.serial, WT_LOVF_BACKOFF_S,
                )
        elif cmd.outcome is Outcome.EXPIRED and not (
            cmd.deadline is not None and scheduler.now() >= cmd.deadline
        ):
            self._retry_at[address] = now + WT_RESERVE_RETRY_S  # the airtime reserve
        if cmd.outcome in (Outcome.SENT, Outcome.ACKED):
            wall.sent_at, wall.sent_measured = now, value
            self._hub._notify(wall)
        self._wake(address)


    def window_open(self, address: int) -> bool:
        """Whether any contact linked with this virtual wall thermostat (real or virtual) is open."""
        dev = self.get(address)
        if dev is None:
            return False
        return any(
            other.device_type is DeviceType.SHUTTER_CONTACT
            and other.window_open is True
            and (not other.virtual or other.source_ok)  # a virtual one without source: closed
            and self._linked(dev, other)
            for other in self._hub.devices.values()
        )

    def wall_of(self, dev: MaxDevice) -> MaxDevice | None:
        """The virtual wall thermostat whose room this radiator thermostat belongs to
        (linked on both sides, not being removed)."""
        if not dev.is_heating_thermostat:
            return None
        return next(
            (
                wall for wall in self._walls()
                if not wall.removing and self._linked(wall, dev)
            ),
            None,
        )

    def _mates(self, wall: MaxDevice) -> list[MaxDevice]:
        """The radiator thermostats that carry the link with the wall thermostat."""
        return [
            d for d in self._hub.devices.values()
            if d.is_heating_thermostat and not d.virtual and self._linked(wall, d)
        ]

    def _walls(self) -> list[MaxDevice]:
        return [
            d for d in self._hub.devices.values()
            if d.virtual and d.device_type is DeviceType.WALL_THERMOSTAT
        ]

    def set_setpoint(
        self, wall: MaxDevice, target: float | None, mode: Mode, until: datetime | None = None
    ) -> None:
        """A setpoint from Home Assistant for the room (validated by the hub): the wall
        thermostat has it at once, every linked thermostat gets it addressed."""
        if wall.removing:
            raise FrameError(f"{wall.name or wall.serial} is being removed", key="virtual_removing")
        self._cancel_forward(wall.address)  # this one is newer than the reported one
        self._adopt(wall, target, mode, until)
        self._hub._notify(wall)
        self._send_to_room(wall, target, mode, until)

    def _cancel_forward(self, address: int) -> None:
        pending = self._forwards.pop(address, None)
        if pending is not None:
            pending[0].cancel()

    def _adopt(self, wall: MaxDevice, target: float | None, mode: Mode, until: datetime | None) -> None:
        """The wall thermostat's own state; the caller notifies (not before the answer is
        out). A target in automatic mode holds until the program's next switch point. An
        away period remembers what it returns to (a later one replacing it keeps that)."""
        if mode is Mode.TEMPORARY and wall.mode is not Mode.TEMPORARY:
            boost = self._boosts.get(wall.address)
            if wall.mode is Mode.BOOST and boost is not None:
                wall.resume_mode, wall.resume_target = boost[1][0], boost[1][1]
            else:
                wall.resume_mode, wall.resume_target = wall.mode, wall.target
        elif mode not in (Mode.TEMPORARY, Mode.BOOST):
            wall.resume_mode = wall.resume_target = None
        if mode is Mode.BOOST and wall.mode is not Mode.BOOST:
            self._boosts[wall.address] = (self._hub._now(), (wall.mode or Mode.AUTO, wall.target, wall.until))
        elif mode is not Mode.BOOST:
            self._boosts.pop(wall.address, None)
        wall.mode = mode
        if target is not None:
            wall.target = target
        wall.until = until if mode is Mode.TEMPORARY else None
        if mode is Mode.AUTO and target is not None:
            now = self._hub._local_now()
            if program_target(wall.week_profile, now) is not None:
                wall.override_target, wall.override_until = target, next_switch(wall.week_profile, now)
            else:
                wall.override_target = wall.override_until = None
        elif mode is not Mode.BOOST:
            wall.override_target = wall.override_until = None
        self._refresh(wall)
        wall.note_comfort()

    def _send_to_room(
        self, wall: MaxDevice, target: float | None, mode: Mode, until: datetime | None,
        *, skip: set[int] | frozenset[int] = frozenset(),
    ) -> None:
        if self._stopped:
            return
        for mate in self._mates(wall):
            if mate.address not in skip:
                self._hub._send_setpoint(mate, target, mode, until, group=0)

    def _take_setpoint(self, wall: MaxDevice, frame: Frame) -> tuple[Mode, float | None] | None:
        """A thermostat of the room reports a setpoint (handwheel, boost button): the wall
        thermostat takes it, and hands a change on to the other thermostats a little
        later. Measured 20.11.2026: a boost, and a setpoint that changes nothing, stay
        with the wall thermostat. Returns what the answer carries when it is not the wall
        thermostat's state: a setpoint not taken is answered with itself (otherwise the
        thermostat tries again every minute), a boost with the boost status."""
        mode, target = decode_set_temperature(frame.payload)
        sender = self._hub.devices.get(frame.src)
        if wall.removing or sender is None or not self._member(wall, sender):
            return mode, target
        name = wall.name or wall.serial
        if mode is Mode.AUTO and not self._program_known(wall):
            # The Auto button at the device: without a known program the room stays as it
            # is; answered with itself (the thermostat is satisfied), then put back.
            _LOGGER.info(
                "MAX! %s (%s): automatic mode of %s not taken (no week program known), it gets the room's setpoint",
                name, wall.serial, sender.serial,
            )
            if wall.mode is Mode.TEMPORARY:
                # Auto ends an away period: the room returns to what applied before (as
                # at its end time); every thermostat gets that after the answer.
                self._end_away(wall)
                self._unnotified.add(wall.address)
                return mode, target
            self._schedule_correction(wall, sender)
            return mode, target
        until = None
        if mode is Mode.TEMPORARY and len(frame.payload) >= 4:
            try:
                until = decode_until(frame.payload[1:4])
            except FrameError:
                until = None
        if mode is Mode.TEMPORARY and until is None:
            # Without a readable end time it would end at once (an away period ends at
            # its end time) and cannot be handed on (a 0x40 needs it): answered with
            # itself so the thermostat is satisfied, the room stays as it is.
            _LOGGER.info("MAX! %s (%s): away setpoint of %s without end time not taken", name, wall.serial, sender.serial)
            return mode, target
        new_target: float | None = target
        if mode is Mode.AUTO and not target:
            new_target = None  # automatic mode without a value of its own
        elif not OFF_TEMPERATURE <= target <= MAX_TEMPERATURE:
            # No thermostat sets this (off is 4.5, on 30.5): a garbled value must not become
            # the room's setpoint. The answer keeps the old target.
            _LOGGER.info("MAX! %s (%s): setpoint %.1f of %s ignored", name, wall.serial, target, sender.serial)
            return None
        self._reports[wall.address] = (frame.src, frame.counter, mode, new_target, until)
        if mode is Mode.BOOST:
            # Only that thermostat boosts: the room keeps its mode, the answer says boost.
            _LOGGER.info("MAX! %s (%s): boost at %s", name, wall.serial, sender.serial)
            pending = self._forwards.get(wall.address)
            if pending is not None:
                pending[1].add(sender.address)  # a forward still waiting must not end its boost
            return Mode.BOOST, wall.target
        before = (wall.target, wall.mode, wall.until)
        self._adopt(wall, new_target, mode, until)
        changed = (
            (new_target is not None and new_target != before[0])
            or until != before[2]
            or (mode is not before[1] and Mode.BOOST not in (mode, before[1]))
        )
        _LOGGER.info(
            "MAX! %s (%s): setpoint %s %s from %s%s", name, wall.serial, mode.name,
            "-" if new_target is None else f"{new_target:.1f}", sender.serial, " (for the room)" if changed else "",
        )
        if not changed or self._stopped:
            return None
        self._cancel_forward(wall.address)
        self._forwards[wall.address] = (
            asyncio.get_running_loop().call_later(
                WT_FORWARD_DELAY_S, self._forward, wall.address, new_target, mode, until
            ),
            {sender.address},
        )
        return None

    def _schedule_correction(self, wall: MaxDevice, sender: MaxDevice) -> None:
        if self._stopped:
            return
        pair = (wall.address, sender.address)
        old = self._corrections.pop(pair, None)
        if old is not None:
            old.cancel()
        self._corrections[pair] = asyncio.get_running_loop().call_later(WT_FORWARD_DELAY_S, self._correct, pair)

    def _correct(self, pair: tuple[int, int]) -> None:
        """The thermostat that went to automatic mode gets the room's setpoint again."""
        self._corrections.pop(pair, None)
        wall, mate = self.get(pair[0]), self._hub.devices.get(pair[1])
        if self._stopped or wall is None or mate is None or wall.removing or not self._linked(wall, mate):
            return
        if wall.mode is Mode.AUTO and self._program_known(wall):
            return  # a program arrived meanwhile: automatic mode is right
        if wall.target is None:
            return
        if wall.mode is Mode.TEMPORARY and not self._hub._expired(wall.mode, wall.until):
            self._hub._send_setpoint(mate, wall.target, Mode.TEMPORARY, wall.until, group=0)
        else:
            self._hub._send_setpoint(mate, wall.target, Mode.MANUAL, None, group=0)

    def _forward(self, address: int, target: float | None, mode: Mode, until: datetime | None) -> None:
        pending = self._forwards.pop(address, None)
        wall = self.get(address)
        if pending is None or wall is None or wall.removing or self._hub._expired(mode, until):
            return
        self._send_to_room(wall, target, mode, until, skip=pending[1])

    def _wall_link_committed(self, dev: MaxDevice, partner: MaxDevice, op: str, *, forced: bool = False) -> None:
        """Who wins when a thermostat joins a virtual wall thermostat: the first one hands
        over what eq3_max knows of it to a wall thermostat without a state of its own (no
        radio); each later one, once it took the link, gets the room's setpoint if it has
        another. A thermostat that left the room gives back its group id."""
        if op == LINK_REMOVE:
            for wall in (dev, partner):
                if wall.virtual and wall.device_type is DeviceType.WALL_THERMOSTAT and not self._mates(wall):
                    self._cancel_room_timers(wall.address)  # nobody left to send to
            if partner.virtual and partner.device_type is DeviceType.WALL_THERMOSTAT and dev.is_heating_thermostat:
                self._drop_room_group(dev, forced=forced)
            return
        if op != LINK_ADD:
            return
        if dev.virtual and dev.device_type is DeviceType.WALL_THERMOSTAT and partner.is_heating_thermostat:
            others = [
                d for d in self._hub.devices.values()
                if d.is_heating_thermostat and d is not partner and d.serial in dev.links
            ]
            if not others and dev.mode is None and partner.mode is not None:
                self._adopt_room(dev, partner)
        elif partner.virtual and partner.device_type is DeviceType.WALL_THERMOSTAT and dev.is_heating_thermostat:
            wall = partner
            if not wall.removing and self._linked(wall, dev):
                self._give_room_group(wall, dev)
            if (
                wall.removing
                or wall.mode is None
                or wall.mode is Mode.BOOST  # the room's boost is not handed to a newcomer
                or self._hub._expired(wall.mode, wall.until)
                or not self._linked(wall, dev)
            ):
                return
            if wall.mode is Mode.AUTO:
                differs, target = dev.mode is not Mode.AUTO, None
            else:
                differs, target = (dev.target, dev.mode, dev.until) != (wall.target, wall.mode, wall.until), wall.target
            if differs:
                self._hub._send_setpoint(dev, target, wall.mode, wall.until, group=0)

    @staticmethod
    def _group_of(dev: MaxDevice) -> int:
        return dev.pending_group if dev.pending_group is not None else dev.group

    def _give_room_group(self, wall: MaxDevice, dev: MaxDevice) -> None:
        """A thermostat that took the link gets the room's group id (for the room
        temperature to the group): another thermostat's of the room, else its own if no
        device outside the room uses it, else a free one. The wall thermostat takes it
        without radio. Not set_room_group: that would send to the wall thermostat and
        take the id from every other thermostat."""
        hub = self._hub
        group_of = self._group_of
        mates = self._mates(wall)
        others = [group_of(mate) for mate in mates if mate is not dev and group_of(mate)]
        if len(set(others)) > 1:
            _LOGGER.warning(
                "MAX! %s (%s): the room's thermostats have different group ids (%s), %s gets %d",
                wall.name or wall.serial, wall.serial, ", ".join(str(g) for g in sorted(set(others))),
                dev.name or dev.serial, others[0],
            )
        room = {wall.address, dev.address, *(mate.address for mate in mates)}
        own = group_of(dev)
        if others:
            group = others[0]
        elif own and not any(
            group_of(d) == own for d in hub.devices.values() if d.address not in room and d.is_climate
        ):
            group = own
        else:
            group = hub.free_group([dev, wall])
        if group_of(dev) != group:
            hub.set_group(dev.address, group)
        if wall.group != group:
            hub.set_group(wall.address, group)

    def _drop_room_group(self, dev: MaxDevice, *, forced: bool) -> None:
        """A thermostat whose link to a virtual wall thermostat is gone loses the room's
        group id (one telegram), unless it still belongs to another wall thermostat or the
        removal was forced (a leftover, the device is not ours to tidy)."""
        if forced or not self._group_of(dev):
            return
        if any(
            other.device_type is DeviceType.WALL_THERMOSTAT and other.serial in dev.links
            for other in self._hub.devices.values()
        ):
            return
        _LOGGER.info("MAX! %s (%s): left its virtual room, group id removed", dev.name or dev.serial, dev.serial)
        self._hub.set_group(dev.address, 0)

    def _adopt_room(self, wall: MaxDevice, source: MaxDevice) -> None:
        """The first thermostat's state for a wall thermostat that has none of its own:
        never an empty value over a stored one, never a passing state (boost, the window
        temperature) as the room's setpoint."""
        target, mode = source.target, source.mode
        if mode is Mode.BOOST or (target is not None and target == source.window_open_temperature):
            # As after a reset (_restore): the last comfort value, else automatic.
            target = source.last_comfort
            if target is None and isinstance(source.config.get("komfort"), int | float):
                target = float(source.config["komfort"])
            mode = Mode.MANUAL if target is not None else Mode.AUTO
        for day, points in source.week_profile.items():
            if points and not wall.week_profile.get(day):
                wall.week_profile[day] = copy.deepcopy(points)
        if mode is Mode.AUTO and not self._program_known(wall):
            # Automatic mode needs a known program (each 0x42 sets the target): manual
            # with what it has; the thermostat gets it once it took the link.
            if target is None and isinstance(wall.config.get("komfort"), int | float):
                target = float(wall.config["komfort"])
            mode = Mode.MANUAL
        if mode is Mode.TEMPORARY:
            # Its away period stays; afterwards manual with its comfort value (the
            # state before it is not known).
            wall.resume_mode = Mode.MANUAL
            wall.resume_target = source.last_comfort
        wall.mode = mode
        if target is not None:
            wall.target = target
        wall.until = source.until if mode is Mode.TEMPORARY else None
        for key in CONFIG_VIRTUAL_WALL_KEYS:
            if source.config.get(key) is not None and wall.config_source.get(key, SOURCE_FACTORY) == SOURCE_FACTORY:
                wall.config[key] = source.config[key]
                if key in source.config_source:
                    wall.config_source[key] = source.config_source[key]
        self._refresh(wall)
        wall.note_comfort()
        _LOGGER.info(
            "MAX! %s (%s): setpoint, week profile and settings taken from %s (first thermostat)",
            wall.name or wall.serial, wall.serial, source.name or source.serial,
        )
        self._hub._notify(wall)
        self._after_refresh(wall)
