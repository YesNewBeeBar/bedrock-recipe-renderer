"""Bedrock block geometry (``models/**/*.geo.json``) -> inventory icon.

Supports the geometry format used by Bedrock add-ons (1.12 / 1.16):

* ``bones`` with a ``parent`` chain, ``pivot`` and ``rotation`` (degrees)
* ``cubes`` with ``origin``/``size`` (model units, 16 = one block, y up, x/z centred),
  ``uv`` either as the box layout ``[u, v]`` or per face
  ``{"north": {"uv": [u, v], "uv_size": [w, h]}, ...}``, plus ``inflate`` / ``mirror``
* ``texture_width`` / ``texture_height`` for the UV space

The geometry is rasterised at the output resolution with a z-buffer, using the same
isometric GUI transform as the plain block cubes, so models with several parts,
rotated bones or non-cube shapes come out looking like the game's inventory icon.
"""
from __future__ import annotations

import glob
import json
import math
import os
from dataclasses import dataclass, field

from PIL import Image

from . import icon as icon_mod
from .icon import FACE_BRIGHTNESS

# cube face -> (four corners in unit-cube space, outward normal)
# corners are listed so that texture u runs along the first edge and v along the
# second, matching Minecraft's box-UV unwrap (no mirrored faces when seen outside)
_FACES = {
    "north": ((0, 1, 0, 1, 1, 0, 1, 0, 0, 0, 0, 0), (0, 0, -1)),
    "south": ((1, 1, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1), (0, 0, 1)),
    "east": ((1, 1, 1, 1, 1, 0, 1, 0, 0, 1, 0, 1), (1, 0, 0)),
    "west": ((0, 1, 0, 0, 1, 1, 0, 0, 1, 0, 0, 0), (-1, 0, 0)),
    "up": ((0, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 1), (0, 1, 0)),
    "down": ((0, 0, 1, 1, 0, 1, 1, 0, 0, 0, 0, 0), (0, -1, 0)),
}
# box UV layout: face -> (u offset, v offset, u size, v size) as multipliers of (w,h,d)
_BOX_UV = {
    "up": (1, 0, 1, 0),        # (u + d, v), size (w, d)
    "down": (2, 0, 1, 0),      # (u + d + w, v)
    "west": (0, 1, 2, 1),      # (u, v + d), size (d, h)  -> uses d for u, h for v
    "north": (1, 1, 1, 1),     # (u + d, v + d), size (w, h)
    "east": (2, 1, 2, 1),      # (u + d + w, v + d), size (d, h)
    "south": (3, 1, 1, 1),     # (u + d + w + d, v + d), size (w, h)
}


@dataclass
class GeoCube:
    origin: tuple
    size: tuple
    uv: object = None
    pivot: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0.0, 0.0, 0.0)
    inflate: float = 0.0
    mirror: bool = False
    # optional per-cube images (face name -> PIL image); overrides the geometry ones
    textures: dict = None


@dataclass
class GeoBone:
    name: str
    parent: str | None = None
    pivot: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0.0, 0.0, 0.0)
    cubes: list = field(default_factory=list)


@dataclass
class Geometry:
    identifier: str
    texture_width: int = 16
    texture_height: int = 16
    bones: list = field(default_factory=list)
    # bone name -> resolved world matrix (filled by resolve())
    matrices: dict = field(default_factory=dict)

    def resolve(self) -> None:
        """Build a world matrix per bone, walking the parent chain."""
        by_name = {b.name: b for b in self.bones}

        def world(bone: GeoBone, depth=0):
            if bone.name in self.matrices:
                return self.matrices[bone.name]
            m = mat_identity()
            if bone.parent and bone.parent in by_name and depth < 32:
                m = world(by_name[bone.parent], depth + 1)
            m = mat_mul(m, bone_matrix(bone.pivot, bone.rotation))
            self.matrices[bone.name] = m
            return m

        for bone in self.bones:
            world(bone)
        for bone in self.bones:
            for cube in bone.cubes:
                self.matrices[f"__cube__{bone.name}__{id(cube)}"] = self.matrices[bone.name]


# ------------------------------------------------------------------ matrices
def mat_identity():
    return [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]


def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def mat_apply(m, p):
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def mat_apply_dir(m, p):
    x, y, z = p
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z,
            m[1][0] * x + m[1][1] * y + m[1][2] * z,
            m[2][0] * x + m[2][1] * y + m[2][2] * z)


def _rot(axis, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    m = mat_identity()
    if axis == "x":
        m[1][1], m[1][2], m[2][1], m[2][2] = c, -s, s, c
    elif axis == "y":
        m[0][0], m[0][2], m[2][0], m[2][2] = c, s, -s, c
    else:
        m[0][0], m[0][1], m[1][0], m[1][1] = c, -s, s, c
    return m


def _trans(x, y, z):
    m = mat_identity()
    m[0][3], m[1][3], m[2][3] = x, y, z
    return m


def bone_matrix(pivot, rotation):
    """Translate to the pivot, rotate (Z then Y then X, as Bedrock does), translate back."""
    px, py, pz = pivot
    rx, ry, rz = rotation
    m = _trans(px, py, pz)
    m = mat_mul(m, _rot("z", rz))
    m = mat_mul(m, _rot("y", ry))
    m = mat_mul(m, _rot("x", rx))
    m = mat_mul(m, _trans(-px, -py, -pz))
    return m


# -------------------------------------------------------------------- loading
def _parse_cube(raw) -> GeoCube:
    return GeoCube(
        origin=tuple(raw.get("origin", (0, 0, 0))),
        size=tuple(raw.get("size", (0, 0, 0))),
        uv=raw.get("uv"),
        pivot=tuple(raw.get("pivot", raw.get("rotation_pivot", (0, 0, 0)))),
        rotation=tuple(raw.get("rotation", (0, 0, 0))),
        inflate=float(raw.get("inflate", 0) or 0),
        mirror=bool(raw.get("mirror", False)),
    )


def parse_geometry_file(path: str) -> list:
    """Parse one .geo.json into Geometry objects (there may be several)."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        return []
    out = []
    for entry in data.get("minecraft:geometry", []) or []:
        desc = entry.get("description", {}) or {}
        bones = []
        for raw_bone in entry.get("bones", []) or []:
            bones.append(GeoBone(
                name=raw_bone.get("name", ""),
                parent=raw_bone.get("parent"),
                pivot=tuple(raw_bone.get("pivot", (0, 0, 0))),
                rotation=tuple(raw_bone.get("rotation", (0, 0, 0))),
                cubes=[_parse_cube(c) for c in raw_bone.get("cubes", []) or []],
            ))
        geo = Geometry(identifier=desc.get("identifier", ""),
                       texture_width=int(desc.get("texture_width", 16) or 16),
                       texture_height=int(desc.get("texture_height", 16) or 16),
                       bones=bones)
        geo.resolve()
        out.append(geo)
    return out


def load_geometries(roots) -> dict:
    """Scan resource-pack roots for models/**/*.geo.json."""
    out = {}
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for path in glob.glob(os.path.join(root, "models", "**", "*.json"), recursive=True):
            for geo in parse_geometry_file(path):
                if geo.identifier:
                    out[geo.identifier] = geo
    return out


# ------------------------------------------------------------------- raster
def _project(v_unit, size):
    x, y, z = icon_mod._rotate(v_unit)
    s = icon_mod.GUI_SCALE * icon_mod.PX_PER_UNIT * (size / 16.0)
    return (x * s + size / 2.0, -y * s + size / 2.0, z)


def _to_unit(p):
    """Model units (16 = 1 block, y up from the block's bottom) -> centred unit cube."""
    return ((p[0]) / 16.0, (p[1] - 8.0) / 16.0, (p[2]) / 16.0)


def _uv_rect(cube, face, geo):
    """Return the (u0, v0, u1, v1) source rect in pixels for one face."""
    uv = cube.uv
    w, h, d = (abs(v) for v in cube.size)
    if isinstance(uv, dict):
        entry = uv.get(face)
        if entry is None:
            return None
        if isinstance(entry, dict):
            u, v = entry.get("uv", (0, 0))
            uw, uh = entry.get("uv_size", (w, h))
            return (u, v, u + uw, v + uh)
        if len(entry) == 4:                  # explicit rect (u0, v0, u1, v1)
            return tuple(entry)
        u, v = entry
        return (u, v, u + w, v + h)
    if isinstance(uv, (list, tuple)) and len(uv) >= 2:
        u, v = uv[0], uv[1]
        if face == "up":
            return (u + d, v, u + d + w, v + d)
        if face == "down":
            return (u + d + w, v, u + 2 * w + d, v + d)
        if face == "west":
            return (u, v + d, u + d, v + d + h)
        if face == "north":
            return (u + d, v + d, u + d + w, v + d + h)
        if face == "east":
            return (u + d + w, v + d, u + 2 * d + w, v + d + h)
        if face == "south":
            return (u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h)
    return None


def render_geometry(geo: Geometry, textures: dict, size: int = 64) -> Image.Image:
    """Rasterise the geometry at ``size``x``size`` pixels."""
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = out.load()
    zbuf = [[-9e9] * size for _ in range(size)]

    for bone in geo.bones:
        bone_m = geo.matrices.get(bone.name, mat_identity())
        for cube in bone.cubes:
            cube_m = mat_mul(bone_m, bone_matrix(cube.pivot, cube.rotation))
            ox, oy, oz = cube.origin
            inflate = cube.inflate
            sw, sh, sd = (abs(v) + 2 * inflate for v in cube.size)
            for face, (coords, normal) in _FACES.items():
                # a cube may carry its own images (a model built from several
                # textures, e.g. the dried ghast body plus its tentacles)
                own = cube.textures or {}
                tex = own.get(face) or own.get("*") or textures.get(face) or textures.get("*")
                if tex is None:
                    continue
                rect = _uv_rect(cube, face, geo)
                if rect is None:
                    continue
                quad = []
                seq = list(zip(coords[0::3], coords[1::3], coords[2::3]))
                for cx, cy, cz in seq:
                    p = (ox - inflate + cx * sw, oy - inflate + cy * sh, oz - inflate + cz * sd)
                    quad.append(mat_apply(cube_m, p))
                # visibility from the transformed normal, seen through the GUI rotation
                n = mat_apply_dir(cube_m, normal)
                if icon_mod._rotate(n)[2] <= 0:
                    continue
                brightness = _brightness(icon_mod._rotate(n))
                _raster_face(px, zbuf, size, quad, rect, tex, brightness)
    return out


def _brightness(n):
    ax, ay, az = (abs(n[0]), abs(n[1]), abs(n[2]))
    if ay >= ax and ay >= az:
        return FACE_BRIGHTNESS["up" if n[1] > 0 else "down"]
    if ax >= az:
        return FACE_BRIGHTNESS["east" if n[0] > 0 else "west"]
    return FACE_BRIGHTNESS["north" if n[2] < 0 else "south"]


def _raster_face(px, zbuf, size, quad_model, rect, tex, brightness):
    tex = tex.convert("RGBA")
    tp = tex.load()
    tw, th = tex.size
    u0, v0, u1, v1 = rect
    # screen positions + uv per corner, in the order the corners were emitted
    screen = []
    for model_p in quad_model:
        screen.append(_project(_to_unit(model_p), size))
    uv = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    for a, b, c, uv_a, uv_b, uv_c in ((0, 1, 2, uv[0], uv[1], uv[2]),
                                      (0, 2, 3, uv[0], uv[2], uv[3])):
        _raster_tri(px, zbuf, size, (screen[a], screen[b], screen[c]),
                    (uv_a, uv_b, uv_c), tex, tp, tw, th, brightness)


def _raster_tri(px, zbuf, size, pts, uvs, tex, tp, tw, th, brightness):
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts
    minx = max(0, int(math.floor(min(x0, x1, x2))))
    maxx = min(size - 1, int(math.ceil(max(x0, x1, x2))))
    miny = max(0, int(math.floor(min(y0, y1, y2))))
    maxy = min(size - 1, int(math.ceil(max(y0, y1, y2))))
    denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(denom) < 1e-9:
        return
    for y in range(miny, maxy + 1):
        for x in range(minx, maxx + 1):
            cx, cy = x + 0.5, y + 0.5
            w0 = ((y1 - y2) * (cx - x2) + (x2 - x1) * (cy - y2)) / denom
            w1 = ((y2 - y0) * (cx - x2) + (x0 - x2) * (cy - y2)) / denom
            w2 = 1.0 - w0 - w1
            if w0 < -0.001 or w1 < -0.001 or w2 < -0.001:
                continue
            depth = w0 * z0 + w1 * z1 + w2 * z2
            if depth <= zbuf[y][x]:
                continue
            u = w0 * uvs[0][0] + w1 * uvs[1][0] + w2 * uvs[2][0]
            v = w0 * uvs[0][1] + w1 * uvs[1][1] + w2 * uvs[2][1]
            tx = min(tw - 1, max(0, int(u)))
            ty = min(th - 1, max(0, int(v)))
            r, g, b, alpha = tp[tx, ty]
            if alpha == 0:
                continue
            zbuf[y][x] = depth
            px[x, y] = (min(255, int(r * brightness)), min(255, int(g * brightness)),
                        min(255, int(b * brightness)), alpha)
