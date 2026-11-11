# FAQ

??? question "The valve stays at 0 % although it is cold"
    After a restart (e.g. a loose battery contact) the thermostat is stuck in
    installation mode and shows "InS". Press the **boost button** on the thermostat.
    In HA you can recognise this as follows: valve 0 %, actual temperature does not move,
    no radio errors.

??? question "The stick no longer receives anything"
    The integration reopens the port itself and creates a repair issue for persistent
    problems. First **change the USB port**: often the port voltage collapses while
    sending (see [Hardware](loslegen/hardware.md)). Then choose the new `by-path` path in
    the options.

??? question "Who acknowledges the devices' messages to the central unit?"
    What devices send to the central unit (window contact 0x30, set command from the
    wall thermostat 0x40, button 0x50) needs an acknowledgement. Up to 0.6.x the culfw
    gave it itself (`Za<address>`). Since 0.7.0, with a USB main module the integration
    acknowledges, exactly once and through the module that delivered the message first;
    with a network main module its firmware still does. Why: see
    [Multiple radio modules](handbuch/funkmodule.md). 0x60/0x70 are broadcasts and are
    not acknowledged.

??? question "A thermostat suddenly shows 12 °C"
    Usually it is the **window-open detection of the thermostat itself**: if the measured
    temperature drops quickly, it assumes an open window and goes to the window-open
    temperature for the window-open duration (factory setting 12 °C, 15 min), even without
    a window contact. It can be switched off with `fenster_dauer` (window-open duration) 0
    (see [Device configuration](handbuch/konfiguration.md)).
    If the 12 °C remain after a window has been closed, check your own
    automations: a heating control that takes a snapshot when a window opens and restores
    it when it closes may restore the window-open temperature. For the
    blueprint "Advanced Heating Control", the option *Legacy restore* helps.

??? question "Does this also work with a flashed MAX! Cube?"
    Yes. Flashed with a-culfw, the Cube is the second possible radio module besides the nanoCUL,
    via network (port 2323) or via USB; flashed Cubes run in two further
    installations. A Cube with
    original firmware does not work, for that there is `maxcube`. Details:
    [Hardware](loslegen/hardware.md).

??? question "Why does a set command sometimes take up to 10 seconds?"
    Every telegram needs a 1 s wake-up preamble. If the acknowledgement does not arrive within 3 s,
    it is repeated up to three times. If the device is operated at the same time (wall thermostat,
    button), radio telegrams can overlap.

??? question "Can I use several sticks or Cubes at the same time?"
    Yes, all with the same central address. Every device sends through the module it is
    assigned to; switching works without re-pairing. See
    [Multiple radio modules](handbuch/funkmodule.md).
