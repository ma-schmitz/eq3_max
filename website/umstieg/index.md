# Migrating to eq3_max

This is how an existing MAX! installation moves to the integration **eq3_max** ("eQ-3 MAX!").
The path from Homegear has been proven on an installation with 24 devices.

## Which guide fits?

| Before | Guide | Pair again? | Entity IDs |
|---|---|---|---|
| Homegear + legacy `homematic` integration | [From Homegear](homegear.md) | no | taken over automatically |
| nothing, new installation | [Setup](../loslegen/einrichtung.md) | – | – |

## The principle

!!! abstract "Three rules"

    - **MAX! devices remember the radio address of their central unit.** If eq3_max sends
      with the same address and knows the device list, no device has to be paired again.
    - **Entity IDs stay**, so automations, dashboards and history keep working.
    - **Never two central units at the same time.** The old solution is switched off before
      eq3_max starts. As long as `homematic` is loaded in HA, eq3_max refuses
      setup.

## Requirements

- Home Assistant **2026.8 or newer** (logo in the UI from 2026.9).
- A radio module with culfw, either of the two (details under [Hardware](../loslegen/hardware.md)):
  - **nanoCUL** via USB on the HA box (proven), or
  - **MAX! Cube with a-culfw** on the network (port 2323) or via USB (in use in further
    installations).

  For the migration it does not matter which: what counts is the central address, not
  the module.
- Access to `/config` on the HA box (SSH add-on or Samba).
- About an hour, ideally during the day when little heating is needed. The thermostats keep
  regulating on their own during the switchover, only commands from HA do not arrive.

## Common pitfalls

| Symptom | Cause and remedy |
|---|---|
| Setup aborts with "Homematic integration still active" | `homematic:` is still in the YAML, or HA was not restarted |
| New entities are named `…_2` | The predecessor entry belongs to another integration or was missing in the dry run |
| Devices are named after their serial number | Export without names and no predecessor with names → set `name` in the export file |
| Configuration shows `werksvorgabe` (factory default) everywhere | Export without values → repeat the export while Homegear is running, or set the values in eq3_max |
| Links are missing | Export without `links` → add them on the "eQ-3 MAX!" panel or with `eq3_max.link` |
| Commands stay "pending", radio errors | Stick goes deaf after sending (USB port). The integration then reopens the port itself. Permanent remedy: another port, a short extension cable or an active hub |
| Commands delayed, `LOVF` in the log, "waiting for airtime" on the radio module | The firmware's airtime reserve is empty (nanoCUL/CUL 9 s, Cube 36 s in one go, 10 ms per second are refilled). eq3_max waits and continues sending by itself; do nothing. Many commands in a row (week programs, configuration of many devices) take correspondingly long |
| Flashed Cube: radio module turns red again and again, commands stay unacknowledged | The Cube restarts because it is on the LAN and draws its power from a USB port of a router/NAS/computer (bug in a-culfw) → connect it to a USB power supply |
| New code has no effect | Reloading the integration does not load new Python code → restart HA |
