"""Diagnostics for eq3_max."""

from __future__ import annotations

from typing import Any

from .connection import connection_target, connection_type
from .radios import describe, radio_items


async def async_get_config_entry_diagnostics(hass, entry) -> dict[str, Any]:
    hub = entry.runtime_data.hub
    return {
        "connection": {"type": connection_type(entry.data), "target": connection_target(entry.data)},
        "version": hub.version,
        "connected": hub.connected,
        "airtime_last_hour": hub.airtime_last_hour,
        "queue_length": hub.queue_length,
        "radios": [{**describe(item), "id": item["id"], "name": item["name"]} for item in radio_items(entry.data)],
        "radio_status": hub.radio_status(),
        "devices": {str(a): d.to_dict() for a, d in hub.devices.items()},
        "raw_history": {str(a): list(lines) for a, lines in hub.raw_history.items()},
    }
