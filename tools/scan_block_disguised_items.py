"""排查：哪些自定义物品是「用方块伪装实现动态纹理」的。

判据（从包数据直接推）：
  A. 在 BP 的 items/ 里声明为 minecraft:item          → 是"真物品"
  B. 不在 item_texture 里，但（短名）出现在 terrain_texture → 视觉来自方块侧
  C. 该 id 在 BP 的 blocks/ 下有几何/材质定义          → 走了方块那套渲染
  D. 它的贴图在 flipbook_textures.json 里登记（动态纹理）→ 正是"为了动态纹理"

输出每条的实际情况 + 当前渲染出来的图标来源，用于判断是否需要适配。
"""
import os
import sys
import json
import zipfile
import tempfile

sys.path.insert(0, r"D:\合成表生成器")
os.chdir(r"D:\合成表生成器")
from mcrender.assets import Assets
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


def jload(p, default):
    try:
        d = json.load(open(p, encoding="utf-8"))
        return d if isinstance(d, (dict, list)) else default
    except Exception:
        return default


# ---- BP 侧：物品定义 / 方块定义
bp_items, bp_blocks = {}, {}
for base, _d, fs in os.walk(bp):
    for f in fs:
        if not f.endswith(".json"):
            continue
        d = jload(os.path.join(base, f), {})
        if not isinstance(d, dict):
            continue
        for k, body in d.items():
            if not isinstance(body, dict):
                continue
            desc = body.get("description")
            if not isinstance(desc, dict):
                continue
            ident = desc.get("identifier")
            if not ident:
                continue
            if k.startswith("minecraft:item"):
                bp_items[ident] = body
            elif k.startswith("minecraft:block"):
                bp_blocks[ident] = body

# ---- RP 侧：表
def table(rel, key="texture_data"):
    d = jload(os.path.join(rp, rel), {})
    return d.get(key) or d.get("textures") or {} if isinstance(d, dict) else {}

item_t = table(os.path.join("textures", "item_texture.json"))
terr_t = table(os.path.join("textures", "terrain_texture.json"))
flip = jload(os.path.join("textures", "flipbook_textures.json"), [])
flip_set = set()
if isinstance(flip, list):
    for e in flip:
        if isinstance(e, dict) and e.get("flipbook_texture"):
            t = str(e["flipbook_texture"]).lower()
            flip_set.add(t if t.endswith(".png") else t + ".png")

print(f"BP 物品定义: {len(bp_items)}   BP 方块定义: {len(bp_blocks)}")
print(f"item_texture: {len(item_t)}   terrain: {len(terr_t)}   flipbook: {len(flip_set)}")
print()

a = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=os.path.join(MOB, "vanilla"),
           wiki_root=MOB, wiki_icons="never", wiki_language="zh",
           vanilla_download=False, local_only=True, tool_root=MOB, bundle_root=MOB)

rows = []
for ident in sorted(bp_items):
    ns, name = ident.split(":", 1)
    in_item = ident in item_t or name in item_t or f"{ns}.{name}" in item_t
    in_terr = name in terr_t or ident in terr_t
    in_blocks = ident in bp_blocks
    comps = bp_blocks.get(ident, {}).get("components")
    geom = comps.get("minecraft:geometry") if isinstance(comps, dict) else None
    if isinstance(geom, dict):
        geom = geom.get("identifier")
    ic = a.resolve(ident)
    rows.append(dict(ident=ident, item=in_item, terr=in_terr, blk=in_blocks,
                     geom=bool(geom), icon=ic.kind, note=ic.note or "",
                     size=getattr(getattr(ic, "item", None), "size", None)))

sus = [r for r in rows if (not r["item"]) and (r["terr"] or r["blk"] or r["geom"])]
print(f"=== 疑似「方块伪装」的物品：{len(sus)} / {len(rows)} ===")
print(f"{'id':30s} {'item':5s} {'terr':5s} {'blk':5s} {'geom':5s} {'渲染':7s} {'尺寸':9s} note")
for r in sus:
    print(f"  {r['ident']:28s} {'Y' if r['item'] else '-':5s} {'Y' if r['terr'] else '-':5s} "
          f"{'Y' if r['blk'] else '-':5s} {'Y' if r['geom'] else '-':5s} "
          f"{r['icon']:7s} {str(r['size']):9s} {r['note'][:24]}")

print()
print("=== 这些里的渲染结果统计 ===")
from collections import Counter
print("  ", dict(Counter(r["icon"] for r in sus)))
print("   正常物品图标(16x16):", sum(1 for r in sus if r["icon"] == "item" and r["size"] == (16, 16)))
print("   画成方块(model/block):", sum(1 for r in sus if r["icon"] in ("model", "block")))

# 贴图是否真的是动态纹理：看资产里有没有对应 png 且是长条
print()
print("=== 疑似者的贴图是否为长条（动态）===")
for r in sus[:12]:
    for cand in (f"textures/blocks/{r['ident'].split(':')[1]}.png",
                 f"textures/items/{r['ident'].split(':')[1]}.png"):
        p = a.find_file(cand)
        if p and os.path.isfile(p):
            try:
                im = Image.open(p)
                tag = "长条(动态)" if im.height > im.width else "方形"
                print(f"  {r['ident']:28s} {cand:44s} {im.size} {tag}")
            except Exception:
                pass
            break
