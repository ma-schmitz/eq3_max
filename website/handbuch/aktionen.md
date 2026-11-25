# Actions and automations

Everything you can do with eq3_max from automations, scripts and the developer tools: the
integration's actions, Home Assistant's standard actions on MAX! devices, the settings
entities and the triggers. Ready-made examples are at the end.

Every action can be tried under **Developer tools → Actions**. If you do not have a device id
at hand: pick the device in the visual editor, then switch to "Edit in YAML" – the id is there.

## Overview

| Action | What for | Who may | Waits for the device |
|---|---|---|---|
| [`climate.set_temperature`](#climateset_temperature) | target, optionally with mode | everyone | no |
| [`climate.set_hvac_mode`](#climateset_hvac_mode) | heat, auto, off | everyone | no |
| [`climate.set_preset_mode`](#climateset_preset_mode) | comfort, eco, boost, away, none | everyone | no |
| [`climate.turn_on` / `turn_off`](#climateturn_on-and-climateturn_off) | heat or off | everyone | no |
| [`eq3_max.set_away`](#eq3_maxset_away) | fixed temperature until a point in time | everyone | no |
| [`eq3_max.set_week_profile`](#eq3_maxset_week_profile) | write a week program | option¹ | **yes** |
| [`eq3_max.copy_week_profile`](#eq3_maxcopy_week_profile) | copy a week program | option¹ | **yes** |
| [`eq3_max.set_time`](#eq3_maxset_time) | set the thermostats' clock | everyone | **yes** |
| [`eq3_max.link`](#eq3_maxlink) | link devices | admins | no |
| [`eq3_max.unlink`](#eq3_maxunlink) | remove a link | admins | no |
| [`eq3_max.cancel_link`](#eq3_maxcancel_link) | drop an open link request | admins | – (sends nothing) |
| [`eq3_max.factory_reset`](#eq3_maxfactory_reset) | factory reset, remove the device | admins | **yes** |
| [`number.set_value` / `select.select_option`](#settings-entities) | device configuration | option² | no |
| [`select.select_option` (radio module)](#switching-the-radio-module) | assign a device to a radio module | admins | no |
| [`button.press` (pairing)](#pairing) | open pairing for 60 s | admins | no |

¹ "Users without admin rights may change week programs", ² "… may change device settings"
(both on by default). Automations run by their trigger may always do everything; details under
[Who may do what](dienste.md#who-may-do-what-from-080).

**"Does not wait for the device"** means: the action queues the command and returns right away.
The thermostat acknowledges it seconds later; until then the value is in the attribute
`ausstehend`. Without an acknowledgement it is repeated up to three times, then
`binary_sensor.…_funkfehler` turns on and the command goes out again at the device's next
report (see [Commands and acknowledgements](bedienung.md#commands-and-acknowledgements)). The
action itself only fails on invalid input or missing permission.

**"Waits for the device"** means: the action ends only when every device named has
acknowledged, and reports an error if one refuses or does not answer. An automation stands
still that long – with a week program and little airtime that can be minutes.

## Controlling a thermostat

All actions in this section take an eq3_max `climate` entity as target (radiator or wall
thermostat, also a virtual wall thermostat).

### `climate.set_temperature`

| Field | Required | Values |
|---|---|---|
| `temperature` | yes (unless `hvac_mode` alone) | 4.5 to 30.5 °C in steps of 0.5; 4.5 = off, 30.5 = fully open |
| `hvac_mode` | no | `heat`, `auto`, `off` |

What happens depends on the mode:

| Call | Effect on the thermostat |
|---|---|
| only `temperature`, thermostat in **auto** | applies until the next switching point, then the program again |
| only `temperature`, thermostat in **heat** | applies for good |
| only `temperature`, thermostat in **away** | ends away, applies for good |
| `temperature` + `hvac_mode: heat` | for good, switches to heat |
| `temperature` + `hvac_mode: auto` | back to the program, the temperature holds until the next switching point |
| `hvac_mode: off` (with or without temperature) | off (4.5 °C) |

```yaml
action: climate.set_temperature
target:
  entity_id: climate.ht_living_room
data:
  temperature: 21.5
  hvac_mode: heat
```

Several quick calls to the same thermostat send only the latest state. A change in auto mode
that is not acknowledged by the switching point lapses; the thermostat then follows its
program.

### `climate.set_hvac_mode`

| `hvac_mode` | Effect |
|---|---|
| `heat` | heat with the current target; coming from off, away or boost, with the last manually set value |
| `auto` | auto: the thermostat follows its week program |
| `off` | off (manual 4.5 °C, frost protection) |

A virtual wall thermostat offers `auto` only once a complete week program has been written to
it.

```yaml
action: climate.set_hvac_mode
target:
  entity_id: climate.ht_living_room
data:
  hvac_mode: auto
```

### `climate.set_preset_mode`

| `preset_mode` | Effect |
|---|---|
| `comfort` | comfort temperature from the device configuration; in auto until the next switching point |
| `eco` | eco temperature from the device configuration; in auto until the next switching point |
| `boost` | valve wide open for the boost duration, then back |
| `away` | away temperature from the options for the away duration (default 18 °C, 24 h) |
| `none` | ends away or boost (back to the last manual value); in auto back to the plain program |

```yaml
action: climate.set_preset_mode
target:
  entity_id: climate.ht_bathroom
data:
  preset_mode: boost
```

Without a known comfort or eco temperature, `comfort`/`eco` report "Invalid value"; set the
values once under [Device configuration](konfiguration.md).

### `climate.turn_on` and `climate.turn_off`

`turn_off` is `hvac_mode: off`, `turn_on` is `hvac_mode: heat` (see above).

### `eq3_max.set_away`

A fixed temperature until a point in time; afterwards the thermostat returns to its previous
mode **by itself** – even if Home Assistant is not running then. Good for holidays.

| Field | Required | Values |
|---|---|---|
| target | yes | one or more eq3_max `climate` entities |
| `until` | yes | date and time; rounded **up** to the next full or half hour, must then lie in the future |
| `temperature` | no | 4.5 to 30.5 °C; without it the away temperature from the options |

```yaml
action: eq3_max.set_away
target:
  entity_id:
    - climate.ht_living_room
    - climate.ht_kitchen
data:
  temperature: 16
  until: "2026-12-27 18:00:00"
```

The thermostat's attribute `bis` shows the end time once the device reports it. To end early:
`climate.set_preset_mode` with `none` or `climate.set_hvac_mode` with `heat`/`auto`.

## Week program and clock

### `eq3_max.set_week_profile`

Writes whole days of the week program to one or more thermostats. The device follows the
program in **auto** mode.

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | one or more thermostats (radiator, wall, virtual wall thermostat) |
| `weekday` | yes | one or more days: `saturday` … `friday` or German `Samstag` … `Freitag`, or `all`/`alle`; case does not matter |
| `profile` | yes | 1 to 13 points `{temperature, until}`; each applies **until** its time |
| `force` | no | `true`: also write days the device already has exactly like this |

Rules for `profile`:

- `until` as `hh:mm`, in steps of 5 minutes, ascending; leave it out on the last point or use
  `24:00` (it applies until midnight).
- `temperature` 4.5 to 30.5 °C in steps of 0.5.
- A time without quotes (`until: 06:00`) is read by YAML as a number; that works too.

```yaml
action: eq3_max.set_week_profile
data:
  device_id: <wall thermostat living room>
  weekday: [monday, tuesday, wednesday, thursday, friday]
  profile:
    - {temperature: 17, until: "06:00"}
    - {temperature: 21, until: "08:30"}
    - {temperature: 18, until: "16:00"}
    - {temperature: 21, until: "22:30"}
    - {temperature: 17}
```

Good to know:

- **The whole room gets the program.** If the thermostat is linked through a wall thermostat,
  the integration writes the same days to the room's other thermostats too. The action waits
  for the devices named; the others run alongside.
- **Unchanged days are not sent again.** A day a device has already acknowledged exactly like
  this is skipped. `force: true` writes everything anyway, e.g. after the program was changed
  on the device itself.
- **It can take a while.** One or two telegrams per day (two from eight points). On a nanoCUL
  the airtime in one go suffices for a few days; after that every telegram waits about two
  minutes, a whole week takes a quarter of an hour and more. Writing goes on even when the
  automation no longer waits; the "eQ-3 MAX!" panel shows the progress in the "Week program"
  tab, as does the attribute `wochenprogramm_schreibt`.
- **While a write is running**, a second one for the same thermostat is refused ("week program
  is being written").
- A restart of Home Assistant aborts it; write the missing days again afterwards.

Possible errors: "week program *day* rejected", "… not acknowledged", "week program is being
written", "only thermostats have a week program", and the messages about invalid points
(count, temperature, time, order).

#### "Clearing" a program

A thermostat always has a program; clearing means writing a new one. Factory program:

```yaml
- action: eq3_max.set_week_profile
  data:
    device_id: <thermostat>
    weekday: [monday, tuesday, wednesday, thursday, friday]
    profile:
      - {temperature: 17, until: "06:00"}
      - {temperature: 21, until: "09:00"}
      - {temperature: 17, until: "17:00"}
      - {temperature: 21, until: "23:00"}
      - {temperature: 17}
- action: eq3_max.set_week_profile
  data:
    device_id: <thermostat>
    weekday: [saturday, sunday]
    profile:
      - {temperature: 17, until: "06:00"}
      - {temperature: 21, until: "22:00"}
      - {temperature: 17}
```

A fixed temperature around the clock: `weekday: all` and `profile: [{temperature: 17}]`. The
"eQ-3 MAX!" panel has the buttons "Write factory program" and "Write fixed temperature" for
this.

### `eq3_max.copy_week_profile`

Writes a thermostat's stored program (its last acknowledged days) to others.

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | source, one thermostat |
| `target_device_id` | yes | one or more targets |

```yaml
action: eq3_max.copy_week_profile
data:
  device_id: <thermostat living room>
  target_device_id:
    - <thermostat dining room>
    - <thermostat kitchen>
```

The devices do not report their program; the integration only knows what it wrote itself. A
program that exists only in the device (set on the device, by the Cube or from Homegear) cannot
be copied ("no week program stored for …"). As with `set_week_profile`, a target's whole room
gets the program, and unchanged days are skipped.

### `eq3_max.set_time`

Sets the clock of thermostats to Home Assistant's local time and waits for each
acknowledgement.

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | one or more radiator or wall thermostats |

```yaml
action: eq3_max.set_time
data:
  device_id:
    - <thermostat>
```

In operation the devices fetch the time themselves now and then, and the integration corrects
a wall thermostat's clock that is off by itself. The action is for the case that a clock is
wrong anyway. Window contacts and eco buttons have no clock.

## Links

Linked devices talk to each other **directly over the air**, even when Home Assistant is not
running. Background and states: [Links](verknuepfungen.md).

The actions place a request and return right away. The progress shows in
`sensor.<device>_verknuepfungen` (state: number of completed links; attributes `partner` and
`ausstehend`). **Window contacts and eco buttons sleep**: a request to them waits until they
report – open and close the window, press the button or briefly the pairing button.

### `eq3_max.link`

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | one device |
| `partner_device_id` | yes | the other device (on the same integration entry) |

```yaml
action: eq3_max.link
data:
  device_id: <window contact bathroom>
  partner_device_id: <thermostat bathroom>
```

Allowed:

| Device | can be linked with |
|---|---|
| radiator thermostat | radiator thermostat, wall thermostat, window contact, eco button |
| wall thermostat | radiator thermostat, window contact, eco button |
| window contact, eco button | radiator thermostat, wall thermostat |

A radiator thermostat has at most one wall thermostat. Errors: "these devices cannot be
linked", "already linked", "already requested", "this thermostat already has a wall
thermostat".

### `eq3_max.unlink`

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | one device |
| `partner_device_id` | yes | the partner |
| `force` | no | `true`: remove on `device_id` only, nothing is sent to the partner; also for partners the integration does not know as linked |

```yaml
action: eq3_max.unlink
data:
  device_id: <thermostat>
  partner_device_id: <old window contact>
  force: true
```

`force` is for leftovers: a device still holds a partner that was swapped or no longer knows
the link (signs: radio error on every change, a contact repeating for minutes).

### `eq3_max.cancel_link`

Drops open or failed requests of a device **without sending anything**.

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | the device with the request |
| `partner` | no | serial number or device id of the partner; empty: all requests of the device |

```yaml
action: eq3_max.cancel_link
data:
  device_id: <thermostat>
  partner: MEQ0000001
```

## Resetting a device

### `eq3_max.factory_reset`

Resets a device to factory settings and removes it from the integration. It then has to be
paired again; its links are also removed on the partners.

| Field | Required | Values |
|---|---|---|
| `device_id` | yes | a MAX! device (not the radio module) |

```yaml
action: eq3_max.factory_reset
data:
  device_id: <device>
```

The action waits for the acknowledgement. "Factory reset not sent": radio module not connected
or the device did not report in time. "… not acknowledged – it may have been reset anyway":
check the device (display "rES" or ready for pairing).

!!! danger "Use deliberately"
    A factory reset cannot be undone. To remove a device only from Home Assistant, without a
    radio command: device page → "Delete device".

## Settings entities

The device configuration is available as `number` and `select` entities on the device (list
under [Device configuration](konfiguration.md)). From automations they are set with the
standard actions:

```yaml
action: number.set_value
target:
  entity_id: number.ht_living_room_eco
data:
  value: 17
```

```yaml
action: select.select_option
target:
  entity_id: select.ht_living_room_boost_dauer
data:
  option: "10 min"
```

| Entity | Values |
|---|---|
| `number.…_komfort`, `_eco`, `_maximal`, `_minimal`, `_fenster_temperatur` | 4.5 to 30.5 °C, step 0.5 |
| `number.…_offset` | −3.5 to +3.5 K, step 0.5 |
| `number.…_fenster_dauer` | 0 to 60 min, step 5 (0 = own window detection off) |
| `number.…_boost_ventil` | 0 to 100 %, step 5 |
| `number.…_ventil_max`, `_ventil_offset` | 0 to 100 %, step 1 |
| `number.…_entkalkung_stunde` | 0 to 23 |
| `select.…_boost_dauer` | `0 min`, `5 min` … `30 min`, `60 min` |
| `select.…_entkalkung_tag` | `saturday` … `friday` |
| `select.…_anzeige` | `setpoint` or `actual`, wall thermostat only |
| `select.…_ist_abfragen` | `off`, `15`, `30`, `60`, `120`, `240` (minutes), radiator only |

- Every change sends the device's whole set (all temperatures or all valve values).
- **Room values** (comfort, eco, limits, window, boost, decalcification) are also set on the
  room's other thermostats.
- Values off the grid are refused ("value must be between … in steps of …"); 21.3 °C does not
  work.
- The devices do not report their settings back: the entity shows the last acknowledged value,
  the attribute `quelle` where it came from.

### Switching the radio module

With several radio modules every device has `select.<device>_funkmodul`. The option is the
module's name; the attributes `rssi_<module>` show how well each module hears the device.

```yaml
action: select.select_option
target:
  entity_id: select.ht_bathroom_upstairs_funkmodul
data:
  option: Upstairs
```

### Pairing

`button.eq3_max_anlernen` opens pairing for 60 seconds – like the button on the "eQ-3 MAX!"
panel.

```yaml
action: button.press
target:
  entity_id: button.eq3_max_anlernen
```

## Triggers and states

What works as a trigger or condition:

| Entity | State / event | Typical use |
|---|---|---|
| `event.<button>` | event type `auto` or `eco` | the eco button switches something else, e.g. lights |
| `binary_sensor.<contact>_state` | `on` = open | window open for long → notification |
| `binary_sensor.<device>_lowbat` | `on` = battery low | battery change reminder |
| `binary_sensor.<device>_funkfehler` | `on` = radio error or command not acknowledged | report a fault |
| `sensor.<device>_zuletzt_gemeldet` | timestamp | device has stopped reporting |
| `sensor.<radiator>_ventil` | valve opening in % | pass heat demand to the boiler |
| `climate.<thermostat>` | mode, attributes `temperature`, `current_temperature`, `preset_mode` | room temperature, target |
| `binary_sensor.eq3_max_verbunden` | `off` = a radio module disconnected | report an outage |
| `sensor.eq3_max_sendezeit_1h` | airtime of the last hour in s | watch the 36 s limit |

**Attributes of the thermostat**, useful in templates:

| Attribute | Content |
|---|---|
| `ausstehend`, `ausstehend_modus` | target and mode sent but not acknowledged yet |
| `bis` | end time of away |
| `valve` | valve opening (radiator only) |
| `id` | serial number |
| `fenster` | linked window contacts of the device and its room (entity ids) |
| `raum` | the room's other thermostats |
| `wochenprogramm` | the stored program per weekday |
| `wochenprogramm_schreibt`, `wochenprogramm_fehler` | days being written right now, and why a write was aborted |

**Eco button:** every press creates exactly one event; repetitions by the device are filtered
out. The button still switches its linked thermostats itself – the automation comes on top.

## Examples

### Holiday for all rooms

```yaml
alias: Heating holiday
triggers:
  - trigger: state
    entity_id: input_boolean.holiday
    to: "on"
actions:
  - action: eq3_max.set_away
    target:
      entity_id: all
    data:
      temperature: 15
      until: "{{ states('input_datetime.holiday_end') }}"
```

`entity_id: all` covers all eq3_max `climate` entities (the action belongs to the
integration). The thermostats return by themselves at the end time.

### Eco button also switches the lights

```yaml
alias: Eco button hallway
triggers:
  - trigger: state
    entity_id: event.button_hallway
actions:
  - choose:
      - conditions: "{{ trigger.to_state.attributes.event_type == 'eco' }}"
        sequence:
          - action: light.turn_off
            target:
              area_id: hallway
      - conditions: "{{ trigger.to_state.attributes.event_type == 'auto' }}"
        sequence:
          - action: light.turn_on
            target:
              area_id: hallway
```

### Window open for 15 minutes

```yaml
alias: Window open reminder
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.fk_bathroom_state
      - binary_sensor.fk_kitchen_state
    to: "on"
    for: "00:15:00"
actions:
  - action: notify.notify
    data:
      message: "{{ trigger.to_state.name }} has been open for 15 minutes."
```

The thermostat already turns down by itself while the window is open; the automation is only
the reminder.

### Winter and summer program

```yaml
alias: Summer program
triggers:
  - trigger: state
    entity_id: input_boolean.summer
    to: "on"
actions:
  - action: eq3_max.set_week_profile
    data:
      device_id:
        - <wall thermostat living room>
        - <thermostat bathroom>
      weekday: all
      profile:
        - {temperature: 4.5}
```

`4.5` is "off". The winter program is written back the other way round. Because the action
waits for the devices, such an automation runs for a few minutes; later steps come only then.

### Batteries low

```yaml
alias: MAX! battery low
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.ht_living_room_lowbat
      - binary_sensor.fk_bathroom_lowbat
    to: "on"
actions:
  - action: notify.notify
    data:
      message: "Battery low: {{ trigger.to_state.name }}"
```

## When something does not work

- **"Only administrators may do this" / "… only administrators may change (integration
  option)":** a user without admin rights triggered the action (also through a dashboard
  button). It does not apply when the automation runs through its trigger.
- **"Radio module not connected":** the device's module is disconnected; the "eQ-3 MAX!" panel
  shows which one.
- **Value does not arrive, `funkfehler` on:** device out of range, battery, or the airtime is
  used up ("eQ-3 MAX!" panel: "waiting for airtime"). The command is repeated as soon as the
  device reports.
- **The automation hangs:** `set_week_profile`, `copy_week_profile`, `set_time` and
  `factory_reset` wait for the device. With little airtime that takes a while; with
  `continue_on_error: true` the automation goes on after an error.
