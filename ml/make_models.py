"""Builds one small 3D model (.glb) per product for the AR view, at real-world size in metres.

The label texture carries the product name, pack size and the category colour, so what the shopper
places on their table through ARCore looks like the actual pack. Run: python ml/make_models.py
"""
import io
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.store import CAT, PRODUCTS  # noqa: E402

OUT = ROOT / "static" / "models"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ACCENT = {"produce": "#2E7D32", "dairy": "#1565C0", "bakery": "#E65100", "staples": "#BF360C", "snacks": "#AD1457",
          "health": "#00838F", "household": "#4527A0", "baby": "#F9A825", "electronics": "#37474F", "frozen": "#0277BD"}


def wrap(text, font, width, draw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def label(p: dict) -> Image.Image:
    accent = ACCENT[p["category"]]
    img = Image.new("RGB", (512, 512), CAT[p["category"]]["color"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 512, 96], fill=accent)
    d.rectangle([0, 416, 512, 512], fill=accent)
    d.text((256, 48), "FRESHCART", font=ImageFont.truetype(FONT, 34), fill="white", anchor="mm")
    f = ImageFont.truetype(FONT, 46)
    lines = wrap(p["name"], f, 440, d)[:3]
    y0 = 256 - (len(lines) - 1) * 28
    for i, ln in enumerate(lines):
        d.text((256, y0 + i * 56), ln, font=f, fill="#1B1B1B", anchor="mm")
    d.text((256, 360), p["unit"], font=ImageFont.truetype(FONT_REG, 32), fill="#333333", anchor="mm")
    d.text((256, 464), CAT[p["category"]]["name"].upper(), font=ImageFont.truetype(FONT, 24), fill="white", anchor="mm")
    return img


def box(w, h, d):
    """Cuboid centred on x/z, sitting on y=0, each face mapped to the whole label."""
    x, z = w / 2, d / 2
    faces_def = [  # (corner a, b, c, d) counter-clockwise seen from outside
        [(-x, 0, z), (x, 0, z), (x, h, z), (-x, h, z)],      # front
        [(x, 0, -z), (-x, 0, -z), (-x, h, -z), (x, h, -z)],  # back
        [(x, 0, z), (x, 0, -z), (x, h, -z), (x, h, z)],      # right
        [(-x, 0, -z), (-x, 0, z), (-x, h, z), (-x, h, -z)],  # left
        [(-x, h, z), (x, h, z), (x, h, -z), (-x, h, -z)],    # top
        [(-x, 0, -z), (x, 0, -z), (x, 0, z), (-x, 0, z)],    # bottom
    ]
    v, uv, f = [], [], []
    for quad in faces_def:
        base = len(v)
        v += quad
        uv += [(0, 0), (1, 0), (1, 1), (0, 1)]
        f += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return np.array(v), np.array(f), np.array(uv)


def lathe(profile, segments=40):
    """Surface of revolution from (radius, height) points; texture wraps around once."""
    v, uv, f = [], [], []
    hmax = profile[-1][1]
    for j, (r, y) in enumerate(profile):
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            v.append((r * math.sin(a), y, r * math.cos(a)))
            uv.append((i / segments, y / hmax))
    row = segments + 1
    for j in range(len(profile) - 1):
        for i in range(segments):
            a, b = j * row + i, j * row + i + 1
            c, d = a + row, b + row
            f += [(a, b, d), (a, d, c)]
    # caps
    for (r, y), flip in ((profile[0], True), (profile[-1], False)):
        centre = len(v)
        v.append((0, y, 0))
        uv.append((0.5, 0.02 if flip else 0.98))
        start = (0 if flip else (len(profile) - 1) * row)
        for i in range(segments):
            tri = (centre, start + i + 1, start + i) if flip else (centre, start + i, start + i + 1)
            f.append(tri)
    return np.array(v), np.array(f), np.array(uv)


SHAPES = {
    "box": lambda: box(0.19, 0.27, 0.07),
    "carton": lambda: box(0.09, 0.2, 0.065),
    "pouch": lambda: box(0.2, 0.28, 0.05),
    "device": lambda: box(0.08, 0.15, 0.03),
    "bottle": lambda: lathe([(0.042, 0), (0.044, 0.02), (0.044, 0.17), (0.03, 0.21), (0.016, 0.235), (0.016, 0.26)]),
    "jar": lambda: lathe([(0.05, 0), (0.052, 0.01), (0.052, 0.1), (0.045, 0.11), (0.047, 0.115), (0.047, 0.135)]),
    "tub": lambda: lathe([(0.06, 0), (0.068, 0.07), (0.072, 0.075), (0.072, 0.085)]),
}


def build(p: dict) -> bytes:
    v, f, uv = SHAPES.get(p["shape"], SHAPES["box"])()
    tex = label(p)
    material = trimesh.visual.material.PBRMaterial(baseColorTexture=tex, metallicFactor=0.0,
                                                   roughnessFactor=0.55 if p["shape"] != "bottle" else 0.3)
    mesh = trimesh.Trimesh(vertices=v, faces=f, visual=trimesh.visual.TextureVisuals(uv=uv, material=material),
                           process=False)
    return trimesh.Scene(mesh).export(file_type="glb")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for key, p in PRODUCTS.items():
        data = build(p)
        (OUT / f"{key}.glb").write_bytes(data)
        total += len(data)
    print(f"{len(PRODUCTS)} models, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
