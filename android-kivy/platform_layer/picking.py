"""Kivy/Android 平台层：选择器与导出。

- 选择器优先用 plyer（走 SAF，返回真实路径或 content://）
- 拿不到就退回 jnius 直接调 ACTION_OPEN_DOCUMENT
- 复制到的私有目录后再交给核心（核心只认普通文件路径）
"""
from __future__ import annotations

import os
import shutil
import zipfile

ARCHIVE_EXT = (".zip", ".mcaddon", ".mcpack", ".mcworld", ".mcproject")


def is_archive(path: str) -> bool:
    return path.lower().endswith(ARCHIVE_EXT)


# ------------------------------------------------------------------ 选择
def pick_files(multiple: bool = True) -> list[str]:
    """返回本地可读的文件路径列表。"""
    paths = _pick_plyer(multiple) or _pick_jnius(multiple)
    return _localize(paths)


def pick_dir() -> str | None:
    """Kivy 端没有可靠的目录选择器：让用户选该目录下的 manifest.json，取其父目录。"""
    picked = pick_files(multiple=False)
    if not picked:
        return None
    p = picked[0]
    return os.path.dirname(p) if os.path.isfile(p) else p


def _pick_plyer(multiple: bool) -> list[str]:
    try:
        from plyer import filechooser
    except Exception:
        return []
    holder: list[str] = []

    def _cb(selection):
        holder.extend(selection or [])

    try:
        filechooser.open_file(multiple=multiple, on_selection=_cb,
                              filters=["*.json", "*.zip", "*.mcaddon", "*.mcpack"])
        # plyer 在 Android 上是异步回调；给一点时间
        import time
        for _ in range(300):
            if holder:
                break
            time.sleep(0.1)
    except Exception:
        return []
    return holder


def _pick_jnius(multiple: bool) -> list[str]:
    """直接调 SAF；结果通过 android.activity 回调拿。"""
    try:
        from android import activity as android_activity
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        String = autoclass("java.lang.String")
    except Exception:
        return []

    got: list[str] = []
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("*/*")
    if multiple:
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)

    def _on_result(request, result, data):
        if data is None:
            return
        try:
            clip = data.getClipData()
            if clip is not None:
                for i in range(clip.getItemCount()):
                    got.append(str(clip.getItemAt(i).getUri().toString()))
            else:
                uri = data.getData()
                if uri is not None:
                    got.append(str(uri.toString()))
        except Exception:
            pass

    try:
        android_activity.bind(on_activity_result=_on_result)
        PythonActivity.mActivity.startActivityForResult(intent, 0xBEEF)
        import time
        for _ in range(600):
            if got:
                break
            time.sleep(0.1)
        android_activity.unbind(on_activity_result=_on_result)
    except Exception:
        return []
    return _copy_uris(got)


def _copy_uris(uris: list[str]) -> list[str]:
    """content:// → 复制进 App 私有目录（核心只认普通路径）。"""
    if not uris:
        return []
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Uri = autoclass("android.net.Uri")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
    except Exception:
        return [u for u in uris if os.path.isfile(u)]

    out: list[str] = []
    work = os.path.join(os.environ.get("ANDROID_PRIVATE", "."), "picked")
    os.makedirs(work, exist_ok=True)
    for uri in uris:
        try:
            parsed = Uri.parse(uri)
            stream = resolver.openInputStream(parsed)
            name = _display_name(resolver, parsed) or os.path.basename(uri)
            dest = os.path.join(work, name)
            with open(dest, "wb") as fh:
                buf = bytearray(65536)
                while True:
                    n = stream.read(buf)
                    if n <= 0:
                        break
                    fh.write(bytes(buf[:n]))
            stream.close()
            out.append(dest)
        except Exception:
            continue
    return out


def _display_name(resolver, uri) -> str | None:
    try:
        from jnius import autoclass, cast
        OpenableColumns = autoclass("android.provider.OpenableColumns")
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is None:
            return None
        idx = cursor.getColumnIndex("_display_name")
        if idx < 0 or not cursor.moveToFirst():
            cursor.close()
            return None
        name = cursor.getString(idx)
        cursor.close()
        return str(name)
    except Exception:
        return None


def _localize(paths: list[str]) -> list[str]:
    out = []
    for p in paths or []:
        if not p:
            continue
        if p.startswith("content://"):
            out += _copy_uris([p])
        elif os.path.exists(p):
            out.append(p)
    return out


# ------------------------------------------------------------------ 解包
def unpack_recipes(archive: str, work_root: str) -> list[str]:
    """解压缩包（含双层）并返回其中所有配方 JSON。"""
    target = os.path.join(work_root, "unpack", os.path.basename(archive))
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
    except Exception:
        return []
    found = [os.path.join(r, f) for r, _d, fs in os.walk(target)
             for f in fs if f.endswith(".json")]
    for root, _dirs, files in os.walk(target):
        for f in files:
            full = os.path.join(root, f)
            if is_archive(full):
                try:
                    sub = full + "_x"
                    with zipfile.ZipFile(full) as inner:
                        inner.extractall(sub)
                    found += [os.path.join(r, g) for r, _d, gs in os.walk(sub)
                              for g in gs if g.endswith(".json")]
                except Exception:
                    pass
    return sorted(dict.fromkeys(found))
