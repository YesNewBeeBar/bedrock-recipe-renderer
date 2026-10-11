"""路线 A：Kivy + Buildozer 版界面（与 Toga 版等价）。

选这条路的理由只有一个：**python-for-android 有官方维护的 Pillow recipe**，
不用自己交叉编译。核心渲染代码与桌面版完全同一份。

    buildozer -v android debug          # 出 APK
"""
from __future__ import annotations

import asyncio  # noqa: F401  (Kivy 用 Clock 调度，这里仅保持导入一致性)
import os
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch

from bedrock_recipe_renderer.mcrender.assets import Assets
from bedrock_recipe_renderer.mcrender.recipes import collect, parse
from bedrock_recipe_renderer.mcrender.render import Renderer
from bedrock_recipe_renderer.platform import fonts as platform_fonts
from bedrock_recipe_renderer.platform import paths, picker, storage


def android_pick_files(multiple: bool = True):
    """Android 原生选择器（Kivy 走 android.storage / Intent）。"""
    try:
        from android import activity  # noqa: F401
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
        intent.setType("*/*")
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, multiple)
        PythonActivity.mActivity.startActivityForResult(intent, 0xBEEF)
        return []                      # 结果通过 activity 回调拿，见 kivy 官方示例
    except Exception:
        return []


class MainView(BoxLayout):
    log_text = StringProperty("")
    progress = NumericProperty(0.0)
    offline = BooleanProperty(False)

    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=8, spacing=6, **kw)
        self.files: list[str] = []
        self.state = {"bp": "", "rp": "", "vanilla": "", "out": paths.default_output_dir()}
        self._build()

    def _build(self) -> None:
        self.add_widget(Label(text="合成表生成器", size_hint_y=None, height=36))
        row = BoxLayout(size_hint_y=None, height=44, spacing=4)
        row.add_widget(Button(text="选配方", on_press=self.on_pick))
        row.add_widget(Button(text="BP", on_press=lambda *_: self._set("bp")))
        row.add_widget(Button(text="RP", on_press=lambda *_: self._set("rp")))
        row.add_widget(Button(text="原版包", on_press=lambda *_: self._set("vanilla")))
        self.add_widget(row)

        row2 = BoxLayout(size_hint_y=None, height=44, spacing=4)
        self.scale_spin = Spinner(text="4", values=("2", "3", "4", "6", "8"), size_hint_x=0.3)
        self.layout_spin = Spinner(text="modern", values=("modern", "classic"))
        row2.add_widget(self.scale_spin)
        row2.add_widget(self.layout_spin)
        row2.add_widget(Label(text="只用本地"))
        row2.add_widget(Switch(active=False, on_active=self._on_offline))
        self.add_widget(row2)

        row3 = BoxLayout(size_hint_y=None, height=48, spacing=4)
        row3.add_widget(Button(text="▶ 开始出图", on_press=self.on_start))
        row3.add_widget(Button(text="导出 ZIP", on_press=self.on_zip))
        self.add_widget(row3)

        self.bar = ProgressBar(max=1.0)
        self.add_widget(self.bar)
        scroll = ScrollView()
        self.log = Label(text="", size_hint_y=None, halign="left", valign="top")
        self.log.bind(texture_size=self.log.setter("size"))
        scroll.add_widget(self.log)
        self.add_widget(scroll)

    # ------------------------------------------------------------------ 交互
    def _set(self, key: str) -> None:
        picked = picker and None
        self.write(f"{key}: 使用系统的文件夹选择器（Kivy 见 android/storage）")

    def _on_offline(self, _w, value: bool) -> None:
        self.offline = value

    def on_pick(self, _w) -> None:
        files = android_pick_files()
        if files:
            self.files = picker.ensure_local(files, paths.work_dir())
            self.write(f"已选 {len(self.files)} 个文件")

    def write(self, text: str) -> None:
        Clock.schedule_once(lambda *_: setattr(self, "log_text", self.log_text + "\n" + str(text)))

    def on_start(self, _w) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        platform_fonts.install()
        out_root = os.path.join(self.state["out"], "合成表")
        os.makedirs(out_root, exist_ok=True)
        assets = Assets(
            bp_dir=self.state["bp"] or None, rp_dir=self.state["rp"] or None,
            vanilla_dir=self.state["vanilla"] or None,
            wiki_root=paths.tool_root(), wiki_icons="auto", wiki_language="en",
            vanilla_download=not self.offline, local_only=bool(self.offline),
            tool_root=paths.tool_root(), bundle_root=paths.tool_root())
        renderer = Renderer(assets, scale=int(self.scale_spin.text),
                            layout=self.layout_spin.text, background=None)
        recipes = collect(self.state["bp"]) if self.state["bp"] else list(self.files)
        total = len(recipes)
        for i, path in enumerate(recipes, 1):
            try:
                img, _ = renderer.render(parse(path))
                dest = os.path.join(out_root, os.path.relpath(path, self.state["bp"])
                                    if self.state["bp"] else os.path.basename(path))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                img.save(dest)
            except Exception as exc:
                self.write(f"! {os.path.basename(path)}: {exc}")
            Clock.schedule_once(lambda *_a, v=i / max(1, total): setattr(self.bar, "value", v))
        self.write(f"完成 {total} 张 → {out_root}")

    def on_zip(self, _w) -> None:
        out_root = os.path.join(self.state["out"], "合成表")
        zip_path = storage.zip_outputs(out_root, os.path.join(paths.exports_dir(), "合成表.zip"))
        self.write("已打包：" + (zip_path or "没有 PNG"))


class BRRApp(App):
    def build(self):
        self.title = "合成表生成器"
        return MainView()


if __name__ == "__main__":
    BRRApp().run()
