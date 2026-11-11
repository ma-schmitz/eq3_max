# Manual

Everyday operation of the "eQ-3 MAX!" integration.


eq3_max connects Home Assistant directly by radio (868 MHz) to eQ-3 MAX! devices through a
CUL stick or a flashed Cube — without Homegear and without the Cube software.

```
Thermostats, window contacts, buttons  ⇄  radio 868 MHz  ⇄  radio module (USB/LAN)  ⇄  eq3_max in HA
```

Supported devices:

| Device | Model (example) | in HA |
|---|---|---|
| Radiator thermostat | BC-RT-TRX-CyN | Thermostat (`climate`) + sensors |
| Wall thermostat | BC-TC-C-WM-2 | Thermostat (`climate`) + sensors |
| Window contact | BC-SC-Rd-WM-2 | Window sensor (`binary_sensor`) |
| Eco button | BC-PB-2-WM | Event (`event`) |

Each device appears as a device of its own in HA (with logo, serial number, firmware and
radio address as "Hardware version") and sits under the device **"eQ-3 MAX! radio module"**.

## Entities

### Radiator thermostat (example `ht_wohnzimmer`)

| Entity | Meaning |
|---|---|
| `climate.ht_wohnzimmer` | Target, current temperature, mode, preset |
| `sensor.ht_wohnzimmer_ventil` | Valve opening in % |
| `binary_sensor.ht_wohnzimmer_lowbat` | Battery low |
| `sensor.ht_wohnzimmer_rssi` | Signal strength in dBm (diagnostic) |
| `binary_sensor.ht_wohnzimmer_funkfehler` | Device reports a radio error **or** a command was not acknowledged (diagnostic) |
| `binary_sensor.ht_wohnzimmer_gesperrt` | Controls on the device locked (diagnostic) |
| `sensor.ht_wohnzimmer_zuletzt_gemeldet` | Time of the last report (diagnostic) |

**Thermostat attributes:**

| Attribute | Meaning |
|---|---|
| `valve` | Valve opening (same as the valve sensor) |
| `id` | Serial number |
| `ausstehend` | (pending) target sent but not yet acknowledged |
| `ausstehend_modus` | Mode of the pending command |
| `bis` | (until) end time in "Away" mode (reported by the device) |

### Wall thermostat

Like the radiator thermostat, but without a valve.

### Window contact

`binary_sensor.fk_…_state` (on = open), plus battery and RSSI. Linked window contacts
switch their thermostat to the window-open temperature **directly by radio** — this
happens even when HA is not running.

### Eco button

`event.<button>` with the event types `auto` and `eco`.
Each button press creates exactly one event; telegrams repeated by the device are
filtered out.

### Radio module

| Entity | Meaning |
|---|---|
| `binary_sensor.eq3_max_verbunden` | Stick connected |
| `sensor.eq3_max_sendezeit_1h` | Airtime of the last hour in s (legal limit: 36 s = 1 %) |
| `sensor.eq3_max_warteschlange` | Queued commands |
| `button.eq3_max_anlernen` | Opens the pairing window for 60 s |
