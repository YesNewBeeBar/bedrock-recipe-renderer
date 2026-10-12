"""记住用户的选择：出图目录、BP/RP、原版包等，重启后自动复用，不用反复选。

存到 App 私有目录下的 remember.json（纯文本，方便用户自查/删除）。
目录类选择同时由 androidfs.pick_tree 申请了**可持久化**的 SAF 权限
（takePersistableUriPermission），所以重启后这些目录依然可读写。
"""
from __future__ import annotations

import io
import json
import os

from . import paths

#: 需要记住的键（值都是路径或 tree URI 字符串）
KEYS = ("out", "bp", "rp", "vanilla", "files", "scale", "layout", "offline",
        "out_tree", "bp_tree", "rp_tree")


def _file() -> str:
    return os.path.join(paths.tool_root(), "remember.json")


def load() -> dict:
    try:
        with io.open(_file(), encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in KEYS and v}


def save(state: dict) -> None:
    try:
        data = {k: state.get(k) for k in KEYS if state.get(k)}
        with io.open(_file(), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
    except Exception:
        pass


def merge_into(state: dict) -> list:
    """把记住的选择填进 state，返回被恢复的键名（供界面提示）。"""
    saved = load()
    used = []
    for key, value in saved.items():
        if not state.get(key):
            state[key] = value
            used.append(key)
    return used
