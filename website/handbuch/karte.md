# Thermostat card

A dashboard card of its own for MAX! thermostats:
`eq3-max-thermostat-card`. Since eq3_max 0.11.0 it ships with the integration (before: a
repository of its own). It shows at a glance what the built-in HA card does not – valve
position, battery, radio reception, linked window – and lets you change settings and the week
program right in the dashboard.

![Thermostat card, compact layout](../assets/karte/card-kompakt-en-light.png#only-light)
![Thermostat card, compact layout](../assets/karte/card-kompakt-en-dark.png#only-dark)

## Installation

There is nothing to install: the integration brings the card along and enters it itself
under Settings → Dashboards → Resources (`/eq3_max_static/eq3-max-thermostat-card.js`), in
the matching version with every update. Card and integration share one version number.

In the dashboard **Add card → "eQ-3 MAX! Thermostat"**, pick the thermostat. If the card
does not show up after an update, reload the page in the browser once.

!!! note "Resources in configuration.yaml"
    If you keep the dashboard resources in `configuration.yaml` (`resource_mode: yaml`),
    there is nothing to do either: the integration then loads the card itself.

!!! info "Card installed through HACS so far?"
    The separately installed card stays in use until it is removed; the integration does
    not load its own on top and reports this under Settings → Repairs. Remove the card in
    HACS (installed by hand: delete the entry under Resources and the file in
    `/config/www/`) and restart Home Assistant. Nothing changes in the dashboards.

```yaml
type: custom:eq3-max-thermostat-card
entity: climate.living_room
layout: kompakt      # kompakt | ring | kachel
name: Living room    # optional, otherwise the device name
show_modes: true     # optional, show the mode buttons
temperature_sensor: sensor.living_room_temperature  # optional
humidity_sensor: sensor.living_room_humidity        # optional
```

It is suggested for MAX! thermostats under "Community" in "Add card → By
entity".

### External sensors

A thermostat on the radiator often measures warmer or colder than the room. `temperature_sensor`
shows a room sensor as the current temperature instead; when it is unavailable, the card falls
back to the thermostat's value. `humidity_sensor` shows the humidity. Both can be picked in the
visual editor.

This is **display only**: the thermostat keeps regulating on its own sensor. So its value stays
small below ("Thermostat 21.4 °C", in the ring as a tooltip on "Now") – a large gap explains why a
room gets warmer or colder than expected.

## Three layouts

| Layout | Picture | For |
|---|---|---|
| `kompakt` (default) | ![](../assets/karte/card-kompakt-en-light.png) | dashboard grids; narrow cards show the modes as one row of symbols |
| `ring` | ![](../assets/karte/card-ring-en-light.png) | like the HA thermostat card: **set the target by dragging or tapping the ring**, valve opening inside |
| `kachel` (tile) | ![](../assets/karte/card-kachel-en-light.png) | landscape for tablets and wall panels, valve as a vertical level |

## Operation

- **−/+** changes the target in 0.5 °C steps (4.5–30.5 °C). A target not acknowledged yet
  counts, so several taps add up. In Auto the new value holds until the next switch point, in
  manual mode permanently (see [Operating a thermostat](bedienung.md#changing-the-setpoint)).
- **Mode buttons:** Manual, Auto (week program), Comfort, Eco, Boost, Off. When the thermostat
  is set to away, "Away until …" shows; a mode button ends it.
- **Click the current temperature** to open Home Assistant's dialog with its history, **click the
  valve** for the valve history. In the ring, tap the centre for the history; the humidity and valve lines open their own.
  Only the arc itself sets the target (0.1.2+; before, a tap on the valve set 30.5 °C).
- The coloured stripe on the left shows the state: orange = heating, amber = window open,
  red = battery low or radio error.

## Symbols

| Symbol | Meaning |
|---|---|
| window closed / open (amber) | linked window contact of the device or its room – or the thermostat's own open-window detection |
| battery / battery alert (red) | MAX! only reports "ok" or "low" |
| signal 3 / 2 / 1 (amber) / off (red) | above −70 dBm, −70…−85, below −85 dBm, radio error (hover: dBm) |
| link | linked (hover: with whom) |
| lock | operation lock on the device |
| hourglass | command sent, not acknowledged yet |
| "2 min ago" | when the device last reported |

**Your own icons** (from 0.11.0): the card takes over what is set for the entity in Home
Assistant. An icon chosen there for the thermostat (for underfloor heating, say) replaces
radiator or thermostat in the card's header. A linked contact with the device class "Door"
or "Garage door" shows as a door or garage door and reads "Door open"; if the contact has an
icon of its own, that one is shown. With several linked contacts an open one decides the
icon. Both are set in the settings of the entity in question ("Icon" and "Show as").

## Settings in the pop-up

The **cog** opens the settings without leaving the dashboard (from the bottom on phones).
Every value has a hover text and an **ⓘ** that unfolds the explanation.

![Pop-up, Window tab](../assets/karte/popup-temp-en-light.png#only-light)
![Pop-up, Window tab](../assets/karte/popup-temp-en-dark.png#only-dark)

| Tab | Content |
|---|---|
| **Temperatures** | comfort, eco, maximum, minimum, offset; on radiators "Poll current temperature" |
| **Window** | window-open temperature and duration; which window contacts are linked and their state |
| **Boost & valve** | boost duration and opening, decalcification, valve maximum/offset – on the wall thermostat **Boost & display** (boost duration, display set/current) |
| **Week program** | see below |
| **Info** | battery, radio per module, last seen, links, operation lock, serial number, firmware |

Changed values are marked blue and go out only with **Apply** – each set as one telegram. Then
"Sent – waiting for acknowledgement" shows until the device confirms ("Acknowledged by the
device"). Values marked **"applies to the room"** are passed on by eq3_max to the linked
thermostats.

### Week program

![Pop-up, week program](../assets/karte/popup-week-en-light.png#only-light)
![Pop-up, week program](../assets/karte/popup-week-en-dark.png#only-dark)

- At the top the week as coloured bars (blue = cool, orange = warm). The devices do not report
  their program: shown is what they acknowledged last; unknown days are grey.
- Tap a day → edit its periods (end time in 5-minute steps, temperature, insert, delete). An
  unknown day starts with the factory program as template.
- **Write to:** choose the days the program goes to ("all" for the whole week).
- **Copy from …** loads the day of another thermostat into the editor.
- **Also goes to:** eq3_max writes the program to the thermostats of the room as well.
- Every day is one radio telegram; with little airtime left a week can take a few minutes. The
  progress shows in the tab ("writing: Tu, We").

## Who may do what

Temperature, mode and presets are open to all users. Device settings and week programs can be
locked for users without admin rights in the [options](dienste.md#options) of eq3_max; the
card then only shows them the values ("View only"). The integration enforces this itself, so it
also applies outside the card.

## Where the card gets its data

The card needs neither admin rights nor settings of its own: it finds all entities of a
thermostat through its device (renamed entities do not matter) and reads window, room, week
program and permissions from attributes of the thermostat (`fenster`, `raum`,
`wochenprogramm`, `wochenprogramm_schreibt`, `wochenprogramm_fehler`, `einstellungen_frei`,
`wochenprogramm_frei`; not recorded). It writes through the normal entities and the service
`eq3_max.set_week_profile`.
