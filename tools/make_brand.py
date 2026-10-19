"""Render the eq3_max brand images (icon/logo, light/dark, 1x/2x) with Pillow."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
S = 4  # supersampling factor
FONT = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"

PALETTES = {
    "light": {"body": (46, 58, 72), "cap": (68, 84, 102), "dial": (236, 240, 244),
              "heat": (240, 112, 40), "wave": (32, 136, 214), "text": (46, 58, 72)},
    "dark": {"body": (214, 222, 230), "cap": (180, 192, 204), "dial": (36, 44, 54),
             "heat": (255, 138, 70), "wave": (90, 176, 245), "text": (230, 236, 242)},
}


def draw_icon(size: int, pal: dict) -> Image.Image:
    n = size * S
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = n / 256  # design grid 256 x 256

    def box(x0, y0, x1, y1):
        return [x0 * u, y0 * u, x1 * u, y1 * u]

    # valve connector (bottom stub)
    d.rounded_rectangle(box(84, 212, 140, 246), radius=8 * u, fill=pal["cap"])
    # thermostat body
    d.rounded_rectangle(box(36, 80, 188, 222), radius=40 * u, fill=pal["body"])
    # dial face
    d.ellipse(box(62, 103, 162, 203), fill=pal["dial"])
    # gauge track (270 degrees) and heat portion
    d.arc(box(74, 115, 150, 191), start=135, end=45, fill=pal["cap"], width=int(10 * u))
    d.arc(box(74, 115, 150, 191), start=135, end=300, fill=pal["heat"], width=int(10 * u))
    # pointer from the centre towards the end of the heat portion
    import math
    cx, cy, r = 112, 153, 26
    ang = math.radians(300)
    d.line([cx * u, cy * u, (cx + r * math.cos(ang)) * u, (cy + r * math.sin(ang)) * u],
           fill=pal["heat"], width=int(9 * u))
    d.ellipse(box(cx - 9, cy - 9, cx + 9, cy + 9), fill=pal["heat"])
    # radio waves, top right
    wx, wy = 186, 72
    for i, r in enumerate((22, 40, 58)):
        d.arc(box(wx - r, wy - r, wx + r, wy + r), start=-90, end=0,
              fill=pal["wave"], width=int(11 * u))
    d.ellipse(box(wx - 8, wy - 8, wx + 8, wy + 8), fill=pal["wave"])
    return img.resize((size, size), Image.LANCZOS)


def draw_logo(height: int, pal: dict) -> Image.Image:
    icon = draw_icon(height, pal)
    font = ImageFont.truetype(FONT, int(height * 0.42))
    text = "eQ-3 MAX!"
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = tmp.textbbox((0, 0), text, font=font)
    gap = int(height * 0.12)
    width = height + gap + (x1 - x0) + int(height * 0.06)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    img.alpha_composite(icon, (0, 0))
    d = ImageDraw.Draw(img)
    ty = (height - (y1 - y0)) // 2 - y0
    d.text((height + gap - x0, ty), text, font=font, fill=pal["text"])
    return img


for variant, pal in PALETTES.items():
    prefix = "" if variant == "light" else "dark_"
    draw_icon(256, pal).save(OUT / f"{prefix}icon.png", optimize=True)
    draw_icon(512, pal).save(OUT / f"{prefix}icon@2x.png", optimize=True)
    draw_logo(128, pal).save(OUT / f"{prefix}logo.png", optimize=True)
    draw_logo(256, pal).save(OUT / f"{prefix}logo@2x.png", optimize=True)

print(sorted(p.name for p in OUT.iterdir()))
