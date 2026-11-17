"""Repairs: take over the entities of the predecessors, once an admin confirmed the list."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICES
from .migration import MigrationBlocked, async_find_takeovers, async_take_over
from .protocol.devices import MaxDevice


class TakeoverRepairFlow(RepairsFlow):
    """Lists the predecessors' entities and takes them over on confirmation."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict | None = None) -> FlowResult:
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_gone")
        devices = [MaxDevice.from_dict(d) for d in entry.data[CONF_DEVICES]]
        if user_input is not None:
            try:
                async_take_over(self.hass, entry, devices)
            except MigrationBlocked as err:
                return self.async_abort(
                    reason="predecessor_active", description_placeholders={"integration": err.integration}
                )
            # Entity IDs and maybe device names changed: start over with them.
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
            return self.async_create_entry(data={})
        takeovers = async_find_takeovers(self.hass, devices)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders={
                "count": str(len(takeovers)),
                "entities": "\n".join(f"- `{t.old_id}` ({t.platform})" for t in takeovers),
            },
        )


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict | None) -> RepairsFlow:
    return TakeoverRepairFlow((data or {}).get("entry_id", ""))
