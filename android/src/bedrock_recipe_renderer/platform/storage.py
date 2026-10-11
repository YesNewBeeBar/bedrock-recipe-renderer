"""导出与分享：Android 上没有「打开输出文件夹」，改用
1) 打包 ZIP（一次拿到全部 PNG）
2) 逐张另存（SAF，用户自己选位置）
3) 系统分享（Intent，交给微信/QQ/相册）
"""
from __future__ import annotations

import os
import shutil
import zipfile


def zip_outputs(out_root: str, dest_zip: str | None = None) -> str:
    """把输出目录整个打成一个 zip。"""
    dest_zip = dest_zip or (out_root.rstrip("/\\") + ".zip")
    if os.path.exists(dest_zip):
        os.remove(dest_zip)
    count = 0
    with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(out_root):
            for f in files:
                if f.lower().endswith(".png"):
                    full = os.path.join(root, f)
                    zf.write(full, os.path.relpath(full, out_root))
                    count += 1
    return dest_zip if count else ""


def list_png(out_root: str) -> list[str]:
    out = []
    for root, _dirs, files in os.walk(out_root):
        for f in sorted(files):
            if f.lower().endswith(".png"):
                out.append(os.path.join(root, f))
    return out


async def save_as(dialog, src: str, suggested: str | None = None) -> str | None:
    """另存一张图（Android → SAF 的 ACTION_CREATE_DOCUMENT）。"""
    try:
        target = await dialog.save_file(title="另存为", suggested_filename=suggested
                                        or os.path.basename(src))
    except TypeError:
        target = await dialog.save_file(title="另存为")
    if not target:
        return None
    shutil.copy2(src, str(target))
    return str(target)


async def share(app, path: str) -> bool:
    """调用系统分享面板（Toga 在 Android 上支持 share）。"""
    try:
        await app.share(path)          # Toga 0.4+ 的 App.share
        return True
    except Exception:
        return False
