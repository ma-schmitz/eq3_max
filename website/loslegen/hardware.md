# Hardware

eq3_max needs a **radio module with culfw** (868 MHz, MAX! support). Two options:

| | nanoCUL | MAX! Cube with a-culfw |
|---|---|---|
| Connection | USB on the HA box | network (LAN) or USB |
| Firmware | culfw (e.g. `1.66 nanoCUL868`) | a-culfw for the Cube |
| Setup | connection "USB stick", port from `/dev/serial/by-path/` | found on the network ("Search the network" or discovered by Home Assistant itself), otherwise host and port 2323 |
| Radio budget (1 %) | eq3_max throttles to 36 s per hour (default); culfw with budget check additionally refuses by itself (`LOVF`) | a-culfw enforces it itself (`LOVF`) |
| Status | proven in continuous operation | in use in two further installations with flashed Cubes |

!!! info "Both are interchangeable – and can be mixed"
    The devices do not remember the radio module but the **central address**, and
    eq3_max sets it at startup (`Za<address>`). Switching nanoCUL ↔ Cube: options →
    "Change connection", nothing needs to be paired again. Several at once, e.g. one per floor:
    see [Multiple radio modules](../handbuch/funkmodule.md).

## nanoCUL (USB)

- Many nanoCULs have a CH341 converter (USB ID `1a86:7523`) **without a serial number**.
  So always choose `/dev/serial/by-path/…`, never `by-id`.
- 38400 baud, init sequence `V`, `X21`, `Zr`, `Za000000` (from 0.7.0; the integration
  sends the acknowledgements to window contacts, buttons and wall thermostats itself with
  `Zf`; if the main module is a network module, it stays at `Za<address>` with the
  acknowledgement from the firmware). Commands go out with `Zs`.

!!! note "Radio budget: at most 1 % airtime"
    In the 868 MHz band every transmitter may send at most 1 % of the time, i.e. 36 s per hour.
    eq3_max measures this (`sensor.eq3_max_sendezeit_1h`, "Airtime 1h") and keeps to it with
    the **brake**, which is switched on for new entries. Some culfw builds do not check the
    budget themselves – then the brake alone takes care of it; it should stay on.

    The firmware keeps its own credit and refills 10 ms per second. How much it keeps in
    reserve depends on the device (a-culfw source code): **nanoCUL and CUL 9 s**,
    **MAX! Cube and MapleCUN 36 s**; after a restart of the module it is half of that.
    When the reserve is empty, it refuses to send (`LOVF`). eq3_max then waits and retries
    every 10 s; a telegram with wake-up preamble (about 1.1 s) goes out after just under two
    minutes. Nothing is lost, it just takes time: a whole
    [week program](../handbuch/dienste.md) (7 to 14 telegrams) fits into the Cube's
    reserve, on the nanoCUL it takes a quarter of an hour and more. Meanwhile the
    "eQ-3 MAX!" panel shows "waiting for airtime" on the radio module, and the log shows
    `culfw refused to send … (LOVF)` once per command.

!!! warning "Nothing received after sending? Change the USB port first."
    If the stick seems deaf – the firmware answers, sending works, but reception drops out
    after the first transmission –, the cause is often not the stick but the USB port: its
    voltage collapses under the transmit current. Use another port, a short extension cable or an
    active hub. Then choose the new `by-path` path in the options.

## MAX! Cube with a-culfw (network)

The MAX! Cube has the same radio chip as a CUL. Flashed with **a-culfw**, it speaks the
same text protocol as the nanoCUL, just over TCP. Advantage: connected by network cable,
it can sit wherever radio reception is good.

1. **Flash** it following the instructions of the a-culfw project (section MAX! Cube). The
   eQ-3 firmware is lost in the process; `maxcube` and the eQ-3 software no longer work
   afterwards.
2. **Connect it to the LAN.** The Cube gets its address via DHCP; ideally assign a fixed
   one in the router.

    !!! warning "Power only from a power supply, not from a router or computer"
        If the Cube is on the LAN and at the same time draws its power from a USB port
        that addresses it as a device (FRITZ!Box, NAS, Raspberry Pi, PC), **it restarts
        again and again during radio operation**: commands stay unacknowledged, the radio
        module turns red at intervals. This is a known, open bug in a-culfw. Remedy: a
        simple USB power supply or a pure charging cable without data lines.

3. **In eq3_max:** after a short while Home Assistant reports the Cube by itself under
   "Discovered" (from 0.7.0). Otherwise choose **"Search the network"** during setup, or
   enter the address manually (host = IP, port 2323).
4. **Check manually** if it is not found: `nc <cube-ip> 2323`, then type `V` –
   the answer is something like `V 1.26.08 a-culfw … CUBe`.

    !!! note "How the Cube is found"
        a-culfw does not announce itself on the network. eq3_max therefore queries the
        addresses in Home Assistant's network on port 2323 with `V`. Home Assistant
        recognises the Cube by itself from its network address: a-culfw assigns
        `00:80:41:xx:xx:xx` on first start. If the IP address of a Cube found this way
        changes later, eq3_max updates it by itself.
5. Leave the option **"Limit airtime to 36 s per hour"** switched on (default
   for new entries). a-culfw additionally checks the budget itself (Cube reserve 36 s);
   once it is used up, it refuses to send (`LOVF`), eq3_max then waits and sends
   as soon as time is available again (see the note above).

If the Cube restarts (power failure, firmware), eq3_max notices this from 0.7.0 after about
half a minute: a network module from which nothing has arrived for 20 s is asked for its
state and set up again if necessary. The log then shows `lost its settings (it
restarted)` or `does not answer any more`.

If the connection drops, eq3_max notices after about 90 s and reconnects; after 15
minutes the repair issue "CUL not reachable" appears. If the Cube no longer receives
anything, only restarting the Cube helps – reconnecting does not reset its radio module.

A Cube with **original firmware** does not work; it speaks a protocol of its own, for that
there is the HA integration `maxcube`.
