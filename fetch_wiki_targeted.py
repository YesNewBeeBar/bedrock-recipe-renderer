#!/usr/bin/env python
"""精准补充 wiki 图标：只抓「整合包实际用到的物品」+「常用方块类物品」。

大批量抓 1900 个会被维基限流，效率极低；改成按需抓取 + 常用清单，几十秒即可。
"""
import io
import os
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))
from mcrender import jsonc          # noqa: E402
from mcrender import wiki           # noqa: E402

ROOT = os.path.join(HERE, "android-kivy")   # 核心会在其下自建 wiki_cache
OUT = ROOT
PACKS = [
    r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip",
    r"C:\Users\NewBee_Bar\Downloads\3.1.0-alpha.1(26.30+).mcaddon",
    r"C:\Users\NewBee_Bar\Downloads\[苦力怕论坛]natural_journey_0.1.5.zip",
]
COMMON_BLOCKS = [
    "beacon", "copper_block", "redstone_block", "lapis_block", "diamond_block",
    "emerald_block", "netherite_block", "gold_block", "iron_block", "coal_block",
    "quartz_block", "redstone_lamp", "sea_lantern", "glowstone", "shroomlight",
    "obsidian", "crying_obsidian", "ancient_debris", "netherite_scrap",
    "crafting_table", "furnace", "blast_furnace", "smoker", "stonecutter",
    "smithing_table", "brewing_stand", "cauldron", "anvil", "enchanting_table",
    "bookshelf", "chest", "trapped_chest", "ender_chest", "barrel", "hopper",
    "dropper", "dispenser", "observer", "piston", "sticky_piston", "target",
    "note_block", "jukebox", "lodestone", "respawn_anchor", "conduit",
    "sponge", "hay_block", "bone_block", "slime_block", "honey_block",
    "dried_kelp_block", "bamboo_block", "sculk", "sculk_catalyst", "amethyst_block",
    "budding_amethyst", "tuff", "calcite", "dripstone_block", "mud", "clay",
    "snow_block", "ice", "packed_ice", "blue_ice", "magma", "soul_sand",
    "soul_soil", "basalt", "blackstone", "end_stone", "purpur_block",
    "prismarine", "dark_prismarine", "sea_pickle", "melon", "pumpkin",
    "carved_pumpkin", "jack_o_lantern", "cake", "beehive", "bee_nest",
    "composter", "lectern", "loom", "cartography_table", "fletching_table",
    "grindstone", "bell", "campfire", "soul_campfire", "lantern", "soul_lantern",
    "chain", "iron_bars", "ladder", "scaffolding", "lightning_rod",
    "daylight_detector", "tripwire_hook", "lever", "button", "pressure_plate",
]


def ids_from_packs() -> set:
    out = set()
    for arc in PACKS:
        if not os.path.isfile(arc):
            continue
        d = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(arc) as z:
                names = [n for n in z.namelist()
                         if "/recipes/" in n and n.endswith(".json")]
                for n in names:
                    try:
                        data = jsonc.loads(z.read(n).decode("utf-8", "replace"))
                    except Exception:
                        continue
                    text = io.StringIO()
                    import json
                    json.dump(data, text)
                    blob = text.getvalue()
                    import re
                    for m in re.finditer(r'"([a-z0-9_]+:[a-z0-9_/]+)"', blob):
                        out.add(m.group(1))
        except Exception as exc:
            print("  跳过", os.path.basename(arc), exc)
    return out


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    targets = {f"minecraft:{b}" for b in COMMON_BLOCKS} | ids_from_packs()
    targets = sorted(t for t in targets if t.startswith("minecraft:"))
    print(f"目标 {len(targets)} 个 id", flush=True)
    ok = miss = 0
    t0 = time.time()
    for i, ident in enumerate(targets, 1):
        try:
            img = wiki.fetch_icon(ident, OUT, "en", offline=False)
        except Exception:
            img = None
        if img is not None:
            ok += 1
        else:
            miss += 1
        time.sleep(0.25)
        if wiki._OFFLINE["yes"]:
            wiki._OFFLINE["yes"] = False
            wiki._STREAK["n"] = 0
            time.sleep(5)
        if i % 25 == 0:
            print(f"  {i}/{len(targets)} 成功 {ok} 缺 {miss} ({time.time()-t0:.0f}s)",
                  flush=True)
    png = sum(1 for f in os.listdir(OUT) if f.endswith(".png"))
    print(f"完成：本次成功 {ok}，未取到 {miss}；缓存 png 共 {png} 个", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
