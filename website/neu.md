# What's new in 0.8.0

The biggest update so far: a thermostat card of its own, more control right at the thermostat,
and features only the MAX! Cube had until now.

![Thermostat card](assets/karte/card-kompakt-en-light.png#only-light)
![Thermostat card](assets/karte/card-kompakt-en-dark.png#only-dark)

## Thermostat card

A dashboard card of its own in three layouts (compact, ring to drag, tile) with valve, battery,
radio and window at a glance – and **settings including the week program in a pop-up**, without
leaving the dashboard. → [Thermostat card](handbuch/karte.md)

## At the thermostat

| New | What for | More |
|---|---|---|
| **Presets Comfort and Eco** | one click to the configured comfort or eco temperature, like the buttons on the device | [Operation](handbuch/bedienung.md#presets) |
| **Display set/current on the wall thermostat** | the display shows the current temperature – its menu is locked while paired with a central | [Device configuration](handbuch/konfiguration.md) |
| **Poll current temperature** | radiators report their temperature only on changes; eq3_max nudges them regularly on request – for history graphs | [Device configuration](handbuch/konfiguration.md#poll-the-current-temperature-from-080) |

## Rooms

| New | What for | More |
|---|---|---|
| **Group id** | a target sent to the wall thermostat reaches the whole room from one telegram (measured 1–2 min instead of 2–5 min) | [Links](handbuch/verknuepfungen.md#group-id-from-080) |
| **Room values** | comfort, eco, window and boost apply to all thermostats of a room | [Device configuration](handbuch/konfiguration.md) |

## Safety and reliability

| New | What for |
|---|---|
| **Permissions** | device settings and week programs can be locked for users without admin rights; factory reset, links and radio module for admins only ([Who may do what](handbuch/dienste.md#who-may-do-what-from-080)) |
| **Several radio modules no longer transmit at once** | room-wide changes through two modules overlapped and ended as radio errors |
| **Eco button** | a late repeat no longer switches a light back |
| **Explanations** | every setting on the "eQ-3 MAX!" panel and in the card has a hover text and an ⓘ |

## Recognised, not controlled yet

- **Plug adapter** (BC-TS-Sw-Pl) is paired and shown; captures help to add it.

All details: [Changelog](changelog.md).
