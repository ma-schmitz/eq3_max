# Virtual devices


A virtual device exists only in Home Assistant, not as hardware. eq3_max uses it to appear
to your real radiator thermostats as a MAX! device, fed by an entity that Home Assistant
already knows.

| Kind | Source | Effect |
|---|---|---|
| Virtual **window contact** | a `binary_sensor` (for example a Zigbee window contact) | the linked thermostats get "open" or "closed" and lower to the window-open temperature |
| Virtual **wall thermostat** | a temperature `sensor` (°F and K are converted) | the thermostats of a room regulate on this temperature instead of their own sensor, and a setpoint applies to the whole room |

**What for?** A radiator thermostat measures right at the radiator, where it is warmest. A
room sensor you already have (Zigbee, ESPHome, ...) measures better. Likewise, a window
contact you have already installed can make the thermostats lower by radio directly,
without a second MAX! contact on the window.

## Creating

On the "eQ-3 MAX!" panel choose **"Create virtual device"** (admins only) and enter:

1. the **kind** (window contact or wall thermostat),
2. a **name**,
3. the **source**: a `binary_sensor` for the contact, a temperature `sensor` for the wall
   thermostat (device class temperature or unit °C, °F or K).

You do not choose a radio module: a virtual device sends through the radio module of the
thermostat concerned and answers through the module that heard a telegram first. The
thermostats of a virtual wall thermostat must be on a radio module connected by **USB or
serial** (see [Limits](#limits-in-0100)); eq3_max checks this when you link.

!!! tip "Which source?"

    Use a sensor of a device that reports regularly (Zigbee, ESPHome, ...). Sensors that only
    write a new state when the value changes (template or helper sensors) count as
    unavailable after **3 hours** without a report, even if the temperature simply did not
    change.

The virtual device appears like a bought one: as a device in Home Assistant, with a
`binary_sensor` (contact) or a `climate` entity (wall thermostat). It has no battery,
signal-strength or radio-error entity.

## Linking

Then **link** it with the thermostats exactly like a bought device
([Links](verknuepfungen.md)): on the "eQ-3 MAX!" panel in the Links tab, or with the
`eq3_max.link` service.

!!! info "The first thermostat sets the room"

    The first thermostat you link hands its setpoint, mode, week program and the comfort,
    eco and window settings over to the virtual wall thermostat, but only while the virtual
    wall thermostat has no setpoint of its own yet. What you already entered there (the week
    program of single days, saved settings) stays. If the thermostat is at the window-open
    temperature or on boost just then, that does not become the room's setpoint; its last
    comfort value is used instead. If it is in automatic mode while no complete week program
    is known, the room runs manually with its current setpoint, and the thermostat is set to
    manual as well (see [Automatic](#what-the-virtual-wall-thermostat-does)). Thermostats linked later get the room's
    setpoint and mode. Their **week program is not overwritten unasked**: the panel shows a
    hint and offers to copy the room's program.

!!! warning "Link the window contact with the wall thermostat too"

    For "window open" to work in the room, link the contact (real or virtual) **with the
    virtual wall thermostat as well**, not only with the thermostats. If it is missing, the
    panel shows a hint.

## What the virtual wall thermostat does

**Temperature.** The temperature of the source goes to the thermostats **every 5 minutes**,
fixed and on time, whether it changed or not. A thermostat waits just under **10 minutes**
for its wall thermostat; if nothing arrives by then, it regulates on its own sensor and shows
a radio error until the next telegram arrives.

If all thermostats of the room share a group (a group ID shared by all thermostats of a room, which eq3_max assigns itself
when you link) and a radio module, **one telegram** (a single radio message) **for the whole
room** is enough. Otherwise the temperature is sent to each thermostat in turn: each
thermostat then needs a telegram of its own every 5 minutes, which costs about **13 s per hour
per thermostat**. With more than one thermostat the airtime for this can run short, and they
regulate on their own sensor at times. So give the room a common group: the panel shows a
hint at the virtual wall thermostat and offers **"Assign for the room"**. If the thermostats
are on different radio modules, a group does not help; the hint then says so.

When a thermostat leaves the virtual room (link removed or virtual wall thermostat removed),
eq3_max takes its group ID away again, unless it still belongs to another wall thermostat.

A **falling** temperature is passed on in steps of at most **1.0 °C** per telegram. A sudden
drop would otherwise trigger the thermostat's built-in open-window detection, and it would
lower its setpoint.

**Setpoint.** A setpoint applies to the whole room:

- If you turn the handwheel of one thermostat, the change reaches the virtual wall
  thermostat after a few seconds and from there the other thermostats of the room.
- A setpoint set in Home Assistant on the virtual wall thermostat or on one of its
  thermostats also applies to the whole room.

**Automatic and away.** Every temperature telegram also sets the thermostats' setpoint.
Automatic mode is therefore only possible when the virtual wall thermostat knows a **complete
week program**, one written for all seven days through eq3_max (in the Week program tab or
with `eq3_max.set_week_profile`). Without one the room runs **manually**: Home Assistant does
not offer Auto, the panel shows a hint with **"Set week program"**, and if someone presses the
Auto button at a thermostat, eq3_max sets it back to the room's setpoint shortly after
(during an away period the Auto button ends the away period for the whole room).
Writing the program does not change the mode; afterwards you can choose Auto.

In automatic mode the room follows the week program. A change at the handwheel or in Home
Assistant holds until the program's **next switch point**, then the program applies again, as
with a real wall thermostat; a newly written program cancels it. An away period ("away" with
an end time) also works without a program. It ends by itself at the set time; then what
applied before applies again: automatic mode (with a program) or the manual setpoint from
before.

**Boost.** A boost at one thermostat (handwheel or Home Assistant) stays with that
thermostat, as with a real wall thermostat; the virtual wall thermostat keeps showing the
room's mode, not "boost". A boost on the virtual wall thermostat boosts **every** thermostat
of the room; it ends after the thermostats' boost duration, at the latest after an hour.

**Window.** See above: link the contact with the virtual wall thermostat too. A window
change goes to the thermostats **at once** (on "open" with the window-open temperature), not
only with the next 5-minute telegram; a further change within the same minute follows at the
end of that minute. At most **12** such immediate telegrams go out per hour and room; beyond
that the next regular telegram carries the window state.

**Virtual window contact.** It sends "open" or "closed" with acknowledgement (the thermostat confirms receipt) to each linked
thermostat. If a thermostat does not acknowledge, the state is repeated **every 5 minutes**,
after three failures in a row **every 15 minutes**, and once right away when the radio
module is back after an interruption. Two state changes to the same thermostat are **at
least one minute** apart: a change within that minute goes out at its end, and only the
state current by then. At most **12 telegrams per hour** go to each thermostat (repeats
included); beyond that the newest state waits until there is room again. Nothing is sent
periodically. After a restart, eq3_max only sends if
the state differs from the last delivered one.

**Source unavailable.** If the source is unavailable, the `climate` entity or sensor of the
virtual device is unavailable and nothing is sent. The settings stay usable. Without
telegrams a thermostat falls back to its own sensor by itself after just under 10 minutes. A
temperature source that has not reported for **3 hours** also counts as unavailable (a
sensor with a dead battery often just keeps showing its last value). A virtual window
contact without a source counts as closed for the virtual wall thermostat.

## Airtime: how many rooms per radio module?

Radio in the 868 MHz band may only transmit **1 % of the time** per device, which is **36
seconds per hour per radio module**. With its telegram every 5 minutes a virtual wall
thermostat needs about **13 s per hour**. With the option **"Limit airtime to 36 s"**
switched on, 10 s of the hour are kept free for commands, and a temperature telegram that
would eat into this reserve is skipped; without the option the radio module itself decides.

**Rule of thumb: one radio module is enough for two virtual wall thermostats.**
Spread more rooms over several radio modules ([Multiple radio modules](funkmodule.md)).

!!! note "Long jobs push out the temperature"

    A long job, for example writing a week program to three thermostats (which needs more
    than the 36 s of an hour), can keep a room without temperature telegrams for up to about
    **an hour**. The thermostats then regulate on their own sensor and return to the room
    sensor afterwards.

## Limits in 0.10.0

- The **thermostats** you link with a virtual wall thermostat must be on a radio module
  connected by **USB or serial**, not on a network module (for example a flashed MAX! Cube);
  otherwise eq3_max refuses the link. The virtual **window contact** works with any module.
- There is **no eco button** at a virtual wall thermostat.
- A thermostat can have only **one** wall thermostat (real or virtual).

## When Home Assistant is not running

While Home Assistant is not running, nobody answers for the virtual wall thermostat. The
same applies while the integration is not loaded (radio module missing, integration disabled
or reloading). The thermostats **keep heating**, after just under 10 minutes with their own
sensor. A setpoint change at the handwheel during that time costs the thermostat airtime,
though: in the worst case (within the first 10 minutes or so of the outage) it
repeats for about **16 minutes** and is then silent for up to **an hour**. It keeps
heating meanwhile. There is no technical remedy.

## Removing

- **"Remove"** first removes the links at the thermostats. The virtual device stays visible
  as **"being removed"** and keeps answering until every linked device has acknowledged.
- **"Remove anyway"** removes it at once. A thermostat that still knows the link then
  sends into the void and can fall silent for up to **an hour**.
- The same applies if you delete a virtual device while the integration is disabled: it is
  removed at once, with the same consequence.

!!! warning "Before going back to an older version"

    Remove all virtual devices before you go back to a version older than 0.10.0. An older
    version takes them for real devices at an address nobody answers.

!!! tip "Be patient"

    Choose "Remove" and wait until the device disappears. "Remove anyway" is meant for the
    case that a thermostat is permanently unreachable (broken, removed, no battery).
    Deleting a virtual device while the integration is disabled also removes it at once,
    with the same consequence.
