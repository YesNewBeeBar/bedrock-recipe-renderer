#!/usr/bin/env python
"""整包渲染并与用户提供的对照图逐像素比较，输出差异排行。"""
import os
import sys
import tempfile
import zipfile

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcrender.assets import Assets           # noqa: E402
from mcrender.recipes import collect         # noqa: E402
from mcrender.render import Renderer         # noqa: E402

ARC = r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip"
REF = r"C:\Users\NewBee_Bar\Pictures\合成表\crafting"
VAN = r"D:\合成表生成器移动端\android-kivy\vanilla"


def main() -> int:
    work = tempfile.mkdtemp()
    with zipfile.ZipFile(ARC) as z:
        z.extractall(work)
    bp = rp = None
    for base, _d, fs in os.walk(work):
        if "manifest.json" not in fs:
            continue
        if os.path.isdir(os.path.join(base, "recipes")):
            bp = base
        if os.path.isdir(os.path.join(base, "textures")):
            rp = base

    a = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=VAN,
               wiki_root=os.path.join(HERE, "wiki_cache"), wiki_icons="auto",
               wiki_language="en", vanilla_download=False, local_only=False,
               tool_root=HERE, bundle_root=HERE)
    print("item_texture 键:", len(a.item_texture), "| vanilla 存在:", os.path.isdir(VAN))
    r = Renderer(a, scale=4, layout="modern", background=None)

    same = diff = miss = 0
    worst = []
    for rec in collect(bp):
        if getattr(rec, "kind", "unknown") == "unknown":
            continue
        name = os.path.splitext(os.path.basename(rec.path))[0]
        ref = os.path.join(REF, name + ".png")
        try:
            img, _ = r.render(rec)
        except Exception as exc:
            print("  渲染异常", name, exc)
            continue
        if not os.path.isfile(ref):
            miss += 1
            continue
        b = Image.open(ref).convert("RGB")
        if img.size != b.size:
            diff += 1
            worst.append((10 ** 9, name))
            continue
        d = sum(1 for x, y in zip(img.convert("RGB").getdata(), b.getdata()) if x != y)
        if d == 0:
            same += 1
        else:
            diff += 1
            worst.append((d, name))
    print(f"与对照：完全一致 {same}，有差异 {diff}，对照里没有 {miss}")
    worst.sort(reverse=True)
    for d, n in worst[:10]:
        print(f"   {n}: {d} 像素")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
