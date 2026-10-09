"""Extract CJK glyph bitmaps from a crisp in-game screenshot.

Bedrock renders a CJK glyph by laying the 16x16 font cell into an 8 GUI-unit box
at screen resolution, so at GUI scale 4 each glyph is a 32x32 block of 2x2
uniform pixels.  That makes the original 16x16 bitmap exactly recoverable.

usage:
    python -m tools.extract_glyphs <screenshot.png> "合成" --region 100 10 420 80 [--scale 4]
"""
from __future__ import annotations

import argparse
import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GLYPH_FILE = os.path.join(HERE, "mcrender", "glyphs.json")


def load_glyphs() -> dict:
    if os.path.exists(GLYPH_FILE):
        with open(GLYPH_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_glyphs(data: dict) -> None:
    with open(GLYPH_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)


def uniform_score(px, bx, by, text: str, scale: int, thr: int = 128) -> int:
    """How many 2x2 pixel blocks inside the text box are uniform (0..2)?  A
    correctly aligned box is made of uniform 2x2 blocks only."""
    good = bad = 0
    for gi in range(len(text)):
        for sy in range(16 * scale // 2 * 2 // scale):
            pass
    width = len(text) * 8 * scale
    height = 8 * scale
    for y in range(by, by + height, 2):
        for x in range(bx, bx + width, 2):
            vals = [px[x + dx, y + dy][0] for dx in (0, 1) for dy in (0, 1)]
            if max(vals) - min(vals) <= 8:
                good += 1
            else:
                bad += 1
    return good - bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("text")
    ap.add_argument("--region", nargs=4, type=int, required=True,
                    metavar=("X0", "Y0", "X1", "Y1"), help="search area for the title")
    ap.add_argument("--scale", type=int, default=4)
    ap.add_argument("--threshold", type=int, default=150)
    ap.add_argument("--box", nargs=2, type=int, metavar=("X", "Y"),
                    help="exact glyph box origin (skip the automatic search)")
    args = ap.parse_args(argv)

    im = Image.open(args.image).convert("RGB")
    px = im.load()
    x0, y0, x1, y1 = args.region
    ink = [(x, y) for y in range(y0, y1) for x in range(x0, x1) if px[x, y][0] < args.threshold]
    if not ink:
        print("no text pixels found in that region")
        return 2
    ix = min(p[0] for p in ink)
    iy = min(p[1] for p in ink)
    ax = max(p[0] for p in ink)
    ay = max(p[1] for p in ink)
    width = len(args.text) * 8 * args.scale
    height = 8 * args.scale

    if args.box:
        bx, by = args.box
        score = uniform_score(px, bx, by, args.text, args.scale)
        print(f"text box origin: ({bx}, {by})  uniformity score {score} (given)")
    else:
        best = None
        for by in range(iy - 8, iy + 9):
            for bx in range(ix - 8, ix + 9):
                if by < 0 or bx < 0:
                    continue
                if not (bx <= ix and bx + width > ax and by <= iy and by + height > ay):
                    continue                     # the box must contain every ink pixel
                s = uniform_score(px, bx, by, args.text, args.scale)
                if best is None or s > best[0]:
                    best = (s, bx, by)
        if best is None:
            print("could not fit an 8-unit-per-glyph box around the text; pass --box")
            return 2
        score, bx, by = best
        print(f"text box origin: ({bx}, {by})  uniformity score {score} (searched)")

    data = load_glyphs()
    box = 8 * args.scale
    for gi, ch in enumerate(args.text):
        if ch == " ":
            continue
        rows = []
        for sy in range(16):
            row = 0
            for sx in range(16):
                v = px[bx + gi * box + sx * (args.scale // 2), by + sy * (args.scale // 2)][0]
                if v < args.threshold:
                    row |= 1 << sx
            rows.append(row)
        data[ch] = rows
        print(f"  {ch}: " + " ".join(f"{r:04x}" for r in rows))
    save_glyphs(data)
    print(f"glyph cache now holds {len(data)} character(s): {''.join(sorted(data))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
