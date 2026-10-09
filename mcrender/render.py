"""Compose the final recipe images."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from PIL import Image, ImageColor

from . import panel
from .assets import Assets
from .fonts import GlyphSheets, ASCII_HEIGHT, ASCII_WIDTH, ascii_advance, draw_ascii
from .recipes import Recipe

_SPRITES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites.json")
# fallback copy of the shapeless (shuffle) mark, in case sprites.json is missing
SHAPELESS_MARK = [
    "###....####",
    "####..#####",
    "...#.##..#.",
    "....##.....",
    "...##.#..#.",
    "####..#####",
    "###....####",
]
# margins of the mark from the panel's outer bottom/right edges, in GUI units
SHAPELESS_RIGHT_MARGIN = 4.3
SHAPELESS_BOTTOM_MARGIN = 5.0
MARK_COLOR = (139, 139, 139, 255)         # same grey as the arrow sprite


def _load_mark() -> list:
    try:
        with open(_SPRITES_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        mark = data.get("shapeless")
        if mark:
            return mark
    except Exception:
        pass
    return SHAPELESS_MARK

TITLES = {
    "shaped": "合成",
    "shapeless": "合成",
    "furnace": "熔炉",
    "stonecutter": "切石机",
    "smithing": "锻造台",
    "brewing": "酿造台",
}

# Panel title per crafting station tag (recipe "tags" field).
STATION_TITLES = {
    "crafting_table": "合成",
    "furnace": "熔炉",
    "blast_furnace": "高炉",
    "smoker": "烟熏炉",
    "campfire": "营火",
    "stonecutter": "切石机",
    "smithing_table": "升级装备",
    "brewing_stand": "酿造台",
    "stone_crafting_table": "石头工作台",
    "stone_convert_table": "石头转换台",
    "stone_smithing_table": "石头锻造台",
}

# Items used to picture a vanilla item tag (a tag has no texture of its own).
TAG_ITEMS = {
    "minecraft:planks": "minecraft:oak_planks",
    "minecraft:logs": "minecraft:oak_log",
    "minecraft:stone_crafting_materials": "minecraft:cobblestone",
    "minecraft:stone_tool_materials": "minecraft:cobblestone",
    "minecraft:stone_bricks": "minecraft:stone_bricks",
    "minecraft:coals": "minecraft:coal",
    "minecraft:wool": "minecraft:white_wool",
    "minecraft:sand": "minecraft:sand",
    "minecraft:wooden_slabs": "minecraft:oak_slab",
    "minecraft:wooden_stairs": "minecraft:oak_stairs",
}

# UI metrics of the crafting panel, in GUI units (1 unit = `scale` output pixels).
#   classic -> the compact panel of the reference image the user supplied first
#   modern  -> the spacing of the current Bedrock UI (screenshots 2-4)
LAYOUTS = {
    "classic": {"panel": (160, 80), "grid": (22, 16), "arrow": (83, 35),
                "result": (112, 30), "title": (23, 6), "title_align": "left"},
    # current Bedrock UI: the panel is wider, the title is centred over the grid and
    # the title/arrow sit on a half-unit boundary (measured off the crisp screenshots)
    "modern": {"panel": (176, 80), "grid": (29, 16), "arrow": (90, 35.5),
               "result": (123, 30), "title": (0, 5.5), "title_align": "center"},
}

WHITE_TEXT = (255, 255, 255, 255)
SHADOW = (63, 63, 63, 255)
TITLE_COLOR = (76, 76, 76, 255)          # #4C4C4C, read off the crisp screenshots
TITLE_UNIT = 8                            # CJK glyphs occupy an 8x8 GUI-unit box


@dataclass
class Layout:
    """A drawable description of one recipe panel."""

    width: int = 160
    height: int = 80
    title: str = "合成"
    title_pos: tuple = (23, 6)                  # GUI units, ignored when align == center
    title_align: str = "left"
    title_span: tuple = None                    # (from, to) GUI units to centre the title over
    slots: list = field(default_factory=list)   # (item_id, x, y, size)
    arrows: list = field(default_factory=list)  # (x, y)
    flames: list = field(default_factory=list)  # (x, y)
    result: tuple = None                        # (item_id, count, x, y, size)
    shapeless: bool = False                     # draw the shuffle mark in the corner
    pipes: list = field(default_factory=list)   # (x, y, w, h) GUI units, brewing pipes
    sprites: list = field(default_factory=list)  # (vanilla path, x, y, w, h) GUI units
    fuel: list = field(default_factory=list)    # (x, y) slots with the empty-fuel art
    bottles: list = field(default_factory=list)  # (x, y) slots with the empty-bottle art
    # slot art drawn *under* the items: (vanilla path, x, y, w, h) GUI units
    slot_art: list = field(default_factory=list)
    notes: list = field(default_factory=list)


class Renderer:
    def __init__(self, assets: Assets, scale: int = 4, title: str | None = None,
                 show_counts: bool = True, background: str | None = None,
                 glyph_size: int = 8, layout: str = "classic"):
        self.assets = assets
        self.scale = max(1, int(scale))
        self.title = title
        self.show_counts = show_counts
        self.background = background
        self.title_unit = int(glyph_size)
        self.metrics = LAYOUTS.get(layout, LAYOUTS["classic"])
        vanilla_source = getattr(assets, "vanilla", None)
        self.font = GlyphSheets(assets.vanilla_dir, source=vanilla_source)
        self.sprites = panel.Sprites(vanilla_source or assets.vanilla_dir)
        self.warnings: list[str] = []

    # ------------------------------------------------------------- layout
    @staticmethod
    def _station_of(rec: Recipe) -> str | None:
        """The station a recipe really runs on, from its ``tags``.

        Bedrock lets a machine recipe be written as an ordinary ``recipe_shapeless``
        (or shaped) as long as the tag names the station - stonecutters and furnaces
        are commonly authored that way, so the tag decides the panel, not the kind.
        """
        for tag in rec.stations:
            short = str(tag).split(":")[-1].lower()
            if short in ("stonecutter", "furnace", "blast_furnace", "smoker",
                         "smithing_table", "brewing_stand"):
                return short
        return None

    def layout(self, rec: Recipe) -> Layout:
        title = self.title or self._station_title(rec) or TITLES.get(rec.kind, "合成")
        if rec.note and rec.kind == "unknown":
            lay = Layout(title=title)
            lay.notes.append(rec.note)
            return lay
        station = self._station_of(rec)
        if rec.kind in ("shaped", "shapeless"):
            if station == "stonecutter":
                return self._layout_stonecutter(rec, title)
            if station in ("furnace", "blast_furnace", "smoker"):
                return self._layout_furnace(rec, title)
            if station == "smithing_table" and rec.special:
                return self._layout_smithing(rec, title)
            return self._layout_crafting(rec, title)
        if rec.kind == "furnace":
            return self._layout_furnace(rec, title)
        if rec.kind == "stonecutter":
            return self._layout_stonecutter(rec, title)
        if rec.kind == "smithing":
            return self._layout_smithing(rec, title)
        if rec.kind == "brewing":
            return self._layout_brewing(rec, title)
        lay = Layout(title=title)
        lay.notes.append(rec.note or f"unsupported recipe type {rec.raw_kind}")
        return lay

    @staticmethod
    def _station_title(rec: Recipe) -> str | None:
        """Title taken from the recipe's station tag, when we know a name for it."""
        for tag in rec.stations:
            key = str(tag)
            if key in STATION_TITLES:
                return STATION_TITLES[key]
            short = key.split(":")[-1]
            if short in STATION_TITLES:
                return STATION_TITLES[short]
        return None

    def _layout_crafting(self, rec: Recipe, title: str) -> Layout:
        rows, cols = max(1, rec.rows), max(1, rec.cols)
        gx, gy = self.metrics["grid"]
        # every crafting recipe is shown on the full 3x3 crafting table; the pattern
        # (or the shapeless ingredients, in reading order) starts at the top-left
        grid_rows = grid_cols = panel.GRID
        ox, oy = gx, gy
        lay = Layout(width=self.metrics["panel"][0], height=self.metrics["panel"][1], title=title,
                     title_pos=self.metrics["title"], title_align=self.metrics["title_align"],
                     title_span=(gx, gx + panel.GRID_AREA),
                     shapeless=(rec.kind == "shapeless"))
        for r in range(grid_rows):
            for c in range(grid_cols):
                ident = rec.grid[r][c] if r < len(rec.grid) and c < len(rec.grid[r]) else None
                lay.slots.append((ident, ox + c * panel.SLOT_SIZE, oy + r * panel.SLOT_SIZE,
                                  panel.SLOT_SIZE))
        lay.arrows.append(self.metrics["arrow"])
        if rec.result:
            rx, ry = self.metrics["result"]
            lay.result = (rec.result[0], rec.result[1], rx, ry, panel.RESULT_SIZE)
        return lay

    @staticmethod
    def _first_input(rec: Recipe):
        """The recipe's input: its declared input slot, else the first ingredient of
        the grid (a machine recipe written as recipe_shapeless has only that)."""
        inp = rec.special.get("input")
        if inp:
            return inp[0] if isinstance(inp, tuple) else inp
        for row in rec.grid:
            for cell in row:
                if cell:
                    return cell[0] if isinstance(cell, tuple) else cell
        return None

    def _layout_stonecutter(self, rec: Recipe, title: str) -> Layout:
        """Bedrock stonecutter screen: one 18x18 input slot, the large arrow and the
        26x26 result slot, with the row centred in a 176-wide panel (as in the game)."""
        cy = 30 + panel.SLOT_SIZE // 2                 # 39
        lay = Layout(width=176, height=80, title=title, title_align="center",
                     title_span=(0, 176))
        lay.slots.append((self._first_input(rec), 41, 30, panel.SLOT_SIZE))
        lay.arrows.append((72, cy - 7.5))
        if rec.result:
            lay.result = (rec.result[0], rec.result[1], 103, cy - 13, panel.RESULT_SIZE)
        return lay

    def _layout_smithing(self, rec: Recipe, title: str) -> Layout:
        """Bedrock smithing table screen, measured off the game's own UI definition
        (``ui/smithing_table_2_screen.json``) and the reference screenshot:

        a 30x30 station icon at the top-left, the centred title beside it, the three
        18x18 slots in a row with the game's template / material slot overlays, then
        the arrow and the 26x26 result slot.
        """
        lay = Layout(width=176, height=104, title=title, title_align="left",
                     title_pos=(38, 13))
        for ident, x in ((rec.special.get("template"), 10), (rec.special.get("base"), 28),
                         (rec.special.get("addition"), 46)):
            if isinstance(ident, tuple):
                ident = ident[0]
            lay.slots.append((ident, x, 56, panel.SLOT_SIZE))
        # the overlays are strips; the game reads one 16x16 frame via a uv animation
        lay.slot_art += [
            ("textures/ui/templates_slot_overlay.png", 11, 57, 16, 16, (0, 0, 16, 16)),
            ("textures/ui/smithing_material_slot_overlay.png", 47, 57, 16, 16, (0, 0, 16, 16)),
        ]
        lay.arrows.append((71, 58))
        if rec.result:
            lay.result = (rec.result[0], rec.result[1], 97, 52, panel.RESULT_SIZE)
        lay.sprites.append(("textures/ui/smithing_icon.png", 4, 4, 30, 30))
        return lay

    def _layout_row(self, rec: Recipe, title: str, inputs) -> Layout:
        cy = 30 + panel.SLOT_SIZE // 2                 # 39
        arrow_x = max(x + panel.SLOT_SIZE for _i, x, _y in inputs) + 10
        result_x = arrow_x + 22 + 8
        lay = Layout(width=result_x + panel.RESULT_SIZE + 24, height=80, title=title,
                     title_align="center")
        for ident, x, y in inputs:
            if isinstance(ident, tuple):
                ident = ident[0]
            if ident:
                lay.slots.append((ident, x, y, panel.SLOT_SIZE))
        lay.arrows.append((arrow_x, cy - 8))
        if rec.result:
            lay.result = (rec.result[0], rec.result[1], result_x, cy - 13, panel.RESULT_SIZE)
        return lay

    def _layout_furnace(self, rec: Recipe, title: str) -> Layout:
        cy = 43
        lay = Layout(width=124, height=80, title=title, title_align="center")
        inp = self._first_input(rec)
        if inp:
            lay.slots.append((inp, 22, 16, panel.SLOT_SIZE))
        lay.slots.append((None, 22, 54, panel.SLOT_SIZE))          # fuel slot (empty)
        lay.flames.append((22 + (panel.SLOT_SIZE - 14) // 2, 38))
        lay.arrows.append((44, cy - 8))
        if rec.result:
            lay.result = (rec.result[0], rec.result[1], 74, cy - 13, panel.RESULT_SIZE)
        return lay

    def _layout_brewing(self, rec: Recipe, title: str) -> Layout:
        """Bedrock brewing stand UI: fuel slot, ingredient slot, three bottle slots,
        the stand's pipes and the vertical progress arrow - measured off the game."""
        lay = Layout(width=176, height=80, title=title, title_align="center",
                     title_span=(0, 176))
        # fuel (empty, as in the game) + ingredient
        lay.slots.append((None, 8.75, 15.5, panel.SLOT_SIZE))
        lay.fuel.append((8.75, 15.5))
        reagent = rec.special.get("reagent")
        if isinstance(reagent, tuple):
            reagent = reagent[0]
        lay.slots.append((reagent, 79, 15.5, panel.SLOT_SIZE))
        # three bottles: the brewed potion sits in the middle one, as in the game
        lay.slots.append((None, 56, 49.5, panel.SLOT_SIZE))
        lay.slots.append((rec.result[0] if rec.result else None, 79, 56.5, panel.SLOT_SIZE))
        lay.slots.append((None, 102, 49.5, panel.SLOT_SIZE))
        for pos in ((56, 49.5), (79, 56.5), (102, 49.5)):
            lay.bottles.append(pos)
        # the pipe cluster is the game's own sprite (30x26) - no hand-drawn pipes, so
        # nothing can overlap the fuel bar the way it used to
        # decorations: the game's own UI definition (ui/brewing_stand_screen.json) gives
        # every element as an offset from the screen centre, and this panel is centred
        # on the ingredient slot the same way, so the offsets carry over directly.
        #   coil (-47,-5) 30x22 | bar (-23,3) 24x6 + fill 22x4 | bubbles (-23,-14) 12x30
        #   pipes (0,3) 30x26 | arrow (16,-14) 9x28
        cx, cy = 88, 42.5
        lay.sprites.append(("textures/ui/brewing_fuel_pipes.png", cx - 47 - 15, cy - 5 - 11, 30, 22))
        lay.sprites.append(("textures/ui/brewing_fuel_bar_empty.png", cx - 23 - 12, cy + 3 - 3, 24, 6))
        lay.sprites.append(("textures/ui/brewing_fuel_bar_full.png", cx - 23 - 11, cy + 3 - 2, 22, 4))
        lay.sprites.append(("textures/ui/bubbles_empty.png", cx - 23 - 6, cy - 14 - 15, 12, 30))
        lay.sprites.append(("textures/ui/bubbles_full.png", cx - 23 - 6, cy - 14 - 15, 12, 30))
        lay.sprites.append(("textures/ui/brewing_pipes.png", cx - 15, cy + 3 - 13, 30, 26))
        lay.sprites.append(("textures/ui/brewing_arrow_empty.png", cx + 16 - 4.5, cy - 14 - 14, 9, 28))
        return lay

    # -------------------------------------------------------------- draw
    def render(self, rec: Recipe) -> tuple[Image.Image, Layout]:
        lay = self.layout(rec)
        if not lay.slots and not lay.result:
            raise ValueError(lay.notes[0] if lay.notes else "nothing to draw")
        s = self.scale

        # 1) the GUI itself is 1x-per-unit, then scaled by the GUI scale (NEAREST)
        base = Image.new("RGBA", (lay.width, lay.height), (0, 0, 0, 0))
        panel.draw_panel(base, lay.width, lay.height)
        for x, y, w, h in lay.pipes:                    # behind the slots
            panel.draw_pipe(base, x, y, w, h)
        for _ident, x, y, size in lay.slots:
            panel.draw_slot(base, x, y, size)
        if lay.result:
            _ident, _count, x, y, size = lay.result
            panel.draw_slot(base, x, y, size)
        img = base if s == 1 else base.resize((lay.width * s, lay.height * s), Image.NEAREST)

        # 1b) slot decorations (empty fuel / empty bottle art from the vanilla UI)
        for x, y in lay.fuel:
            art = self.sprites.get("textures/ui/brewing_fuel_empty.png")
            if art is not None:
                panel.blit(img, art.resize((16 * s, 16 * s), Image.NEAREST),
                           int(round((x + 1) * s)), int(round((y + 1) * s)))
        bottle_art = self.sprites.get("textures/ui/bottle_empty.png")
        if bottle_art is not None:
            for x, y in lay.bottles:
                panel.blit(img, bottle_art.resize((16 * s, 16 * s), Image.NEAREST),
                           int(round((x + 1) * s)), int(round((y + 1) * s)))

        # 2) item and block icons are rasterised at the output resolution, so a
        #    64x64 block icon has a real 64x64 silhouette instead of 16x16 blocks
        for entry in lay.slot_art:
            path, x, y, w, h = entry[:5]
            crop = entry[5] if len(entry) > 5 else None
            art = self.sprites.get(path)
            if art is None:
                self.warnings.append(f"vanilla {path} missing")
                continue
            if crop:
                art = art.crop(crop)
            panel.blit(img, art.resize((max(1, int(round(w * s))), max(1, int(round(h * s)))),
                                       Image.NEAREST),
                       int(round(x * s)), int(round(y * s)))
        for ident, x, y, size in lay.slots:
            self._draw_item(img, ident, x, y, size)
        if lay.result:
            ident, count, x, y, size = lay.result
            self._draw_item(img, ident, x, y, size)
            if self.show_counts and count > 1:
                self._draw_count(img, x, y, size, count)

        # 3) vanilla sprites (arrow, furnace flame) are 1x-per-unit art
        arrow = self.sprites.arrow
        for x, y in lay.arrows:
            if arrow is not None:
                panel.blit(img, arrow.resize((arrow.width * s, arrow.height * s), Image.NEAREST),
                           int(round(x * s)), int(round(y * s)))
            else:
                self.warnings.append("vanilla textures/ui/arrow_large.png missing; arrow skipped")
        flame = self.sprites.flame
        for x, y in lay.flames:
            if flame is not None:
                panel.blit(img, flame.resize((flame.width * s, flame.height * s), Image.NEAREST),
                           int(round(x * s)), int(round(y * s)))
            else:
                self._draw_flame(img, x * s, y * s, s)

        # 3b) extra vanilla UI sprites, stretched to their GUI-unit box
        for entry in lay.sprites:
            path, x, y, w, h = entry[:5]
            crop = entry[5] if len(entry) > 5 else None
            sprite = self.sprites.get(path)
            if sprite is None:
                self.warnings.append(f"vanilla {path} missing")
                continue
            if crop:
                sprite = sprite.crop(crop)
            panel.blit(img, sprite.resize((int(round(w * s)), int(round(h * s))), Image.NEAREST),
                       int(round(x * s)), int(round(y * s)))

        # 4) title: the 16x16 glyph cell is laid into an 8-unit box at output
        #    resolution - exactly how Bedrock renders CJK
        if lay.title:
            box = self.title_unit * s
            width = len(lay.title) * box
            if lay.title_align == "center":
                lo, hi = lay.title_span or (0, lay.width)
                tx = int(((lo + hi) * s - width) // 2)
                ty = int(round(lay.title_pos[1] * s))
            else:
                tx, ty = int(round(lay.title_pos[0] * s)), int(round(lay.title_pos[1] * s))
            self.font.draw_crisp(img, tx, ty, lay.title, TITLE_COLOR, unit=self.title_unit, scale=s)

        # 5) shapeless recipes carry Bedrock's shuffle mark in the bottom-right corner
        if lay.shapeless:
            self._draw_shapeless(img, lay)

        if self.background:
            bg = Image.new("RGBA", img.size, ImageColor.getrgb(self.background) + (255,))
            bg.alpha_composite(img)
            img = bg
        for note in lay.notes:
            self.warnings.append(f"{rec.identifier or rec.path}: {note}")
        return img, lay

    def _draw_item(self, img: Image.Image, ident: str, x: int, y: int, size: int) -> None:
        if isinstance(ident, tuple):                 # (item, count) pairs from parsed recipes
            ident = ident[0]
        if not ident:                                # empty slot: the slot art is already drawn
            return
        if ident and str(ident).startswith("tag:"):
            tag = str(ident)[4:]
            resolved = (TAG_ITEMS.get(tag) or TAG_ITEMS.get("minecraft:" + tag.split(":")[-1])
                        or self.assets.tag_items.get(tag))   # tags the pack itself declares
            if resolved:
                self.warnings.append(f"item tag {tag} drawn as {resolved}")
                ident = resolved
            else:
                self.warnings.append(f"item tag {tag} has no representative item; missing texture")
                ident = None
        sprite = None
        if ident:
            icon = self.assets.resolve(ident)
            sprite = icon.render(16 * self.scale)
            if icon.kind == "missing":
                self.warnings.append(f"missing texture for {ident}")
        if sprite is None:
            from .icon import missing_texture
            sprite = missing_texture(16 * self.scale)
        off = ((size - 16) // 2) * self.scale
        img.alpha_composite(sprite, (int(round(x * self.scale)) + off,
                                     int(round(y * self.scale)) + off))

    def _draw_count(self, img: Image.Image, x: int, y: int, size: int, count: int) -> None:
        """Vanilla stack-count badge: bottom-right of the item, white with a shadow."""
        s = self.scale
        text = str(count)
        off = (size - 16) // 2
        tx = (x + off + 17) * s - ascii_advance(text) * s
        draw_ascii(img, tx, (y + off + 9) * s, text, WHITE_TEXT, SHADOW, scale=s)

    def _draw_shapeless(self, img: Image.Image, lay: Layout) -> None:
        """Bedrock's shuffle mark: bottom-right corner of the panel, for shapeless recipes."""
        mark = _load_mark()
        s = self.scale
        h = len(mark)
        w = max(len(r) for r in mark)
        x0 = int(round((lay.width - SHAPELESS_RIGHT_MARGIN - w) * s))
        y0 = int(round((lay.height - SHAPELESS_BOTTOM_MARGIN - h) * s))
        px = img.load()
        for ry, row in enumerate(mark):
            for rx, ch in enumerate(row):
                if ch == ".":
                    continue
                for dy in range(s):
                    for dx in range(s):
                        tx, ty = x0 + rx * s + dx, y0 + ry * s + dy
                        if 0 <= tx < img.width and 0 <= ty < img.height:
                            px[tx, ty] = MARK_COLOR

    def _draw_flame(self, img: Image.Image, x: int, y: int, s: int) -> None:
        """Fallback 14x14 vanilla-style furnace flame (drawn at output scale)."""
        rows = [
            ".....###......",
            "....#####.....",
            "....#####.....",
            "...#######....",
            "...##OOO##....",
            "..##OOOOO##...",
            "..#OOOOOOO#...",
            ".############.",
            "..##OOOOO##...",
            "....#####.....",
            ".....###......",
        ]
        px = img.load()
        colors = {"#": (255, 160, 0, 255), "O": (255, 235, 100, 255)}
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                if ch not in colors:
                    continue
                for dy in range(s):
                    for dx in range(s):
                        tx, ty = x + rx * s + dx, y + ry * s + dy
                        if 0 <= tx < img.width and 0 <= ty < img.height:
                            px[tx, ty] = colors[ch]
