"""Geraetesuche, die auf alten und neuen Home-Assistant-Versionen funktioniert."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr


def find_device(
    reg: dr.DeviceRegistry, config_entry_id: str, identifier: tuple[str, str]
) -> dr.DeviceEntry | None:
    """Das Geraet mit dieser Kennung, das zum Konfigeintrag gehoert.

    Kennungen sind nicht mehr eintragsuebergreifend eindeutig, daher wird immer
    auf den eigenen Konfigeintrag eingegrenzt. Die Iteration ueber
    async_entries_for_config_entry laeuft auf alten wie neuen Versionen und
    vermeidet das veraltete async_get_device.
    """
    for device in dr.async_entries_for_config_entry(reg, config_entry_id):
        if identifier in device.identifiers:
            return device
    return None
