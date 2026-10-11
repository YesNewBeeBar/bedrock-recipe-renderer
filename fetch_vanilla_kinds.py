#!/usr/bin/env python
"""下载原版行为包里的**物品/方块定义**，用来准确区分 item 与 block。

用户给的规则：
    带 "minecraft:item"  的是**物品**（画物品图标，绝不画立方体）
    带 "minecraft:block" 的是**方块**（画立方体）

这些东西在 vanilla 的 behavior_pack/{items,blocks}/*.json 里，
下载后生成一张 id -> "item"|"block" 的映射表，供渲染与打包使用。
"""
import concurrent.futures
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "android-kivy", "vanilla_kinds.json")
RAW = "https://raw.githubusercontent.com/Mojang/bedrock-samples/main/behavior_pack/"
UA = {"User-Agent": "Mozilla/5.0"}
API = ("https://api.github.com/repos/Mojang/bedrock-samples/git/trees/main"
       "?recursive=1")


def list_paths() -> list:
    with urllib.request.urlopen(urllib.request.Request(API, headers=UA),
                                timeout=60) as r:
        tree = json.load(r)
    out = []
    for node in tree.get("tree", []):
        path = node.get("path", "")
        if path.startswith("behavior_pack/") and path.endswith(".json") and \
                ("/items/" in path or "/blocks/" in path):
            out.append(path)
    return out


def fetch(path: str):
    url = f"https://raw.githubusercontent.com/Mojang/bedrock-samples/main/{path}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=40) as r:
            data = json.loads(r.read().decode("utf-8-sig", "replace"))
    except Exception:
        return []
    kind = "item" if "/items/" in path else "block"
    out = []
    for key, body in (data or {}).items():
        if not isinstance(body, dict):
            continue
        if kind == "item" and not key.startswith("minecraft:item"):
            continue
        if kind == "block" and not key.startswith("minecraft:block"):
            continue
        ident = (body.get("description") or {}).get("identifier")
        if ident:
            out.append((ident, kind))
    return out


def main() -> int:
    paths = list_paths()
    print(f"行为包定义文件 {len(paths)} 个", flush=True)
    mapping = {}
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for pairs in pool.map(fetch, paths):
            for ident, kind in pairs:
                mapping[ident] = kind
            done += 1
            if done % 100 == 0:
                print(f"  已处理 {done}/{len(paths)}，累计 {len(mapping)} 条",
                      flush=True)
    mapping["minecraft:heavy_core"] = "item"        # 用户指出：它是物品
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(mapping, io.open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0, sort_keys=True)
    items = sum(1 for v in mapping.values() if v == "item")
    print(f"完成：{len(mapping)} 条（物品 {items}，方块 {len(mapping)-items}）→ {OUT}",
          flush=True)
    for probe in ("minecraft:beacon", "minecraft:cactus", "minecraft:tnt",
                  "minecraft:heavy_core", "minecraft:mace", "minecraft:shield",
                  "minecraft:sulfur", "minecraft:honey_block"):
        print(f"  {probe:26s} → {mapping.get(probe, '（未收录）')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
