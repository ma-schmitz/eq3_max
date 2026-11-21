"""Target temperature from a stored week program."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from .devices import WEEKDAYS
from .messages import parse_until


def program_target(week_profile: Mapping[str, list[dict[str, Any]]], when: datetime) -> float | None:
    """Target of the week program at `when`; None if nothing is stored for that weekday."""
    points = week_profile.get(WEEKDAYS[(when.weekday() + 2) % 7])
    if not points:
        return None
    minutes = when.hour * 60 + when.minute
    for point in points:
        if minutes < parse_until(point["until"]):
            return float(point["temperature"])
    return float(points[-1]["temperature"])


def next_switch(week_profile: Mapping[str, list[dict[str, Any]]], when: datetime) -> datetime | None:
    """The next moment after `when` at which the program's target changes value (its next
    switch point that matters); None if it never does within a week."""
    current = program_target(week_profile, when)
    day = when.replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(8):
        start = day + timedelta(days=offset)
        points = week_profile.get(WEEKDAYS[(start.weekday() + 2) % 7]) or []
        # The day's start and every point's end are where the target may change.
        moments = [start] + [start + timedelta(minutes=parse_until(p["until"])) for p in points]
        for moment in moments:
            if moment > when and program_target(week_profile, moment) != current:
                return moment
    return None


def override_over(
    week_profile: Mapping[str, list[dict[str, Any]]], since: datetime, now: datetime, fallback_s: float
) -> bool:
    """Whether a setpoint changed in automatic mode at `since` has ended by `now`: at the
    program's next switch point after `since`. Without a program for that day, and for a
    program that never changes its target (next_switch is None), after `fallback_s`."""
    if program_target(week_profile, since) is not None:
        switch = next_switch(week_profile, since)
        if switch is not None:
            return now >= switch
    return (now - since).total_seconds() > fallback_s
