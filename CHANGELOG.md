# Changelog

**English** · [Deutsch](https://github.com/ma-schmitz/eq3_max/blob/main/CHANGELOG.de.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.8.0] – 2026-11-14

### Added
- **Wall thermostat display: set or current temperature.** New select
  `select.<device>_anzeige` (category configuration) and set **Display** on the "eQ-3 MAX!"
  page. The wall thermostat's own menu item "S-A" is locked while it is paired with a
  central, so the integration sets it by radio (telegram 0x82, as FHEM does). The device
  reports the setting itself in its full status: the value is unknown until that report
  (source `gemeldet`) or the acknowledgement (source `gesetzt`); no factory value is assumed.
  Requested in Discussion #5.
- **Presets "Comfort" and "Eco"** on every thermostat: manual mode at the comfort or eco
  temperature of the device configuration (telegram 0x40, as FHEM does). Shown as well when
  the target gets there another way; an open window wins. Eco is no comfort value to return
  to after Away/Boost.
- **Group id**: set (0x22) or remove (0x23) per thermostat, or "Assign for the room" for a
  thermostat and the thermostats linked with it (one free or already common id). Counts
  after the acknowledgement, resent with the next report otherwise, given back after a
  factory reset. "Assign for the room" removes that id once from all other thermostats (devices
  do not report their group; an old one from Cube/Homegear times would follow the room). Panel: tab
  Links; websocket command `eq3_max/set_group`.
- **Plug adapter (BC-TS-Sw-Pl, device type 8)** is paired instead of being dropped as an
  unknown type: shown with RSSI and "last seen", its telegrams logged at INFO for a capture.
  Not controlled yet.
- **Attributes for the thermostat card** (`eq3-max-thermostat-card`, own repository) on every
  thermostat: `fenster` (window contacts of the device and its room), `raum` (thermostats of
  the room), `wochenprogramm`, `wochenprogramm_schreibt`, `wochenprogramm_fehler`,
  `einstellungen_frei`, `wochenprogramm_frei`. Not recorded by the recorder.
- **Options "Users without admin rights may change device settings / week programs"**
  (both on by default). Enforced by the integration: entities and services refuse users
  without admin rights when off; automations and admins always may.
- **Poll the current temperature** of radiator thermostats: `select.<device>_ist_abfragen`
  (off, every 15/30/60/120/240 min). Only when the device did not report by itself: target
  +0.5 °C until it sends its status (about 1 min), then back; invisible in Home Assistant.
- **Explanations** for every setting on the "eQ-3 MAX!" page: hover text and an ⓘ that unfolds
  it (for phones and tablets).
- WakeUp telegram (0xF1) in the protocol and the hub (`wake_up`); not used on its own yet,
  whether it helps with series of telegrams is to be measured first.

### Fixed
- **Several radio modules no longer transmit at the same time.** Each module had its own queue;
  a room-wide change (wall thermostat on one module, radiator on the other) went out on both
  within milliseconds, the telegrams overlapped, and with the same retry interval they did so on
  every attempt – neither device acknowledged and both showed a radio error. Now one module
  transmits and waits for its acknowledgement at a time.

### Changed
- **Factory reset, link, unlink and the radio module selection are for administrators only.**
  Automations run by their triggers (no user) still may; a script a user starts counts as that user. Before, every Home Assistant user could
  call these services.

## [0.7.2] – 2026-11-13

### Fixed
- A push button repeats a press whose acknowledgement it did not take, with the same
  counter, sometimes only 8–12 s later. Repeats were filtered for 5 s only, so a late one
  counted as a second press, and an automation toggling a light switched it back. Repeats
  are now recognised for 30 s; a new press always has a new counter.

### Added
- Community files: issue forms (bug report, feature request), pull request template,
  CONTRIBUTING.md, code of conduct (Contributor Covenant 2.1), SECURITY.md with private
  vulnerability reporting; GitHub Discussions for questions.

## [0.7.1] – 2026-11-11

### Fixed

- The weekday selection of the week program actions used option keys with capital letters
  (`Montag`), which Home Assistant does not accept for translations (hassfest failed, the
  selection was not translated). The options are now lower case (`montag` …); the actions
  accept any capitalisation as before.

## [0.7.0] – 2026-11-11

### Added

- **German and English:** device and entity names, select options, error messages,
  setup and options dialogs as well as the "eQ-3 MAX!" panel follow the language of Home
  Assistant or of the user. Entity IDs of existing installations stay as they are.
  The project website and README are available in English and German, the changelog in English
  from this version on.
- **Rename radio modules**, including the main module: pencil on the module's tile on the
  "eQ-3 MAX!" panel, or options → "Radio modules" → "Rename a radio module" (WebSocket
  `eq3_max/rename_radio`), e.g. "Ground floor" instead of "Main module". Entity IDs, the attributes
  `rssi_<module>` and the assignment of the devices stay.
- **Pairing through a chosen radio module:** on the "eQ-3 MAX!" panel the module can be chosen
  next to "Pair"; only this module answers, and the device is assigned to it
  (WebSocket `eq3_max/pair` with `radio`, overview `pairing_radio`).
- **Search the network:** setup, "Radio modules" and "Change connection" can query
  all addresses in Home Assistant's network on port 2323 (at most 254, a few seconds)
  and list whatever answers as culfw. Modules already set up are not queried.
- **A flashed MAX! Cube is discovered automatically:** a-culfw gives the Cube a
  network address `00:80:41:…`; Home Assistant reports it under "Discovered". From there it
  becomes a new central unit or a further radio module of an existing entry.
- If a Cube discovered this way gets a new IP address via DHCP, the integration updates it
  by itself and reloads.
- **Room values apply to the whole room.** The devices store their settings each on
  their own and do not synchronise them with each other; when paired to a central unit, the
  wall thermostat's menu is locked. Changing a room value on one thermostat now applies it to
  all thermostats linked with it via a wall thermostat: comfort and
  eco temperature, minimum and maximum temperature, window-open temperature and duration,
  boost duration and valve opening, decalcification and the **week program**. Temperature
  offset and valve limits stay per device.
- **Boost duration on the wall thermostat:** it counts the boost down by its own duration and
  gets `select.<wt>_boost_dauer` for it.
- **A reset device is restored:** if a known device is paired again after a
  factory reset (it keeps its address and serial number, its name and its entities
  stay), the integration writes back everything it knows about it: its side
  of the links, both settings sets, the target temperature, the stored week program
  and the time. This is the way to get rid of old unknown links in a device.
- **Set a thermostat's clock:** service `eq3_max.set_time` and button "Set clock now"
  in the "Week program" tab. Sets it to Home Assistant's local time, the device
  acknowledges. The thermostats switch their week program by their own clock; after a
  battery change with manual entry it is often wrong.
- **Delete a leftover link on one device:** `eq3_max.unlink` with `force: true` removes a
  partner only on the given device, even if the integration does not know the link. For
  leftovers of swapped or moved thermostats: otherwise the device keeps transmitting to the
  old partner, so a wall thermostat reports radio errors on every target temperature change and a
  window contact repeats for minutes.
- **Network modules are monitored:** if nothing arrived for 20 s, the integration asks the module
  for its state (`X`). If it does not answer or has lost its settings
  (Cube restarted), it is reconnected and set up again immediately. Previously a freshly
  restarted Cube stayed "connected" and deaf for up to one and a half minutes.

### Changed

- The integration now depends on Home Assistant's `network` integration (for the search).
- Log messages and device model names are in English ("Radiator thermostat",
  "Wall thermostat+" …). The services accept weekdays in German or English, in any
  capitalisation (`montag`, `Monday`, `alle`, `all`); the selection in the action dialog shows them in the user's language.
- After a connection loss, the first new attempt comes after 3 s instead of 30 s.
- **Acknowledgements: exactly one per message.** With a **USB main module**, the messages of
  window contacts, buttons and wall thermostats are no longer answered by the firmware (`Za`)
  but by the integration: immediately and before any further processing, without wake-up
  preamble (`Zf`), through the radio module that delivered the telegram first, in the form used by
  Homegear (flags `02`); all modules get `Za000000`. With a **network main module**
  (Cube, CUN) its firmware still acknowledges, because the route over the network takes too
  long for a window contact; additional modules never acknowledge by themselves any more.

### Fixed

- **Multiple radio modules: devices reported radio errors.** Every module acknowledged telegrams to
  the central unit itself (`Za`); two acknowledgements at the same moment interfered, the device
  repeated and reported radio errors (wall thermostat). Now the firmware's auto-acknowledgement
  is switched off on all modules and the integration acknowledges itself (see
  "Changed").
- **Restart of a device (battery change):** it requests the time and right afterwards
  registers with its central unit again. The time answer with its repetitions (12 s) got in
  the way of the registration answer. Now the running time answer is abandoned on registration,
  the registration is answered immediately and the time is sent afterwards. A wall thermostat
  still asks for date and time on the device: during this entry it accepts no
  radio answer.
- **Wall thermostat reported radio errors after its clock had been set manually.** It then
  passes its time on to the central unit and expects an acknowledgement; without an answer
  it repeats three times and sets the radio error, which stays until the next battery
  change. The integration now acknowledges this time message and sends the correct time
  back if the reported one is off by more than a minute.
- **nanoCUL hung after two send commands in quick succession.** If an answer was abandoned in
  favour of a more urgent one (time answer for the registration of a freshly restarted device),
  the stick got the next telegram while it was still sending the previous one, and stayed silent
  until unplugged and plugged in again. The next telegram now waits until the previous one has been sent.
- **The "eQ-3 MAX!" panel on a phone:** there was no way back out of the device window (it fills
  the screen there, the close cross was under the status bar). Now there is a back button at the
  top left, spacing to the status bar, and the back gesture closes the
  window instead of leaving the page. The tabs can be scrolled sideways, and a
  swipe left or right switches the tab.
- A rejected removal request for a partner that the integration does not know either remained
  as "rejected" and made the device appear as pending.
- Home Assistant 2026.11 reported the deprecated access `DeviceEntry.config_entries`
  (removal in 2027.10) for services and on the "eQ-3 MAX!" panel; the integration now uses
  `config_entry_id`.
- Docs: the FAQ still described acknowledgement by the firmware; new is an entry about
  thermostats that suddenly show 12 °C (their own window-open detection,
  heating automations with snapshot). A wall thermostat's radio error indicator
  also goes off again without a battery change.
- Docs: the firmware's airtime reserve depends on the device (nanoCUL/CUL 9 s, Cube and
  MapleCUN 36 s); 0.6.4 stated 9 s across the board.
- Docs: a flashed Cube that is on the LAN and powered from a USB port of a router, NAS
  or computer restarts again and again during radio operation (bug in a-culfw);
  it belongs on a power supply.

## Earlier versions

Versions up to 0.6.4 are documented in German: [CHANGELOG.de.md](https://github.com/ma-schmitz/eq3_max/blob/main/CHANGELOG.de.md).
