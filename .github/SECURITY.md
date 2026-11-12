# Security policy

## Supported versions

Only the latest release of eq3_max receives fixes.

## Reporting a vulnerability

Please **do not** open a public issue. Report it privately via
[GitHub private vulnerability reporting](https://github.com/ma-schmitz/eq3_max/security/advisories/new)
(Security → Report a vulnerability). English or German is fine.

You will get an answer within a few days. eq3_max is maintained in spare time,
so please allow some time for a fix before publishing details.

## Scope

eq3_max talks to the radio module (USB or TCP on the local network) and offers a panel
and WebSocket commands inside Home Assistant. Relevant are, for example, ways to send
radio telegrams or change devices without Home Assistant admin rights, or problems with
the network connection to a MAX! Cube / CUN.

Not in scope: the MAX! radio protocol itself (it has no encryption or authentication –
anyone in radio range with a CUL can talk to the devices) and the firmware of the radio
modules (culfw/a-culfw).
