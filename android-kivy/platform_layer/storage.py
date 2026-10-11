"""Kivy/Android 导出：打包 ZIP、写到外部私有目录、调系统分享。"""
from __future__ import annotations

import os
import shutil
import zipfile


def app_files_dir() -> str:
    """外部私有目录：/sdcard/Android/data/<包名>/files —— 文件管理器可见，免权限。"""
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ctx = PythonActivity.mActivity
        ext = ctx.getExternalFilesDir(None)
        if ext is not None:
            return str(ext.getAbsolutePath())
    except Exception:
        pass
    return os.environ.get("ANDROID_PRIVATE", ".")


def zip_outputs(out_root: str, dest_zip: str | None = None) -> str:
    dest_zip = dest_zip or os.path.join(app_files_dir(), "合成表.zip")
    try:
        os.makedirs(os.path.dirname(dest_zip), exist_ok=True)
    except Exception:
        pass
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
    if not count:
        os.remove(dest_zip)
        return ""
    # 同时放一份到更易找到的位置
    try:
        public = os.path.join(app_files_dir(), "合成表.zip")
        if os.path.abspath(public) != os.path.abspath(dest_zip):
            shutil.copy2(dest_zip, public)
    except Exception:
        pass
    return dest_zip


def list_png(out_root: str) -> list[str]:
    return [os.path.join(r, f) for r, _d, fs in os.walk(out_root) for f in sorted(fs)
            if f.lower().endswith(".png")]


def share(path: str) -> bool:
    """用系统分享面板把 ZIP 发出去（微信/QQ/网盘）。"""
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        File = autoclass("java.io.File")
        String = autoclass("java.lang.String")
        activity = PythonActivity.mActivity
        intent = Intent(Intent.ACTION_SEND)
        intent.setType("application/zip")
        intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable",
                                                  File(path).toURI()))
        activity.startActivity(Intent.createChooser(intent, cast("java.lang.CharSequence",
                                                                 String("分享合成表"))))
        return True
    except Exception:
        return False
