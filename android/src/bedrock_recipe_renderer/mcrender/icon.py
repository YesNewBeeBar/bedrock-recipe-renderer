"""Item / block icon rasterisation: flat sprites and Minecraft's isometric block cube."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

# Minecraft's display transform for blocks in the GUI ("models/block/block.json"):
#   {"gui": {"rotation": [30, 225, 0], "scale": [0.625, 0.625, 0.625]}}
GUI_ROT_X = 30.0
GUI_ROT_Y = 225.0
GUI_SCALE = 0.625
PX_PER_UNIT = 16.0          # the GUI projection maps one model unit to 16 pixels

FACE_BRIGHTNESS = {"up": 1.0, "down": 0.5, "north": 0.8, "south": 0.8, "east": 0.6, "west": 0.6}

# "vanilla"  = Minecraft's own block-light factors (up 1.0, N/S 0.8, E/W 0.6)
# "reference"= factors fitted to the supplied screenshot, whose cube was lit by a
#              shader/deferred-lighting resource pack (left face ~0.68, right ~0.40)
SHADING_PRESETS = {
    "vanilla": {"up": 1.0, "down": 0.5, "north": 0.8, "south": 0.8, "east": 0.6, "west": 0.6},
    "reference": {"up": 1.0, "down": 0.5, "north": 0.40, "south": 0.40, "east": 0.68, "west": 0.68},
}


def set_shading(name: str) -> None:
    FACE_BRIGHTNESS.update(SHADING_PRESETS.get(name, SHADING_PRESETS["vanilla"]))

# corner order and UVs per face (uv 0,0 = top-left of the texture)
_FACES = {
    #  name    corners (x, y, z), texture uv corners
    "up":    ((-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)),
    "down":  ((-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5), (-0.5, -0.5, -0.5)),
    "north": ((-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, -0.5, -0.5), (-0.5, -0.5, -0.5)),
    "south": ((0.5, 0.5, 0.5), (-0.5, 0.5, 0.5), (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5)),
    "east":  ((0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5), (0.5, -0.5, -0.5)),
    "west":  ((-0.5, 0.5, 0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5)),
}
_NORMALS = {"up": (0, 1, 0), "down": (0, -1, 0), "north": (0, 0, -1),
            "south": (0, 0, 1), "east": (1, 0, 0), "west": (-1, 0, 0)}
_UVS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


def _rotate(v):
    """Minecraft's GUI block rotation: M = Ry(225) * Rx(30)."""
    x, y, z = v
    rx, ry = math.radians(GUI_ROT_X), math.radians(GUI_ROT_Y)
    x1 = x * math.cos(ry) + z * math.sin(ry)
    z1 = -x * math.sin(ry) + z * math.cos(ry)
    y1 = y * math.cos(rx) - z1 * math.sin(rx)
    z2 = y * math.sin(rx) + z1 * math.cos(rx)
    return x1, y1, z2


def _project(v, size: int):
    """Project a point of the unit cube into a ``size``x``size`` icon box.

    ``size`` is the rendered pixel size of the 16x16 item cell, so the cube is
    rasterised at the final resolution instead of being upscaled afterwards.
    """
    x, y, _ = _rotate(v)
    s = GUI_SCALE * PX_PER_UNIT * (size / 16.0)
    return (x * s + size / 2.0, -y * s + size / 2.0)


def _signed_area(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _affine(p0, p1, p2, uv0, uv1, uv2):
    """Solve the affine screen->uv map through three point correspondences."""
    det = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
    if abs(det) < 1e-9:
        return None
    a = ((uv1[0] - uv0[0]) * (p2[1] - p0[1]) - (uv2[0] - uv0[0]) * (p1[1] - p0[1])) / det
    b = ((uv2[0] - uv0[0]) * (p1[0] - p0[0]) - (uv1[0] - uv0[0]) * (p2[0] - p0[0])) / det
    c = ((uv1[1] - uv0[1]) * (p2[1] - p0[1]) - (uv2[1] - uv0[1]) * (p1[1] - p0[1])) / det
    d = ((uv2[1] - uv0[1]) * (p1[0] - p0[0]) - (uv1[1] - uv0[1]) * (p2[0] - p0[0])) / det
    e = uv0[0] - a * p0[0] - b * p0[1]
    f = uv0[1] - c * p0[0] - d * p0[1]
    return a, b, c, d, e, f


def _inside(poly, x, y):
    sign = 0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        cross = (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)
        if abs(cross) < 1e-9:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


@dataclass
class Icon:
    ident: str
    kind: str = "missing"                  # item | block | model | missing
    item: Image.Image | None = None
    faces: dict[str, Image.Image] = field(default_factory=dict)
    geometry: object = None                # mcrender.geometry.Geometry for kind == "model"
    smooth: bool = False                   # hi-res source (wiki icon): scale smoothly
    note: str = ""

    def render(self, size: int = 16) -> Image.Image:
        if self.kind == "item" and self.item is not None:
            return _flat(self.item, size, self.smooth)
        if self.kind == "block" and self.faces:
            return render_cube(self.faces, size)
        if self.kind == "model" and self.geometry is not None:
            from .geometry import render_geometry
            return render_geometry(self.geometry, self.faces, size)
        return missing_texture(size)


def _flat(image: Image.Image, size: int, smooth: bool = False) -> Image.Image:
    img = image.convert("RGBA")
    if img.height > img.width:            # animated flipbook strip -> first frame
        img = img.crop((0, 0, img.width, img.width))
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS if smooth else Image.NEAREST)
    return img


def render_cube(faces: dict[str, Image.Image], size: int = 16) -> Image.Image:
    """Rasterise a textured 1x1x1 cube exactly like the vanilla inventory render."""
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = out.load()

    # visibility: a face is drawn when its rotated normal points at the camera
    visible = []
    for name, corners in _FACES.items():
        if _rotate(_NORMALS[name])[2] <= 0:
            continue
        poly = [_project(c, size) for c in corners]
        depth = sum(_rotate(c)[2] for c in corners) / 4.0
        visible.append((depth, name, poly))
    visible.sort(key=lambda t: t[0])      # back to front

    for _, name, poly in visible:
        tex = faces.get(name) or faces.get("side") or faces.get("up")
        if tex is None:
            continue
        tex = tex.convert("RGBA")
        tw, th = tex.size
        tp = tex.load()
        bright = FACE_BRIGHTNESS[name]
        m = _affine(poly[0], poly[1], poly[2], _UVS[0], _UVS[1], _UVS[2])
        if m is None:
            continue
        a, b, c, d, e, f = m
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        for y in range(max(0, int(math.floor(min(ys)))), min(size, int(math.ceil(max(ys))) + 1)):
            for x in range(max(0, int(math.floor(min(xs)))), min(size, int(math.ceil(max(xs))) + 1)):
                if not _inside(poly, x + 0.5, y + 0.5):
                    continue
                u = a * (x + 0.5) + b * (y + 0.5) + e
                v = c * (x + 0.5) + d * (y + 0.5) + f
                tx = min(tw - 1, max(0, int(u * tw)))
                ty = min(th - 1, max(0, int(v * th)))
                r, g, bb, alpha = tp[tx, ty]
                if alpha == 0:
                    continue
                px[x, y] = (int(r * bright), int(g * bright), int(bb * bright), alpha)
    return out


def missing_texture(size: int = 16) -> Image.Image:
    """Vanilla 'missing texture' magenta/black checker."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    px = img.load()
    half = max(1, size // 2)
    for y in range(size):
        for x in range(size):
            if ((x // half) + (y // half)) % 2 == 0:
                px[x, y] = (255, 0, 255, 255)
    return img
