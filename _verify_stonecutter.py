"""复验：切石机 / 锻造台 能正常渲染（之前 100% 崩溃）。"""
import os
import sys
import zipfile
import tempfile

sys.path.insert(0, r"D:\合成表生成器")
os.chdir(r"D:\合成表生成器")
from mcrender.assets import Assets
from mcrender.recipes import collect
from mcrender.render import Renderer
from PIL import Image

MOB = r"D:\合成表生成器移动端\android-kivy"
ARC = r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip"
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
r = Renderer(a, scale=4, layout="modern")

stats = {}
succ = fail = 0
shots = []
for rec in collect(bp):
    k = getattr(rec, "kind", "?")
    stats[k] = stats.get(k, 0) + 1
    try:
        img, _ = r.render(rec)
        succ += 1
        shots.append((getattr(rec, "identifier", "?"), img.convert("RGBA"))) if k in ("stonecutter","smithing") or len(shots) < 6 else None
    except Exception as exc:
        fail += 1
        if fail <= 5:
            print("  ✗ 失败:", getattr(rec, "identifier", "?"), type(exc).__name__, exc)

print("配方种类统计:")
for k, v in sorted(stats.items()):
    print(f"   {k:12s} {v}")
print()
print("整包渲染成功:", succ, "失败:", fail, "张")
if shots:
    cw = max(i.width for _n, i in shots)
    ch = max(i.height for _n, i in shots)
    cols = min(3, len(shots))
    rows = (len(shots) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw + 10, rows * ch + 10), (245, 245, 248, 255))
    for n, (_i, im) in enumerate(shots):
        sheet.paste(im, ((n % cols) * cw + 5, (n // cols) * ch + 5), im)
    sheet.save(r"D:\合成表生成器\_stonecutter_smithing.png")
    print("对照图: _stonecutter_smithing.png", sheet.size)
