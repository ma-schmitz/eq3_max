#!/usr/bin/env python3
"""Convert Homegear log lines into culfw-style test lines."""

from __future__ import annotations

import re
import sys

_RX = re.compile(r"MAX packet received \([^,]+, RSSI: 0x([0-9A-Fa-f]{2})\): ([0-9A-Fa-f]+)")
_TX = re.compile(r"Sending \([^)]*\): ([0-9A-Fa-f]+)")


def convert(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        if m := _RX.search(raw):
            out.append("Z" + m.group(2).upper() + m.group(1).upper())
        elif m := _TX.search(raw):
            out.append("Zs" + m.group(1).upper())
    return out


def main() -> int:
    for item in convert(sys.stdin.read()):
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
