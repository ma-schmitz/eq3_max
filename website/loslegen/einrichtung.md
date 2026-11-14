# Setup

Settings → Devices & services → **Add integration** → "eQ-3 MAX!". The dialog
asks in turn:

## 1. Connection

=== "USB stick"

    Choose the stick under `/dev/serial/by-path/…`. **Never `by-id`**: many CUL sticks
    have no serial number, two identical sticks could not be told apart that way.

=== "Search the network (from 0.7.0)"

    Queries every address in Home Assistant's network on port **2323** (at most 254,
    a few seconds) and lists whatever answers as culfw, with address and firmware ID,
    e.g. `192.0.2.60 – V 1.26.08 a-culfw … CUBe`. Select it, continue. Modules already
    set up are not listed. A module in a different network (VLAN) or with a changed port
    is not found; for that there is manual entry.

    **Home Assistant also reports a flashed MAX! Cube by itself** under
    Settings → Devices & services → "Discovered" (it is recognised by its network address
    `00:80:41:…`). If there already is an eQ-3 MAX! entry, the Cube can be added to it
    right there as a further radio module.

=== "Network: enter the address"

    Host (name or IP only, no `http://`) and port, default **2323**. Before continuing,
    the dialog sends `V`; if no culfw answers within 5 s, it shows
    "No culfw answered (no reply to V)."

## 2. Central address

Six hex digits, default `C0FFEE`. MAX! devices remember the address of their central unit.

!!! important "Keep the previous address when migrating"
    If you come from Homegear or FHEM, enter **the same address** as before. Then no
    device has to be paired again. How to find it is described under
    [From Homegear](../umstieg/homegear.md#vorbereiten).

## 3. Import devices

| Source | When |
|---|---|
| **JSON** | Export file from Homegear or an earlier installation (recommended when migrating) |
| **Homegear** | Query Homegear directly while it is still running |
| **none** (`keine`) | New installation, devices are [paired](../handbuch/anlernen.md) afterwards |

The entity IDs of the previous `homematic` integration are kept.

## Options

Later under **Configure**:

| Menu item | Content |
|---|---|
| "Settings" | Airtime brake (36 s per hour and module, on for new entries), away temperature (18.0 °C) and away duration (24 h), from 0.8.0 the permissions for users without admin rights |
| "Change connection" | USB ↔ network or a different port/host, without creating the integration again |
| "Radio modules" | add and remove further sticks or Cubes, see [Multiple radio modules](../handbuch/funkmodule.md) |

A changed connection is checked with `V` as during setup and reloads the
integration; the settings take effect without a restart.
