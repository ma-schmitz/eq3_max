import pytest

from custom_components.eq3_max.protocol import virtual
from custom_components.eq3_max.protocol.hub import MaxHub

from .fakes import FakeCul, until
from .hubkit import CENTRAL, LocalClock, Recorder, devices


@pytest.fixture(autouse=True)
def short_window_gap(monkeypatch):
    """Two window telegrams to one thermostat are a minute apart; tests that do not look
    at the gap send their changes at once."""
    monkeypatch.setattr(virtual, "SC_MIN_GAP_S", 0.05)


@pytest.fixture
async def hub():
    cul = FakeCul()
    rec = Recorder()
    h = MaxHub(
        "/dev/serial/by-path/x", CENTRAL, devices(),
        on_update=rec.updates.append,
        on_button=lambda d, t: rec.buttons.append((d.address, t)),
        on_device_added=rec.added.append,
        on_device_removed=rec.removed.append,
        on_problem=rec.problems.append,
        open_connection=cul.open,
        ack_timeout=0.05,
        now=lambda: 1_700_000_000.0,
        local_now=LocalClock(),
    )
    await h.start()
    await until(lambda: h.connected)
    yield h, cul, rec
    await h.stop()
