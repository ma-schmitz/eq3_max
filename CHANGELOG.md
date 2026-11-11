# Changelog

**English** · [Deutsch](https://github.com/ma-schmitz/eq3_max/blob/main/CHANGELOG.de.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
