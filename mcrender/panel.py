"""Minecraft GUI primitives: rounded container panel, inventory slots, sprites."""
from __future__ import annotations

import os

from PIL import Image

BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
SHADE = (85, 85, 85, 255)          # #555555
PANEL = (198, 198, 198, 255)       # #C6C6C6
SLOT = (139, 139, 139, 255)        # #8B8B8B
SLOT_DARK = (55, 55, 55, 255)      # #373737

SLOT_SIZE = 18
RESULT_SIZE = 26
GRID = 3
GRID_AREA = GRID * SLOT_SIZE        # 54
GRID_ORIGIN = (22, 16)
ARROW_ORIGIN = (83, 35)             # vanilla textures/ui/arrow_large (22x15)
RESULT_ORIGIN = (112, 30)           # 26x26, centred on the grid
TITLE_ORIGIN = (23, 6)
PANEL_SIZE = (160, 80)
CORNER = 1                          # x >= w-3 / y >= h-3 -> bottom/right shade


def shape(w: int, h: int, inset: int = 0):
    """Pixels of a rounded rectangle inset by *inset* (2px corner chamfer)."""
    iw, ih = w - 2 * inset, h - 2 * inset
    for y in range(ih):
        for x in range(iw):
            if min(x, iw - 1 - x) + min(y, ih - 1 - y) >= 2:
                yield inset + x, inset + y


def draw_panel(img: Image.Image, w: int, h: int, origin=(0, 0)) -> None:
    """Minecraft container background: 1px black outline, 2px white top/left,
    2px #555555 bottom/right, chamfered corners."""
    ox, oy = origin
    px = img.load()

    def put(x, y, color):
        tx, ty = ox + x, oy + y
        if 0 <= tx < img.width and 0 <= ty < img.height:
            px[tx, ty] = color

    for x, y in shape(w, h, 0):
        put(x, y, BLACK)
    for x, y in shape(w, h, 1):
        put(x, y, WHITE)
    for x, y in shape(w, h, 1):
        if x >= w - 3 or y >= h - 3:
            put(x, y, SHADE)
    for x, y in shape(w, h, 3):
        put(x, y, PANEL)


def draw_slot(img: Image.Image, x: float, y: float, size: int = SLOT_SIZE) -> None:
    """One inventory slot: #8B8B8B base, dark top/left, white bottom/right."""
    px = img.load()
    x, y = int(round(x)), int(round(y))
    for yy in range(y, y + size):
        for xx in range(x, x + size):
            if 0 <= xx < img.width and 0 <= yy < img.height:
                px[xx, yy] = SLOT
    for i in range(size):
        for (dx, dy), color in (((i, 0), SLOT_DARK), ((0, i), SLOT_DARK),
                                ((i, size - 1), WHITE), ((size - 1, i), WHITE)):
            xx, yy = x + dx, y + dy
            if 0 <= xx < img.width and 0 <= yy < img.height:
                px[xx, yy] = color


def blit(img: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    img.alpha_composite(sprite.convert("RGBA"), (x, y))


def draw_pipe(img: Image.Image, x: float, y: float, w: float, h: float) -> None:
    """One brewing-stand pipe segment: dark edge on the top/left, grey fill.

    Mirrors the vanilla ``brewing_pipes`` art (each pipe is 1.5 units wide:
    0.5 unit of #373737 plus 1 unit of #8B8B8B).
    """
    px = img.load()
    x0, y0 = int(round(x)), int(round(y))
    w, h = max(1, int(round(w))), max(1, int(round(h)))
    for yy in range(y0, y0 + h):
        for xx in range(x0, x0 + w):
            if 0 <= xx < img.width and 0 <= yy < img.height:
                px[xx, yy] = SLOT_DARK if (xx < x0 + 1 or yy < y0 + 1) else SLOT


class Sprites:
    """Vanilla GUI sprites, from a local pack folder or the vanilla source resolver."""

    def __init__(self, source):
        self.source = source
        self.root = source if isinstance(source, str) else None
        self._cache: dict[str, Image.Image | None] = {}

    def _path(self, rel: str):
        if self.root:
            path = os.path.join(self.root, rel.replace("/", os.sep))
            return path if os.path.exists(path) else None
        if self.source is None:
            return None
        return self.source.find(rel, extensions=(".png",))

    def get(self, rel: str) -> Image.Image | None:
        if rel not in self._cache:
            path = self._path(rel)
            try:
                self._cache[rel] = Image.open(path).convert("RGBA") if path else None
            except Exception:
                self._cache[rel] = None
        return self._cache[rel]

    @property
    def arrow(self) -> Image.Image | None:
        return self.get("textures/ui/arrow_large.png")

    @property
    def flame(self) -> Image.Image | None:
        return self.get("textures/ui/flame_full_image.png")
