#!/usr/bin/env python
"""预下所有「走 wiki 图标」的物品图（含方块类物品），供打进 APK / 桌面端缓存。

背景：头颅/头、床、旗帜、告示牌、潜影盒、花盆、植物、药水、失水恶魂，
以及**信标、铜块这类没有物品图标的方块**，桌面端是从 wiki 图标缓存取图的
（与游戏库存图标一致）；移动端离线且无缓存时会退回"内置几何体/方块模型"，
画出来与游戏不符。

范围：
  1) 核心会走 wiki 的具名清单（头颅、床、旗帜、植物、药水…）
  2) item_texture.json 的全部键（504 个）
  3) blocks.json 的全部键（方块类物品，信标/铜块等）

先清掉上一次因为**网络抖动**写下的 .none 标记（那只代表"没连上"，不代表没有）。
"""
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))

from mcrender import assets as A          # noqa: E402
from mcrender import jsonc                # noqa: E402
from mcrender import wiki                 # noqa: E402

VANILLA = os.path.join(HERE, "android-kivy", "vanilla")
OUT = os.path.join(HERE, "android-kivy", "wiki_cache")

COLOURS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
           "red", "black")
SUFFIXES = ("bed", "banner", "sign", "hanging_sign", "shulker_box", "candle",
            "carpet", "concrete", "concrete_powder", "terracotta", "wool",
            "stained_glass", "stained_glass_pane", "glazed_terracotta")


def wanted() -> list:
    ids = set(A.SKULL_BY_NAME) | set(A.WIKI_SPECIAL) | set(A.WIKI_PLANTS)
    ids |= set(A.POTION_BOTTLES)
    for _d, nm in (A.DATA_VARIANTS.get("skull") or {}).items():
        ids.add(nm)
    ids |= {"dried_ghast", "skull", "head", "bed", "banner", "sign",
            "hanging_sign", "shulker_box", "undyed_shulker_box", "flower_pot",
            "decorated_pot", "shelf", "crafter", "chiseled_bookshelf",
            "campfire", "soul_campfire"}
    for c in COLOURS:
        for s in SUFFIXES:
            ids.add(f"{c}_{s}")
    for rel in ("textures/item_texture.json", "blocks.json"):
        path = os.path.join(VANILLA, *rel.split("/"))
        data = jsonc.load(path) if os.path.isfile(path) else None
        if isinstance(data, dict):
            if "texture_data" in data:
                ids |= set(data["texture_data"])
            else:
                ids |= {k for k in data if k != "format_version"}
    return sorted(i for i in ids if i)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)

    # 1) 清掉上一次网络抖动留下的 .none（保留真正的 404 由本次重新判定）
    removed = 0
    for f in os.listdir(OUT):
        if f.endswith(".none"):
            os.remove(os.path.join(OUT, f))
            removed += 1
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            base = f[:-4]
            nf = os.path.join(OUT, base + ".none")
            if os.path.exists(nf):
                os.remove(nf)
    print(f"已清掉 {removed} 个 .none 标记，重新判定", flush=True)

    targets = wanted()
    print(f"目标 {len(targets)} 个 id", flush=True)
    ok = miss = 0
    t0 = time.time()
    for i, name in enumerate(targets, 1):
        ident = name if ":" in name else f"minecraft:{name}"
        try:
            img = wiki.fetch_icon(ident, OUT, "en", offline=False)
        except Exception:
            img = None
        if img is not None:
            ok += 1
            # 体积闸门：图标只有几 KB，几十 KB 以上的都是维基的页面截图
            for f in os.listdir(OUT):
                if f.startswith(f"minecraft__{name}.") and f.endswith(".png"):
                    fp = os.path.join(OUT, f)
                    if os.path.getsize(fp) > 64 * 1024:
                        os.remove(fp)
                        ok -= 1
                        miss += 1
        else:
            miss += 1
        time.sleep(0.4)                 # 限速：别把维基打到限流
        if wiki._OFFLINE["yes"]:        # 触发了熔断就歇一会儿再继续
            wiki._OFFLINE["yes"] = False
            wiki._STREAK["n"] = 0
            print(f"  （第 {i} 个触发熔断，休息 20 秒后继续）", flush=True)
            time.sleep(20)
        if i % 50 == 0:
            print(f"  {i}/{len(targets)} 成功 {ok} 缺 {miss} ({time.time()-t0:.0f}s)",
                  flush=True)
    png = sum(1 for f in os.listdir(OUT) if f.endswith(".png"))
    print(f"完成：成功 {ok}，未取到 {miss}；缓存 png {png} 个", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
