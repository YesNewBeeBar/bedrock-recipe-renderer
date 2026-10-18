"""复现三个问题：标题被截断 / oxidized_copper 误判 / 原版物品模糊。"""
import os
import sys
import json
import zipfile
import tempfile

sys.path.insert(0, r"D:\合成表生成器")
os.chdir(r"D:\合成表生成器")
from mcrender.assets import Assets
from mcrender.recipes import collect
from mcrender.render import Renderer
from PIL import Image

MOB = r"D:\合成表生成器移动端\android-kivy"
ARC = r"D:\wechat\xwechat_files\wxid_3k448ibotd0d22_40d3\msg\file\2026-10\磐石之旅v1.2.1(1.26.40+)(3).mcaddon"
if not os.path.isfile(ARC):
    for base, _d, fs in os.walk(r"D:\wechat"):
        for f in fs:
            if "磐石之旅" in f and f.endswith(".mcaddon"):
                ARC = os.path.join(base, f)
                break
print("包:", os.path.basename(ARC))

root = tempfile.mkdtemp()
with zipfile.ZipFile(ARC) as z:
    z.extractall(root)
for _ in range(3):
    found = False
    for base, _d, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith((".zip", ".mcpack")):
                sub = os.path.join(base, f) + "_x"
                if os.path.isdir(sub):
                    continue
                with zipfile.ZipFile(os.path.join(base, f)) as z:
                    z.extractall(sub)
                found = True
    if not found:
        break
bp = rp = None
for base, _d, fs in os.walk(root):
    if "manifest.json" not in fs:
        continue
    if os.path.isdir(os.path.join(base, "recipes")):
        bp = base
    if os.path.isdir(os.path.join(base, "textures")):
        rp = base

a = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=os.path.join(MOB, "vanilla"),
           wiki_root=MOB, wiki_icons="auto", wiki_language="zh",
           vanilla_download=False, local_only=True, tool_root=MOB, bundle_root=MOB)

print("\n=== ② oxidized_copper 解析 ===")
for t in ("minecraft:oxidized_copper", "minecraft:copper", "minecraft:oxidized_copper_door",
          "minecraft:polished_copper", "minecraft:diamond"):
    ic = a.resolve(t)
    size = getattr(getattr(ic, "item", None), "size", None)
    print(f"  {t:38s} kind={a.kind_of(t):6s} icon={ic.kind:6s} size={str(size):10s} note={ic.note or '-'}")
    print(f"      fuzzy='{a._fuzzy_item_key(t.split(':')[1])}'")

print("\n=== ① 标题渲染 ===")
r = Renderer(a, scale=4, layout="modern")
picked = {}
for rec in collect(bp):
    k = getattr(rec, "kind", "?")
    if k in ("shaped", "furnace") and k not in picked:
        picked[k] = rec
for k, rec in picked.items():
    try:
        img, lay = r.render(rec)
    except Exception as exc:
        print("  渲染失败", k, exc)
        continue
    title = lay.title
    ty = int(round(lay.title_pos[1] * 4))
    box = 8 * 4
    crop = img.crop((0, max(0, ty - 8), img.width, min(img.height, ty + box + 16)))
    crop.save(rf"D:\合成表生成器\_title_{k}.png")
    print(f"  {k}: title='{title}' title_pos={lay.title_pos} align={lay.title_align} "
          f"→ 截图 _title_{k}.png {crop.size}")

print("\n=== ③ 原版物品图标清晰度（看 size 与来源）===")
for t in ("minecraft:diamond", "minecraft:iron_ingot", "minecraft:netherite_ingot",
          "minecraft:emerald", "minecraft:enchanted_book", "minecraft:totem_of_undying"):
    ic = a.resolve(t)
    im = getattr(ic, "item", None)
    print(f"  {t:32s} icon={ic.kind:6s} size={str(getattr(im,'size',None)):10s} note={ic.note or '-'}")
