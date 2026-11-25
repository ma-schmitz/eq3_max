# Options and permissions

All actions (formerly "services") with fields and examples are now under
[Actions and automations](aktionen.md).

## Deleting a device

"Delete device" on the device page only removes a device from HA (no radio command). Useful
for devices that no longer physically exist.

## Options

Settings → Devices & services → eQ-3 MAX! → Configure. The menu offers
"Settings" (table below), "Change connection": USB stick or network (CUN, flashed Cube,
host and port, default 2323), and "Radio modules" (further modules, see
[Several radio modules](funkmodule.md)). The new connection is checked with `V`; a changed
connection restarts the integration, the settings do not.

| Option | Default | Meaning |
|---|---|---|
| Limit airtime to 36 s per hour | on (new entries) | keeps to the legal limit of 36 s per hour (1 %); commands may then wait |
| Away temperature | 18.0 °C | for the preset "Away" |
| Away duration (hours) | 24 h | for the preset "Away" |
| Users without admin rights may change device settings | on | comfort/eco, offset, window, boost, valve, display (entities, thermostat card); from 0.8.0 |
| Users without admin rights may change week programs | on | `set_week_profile`, `copy_week_profile`, thermostat card; from 0.8.0 |

## Who may do what (from 0.8.0)

Home Assistant has no rights per entity: every user may call every service. eq3_max
therefore checks the caller itself:

- **Administrators only:** `factory_reset`, `link`, `unlink`, the choice of radio module and the
  pairing button (from 0.8.2).
- **By option** (see above, open by default): device settings and week programs.
- **Always open:** temperature, mode, presets, `set_away`, `set_time`.

Automations run by their triggers have no user and may do everything. If a user starts a
script or automation by hand (dashboard button, "Run"), the call counts as that user and is
checked like them. A rejected call says
"Only administrators may do this" or points to the option.
