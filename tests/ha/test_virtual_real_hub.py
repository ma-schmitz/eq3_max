"""A virtual device through the real hub and coordinator (fake radio stick, no FakeHub):
created into the entry, back after a reload with its address and stored runtime state,
and gone from entry and registry after a forced removal."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.helpers import device_registry as dr

from custom_components.eq3_max.const import CONF_DEVICES, DOMAIN
from custom_components.eq3_max.protocol.hub import MaxHub
from custom_components.eq3_max.protocol.messages import DeviceType

from tests.protocol.fakes import FakeCul, until


def _item(entry, serial):
    return next((i for i in entry.data[CONF_DEVICES] if i.get("serial") == serial), None)


async def test_virtual_devices_through_the_real_hub(hass, entry):
    culs: list[FakeCul] = []

    def real_hub(*args, **kwargs):
        cul = FakeCul()
        culs.append(cul)
        return MaxHub(*args, **{**kwargs, "open_connection": cul.open, "ack_timeout": 0.05, "lovf_wait": 0.01})

    hass.states.async_set("binary_sensor.kueche", "on")
    hass.states.async_set("sensor.buero", "21.5", {"unit_of_measurement": "°C"})
    with patch("custom_components.eq3_max.coordinator.MaxHub", real_hub):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hub = entry.runtime_data.hub
        await until(lambda: hub.connected)

        contact = hub.virtual.create(DeviceType.SHUTTER_CONTACT, "Küche", "binary_sensor.kueche")
        await hass.async_block_till_done()                                    # the entry reloads
        item = _item(entry, contact.serial)
        assert item is not None and item["virtual"] is True and item["source"] == "binary_sensor.kueche"
        assert item["address"] == contact.address
        hub = entry.runtime_data.hub
        wall = hub.virtual.create(DeviceType.WALL_THERMOSTAT, "Büro", "sensor.buero")
        await hass.async_block_till_done()
        assert _item(entry, wall.serial)["source"] == "sensor.buero"

        hub = entry.runtime_data.hub
        await until(lambda: hub.connected)
        again = hub.devices[contact.address]
        assert again.virtual and again.serial == contact.serial and again.window_open is True  # fed by its source
        assert hub.devices[wall.address].measured == 21.5
        again.delivered = {"MEQ9000007": True}
        hub.devices[wall.address].sent_at, hub.devices[wall.address].sent_measured = 1_700_000_000.0, 21.5

        await hass.config_entries.async_reload(entry.entry_id)              # the store is written on stop
        await hass.async_block_till_done()
        hub = entry.runtime_data.hub
        await until(lambda: hub.connected)
        assert hub.devices[contact.address].delivered == {"MEQ9000007": True}
        assert (hub.devices[wall.address].sent_at, hub.devices[wall.address].sent_measured) == (1_700_000_000.0, 21.5)
        assert hub.devices[wall.address].serial == wall.serial

        assert hub.virtual.remove(contact.address, force=True) is True
        await hass.async_block_till_done()
        assert _item(entry, contact.serial) is None
        assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, contact.serial)}) is None
        assert _item(entry, wall.serial) is not None

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
