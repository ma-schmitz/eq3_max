"""Shared table of the configuration values (entities and panel)."""

from __future__ import annotations

import pytest

from custom_components.eq3_max.config_defs import (
    CONFIG_LABELS,
    OPTION_VALUES,
    RANGES,
    config_meta,
    validate_config_value,
)
from custom_components.eq3_max.migration import SELECT_CONFIG_KEYS
from custom_components.eq3_max.protocol.devices import FACTORY_CONFIG


def test_every_config_key_is_number_or_select():
    assert set(OPTION_VALUES) == set(SELECT_CONFIG_KEYS)
    assert set(RANGES) | set(OPTION_VALUES) == set(FACTORY_CONFIG) == set(CONFIG_LABELS)
    for key, value in FACTORY_CONFIG.items():
        assert validate_config_value(key, value) == value


def test_config_meta_number_and_select():
    assert config_meta("offset") == {
        "key": "offset", "label": "Temperatur-Offset", "type": "number",
        "min": -3.5, "max": 3.5, "step": 0.5, "unit": "K",
    }
    meta = config_meta("boost_dauer")
    assert meta["type"] == "select"
    assert meta["options"][1] == {"value": 5, "label": "5 min"}
    assert config_meta("entkalkung_tag")["options"][0] == {"value": "Samstag", "label": "saturday"}


@pytest.mark.parametrize(
    "key,value,expected",
    [("komfort", "22.5", 22.5), ("fenster_dauer", 20.0, 20), ("boost_dauer", "10 min", 10), ("boost_dauer", 10, 10),
     ("entkalkung_stunde", 23, 23), ("offset", -3.5, -3.5)],
)
def test_validate_accepts_grid_values(key, value, expected):
    result = validate_config_value(key, value)
    assert result == expected and type(result) is type(expected)


@pytest.mark.parametrize(
    "key,value,translation_key,placeholders",
    [
        ("komfort", 22.3, "config_value_range", {"low": "4.5", "high": "30.5", "step": "0.5"}),
        ("fenster_dauer", 7, "config_value_range", {"low": "0", "high": "60", "step": "5"}),
        ("boost_ventil", True, "config_value_range", {"low": "0", "high": "100", "step": "5"}),
        ("eco", "warm", "config_not_a_number", {"value": "warm"}),
        ("boost_dauer", 45, "option_invalid", {"option": "45"}),
        ("bogus", 1, "config_key_unknown", {"key": "bogus"}),
    ],
)
def test_validate_rejects_with_translated_error(key, value, translation_key, placeholders):
    from homeassistant.exceptions import ServiceValidationError

    with pytest.raises(ServiceValidationError) as exc:
        validate_config_value(key, value)
    assert exc.value.translation_key == translation_key
    assert exc.value.translation_placeholders == placeholders
