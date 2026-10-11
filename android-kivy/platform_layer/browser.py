"""内置文件浏览器（Kivy）——纯 Python 列目录，不跳 Activity、不碰 SAF。

背景：Android 的 SAF 选择器在部分 ROM（如 realme/OPPO）上会出现黑屏、
返回键退出 App、只能选单文件等问题。拿到「所有文件访问权限」后，
直接用 os.listdir 就能浏览 /sdcard，稳定且可控。

用法：
    FileBrowser(start="/sdcard/Download", mode="file",
                on_pick=lambda path: ..., filter_ext=(".json", ".zip")).open()
    mode="dir"  选目录（底部按钮变成「选择此目录」）
"""
from __future__ import annotations

import os

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView


class FileBrowser(Popup):
    def __init__(self, start: str = "/sdcard", mode: str = "file", on_pick=None,
                 filter_ext=None, title: str = "选择文件", **kw):
        super().__init__(title=title, size_hint=(0.96, 0.92), **kw)
        self.mode = mode                       # "file" | "dir"
        self.on_pick = on_pick
        self.filter_ext = tuple(filter_ext) if filter_ext else None
        self.cwd = start if os.path.isdir(start) else "/sdcard"

        root = BoxLayout(orientation="vertical", spacing=dp(4), padding=dp(4))

        # 顶部：当前路径 + 快捷入口
        self.path_label = Label(text=self.cwd, size_hint_y=None, height=dp(28),
                                font_size=dp(12), shorten=True)
        root.add_widget(self.path_label)

        shortcuts = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))
        for label, path in self._shortcuts():
            btn = Button(text=label, font_size=dp(11))
            btn.bind(on_release=lambda _b, p=path: self._go(p))
            shortcuts.add_widget(btn)
        root.add_widget(shortcuts)

        # 文件列表
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(2))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(self.list_box)
        root.add_widget(scroll)

        # 底部：动作
        actions = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        pick_text = "选择此目录" if mode == "dir" else "选择此文件"
        self.pick_btn = Button(text=pick_text)
        self.pick_btn.bind(on_release=self._pick_current)
        up = Button(text="上一级")
        up.bind(on_release=lambda *_: self._go(os.path.dirname(self.cwd)))
        cancel = Button(text="取消")
        cancel.bind(on_release=lambda *_: self.dismiss())
        actions.add_widget(up)
        actions.add_widget(self.pick_btn)
        actions.add_widget(cancel)
        root.add_widget(actions)

        # 选文件模式下，"当前目录"不能被选中
        self.pick_btn.disabled = (mode == "file")

        self.content = root
        self._refresh()

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _shortcuts():
        from . import perm
        return perm.shortcut_dirs()

    def _go(self, path: str) -> None:
        path = os.path.abspath(path)
        if os.path.isdir(path):
            self.cwd = path
            self._refresh()

    def _refresh(self) -> None:
        self.path_label.text = self.cwd
        self.list_box.clear_widgets()
        try:
            entries = sorted(os.scandir(self.cwd), key=lambda e: (not e.is_dir(),
                                                                  e.name.lower()))
        except Exception as exc:
            self.list_box.add_widget(Label(text="无法读取该目录：" + str(exc)[:60],
                                           size_hint_y=None, height=dp(40)))
            return

        if os.path.dirname(self.cwd) not in (self.cwd, ""):
            b = Button(text="[ 上一级 ]", size_hint_y=None, height=dp(42))
            b.bind(on_release=lambda *_: self._go(os.path.dirname(self.cwd)))
            self.list_box.add_widget(b)

        shown = 0
        for ent in entries:
            try:
                is_dir = ent.is_dir()
            except Exception:
                continue
            if not is_dir and self.filter_ext is not None and \
                    not ent.name.lower().endswith(self.filter_ext):
                continue
            if ent.name.startswith("."):
                continue
            label = ("[目录] " if is_dir else "        ") + ent.name
            b = Button(text=label, size_hint_y=None, height=dp(42), halign="left",
                       font_size=dp(12))
            if is_dir:
                b.bind(on_release=lambda _b, p=ent.path: self._go(p))
            else:
                b.bind(on_release=lambda _b, p=ent.path: self._choose(p))
            self.list_box.add_widget(b)
            shown += 1
            if shown >= 400:                    # 防止超大目录卡顿
                self.list_box.add_widget(Label(text="（只显示前 400 项）",
                                               size_hint_y=None, height=dp(30)))
                break
        if shown == 0:
            self.list_box.add_widget(Label(text="（此目录下没有可选内容）",
                                           size_hint_y=None, height=dp(40)))

    def _choose(self, path: str) -> None:
        if self.on_pick:
            self.on_pick(path)
        self.dismiss()

    def _pick_current(self, *_a) -> None:
        if self.mode == "dir":
            self._choose(self.cwd)
        else:
            self._choose(self.cwd)
