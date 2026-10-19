import asyncio

import pytest

from custom_components.eq3_max.protocol.transport import CulTransport

from .fakes import FakeClock, FakeCul, until

ADDR = 0xC0FFEE


def make(cul, clock=None, **kw):
    events = {"frames": [], "lovf": 0, "conn": [], "problems": []}
    t = CulTransport(
        "/dev/serial/by-path/x",
        ADDR,
        on_frame=events["frames"].append,
        on_lovf=lambda: events.__setitem__("lovf", events["lovf"] + 1),
        on_connection=events["conn"].append,
        on_problem=events["problems"].append,
        open_connection=cul.open,
        clock=clock or FakeClock(),
        **kw,
    )
    return t, events


async def test_init_sequence_and_version():
    cul = FakeCul()
    t, ev = make(cul)
    await t.start()
    await until(lambda: t.connected)
    assert cul.written == ["V", "X21", "Zr", "ZaC0FFEE"]
    assert t.version == "V 1.66 nanoCUL868"
    assert ev["conn"] == [True]
    await t.stop()


async def test_frames_and_lovf_are_dispatched_other_lines_ignored():
    cul = FakeCul()
    t, ev = make(cul)
    await t.start()
    await until(lambda: t.connected)
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    cul.feed("LOVF")
    cul.feed("something else")
    await until(lambda: ev["lovf"] == 1)
    assert ev["frames"] == ["Z0EF20202A1B005C0FFEE0001193009"]
    await t.stop()


async def test_write_line_appends_newline_and_fails_when_disconnected():
    cul = FakeCul()
    t, _ = make(cul)
    with pytest.raises(ConnectionError):
        await t.write_line("Zs00")
    await t.start()
    await until(lambda: t.connected)
    await t.write_line("Zs0B010040C0FFEEA1B005006A")
    assert cul.written[-1] == "Zs0B010040C0FFEEA1B005006A"
    await t.stop()


async def test_no_version_answer_means_not_connected_and_retry():
    cul = FakeCul()
    cul.answer_version = False
    t, ev = make(cul, version_timeout=0.02, reconnect_delay=0.01)
    await t.start()
    await until(lambda: cul.opened >= 2)
    assert not t.connected
    await t.stop()


async def test_unplug_reconnects():
    cul = FakeCul()
    t, ev = make(cul, reconnect_delay=0.01)
    await t.start()
    await until(lambda: t.connected)
    cul.unplug()
    await until(lambda: cul.opened == 2 and t.connected)
    assert ev["conn"] == [True, False, True]
    await t.stop()


async def test_port_lost_problem_after_timeout():
    cul = FakeCul()
    cul.fail_open = True
    clock = FakeClock()
    t, ev = make(cul, clock=clock, reconnect_delay=0.01, problem_after=900.0)
    await t.start()
    await asyncio.sleep(0.03)
    assert ev["problems"] == []
    clock.t += 901
    await until(lambda: ev["problems"] == ["port_lost"])
    await asyncio.sleep(0.03)
    assert ev["problems"] == ["port_lost"]
    await t.stop()


async def test_deaf_stick_is_reopened_and_reported_on_second_time():
    cul = FakeCul()
    clock = FakeClock()
    t, ev = make(cul, clock=clock, silence_timeout=600.0, check_interval=0.005)
    await t.start()
    await until(lambda: t.connected)
    await t.write_line("Zs0B010040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 2 and t.connected)
    assert ev["problems"] == []
    await t.write_line("Zs0B020040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: ev["problems"] == ["stick_deaf"])
    await t.stop()


async def test_received_frame_resets_deaf_counter():
    cul = FakeCul()
    clock = FakeClock()
    t, ev = make(cul, clock=clock, silence_timeout=600.0, check_interval=0.005)
    await t.start()
    await until(lambda: t.connected)
    await t.write_line("Zs0B010040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 2 and t.connected)
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    await until(lambda: len(ev["frames"]) == 1)
    await t.write_line("Zs0B020040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 3 and t.connected)
    assert ev["problems"] == []
    await t.stop()


async def test_faulty_frame_callback_does_not_kill_reading():
    cul = FakeCul()
    frames: list[str] = []
    calls = 0

    def on_frame(text):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("callback bug")
        frames.append(text)

    t = CulTransport(
        "/dev/serial/by-path/x",
        ADDR,
        on_frame=on_frame,
        on_lovf=lambda: None,
        on_connection=lambda _c: None,
        on_problem=lambda _p: None,
        open_connection=cul.open,
        clock=FakeClock(),
    )
    await t.start()
    await until(lambda: t.connected)
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    await until(lambda: len(frames) == 1)
    assert t.connected
    assert cul.opened == 1
    await t.stop()


async def test_overlong_line_reconnects_instead_of_dying():
    cul = FakeCul()
    t, _ = make(cul, reconnect_delay=0.01)
    await t.start()
    await until(lambda: t.connected)
    cul.feed("A" * 70000)
    await until(lambda: cul.opened == 2 and t.connected)
    await t.stop()


async def test_stick_deaf_reported_once_across_three_deaf_cycles():
    cul = FakeCul()
    clock = FakeClock()
    t, ev = make(cul, clock=clock, silence_timeout=600.0, check_interval=0.005)
    await t.start()
    await until(lambda: t.connected)
    await t.write_line("Zs0B010040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 2 and t.connected)
    await t.write_line("Zs0B020040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 3 and t.connected)
    assert ev["problems"] == ["stick_deaf"]
    await t.write_line("Zs0B030040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 4 and t.connected)
    assert ev["problems"] == ["stick_deaf"]
    await t.stop()


# --- final fix wave ---

async def test_wait_connected_blocks_until_handshake_and_again_after_unplug():
    cul = FakeCul()
    cul.fail_open = True
    t, ev = make(cul, reconnect_delay=0.01)
    await t.start()
    waiter = asyncio.create_task(t.wait_connected())
    await asyncio.sleep(0.05)
    assert not waiter.done()
    cul.fail_open = False
    await asyncio.wait_for(waiter, 1.0)
    assert t.connected
    cul.fail_open = True
    cul.unplug()
    await until(lambda: not t.connected)
    waiter = asyncio.create_task(t.wait_connected())
    await asyncio.sleep(0.05)
    assert not waiter.done()
    cul.fail_open = False
    await asyncio.wait_for(waiter, 1.0)
    await t.stop()


# --- Fix: schnelles Wiederoeffnen bei tauben Stick ---

async def test_last_frame_rx_tracks_z_frames_across_reconnects():
    cul = FakeCul()
    clock = FakeClock()
    t, ev = make(cul, clock=clock, reconnect_delay=0.01)
    await t.start()
    await until(lambda: t.connected)
    assert t.last_frame_rx is None
    clock.t = 1234.0
    cul.feed("LOVF")
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    await until(lambda: len(ev["frames"]) == 1)
    assert t.last_frame_rx == 1234.0
    cul.unplug()
    await until(lambda: cul.opened == 2 and t.connected)
    assert t.last_frame_rx == 1234.0
    await t.stop()


async def test_request_reopen_once_per_quiet_episode_and_never_stick_deaf():
    cul = FakeCul()
    t, ev = make(cul, reconnect_delay=60.0)
    await t.start()
    await until(lambda: t.connected)
    t.request_reopen()
    assert not t.connected
    await until(lambda: cul.opened == 2 and t.connected)
    assert ev["conn"] == [True, False, True]
    t.request_reopen()
    t.request_reopen()
    await asyncio.sleep(0.03)
    assert cul.opened == 2 and t.connected
    assert ev["problems"] == []
    cul.feed("Z0EF20202A1B005C0FFEE0001193009")
    await until(lambda: len(ev["frames"]) == 1)
    t.request_reopen()
    await until(lambda: cul.opened == 3 and t.connected)
    assert ev["problems"] == []
    await t.stop()


async def test_fast_reopen_does_not_count_toward_watchdog_stick_deaf():
    cul = FakeCul()
    clock = FakeClock()
    t, ev = make(cul, clock=clock, silence_timeout=600.0, check_interval=0.005)
    await t.start()
    await until(lambda: t.connected)
    t.request_reopen()
    await until(lambda: cul.opened == 2 and t.connected)
    await t.write_line("Zs0B010040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: cul.opened == 3 and t.connected)
    assert ev["problems"] == []
    await t.write_line("Zs0B020040C0FFEEA1B005006A")
    clock.t += 601
    await until(lambda: ev["problems"] == ["stick_deaf"])
    await t.stop()


async def test_request_reopen_when_disconnected_does_nothing():
    cul = FakeCul()
    cul.fail_open = True
    t, ev = make(cul, reconnect_delay=60.0)
    await t.start()
    await asyncio.sleep(0.02)
    t.request_reopen()
    await asyncio.sleep(0.02)
    assert ev["problems"] == [] and ev["conn"] == []
    await t.stop()
