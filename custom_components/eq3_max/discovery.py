"""Search the local network for culfw modules (flashed MAX! Cube, CUN).

a-culfw does not announce itself (no mDNS in the Cube build, no UDP discovery, no host
name in its DHCP request), but it listens on TCP 2323 and answers "V" with its version.
So the search asks every address of Home Assistant's own subnets.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
from collections.abc import Awaitable, Callable, Collection, Iterable
from dataclasses import dataclass
from typing import Any

from homeassistant.components import network
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NETWORK_PORT
from .protocol.transport import open_tcp

_LOGGER = logging.getLogger(__name__)

# Larger networks are cut to the /24 around Home Assistant's own address.
MIN_PREFIX = 24
CONNECT_TIMEOUT_S = 1.0
ANSWER_TIMEOUT_S = 2.0
CONCURRENCY = 64


@dataclass(frozen=True)
class Found:
    host: str
    port: int
    version: str

    @property
    def target(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def label(self) -> str:
        return f"{self.host} – {self.version}"


def candidate_hosts(adapters: Iterable[dict[str, Any]]) -> list[str]:
    """Host addresses of the enabled adapters' IPv4 subnets, without the own addresses."""
    own: set[ipaddress.IPv4Address] = set()
    hosts: set[ipaddress.IPv4Address] = set()
    for adapter in adapters:
        if not adapter.get("enabled"):
            continue
        for item in adapter.get("ipv4") or []:
            try:
                address = ipaddress.IPv4Address(item["address"])
                prefix = max(int(item["network_prefix"]), MIN_PREFIX)
                net = ipaddress.IPv4Network((address, prefix), strict=False)
            except (KeyError, ValueError):
                continue
            if address.is_loopback or address.is_link_local:
                continue
            own.add(address)
            hosts.update(net.hosts())
    return [str(host) for host in sorted(hosts - own)]


async def probe_version(
    host: str, port: int, *, connect_timeout: float = CONNECT_TIMEOUT_S, answer_timeout: float = ANSWER_TIMEOUT_S
) -> str | None:
    """culfw's answer to "V" ("V 1.26.08 a-culfw CUBE"), None if nothing like it comes."""
    try:
        reader, writer = await open_tcp(host, port, connect_timeout=connect_timeout)
    except (OSError, TimeoutError, ValueError, UnicodeError):
        return None
    loop = asyncio.get_running_loop()
    try:
        writer.write(b"V\n")
        await writer.drain()
        deadline = loop.time() + answer_timeout
        while (remaining := deadline - loop.time()) > 0:
            try:
                raw = await asyncio.wait_for(reader.readline(), remaining)
            except TimeoutError:
                return None
            if not raw:
                return None
            text = raw.decode(errors="replace").strip()
            # Frames ("Z...") may come first: culfw keeps receiving between sessions.
            if text.startswith("V "):
                return text
        return None
    except (OSError, ValueError):
        # ValueError: a line longer than the reader's limit (not a culfw).
        return None
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def scan(
    hosts: Iterable[str],
    port: int,
    *,
    skip: Collection[str] = frozenset(),
    probe: Callable[[str, int], Awaitable[str | None]] = probe_version,
    concurrency: int = CONCURRENCY,
) -> list[Found]:
    """Ask the hosts, a limited number at a time; targets in `skip` ("host:port") are not
    connected to (a module in use must not be disturbed). Sorted by address."""
    gate = asyncio.Semaphore(concurrency)

    async def ask(host: str) -> Found | None:
        async with gate:
            try:
                version = await probe(host, port)
            except Exception:
                _LOGGER.debug("search: %s:%s failed", host, port, exc_info=True)
                return None
        return None if version is None else Found(host, port, version)

    results = await asyncio.gather(*(ask(host) for host in hosts if f"{host}:{port}" not in skip))
    found = [item for item in results if item is not None]
    return sorted(found, key=lambda item: ipaddress.ip_address(item.host))


async def async_search_network(
    hass: HomeAssistant, *, skip: Collection[str] = frozenset(), port: int = DEFAULT_NETWORK_PORT
) -> list[Found]:
    """culfw modules on Home Assistant's own subnets (port 2323)."""
    hosts = candidate_hosts(await network.async_get_adapters(hass))
    found = await scan(hosts, port, skip=skip)
    _LOGGER.info("search for culfw on port %s: %s addresses asked, %s found", port, len(hosts), len(found))
    return found
