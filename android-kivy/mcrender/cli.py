"""Command line interface: render every Bedrock recipe as a crafting-table image."""
from __future__ import annotations

import argparse
import os
import sys

from . import icon
from . import recipes as recipes_mod
from .assets import Assets
from .render import Renderer

# no personal paths baked in: everything comes from the command line or config.json
DEFAULT_BP = ""
DEFAULT_RP = ""
DEFAULT_VANILLA = ""
DEFAULT_OUT = ""

SUPPORTED = ("shaped", "shapeless", "furnace", "stonecutter", "smithing", "brewing")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mcrender",
                                description="Render Bedrock addon recipes as Minecraft crafting panels.")
    p.add_argument("--bp", default=DEFAULT_BP, help="behaviour pack (folder containing recipes/)")
    p.add_argument("--rp", default=DEFAULT_RP, help="resource pack used for textures")
    p.add_argument("--vanilla", default=DEFAULT_VANILLA,
                   help="vanilla/sample resource pack used as the fallback texture source")
    p.add_argument("--recipes", default=None, help="recipes folder (default: <bp>/recipes)")
    p.add_argument("--out", default=DEFAULT_OUT,
                   help="output folder (default: the 备份\\合成表 backup folder)")
    p.add_argument("--scale", type=int, default=4, help="integer upscale of the 1x panel (default 4)")
    p.add_argument("--title", default=None, help="override the panel title text")
    p.add_argument("--title-size", type=int, default=8,
                   help="title glyph size in panel pixels (vanilla renders CJK at 8)")
    p.add_argument("--layout", choices=("classic", "modern"), default="modern",
                   help="panel metrics: 'modern' = current Bedrock UI (default, matches the "
                        "latest screenshots), 'classic' = the compact first reference panel")
    p.add_argument("--kind", default=",".join(SUPPORTED),
                   help="comma separated recipe kinds to render")
    p.add_argument("--filter", action="append", default=[],
                   help="only render recipes whose path/identifier contains this text (repeatable)")
    p.add_argument("--limit", type=int, default=0, help="stop after N recipes")
    p.add_argument("--no-counts", action="store_true", help="do not draw result count badges")
    p.add_argument("--cube-shading", choices=("vanilla", "reference"), default="vanilla",
                   help="block cube face shading: vanilla factors, or the ones fitted to the reference shot")
    p.add_argument("--background", default="none",
                   help="'none' for transparency, or a colour like #C6C6C6 / white")
    p.add_argument("--list", action="store_true", help="list matching recipes and exit")
    p.add_argument("--report", default=None, help="report path (default <out>/_report.md)")
    p.add_argument("--quiet", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    recipes_dir = args.recipes or os.path.join(args.bp, "recipes")
    if not os.path.isdir(recipes_dir):
        print(f"recipes folder not found: {recipes_dir}", file=sys.stderr)
        return 2

    kinds = {k.strip() for k in args.kind.split(",") if k.strip()}
    all_recipes = recipes_mod.collect(recipes_dir)
    picked = []
    for rec in all_recipes:
        if rec.kind not in kinds:
            continue
        if args.filter and not any(f.lower() in (rec.path + " " + rec.identifier).lower()
                                   for f in args.filter):
            continue
        picked.append(rec)
    if args.limit:
        picked = picked[:args.limit]

    if args.list:
        for rec in picked:
            print(f"{rec.kind:11s} {rec.identifier or os.path.basename(rec.path):55s} {rec.path}")
        print(f"\n{len(picked)} of {len(all_recipes)} recipes selected")
        return 0

    assets = Assets(bp_dir=args.bp, rp_dir=args.rp, vanilla_dir=args.vanilla)
    icon.set_shading(args.cube_shading)
    renderer = Renderer(assets, scale=args.scale, title=args.title,
                        show_counts=not args.no_counts,
                        background=None if args.background in ("none", "") else args.background,
                        glyph_size=args.title_size, layout=args.layout)

    os.makedirs(args.out, exist_ok=True)
    rows, skipped, failures = [], [], []
    for rec in picked:
        rel = os.path.relpath(rec.path, recipes_dir)
        target = os.path.splitext(rel)[0] + ".png"
        try:
            img, lay = renderer.render(rec)
        except Exception as exc:
            skipped.append((rec, str(exc)))
            continue
        dest = os.path.join(args.out, target)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        img.save(dest)
        rows.append((rec, target, lay))
        if not args.quiet:
            print(f"  {target}")

    used, missing = set(), set()
    for ident in (i for rec in picked for i in rec.items()):
        if not str(ident).startswith("tag:"):
            used.add(ident)
    for ident in sorted(used):
        if assets.resolve(ident).kind == "missing":
            missing.add(ident)

    report = args.report or os.path.join(args.out, "_report.md")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write("# Recipe render report\n\n")
        fh.write(f"- behaviour pack: `{args.bp}`\n- resource pack: `{args.rp}`\n")
        fh.write(f"- vanilla pack: `{args.vanilla}`\n- scale: {args.scale}x\n\n")
        fh.write(f"rendered: **{len(rows)}**, skipped: **{len(skipped)}**, "
                 f"distinct items: **{len(used)}**, items without textures: **{len(missing)}**\n\n")
        if missing:
            fh.write("## Items without textures\n\n")
            for ident in sorted(missing):
                fh.write(f"- `{ident}`\n")
            fh.write("\n")
        if skipped:
            fh.write("## Skipped\n\n")
            for rec, why in skipped:
                fh.write(f"- `{os.path.relpath(rec.path, recipes_dir)}` — {why}\n")
            fh.write("\n")
        if renderer.warnings:
            fh.write("## Warnings\n\n")
            for warning in sorted(set(renderer.warnings)):
                fh.write(f"- {warning}\n")
        fh.write("\n## Rendered\n\n")
        for rec, target, lay in rows:
            fh.write(f"- [{rec.kind}] `{rec.identifier or rec.path}` → `{target}`\n")

    print(f"\n{len(rows)} image(s) written to {args.out}")
    if skipped:
        print(f"{len(skipped)} recipe(s) skipped (see {report})")
    if missing:
        print(f"{len(missing)} item(s) have no texture (see {report})")
    print(f"report: {report}")
    return 0
