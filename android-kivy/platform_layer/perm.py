"""「所有文件访问权限」（MANAGE_EXTERNAL_STORAGE）的申请与检测。

为什么需要：Android 11+ 的 SAF 选择器在部分 ROM 上会黑屏 / 返回键退出 App；
拿到这个权限后，App 可以像文件管理器一样直接读写 /sdcard，内置浏览器就能工作，
完全不再依赖 SAF 的 Activity 跳转。
"""
from __future__ import annotations

import os


def _jnius():
    from jnius import autoclass
    return autoclass


def has_all_files() -> bool:
    """是否已获得「所有文件访问权限」。Android 10 及以下直接返回 True。"""
    try:
        j = _jnius()
        Environment = j("android.os.Environment")
        if hasattr(Environment, "isExternalStorageManager"):
            return bool(Environment.isExternalStorageManager())
        return True
    except Exception:
        return True


def can_read_public() -> bool:
    """粗略地试一下能不能读公共目录（拿不到权限时会失败）。"""
    for probe in ("/sdcard/Download", "/sdcard/Documents", "/sdcard"):
        try:
            os.listdir(probe)
            return True
        except Exception:
            continue
    return False


def request_all_files() -> bool:
    """跳到系统的「所有文件访问」授权页。必须在主线程调用。"""
    try:
        j = _jnius()
        activity = j("org.kivy.android.PythonActivity").mActivity
        Intent = j("android.content.Intent")
        Uri = j("android.net.Uri")
        Settings = j("android.provider.Settings")
        Action = j("android.provider.Settings$Action")
        pkg = str(activity.getPackageName())
        intent = Intent("android.settings.MANAGE_APP_ALL_FILES_ACCESS_PERMISSION")
        intent.setData(Uri.parse("package:" + pkg))
        activity.startActivity(intent)
        return True
    except Exception:
        try:
            j = _jnius()
            activity = j("org.kivy.android.PythonActivity").mActivity
            Intent = j("android.content.Intent")
            intent = Intent("android.settings.MANAGE_ALL_FILES_ACCESS_PERMISSION")
            activity.startActivity(intent)
            return True
        except Exception:
            return False


def shortcut_dirs() -> list[tuple[str, str]]:
    """常见目录快捷入口（只保留存在的）。"""
    home = "/sdcard"
    candidates = [
        ("Download", home + "/Download"),
        ("Documents", home + "/Documents"),
        ("Pictures", home + "/Pictures"),
        ("根目录 /sdcard", home),
        ("微信", home + "/Android/data/com.tencent.mm/MicroMsg/Download"),
        ("QQ", home + "/Tencent/QQfile_recv"),
        ("Minecraft", home + "/games/com.mojang"),
    ]
    out = [("根目录 /sdcard", home)]
    for label, path in candidates:
        try:
            if os.path.isdir(path) and path != home:
                out.append((label, path))
        except Exception:
            continue
    return out
