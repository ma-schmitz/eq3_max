"""Who may change what.

Home Assistant has no per-entity rights: every user may call every service. eq3_max checks
the caller itself. Admin actions (factory reset, links, radio module) are for admins only;
device settings and week programs follow two options. Calls without a user (automations
run by their triggers) are always allowed; a script or automation a user starts by hand
(dashboard button, "Run") carries that user and is checked like the user.
"""

from __future__ import annotations

from typing import Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant

from .const import CONF_ALLOW_USER_CONFIG, CONF_ALLOW_USER_WEEK_PROFILE
from .errors import invalid

Kind = Literal["config", "week_profile", "admin"]


def user_allowed_flags(entry: ConfigEntry) -> tuple[bool, bool]:
    """(device settings, week programs) open to users without admin rights."""
    return (
        bool(entry.options.get(CONF_ALLOW_USER_CONFIG, True)),
        bool(entry.options.get(CONF_ALLOW_USER_WEEK_PROFILE, True)),
    )


async def async_check_allowed(
    hass: HomeAssistant, entry: ConfigEntry | None, context: Context | None, kind: Kind
) -> None:
    """Raise the translated not_allowed_<kind> error if the caller may not do this. The entry
    (its options) only counts for config/week_profile; admin actions need none."""
    if context is None or context.user_id is None:
        return
    user = await hass.auth.async_get_user(context.user_id)
    if user is None or user.is_admin:
        return
    if entry is None:
        raise invalid(f"not_allowed_{kind}")
    config, week = user_allowed_flags(entry)
    if (kind == "config" and config) or (kind == "week_profile" and week):
        return
    raise invalid(f"not_allowed_{kind}")
