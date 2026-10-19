#!/usr/bin/env python3
"""Export the MAX! device list from Homegear as JSON for eq3_max."""

from __future__ import annotations

import argparse
import sys
import xmlrpc.client
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from custom_components.eq3_max.homegear_import import export_from_homegear, save_export  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Homegear-Host")
    parser.add_argument("--port", type=int, default=2001)
    parser.add_argument("--out", default="eq3_max_export.json")
    args = parser.parse_args()
    proxy = xmlrpc.client.ServerProxy(f"http://{args.host}:{args.port}")
    data = export_from_homegear(proxy)
    save_export(data, args.out)
    print(f"{len(data['devices'])} Geraete nach {args.out} exportiert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
