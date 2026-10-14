"""验证 issue #10 修复：报告里的 id 应为 item，真方块仍应为 block。"""
import os
import sys
import json
import tempfile

sys.path.insert(0, r"D:\合成表生成器")
sys.path.insert(0, r"D:\合成表生成器移动端\android-kivy")
import mcrender, os as _os
print("实际加载的核心:", _os.path.dirname(mcrender.__file__))
from mcrender.assets import Assets
from platform_layer import picking

ARC = r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip"
MOB = r"D:\合成表生成器移动端\android-kivy"
root = picking.unpack_archive(ARC, tempfile.mkdtemp())
bp = rp = None
for base, _d, fs in os.walk(root):
    if "manifest.json" not in fs:
        continue
    if os.path.isdir(os.path.join(base, "recipes")):
        bp = base
    if os.path.isdir(os.path.join(base, "textures")):
        rp = base

a = Assets(bp_dir=bp, rp_dir=rp, vanilla_dir=os.path.join(MOB, "vanilla"),
           wiki_root=MOB, wiki_icons="auto", wiki_language="en",
           vanilla_download=False, local_only=True, tool_root=MOB, bundle_root=MOB)

CASES = [
    # (id, 期望)
    ("xyby:dragon_fireball", "item"),
    ("xyby:small_fire_ball", "item"),
    ("xyby:fire_ball", "item"),
    ("xyby:tnt_ball", "item"),
    ("xyby:cactus_ball", "item"),
    ("xyby:honey_block", "item"),      # 包内自定义物品，撞名原版方块
    ("xyby:big_spider_web_ball", "item"),
    ("xyby:andesite_ball", "item"),
    ("xyby:beacon_ball", "item"),
    ("xyby:bedrock_ball", "item"),
    # 真方块不能被改坏
    ("minecraft:stone", "block"),
    ("minecraft:honey_block", "block"),
    ("minecraft:web", "block"),
    ("minecraft:crafting_table", "block"),
    ("minecraft:cobweb", "item"),      # 原版 id 是 item
]

ok = bad = 0
print(f"{'id':30s} {'期望':6s} {'实际':6s} 结果")
for ident, want in CASES:
    got = a.kind_of(ident)
    good = got == want
    ok += good
    bad += (not good)
    print(f"  {ident:28s} {want:6s} {got:6s} {'OK' if good else '✗ 不符'}")

print()
print(f"通过 {ok} / {ok + bad}")
sys.exit(1 if bad else 0)
