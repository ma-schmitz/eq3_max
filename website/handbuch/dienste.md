# Services


## `eq3_max.set_away`

Set a thermostat to a fixed temperature until a point in time (e.g. holidays).

```yaml
action: eq3_max.set_away
target:
  entity_id: climate.ht_wohnzimmer
data:
  temperature: 16
  until: "2026-10-20 18:00:00"
```

`temperature` is optional (otherwise the away temperature from the options). `until` must be
in the future and is rounded up to :00/:30.

## `eq3_max.factory_reset`

Resets a device to factory settings and removes it from the integration.

!!! danger "Use deliberately only"
    Afterwards the device must be paired again.

```yaml
action: eq3_max.factory_reset
data:
  device_id: <device ID from the device page>
```

Responses: success → device removed. "Factory reset not sent" → stick not connected or
30 s window elapsed. "The device did not acknowledge the factory reset – it may have been
reset anyway" → check on the device.

## `eq3_max.set_week_profile`

Writes whole days of the week program to one or more thermostats (radiator or wall
thermostat). The device follows the program in mode **Auto**.

```yaml
action: eq3_max.set_week_profile
data:
  device_id:
    - <thermostat device ID>
  weekday:
    - monday
    - tuesday
  profile:
    - temperature: 17
      until: "06:00"
    - temperature: 21
      until: "22:00"
    - temperature: 17
```

- `weekday`: one or more weekdays, in English (`monday` … `sunday`) or German (`Montag` …,
  as the UI stores them), any case, or `all` (German `alle`).
- `profile`: up to 13 points per day, each lasts **until** its time (5-minute steps,
  ascending). The last point may omit `until`; it lasts until 24:00. Temperatures
  4.5 to 30.5 °C in steps of 0.5 (4.5 = off, 30.5 = on).
- The service waits for the device's acknowledgements and reports an error if it refuses
  or does not answer; the remaining days are then not sent. Each day takes one or two
  telegrams (two from eight points on), so a whole week is 7 to 14 telegrams of about
  1.2 s airtime each.
- **This can take a while.** On a nanoCUL/CUL a whole week needs more airtime than the
  firmware allows in one go (9 s; on the Cube 36 s, where it fits; see
  [Hardware](../loslegen/hardware.md)). After the first days every further telegram then
  waits about two minutes, and a week takes a quarter of an hour and more. From 0.6.4 there
  is no time limit for this any more (before, the service aborted after 10 minutes and
  dropped the remaining days). The writing belongs to the integration: it continues when the
  caller stops waiting or the panel is closed. The "Week program" tab shows the progress
  (days still to do, reason for an abort). While a write is running, a second one for the
  same thermostat is refused. A restart of Home Assistant ends it; then write the missing
  days again.
- **The program applies to the whole room (from 0.7.0).** Wall thermostat and radiators
  each switch by their own copy. If you write days to a thermostat that is linked through
  a wall thermostat, the integration writes the same days to the other thermostats of the
  room as well. The service waits for the named device; the others run alongside, their
  progress is shown in the "Week program" tab. With five devices that is up to 70 telegrams
  for a whole week.
- The integration cannot read the program (the devices do not report it). It remembers the
  last acknowledged days per device; they are in the diagnostics and on the
  "eQ-3 MAX!" panel (data basis `week_profile`).

!!! tip "Unquoted times"
    YAML reads `until: 06:00` without quotes as a number (360 minutes). The service
    accepts both.

## `eq3_max.copy_week_profile`

Writes the week program stored for one thermostat (its last acknowledged days) to other
thermostats.

```yaml
action: eq3_max.copy_week_profile
data:
  device_id: <source device ID>
  target_device_id:
    - <target device ID 1>
    - <target device ID 2>
```

The source must have been written with `set_week_profile` before; a program that only
exists in the device (Cube, Homegear, set on the device) is unknown to the integration.

### "Clearing" a program

A thermostat always has a program. Clearing therefore means writing a new one – on the
"eQ-3 MAX!" panel with the buttons **Write factory program** and **Write fixed temperature**,
by service like this:

```yaml
# Factory program (as shipped): two calls
action: eq3_max.set_week_profile
data:
  device_id: <device ID>
  weekday: [monday, tuesday, wednesday, thursday, friday]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "09:00"}
    - {temperature: 17, until: "17:00"}
    - {temperature: 21, until: "23:00"}
    - {temperature: 17}
---
action: eq3_max.set_week_profile
data:
  device_id: <device ID>
  weekday: [saturday, sunday]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "22:00"}
    - {temperature: 17}
```

```yaml
# fixed temperature all day, every day
action: eq3_max.set_week_profile
data:
  device_id: <device ID>
  weekday: all
  profile:
    - {temperature: 17}
```

## `eq3_max.set_time`

Sets the clock of thermostats (radiator and wall thermostats) to Home Assistant's local time
now and waits for each acknowledgement (from 0.7.0). On the "eQ-3 MAX!" panel this is the
button **"Set clock now"** in the "Week program" tab.

```yaml
action: eq3_max.set_time
data:
  device_id:
    - <thermostat>
```

- The devices switch their week program by their own clock. In operation they occasionally
  fetch the time from the central unit themselves; the service is for when a clock is wrong.
- **After a battery change** a wall thermostat asks for date and time on the device; during
  this input it accepts no radio answer. Afterwards it reports its time to the central unit.
  If it is off by more than a minute, the integration corrects it by itself.
- Window contacts and eco buttons have no clock.

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

- **Administrators only:** `factory_reset`, `link`, `unlink` and the choice of radio module.
- **By option** (see above, open by default): device settings and week programs.
- **Always open:** temperature, mode, presets, `set_away`, `set_time`.

Automations run by their triggers have no user and may do everything. If a user starts a
script or automation by hand (dashboard button, "Run"), the call counts as that user and is
checked like them. A rejected call says
"Only administrators may do this" or points to the option.
