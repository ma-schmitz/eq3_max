**English** · [Deutsch](README.de.md)

# eq3_max

Home Assistant integration for eQ-3 MAX! via a CUL with culfw: USB stick (e.g. nanoCUL868)
or on the network (a-culfw on a CUN or a flashed MAX! Cube).
Replaces Homegear and the legacy `homematic` integration.

**Documentation:** https://ma-schmitz.github.io/eq3_max/ – installation, migration from Homegear,
manual and FAQ. Source in the folder `website/` (Material for MkDocs, locally:
`uv venv .venv-docs && uv pip install -p .venv-docs -r requirements_docs.txt &&
.venv-docs/bin/mkdocs serve`).

## Features

- Radiator and wall thermostats as `climate`, valve position as a separate sensor
- Window contacts, eco buttons (as event entities), battery, RSSI, radio errors
- State survives restarts, lost commands are detected and repeated
- Takes over existing Homegear pairings and entity IDs without re-pairing
- Airtime sensor and brake at 1 % (36 s per hour, on for new entries)
- Preset "Away" (temporary with end time), factory reset and deleting devices
- Device configuration (comfort/eco temperature, offset, window, boost, decalcification, valve)
- Create and remove links between devices (window contact, button, wall and radiator thermostat)
- CUL via USB or on the network (CUN, flashed Cube), switchable in the options
- Several radio modules with one central address (e.g. one per floor); assign devices to
  another module without re-pairing
- The "eQ-3 MAX!" panel in the sidebar: overview, links and device configuration
- English and German: names, messages, dialogs and the panel follow the language of Home Assistant

## Connection (USB or network)

The first setup step asks for the connection:

- **"USB stick"**: serial port from `/dev/serial/by-path/` (38400 baud), as before.
- **"Search the network"**: queries the own network on port 2323 and lists the
  culfw modules to choose from. Home Assistant also reports a flashed MAX! Cube by
  itself under "Discovered".
- **"Network: enter the address (CUN, flashed Cube)"**: host and port (default 2323). a-culfw on
  a CUN or on a MAX! Cube flashed with a-culfw speaks the same
  text protocol there as the stick. Before continuing, `V` is sent; without an answer
  "V …" within 5 s, "No culfw answered (no reply to V)." appears.

After that it continues as usual with central address and device import. The
unique_id remains the central address.

The connection can be changed later under options → "Change connection"
(USB ↔ network or a different port/host) without creating the integration again. It
is checked as during setup; a changed connection reloads the
integration. The connection currently in use is not checked because the
integration holds it; saved unchanged, it stays without a restart. Entries from before this option (without `connection`) count as USB.

Network connection: connection setup with a 10 s timeout, TCP keepalive (a
vanished device is noticed after about 90 s) and TCP_USER_TIMEOUT 120 s where the
system supports it; reconnect every 30 s. Enter only a host name or IP address as host
(no `http://`, no path). When
the watchdog or the fast reopen "reopens" the CUL, only the
TCP connection is closed and re-established. Unlike reopening the stick
(DTR), this does not reset the radio module itself; if that does not help, cut the
device's power. Depending on the build, a-culfw accepts only one TCP client at a time;
other programs on the same port interfere. Line endings `\r\n` and `\n` are
both accepted.

The diagnostics show the type (`usb`/`network`) and target (path or `host:port`), the
repair issue "CUL not reachable" shows the target.

## Multiple radio modules

Under options → "Radio modules" further USB sticks or network CULs can be added, each with
a name. All work with the same central address (like the interfaces in
Homegear). Every device sends through an assigned module, receiving works through all of them;
telegrams heard twice are evaluated once, the signal strength per module is remembered.
The assignment is changed by the entity `select.<device>_funkmodul` ("Radio module") or the
"Radio module" tab on the "eQ-3 MAX!" panel. Nothing happens on the device, pending commands move along.
Every module has its own radio budget and its own repair issue. Details:
`website/handbuch/funkmodule.md`.

## Device configuration

Every thermostat has configuration entities (category "Configuration" on
the device page):

| Key | HT | WT | Range |
|---|---|---|---|
| `komfort`, `eco`, `maximal`, `minimal`, `fenster_temperatur` | yes | yes | 4.5–30.5 °C, step 0.5 |
| `offset` (measurement offset) | yes | yes | −3.5…+3.5 K, step 0.5 |
| `fenster_dauer` | yes | yes | 0–60 min, step 5 |
| `boost_dauer` (select) | yes | – | "0 min" … "60 min" (0, 5, 10, 15, 20, 25, 30, 60) |
| `boost_ventil` | yes | – | 0–100 %, step 5 |
| `entkalkung_tag` (select) | yes | – | Saturday … Friday |
| `entkalkung_stunde` | yes | – | 0–23 |
| `ventil_max`, `ventil_offset` | yes | – | 0–100 % |

(HT = radiator thermostat, WT = wall thermostat; the keys stand for comfort, eco, maximum,
minimum, window-open temperature/duration, boost duration/valve, decalcification day/hour,
maximum valve opening and valve offset.)

The entity_ids follow the device, e.g. `number.ht_bad_unten_komfort` or
`select.ht_bad_unten_entkalkung_tag`.

- The devices only accept whole sets (temperatures: telegram 0x11, valve:
  0x12). Changing one value sends the whole set with the other
  stored values.
  Values with source `werksvorgabe` are only assumed and are still
  written to the device; the log then warns with "Sende angenommene
  Werksvorgaben mit: …" (sending assumed factory defaults along) and names the affected values.
- The devices do not report their configuration back. Shown is the
  last acknowledged value; a sent but not yet acknowledged one is in the
  attribute `ausstehend` (pending) and is repeated like a set command (next
  status after a failure, after reconnecting and at startup). With several
  quick changes, only the newest set goes out.
- Attribute `quelle` (source): `homegear` (taken over from the export), `werksvorgabe`
  (assumed because unknown) or `gesetzt` (sent from HA and acknowledged by the device
  – applies to all values of the set).
- Factory defaults after pairing: comfort 21.0, eco 17.0, maximum 30.5,
  minimum 4.5 °C, offset 0.0 K, window 12.0 °C for 15 min, boost 5 min at
  80 %, decalcification Saturday 12:00, valve maximum 100 %, valve offset 0 %.
- Configuration and source are stored in the config entry (and in
  storage); pending sets only in storage. At startup, the
  entry takes precedence over storage for each value.
- The window-open temperature is also the value by which the integration
  tells a reported window-open target temperature from a comfort temperature.
  "Heat" without a remembered manual target temperature uses the
  comfort temperature from the configuration.

## Links

Linked devices talk to each other directly: a window contact reports "open"
to its thermostat, a wall thermostat leads its radiator thermostats. The
services `eq3_max.link` and `eq3_max.unlink` create or remove a link
(telegrams 0x20 AddLinkPartner and 0x21 RemoveLinkPartner, like FHEM
`associate`/`deassociate`).

- Allowed: window contact–radiator thermostat, window contact–wall thermostat,
  wall thermostat–radiator thermostat, radiator thermostat–radiator thermostat,
  eco button–radiator or wall thermostat. Other pairs, a device with
  itself, already linked (or, when unlinking, unlinked) pairs and already
  requested changes are rejected by the service with a message.
- A link always has two directions: each of the two devices gets
  the other as partner and acknowledges this separately. A direction that already
  exists is not sent again.
- The service returns right after queuing. Thermostats get their
  part immediately. Window contacts and eco buttons sleep and only listen for a moment
  after sending themselves. After a window event a contact first reports
  to the central unit, then to each partner thermostat (40–110 ms apart), and with
  unreachable partners again and again for minutes: their part waits until they
  report, and goes out 80 ms after the most recent telegram from or to them without
  wake-up preamble (`Zf`) – one attempt per opportunity, 0.5 s acknowledgement wait;
  if the device sends itself meanwhile, the attempt is abandoned and repeated after the
  next telegram. Never with preamble (`Zs`): after 1 s it always comes
  too late. So open and close the window once, or press the button (or the
  pairing button) once; the pairing button works for both, even if the
  device is already paired. Pending requests survive restarts; a
  factory reset of the device discards them.
- Diagnostic sensor `sensor.<base>_verknuepfungen` ("Links") on every device: the state is the
  number of complete links (both directions acknowledged), attribute
  `partner` the names of the partners, attribute `ausstehend` for each unfinished pair
  "<partner>: <state>" with `ausstehend` (queued or in transit),
  "wartet auf Fensterkontakt – bitte Fenster einmal öffnen und schließen"
  (waiting for window contact – please open and close the window once; or "wartet auf
  Eco-Taster – bitte Taster einmal drücken (oder Anlerntaste)", waiting for eco button –
  please press the button once (or the pairing button)), `fehlgeschlagen` (failed),
  `fehlgeschlagen (abgelehnt)` (failed (rejected)) or
  `einseitig` (one-sided: only one of the two devices knows the link, nothing
  requested – complete it with `eq3_max.link`).
- Unacknowledged requests to thermostats go out again like set commands: on the
  device's next status, after reconnecting and at startup. If a
  device refuses (NAK), it stays at `fehlgeschlagen (abgelehnt)`; only a new
  service call sends again.
- Acknowledged links (partner serial numbers, field `links`) are stored in the
  config entry and in storage, open requests only in storage. At
  startup the entry applies; an entry without `links` takes them from storage.
- The Homegear import reads the links via `getLinks`.
- An acknowledged factory reset also removes the device from the links of the
  other devices. Partners that had it acknowledged in their list get
  RemoveLinkPartner (thermostats immediately, sleepers at their next telegram);
  until acknowledged, this shows on the partner under `ausstehend`.

```yaml
action: eq3_max.link
data:
  device_id: 0123456789abcdef0123456789abcdef          # e.g. window contact
  partner_device_id: fedcba9876543210fedcba9876543210  # e.g. radiator thermostat
```

## The "eQ-3 MAX!" panel

Entry **"eQ-3 MAX!"** in the sidebar (administrators only, URL `/eq3-max`); the
device pages of the radio module and the devices link to it with "Visit"
(`configuration_url`). The page is a custom panel without a build step and without
third-party libraries (`custom_components/eq3_max/frontend/eq3-max-panel.js`, served under
`/eq3_max_static/`, cache buster from version and content); it follows the light or dark
HA theme and adapts to narrow screens.

- **Header per radio module:** connected/disconnected, connection (USB path or `host:port`),
  airtime of the last hour as a bar against 36 s, queue, button
  "Pair (60 s)" with countdown (only when the radio module is connected).
- **Device cards by HA area** ("No area" last): actual → target and mode or
  preset, valve bar (radiator thermostat), open/closed (window contact),
  battery, RSSI, "last reported", number of links; markers "pending",
  "not acknowledged", "Radio error", "Battery low".
- **Side panel** (click on a card), tab **"Links":** partners with state
  (linked, pending, waiting for device, failed, rejected, one-sided) and the
  text of the sensor `…_verknuepfungen`, "Unlink" per partner, "Send again" for
  failed ones, "Add partner" offering only the devices the service `link`
  would accept. For window contacts and buttons, the hint to open and close the
  window once or to press the button.
- Tab **"Configuration"** (radiator and wall thermostat): per set ("Temperatures",
  for the radiator thermostat also "Valve") a form on the integration's grid,
  per value the source (Homegear / Factory default / set) and "pending" if applicable –
  only for values that differ from the acknowledged one (the whole set is always sent; that
  it is in transit is shown by "Set pending").
  Change as many values as you like, then **"Send set"**: before sending, the page lists the
  changes and the assumed factory defaults that go along; **one**
  telegram with the whole set is sent.
- The page updates itself (push, debounced 250 ms); while you type, the
  update waits until you leave the field.

WebSocket commands (all administrators only; errors with translated text):

| Command | Data | Effect |
|---|---|---|
| `eq3_max/overview` | – | radio modules, devices, areas, links, configuration |
| `eq3_max/subscribe` | – | event `{"type": "update"}` after changes |
| `eq3_max/link`, `eq3_max/unlink` | `device_id`, `partner_device_id` | like the services `link`/`unlink` |
| `eq3_max/pair` | `entry_id` | open pairing for 60 s |
| `eq3_max/rename_radio` | `entry_id`, `radio`, `name` | rename a radio module (the main one is `""`); the integration reloads |
| `eq3_max/set_config` | `device_id`, `kind` (`temp`/`valve`), `values` | whole set in one telegram; answer `factory_keys` = factory defaults sent along |

## Services

- `eq3_max.set_away` – set thermostats to a temperature until a point in time
  (MAX! mode temporary, then back to auto). Without `temperature` the
  away temperature from the options applies; the end is rounded up to the next half
  hour and must be in the future. The preset "Away"
  does the same with the away duration from the options (default 18.0 °C, 24 h).
- `eq3_max.factory_reset` – reset a device to factory settings over the air.
  Only if it acknowledges is it removed from the integration; pair it
  again afterwards. Without acknowledgement it may have been reset anyway – then
  remove it via "Delete device". Only forgetting (without radio) works via "Delete device" on the
  device page.
- `eq3_max.link` / `eq3_max.unlink` – link two devices or remove the
  link, see "Links".

```yaml
action: eq3_max.set_away
target:
  entity_id: climate.ht_bad_unten
data:
  temperature: 16
  until: "2026-10-12 18:00:00"
```

```yaml
action: eq3_max.factory_reset
data:
  device_id: 0123456789abcdef0123456789abcdef
```

## Installation

Requirement: Home Assistant 2026.8 or newer.

Copy `custom_components/eq3_max` to `/config/custom_components/`, restart Home Assistant,
add the integration "eQ-3 MAX!".

Via HACS: add this repository under HACS → Custom repositories with the
category "Integration", download "eQ-3 MAX!", restart Home Assistant.

Migration from Homegear: see `website/umstieg/`.

## Development

Contributions are welcome – see [CONTRIBUTING.md](.github/CONTRIBUTING.md). Questions go to the
[Discussions](https://github.com/ma-schmitz/eq3_max/discussions), security issues privately (see [SECURITY.md](.github/SECURITY.md)).

    uv venv -p 3.14 .venv && uv pip install -p .venv -r requirements_test.txt
    .venv/bin/pytest


## License and notes

MIT license, see [LICENSE](LICENSE).

eq3_max is a private project and not affiliated with eQ-3 AG. "eQ-3", "MAX!" and
"Homematic" are trademarks of their respective owners and are used descriptively only.

Radio regulations: in the 868 MHz band every transmitter may send at most 1 % of the time (36 s per hour).
eq3_max measures the airtime and keeps to the limit with the brake (on for new entries).
If you switch it off, you are responsible for compliance yourself.

Ideas and protocol knowledge come from [FHEM](https://fhem.de) (10_MAX.pm, 14_CUL_MAX.pm),
[Homegear](https://homegear.eu), [culfw](http://culfw.de)/a-culfw and the project
[maxcul](https://github.com/powerpaul17/maxcul). eq3_max contains no code from them.
