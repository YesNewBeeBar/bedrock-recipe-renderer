#!/usr/bin/env python
"""预下所有「走 wiki 图标」的物品图，供打进 APK。

背景：头颅/头、床、旗帜、告示牌、潜影盒、花盆、植物、药水、失水恶魂等，
桌面端是从 **wiki 图标缓存** 取图的（与游戏库存图标一致）；
移动端离线且无缓存时会退回"内置几何体"，画出来与游戏不符 —— 就是这个 bug。

这里把核心会走 wiki 的 id 全部抓下来，放进 android-kivy/wiki_cache/。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))

from mcrender import assets as A          # noqa: E402
from mcrender import wiki                 # noqa: E402

OUT = os.path.join(HERE, "android-kivy", "wiki_cache")

COLOURS = ("white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
           "gray", "light_gray", "cyan", "purple", "blue", "brown", "green",
           "red", "black")
SUFFIXES = ("bed", "banner", "sign", "hanging_sign", "shulker_box", "candle",
            "carpet", "concrete", "concrete_powder", "terracotta", "wool",
            "stained_glass", "stained_glass_pane", "glazed_terracotta")


def wanted_ids() -> list:
    ids = set()
    # 头颅 / 头（含变体数据值映射到的名字）
    ids |= set(A.SKULL_BY_NAME)
    for _data, name in (A.DATA_VARIANTS.get("skull") or {}).items():
        ids.add(name)
    ids |= set(A.WIKI_SPECIAL)
    ids |= set(A.WIKI_PLANTS)
    for name in A.POTION_BOTTLES:
        ids.add(name)
    ids.add("dried_ghast")
    ids.add("skull")
    ids.add("head")
    # 带颜色前缀的床/旗帜/告示牌/潜影盒…（这些都是 _is_wiki_block 命中的）
    for colour in COLOURS:
        for suffix in SUFFIXES:
            ids.add(f"{colour}_{suffix}")
    ids |= {"bed", "banner", "sign", "hanging_sign", "shulker_box",
            "undyed_shulker_box", "flower_pot", "decorated_pot", "shelf",
            "crafter", "chiseled_bookshelf", "campfire", "soul_campfire"}
    return sorted(i for i in ids if i)


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    ids = wanted_ids()
    print(f"目标 id {len(ids)} 个 → 缓存目录 {OUT}", flush=True)
    ok = miss = 0
    t0 = time.time()
    for i, name in enumerate(ids, 1):
        ident = name if ":" in name else f"minecraft:{name}"
        try:
            img = wiki.fetch_icon(ident, OUT, "en", offline=False)
        except Exception as exc:
            img = None
            if i <= 5:
                print("   异常", ident, exc, flush=True)
        if img is not None:
            ok += 1
        else:
            miss += 1
        if i % 50 == 0:
            print(f"  {i}/{len(ids)} 成功 {ok} 缺 {miss} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    n = sum(len(f) for _b, _d, f in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(b, f))
               for b, _d, fs in os.walk(OUT) for f in fs)
    print(f"完成：成功 {ok}，未取到 {miss}；缓存 {n} 个文件 {size/1048576:.1f} MB",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
