# Links


Window contacts and wall thermostats act **directly by radio** on linked thermostats.

- Display: `sensor.<device>_verknuepfungen` — number of complete links, attribute
  `partner` (names), `ausstehend` (pending: running requests with their state).
- Create/remove: services `eq3_max.link` / `eq3_max.unlink` with two devices; both
  directions are sent and acknowledged separately.
  ```yaml
  action: eq3_max.link
  data:
    device_id: <window contact>
    partner_device_id: <thermostat>
  ```
- **Window contacts and eco buttons sleep.** Requests to them wait until they report:
  state "waiting for window contact – please open and close the window once" (button:
  press it once; for both, the pairing button works too, the device stays paired). Sending
  happens without wake-up preamble, 80 ms after the device's last telegram – one attempt
  per opportunity, because a contact only listens for a moment after sending itself.
  Several opportunities per event are normal: the contact reports to the central unit, then
  to each partner, and to unreachable partners again and again for minutes. If the request
  stays "waiting for …" over several events, the telegram trace helps
  ([Operation](betrieb.md#diagnose)).
- States in `ausstehend`: pending · waiting for … · failed (will be retried) ·
  **failed (rejected)** (the device refused, no automatic retry) ·
  one-sided (only one side knows the other).
- Known (09.10.2026): a radiator thermostat **refuses removal of a wall thermostat**;
  adding works.
- A factory reset also removes the links on the former partners.
- **Leftover links (from 0.7.0).** After thermostats were swapped or moved, a device
  sometimes still holds a partner that the integration does not know and that no longer
  knows it. That partner never acknowledges: a wall thermostat reports a **radio error** on
  every target change, a window contact repeats its telegram for minutes. In the telegram
  trace you recognise it by telegrams from the device to an address that gets no answer.
  Remove it, on this one device only:
  ```yaml
  action: eq3_max.unlink
  data:
    device_id: <device with the leftover>
    partner_device_id: <old partner>
    force: true
  ```
  Nothing is sent to the old partner. For window contacts this request, too, waits for the
  next window event.

## Group id (from 0.8.0)

Thermostats of one group take set commands together: the integration then sends them with
the group id, and every device of the group follows. On the "eQ-3 MAX!" page, tab
**Links**, under **Group id**:

- **Set**: enter an id 1–255; **Remove** takes it away again.
- **Assign for the room**: this thermostat and all thermostats linked with it get one
  common id no other device has (if they share one already, that one stays). All **other**
  thermostats get "remove group" once: the devices do not report their group, and an old id
  from Cube or Homegear times would otherwise make an unrelated thermostat follow.

The new id counts once the device acknowledged it; until then it shows as "pending", and
without an acknowledgement it goes out again with the device's next report. After a factory
reset the device gets its id back automatically.

**Why?** A target HA sends to the wall thermostat is passed on to the radiators only with its
next round (measured 2–5 min). With a common group all devices of the room take it from one
telegram (measured 1–2 min; radiators only listen at intervals).
