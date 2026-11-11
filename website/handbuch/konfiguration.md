# Device configuration


On the device page of each thermostat under **Configuration**:

| Entity (example `ht_wohnzimmer`) | Value | Radiator | Wall |
|---|---|---|---|
| `number.…_komfort` / `_eco` | Comfort/eco temperature (4.5–30.5 °C) | ✓ | ✓ |
| `number.…_maximal` / `_minimal` | Limits for operation on the device | ✓ | ✓ |
| `number.…_offset` | Correction of the measured temperature (−3.5…+3.5 K) | ✓ | ✓ |
| `number.…_fenster_temperatur` / `_fenster_dauer` | Temperature and duration with the window open | ✓ | ✓ |
| `select.…_boost_dauer` | Boost duration | ✓ | ✓ (from 0.7.0) |
| `number.…_boost_ventil` | Valve opening during boost | ✓ | – |
| `select.…_entkalkung_tag`, `number.…_entkalkung_stunde` | Weekly valve decalcification | ✓ | – |
| `number.…_ventil_max` / `_ventil_offset` | Maximum opening, valve offset (%) | ✓ | – |

**Good to know:**

- The devices only know **complete sets** (all temperatures or all valve values). If you
  change one value, the integration sends the whole set with the other stored values.
- The devices do **not** report their configuration back. What is shown is the last
  **acknowledged** state; a value sent but not yet acknowledged is held in `ausstehend` (pending).
- Attribute **`quelle`** (source): `homegear` (from the import), `werksvorgabe` (assumed
  factory default, never confirmed) or `gesetzt` (acknowledged by the device). When factory
  defaults are sent along, the log says "sending assumed factory values along: …"; after the
  acknowledgement they are `gesetzt`.
- Values must lie on the grid (0.5 °C or 5 min/5 %); 21.3 °C is rejected.
- Every change costs one radio telegram; several quick changes → only the last state.
- A configuration change leaves the device's week program untouched.
- **Room values apply to the whole room (from 0.7.0).** Each device stores its settings
  by itself, and the devices do not sync them with each other: the wall thermostat counts
  down the boost by its own duration, each radiator by its own. Without a central unit you
  set these values for the room in the wall thermostat's menu; once paired to a central
  unit the menu is locked, and then it is the central unit's job. So when you change a room
  value on one thermostat, the integration also sets it on the other thermostats linked
  with it through a wall thermostat (the wall thermostat itself and its radiators):

    | Room value (shared) | stays per device |
    |---|---|
    | Comfort and eco temperature | Temperature offset |
    | Minimum and maximum temperature | Maximum valve opening, valve offset |
    | Window-open temperature and duration | |
    | Boost duration and boost valve opening | |
    | Decalcification (day, hour) | |
    | Week program ([Services](dienste.md)) | |

    This costs one telegram per set for each affected device. Devices whose values already
    differ today stay that way until the value is changed once. Thermostats without a wall
    thermostat stay on their own.
