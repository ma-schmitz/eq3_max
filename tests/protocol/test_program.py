from datetime import datetime

from custom_components.eq3_max.protocol.program import program_target

PROFILE = {"Montag": [{"temperature": 17.0, "until": "06:00"}, {"temperature": 21.0, "until": "22:00"}, {"temperature": 17.0, "until": "24:00"}]}


def test_program_target():
    monday = datetime(2026, 11, 23)  # ein Montag
    assert program_target(PROFILE, monday.replace(hour=5, minute=59)) == 17.0
    assert program_target(PROFILE, monday.replace(hour=6, minute=0)) == 21.0
    assert program_target(PROFILE, monday.replace(hour=23)) == 17.0
    assert program_target(PROFILE, datetime(2026, 11, 24, 12)) is None  # Dienstag fehlt


def test_next_switch_is_where_the_target_changes():
    from custom_components.eq3_max.protocol.program import next_switch

    monday = datetime(2026, 11, 23)
    assert next_switch(PROFILE, monday.replace(hour=5)) == monday.replace(hour=6)
    assert next_switch(PROFILE, monday.replace(hour=6)) == monday.replace(hour=22)
    # 22:00 to 24:00 at 17, then Tuesday has no program (None): a change at midnight.
    assert next_switch(PROFILE, monday.replace(hour=23)) == datetime(2026, 11, 24)
    same = {"Montag": [{"temperature": 21.0, "until": "12:00"}, {"temperature": 21.0, "until": "24:00"}]}
    assert next_switch(same, monday.replace(hour=8)) == datetime(2026, 11, 24)   # Dienstag ohne Programm
    every_day = {day: [{"temperature": 20.0, "until": "24:00"}] for day in
                 ("Samstag", "Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag")}
    assert next_switch(every_day, monday.replace(hour=8)) is None


def test_override_over_follows_the_switch_point_or_the_fallback():
    from custom_components.eq3_max.protocol.devices import WEEKDAYS
    from custom_components.eq3_max.protocol.program import override_over

    fallback = 900.0
    # Weekday rollover: Friday 23:00 (17 until midnight), Saturday 17 until 06:00, then 21.
    friday, saturday = datetime(2026, 11, 20, 23), datetime(2026, 11, 21)
    program = {"Freitag": [{"temperature": 21.0, "until": "22:00"}, {"temperature": 17.0, "until": "24:00"}],
               "Samstag": [{"temperature": 17.0, "until": "06:00"}, {"temperature": 21.0, "until": "24:00"}]}
    assert not override_over(program, friday, saturday.replace(hour=5, minute=59), fallback)
    assert override_over(program, friday, saturday.replace(hour=6), fallback)
    # A point ending at 24:00 switches at midnight.
    midnight = {"Freitag": [{"temperature": 21.0, "until": "24:00"}], "Samstag": [{"temperature": 17.0, "until": "24:00"}]}
    assert not override_over(midnight, friday, friday.replace(minute=59), fallback)
    assert override_over(midnight, friday, saturday, fallback)
    # A constant program never switches (next_switch is None): the fallback applies.
    constant = {day: [{"temperature": 20.0, "until": "24:00"}] for day in WEEKDAYS}
    assert not override_over(constant, friday, friday.replace(minute=15), fallback)
    assert override_over(constant, friday, friday.replace(minute=15, second=1), fallback)
    # No program: the fallback.
    assert not override_over({}, friday, friday.replace(minute=15), fallback)
    assert override_over({}, friday, friday.replace(minute=16), fallback)
