"""Vanilla-style bitmap text.

CJK (and anything else present in the vanilla glyph pages) is taken from the
official glyph sheets shipped in the Bedrock sample resource pack
(``texts/<lang>/font/glyph_XX.png``: 256x256 pages holding 16x16 cells of
16x16 glyphs).  Minecraft draws those pages at half size, so every glyph is
box-filtered down to ``size``x``size`` (8x8 by default).

The ASCII digits used by the item-count badge are not part of the sample pack
(it ships no ``glyph_00`` page), so a hand-authored 5x7 pixel font with
Minecraft's metrics (6px advance, 8px line) is used for ASCII.
"""
from __future__ import annotations

import glob
import json
import os
from functools import lru_cache

from PIL import Image


_SYSTEM_FONTS = (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                 r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\simsun.ttc")
_FONT_CACHE: dict = {}
_SYSTEM_GLYPH_CACHE: dict = {}


def system_glyph(ch: str, size: int = 8) -> Image.Image | None:
    """A glyph drawn from a system CJK font, fitted to the 16x16 cell.

    The game's CJK glyphs are two-level bitmaps with roughly 2px strokes; a system
    font at 16px has thinner strokes and its ink can spill out of the cell (which cut
    the last character of a title).  So the glyph is rendered a little smaller,
    centred, binarised and thickened by one pixel.
    """
    key = (ch, size)
    if key in _SYSTEM_GLYPH_CACHE:
        return _SYSTEM_GLYPH_CACHE[key]
    font = _FONT_CACHE.get("font")
    if font is None and "font" not in _FONT_CACHE:
        from PIL import ImageFont
        font = None
        for path in _SYSTEM_FONTS:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, 16)
                    break
                except Exception:
                    font = None
        _FONT_CACHE["font"] = font
    if font is None:
        _SYSTEM_GLYPH_CACHE[key] = None
        return None
    from PIL import ImageDraw
    canvas = Image.new("L", (16, 16), 0)
    draw = ImageDraw.Draw(canvas)
    # centre the ink inside the cell: a 16px face can spill a pixel or two, which used
    # to clip the last character of a longer title
    box = draw.textbbox((0, 0), ch, font=font)
    x = max(0, (16 - (box[2] - box[0])) // 2) - min(0, box[0])
    y = max(0, (16 - (box[3] - box[1])) // 2) - min(0, box[1])
    draw.text((x, y), ch, font=font, fill=255)
    mask = canvas.point(lambda v: 255 if v >= 96 else 0)          # binarise
    out = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    out.putalpha(mask)
    if size != 16:
        out = out.resize((size, size), Image.BOX)
    _SYSTEM_GLYPH_CACHE[key] = out
    return out

_GLYPH_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glyphs.json")


@lru_cache(maxsize=1)
def builtin_glyphs() -> dict:
    """16x16 glyph bitmaps recovered from the user's own screenshots.

    The sample pack only ships zh_TW/ja_JP pages; the game itself renders with the
    (taller) zh_CN glyphs, so those characters are extracted from crisp screenshots
    with ``tools/extract_glyphs.py`` and take precedence over the pages.
    """
    if not os.path.exists(_GLYPH_CACHE):
        return {}
    with open(_GLYPH_CACHE, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = {}
    for ch, rows in raw.items():
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = img.load()
        for y, bits in enumerate(rows):
            for x in range(16):
                if bits >> x & 1:
                    px[x, y] = (255, 255, 255, 255)
        out[ch] = img
    return out

# ---------------------------------------------------------------- ASCII font
_ASCII_DIGITS = {
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
}
ASCII_WIDTH = 6      # 5px glyph + 1px advance
ASCII_HEIGHT = 8     # line height, glyph occupies the lower 7 rows


def ascii_advance(text: str) -> int:
    return len(text) * ASCII_WIDTH


def draw_ascii(img: Image.Image, x: int, y: int, text: str, color, shadow=None,
               scale: int = 1) -> None:
    """Draw ASCII digits; (x, y) is the top-left of the 8px line box.

    ``scale`` draws every font pixel as a ``scale``x``scale`` block, matching the
    game at GUI scale N.
    """
    px = img.load()
    for i, ch in enumerate(text):
        rows = _ASCII_DIGITS.get(ch)
        if rows is None:
            continue
        gx = x + i * ASCII_WIDTH * scale
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit != "1":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        if shadow is not None:
                            tx, ty = gx + rx * scale + sx + scale, y + ry * scale + sy + scale
                            if 0 <= tx < img.width and 0 <= ty < img.height:
                                px[tx, ty] = shadow
                        tx, ty = gx + rx * scale + sx, y + ry * scale + sy
                        if 0 <= tx < img.width and 0 <= ty < img.height:
                            px[tx, ty] = color


# ----------------------------------------------------------- CJK glyph pages
class GlyphSheets:
    """Loads vanilla ``texts/<lang>/font/glyph_XX.png`` pages."""

    LANGS = ("zh_CN", "zh_TW", "ja_JP", "ko_KR")

    def __init__(self, vanilla_root=None, source=None):
        self.root = vanilla_root if isinstance(vanilla_root, str) else None
        self.source = source if source is not None else (
            None if isinstance(vanilla_root, str) else vanilla_root)
        self.font_dir = None
        self.lang = None
        if self.root:
            texts = os.path.join(self.root, "texts")
            for lang in self.LANGS + ("*",):
                cand = os.path.join(texts, lang, "font")
                if glob.glob(os.path.join(cand, "glyph_*.png")):
                    self.font_dir = cand
                    break
        elif self.source is not None:
            for lang in self.LANGS:
                path = self.source.find(f"texts/{lang}/font/glyph_00.png", extensions=(".png",))
                if path:
                    self.font_dir = os.path.dirname(path)
                    self.lang = lang
                    break
        self._cache: dict[str, Image.Image | None] = {}

    @property
    def available(self) -> bool:
        return self.font_dir is not None

    def _page_path(self, key: str):
        if self.source is not None and self.lang:
            hit = self.source.find(f"texts/{self.lang}/font/glyph_{key}.png", extensions=(".png",))
            if hit:
                return hit
        if self.font_dir:
            path = os.path.join(self.font_dir, f"glyph_{key}.png")
            if os.path.exists(path):
                return path
        return None

    def _page(self, page: int) -> Image.Image | None:
        key = f"{page:02X}"
        if key not in self._cache:
            path = self._page_path(key)
            try:
                self._cache[key] = Image.open(path).convert("RGBA") if path else None
            except Exception:
                self._cache[key] = None
        return self._cache[key]

    def glyph(self, ch: str, size: int = 8) -> Image.Image | None:
        """Return an ``size``x``size`` alpha glyph, or None if unavailable."""
        builtin = builtin_glyphs().get(ch)
        if builtin is not None:
            return builtin if size == 16 else builtin.resize((size, size), Image.BOX)
        cp = ord(ch)
        page = self._page(cp >> 8)
        if page is not None:
            cell = page.width // 16
            idx = cp & 0xFF
            glyph = page.crop(((idx % 16) * cell, (idx // 16) * cell,
                               (idx % 16) * cell + cell, (idx // 16) * cell + cell))
            if cell != size:
                glyph = glyph.resize((size, size), Image.BOX)
            return glyph
        # anything the shipped sheets do not carry (a title such as 升级装备):
        # rasterise a 16x16 cell from a system font and binarise it, so it stays crisp
        # pixel art instead of a blurry anti-aliased downscale
        return system_glyph(ch, size)

    def draw(self, img: Image.Image, x: int, y: int, text: str, color, size: int = 8,
             shadow=None) -> int:
        """Draw text with the glyph pages; returns the advance width."""
        alpha = img.split()[-1] if img.mode == "RGBA" else None
        stroke = Image.new("RGBA", (size, size), color)
        tinte = Image.new("RGBA", img.size, (0, 0, 0, 0))
        cursor = x
        for ch in text:
            g = self.glyph(ch, size)
            if g is not None:
                if shadow is not None:
                    sh = Image.new("RGBA", (size, size), shadow)
                    tinte.paste(sh, (cursor + 1, y + 1), g)
                tinte.paste(stroke, (cursor, y), g)
                cursor += size
            else:
                if shadow is not None:
                    draw_ascii(tinte, cursor + 1, y + 1, ch, shadow)
                draw_ascii(tinte, cursor, y, ch, color)
                cursor += ASCII_WIDTH
        img.alpha_composite(tinte)
        return cursor - x

    def measure_crisp(self, text: str, unit: int = 8, scale: int = 1) -> int:
        return len(text) * unit * scale

    def draw_crisp(self, img: Image.Image, x: int, y: int, text: str, color,
                   unit: int = 8, scale: int = 1) -> int:
        """Draw text the way Bedrock does: the 16x16 glyph cell is laid into a
        ``unit``x``unit`` UI box at the *screen* resolution (NEAREST), so at GUI
        scale 4 every glyph pixel becomes a crisp 2x2 block instead of a
        half-resolution, filtered bitmap.

        `x`/`y` are in output pixels; returns the advance width in pixels.
        """
        box = unit * scale
        cursor = x
        for ch in text:
            src = self.glyph(ch, 16)
            if src is None:
                draw_ascii(img, cursor, y + scale, ch, color, scale=scale)
                cursor += ASCII_WIDTH * scale
                continue
            big = src.resize((box, box), Image.NEAREST)
            layer = Image.new("RGBA", big.size, color)
            img.paste(layer, (cursor, y), big)
            cursor += box
        return cursor - x
