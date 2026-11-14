# Several radio modules


If one radio module does not cover the whole house, add more, e.g. one per floor.
USB sticks and flashed Cubes (network) can be mixed.

!!! abstract "How it works – like the interfaces in Homegear"

    - All modules work with **the same central address**. To the devices there is still
      only one central unit; none of them is paired again.
    - Each device has **one assigned module**. All commands to the device go through it:
      targets, configuration, links, factory reset, answers to time requests.
    - **Receiving works through all modules.** If two modules hear the same telegram, it is
      evaluated only once. The integration remembers the signal strength per module.
    - **Switching is purely a setting.** Nothing is sent to the device; queued commands
      move along to the new module.
    - Each module has **its own radio budget** (1 % = 36 s per hour). If a module is waiting
      for airtime, its tile says so.
    - **Only one module transmits at a time** (from 0.8.0) and waits for its acknowledgement
      before another one goes. Two modules side by side would otherwise overlap – on a
      room-wide change (wall thermostat on one module, radiator on the other) on every attempt.

**Adding a module:** Configure → "Radio modules" → "Add USB stick", "Search the network and
add" (from 0.7.0, lists the culfw modules in your own network) or "Add network CUL", with
a name (e.g. "upstairs"). A flashed Cube that Home Assistant discovered by itself can also
be added directly from "Discovered" as a further radio module. The module is checked with
`V`, then the integration reloads. The first module is called "Main module"; it is the
connection from the initial setup.

**Renaming a module** (from 0.7.0): on the "eQ-3 MAX!" panel click the pencil on the module's
tile, enter the name and confirm with Enter or the check mark. Or Configure → "Radio
modules" → "Rename a radio module", choose the module, enter the new name. This also works for the main module, e.g. "Ground
floor" instead of "Main module". Only the displayed name changes (device page, selection
`select.*_funkmodul`, "eQ-3 MAX!" panel); entity IDs, the `rssi_<modul>` attributes and the
device assignments stay.

**Assigning a device to a module**, in one of two ways:

- "eQ-3 MAX!" panel → click the device → tab **Radio module**. It shows for each module how
  well it last heard the device; the best one is marked. "Assign" switches.
- Entity `select.<device>_funkmodul` (also from automations). Its attributes
  `rssi_<modul>` show the signal strength per module.

Newly paired devices stay on the module that heard their pairing request first. To decide
yourself, choose the module when pairing on the "eQ-3 MAX!" panel (see
[Pairing devices](anlernen.md)).

**Removing a module:** Configure → "Radio modules" → "Remove radio module". Its devices
then send through the main module again. If only the main module is left, the
`select.*_funkmodul` entities disappear.

**What you see:**

- In HA each additional module is a device of its own ("eQ-3 MAX! radio module upstairs");
  the MAX! devices sit under their module.
- `binary_sensor.eq3_max_verbunden` is only on when **all** modules are connected. The
  attribute `funkmodule` shows each one separately. `sensor.eq3_max_sendezeit_1h` shows the
  most loaded module, the attribute `funkmodule` all of them.
- If an additional module fails, there is a repair issue of its own, "CUL not reachable",
  with its target. Devices on other modules keep working. Pairing works as long as any
  module is connected.

!!! note "Acknowledgements to the devices: exactly one per report"
    Window contacts, buttons and wall thermostats expect an acknowledgement for their report
    to the central unit. Up to 0.6.x every culfw gave it by itself (`Za`). If two modules hear
    the same device, both then send at the same instant and interfere: the device gets no
    acknowledgement, repeats and reports a radio error (observed in operation with a wall
    thermostat). From 0.7.0 only one place answers:

    - **Main module on USB:** the integration acknowledges itself, through the module that
      delivered the report first; the firmware's auto-acknowledgement is off on all modules
      (`Za000000`). This way even a device heard only by an additional module gets its
      acknowledgement. The answer goes out before Home Assistant processes the report further.
    - **Main module on the network (Cube, CUN):** its firmware keeps acknowledging by itself,
      20 ms after the report. The path over the network and Home Assistant takes 80 to
      160 ms, and a window contact only listens for a few tens of milliseconds. Additional
      modules do not acknowledge; a device heard only by an additional module then gets no
      acknowledgement for its own reports. So the main module should reach the contacts,
      buttons and wall thermostats.

    Software cannot guarantee a fixed latency: if Home Assistant is busy with something else
    at that moment (startup, slow hardware, a blocking integration), the acknowledgement
    comes later. The device then repeats its report after a few seconds.
