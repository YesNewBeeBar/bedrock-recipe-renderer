"""用用户截图里的那两条配方原样出图，直接对比。"""
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
ARC = None
for base, _d, fs in os.walk(r"D:\wechat"):
    for f in fs:
        if "磐石之旅" in f and f.endswith(".mcaddon"):
            ARC = os.path.join(base, f)
print("包:", os.path.basename(ARC or "?"))
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

WANT = ("inlaid_essence_bead_bleeding", "inlaid_essence_bead_sunder", "wither_rose")
for rec in collect(bp):
    ident = getattr(rec, "identifier", "") or ""
    if not any(w in ident for w in WANT):
        continue
    img, lay = r.render(rec)
    name = ident.split(":")[-1]
    out = rf"D:\合成表生成器\_cmp_{name}.png"
    img.save(out)
    print(f"  {ident:44s} kind={rec.kind:10s} title='{lay.title}' pos={lay.title_pos} "
          f"align={lay.title_align} size={img.size} -> {os.path.basename(out)}")
