"""文件选择：桌面拖放 → Android 文件选择器。

Toga 的对话框在 Android 上走系统 SAF（Storage Access Framework），
拿到的是 **content:// 加密路径**；Toga 会把它映射成本地可读文件，
但为稳妥起见这里统一做一次「落到私有目录再交给核心」的处理。
"""
from __future__ import annotations

import os
import shutil

ARCHIVE_EXT = (".zip", ".mcaddon", ".mcpack", ".mcworld", ".mcproject")


async def pick_files(dialog, multiple: bool = True) -> list[str]:
    """选配方 JSON / 压缩包。"""
    try:
        result = await dialog.open_file(
            title="选择配方 JSON 或附加包压缩包",
            multiple=multiple,
            file_types=["json", "zip", "mcaddon", "mcpack", "mcworld", "mcproject"],
        )
    except TypeError:
        # 老版本 Toga 没有 multiple/file_types 参数
        result = await dialog.open_file(title="选择配方 JSON 或附加包压缩包")
    if result is None:
        return []
    if isinstance(result, (list, tuple)):
        return [str(p) for p in result]
    return [str(result)]


async def pick_folder(dialog) -> str | None:
    """选文件夹（行为包 / 资源包 / 输出目录）。"""
    try:
        result = await dialog.select_folder(title="选择文件夹")
    except AttributeError:
        result = await dialog.open_file(title="选择文件夹")
    return str(result) if result else None


def ensure_local(paths: list[str], work_root: str) -> list[str]:
    """content:// 或只读位置 → 复制进私有目录，保证核心能正常读写。"""
    out: list[str] = []
    for path in paths:
        if not path:
            continue
        if path.startswith("content://") or not os.path.exists(path):
            continue
        if os.access(path, os.R_OK):
            out.append(path)
            continue
        target = os.path.join(work_root, "input", os.path.basename(path))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(path, target)
        out.append(target)
    return out


def is_archive(path: str) -> bool:
    return path.lower().endswith(ARCHIVE_EXT)
