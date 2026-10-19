from unittest.mock import patch

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.eq3_max.const import DOMAIN
from custom_components.eq3_max.registry_compat import find_device


def test_find_device_is_scoped_to_config_entry(hass):
    reg = dr.async_get(hass)
    first = MockConfigEntry(domain=DOMAIN)
    second = MockConfigEntry(domain=DOMAIN)
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    ident = (DOMAIN, "MEQ9000007")
    dev1 = reg.async_get_or_create(config_entry_id=first.entry_id, identifiers={ident})
    dev2 = reg.async_get_or_create(config_entry_id=second.entry_id, identifiers={ident})
    assert dev1.id != dev2.id

    with patch.object(dr.DeviceRegistry, "async_get_device", side_effect=AssertionError("veraltet")):
        assert find_device(reg, first.entry_id, ident).id == dev1.id
        assert find_device(reg, second.entry_id, ident).id == dev2.id
        assert find_device(reg, first.entry_id, (DOMAIN, "unbekannt")) is None


async def test_overview_does_not_use_deprecated_lookup(hass, setup_entry, fake_hub):
    from custom_components.eq3_max.websocket_api import _Context

    with patch.object(dr.DeviceRegistry, "async_get_device", side_effect=AssertionError("veraltet")):
        ctx = _Context(hass, setup_entry)
        assert ctx.device_id("MEQ9000007") is not None
