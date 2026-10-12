#!/usr/bin/env python
"""把维基 Module:GameTag/RelOriBE 的 Lua 数据转成 JSON 标签库。

来源：https://zh.minecraft.wiki/index.php?title=Module:GameTag/RelOriBE&action=raw
（基岩版全部标签 → 成员物品/方块，就是"基岩版标签/物品"与"/方块"两个页面的数据源）

输出 android-kivy/tags_be.json：
    { "minecraft:planks": ["minecraft:acacia_planks", ...], ... }
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "android-kivy", "tags_be.json")
WANT = ("items", "blocks")


def parse_lua(text: str) -> dict:
    """极简解析：只认 ['名字'] = { ... } 与 '名字', 这两种结构。"""
    out: dict = {}
    section = tag = None
    tokens = re.finditer(r"\['([^']+)'\]\s*=\s*\{|\}|\s*'([^']+)'\s*,", text)
    depth = 0
    for m in tokens:
        if m.group(1) is not None:              # ['x'] = {
            name = m.group(1)
            if depth == 0:
                section = name if name in WANT else None
                depth = 1
            else:
                if section:
                    tag = name
                    out.setdefault(f"minecraft:{tag}" if section == "items"
                                   else f"minecraft:{tag}", []).__class__
                    out.setdefault(section_tag(section, tag), [])
                depth += 1
        elif m.group(0).strip() == "}":
            if depth == 1:
                section, tag = None, None
            depth = max(0, depth - 1)
        elif m.group(2) is not None and section and depth == 2 and tag:
            out[section_tag(section, tag)].append(
                m.group(2) if ":" in m.group(2) else f"minecraft:{m.group(2)}")
    return out


def section_tag(section: str, tag: str) -> str:
    return f"minecraft:{tag}"


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    if not src or not os.path.isfile(src):
        print("用法: python build_tag_db.py <Module_GameTag_RelOriBE 原文文件>")
        return 1
    text = io.open(src, encoding="utf-8", errors="replace").read()
    data = parse_lua(text)
    data = {k: sorted(set(v)) for k, v in data.items() if v}
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(data, ensure_ascii=False, indent=0, sort_keys=True))
    print(f"标签 {len(data)} 个，成员总数 {sum(len(v) for v in data.values())} → {OUT}")
    for probe in ("minecraft:planks", "minecraft:logs", "minecraft:wool",
                  "minecraft:stone_crafting_materials", "minecraft:is_food",
                  "minecraft:is_pickaxe", "minecraft:spawn_egg"):
        v = data.get(probe, [])
        print(f"  {probe:36s} {len(v):3d} 个 {v[:3]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
