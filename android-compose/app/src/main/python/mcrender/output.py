"""输出目录规则（桌面端 / 移动端 / CLI 共用，保证三处结构一致）。

约定：``<用户选的输出目录>/合成表/<附加包名>/<配方相对路径>.png``
—— 不同附加包的同名配方不会互相覆盖。
"""
from __future__ import annotations

import os

# Windows 文件名不允许的字符
_BAD = '<>:"/\\|?*'
SUB_DIR = "合成表"


def safe_folder_name(name: str) -> str:
    """把附加包文件名 / 文件夹名变成安全的文件夹名。"""
    text = "".join(("_" if c in _BAD or ord(c) < 32 else c) for c in str(name))
    text = text.strip(" .")
    return text or SUB_DIR


def pack_folder_name(source: str) -> str:
    """从压缩包路径 / 文件夹路径得出"附加包名"。

    压缩包：去掉扩展名（.mcaddon / .zip / .mcpack …）
    文件夹：用目录名；若指向包内的 recipes/ 之类的子目录，就用它的上一级
    """
    path = os.path.normpath(str(source))
    base = os.path.basename(path)
    parent = os.path.basename(os.path.dirname(path))
    # 指向包内子目录时（<包>/recipes 这种），取上一级 —— 不管这个路径是否真实存在
    if base.lower() in ("recipes", "items", "texts", "scripts",
                        "loot_tables", "entities", "blocks") and parent:
        return safe_folder_name(parent)
    if os.path.isdir(path):
        return safe_folder_name(base)
    return safe_folder_name(os.path.splitext(base)[0])


def output_dir_for(root: str, pack: str = "") -> str:
    """在输出根下再建一层「合成表/附加包名」。"""
    out = root
    if os.path.basename(os.path.normpath(out)) != SUB_DIR:
        out = os.path.join(out, SUB_DIR)
    if pack:
        out = os.path.join(out, safe_folder_name(pack))
    os.makedirs(out, exist_ok=True)
    return out
