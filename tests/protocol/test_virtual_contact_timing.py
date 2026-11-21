"""Virtual window contact: an undelivered state is repeated by a timer (with back-off and on
reconnect), and two telegrams to one thermostat keep a minimum gap."""

import asyncio
import logging

import pytest

from custom_components.eq3_max.protocol import virtual
from custom_components.eq3_max.protocol.messages import MsgType

from .fakes import line, until
from .hubkit import HT, VC, linked_contact, sent


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(virtual, "SC_DEBOUNCE_S", 0.01)


def contact_lines(cul):
    return [l for l in sent(cul) if l[8:10] == "30"]


def idle(h):
    return h._scheduler_for(HT).pending() == []


def ack_last(cul):
    last = contact_lines(cul)[-1]
    cul.feed(line(int(last[4:6], 16), 0x02, MsgType.ACK, HT, VC, 0, "01190018"))


async def failed_once(h, cul):
    linked_contact(h)
    h.virtual.set_window(VC, True)
    await until(lambda: len(contact_lines(cul)) == 4 and idle(h), timeout=5)  # first send: normal retries
    await until(lambda: (VC, HT) in h.virtual._failures)


# --- I3: repeated by a timer ---


async def test_undelivered_state_is_repeated_by_a_timer_with_back_off(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_REPEAT_MIN_S", 0.2)
    monkeypatch.setattr(virtual, "SC_REPEAT_SLOW_S", 0.8)
    h, cul, _ = hub
    await failed_once(h, cul)                                       # failure 1
    loop = asyncio.get_running_loop()
    times = []
    for count in (5, 6, 7):                                         # failures 2, 3, 4: one attempt each
        await until(lambda: len(contact_lines(cul)) == count, timeout=3)
        times.append(loop.time())
        await until(lambda: idle(h))
    assert times[1] - times[0] < 0.6                                # after failure 2: 0.2 s
    assert times[2] - times[1] >= 0.75                              # after failure 3: the slow repeat
    assert all(l.endswith("0012") for l in contact_lines(cul))


async def test_timer_repeat_stops_on_delivery(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_REPEAT_MIN_S", 0.2)
    h, cul, _ = hub
    await failed_once(h, cul)
    await until(lambda: len(contact_lines(cul)) == 5)
    ack_last(cul)
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True})
    await asyncio.sleep(0.5)
    assert len(contact_lines(cul)) == 5 and not h.virtual._repeat_timers


async def test_timer_repeat_stops_on_unlink_removal_and_stop(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_REPEAT_MIN_S", 0.2)
    h, cul, _ = hub
    await failed_once(h, cul)
    assert (VC, HT) in h.virtual._repeat_timers
    h.virtual.link_committed(h.devices[HT], h.devices[VC].serial, virtual.LINK_REMOVE)
    assert not h.virtual._repeat_timers
    h.virtual._failures[(VC, HT)] = 1
    h.virtual._repeat_timers[(VC, HT)] = asyncio.get_running_loop().call_later(0.2, h.virtual._repeat_due, (VC, HT))
    h.virtual._drop_runtime(VC)                                     # removal
    assert not h.virtual._repeat_timers
    h.virtual._repeat_timers[(VC, HT)] = asyncio.get_running_loop().call_later(0.2, h.virtual._repeat_due, (VC, HT))
    await h.stop()
    assert not h.virtual._repeat_timers
    await asyncio.sleep(0.3)
    assert len(contact_lines(cul)) == 4


async def test_reconnect_gives_an_undelivered_state_one_attempt(hub):
    h, cul, _ = hub
    await failed_once(h, cul)                                       # the timer waits 5 min
    h._on_connection(True)
    await until(lambda: len(contact_lines(cul)) == 5)
    await until(lambda: idle(h))
    await asyncio.sleep(0.1)
    assert len(contact_lines(cul)) == 5


async def test_no_repeat_and_no_timer_after_stop(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_REPEAT_MIN_S", 0.1)
    h, cul, _ = hub
    linked_contact(h)
    await h.stop()
    h.virtual.set_window(VC, True)
    assert not h.virtual._timers
    h.virtual.partner_heard(h.devices[HT])
    h.virtual.tick()
    assert not h.virtual._sending and not h.virtual._repeat_timers


# --- I4: a gap between two telegrams to one thermostat ---


async def test_a_change_within_the_gap_goes_when_it_is_over(hub, monkeypatch, caplog):
    monkeypatch.setattr(virtual, "SC_MIN_GAP_S", 0.5)
    caplog.set_level(logging.INFO)
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    loop = asyncio.get_running_loop()
    h.virtual.set_window(VC, True)
    await until(lambda: len(contact_lines(cul)) == 1)
    first = loop.time()
    ack_last(cul)
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True})
    for state in (False, True, False):                              # a busy door
        h.virtual.set_window(VC, state)
        await asyncio.sleep(0.03)
    await asyncio.sleep(0.1)
    assert len(contact_lines(cul)) == 1                             # held
    await until(lambda: len(contact_lines(cul)) == 2, timeout=2)
    assert loop.time() - first >= 0.45
    assert contact_lines(cul)[1].endswith("0010")                   # only the latest state
    held = [r for r in caplog.records if "waits" in r.getMessage() and r.levelname == "INFO"]
    assert len(held) == 1


async def test_a_change_back_within_the_gap_sends_nothing(hub, monkeypatch):
    monkeypatch.setattr(virtual, "SC_MIN_GAP_S", 0.3)
    h, cul, _ = hub
    linked_contact(h, delivered=False)
    h.virtual.set_window(VC, True)
    await until(lambda: len(contact_lines(cul)) == 1)
    ack_last(cul)
    await until(lambda: h.devices[VC].delivered == {h.devices[HT].serial: True})
    h.virtual.set_window(VC, False)
    await asyncio.sleep(0.05)
    h.virtual.set_window(VC, True)                                  # back to what it has
    await asyncio.sleep(0.5)
    assert len(contact_lines(cul)) == 1 and not h.virtual._gap_timers


# --- F5: hourly budget per thermostat ---


async def test_at_most_the_hours_budget_goes_to_one_thermostat(hub, monkeypatch, caplog):
    monkeypatch.setattr(virtual, "SC_HOUR_MAX", 2)
    monkeypatch.setattr(virtual, "SC_HOUR_S", 0.8)
    caplog.set_level(logging.WARNING)
    h, cul, _ = hub; linked_contact(h, delivered=False)
    loop = asyncio.get_running_loop()
    start = loop.time()
    for count, state in ((1, True), (2, False)):
        h.virtual.set_window(VC, state)
        await until(lambda c=count: len(contact_lines(cul)) == c)
        ack_last(cul)
        await until(lambda: idle(h) and not h.virtual._sending)
    h.virtual.set_window(VC, True)                                  # third within the "hour"
    h.virtual.set_window(VC, False)
    h.virtual.set_window(VC, True)
    await asyncio.sleep(0.3)
    assert len(contact_lines(cul)) == 2
    await until(lambda: len(contact_lines(cul)) == 3, timeout=3)
    assert loop.time() - start >= 0.75 and contact_lines(cul)[-1].endswith("0012")   # the latest: open
    warnings = [r for r in caplog.records if "within the hour" in r.getMessage()]
    assert len(warnings) == 1


async def test_the_hours_budget_counts_every_transmission(hub, monkeypatch):
    """An unreachable thermostat, a contact changing over and over within one "hour": at
    most SC_HOUR_MAX telegrams on air towards it, retries included; after a failure a
    change gets a single attempt."""
    monkeypatch.setattr(virtual, "SC_HOUR_S", 1.5)
    monkeypatch.setattr(virtual, "SC_REPEAT_MIN_S", 100.0)
    h, cul, _ = hub; linked_contact(h, delivered=False)
    loop = asyncio.get_running_loop()
    end = loop.time() + 1.4
    state = False
    while loop.time() < end:
        state = not state
        h.virtual.set_window(VC, state)
        await asyncio.sleep(0.1)
    assert len(contact_lines(cul)) <= virtual.SC_HOUR_MAX
    assert len(contact_lines(cul)) > 4                                         # nach dem ersten nur je ein Versuch


async def test_unlink_forgets_the_budget(hub, monkeypatch):
    h, cul, _ = hub; dev = linked_contact(h, delivered=False)
    pair = (VC, HT)
    h.virtual._air_log[pair] = [asyncio.get_running_loop().time()] * 12
    h.virtual._over_budget.add(pair)
    h.devices[HT].links.remove(dev.serial)
    h.virtual.link_committed(h.devices[HT], dev.serial, "remove")
    assert pair not in h.virtual._air_log and pair not in h.virtual._over_budget
