"""Who may change what: device settings, week programs and admin actions."""

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError

from custom_components.eq3_max.const import CONF_ALLOW_USER_CONFIG, CONF_ALLOW_USER_WEEK_PROFILE, DOMAIN
from custom_components.eq3_max.permissions import async_check_allowed, user_allowed_flags


@pytest.fixture
async def family_user(hass):
    """A normal user without admin rights (group system-users). The first user of a fresh
    instance becomes its owner (always admin), so one is created before."""
    await hass.auth.async_create_user("Eigentümer", group_ids=["system-admin"])
    user = await hass.auth.async_create_user("Familie", group_ids=["system-users"])
    assert not user.is_admin
    return user


def _options(hass, entry, **values):
    hass.config_entries.async_update_entry(entry, options={**entry.options, **values})


@pytest.mark.parametrize("kind", ["config", "week_profile", "admin"])
async def test_admin_and_no_user_always_allowed(hass, setup_entry, hass_admin_user, kind):
    _options(hass, setup_entry, **{CONF_ALLOW_USER_CONFIG: False, CONF_ALLOW_USER_WEEK_PROFILE: False})
    await async_check_allowed(hass, setup_entry, Context(user_id=hass_admin_user.id), kind)
    await async_check_allowed(hass, setup_entry, Context(), kind)
    await async_check_allowed(hass, setup_entry, None, kind)


@pytest.mark.parametrize(
    "kind,option", [("config", CONF_ALLOW_USER_CONFIG), ("week_profile", CONF_ALLOW_USER_WEEK_PROFILE)]
)
async def test_user_follows_the_switch(hass, setup_entry, family_user, kind, option):
    ctx = Context(user_id=family_user.id)
    await async_check_allowed(hass, setup_entry, ctx, kind)  # default: allowed
    _options(hass, setup_entry, **{option: False})
    with pytest.raises(ServiceValidationError) as err:
        await async_check_allowed(hass, setup_entry, ctx, kind)
    assert err.value.translation_key == f"not_allowed_{kind}" and err.value.translation_domain == DOMAIN


async def test_user_never_does_admin_actions(hass, setup_entry, family_user):
    with pytest.raises(ServiceValidationError) as err:
        await async_check_allowed(hass, setup_entry, Context(user_id=family_user.id), "admin")
    assert err.value.translation_key == "not_allowed_admin"


async def test_flags_default_true(hass, setup_entry):
    assert user_allowed_flags(setup_entry) == (True, True)
    _options(hass, setup_entry, **{CONF_ALLOW_USER_WEEK_PROFILE: False})
    assert user_allowed_flags(setup_entry) == (True, False)


# --- enforced in entities and services ---

from homeassistant.const import ATTR_ENTITY_ID  # noqa: E402
from homeassistant.helpers import device_registry as dr  # noqa: E402

from .conftest import HT  # noqa: E402

HT_S, FK_S = "MEQ9000007", "NEQ9000010"


def _dev(hass, serial):
    return dr.async_get(hass).async_get_device(identifiers={(DOMAIN, serial)}).id


async def _call(hass, domain, service, data, user):
    await hass.services.async_call(domain, service, data, blocking=True, context=Context(user_id=user.id))


async def test_user_cannot_change_settings_when_locked(hass, setup_entry, fake_hub, family_user):
    hub = fake_hub.last
    _options(hass, setup_entry, **{CONF_ALLOW_USER_CONFIG: False})
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_komfort", "value": 22}, family_user)
    assert err.value.translation_key == "not_allowed_config"
    with pytest.raises(ServiceValidationError):
        await _call(hass, "select", "select_option", {ATTR_ENTITY_ID: "select.wt_wohnzimmer_anzeige", "option": "actual"}, family_user)
    assert hub.commands == []
    # Temperature stays open to everyone.
    await _call(hass, "climate", "set_temperature", {ATTR_ENTITY_ID: "climate.ht_bad_unten", "temperature": 20}, family_user)
    assert hub.commands[-1][0] == HT


async def test_user_may_change_settings_by_default(hass, setup_entry, fake_hub, family_user):
    await _call(hass, "number", "set_value", {ATTR_ENTITY_ID: "number.ht_bad_unten_komfort", "value": 22}, family_user)
    assert fake_hub.last.commands[-1] == ("config", HT, "komfort", 22.0)


async def test_admin_services_only_for_admins(hass, setup_entry, fake_hub, family_user, hass_admin_user):
    data = {"device_id": _dev(hass, HT_S), "partner_device_id": _dev(hass, FK_S)}
    for service in ("link", "unlink"):
        with pytest.raises(ServiceValidationError) as err:
            await _call(hass, DOMAIN, service, data, family_user)
        assert err.value.translation_key == "not_allowed_admin"
    with pytest.raises(ServiceValidationError):
        await _call(hass, DOMAIN, "factory_reset", {"device_id": _dev(hass, HT_S)}, family_user)
    assert fake_hub.last.commands == []
    await _call(hass, DOMAIN, "link", data, hass_admin_user)
    # Automations and scripts: no user.
    await hass.services.async_call(DOMAIN, "unlink", data, blocking=True)
    assert [c[0] for c in fake_hub.last.commands] == ["link", "unlink"]


async def test_week_profile_follows_its_switch(hass, setup_entry, fake_hub, family_user):
    data = {"device_id": _dev(hass, HT_S), "weekday": ["Montag"], "profile": [{"temperature": 17}]}
    _options(hass, setup_entry, **{CONF_ALLOW_USER_WEEK_PROFILE: False})
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, DOMAIN, "set_week_profile", data, family_user)
    assert err.value.translation_key == "not_allowed_week_profile"
    with pytest.raises(ServiceValidationError):
        await _call(hass, DOMAIN, "copy_week_profile", {"device_id": _dev(hass, HT_S), "target_device_id": [_dev(hass, HT_S)]}, family_user)
