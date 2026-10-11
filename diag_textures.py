#!/usr/bin/env python
"""诊断：磐石之旅包里，哪些物品纹理解析不到，而包里其实有对应文件。

思路（数据优先）：
1. 解包 → 找 BP / RP
2. 渲染 armors 那批配方，收集 missing texture 的 id
3. 对每个失败的 id，把包里所有"看起来相关"的文件找出来：
   - RP/textures/items/*.png 里名字接近的
   - RP/textures/item_texture.json 里的键
   - BP/items/*.json 里定义该物品的文件，看它的 icon / texture 指向什么
   - RP/attachables/*.json（盔甲通常走这里）
"""
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))

from mcrender.assets import Assets          # noqa: E402
from mcrender.recipes import collect        # noqa: E402
from mcrender.render import Renderer        # noqa: E402
from platform_layer import picking          # noqa: E402

MCADDON = (r"D:\wechat\xwechat_files\wxid_3k448ibotd0d22_40d3\msg\file"
           r"\2026-10\磐石之旅v1.2.1(1.26.40+)(2).mcaddon")
VANILLA = os.path.join(HERE, "android-kivy", "vanilla")


def find_packs(root):
    bps, rps = [], []
    for base, _d, files in os.walk(root):
        if "manifest.json" not in files:
            continue
        has_bp = any(os.path.isdir(os.path.join(base, d)) for d in
                     ("recipes", "entities", "loot_tables", "scripts", "items"))
        has_rp = os.path.isdir(os.path.join(base, "textures"))
        if has_bp:
            bps.append(base)
        if has_rp:
            rps.append(base)
    return bps, rps


def main() -> int:
    work = tempfile.mkdtemp()
    root = picking.unpack_archive(MCADDON, work)
    bps, rps = find_packs(root)
    print("BP:", [os.path.relpath(b, root) for b in bps])
    print("RP:", [os.path.relpath(r, root) for r in rps])
    if not bps or not rps:
        print("!! 没找到 BP/RP")
        return 1

    bp, rp = bps[0], rps[0]
    recs = collect(bp)
    print("配方总数:", len(recs))

    assets = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=VANILLA, wiki_root=work,
                    wiki_icons="off", vanilla_download=False, local_only=True,
                    tool_root=work, bundle_root=work)
    rend = Renderer(assets, scale=4, layout="modern", background=None)
    out = os.path.join(work, "out")
    os.makedirs(out, exist_ok=True)

    ok = 0
    for rec in recs:
        if getattr(rec, "kind", "unknown") == "unknown":
            continue
        try:
            rend.render(rec)
            ok += 1
        except Exception as exc:
            print("  渲染异常:", os.path.basename(rec.path), exc)
    miss = []
    for w in rend.warnings:
        s = str(w)
        if s.startswith("missing texture for "):
            ident = s.split("missing texture for ", 1)[1].strip()
            if ident not in miss:
                miss.append(ident)
    print(f"渲染 {ok} 条，缺失纹理 {len(miss)} 个不同 id")
    for m in miss:
        print("   -", m)

    # 对失败 id 找线索
    items_dir = os.path.join(rp, "textures", "items")
    have_items = sorted(os.listdir(items_dir)) if os.path.isdir(items_dir) else []
    itj = {}
    p = os.path.join(rp, "textures", "item_texture.json")
    if os.path.isfile(p):
        try:
            itj = (json.load(io.open(p, encoding="utf-8")).get("texture_data") or {})
        except Exception as exc:
            print("  item_texture.json 读取失败:", exc)
    print(f"RP textures/items 下 {len(have_items)} 个文件；item_texture 键 {len(itj)} 个")

    print("\n=== 逐 id 追查 ===")
    for m in miss[:12]:
        short = m.split(":", 1)[-1]
        print(f"\n[{m}]")
        cand = [f for f in have_items if short in f or short.replace("_", "") in f.replace("_", "")]
        print("  RP/textures/items 名称相近:", cand[:5] or "（无）")
        keys = [k for k in itj if short in k]
        print("  item_texture.json 键相近:", keys[:5] or "（无）")
        if keys:
            print("     其定义:", json.dumps(itj[keys[0]], ensure_ascii=False)[:160])
        # BP 里该物品的定义
        found = []
        for base, _d, files in os.walk(bp):
            for f in files:
                if f.endswith(".json") and short in f:
                    found.append(os.path.join(base, f))
        for fp in found[:2]:
            try:
                data = json.load(io.open(fp, encoding="utf-8"))
                item = (data.get("minecraft:item") or {})
                comp = item.get("components") or {}
                icon = comp.get("minecraft:icon")
                print(f"  BP 定义 {os.path.relpath(fp, bp)}: icon={json.dumps(icon, ensure_ascii=False)[:120]}")
            except Exception as exc:
                print("    读取失败:", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
