"""Kivy/Android 目录：全部落在 App 私有目录，免权限。

Android（python-for-android）：
    ANDROID_PRIVATE   /data/data/<pkg>/files（应用私有，随卸载清除）
    外部私有目录      /sdcard/Android/data/<pkg>/files（文件管理器可见，见 storage.py）
开发时（桌面直接跑 main.py）：落到 ./.devdata/
"""
from __future__ import annotations

import os


def _private() -> str:
    root = (os.environ.get("ANDROID_PRIVATE")
            or os.environ.get("ANDROID_APP_PATH")
            or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".devdata"))
    os.makedirs(root, exist_ok=True)
    return root


def data_dir() -> str:
    p = os.path.join(_private(), "data"); os.makedirs(p, exist_ok=True); return p


def cache_dir() -> str:
    p = os.path.join(_private(), "cache"); os.makedirs(p, exist_ok=True); return p


def exports_dir() -> str:
    p = os.path.join(data_dir(), "exports"); os.makedirs(p, exist_ok=True); return p


def work_dir() -> str:
    p = os.path.join(cache_dir(), "work"); os.makedirs(p, exist_ok=True); return p


def default_output_dir() -> str:
    p = os.path.join(exports_dir(), "out"); os.makedirs(p, exist_ok=True); return p


def tool_root() -> str:
    """核心的 tool_root 参数：vanilla_cache / wiki_cache 落在这里。"""
    return cache_dir()


def bundled_assets() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def describe() -> str:
    return f"data={data_dir()} cache={cache_dir()} exports={exports_dir()}"
