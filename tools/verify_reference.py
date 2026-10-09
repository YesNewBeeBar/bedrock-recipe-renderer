"""Verify a render against the reference material supplied with the request.

Two modes:

``--layout modern``   compares against the *crisp* in-game screenshot (GUI scale 4,
                      panel outer corner at 11,12).  Pixel-exact for everything the
                      game draws; item art is skipped, because the screenshot was
                      taken with a lighting resource pack active.
``--layout classic``  compares against the first (blurred, 3.6x upscaled) reference
                      at logical resolution.

usage:
    python -m tools.verify_reference --layout modern  [render.png] [screenshot.png]
    python -m tools.verify_reference --layout classic [render.png] [reference.png]
"""
from __future__ import annotations

import argparse
import statistics
import sys

from PIL import Image

# reference screenshots are supplied on the command line (--shot / --render):
# no local paths are baked into the repository
MODERN_SHOT = ""
MODERN_RENDER = ""
CLASSIC_SHOT = ""

# GUI palette: anything else is item art / the world and is not compared
GUI_COLOURS = {(198, 198, 198), (139, 139, 139), (255, 255, 255), (55, 55, 55),
               (85, 85, 85), (0, 0, 0), (76, 76, 76), (253, 253, 253)}
PALETTE = {".": (253, 253, 253), "K": (0, 0, 0), "W": (255, 255, 255), "D": (85, 85, 85),
           "S": (139, 139, 139), "P": (198, 198, 198), "t": (55, 55, 55), "T": (76, 76, 76)}


def gui_only(colour) -> bool:
    return tuple(colour[:3]) in GUI_COLOURS


def classify(colour) -> str:
    return min(PALETTE, key=lambda k: sum((a - b) ** 2 for a, b in zip(colour[:3], PALETTE[k])))


def load_flat(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    flat = Image.new("RGB", im.size, (253, 253, 253))
    flat.paste(im, (0, 0), im)
    return flat


def compare_modern(render_path: str, shot_path: str, offset=(11, 12)) -> int:
    mine = Image.open(render_path).convert("RGBA")
    if mine.width % 176:                       # not the modern panel width
        print("warning: render is not 176 units wide; pass --layout classic instead")
    flat = load_flat(render_path)
    ref = Image.open(shot_path).convert("RGB")
    rp, mp = ref.load(), flat.load()
    ox, oy = offset
    bad = tot = gui = 0
    worst = []
    # the screenshot's panel continues into the (cropped) inventory section, so its
    # bottom border is not part of the reference; the right edge sits on a
    # fractional UI unit in the game and may differ by one pixel
    x_limit = flat.width - 4
    y_limit = min(flat.height - 12, ref.height - oy)
    for y in range(y_limit):
        for x in range(x_limit):
            a = rp[ox + x, oy + y]
            b = mp[x, y]
            tot += 1
            if not (gui_only(a) and gui_only(b)):
                continue                        # item art / world: not comparable
            gui += 1
            if max(abs(a[k] - b[k]) for k in range(3)) > 2:
                bad += 1
                if len(worst) < 12:
                    worst.append((x, y, a, b))
    print(f"render    : {render_path}")
    print(f"screenshot: {shot_path}")
    print(f"compared {gui} GUI pixels of {tot} ({gui / tot:.1%}); the rest is item art")
    print(f"pixel mismatches: {bad} = {bad / max(1, gui):.3%}")
    for w in worst[:8]:
        print("   at", w[0], w[1], "ref", w[2], "mine", w[3])
    return 0 if bad / max(1, gui) < 0.02 else 1


def compare_classic(render_path: str, ref_path: str) -> int:
    scale_s, panel_origin = 3.6, (18.0, 11.0)
    mine = Image.open(render_path).convert("RGBA")
    if mine.width // 160 > 1:
        step = mine.width // 160
        mine = mine.resize((mine.width // step, mine.height // step), Image.NEAREST)
    flat = load_flat(render_path) if mine.width == Image.open(render_path).width else None
    flat = load_flat(render_path)
    ref = Image.open(ref_path).convert("RGB")
    rp, mp = ref.load(), flat.load()
    width, height = min(160, flat.width), min(80, flat.height)

    def ref_cell(i, j):
        x0 = int(round(panel_origin[0] + scale_s * i))
        y0 = int(round(panel_origin[1] + scale_s * j))
        vals = [rp[x, y] for y in range(y0, min(ref.height, y0 + int(scale_s)))
                for x in range(x0, min(ref.width, x0 + int(scale_s)))]
        return tuple(int(statistics.median(v[k] for v in vals)) for k in range(3))

    diff = struct = 0
    rows = []
    for j in range(height):
        row = ""
        for i in range(width):
            a, b = classify(ref_cell(i, j)), classify(mp[i, j])
            if a == b:
                row += "."
            else:
                diff += 1
                if (a in "KPWDtT") != (b in "KPWDtT"):
                    struct += 1
                    row += "!"
                else:
                    row += "-"
        rows.append(f"{j:3d} {row}")
    total = width * height
    print(f"render    : {render_path}")
    print(f"reference : {ref_path}")
    print(f"logical panel: {width}x{height}")
    print(f"mismatched cells : {diff}/{total} = {diff / total:.2%}")
    print(f"structural diffs : {struct} ({struct / total:.2%})")
    print("\n".join(rows[:4]))
    return 0 if struct / total < 0.02 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("render", nargs="?", default=MODERN_RENDER)
    ap.add_argument("reference", nargs="?")
    ap.add_argument("--layout", choices=("modern", "classic"), default="modern")
    args = ap.parse_args(argv)
    if not args.render:
        print("用法: verify_reference.py <渲染出的png> [参考截图] [--layout modern|classic]")
        return 2
    if args.layout == "modern":
        return compare_modern(args.render, args.reference or MODERN_SHOT)
    return compare_classic(args.render, args.reference or CLASSIC_SHOT)


if __name__ == "__main__":
    sys.exit(main())
