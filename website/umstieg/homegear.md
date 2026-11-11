# Migrating from Homegear

For installations with **Homegear** and the legacy integration **`homematic`** in Home
Assistant. No device has to be paired again, the entity IDs stay.
Overview and requirements: [Migration](index.md).

## What is taken over

| Before | In eq3_max |
|---|---|
| Radio address of the central unit | the same sender address, no re-pairing |
| Serial number, radio address, type, firmware | device in HA; name from the Homegear metadata, otherwise from the old entity |
| `climate.<name>` | `climate.<name>`, history continues |
| `binary_sensor.<name>_state` (window contact) | `binary_sensor.<name>_state` |
| `binary_sensor.<name>_lowbat` | `binary_sensor.<name>_lowbat` |
| Template sensor `sensor.<name>_ventil` | `sensor.<name>_ventil` (valve), replaces the template entry |
| Area, display name, icon, aliases, labels, "disabled", "hidden" | are kept |
| Configuration (comfort, eco, maximum, minimum, offset, window-open temperature, boost, decalcification) | `number.*`/`select.*` with attribute `quelle: homegear` (source) |
| Links | links per device, `sensor.<name>_verknuepfungen` |
| `homematic.keypress` of the eco buttons | `event.<name>` — **switch automations over** (step 7) |

**Not taken over**, because Homegear does not output them: window-open duration, maximum
valve opening, valve offset. Afterwards they are at the factory default (`quelle: werksvorgabe`).
If you had changed them on the device, set them again in eq3_max.

**New** are `sensor.<name>_rssi`, for thermostats `binary_sensor.<name>_funkfehler` (radio error),
`…_gesperrt` (locked) and `sensor.<name>_zuletzt_gemeldet` (last seen), plus the radio module
entities `*.eq3_max_*`.

## 1. Prepare (operation continues) { #vorbereiten }

1. **Determine the central address.** It is the sender in every telegram Homegear
   sends. Search the Homegear log for `Sending (My-MAX-CUL` (interface name from
   `families/max.conf`):

   ```
   0B 4E 05 40 C0FFEE A1B004 01 66
   Length Counter Flags Type Source Dest  Group Payload
   ```

   So here the address is `C0FFEE`.

2. **Export the devices** while Homegear is running:

   ```bash
   python3 tools/homegear_export.py --host <homegear-host> --port 2001 --out eq3_max_export.json
   ```

   Check: is the number of devices right? Do the wall thermostat and linked thermostats
   have a `links` entry?

   Alternatively, the setup dialog queries Homegear directly (source "Homegear"). This only
   works while Homegear is running. The file is the safe way and stays around for a second
   attempt.

3. **Registry dry run.** Every serial number must appear in the entity registry as a
   homematic entry (`<SERIAL>` for climate, `<SERIAL>_LOWBAT`, `<SERIAL>_STATE`).
   Missing entries will get new IDs later.

4. **Check names.** If Homegear provides no names, eq3_max takes over the display names of the
   old entities. Other names are set as `name` in the export file.

5. Leave **groups** at `0` in the export file. eq3_max addresses devices without a group; this
   also works for devices that Homegear addressed with a group.

## 2. Back up

- Full HA backup (Settings → System → Backups).
- Copy `/config/.storage/core.entity_registry`.
- Back up the Homegear directory on the host.

## 3. Clean up the HA configuration

Create a `.bak` copy of each file first.

- Remove the `homematic:` block from `configuration.yaml`.
- Remove helper constructs around Homegear (REST sensor "Homematic up",
  reconnect automations).
- Retire template sensors that rebuild values from homematic attributes (`sensor.<name>_ventil`).
  eq3_max provides them with the same IDs.
- `check_config` must pass without errors.

## 4. Install the integration

- Copy `custom_components/eq3_max` to `/config/custom_components/`.
- Copy the export file to `/config/eq3_max_export.json`.

## 5. Switch over

1. **Stop Homegear.** Only stop it, do not delete it (way back), autostart off.
2. **Connect the radio module** (see [Hardware](../loslegen/hardware.md)):
   - **nanoCUL:** Move the stick from Homegear to the HA box and determine the path:
     `ls -l /dev/serial/by-path/`. Always use `by-path`, never `by-id`.
   - **MAX! Cube with a-culfw:** Cube on the LAN, check with `nc <cube-ip> 2323` and `V`.
     Homegear cannot use the Cube, so it replaces the stick.
3. **Restart HA.** `homematic` must no longer be loaded afterwards.
4. **Add the integration:** Settings → Devices & services → "eQ-3 MAX!"
   - Connection: "USB stick" with the `by-path` entry, or network with the Cube IP and
     port 2323
   - Central address: the previous one (e.g. `C0FFEE`), also with the Cube
   - Source: JSON, `/config/eq3_max_export.json`
   - Confirm the device list

## 6. Acceptance test

Check in order and take notes:

1. All devices present, all thermostats with values, **no `_2` IDs**.
2. Change the target temperature on a thermostat → `ausstehend` (pending) is empty after a few seconds.
3. Set a device that Homegear addressed with a group specifically → only this one changes.
4. Open/close a window contact → the entity follows.
5. Press an eco button → `event.<name>` shows `auto` or `eco`.
6. Adjust the wall thermostat → it and the linked thermostats follow.
7. Open the **"eQ-3 MAX!"** panel → links as under Homegear, configuration with
   source `homegear`.

## 7. Switch button automations over

`homematic.keypress` becomes event entities:

```yaml
triggers:
  - trigger: state
    entity_id: event.taster
    not_from: unavailable
    not_to: unavailable
```

`not_to: unavailable` prevents triggering when the integration is reloaded. The button
is distinguished by `trigger.to_state.attributes.event_type` (`auto` or `eco`).

## 8. Observe and clean up

- Observe for 48 hours: `binary_sensor.*_funkfehler`, `sensor.eq3_max_sendezeit_1h`,
  log warnings "no ack".
- Then remove the Homegear container or service.

The airtime brake (36 s per hour) is switched on for new entries; this keeps it at 1 % even with a culfw without its own budget check.

## Way back

!!! tip "Back in under 15 minutes"
    As long as Homegear is only stopped and not deleted, this is the way back:


    1. Delete the integration "eQ-3 MAX!".
    2. Stick back to the Homegear host, start Homegear (if you switched to the Cube,
       you need the old stick for this). With Docker, restart it once
       afterwards so the container grabs the device again.
    3. Restore the `.bak` files, restart HA.
    4. If areas or names are missing: stop HA, copy the backed-up `core.entity_registry` back.
