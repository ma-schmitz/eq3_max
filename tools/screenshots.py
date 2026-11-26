#!/usr/bin/env python3
"""Make the images of README and handbook from the test pages, with neutral demo data.

Thermostat card (website/assets/karte/card-{kompakt,ring,kachel}-{de,en}-{light,dark}.png):
tests/card/harness.html?shot=1, card positions from ?rects=1, three rows cut out:
compact (cards 0-2), ring (3-4), tile (5-6).

Page "eQ-3 MAX!" (website/assets/panel*.png): tests/card/panel-harness.html, made-up
devices on two radio modules, the user's own order in the ground floor.
  panel-{de,en}.png        whole page, 1440 px wide
  panel-hero-{de,en}.png   top left part (radio modules, first cards) for README and home page
  panel-handy-{de,en}.png  phone width, "Anordnen" on, upper floor folded

Serves the repository on 127.0.0.1, renders with headless Chromium. Needs chromium,
Pillow and the network (icon font from jsdelivr).

    python3 tools/screenshots.py
"""

from __future__ import annotations

import functools
import http.server
import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "website" / "assets"
CARD_CUTS = {"kompakt": (0, 3), "ring": (3, 5), "kachel": (5, 7)}


def chromium(width: int, height: int, *args: str, scale: int = 1) -> str:
    return subprocess.run(
        ["chromium", "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=5000",
         f"--window-size={width},{height}", f"--force-device-scale-factor={scale}", *args],
        capture_output=True, text=True, timeout=120, check=True,
    ).stdout


def rects(url: str, width: int, height: int, attr: str) -> Any:
    dom = chromium(width, height, "--dump-dom", url + "&rects=1")
    found = re.search(rf'{attr}="([^"]+)"', dom)
    if not found:
        raise SystemExit(f"no positions for {url}")
    return json.loads(found.group(1).replace("&quot;", '"'))


def shot(url: str, width: int, height: int, scale: int = 1) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "page.png"
        chromium(width, height, f"--screenshot={target}", url, scale=scale)
        return Image.open(target).copy()


def save(image: Image.Image, target: Path) -> None:
    image.save(target, optimize=True)
    print(target.relative_to(ROOT), image.size[0], "x", image.size[1])


def cards(base: str) -> None:
    width, height = 1120, 1500
    for lang in ("de", "en"):
        for theme in ("light", "dark"):
            url = f"{base}/tests/card/harness.html?shot=1&lang={lang}&theme={theme}"
            boxes_all = rects(url, width, height, "data-rects")
            page = shot(url, width, height)
            for name, (first, last) in CARD_CUTS.items():
                boxes = boxes_all[first:last]
                box = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                       max(b[2] for b in boxes), max(b[3] for b in boxes))
                save(page.crop(box), ASSETS / "karte" / f"card-{name}-{lang}-{theme}.png")


def panel(base: str) -> None:
    scale = 2
    for lang in ("de", "en"):
        url = f"{base}/tests/card/panel-harness.html?lang={lang}"
        info = rects(url, 1440, 900, "data-rects")
        height = int(info["height"]) + 16
        page = shot(url, 1440, height, scale)
        save(page, ASSETS / f"panel-{lang}.png")
        # Hero: from below the toolbar, 700 x 488 CSS pixels.
        save(page.crop((28 * scale, 68 * scale, 728 * scale, 556 * scale)), ASSETS / f"panel-hero-{lang}.png")

        url = f"{base}/tests/card/panel-harness.html?lang={lang}&narrow=1&arrange=1&collapsed=1"
        info = rects(url, 500, 900, "data-rects")
        height = int(info["height"]) + 16
        page = shot(url, 500, height, scale)
        top = int(info["areas"][0][1]) - 44  # the "Fertig" button above the first area
        bottom = int(info["areas"][-1][3]) + 12  # down to the folded upper floor
        save(page.crop((0, top * scale, 500 * scale, bottom * scale)), ASSETS / f"panel-handy-{lang}.png")


def main() -> None:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

    handler = functools.partial(Quiet, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        cards(base)
        panel(base)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
