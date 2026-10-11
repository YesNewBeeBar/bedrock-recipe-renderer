#!/usr/bin/env python
"""分析一批出图：哪些有缺失占位、按类别统计，并与本机重渲的结果对比。"""
import io
import os
import sys
import tempfile
import zipfile
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))

ZIP = (r"D:\wechat\xwechat_files\wxid_3k448ibotd0d22_40d3\msg\file"
       r"\2026-10\合成表.zip")
VANILLA = os.path.join(HERE, "android-kivy", "vanilla")
MCADDON = (r"D:\wechat\xwechat_files\wxid_3k448ibotd0d22_40d3\msg\file"
           r"\2026-10\磐石之旅v1.2.1(1.26.40+)(2).mcaddon")


def magenta(im):
    px = im.convert("RGB").getdata()
    return sum(1 for r, g, b in px if r > 200 and b > 200 and g < 60)


def main() -> int:
    if not os.path.isfile(ZIP):
        print("找不到", ZIP)
        return 1
    d = tempfile.mkdtemp()
    with zipfile.ZipFile(ZIP) as z:
        z.extractall(d)
    files = [os.path.join(b, f) for b, _dd, fs in os.walk(d) for f in fs
             if f.lower().endswith(".png")]
    print(f"共 {len(files)} 张图")
    bad, good = [], []
    cat = Counter()
    for fp in files:
        try:
            n = magenta(Image.open(fp))
        except Exception:
            continue
        rel = os.path.relpath(fp, d)
        top = rel.split(os.sep)[0]
        cat[top] += 1
        (bad if n > 20 else good).append((rel, n))
    print(f"有缺失占位 {len(bad)} 张 / 正常 {len(good)} 张")
    print("目录分布:", dict(cat))
    print("\n有缺失的（前 25）:")
    for rel, n in bad[:25]:
        print(f"   {rel}  紫 {n}")

    if not bad:
        return 0

    # 本机重渲其中一张做对比
    from mcrender.assets import Assets
    from mcrender.recipes import collect
    from mcrender.render import Renderer
    from platform_layer import picking
    if not os.path.isfile(MCADDON):
        return 0
    work = tempfile.mkdtemp()
    root = picking.unpack_archive(MCADDON, work)
    bp = rp = None
    for base, _dd, fs in os.walk(root):
        if "manifest.json" not in fs:
            continue
        if os.path.isdir(os.path.join(base, "recipes")):
            bp = base
        if os.path.isdir(os.path.join(base, "textures")):
            rp = base
    print("\nBP:", bp and os.path.basename(bp), "RP:", rp and os.path.basename(rp))
    recs = collect(bp)
    a = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=VANILLA, wiki_root=work,
               wiki_icons="off", vanilla_download=False, local_only=True,
               tool_root=work, bundle_root=work)
    r = Renderer(a, scale=4, layout="modern", background=None)
    print("本机重渲全部配方：")
    ok = 0
    for rec in recs:
        if getattr(rec, "kind", "unknown") == "unknown":
            continue
        try:
            r.render(rec)
            ok += 1
        except Exception:
            pass
    miss = sorted({str(w).split("for ", 1)[1] for w in r.warnings
                   if str(w).startswith("missing texture for ")})
    print(f"  渲染 {ok} 条，缺失 id {len(miss)} 个: {miss[:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
