"""目录解析：一套代码同时适配 Android 与桌面。

Android（Briefcase 打包后）：
    私有数据   /data/data/<pkg>/files/…（app.paths.data）
    缓存       app.paths.cache（可被系统清理，存放 vanilla_cache / wiki_cache）
    导出       app.paths.data/exports（免权限可写；再通过「分享」交给系统）

桌面（开发时直接跑）：
    全部落在工作目录下的 .devdata/ 里，互不干扰
"""
from __future__ import annotations

import os
import sys

IS_ANDROID = hasattr(sys, "getandroidapilevel") or "ANDROID_ARGUMENT" in os.environ

_dev_root: str | None = None


def set_dev_root(path: str) -> None:
    """开发/测试时指定根目录（打包后不需要调用）。"""
    global _dev_root
    _dev_root = path


def _paths():
    """拿到 Briefcase 的 app.paths；开发环境返回 None。"""
    try:
        from bedrock_recipe_renderer.app import main_app  # type: ignore  # noqa: F401
    except Exception:
        pass
    try:
        import __main__  # 打包后 Briefcase 会把 app 对象挂在 __main__ 上
        app = getattr(__main__, "app", None)
        return getattr(app, "paths", None)
    except Exception:
        return None


def _fallback(name: str) -> str:
    root = _dev_root or os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), ".devdata")
    path = os.path.join(root, name)
    os.makedirs(path, exist_ok=True)
    return path


def data_dir() -> str:
    """可写、长期保留（放输出与导出包）。"""
    p = _paths()
    if p is not None and getattr(p, "data", None):
        os.makedirs(p.data, exist_ok=True)
        return p.data
    return _fallback("data")


def cache_dir() -> str:
    """可被系统清理（放 vanilla_cache / wiki_cache）。"""
    p = _paths()
    if p is not None and getattr(p, "cache", None):
        os.makedirs(p.cache, exist_ok=True)
        return p.cache
    return _fallback("cache")


def exports_dir() -> str:
    path = os.path.join(data_dir(), "exports")
    os.makedirs(path, exist_ok=True)
    return path


def work_dir() -> str:
    """解包压缩包用的临时目录（对应桌面版的 mcwork_*）。"""
    path = os.path.join(cache_dir(), "work")
    os.makedirs(path, exist_ok=True)
    return path


def default_output_dir() -> str:
    """默认输出根：它下面会再建一个「合成表」子目录，与桌面版一致。"""
    path = os.path.join(exports_dir(), "out")
    os.makedirs(path, exist_ok=True)
    return path


def tool_root() -> str:
    """核心模块的 tool_root 参数：vanilla_cache / wiki_cache 落在这里。"""
    return cache_dir()


def bundled_assets() -> str:
    """随包发布的只读资源（assets/ui、assets/panels、icon）。"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def describe() -> str:
    return (f"android={IS_ANDROID} data={data_dir()} cache={cache_dir()} "
            f"exports={exports_dir()}")
