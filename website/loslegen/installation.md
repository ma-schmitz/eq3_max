# Installation

## Requirements

- **Home Assistant 2026.8** or newer (the integration's own logo appears from 2026.9).
- A **radio module with culfw** and MAX! support, see [Hardware](hardware.md):
  a nanoCUL via USB or a MAX! Cube flashed with a-culfw on the network.
- Coming from Homegear or an older installation: read [Migration](../umstieg/index.md) first.

## Installing

=== "Via HACS"

    1. Open HACS → menu at the top right → **Custom repositories**.
    2. Enter the address of this repository, category **Integration**.
    3. Search for **eQ-3 MAX!** and download it.
    4. Restart Home Assistant.

=== "Manually"

    1. Copy the folder `custom_components/eq3_max` from the repository to
       `/config/custom_components/` on the HA box (SSH add-on or Samba).
    2. Restart Home Assistant.

Then go to **Settings → Devices & services → Add integration**, search for
"eQ-3 MAX!" and follow the [setup](einrichtung.md).

!!! tip "Updates"
    Reloading the integration does not load new Python code. After every update,
    **restart** Home Assistant.
