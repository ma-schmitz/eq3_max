# Operating a thermostat


## Modes

| Mode in HA | Device | Effect |
|---|---|---|
| **Heat** (`heat`) | manual | holds the set target |
| **Auto** (`auto`) | the device's week program | the device follows its own program |
| **Off** (`off`) | manual 4.5 °C | frost protection |

Display "Heat (Heating)" or "Heat (Idle)": before the parentheses the mode, inside them the
current action — Heating with the valve open, Idle at 0 %. The valve position only arrives
when the valve moves; after a change, reload the page if needed.

## Presets

| Preset | Effect |
|---|---|
| **None** | normal operation |
| **Comfort** | manual mode at the comfort temperature from the device configuration (from 0.8.0) |
| **Eco** | manual mode at the eco temperature from the device configuration (from 0.8.0) |
| **Boost** | valve wide open briefly (duration and opening see device configuration), then back |
| **Away** | fixed temperature until an end time (mode "temporary") |

**Away** from the thermostat dialog uses the integration options:
away temperature (default **18.0 °C**) and duration (default **24 h**). The end time is
**rounded up** to the next full or half hour (the devices only know :00 and :30).
When it expires, the device returns to its previous mode by itself.

**Back from Away or Boost:** choose mode "Heat" or preset "None" → the last set comfort
value applies again (no matter whether set in HA or on the wheel; the window-open
temperature does not count as a comfort value).

**Comfort and Eco** set manual mode to that value, like the buttons on the device
(telegram 0x40). HA also shows the preset when the target gets there another way; in
automatic mode and with a window open it says "None". Eco is no comfort value: after Away
or Boost it goes back to the last comfort value.

## Commands and acknowledgements

Every command needs about 1 s of wake-up preamble; the device acknowledges it. Until the
acknowledgement, the value is held in `ausstehend` (pending), while the display keeps
showing the last **reported** value. Without an acknowledgement, the command is repeated up
to three times (3 s wait each), so up to ~13 s can pass. If it stays unacknowledged,
`funkfehler` turns on and the command is sent again automatically with the device's next
report. Several quick changes to the same device: only the last one is sent.
