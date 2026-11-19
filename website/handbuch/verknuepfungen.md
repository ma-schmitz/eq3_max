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
  state "waiting for window contact – please press its pairing button briefly (or open and close the window)" (button:
  press it once; for both, the pairing button works too, the device stays paired). Sending
  happens without wake-up preamble, 80 ms after the device's last telegram – one attempt
  per opportunity, because a contact only listens for a moment after sending itself.
  Several opportunities per event are normal: the contact reports to the central unit, then
  to each partner, and to unreachable partners again and again for minutes. If the request
  stays "waiting for …" over several events, the telegram trace helps
  ([Operation](betrieb.md#diagnose)). **From 0.8.3** eq3_max gives up after **5 reports without
  acknowledgement**: the request then shows as "failed" and is tried again only with **"Send
  again"** – otherwise every report of the contact would cost airtime for good. **From 0.8.4**
  one round counts per event (retries and reports to partners within a few seconds count once).
- **Contact without partners (from 0.8.4):** a window contact not yet linked to any thermostat
  only reports to the central unit and goes back to sleep on its acknowledgement – opening and
  closing the window never gets the request through. **Press its pairing button briefly** (LED
  blinks): the contact reports to the central again and listens for a few seconds; eq3_max sends
  the next waiting link right after (also a "failed" one). **One per press:** after the first
  the contact stops listening (#6); as it has a partner now, the others follow on the next
  window event or the next press. New batteries are not enough, a contact
  does not report again after a restart.
- **Lost acknowledgement (from 0.8.6):** a contact or button reporting its event to the partner
  carries the link – only a linked device does that. A change still open ("waiting for …" or
  "failed") counts as acknowledged then, nothing is sent again (#6).
- States in `ausstehend`: pending · waiting for … · failed (will be retried) ·
  **failed (rejected)** (the device refused, no automatic retry) ·
  one-sided (only one side knows the other).
- Known (09.10.2026): a radiator thermostat **refuses removal of a wall thermostat**;
  adding works.
- A factory reset also removes the links on the former partners.
- **Cancelling a request.** An open or failed request can be dropped without sending
  anything: button **"Cancel request"** next to it on the "eQ-3 MAX!" page, or
  ```yaml
  action: eq3_max.cancel_link
  data:
    device_id: <device with the request>
    partner: MEQ0000001   # serial number or device; empty: all requests of the device
  ```
  Useful for requests that can never complete, e.g. a removal the device refused. Links and
  requests to devices deleted from the integration are dropped at the next start; only a removal
  still waiting stays, it can still arrive.
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
