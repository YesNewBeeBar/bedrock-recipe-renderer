#!/usr/bin/env python
"""复现 6 个 issue：渲染问题配方，与用户提供的对照图做像素对比。

用法： python repro_issues.py
产出： .\_repro\ 下渲染结果 + 控制台报告（哪些与对照图不同）
"""
import os
import shutil
import sys
import tempfile
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from mcrender.assets import Assets           # noqa: E402
from mcrender.recipes import collect, parse  # noqa: E402
from mcrender.render import Renderer         # noqa: E402

ARC = r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip"
REF = r"C:\Users\NewBee_Bar\Pictures\合成表\crafting"
OUT = os.path.join(HERE, "_repro")

CASES = ["beacon_ball", "shield_ball", "bucket_ball", "lava_bucket_ball",
         "milk_bucket_ball", "sulfur_ball", "dirt", "dragon_fireball"]


def main() -> int:
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT, exist_ok=True)

    work = tempfile.mkdtemp()
    with zipfile.ZipFile(ARC) as z:
        z.extractall(work)

    bp = rp = None
    for base, _d, files in os.walk(work):
        if "manifest.json" not in files:
            continue
        if os.path.isdir(os.path.join(base, "recipes")):
            bp = base
        if os.path.isdir(os.path.join(base, "textures")):
            rp = base
    print("BP:", bp and os.path.basename(bp), "| RP:", rp and os.path.basename(rp))

    recs = collect(bp)
    print("配方总数:", len(recs))

    assets = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=r"D:\合成表生成器移动端ndroid-kivyanilla",
                    wiki_root=r"D:\合成表生成器\wiki_cache", wiki_icons="auto",
                    wiki_language="en", vanilla_download=False, local_only=False,
                    tool_root=HERE, bundle_root=HERE)
    rend = Renderer(assets, scale=4, layout="modern", background=None)

    print("\n=== 问题用例 ===")
    for rec in recs:
        name = os.path.splitext(os.path.basename(rec.path))[0]
        if name not in CASES:
            continue
        try:
            img, lay = rend.render(rec)
        except Exception as exc:
            print(f"  {name}: 渲染异常 {type(exc).__name__} {exc}")
            continue
        out = os.path.join(OUT, name + ".png")
        img.save(out)

        # 配方内容摘要
        items = []
        for slot in (getattr(rec, "grid", None) or []):
            if slot is not None:
                items.append(getattr(slot, "ident", str(slot)))
        detail = f"kind={rec.kind} 输入={items}"
        note = f"  {name}: {detail}"

        ref = os.path.join(REF, name + ".png")
        if os.path.isfile(ref):
            a = Image.open(out).convert("RGB")
            b = Image.open(ref).convert("RGB")
            if a.size == b.size:
                diff = sum(1 for x, y in zip(a.getdata(), b.getdata()) if x != y)
                note += f" | 与对照图差异像素 {diff}/{a.size[0]*a.size[1]}"
            else:
                note += f" | 尺寸不同 {a.size} vs {b.size}"
        print(note)

    print("\n渲染结果:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
