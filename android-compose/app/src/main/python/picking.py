"""Android 文件/目录选择 —— 只用一条 jnius 通道，异步，绝不阻塞主线程。

历史教训：
1. 早期先调 plyer 又调 jnius → 一次点击启动两个选择器 ✗
   → 黑屏 + 第二个选择器 + 返回键把整个 App 关掉 ✗
2. 早期在主线程 for ... sleep(0.1) 死等回调 → 主线程卡死 = 黑屏 ✗
   → 正确：发 Intent 后立刻返回，结果在 on_activity_result 处理
3. 回调必须在收到结果时解绑，否则下次点击叠加多个回调 ✗
"""
from __future__ import annotations

import os
import shutil
import threading
import zipfile

FILE_REQUEST = 0xBEE2
TREE_REQUEST = 0xBEE3
ARCHIVE_EXT = (".zip", ".mcaddon", ".mcpack", ".mcworld", ".mcproject")


def is_archive(path):
    return path.lower().endswith(ARCHIVE_EXT)


def _activity():
    from jnius import autoclass
    return autoclass("org.kivy.android.PythonActivity").mActivity


def _private():
    return os.environ.get("ANDROID_PRIVATE", ".")


def _to_ui(fn, *args):
    try:
        from kivy.clock import Clock
        Clock.schedule_once(lambda *_: fn(*args), 0)
    except Exception:
        try:
            fn(*args)
        except Exception:
            pass


def _copy_uri(uri, work_dir):
    try:
        from jnius import autoclass
        Uri = autoclass("android.net.Uri")
        activity = _activity()
        resolver = activity.getContentResolver()
        parsed = Uri.parse(uri)
        name = ""
        cursor = resolver.query(parsed, None, None, None, None)
        if cursor is not None:
            idx = cursor.getColumnIndex("_display_name")
            if idx >= 0 and cursor.moveToFirst():
                name = str(cursor.getString(idx))
            cursor.close()
        name = name or uri.rsplit("/", 1)[-1]
        os.makedirs(work_dir, exist_ok=True)
        dest = os.path.join(work_dir, name)
        stream = resolver.openInputStream(parsed)
        with open(dest, "wb") as fh:
            buf = bytearray(1 << 16)
            while True:
                n = stream.read(buf)
                if n <= 0:
                    break
                fh.write(bytes(buf[:n]))
        stream.close()
        return [dest]
    except Exception:
        return []


def _import_tree(uri, dest):
    try:
        from jnius import autoclass
        Uri = autoclass("android.net.Uri")
        DocumentFile = autoclass("androidx.documentfile.provider.DocumentFile")
        activity = _activity()
        root = DocumentFile.fromTreeUri(activity, Uri.parse(uri))
        resolver = activity.getContentResolver()
    except Exception:
        return 0
    count = 0
    stack = [(root, dest)]
    while stack:
        doc, out_dir = stack.pop()
        try:
            os.makedirs(out_dir, exist_ok=True)
            for child in doc.listFiles():
                nm = str(child.getName() or "unnamed")
                if child.isDirectory():
                    stack.append((child, os.path.join(out_dir, nm)))
                    continue
                stream = resolver.openInputStream(child.getUri())
                with open(os.path.join(out_dir, nm), "wb") as fh:
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


def unpack_archive(archive, work_root, depth=3):
    """把压缩包（含双层压缩）解到私有目录，返回解包根目录。

    只负责解包，**不判断哪些是配方** —— 那是核心 mcrender.recipes.collect() 的活。
    实测同一份 .mcaddon：自己按目录名找只认出 14 条，核心 collect() 能认出 310 条。
    """
    target = os.path.join(work_root, "unpack", os.path.basename(archive))
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
    except Exception:
        return target

    for _ in range(depth):                     # 逐层解开内层压缩包
        found_any = False
        for base, _dirs, files in os.walk(target):
            for f in files:
                if not is_archive(f):
                    continue
                full = os.path.join(base, f)
                sub = full + "_x"
                if os.path.isdir(sub):
                    continue
                try:
                    with zipfile.ZipFile(full) as z:
                        z.extractall(sub)
                    found_any = True
                except Exception:
                    continue
        if not found_any:
            break
    return target


def unpack_recipes(archive, work_root):
    """兼容旧调用：返回解出来的全部 json（配方识别交给核心 collect()）。"""
    root = unpack_archive(archive, work_root)
    return [os.path.join(b, f) for b, _d, fs in os.walk(root) for f in fs
            if f.lower().endswith(".json")]


def pick_files(on_done, multiple=True):
    """选文件：只发一次 Intent，立刻返回；结果经 on_done(list[path]) 回调。"""
    from android import activity as android_activity
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
    intent.addCategory(Intent.CATEGORY_OPENABLE)
    intent.setType("*/*")
    if multiple:
        intent.putExtra("android.intent.extra.ALLOW_MULTIPLE", True)

    def _result(request, _code, data):
        if request != FILE_REQUEST:
            return
        android_activity.unbind(on_activity_result=_result)
        uris = []
        if data is not None:
            try:
                clip = data.getClipData()
                if clip is not None:
                    for i in range(clip.getItemCount()):
                        uris.append(str(clip.getItemAt(i).getUri().toString()))
                else:
                    got = data.getData()
                    if got is not None:
                        uris.append(str(got.toString()))
            except Exception:
                pass

        def work():
            work_dir = os.path.join(_private(), "picked")
            out = []
            for u in uris:
                out += _copy_uri(u, work_dir)
            _to_ui(on_done, out)

        threading.Thread(target=work, daemon=True).start()

    android_activity.bind(on_activity_result=_result)
    _activity().startActivityForResult(intent, FILE_REQUEST)


def pick_tree(on_done, title="选择文件夹"):
    """选目录：同样只发一次；on_done(uri, local_dir, copied)。"""
    from android import activity as android_activity
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
    intent.addFlags(0x40 | 0x1 | 0x2)

    def _result(request, _code, data):
        if request != TREE_REQUEST:
            return
        android_activity.unbind(on_activity_result=_result)
        uri = ""
        if data is not None:
            try:
                got = data.getData()
                if got is not None:
                    uri = str(got.toString())
            except Exception:
                pass
        if not uri:
            _to_ui(on_done, "", "", 0)
            return
        try:
            from jnius import autoclass as _ac
            Uri = _ac("android.net.Uri")
            _activity().getContentResolver().takePersistableUriPermission(
                Uri.parse(uri), 0x1 | 0x2)
        except Exception:
            pass

        def work():
            safe = "".join(c if c.isalnum() else "_" for c in uri[-28:])
            dest = os.path.join(_private(), "picked_tree", safe)
            n = _import_tree(uri, dest)
            _to_ui(on_done, uri, dest, n)

        threading.Thread(target=work, daemon=True).start()

    android_activity.bind(on_activity_result=_result)
    _activity().startActivityForResult(intent, TREE_REQUEST)
