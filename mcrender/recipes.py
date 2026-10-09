"""Parse Bedrock recipe files into a normalised shape the renderer can draw."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

from . import jsonc

CRAFT_KINDS = {
    "minecraft:recipe_shaped": "shaped",
    "minecraft:recipe_shapeless": "shapeless",
    "minecraft:recipe_furnace": "furnace",
    "minecraft:recipe_stonecutter": "stonecutter",
    "minecraft:recipe_smithing_transform": "smithing",
    "minecraft:recipe_brewing_mix": "brewing",
    "minecraft:recipe_brewing_container": "brewing",
}


def _item(value):
    """Normalise an item reference to (id, count).

    A legacy ``data`` / ``variation`` value is kept on the id as ``id#<n>`` so the
    asset resolver can pick the right variant (a skull's ``data`` decides whether
    it is a skeleton, wither skeleton, zombie, player, creeper or dragon head).
    """
    if value is None:
        return None, 1
    if isinstance(value, str):
        return value, 1
    if isinstance(value, list):
        for v in value:
            if v is not None:
                return _item(v)
        return None, 1
    if isinstance(value, dict):
        if "item" in value:
            ident = str(value["item"])
            data = value.get("data", value.get("variation"))
            if data is not None and "#" not in ident:
                try:
                    ident = f"{ident}#{int(data)}"
                except (TypeError, ValueError):
                    pass
            elif "potion_type" in value and "#" not in ident:
                ident = f"{ident}#{value['potion_type']}"
            return ident, int(value.get("count", 1) or 1)
        if "tag" in value:
            return "tag:" + str(value["tag"]), 1
        if "items" in value:
            return _item(value["items"])
    return None, 1


@dataclass
class Recipe:
    path: str
    kind: str = "unknown"
    raw_kind: str = ""
    identifier: str = ""
    stations: list = field(default_factory=list)
    grid: list = field(default_factory=list)          # list[list[str|None]]
    special: dict = field(default_factory=dict)        # extra inputs per kind
    result: tuple | None = None                        # (item_id, count)
    note: str = ""

    @property
    def rows(self) -> int:
        return len(self.grid)

    @property
    def cols(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    @property
    def size(self) -> int:
        return max(self.rows, self.cols, 1)

    def items(self):
        out = []
        for row in self.grid:
            out += [c for c in row if c]
        for v in self.special.values():
            if v:
                out.append(v[0] if isinstance(v, tuple) else v)
        if self.result:
            out.append(self.result[0])
        return out


def _compact_grid(items):
    n = len(items)
    if n == 0:
        return []
    cols = min(3, max(1, math.ceil(math.sqrt(n))))
    rows = math.ceil(n / cols)
    grid = [[None] * cols for _ in range(rows)]
    for i, it in enumerate(items):
        grid[i // cols][i % cols] = it
    return grid


def _trim(grid):
    grid = [row[:] for row in grid]
    while grid and all(c is None for c in grid[0]):
        grid.pop(0)
    while grid and all(c is None for c in grid[-1]):
        grid.pop()
    if not grid:
        return []
    width = max(len(r) for r in grid)
    grid = [r + [None] * (width - len(r)) for r in grid]
    while width and all(r[0] is None for r in grid):
        grid = [r[1:] for r in grid]
        width -= 1
    while width and all(r[-1] is None for r in grid):
        grid = [r[:-1] for r in grid]
        width -= 1
    return grid


def parse(path: str) -> Recipe | None:
    try:
        data = jsonc.load(path)
    except Exception as exc:                                  # pragma: no cover
        rec = Recipe(path=path, kind="unknown", note=f"JSON parse failed: {exc}")
        return rec
    if not isinstance(data, dict):
        return None
    for key, body in data.items():
        if key not in CRAFT_KINDS or not isinstance(body, dict):
            continue
        kind = CRAFT_KINDS[key]
        rec = Recipe(path=path, kind=kind, raw_kind=key,
                     identifier=(body.get("description") or {}).get("identifier", ""),
                     stations=list(body.get("tags") or []))
        if kind == "shaped":
            key_map = body.get("key") or {}
            pattern = body.get("pattern") or []
            grid = []
            for row in pattern:
                grid.append([_item(key_map.get(ch))[0] if ch != " " else None for ch in row])
            rec.grid = _trim(grid)
        elif kind == "shapeless":
            ing = [_item(i)[0] for i in (body.get("ingredients") or [])]
            rec.grid = _compact_grid([i for i in ing if i])
        elif kind == "furnace":
            rec.special["input"] = _item(body.get("input"))
            rec.special["output"] = _item(body.get("output"))
        elif kind == "stonecutter":
            rec.special["input"] = _item(body.get("input") or body.get("ingredient"))
            rec.special["output"] = _item(body.get("output") or body.get("result"))
        elif kind == "smithing":
            rec.special["template"] = _item(body.get("template"))
            rec.special["base"] = _item(body.get("base") or body.get("input"))
            rec.special["addition"] = _item(body.get("addition"))
        elif kind == "brewing":
            rec.special["input"] = _item(body.get("input"))
            rec.special["reagent"] = _item(body.get("reagent"))
            rec.special["output"] = _item(body.get("output"))
        res = body.get("result")
        if res is None and kind in ("furnace", "stonecutter", "brewing"):
            res = body.get("output")
        item, count = _item(res)
        if item is None and kind == "shaped":
            item, count = _item(body.get("result"))
        rec.result = (item, count) if item else None
        return rec
    return None


def collect(recipes_dir: str) -> list[Recipe]:
    out = []
    for root, _dirs, files in os.walk(recipes_dir):
        for name in sorted(files):
            if name.lower().endswith(".json"):
                rec = parse(os.path.join(root, name))
                if rec is not None:
                    out.append(rec)
    out.sort(key=lambda r: r.path)
    return out
