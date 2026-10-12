"""Android 目录（SAF tree）支持：选目录、把目录内容导入到私有目录、把结果写回所选目录。

为什么需要它：
- 手机上"选择文件夹"必须用 ACTION_OPEN_DOCUMENT_TREE（文件选择器只能选单个文件）
- 核心渲染只认普通文件路径，所以要先把选中的目录内容复制进 App 私有目录
- 出图目录同样通过 tree URI 写入（DocumentFile.createFile + openOutputStream）
"""
from __future__ import annotations

import os
import threading
import time

TREE_REQUEST = 0xBEE1


def _jnius():
    from jnius import autoclass
    return {
        "autoclass": autoclass,
        "PythonActivity": autoclass("org.kivy.android.PythonActivity"),
        "Intent": autoclass("android.content.Intent"),
        "Uri": autoclass("android.net.Uri"),
        "DocumentFile": autoclass("androidx.documentfile.provider.DocumentFile"),
    }


def pick_tree(title: str = "选择文件夹") -> str:
    """弹系统目录选择器，返回 tree URI 字符串（失败返回空串）。必须在主线程调用。"""
    try:
        from android import activity as android_activity
        j = _jnius()
    except Exception:
        return ""

    result = []

    def _on_result(request, code, data):
        if request != TREE_REQUEST or data is None:
            return
        try:
            uri = data.getData()
            if uri is not None:
                result.append(str(uri.toString()))
        except Exception:
            pass

    try:
        j["Intent"]  # noqa: B018
        intent = j["Intent"](j["Intent"].ACTION_OPEN_DOCUMENT_TREE)
        intent.addFlags(0x00000040 | 0x00000001 | 0x00000002)  # GRANT_* + PERSISTABLE
        android_activity.bind(on_activity_result=_on_result)
        j["PythonActivity"].mActivity.startActivityForResult(intent, TREE_REQUEST)
        for _ in range(1200):
            if result:
                break
            time.sleep(0.1)
        android_activity.unbind(on_activity_result=_on_result)
    except Exception:
        return ""
    if not result:
        return ""
    # 持久授权，重启后仍可写
    try:
        j["PythonActivity"].mActivity.getContentResolver().takePersistableUriPermission(
            j["Uri"].parse(result[0]), 0x00000001 | 0x00000002)
    except Exception:
        pass
    return result[0]


def _open_tree(uri: str):
    j = _jnius()
    ctx = j["PythonActivity"].mActivity
    return j["DocumentFile"].fromTreeUri(ctx, j["Uri"].parse(uri)), ctx


def import_tree(uri: str, dest: str) -> int:
    """把 SAF 目录里的全部文件复制到 dest（返回复制数量）。"""
    if not uri:
        return 0
    try:
        root, ctx = _open_tree(uri)
        resolver = ctx.getContentResolver()
    except Exception:
        return 0
    count = 0
    stack = [(root, dest)]
    while stack:
        doc, out_dir = stack.pop()
        try:
            os.makedirs(out_dir, exist_ok=True)
            for child in doc.listFiles():
                name = str(child.getName() or "unnamed")
                if child.isDirectory():
                    stack.append((child, os.path.join(out_dir, name)))
                    continue
                stream = resolver.openInputStream(child.getUri())
                with open(os.path.join(out_dir, name), "wb") as fh:
                    buf = bytearray(1 << 16)
                    while True:
                        n = stream.read(buf)
                        if n <= 0:
                            break
                        fh.write(bytes(buf[:n]))
                stream.close()
                count += 1
        except Exception:
            continue
    return count


def export_tree(uri: str, src_dir: str, folder: str = "合成表") -> str:
    """把 src_dir 下的所有 PNG 写进所选目录的 <folder> 子目录，返回提示信息。"""
    if not uri or not os.path.isdir(src_dir):
        return ""
    try:
        root, ctx = _open_tree(uri)
        sub = root.findFile(folder) or root.createDirectory(folder)
        if sub is None:
            return ""
        written = 0
        for r, _dirs, files in os.walk(src_dir):
            for f in files:
                if not f.lower().endswith(".png"):
                    continue
                name = f
                target = sub.findFile(name)
                if target is None:
                    target = sub.createFile("image/png", name)
                if target is None:
                    continue
                src = os.path.join(r, f)
                with open(src, "rb") as fh:
                    data = fh.read()
                stream = ctx.getContentResolver().openOutputStream(target.getUri())
                stream.write(bytearray(data))
                stream.flush()
                stream.close()
                written += 1
        return f"已写入 {written} 张到所选目录 / {folder}"
    except Exception as exc:
        return "写入失败: " + str(exc)[:80]


def run_async(fn, *args):
    """在后台线程里跑导入/导出（不涉及 Activity 调用，安全）。"""
    t = threading.Thread(target=fn, args=args, daemon=True)
    t.start()
    return t

# ---- 官方"选择文件"接口：Intent.ACTION_OPEN_DOCUMENT（可多选） ----------------
# 文档：https://developer.android.com/training/data-storage/shared/documents-files
# 选中的是 content:// URI，核心只认普通路径，所以先复制进 App 私有目录再交给核心。
FILE_REQUEST = 0xBEE2


def pick_files(title: str = "选择文件", mime: str = "*/*") -> list:
    """弹**系统**文件选择器（可多选），返回复制到私有目录后的真实路径列表。

    - 用官方 Intent.ACTION_OPEN_DOCUMENT + EXTRA_ALLOW_MULTIPLE，不自己写文件浏览器
    - 同时申请可持久化的读权限，重启后仍能访问同一批文件
    - 失败/取消返回 []（调用方可以退回内置浏览器）
    """
    try:
        from android import activity as android_activity
        j = _jnius()
        Intent = j["Intent"]
        Uri = j["Uri"]
        PythonActivity = j["PythonActivity"]
        activity = PythonActivity.mActivity
    except Exception:
        return []

    out = []
    done = threading.Event()

    def _on_result(request, code, data):
        if request != FILE_REQUEST:
            return
        try:
            if code == -1 and data is not None:              # RESULT_OK
                uris = []
                clip = data.getClipData()
                if clip is not None:
                    for i in range(clip.getItemCount()):
                        uris.append(clip.getItemAt(i).getUri())
                elif data.getData() is not None:
                    uris.append(data.getData())
                resolver = activity.getContentResolver()
                dest = os.path.join(os.path.dirname(os.path.dirname(
                    os.path.abspath(__file__))), "picked")
                os.makedirs(dest, exist_ok=True)
                for uri in uris:
                    try:
                        # 持久化读权限：官方说明里这是重启后继续访问的唯一方式
                        resolver.takePersistableUriPermission(
                            uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    except Exception:
                        pass
                    name = _display_name(resolver, uri) or "picked"
                    target = os.path.join(dest, name)
                    with open(target, "wb") as fh:
                        stream = resolver.openInputStream(uri)
                        buf = bytearray(65536)
                        while True:
                            n = stream.read(buf)
                            if n <= 0:
                                break
                            fh.write(bytes(buf[:n]))
                        stream.close()
                    out.append(target)
        except Exception:
            pass
        finally:
            done.set()

    android_activity.bind(on_activity_result=_on_result)
    try:
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.addCategory(Intent.CATEGORY_OPENABLE)
        intent.setType(mime)
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, True)
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                        | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
        PythonActivity.mActivity.startActivityForResult(intent, FILE_REQUEST)
    except Exception:
        return []
    done.wait(timeout=600)
    return out


def _display_name(resolver, uri) -> str:
    """从 content:// URI 查出真实文件名（官方 OpenableColumns.DISPLAY_NAME）。"""
    try:
        from jnius import autoclass
        OpenableColumns = autoclass("android.provider.OpenableColumns")
        cursor = resolver.query(uri, None, None, None, None)
        if cursor is not None:
            try:
                if cursor.moveToFirst():
                    idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if idx >= 0:
                        return cursor.getString(idx)
            finally:
                cursor.close()
    except Exception:
        pass
    return ""

