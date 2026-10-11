"""把桌面版（D:\\合成表生成器）的核心模块同步到 Android 工程里。

桌面版继续作为唯一实现；移动端只保留一份**只读副本**，避免两边逻辑漂移。
用法：
    python sync_core.py            # 同步并打印清单
    python sync_core.py --check    # 只校验是否一致（CI/提交前用）
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 默认用**本仓库**里的桌面核心（本目录就是仓库工作副本）；
# 若想从另一份桌面版同步，用环境变量覆盖：set BRR_DESKTOP=D:\合成表生成器
DESKTOP = os.environ.get("BRR_DESKTOP", HERE)
DEST = os.path.join(HERE, "android", "src", "bedrock_recipe_renderer")
KIVY = os.path.join(HERE, "android-kivy")

# 核心逻辑：移动端零改动复用（mcrender 包保持同名，相对导入才成立）
CORE_FILES = [
    "__init__.py", "__main__.py", "assets.py", "cli.py", "fonts.py", "geometry.py",
    "glyphs.json", "icon.py", "jsonc.py", "panel.py", "recipes.py", "render.py",
    "shapes.py", "sprites.json", "vanilla.py", "wiki.py",
]
# 内置资源：UI 贴图、裁剪面板、程序图标
ASSET_TREES = ["assets"]


def digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def plan() -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for name in CORE_FILES:
        items.append((os.path.join(DESKTOP, "mcrender", name),
                      os.path.join(DEST, "mcrender", name)))
    for tree in ASSET_TREES:
        src_root = os.path.join(DESKTOP, tree)
        for root, _dirs, files in os.walk(src_root):
            rel = os.path.relpath(root, src_root)
            for f in files:
                items.append((os.path.join(root, f),
                              os.path.join(DEST, tree, rel, f) if rel != "." else
                              os.path.join(DEST, tree, f)))
    # Briefcase 的应用图标必须叫 resources/icon.png
    items.append((os.path.join(DESKTOP, "assets", "icon.png"),
                  os.path.join(DEST, "resources", "icon.png")))

    # ---- Kivy/Buildozer 工程：核心 + 资源 + 平台层（paths/fonts/net 两端共用）----
    for name in CORE_FILES:
        items.append((os.path.join(DESKTOP, "mcrender", name),
                      os.path.join(KIVY, "mcrender", name)))
    for tree in ASSET_TREES:
        src_root = os.path.join(DESKTOP, tree)
        for root, _dirs, files in os.walk(src_root):
            rel = os.path.relpath(root, src_root)
            for f in files:
                items.append((os.path.join(root, f),
                              os.path.join(KIVY, tree, rel, f) if rel != "." else
                              os.path.join(KIVY, tree, f)))
    items.append((os.path.join(DESKTOP, "assets", "icon.png"),
                  os.path.join(KIVY, "icon.png")))
    for shared in ("fonts.py", "net.py"):   # paths/picking/storage 两端各写各的
        items.append((os.path.join(HERE, "android", "src", "bedrock_recipe_renderer",
                                   "platform", shared),
                      os.path.join(KIVY, "platform_layer", shared)))
    return items


def make_android_icons(icon_path: str, dest_root: str) -> list[str]:
    """按 Briefcase 要求的**文件名**生成 Android 图标（它只认 icon-<variant>-<size>.png）。"""
    from PIL import Image, ImageDraw

    if not os.path.isfile(icon_path):
        return []
    src = Image.open(icon_path).convert("RGBA")
    made = []
    specs = ([("round", n) for n in (48, 72, 96, 144, 192)]
             + [("square", n) for n in (48, 72, 96, 144, 192, 320, 480, 640, 960, 1280)]
             + [("adaptive", n) for n in (108, 162, 216, 324, 432)])
    for variant, size in specs:
        img = src.resize((size, size), Image.LANCZOS)
        if variant == "round":                       # 圆形裁剪
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
            img.putalpha(mask)
        elif variant == "adaptive":                  # 自适应图标留安全边距
            inner = int(size * 0.66)
            small = src.resize((inner, inner), Image.LANCZOS)
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            off = (size - inner) // 2
            img.paste(small, (off, off), small)
        path = os.path.join(dest_root, f"icon-{variant}-{size}.png")
        img.save(path)
        made.append(path)
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不写入")
    args = ap.parse_args()

    if not os.path.isdir(DESKTOP):
        print(f"找不到桌面版：{DESKTOP}（可用 BRR_DESKTOP 环境变量指定）")
        return 2

    items = plan()
    missing = [s for s, _ in items if not os.path.isfile(s)]
    if missing:
        print("桌面版缺文件：")
        for m in missing[:10]:
            print("   ", m)
        return 2

    same = differ = copied = 0
    for src, dst in items:
        if os.path.isfile(dst) and digest(src) == digest(dst):
            same += 1
            continue
        if args.check:
            differ += 1
            print("不一致:", os.path.relpath(dst, HERE))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied += 1

    if args.check:
        print(f"检查完成：一致 {same}，不一致 {differ}")
        return 1 if differ else 0
    icons = make_android_icons(os.path.join(DESKTOP, "assets", "icon.png"),
                               os.path.join(DEST, "resources"))
    print(f"同步完成：一致 {same}，更新 {copied} -> {DEST}")
    if icons:
        print(f"Android 图标已生成：{len(icons)} 个（round/square × 48/72/96/144/192）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
