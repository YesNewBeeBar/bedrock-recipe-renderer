"""崩溃捕获：在应用内**弹窗显示完整 traceback** + 一键复制到剪贴板。

为什么不用文件：Android 11+ 把 Android/data/<包名>/files 对第三方文件管理器隐藏了，
用户根本看不到日志文件。所以这里改成：
    1) 仍然写一份到私有目录（有 root / 用 adb 时可取）
    2) 同时在 App 内弹一个可滚动、可选中、可复制的窗口 —— 用户粘到微信发出来即可
"""
from __future__ import annotations

import os
import sys
import traceback

_VIEW = None
_SHOWN = set()


def crash_path() -> str:
    try:
        from jnius import autoclass
        ctx = autoclass("org.kivy.android.PythonActivity").mActivity
        ext = ctx.getExternalFilesDir(None)
        if ext is not None:
            return os.path.join(str(ext.getAbsolutePath()), "crash.log")
    except Exception:
        pass
    return os.path.join(os.environ.get("ANDROID_PRIVATE", "."), "crash.log")


def _write_file(text: str) -> str:
    try:
        with open(crash_path(), "a", encoding="utf-8") as fh:
            fh.write(text)
            fh.write("-" * 60)
            fh.write("\n")
        return crash_path()
    except Exception:
        return ""


def _popup(title: str, body: str) -> None:
    """在主线程弹窗展示，内容可选中复制。"""
    def _show(*_a):
        try:
            from kivy.core.clipboard import Clipboard
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.button import Button
            from kivy.uix.label import Label
            from kivy.uix.popup import Popup
            from kivy.uix.scrollview import ScrollView
            from kivy.uix.textinput import TextInput

            box = BoxLayout(orientation="vertical", spacing=4, padding=6)
            box.add_widget(Label(text=title, size_hint_y=None, height=30))
            ti = TextInput(text=body, readonly=True, font_size="11sp")
            scroll = ScrollView()
            scroll.add_widget(ti)
            box.add_widget(scroll)

            row = BoxLayout(size_hint_y=None, height=44, spacing=4)
            btn_copy = Button(text="复制日志")
            btn_close = Button(text="关闭")

            def _copy(*_x):
                Clipboard.copy(body)
                btn_copy.text = "已复制 ✓"

            btn_copy.bind(on_release=_copy)
            row.add_widget(btn_copy)

            popup = Popup(title="出错了（请把下面内容发我）", content=box,
                          size_hint=(0.95, 0.85))

            def _close(*_x):
                popup.dismiss()

            btn_close.bind(on_release=_close)
            row.add_widget(btn_close)
            box.add_widget(row)
            popup.open()
        except Exception:
            pass

    try:
        from kivy.clock import Clock
        Clock.schedule_once(_show, 0)
    except Exception:
        pass


def report(kind: str, exc: BaseException) -> None:
    txt = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    head = f"# {kind}: {exc}\n"
    path = _write_file(head + txt)
    key = str(exc)[:200]
    if key in _SHOWN:
        return
    _SHOWN.add(key)
    body = head + txt
    if path:
        body += f"\n（也已写入 {path}）"
    if _VIEW is not None:
        try:
            _VIEW.write("!! 崩溃：" + str(exc)[:120])
        except Exception:
            pass
    _popup(kind, body)


def install(view=None) -> None:
    global _VIEW
    _VIEW = view

    def _hook(exc_type, exc, tb):
        report("未捕获异常", exc)

    sys.excepthook = _hook

    try:                     # Kivy 回调里的异常也走同一条路
        from kivy.base import ExceptionHandler, ExceptionManager

        class _Handler(ExceptionHandler):
            def handle_exception(self, inst):
                report("界面回调异常", inst)
                return ExceptionManager.PASS

        ExceptionManager.add_handler(_Handler())
    except Exception:
        pass
