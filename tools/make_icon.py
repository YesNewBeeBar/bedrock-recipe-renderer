"""Generate the window / exe icon from the tool's own block renderer.

Renders the vanilla crafting table exactly the way the tool renders every other
block, then writes ``assets/icon.png`` and a multi-size ``assets/icon.ico``.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from mcrender.assets import Assets          # noqa: E402

OUT = os.path.join(ROOT, "assets")


def main() -> int:
    import json
    cfg_path = os.path.join(ROOT, "config.json")
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)

    assets = Assets(bp_dir=cfg.get("bp"), rp_dir=cfg.get("rp"),
                    vanilla_dir=cfg.get("vanilla"), tool_root=ROOT,
                    wiki_icons="never", vanilla_download=True)

    icon = assets.resolve("minecraft:crafting_table")
    if icon.kind == "missing":
        print("crafting_table texture not found; falling back to stone")
        icon = assets.resolve("minecraft:stone")
    base = icon.render(64)
    print("base render:", icon.kind, base.size)

    os.makedirs(OUT, exist_ok=True)
    big = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    big.paste(base.resize((256, 256), Image.NEAREST), (0, 0))
    big.save(os.path.join(OUT, "icon.png"))

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    frames = [big.resize(size, Image.LANCZOS if size[0] < 64 else Image.NEAREST)
              for size in sizes]
    frames[-1].save(os.path.join(OUT, "icon.ico"), format="ICO",
                    sizes=[size for size in sizes])
    print("wrote", os.path.join(OUT, "icon.png"), "and icon.ico")
    return 0


if __name__ == "__main__":
    sys.exit(main())
