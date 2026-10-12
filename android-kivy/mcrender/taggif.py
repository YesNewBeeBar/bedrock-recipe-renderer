"""同标签物品轮播 GIF（issue #1）。

配方里常写 ``{"tag": "minecraft:planks"}`` 这类"标签"当材料 —— 游戏里这些位置可以
放该标签下的任意物品。静态图只能画一个代表物品，这里额外生成一张**轮播 GIF**，
把标签下的成员依次画一遍。

桌面端（mcrender_gui.py）和移动端（android-kivy/main.py）都调用本模块，
保证两端行为一致。
"""
from __future__ import annotations

import os

from PIL import Image


def tags_in(recipe) -> list:
    """配方里用到的标签 id（形如 minecraft:planks）。"""
    found: list = []

    def walk(node) -> None:
        if isinstance(node, str):
            if node.startswith("tag:"):
                name = node[4:]
                if name not in found:
                    found.append(name)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for item in node.values():
                walk(item)

    for attr in ("grid", "result", "rows", "special", "pattern", "key"):
        if hasattr(recipe, attr):
            walk(getattr(recipe, attr))
    return found


def multi_tags(recipe, assets) -> list:
    """只保留"成员多于一个"的标签 —— 只有一个成员时轮播没有意义。"""
    out = []
    for tag in tags_in(recipe):
        if len(assets.members_for_tag(tag)) >= 2:
            out.append(tag)
    return out


def render_gif(renderer, recipe, target_png: str, max_frames: int = 16,
               duration: int = 600, log=None) -> str:
    """给 ``target_png`` 配一张同名 .gif；不需要时返回空串。"""
    assets = renderer.assets
    tags = multi_tags(recipe, assets)
    if not tags:
        return ""

    def say(text: str) -> None:
        if log:
            try:
                log(text)
            except Exception:
                pass

    saved = {t: assets.tag_items.get(t) for t in tags}
    frames = []
    count = min(max_frames, max(len(assets.members_for_tag(t)) for t in tags))
    try:
        for i in range(count):
            for t in tags:
                members = assets.members_for_tag(t)
                assets.tag_items[t] = members[i % len(members)]
            img, _lay = renderer.render(recipe)
            frames.append(img.convert("RGBA"))
            if hasattr(renderer, "warnings"):
                renderer.warnings.clear()   # 轮播每帧都会重报"标签画成了X"，别刷屏
    except Exception as exc:
        say(f"   ! GIF 生成失败：{exc}")
        frames = []
    finally:
        for t in tags:                       # 还原，别影响后面的配方
            if saved[t] is None:
                assets.tag_items.pop(t, None)
            else:
                assets.tag_items[t] = saved[t]

    if len(frames) < 2:
        return ""
    gif = os.path.splitext(target_png)[0] + ".gif"
    try:
        palette = [f.convert("P", palette=Image.ADAPTIVE) for f in frames]
        palette[0].save(gif, save_all=True, append_images=palette[1:],
                        duration=duration, loop=0, disposal=2, optimize=True)
    except Exception as exc:
        say(f"   ! GIF 保存失败：{exc}")
        return ""
    say(f"   ↻ 同标签轮播 {count} 帧 → {os.path.basename(gif)}")
    return gif
