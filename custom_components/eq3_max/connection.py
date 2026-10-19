"""Connection to the CUL from the entry data: USB stick or network (TCP).

Entries from before the network option carry no "connection" key: they are USB.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import CONF_CONNECTION, CONF_HOST, CONF_PORT, CONNECTION_NETWORK, CONNECTION_USB
from .protocol.transport import OpenConnection, tcp_opener


def connection_type(data: Mapping[str, Any]) -> str:
    return data.get(CONF_CONNECTION, CONNECTION_USB)


def connection_target(data: Mapping[str, Any]) -> str:
    """Serial path (USB) or "host:port" (network), for the hub, logs and diagnostics."""
    if connection_type(data) == CONNECTION_NETWORK:
        return f"{data[CONF_HOST]}:{int(data[CONF_PORT])}"
    return data[CONF_PORT]


def hub_connection(data: Mapping[str, Any]) -> tuple[str, OpenConnection | None]:
    """Target and opener for MaxHub; None keeps the transport's serial default."""
    if connection_type(data) == CONNECTION_NETWORK:
        return connection_target(data), tcp_opener(data[CONF_HOST], int(data[CONF_PORT]))
    return data[CONF_PORT], None
