"""Virtual devices: the hub plays a window contact or a wall thermostat towards real
radiator thermostats. No hardware behind them; their state comes from Home Assistant.

This module creates them and says what they answer, and runs the window contact; the
wall thermostat's part is in virtual_wall.py. The hub does the radio work."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from .devices import LINK_REMOVE, MaxDevice
from .messages import DeviceType, Frame, FrameError, build_shutter_contact_state
from .scheduler import Command, Outcome
from .virtual_wall import WallThermostats

if TYPE_CHECKING:
    from .hub import MaxHub

_LOGGER = logging.getLogger(__name__)

VIRTUAL_TYPES = (DeviceType.SHUTTER_CONTACT, DeviceType.WALL_THERMOSTAT)
_ADDRESS_SPACE = 0x1000000
# A window contact's state counts once it held this long (s): the last of quick changes goes out.
SC_DEBOUNCE_S = 2.0
# A state a partner did not acknowledge is repeated, with a single attempt each: after
# SC_REPEAT_MIN_S (s), from the third failure in a row on after SC_REPEAT_SLOW_S, and
# with the partner's next status (at most every SC_REPEAT_MIN_S, hub wall clock).
SC_REPEAT_MIN_S = 300.0
SC_REPEAT_SLOW_S = 900.0
# Failures in a row towards one partner after which a warning is logged (once) and the
# slow repeat begins.
SC_WARN_FAILURES = 3
# Two window telegrams to one partner go on air at least this far apart (s): a busy door
# or a flapping source must not drain the stick. A change within it goes when it ends.
SC_MIN_GAP_S = 60.0
# At most this many window telegrams to one partner go on air per rolling hour (every
# transmission: first sends, the scheduler's retries and repeats together); beyond it the
# latest state waits for a free slot.
SC_HOUR_MAX = 12
SC_HOUR_S = 3600.0


class Virtuals(WallThermostats):
    """The hub's virtual devices (they live in hub.devices with `virtual` set)."""

    def __init__(self, hub: MaxHub) -> None:
        self._hub = hub
        # Window contact address -> debounce timer of its last change.
        self._timers: dict[int, asyncio.TimerHandle] = {}
        # (contact, partner address) -> its state telegram queued or on air, and the state in it.
        self._sending: dict[tuple[int, int], tuple[Command, bool]] = {}
        # (contact, partner address) -> hub time of the last repeat / failures in a row.
        self._repeated_at: dict[tuple[int, int], float] = {}
        self._failures: dict[tuple[int, int], int] = {}
        # (contact, partner address) -> timer repeating an undelivered state, timer sending
        # a change once the gap since the last telegram is over, loop time the last one
        # went on air.
        self._repeat_timers: dict[tuple[int, int], asyncio.TimerHandle] = {}
        self._gap_timers: dict[tuple[int, int], asyncio.TimerHandle] = {}
        self._aired: dict[tuple[int, int], float] = {}
        # (contact, partner address) -> loop times its telegrams went on air in the last
        # hour, and the pairs whose budget is used up (warned once until it recovers).
        self._air_log: dict[tuple[int, int], list[float]] = {}
        self._over_budget: set[tuple[int, int]] = set()
        # Serials of virtual devices removed while running: a link addition to one that a
        # real device acknowledges later is taken apart again (hub._ghost_link).
        self.removed_serials: set[str] = set()
        self._init_walls()

    def stop(self) -> None:
        """No timers and nothing sent of its own any more (acknowledging goes on while the
        transports run)."""
        self._stop_walls()
        for timer in [*self._timers.values(), *self._repeat_timers.values(), *self._gap_timers.values()]:
            timer.cancel()
        self._timers.clear()
        self._repeat_timers.clear()
        self._gap_timers.clear()
        self._sending.clear()

    def create(
        self,
        device_type: DeviceType,
        name: str,
        source: str,
        radio: str = "",
        *,
        address: int | None = None,
    ) -> MaxDevice:
        """A new virtual device on a free random address, reported like a paired one.
        `radio` is ignored (kept for older callers): a virtual device has no module of its
        own; the restriction to USB modules applies to the thermostats linked with a
        virtual wall thermostat (hub.link)."""
        hub = self._hub
        if device_type not in VIRTUAL_TYPES:
            raise FrameError(f"no virtual {device_type!r}", key="virtual_type")
        if address is None:
            address = self._free_address()
        elif address in (0, hub.address) or address in hub.devices:
            raise FrameError(f"address {address:06X} is taken")
        dev = MaxDevice(
            address, f"VIRT{address:06X}", device_type, name=name, virtual=True, source=source
        )
        dev.ensure_config_defaults()
        hub.devices[address] = dev
        hub._safe(hub._on_device_added, dev)
        return dev

    def _free_address(self) -> int:
        taken = {0, self._hub.address, *self._hub.devices}
        while True:
            address = random.randrange(1, _ADDRESS_SPACE)
            if address not in taken:
                return address

    def get(self, address: int) -> MaxDevice | None:
        dev = self._hub.devices.get(address)
        return dev if dev is not None and dev.virtual else None

    def is_virtual(self, address: int) -> bool:
        return self.get(address) is not None

    # --- Removal in two steps ---

    def remove(self, address: int, *, force: bool = False) -> bool:
        """Remove a virtual device. A real device that still carries it keeps sending to
        it and, unanswered, repeats until its airtime is gone: so it first stops sending
        of its own, keeps acknowledging, every real partner gets RemoveLinkPartner
        (virtual ones drop it at once), and it disappears once no real device carries it
        any more. `force` drops it at once (a partner that is gone or never answers; it
        may still know the address). True if it is gone now."""
        dev = self.get(address)
        if dev is None:
            raise FrameError(f"no virtual device at {address:06X}", key="not_virtual")
        if force:
            dev.removing = True
            self._finish_removal(dev)
            return True
        if dev.removing:
            return self._settle(dev)
        dev.removing = True
        told_open = self._told_open(dev)
        self._drop_runtime(address)
        _LOGGER.info("MAX! %s (%s): being removed, unlinking its partners", dev.name or dev.serial, dev.serial)
        # Queued ahead of the unlink (same queue, same priority): a thermostat last told
        # "open" would otherwise stay at the window temperature.
        for partner in told_open:
            self._send_closed(dev, partner)
        self._unlink_partners(dev, again=True)
        self._hub._notify(dev)
        return self._settle(dev)

    def _told_open(self, dev: MaxDevice) -> list[MaxDevice]:
        """Real partners of a window contact that were last told "open", or have an "open"
        on air (a waiting one is cancelled and never goes out)."""
        if dev.device_type is not DeviceType.SHUTTER_CONTACT:
            return []
        told = []
        for partner in self._hub.devices.values():
            if not self._receives(dev, partner):
                continue
            on_the_way = self._sending.get((dev.address, partner.address))
            on_air = on_the_way is not None and on_the_way[1] and on_the_way[0].first_sent_at is not None
            if dev.delivered.get(partner.serial) is True or on_air:
                told.append(partner)
        return told

    def _send_closed(self, dev: MaxDevice, partner: MaxDevice) -> None:
        """"Closed" to a partner of a contact being removed; the removal does not wait for it."""
        src, dst = dev.address, partner.address
        cmd = Command(
            dst=dst,
            build=lambda counter: build_shutter_contact_state(counter, src, dst, False),
            key=f"vwin:{src}:{dst}",
        )
        cmd.on_done = lambda _ok: self._closed_done(dev, partner, cmd)
        self._sending[(src, dst)] = (cmd, False)
        self._hub._submit(cmd)

    def _closed_done(self, dev: MaxDevice, partner: MaxDevice, cmd: Command) -> None:
        pair = (dev.address, partner.address)
        if cmd.first_sent_at is not None:
            self._note_aired(pair, cmd.sent)
        current = self._sending.get(pair)
        if current is not None and current[0] is cmd:
            del self._sending[pair]
        if cmd.outcome is Outcome.ACKED:
            dev.delivered[partner.serial] = False
            return
        _LOGGER.warning(
            "MAX! %s (%s): window state closed not acknowledged by %s (%s) before the unlink; "
            "it may stay at the window temperature until its window is closed otherwise",
            dev.name or dev.serial, dev.serial, partner.name or partner.serial, partner.serial,
        )

    def check_removals(self) -> None:
        """Remove every device being removed that no real device carries any more (the
        hub calls it after each link outcome and after forgetting unknown partners)."""
        for dev in [d for d in self._hub.devices.values() if d.virtual and d.removing]:
            self._settle(dev)

    def resume_removals(self) -> None:
        """On start: a removal begun before a restart goes on. Operations stored with the
        partners were sent again by the hub; only partners without one get the unlink."""
        for dev in [d for d in self._hub.devices.values() if d.virtual and d.removing]:
            self._unlink_partners(dev, again=False)
        self.check_removals()

    def _carriers(self, dev: MaxDevice) -> list[MaxDevice]:
        """Real devices that may know the address: the link, or any operation naming it
        (a waiting or failed removal included)."""
        return [
            d for d in self._hub.devices.values()
            if not d.virtual and (dev.serial in d.links or d.link_op(dev.serial) is not None)
        ]

    def _unlink_partners(self, dev: MaxDevice, *, again: bool) -> None:
        """Unlink every partner, real ones by radio. `again`: a removal that failed or was
        refused is sent once more (a new request); otherwise a partner with a removal of
        any state is left to it."""
        hub = self._hub
        partners = [d for d in hub.devices.values() if d is not dev and d.serial in dev.links]
        partners += [d for d in self._carriers(dev) if d not in partners]
        for partner in partners:
            op = partner.link_op(dev.serial)
            if not again and op is not None and op["op"] == LINK_REMOVE:
                continue
            try:
                hub._change_link(dev.address, partner.address, LINK_REMOVE)
            except FrameError as err:  # nothing to do on either side, or already on its way
                _LOGGER.debug("MAX! %s: unlink %s: %s", dev.serial, partner.serial, err)

    def _settle(self, dev: MaxDevice) -> bool:
        if self._carriers(dev):
            return False
        self._finish_removal(dev)
        return True

    def _finish_removal(self, dev: MaxDevice) -> None:
        """Gone for good: its own transmissions and state go, so does every link and open
        operation naming it (queued ones are not sent), then Home Assistant hears of it."""
        hub = self._hub
        self._drop_runtime(dev.address)
        for other in list(hub.devices.values()):
            if other is dev:
                continue
            entry = other.link_op(dev.serial)
            if entry is not None:
                hub._cancel_key(hub._link_key(other, entry["address"]))
                hub._link_missed_at.pop((other.address, dev.serial), None)
            if other.forget_partner(dev.serial):
                hub._notify(other)
        if hub.devices.get(dev.address) is dev:
            del hub.devices[dev.address]
        self.removed_serials.add(dev.serial)
        _LOGGER.info("MAX! %s (%s): removed", dev.name or dev.serial, dev.serial)
        hub._safe(hub._on_device_removed, dev)

    def _drop_runtime(self, address: int) -> None:
        """Cancel what the device would still send of its own and forget its runtime state."""
        timer = self._timers.pop(address, None)
        if timer is not None:
            timer.cancel()
        for pair in [p for p in self._sending if p[0] == address]:
            del self._sending[pair]
            self._hub._cancel_key(f"vwin:{pair[0]}:{pair[1]}")
        for pair in [p for p in self._repeat_timers if p[0] == address]:
            self._repeat_timers.pop(pair).cancel()
        for pair in [p for p in self._gap_timers if p[0] == address]:
            self._gap_timers.pop(pair).cancel()
        for state in (self._repeated_at, self._failures, self._aired, self._air_log):
            for pair in [p for p in state if p[0] == address]:
                del state[pair]
        self._over_budget = {pair for pair in self._over_budget if pair[0] != address}
        self._cancel_forward(address)
        self._reports.pop(address, None)
        self._forget_wall(address)

    def ack_payload(self, dev: MaxDevice, frame: Frame) -> bytes:
        """What the virtual device answers to this telegram, computed at send time (once
        per telegram: repeats within the guard time never get here). Never raises.

        A wall thermostat takes a setpoint first, so the answer carries it (otherwise the
        thermostat tries again every minute), and reports mode and target like the real
        one; without a usable target it answers like a contact rather than invent one."""
        try:
            if dev.device_type is DeviceType.WALL_THERMOSTAT:
                return self._wall_ack_payload(dev, frame)
        except Exception:
            _LOGGER.exception("MAX! %s (%s): answer to %s", dev.name or dev.serial, dev.serial, frame)
        return b"\x00"

    def on_frame(self, frame: Frame) -> None:
        """A telegram to a virtual device, after its acknowledgement (Home Assistant hears
        of it only now, the answer must not wait for it)."""
        dev = self.get(frame.dst)
        sender = self._hub.devices.get(frame.src)
        if dev is not None and sender is not None and dev.device_type is DeviceType.WALL_THERMOSTAT:
            self._wall_frame(dev, sender, frame)

    # --- Window contact ---

    def set_window(self, address: int, is_open: bool | None) -> None:
        """New state of the contact's source (None: unavailable). Sent to the linked
        thermostats once it held SC_DEBOUNCE_S, and only where it differs from what
        they were last told."""
        dev = self.get(address)
        if dev is None or dev.device_type is not DeviceType.SHUTTER_CONTACT:
            raise FrameError(f"no virtual window contact at {address:06X}", key="device_unknown")
        timer = self._timers.pop(address, None)
        if timer is not None:
            timer.cancel()
        hub = self._hub
        if is_open is None:
            dev.source_ok = False
            hub._notify(dev)
            for wall in self._walls():
                if self._linked(wall, dev):
                    hub._notify(wall)  # a contact without source counts as closed there
                    self.window_changed(wall)
            return
        dev.source_ok = True
        if dev.window_open is not None and dev.window_open != is_open:
            dev.window_changed_at = hub._now()
        dev.window_open = is_open
        hub._notify(dev)
        for wall in self._walls():
            if self._linked(wall, dev):
                hub._notify(wall)  # its window_open() follows
        if not dev.removing and not self._stopped:
            self._timers[address] = asyncio.get_running_loop().call_later(
                SC_DEBOUNCE_S, self._debounced, address
            )

    def _debounced(self, address: int) -> None:
        self._timers.pop(address, None)
        dev = self.get(address)
        if dev is None:
            return
        for partner in list(self._hub.devices.values()):
            if self._receives(dev, partner):
                self._send_window(dev, partner)
            elif partner.virtual and partner.device_type is DeviceType.WALL_THERMOSTAT and self._linked(partner, dev):
                self.window_changed(partner)  # its room temperature carries the window

    @staticmethod
    def _receives(contact: MaxDevice, partner: MaxDevice) -> bool:
        """A real device that carries the contact as its partner: only it knows our address.
        Virtual wall thermostats read the contact's state directly."""
        return not partner.virtual and contact.serial in partner.links

    def _send_window(
        self, dev: MaxDevice, partner: MaxDevice, *, force: bool = False, repeat: bool = False
    ) -> bool:
        """Queue the current state for this partner unless it already has it or gets it:
        the state on the way counts before the delivered one (a "closed" behind a waiting
        "open" must not be lost). A repeat has a single attempt. True if queued, or held
        until the gap after the last telegram is over."""
        is_open = dev.window_open
        if self._stopped or dev.removing or not dev.source_ok or is_open is None:
            return False
        src, dst = dev.address, partner.address
        pair = (src, dst)
        on_the_way = self._sending.get(pair)
        known = on_the_way[1] if on_the_way is not None else dev.delivered.get(partner.serial)
        if not force and known == is_open:
            return False
        if self._hold_for_gap(dev, partner, on_the_way):
            return True  # goes when the gap is over
        timer = self._repeat_timers.pop(pair, None)
        if timer is not None:
            timer.cancel()  # this one is the attempt
        cmd = Command(
            dst=dst,
            build=lambda counter: build_shutter_contact_state(counter, src, dst, is_open),
            key=f"vwin:{src}:{dst}",
            # A repeat, and any state to a partner whose last one went unacknowledged,
            # gets a single attempt until it acknowledges again.
            retries=0 if repeat or pair in self._failures else None,
        )
        cmd.on_done = lambda _ok: self._window_done(dev, partner, cmd, is_open)
        # Same key: replaces a waiting telegram that never went on air.
        self._sending[pair] = (cmd, is_open)
        self._hub._submit(cmd)
        return True

    def _hold_for_gap(
        self, dev: MaxDevice, partner: MaxDevice, on_the_way: tuple[Command, bool] | None
    ) -> bool:
        """Whether the state must wait for the gap after the last telegram to this partner
        (one on air counts as just sent); then it goes when the gap is over, the latest
        state only. A waiting one that never went out is simply replaced."""
        pair = (dev.address, partner.address)
        if pair in self._gap_timers:
            return True  # the timer sends the latest state
        loop = asyncio.get_running_loop()
        on_air = on_the_way is not None and on_the_way[0].first_sent_at is not None
        last = loop.time() if on_air else self._aired.get(pair)
        if last is None or loop.time() - last >= SC_MIN_GAP_S:
            return self._hold_for_budget(dev, partner)
        delay = SC_MIN_GAP_S - (loop.time() - last)
        _LOGGER.info(
            "MAX! %s (%s): window state to %s waits %.0f s (at least %.0f s between two telegrams)",
            dev.name or dev.serial, dev.serial, partner.serial, delay, SC_MIN_GAP_S,
        )
        self._gap_timers[pair] = loop.call_later(delay, self._gap_over, pair)
        return True

    def _hold_for_budget(self, dev: MaxDevice, partner: MaxDevice) -> bool:
        """Whether the hour's SC_HOUR_MAX telegrams to this partner are on air already;
        then the latest state goes once the oldest of them is an hour old."""
        pair = (dev.address, partner.address)
        now = asyncio.get_running_loop().time()
        log = [t for t in self._air_log.get(pair, []) if now - t < SC_HOUR_S]
        self._air_log[pair] = log
        if len(log) < SC_HOUR_MAX:
            self._over_budget.discard(pair)
            return False
        if pair not in self._over_budget:
            self._over_budget.add(pair)
            _LOGGER.warning(
                "MAX! %s (%s): %d window telegrams to %s within the hour, the next waits for a free slot",
                dev.name or dev.serial, dev.serial, SC_HOUR_MAX, partner.serial,
            )
        self._gap_timers[pair] = asyncio.get_running_loop().call_later(
            log[0] + SC_HOUR_S - now, self._gap_over, pair
        )
        return True

    def _note_aired(self, pair: tuple[int, int], count: int) -> None:
        """`count` transmissions of one command went on air (each costs airtime)."""
        now = asyncio.get_running_loop().time()
        self._aired[pair] = now
        self._air_log.setdefault(pair, []).extend([now] * max(1, count))

    def _gap_over(self, pair: tuple[int, int]) -> None:
        self._gap_timers.pop(pair, None)
        dev, partner = self.get(pair[0]), self._hub.devices.get(pair[1])
        if dev is None or partner is None or not self._receives(dev, partner):
            return
        if pair in self._sending and self._sending[pair][0].first_sent_at is not None:
            # Still on air: after it (its outcome decides).
            self._gap_timers[pair] = asyncio.get_running_loop().call_later(SC_MIN_GAP_S, self._gap_over, pair)
            return
        # After a failure it is a repeat: a single attempt.
        self._send_window(dev, partner, repeat=pair in self._failures)

    def _window_done(self, dev: MaxDevice, partner: MaxDevice, cmd: Command, is_open: bool) -> None:
        if self.get(dev.address) is not dev:
            return  # removed while it was on air
        pair = (dev.address, partner.address)
        if cmd.first_sent_at is not None:
            self._note_aired(pair, cmd.sent)
        current = self._sending.get(pair)
        if current is not None and current[0] is cmd:
            del self._sending[pair]
        name = dev.name or dev.serial
        if cmd.outcome is Outcome.ACKED:
            dev.delivered[partner.serial] = is_open
            self._failures.pop(pair, None)
            self._repeated_at.pop(pair, None)
            self._cancel_repeat(pair)
            self._hub._notify(dev)
            if dev.window_open != is_open and dev.address not in self._timers:
                # Changed while this one was on the way and nothing newer was queued.
                self._send_window(dev, partner)
            return
        if current is None or current[0] is not cmd:
            return  # a newer state is on its way: its outcome counts
        failures = self._failures[pair] = self._failures.get(pair, 0) + 1
        delay = SC_REPEAT_MIN_S if failures < SC_WARN_FAILURES else SC_REPEAT_SLOW_S
        if failures == SC_WARN_FAILURES:
            _LOGGER.warning(
                "MAX! %s (%s): window state not acknowledged by %s %d times in a row, "
                "repeated every %.0f min from now on",
                name, dev.serial, partner.serial, failures, SC_REPEAT_SLOW_S / 60,
            )
        else:
            _LOGGER.info(
                "MAX! %s (%s): window state not acknowledged by %s, again in %.0f min or with its next telegram",
                name, dev.serial, partner.serial, delay / 60,
            )
        if not self._stopped and not dev.removing:
            self._cancel_repeat(pair)
            self._repeat_timers[pair] = asyncio.get_running_loop().call_later(delay, self._repeat_due, pair)

    def _cancel_repeat(self, pair: tuple[int, int]) -> None:
        timer = self._repeat_timers.pop(pair, None)
        if timer is not None:
            timer.cancel()

    def _repeat_due(self, pair: tuple[int, int]) -> None:
        """The timer's repeat of an undelivered state (or one on reconnect): one attempt."""
        self._cancel_repeat(pair)
        dev, partner = self.get(pair[0]), self._hub.devices.get(pair[1])
        if dev is None or partner is None or not self._receives(dev, partner) or pair in self._sending:
            return
        if self._send_window(dev, partner, repeat=True):
            self._repeated_at[pair] = self._hub._now()

    def reconnected(self) -> None:
        """A radio module is back: every undelivered state gets one attempt now."""
        for pair in list(self._failures):
            self._repeat_due(pair)

    def partner_heard(self, partner: MaxDevice) -> None:
        """A real device sent its status: repeat what it has not acknowledged yet (not
        while a change is being debounced or a telegram to it is still on the way, and
        at most every SC_REPEAT_MIN_S per pair)."""
        if partner.virtual:
            return
        now = self._hub._now()
        for dev in self._contacts():
            pair = (dev.address, partner.address)
            last = self._repeated_at.get(pair)
            if (
                self._receives(dev, partner)
                and dev.address not in self._timers
                and pair not in self._sending
                and pair not in self._gap_timers
                and (last is None or now - last >= SC_REPEAT_MIN_S)
                and self._send_window(dev, partner, repeat=True)
            ):
                self._repeated_at[pair] = now

    def link_committed(self, dev: MaxDevice, partner_serial: str, op: str, *, forced: bool = False) -> None:
        """A device took a link change with `partner_serial` (a real one by its
        acknowledgement, a virtual one at once): a newly linked thermostat learns the
        contact's current state, a removed one is forgotten; a virtual wall thermostat
        and its thermostats agree on the room's setpoint."""
        partner = next((d for d in self._hub.devices.values() if d.serial == partner_serial), None)
        if partner is None:
            return
        self._wall_link_committed(dev, partner, op, forced=forced)
        if dev.virtual:
            # A virtual partner reads the contact directly: nothing on air.
            if partner.device_type is DeviceType.SHUTTER_CONTACT and dev.device_type is DeviceType.WALL_THERMOSTAT:
                self._hub._notify(dev)
                self.window_changed(dev)
            return
        contact = partner if partner.virtual and partner.device_type is DeviceType.SHUTTER_CONTACT else None
        if contact is None:
            return
        if op == LINK_REMOVE:
            contact.delivered.pop(dev.serial, None)
            pair = (contact.address, dev.address)
            self._cancel_repeat(pair)
            gap = self._gap_timers.pop(pair, None)
            if gap is not None:
                gap.cancel()
            self._failures.pop(pair, None)
            self._air_log.pop(pair, None)
            self._over_budget.discard(pair)
        elif contact.address not in self._timers:
            self._send_window(contact, dev, force=True)

    def _contacts(self) -> list[MaxDevice]:
        return [
            d for d in self._hub.devices.values()
            if d.virtual and d.device_type is DeviceType.SHUTTER_CONTACT
        ]
