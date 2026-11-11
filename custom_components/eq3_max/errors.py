"""Errors for the user, translated by Home Assistant (strings.json, section exceptions).

Messages raised here are English (logs, str()); the frontend shows the translation of
`translation_key` in the user's language. The panel translates the same keys.
"""

from __future__ import annotations

from typing import Any

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN


def _placeholders(values: dict[str, Any]) -> dict[str, str]:
    return {name: str(value) for name, value in values.items()}


def invalid(key: str, /, **placeholders: Any) -> ServiceValidationError:
    """The request itself is wrong (wrong device, value, weekday ...)."""
    return ServiceValidationError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=_placeholders(placeholders)
    )


def failed(key: str, /, **placeholders: Any) -> HomeAssistantError:
    """The request was fine, the radio or the device did not take it."""
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key=key, translation_placeholders=_placeholders(placeholders)
    )


def translated(
    err: Exception, cls: type[HomeAssistantError] = HomeAssistantError, language: str | None = None
) -> HomeAssistantError:
    """An error of the protocol layer (FrameError, ConfigValueError) for the user: its key
    if it has one, otherwise its English text.

    Home Assistant wants the same placeholders in every language, so a weekday travels as
    `day` in the given language (German or English); `day_de`/`day_en` stay for the panel,
    which picks by the user's language."""
    key = getattr(err, "key", None)
    placeholders = dict(getattr(err, "placeholders", {}) or {})
    if key is None:
        key, placeholders = "radio_error", {"detail": str(err)}
    if "day_de" in placeholders and (language or "").lower().startswith("de"):
        placeholders["day"] = placeholders["day_de"]
    return cls(translation_domain=DOMAIN, translation_key=key, translation_placeholders=_placeholders(placeholders))


def send_ws_error(connection: Any, msg_id: int, code: str, err: Exception) -> None:
    """Answer a panel request with the error, translation key included (the panel shows
    it in the user's language)."""
    if not isinstance(err, HomeAssistantError) or getattr(err, "translation_domain", None) != DOMAIN:
        hass = getattr(connection, "hass", None)
        err = translated(err, ServiceValidationError, hass.config.language if hass else None)
    connection.send_error(
        msg_id,
        code,
        str(err),
        translation_key=err.translation_key,
        translation_domain=DOMAIN,
        translation_placeholders=err.translation_placeholders,
    )
