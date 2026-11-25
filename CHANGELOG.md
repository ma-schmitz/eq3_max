# Changelog

**English** · [Deutsch](https://github.com/ma-schmitz/eq3_max/blob/main/CHANGELOG.de.md)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.11.0] – 2026-11-25

The thermostat card is now part of the integration, and both the panel and the card take
their icons from Home Assistant.

### Added
- **The thermostat card ships with the integration.** The card `eq3-max-thermostat-card`
  now lives in the integration, which enters it as a dashboard resource; it is always there
  in the matching version and no longer needs to be installed separately. Card and
  integration share one version number from now on. Existing dashboards keep working
  unchanged (`type: custom:eq3-max-thermostat-card`). Where resources are kept in
  `configuration.yaml`, the integration loads the card itself. Removing the integration
  removes the entry again.
- **Icons from Home Assistant** (discussion #18). The "eQ-3 MAX!" panel and the card show
  the icon chosen for the entity in Home Assistant, for example one of your own for
  underfloor heating. A window contact with the device class "Door" or "Garage door" shows
  as a door or garage door, open and closed; the card then also says "Door open". Both are
  set as usual in the entity's settings ("Icon" and "Show as").
- **Collapse and arrange areas** (discussion #18). On the "eQ-3 MAX!" panel a click on an
  area's heading folds its devices away and back; the browser remembers this, so other
  areas can be closed on the phone than on the desktop. "Arrange" lets you move areas and
  the devices within them with arrow buttons. The order is stored per user in Home
  Assistant and applies on every device; new areas and devices line up behind, and "Reset
  order" brings back the alphabetical one.

### Changed
- **"Radio module waiting for airtime"** (#20). The panel now tells who holds a command
  back: the integration's airtime limit ("waiting for airtime") or the radio module
  itself, whose firmware keeps the 1% rule and refuses the command with `LOVF` ("radio
  module waiting for airtime"). The hint on the radio module adds that the setting "Limit
  airtime" does not change that.

### Fixed
- **Card, layout "kachel": text ran into the target buttons.** With an external sensor and
  humidity, the line below the reading ("47 % · Thermostat 20.5 °C") reached into the target
  buttons on narrow cards such as on a phone. It now sits below the row with reading and
  buttons and has the full width.

### Moving from the separately installed card
If you installed the card as its own repository in HACS (or by hand under `/config/www/`),
you keep it for now: the integration sees the existing entry, does not load its own card on
top and reports this under Settings → Repairs. Remove the card in HACS and restart Home
Assistant – the integration then enters its card, and nothing has to change in the
dashboards.

## [0.10.1] – 2026-11-22

Less airtime, and the airtime limit holds across a restart.

### Changed
- **Virtual wall thermostat: cadence by the number of rooms.** Up to two rooms per radio
  module the room temperature still goes out every 5 minutes. With more rooms the cadence
  of all rooms of that module slows in proportion (three rooms: every 7.5 minutes), 8 minutes
  at most. Three rooms then need about 27 instead of 40 s of airtime per hour and fit into a
  module's 36 s. A room that sends addressed (no group) counts once per thermostat. A
  thermostat waits just under 10 minutes for its wall thermostat: if a telegram is lost on
  the slower cadence, it regulates on its own sensor until the next one. The log names the
  cadence whenever it changes.
- **Week program: unchanged days are not sent again.** A day a thermostat acknowledged
  exactly like this is not sent to it again; this applies per device, also to the room's
  other thermostats. A day whose telegrams went out without its acknowledgement (a failed or
  aborted write, also before a restart) always goes out. The service
  `eq3_max.set_week_profile` has the new field `force` (write unchanged days too), e.g.
  after the program was changed at the device. "Write factory program" and "Write fixed
  temperature" on the page always write everything.

### Fixed
- **The airtime of the last hour survives a restart.** The bookkeeping used to start at zero
  after a restart of Home Assistant or the integration; with "Limit airtime" up to 72 s could
  go out within one hour. The transmissions of the last hour are now stored and counted
  again at start.
- **`ZERR…` lines of the radio module no longer count as reception.** culfw reports the
  state of its transmitter after a telegram that way. The line used to count as a received
  telegram and could hide that a radio module had stopped hearing.

## [0.10.0] – 2026-11-21

### Added
- **Virtual window contact.** On the "eQ-3 MAX!" panel, "Create virtual device" creates a
  window contact that exists only in Home Assistant. The source is any `binary_sensor` (for
  example a Zigbee contact); "open" and "closed" go to every linked radiator thermostat with
  acknowledgement (the thermostat confirms receipt). If a thermostat does not acknowledge, the
  state is repeated every 5 minutes, after three failures in a row every 15 minutes, and once
  when the radio module is back; two state changes to the same thermostat are at least one
  minute apart, and at most 12 telegrams per hour go to each thermostat. Nothing is sent
  periodically. After a restart it only sends if the state differs from the last delivered
  one. Works with any radio module. You do not choose a radio module when creating it: a
  virtual device sends through the module of the thermostat concerned.
- **Virtual wall thermostat.** The source is a temperature `sensor` (°F and K are converted).
  The thermostats of a room regulate on that temperature instead of their own sensor. A
  source that has not reported for 3 hours counts as unavailable; sensors that only write a
  new state when the value changes (template or helper sensors) can therefore drop out at
  times; better use a device sensor that reports regularly.
- **Virtual wall thermostat: temperature.** The temperature is sent every 5 minutes, fixed
  and on time. A thermostat waits just under 10 minutes for its wall thermostat and then
  regulates on its own sensor (with a radio error) until the next telegram arrives. A window
  change goes out at once (at most once a minute). One telegram (a radio message) is enough
  for the whole room if all its thermostats share a group and a radio module (the
  integration assigns the group when you link), otherwise one is sent to each thermostat in
  turn (about 13 s per hour per thermostat; with more than one thermostat they regulate on
  their own sensor at times; the panel then shows a hint and offers "Assign for the
  room"). A thermostat that leaves the
  virtual room loses its group ID. A falling temperature is passed on in steps of at most
  1.0 °C per telegram so that the thermostats' built-in open-window detection does not
  trigger.
- **Virtual wall thermostat: setpoint and boost.** Setpoints stay in sync across the room: a
  change at a handwheel reaches all thermostats of the room after a few seconds, and so does a
  setpoint set in Home Assistant. Auto is only available with a complete week program
  written through eq3_max (every temperature telegram also sets the thermostats' setpoint);
  without one the room runs manually, and the panel says so. In automatic mode the room
  follows the week program; a change at the handwheel or in Home Assistant holds until the
  next switch point. An away period ends by itself at the set time; then what applied before
  applies again. Boost stays with the thermostat where it was
  started (the wall thermostat keeps showing the room's mode); a boost on the virtual wall
  thermostat applies to the whole room and ends with the thermostats' boost duration, after
  an hour at the latest.
- **Virtual wall thermostat: first link.** The first thermostat you link hands its setpoint,
  mode, week program and comfort/eco/window settings over to a virtual wall thermostat that
  has no setpoint of its own yet; what was already entered there stays, and a window-open
  temperature or a boost does not become the room's setpoint. Thermostats
  linked later get the room's setpoint and mode. Their week program is not overwritten
  unasked (the panel shows a hint and offers to copy the room's program).
- **Virtual devices: good to know.** A virtual wall thermostat costs about 13 s of airtime per
  hour (of 36 s per radio module); one radio module is enough for two. With the option "Limit
  airtime to 36 s" 10 s per hour stay free for commands; without it the radio module itself
  decides. The thermostats linked with a virtual wall thermostat must be on a radio module
  connected by USB or serial, not on a network module; there is no eco button. A long job
  can leave a room without temperature for up to about an hour. If
  Home Assistant is not running, nobody answers for the wall thermostat: the thermostats keep
  heating with their own sensor, but a setpoint change at the handwheel can leave them
  silent for up to an hour; there is no technical remedy. The same applies while the
  integration is not loaded (radio module missing, integration disabled or reloading).
  Before going back to a version older than 0.10.0, remove all virtual devices: an older
  version takes them for real devices at an address nobody answers. "Remove" first removes the links.
  "Remove anyway" deletes at once; a thermostat that still knows the link can then fall
  silent for up to an hour. Details in the manual under "Virtual devices".

### Changed
- **Change in behaviour: a setpoint in Auto holds until the next switch point.** Changing the
  temperature in Home Assistant (or on the thermostat card) of a thermostat that runs in Auto
  now does the same as the handwheel: the value holds until the next switch point of the week
  program, the thermostat stays in Auto and follows its program again afterwards. Until now
  every change from Home Assistant switched to manual for good. The same applies to the
  presets "Comfort" and "Eco". To keep a value permanently, switch to "Heat" (manual) first or
  send `hvac_mode: heat` with the temperature. `hvac_mode: auto` with a temperature returns to
  the program and holds that temperature until the next switch point (until now the
  temperature was ignored there). The preset "None" in Auto ends such a change and returns to
  the program; "Comfort" and "Eco" stay shown in Auto while the value holds. If the command
  does not reach the thermostat in time – by the next switch point or, when eq3_max does not
  know the week program, within 15 minutes – it is no longer repeated; instead the thermostat
  goes back to plain Auto (its program). While such a change from Home Assistant holds,
  polling the current temperature pauses for that thermostat (at most 12 hours). Nothing changes in manual mode
  or during "Away" or "Boost". In the room of a virtual wall thermostat without a week program
  every setpoint stays manual.
- **Installation through the HACS search.** eq3_max has been in the HACS default catalog since
  2026-11-19. README and website therefore lead with searching for "eQ-3 MAX!" in HACS; the
  detour via "Custom repositories" is gone.

### Fixed

- **Week program for a room day by day: no thermostat of the room is left with missing days
  any more.** When days were written for a room in quick succession (say Monday to Friday
  first, then the weekend), a thermostat of the room still busy with the first days did not
  get the others – only a warning in the log. Now the integration writes them to it right
  afterwards; until then the "Week program" tab shows them as outstanding. For a virtual wall
  thermostat the call waits until the room's thermostats are done; if one fails, the reason
  is shown at that thermostat.
- **Week program for a whole room: each thermostat is written once.** When the wall
  thermostat and its radiators were selected together (say by area in the "Week program"
  tab, or when copying), the radiators got the program twice – once as room mates, once as a
  target of their own – which cost airtime. The source of a copy within a room is no longer
  written again.

## [0.9.3] – 2026-11-19

### Added
- **Look into the queue.** "Queue N" in the header of the "eQ-3 MAX!" page is now a button:
  a click unfolds the list of pending commands – per command the device, the kind (setpoint
  / mode, week program with weekday, settings, link with partner, time, factory reset …) and
  the state ("being sent", "waiting for airtime", "waiting", from the second attempt on with
  a counter). The order is the sending order; the command on air comes first. With several
  radio modules the list is grouped by module. The WebSocket overview (`eq3_max/overview`)
  carries the new field `pending` per radio module for this.

### Fixed
- **Page: "waiting for airtime" not centred.** With little room the hint at the radio module
  wrapped inside and was left-aligned then. It now stays on one line and centred; when space
  runs out it moves to the next line as a whole.

## [0.9.2] – 2026-11-19

### Added
- **Pairing: warning for devices still paired to another central.** Such a device (bought
  used, from another MAX! system) sends its pairing request to its old central, which the
  integration never answers – so far without a word. While the pairing window is open it
  now logs one warning per device and the "eQ-3 MAX!" panel shows a hint below the pairing
  button: reset the device to factory settings and pair it again. With the window closed it
  stays silent, so the neighbours' MAX! devices do not fill the log.
- **Cancel link requests.** An open or failed link request can now be dropped without
  sending anything: button "Cancel request" on the "eQ-3 MAX!" page (tab Links), service
  `eq3_max.cancel_link` and WebSocket command `eq3_max/cancel_link`. Until now a request that
  could never complete – e.g. a removal the device refused, towards a partner deleted since –
  stayed for good and could only be removed by stopping Home Assistant and editing the
  storage file.

### Changed
- **Links and requests to deleted devices are dropped at startup,** as far as nothing can be
  done about them any more: a link without an open request, a removal the device refused, an
  addition. A removal still waiting stays – it can still arrive (e.g. at a window contact
  after its thermostat was reset and deleted) and can otherwise be dropped with "Cancel
  request". After "Delete device" the other devices used to keep the deleted one as partner
  and its open requests.
- **Page "eQ-3 MAX!": links with their area.** Partners and open requests read "name · area",
  as the selection list already did (discussion #12).

### Fixed
- **Page "eQ-3 MAX!": the week program could not be edited.** "Add point" did nothing, and for
  a device without a valid program (e.g. after a factory reset) the tab did not open at all:
  the check of the points crashed as soon as it had something to report
  (`t is not a function`). The thermostat card was not affected (#13).

The pairing warning and cancelling requests were contributed by @BSass (#14, #15).

## [0.9.1] – 2026-11-17

### Added
- **Page "eQ-3 MAX!": targets 4.5 and 30.5 °C optionally as "Off" and "On",** as on the
  devices' display. Turn it on under Settings → Devices & services → eQ-3 MAX! → Configure →
  Settings; without the option the numbers stay. The thermostat entities still report the
  temperature (#11).

## [0.9.0] – 2026-11-17

### Changed
- **Entities of a predecessor are only taken over after confirmation.** Until now the setup
  replaced the registry entries of the predecessors (`homematic`, `max_cul`) on its own. Now it
  leaves them alone and raises a repair that lists them; only **Submit** removes them and moves
  entity ID, area, name, icon, aliases and labels to the eQ-3 MAX! entities. Until then these
  sit next to them with a suffix (`_2`).
- **Template entities are never touched.** A template entity on an entity ID eQ-3 MAX! would
  like (e.g. `sensor.<name>_ventil`) keeps its place; delete it yourself to free the ID.

## [0.8.6] – 2026-11-17

### Fixed
- **A window contact reporting to a partner proves the link (#6).** A contact took a link,
  but its acknowledgement never arrived, so the link stayed "waiting" or "failed" although
  thermostat and wall thermostat already followed the window. A telegram from the contact (or
  eco button) to the partner now counts as the acknowledgement; nothing is sent again.
- The telegram trace shows the state of each waiting link change of a sleeping device.

### Changed
- **Copying a week program: targets grouped by area, with a "whole area" tick** (discussion #9).
  Devices of the same name are told apart by their room. A note says that thermostats linked
  in a room get the program along with it, so one device per room is enough.

## [0.8.5] – 2026-11-16

### Fixed
- **A late repeat of an eco button press no longer counts as a new press.** A button that
  misses the acknowledgement sends the press again with the same number, on 15.11.2026 still
  52 s later, which toggled a light back on (the filter only covered 30 s). The same number
  as the last press now counts as that press for 10 minutes; each repeat shows in the
  telegram trace.
- **One link per teach-in press.** After taking one link a window contact stopped listening,
  and the next one went out nine times in vain (#6). Now the next press brings the next link;
  once the contact has a partner, the others also follow on the next window event.
- **"To the editor" on the week program shows temperatures with a decimal (#10).** 17.5 °C
  came into the editor as "17,5" in German, which a number field does not take, so it stayed
  empty.

## [0.8.4] – 2026-11-15

### Fixed
- **Window contacts without a partner can be linked (#6).** Such a contact only talks to the
  central and goes back to sleep on its acknowledgement, so a link waited forever. Now the
  waiting links go out as soon as the contact reports to its central again: press its
  teach-in button briefly (LED blinks). It listens for a few seconds then, the link is retried
  every half second meanwhile. Links given up after 5 rounds are sent again then as well.
  (New batteries are not enough: a window contact does not report to its central after a
  restart.)
- A window contact no longer gets the time after reporting to its central: it has no clock
  and never acknowledged it (four useless sends).
- **Link changes for sleeping devices count rounds per event.** Retries and reports to
  partners within a few seconds count as one of the 5 rounds; before, one window event used up
  several, and a link was given up after two events.
- **The panel suggests the pairing button for waiting window contacts** ("press its pairing
  button briefly (or open and close the window)") – the only way for a contact without partners.

## [0.8.3] – 2026-11-14

### Fixed
- **Window contacts keep the time they really opened or closed across a reload or restart.**
  Home Assistant dated every window to the reload, so schedules waiting for a window to stay
  closed (e.g. the Advanced Heating Control blueprint) treated every room as "window just
  closed" and skipped a setback in that time.

### Changed
- **Link changes for window contacts and eco buttons give up after 5 reports of the device
  without acknowledgement** and show as "failed"; "Send again" on the "eQ-3 MAX!" page starts
  over. Before, every report of a device that never took the change cost airtime for good
  (e.g. behind a radio module whose firmware acknowledges, #6, discussion #8).

## [0.8.2] – 2026-11-14

### Added
- **Set the area right on the "eQ-3 MAX!" page**: the device drawer has an area selection next
  to the device type (writes to Home Assistant's device registry) – no jump to the device page
  for new devices (#7).

### Changed
- **The pairing button (`button.eq3_max_anlernen`) is for administrators only**, like linking and
  factory reset (automations still may). The pairing on the "eQ-3 MAX!" page always was.

## [0.8.1] – 2026-11-14

### Added
- **Area in the partner list** of the "eQ-3 MAX!" page ("Radiator · Living room"): devices with
  the same name can be told apart (#7).
- **"Link with all devices in the area"**: links a device with all suitable devices in the same
  Home Assistant area (wall thermostat ↔ radiators, window contact/button ↔ thermostats); the page
  lists the links before they are requested (#7).

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
