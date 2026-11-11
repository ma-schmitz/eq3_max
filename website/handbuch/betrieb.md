# Operation and faults


## What to keep an eye on

- `binary_sensor.*_funkfehler` — single short "Problem" phases are normal (radio collision);
  permanently on points to an unreachable device (battery, range).
- `sensor.eq3_max_sendezeit_1h` — normally well below 36 s.
- `binary_sensor.*_lowbat` — replace the batteries.

## Self-healing

| Situation | Integration's reaction |
|---|---|
| Stick unplugged / port gone / network CUL not reachable | reconnect every 30 s; after 15 min repair issue "CUL not reachable" |
| Stick receives nothing after sending | port is reopened **immediately** (at most once per radio silence); pending commands go out again afterwards |
| A single device does not answer, but the radio works (other devices are heard) | the device counts as **silent**: no further reopening on its account, log warning "does not answer … check the device"; its command goes out again with its next report |
| Sending for 10 min but nothing received | a watchdog reopens the port; the second time, repair issue "CUL stick receives nothing" |
| HA restart | all values back immediately; pending commands are sent again, expired "Away" commands discarded |

On an outage, entities do **not** become "unavailable" but keep their last value — so
automations do not flip.

## Repair issues

| Issue | Meaning |
|---|---|
| CUL not reachable | no connection to the CUL for 15 min (path or `host:port` is in the message) |
| CUL stick receives nothing | no reception even after two restarts → different USB port; power-cycle a network CUL |
| Homematic integration still active | remove `homematic:` from the YAML, restart |

## Diagnostics { #diagnose }

Device page of the radio module → "Download diagnostics": connection type and target, stick version, connection, airtime,
queue, all device states and the last raw telegrams per device.

**Telegram trace.** The logger `custom_components.eq3_max.trace` writes, at level `info`,
every line to (`-> Zs…`) and from the radio module (`<- Z…`) as well as the send window of
sleeping devices to `home-assistant.log`. Enable it in `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.eq3_max: debug
```

or at runtime with the service `logger.set_level`. This is the log that helps with "device
does not react" (for example a window contact that does not accept its link). Deliberately
`info` instead of `debug`: Home Assistant OS does not write `debug` lines to the log file.

## Limits

- Week programs can be written ([Services](dienste.md)) but not read from the devices; the
  integration only knows what it has written itself.
- Configuration is not read from the device (the devices cannot do that).
- After a battery change a wall thermostat asks for date and time on the device; during this
  input it accepts no radio answer. Its radio error indicator goes off again as soon as it
  has successfully delivered a report.
- Observed, cause unknown: after a new valve configuration (boost, decalcification, valve
  limits) the radiator thermostats of a room did not acknowledge the temperature reports of
  their wall thermostat for about a quarter of an hour, and the wall thermostat set a radio
  error. With the next target change on the wall thermostat it worked again.
