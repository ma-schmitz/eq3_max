"""Radio modules of an entry: the main one (connection keys at the top of the entry
data, as before) and any number of extra ones under "radios", all with the entry's
central address. Devices name their module by id ("" = main)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .connection import connection_target, connection_type
from .const import CONF_CONNECTION, CONF_HOST, CONF_NAME, CONF_PORT, CONF_RADIO_NEXT, CONF_RADIOS, MAIN_RADIO_NAME
from .protocol.hub import MAIN_RADIO

CONNECTION_KEYS = (CONF_CONNECTION, CONF_HOST, CONF_PORT)


def extra_radios(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in data.get(CONF_RADIOS) or []]


def radio_items(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """All modules, main first: id, name and the connection keys."""
    main = {key: data[key] for key in CONNECTION_KEYS if key in data}
    return [{"id": MAIN_RADIO, CONF_NAME: MAIN_RADIO_NAME, **main}, *extra_radios(data)]


def radio_names(data: Mapping[str, Any]) -> dict[str, str]:
    return {item["id"]: item[CONF_NAME] for item in radio_items(data)}


def describe(item: Mapping[str, Any]) -> dict[str, str]:
    return {"connection": connection_type(item), "target": connection_target(item)}


def new_radio_id(data: Mapping[str, Any]) -> tuple[str, int]:
    """Id for the next extra module (r2, r3, ...) and the counter to store. Ids are
    never reused: a removed module's id may still sit in stored state."""
    used = {item["id"] for item in extra_radios(data)}
    number = next_radio_number(data)
    while f"r{number}" in used:
        number += 1
    return f"r{number}", number + 1


def next_radio_number(data: Mapping[str, Any], *also: str) -> int:
    """Lowest number above every id ever handed out (stored counter, current ids and
    the given ones, e.g. a module being removed)."""
    numbers = [int(data.get(CONF_RADIO_NEXT, 2)), 2]
    for radio_id in [*(item["id"] for item in extra_radios(data)), *also]:
        if radio_id.startswith("r") and radio_id[1:].isdigit():
            numbers.append(int(radio_id[1:]) + 1)
    return max(numbers)


def radio_identifier(address_hex: str, radio: str) -> str:
    """Device registry identifier of an extra radio module."""
    return f"{address_hex}:{radio}"
