# What's new

The main additions of the last versions – all details in the [changelog](changelog.md).

## 0.11 – Thermostat card included

![Thermostat card](assets/karte/card-kompakt-en-light.png#only-light)
![Thermostat card](assets/karte/card-kompakt-en-dark.png#only-dark)

| New | What for | More |
|---|---|---|
| **The thermostat card ships with the integration** | nothing to install separately; the integration enters the card as a dashboard resource itself, always in the matching version | [Thermostat card](handbuch/karte.md) |
| **Icons from Home Assistant** | an icon of your own (say, for underfloor heating) and "Show as" door or garage door appear on the panel and in the card | [Panel](handbuch/seite.md) |
| **Collapse and arrange areas** | sort the "eQ-3 MAX!" panel to match your home, keep only the rooms open on the phone that you need | [Panel](handbuch/seite.md) |
| **"Radio module waiting for airtime"** | shows whether the integration holds back or the radio module itself refuses | [Panel](handbuch/seite.md) |

!!! info "Card installed through HACS so far?"
    Remove it there and reload the integration – nothing changes in the dashboards. Until
    then the old card stays in use, and Repairs shows a hint.

## 0.10 – Virtual devices and less airtime

| New | What for | More |
|---|---|---|
| **Virtual window contact** | any contact in Home Assistant (e.g. Zigbee) reports "open" straight to the thermostats | [Virtual devices](handbuch/virtuelle-geraete.md) |
| **Virtual wall thermostat** | any temperature sensor regulates a room like a real wall thermostat | [Virtual devices](handbuch/virtuelle-geraete.md) |
| **Auto and manual as on the device** | a target in auto mode applies until the next switching point, in manual mode for good | [Operation](handbuch/bedienung.md) |
| **Less airtime** (0.10.1) | unchanged days of the week program are not sent again; the airtime survives a restart | [Services](handbuch/dienste.md) |
| **Installation through the HACS search** | eq3_max is in the HACS default catalog | [Installation](loslegen/installation.md) |

## 0.9 – More overview on the panel

| New | What for |
|---|---|
| **View the queue** | which command is on air right now and what is still waiting |
| **Warning while pairing** | a device still paired to another central is recognised |
| **Cancel link jobs** | a stuck job can be withdrawn |
| **"On"/"Off" instead of 30.5/4.5 °C** | optionally like on the devices' display |
| **Takeover only after confirmation** | entities of Homegear or max_cul are taken over only after a repair is confirmed |

## 0.8 – Rooms like the Cube

| New | What for | More |
|---|---|---|
| **Presets comfort and eco** | one click to the set comfort or eco temperature, like the buttons on the device | [Operation](handbuch/bedienung.md#presets) |
| **Group id** | a target sent to the wall thermostat reaches the whole room in one telegram | [Links](handbuch/verknuepfungen.md#gruppen-id-ab-080) |
| **Room values** | comfort, eco, window and boost apply to all thermostats of a room | [Device configuration](handbuch/konfiguration.md) |
| **Display set/current on the wall thermostat** | the display shows the current temperature | [Device configuration](handbuch/konfiguration.md) |
| **Poll the current temperature** | radiators report their temperature regularly – for history graphs | [Device configuration](handbuch/konfiguration.md#ist-temperatur-abfragen-ab-080) |
| **Permissions** | device settings and week programs lockable for users without admin rights | [Who may do what](handbuch/dienste.md#wer-darf-was-ab-080) |
| **Thermostat card of its own** | valve, battery, radio and window at a glance, settings and week program in a pop-up | [Thermostat card](handbuch/karte.md) |
