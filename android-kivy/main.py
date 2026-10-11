"""合成表生成器 · Android（Kivy + Buildozer）

与桌面版共用同一份核心渲染代码（mcrender/）。本文件只做：
选输入 → 调核心 → 报进度 → 导出。

Buildozer 入口：main.py（本文件）。
"""
from __future__ import annotations

import os
import threading
import traceback


# ---------------------------------------------------------------------------
# Kivy 默认字体不含中文 → 界面上的按钮/标签会显示成方框。
# 这里把随包字体注册为 Kivy 的默认字体（必须在任何控件创建之前执行）。
import os as _os

def _install_ui_font() -> str:
    from kivy.core.text import LabelBase, DEFAULT_FONT
    here = _os.path.dirname(_os.path.abspath(__file__))
    for name in ("NotoSansSC-Regular.ttf", "NotoSansSC-Regular.otf"):
        path = _os.path.join(here, "fonts", name)
        if _os.path.isfile(path):
            LabelBase.register(DEFAULT_FONT, fn_regular=path)
            return path
    return ""

UI_FONT = _install_ui_font()

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.switch import Switch
from kivy.uix.textinput import TextInput

from platform_layer import fonts as p_fonts
from platform_layer import net as p_net
from platform_layer import paths as p_paths
from platform_layer import androidfs, picking, storage


class MainView(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(6), spacing=dp(4), **kw)
        self.state = {
            "bp": "", "rp": "", "vanilla": "", "out": p_paths.default_output_dir(),
            "files": [], "offline": False, "zip": "", "out_uri": "",
        }
        self._build()

    # ------------------------------------------------------------------ UI
    def _btn(self, text, cb, **kw):
        b = Button(text=text, size_hint_y=None, height=dp(44), **kw)
        b.bind(on_release=cb)
        return b

    def _row(self, *widgets):
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(4))
        for w in widgets:
            row.add_widget(w)
        return row

    def _build(self) -> None:
        self.add_widget(Label(text="合成表生成器", size_hint_y=None, height=dp(34),
                              bold=True))
        self.add_widget(self._row(
            self._btn("选配方/压缩包", self.on_pick_files),
            self._btn("选 BP", lambda *_: self._pick_dir("bp")),
            self._btn("选 RP", lambda *_: self._pick_dir("rp")),
        ))
        self.add_widget(self._row(
            self._btn("选原版包(zip)", self.on_pick_vanilla),
            self._btn("补全原版资源", self.on_sync),
        ))
        self.add_widget(self._row(
            Label(text="缩放", size_hint_x=None, width=dp(44)),
            Spinner(text="4", values=("2", "3", "4", "6", "8"), size_hint_x=None,
                    width=dp(70), on_text=self._set_scale),
            Label(text="版式", size_hint_x=None, width=dp(44)),
            Spinner(text="modern", values=("modern", "classic"), on_text=self._set_layout),
        ))
        self.add_widget(self._row(
            Label(text="只用本地(不联网)", size_hint_x=None, width=dp(150)),
            Switch(active=False, on_active=self._set_offline),
            self._btn("选择出图目录", self.on_pick_out),
        ))
        self.add_widget(self._row(
            self._btn("▶ 开始出图", self.on_start),
            self._btn("导出 ZIP", self.on_zip),
            self._btn("分享 ZIP", self.on_share),
        ))
        self.bar = ProgressBar(max=1.0, size_hint_y=None, height=dp(14))
        self.add_widget(self.bar)
        self.log = TextInput(text="", readonly=True, size_hint_y=0.45,
                             font_size=dp(11), background_color=(0.10, 0.10, 0.12, 1))
        self.add_widget(self.log)
        self.write("就绪。先选配方（.json / .mcaddon / .zip / 整个 BP），再点开始出图")
        self.write("输出目录: " + self.state["out"])

    # --------------------------------------------------------------- 状态
    def _set_scale(self, _s, text):
        self.state["scale"] = text

    def _set_layout(self, _s, text):
        self.state["layout"] = text

    def _set_offline(self, _w, value):
        self.state["offline"] = bool(value)

    def write(self, text: str) -> None:
        line = str(text)
        Clock.schedule_once(lambda *_: setattr(self.log, "text",
                                              (self.log.text + "\n" + line).strip()))

    def _progress(self, value: float) -> None:
        Clock.schedule_once(lambda *_: setattr(self.bar, "value", float(value)))

    # ------------------------------------------------------------- 选择器
    # Android 的 SAF 选择器**必须在主线程**调用（startActivityForResult 不允许从子线程调），
    # 所以这三个回调不再包后台线程；只有渲染才放线程里。
    @mainthread
    def on_pick_files(self, *_a) -> None:
        picked = picking.pick_files(multiple=True)
        if picked:
            self.state["files"] = picked
            self.write(f"已选 {len(picked)} 个文件")
            for p in picked[:3]:
                self.write("  " + os.path.basename(p))
        else:
            self.write("未选择文件（若点了没反应，说明选择器被系统拦下）")

    @mainthread
    def _pick_dir(self, key: str) -> None:
        """BP/RP 必须是文件夹：用 SAF 目录选择器，再把内容导入 App 私有目录。"""
        title = "选择行为包 BP 文件夹" if key == "bp" else "选择资源包 RP 文件夹"
        self.write(f"请选择 {key.upper()} 文件夹…")
        uri = androidfs.pick_tree(title)
        if not uri:
            self.write(f"未选择 {key.upper()} 文件夹")
            return
        dest = os.path.join(p_paths.data_dir(), "packs", key)
        self.write("正在导入文件夹内容…")
        n = androidfs.import_tree(uri, dest)
        if n:
            self.state[key] = dest
            self.write(f"{key.upper()} 已导入 {n} 个文件 → {dest}")
        else:
            self.write(f"{key.upper()} 导入失败（目录为空或权限被拒）")

    @mainthread
    def on_pick_out(self, *_a) -> None:
        """选择出图目录（写回用户选的文件夹，而不是只能待在私有目录）。"""
        self.write("请选择出图目录…")
        uri = androidfs.pick_tree("选择出图目录")
        if uri:
            self.state["out_uri"] = uri
            self.write("出图目录已设置（出图后点导出会写入该目录）")
        else:
            self.write("未选择出图目录")

    @mainthread
    def on_pick_vanilla(self, *_a) -> None:
        picked = picking.pick_files(multiple=False)
        if picked:
            self.state["vanilla"] = picked[0]
            self.state["offline"] = True
            self.write("原版包: " + picked[0] + "（已自动切到本地模式）")
        else:
            self.write("未选择原版包")

    # --------------------------------------------------------------- 出图
    def on_start(self, *_a) -> None:
        self.bar.value = 0
        threading.Thread(target=self._render, daemon=True).start()

    def _render(self) -> None:
        try:
            p_fonts.install()
            p_net.prepare_tls()
            from mcrender.assets import Assets
            from mcrender.recipes import collect, parse
            from mcrender.render import Renderer

            st = self.state
            out_root = os.path.join(st["out"], "合成表")
            os.makedirs(out_root, exist_ok=True)

            recipes = self._collect()
            if not recipes:
                self.write("没有找到配方：请先选文件或 BP")
                return
            self.write(f"开始出图，共 {len(recipes)} 条 → {out_root}")

            assets = Assets(
                bp_dir=st["bp"] or None, rp_dir=st["rp"] or None,
                vanilla_dir=st["vanilla"] or None,
                wiki_root=p_paths.tool_root(), wiki_icons="auto", wiki_language="en",
                vanilla_download=not st["offline"], local_only=bool(st["offline"]),
                tool_root=p_paths.tool_root(), bundle_root=p_paths.tool_root())
            renderer = Renderer(assets, scale=int(st.get("scale", 4)),
                                layout=st.get("layout", "modern"), background=None)

            done = failed = 0
            for i, path in enumerate(recipes, 1):
                try:
                    img, _lay = renderer.render(parse(path))
                    rel = self._relname(path)
                    dest = os.path.join(out_root, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    img.save(dest)
                    done += 1
                except Exception as exc:
                    failed += 1
                    if failed <= 5:
                        self.write(f"! {os.path.basename(path)}: {exc}")
                self._progress(i / len(recipes))
            for w in renderer.warnings[:5]:
                self.write("! " + w)
            self.write(f"完成 {done}/{len(recipes)}，失败 {failed}")
            self.write("输出目录: " + out_root)
        except Exception:
            self.write("失败:\n" + traceback.format_exc(limit=4))

    def _collect(self) -> list[str]:
        from mcrender.recipes import collect
        st = self.state
        out: list[str] = []
        for p in st["files"]:
            if os.path.isdir(p):
                out += collect(p)
            elif p.lower().endswith((".zip", ".mcaddon", ".mcpack", ".mcworld")):
                out += picking.unpack_recipes(p, p_paths.work_dir())
            elif p.lower().endswith(".json"):
                out.append(p)
        if not out and st["bp"] and os.path.isdir(st["bp"]):
            out = collect(st["bp"])
        return sorted(dict.fromkeys(out))

    def _relname(self, path: str) -> str:
        st = self.state
        for base in (st["bp"], *(p for p in st["files"] if os.path.isdir(p))):
            if base and path.startswith(base):
                return os.path.relpath(path, base)
        return os.path.basename(path)

    def on_sync(self, *_a) -> None:
        def job():
            try:
                from mcrender.vanilla import VanillaSource
                src = VanillaSource(
                    local_dirs=[p_paths.tool_root()],
                    cache_dir=os.path.join(p_paths.tool_root(), "vanilla_cache"),
                    allow_download=True, log=self.write)
                report = src.sync_all(log=self.write)
                self.write(f"补全完成：清单 {report.get('listed', 0)}，"
                           f"新下载 {report.get('fetched', 0)}，失败 {report.get('failed', 0)}")
                if not report.get("failed"):
                    self.write("已可完全离线运行")
            except Exception as exc:
                self.write("补全失败: " + str(exc))
        threading.Thread(target=job, daemon=True).start()

    # --------------------------------------------------------------- 导出
    def on_zip(self, *_a) -> None:
        def job():
            out_root = os.path.join(self.state["out"], "合成表")
            if not os.path.isdir(out_root):
                self.write("还没有输出目录")
                return
            dest = os.path.join(p_paths.exports_dir(), "合成表.zip")
            zpath = storage.zip_outputs(out_root, dest)
            self.state["zip"] = zpath
            self.write("已打包: " + (zpath or "没有 PNG"))
            uri = self.state.get("out_uri", "")
            if uri:
                msg = androidfs.export_tree(uri, out_root)
                self.write(msg or "写入所选目录失败")
        threading.Thread(target=job, daemon=True).start()

    def on_share(self, *_a) -> None:
        if not self.state.get("zip"):
            self.on_zip()
            return
        ok = storage.share(self.state["zip"])
        self.write("已调起系统分享" if ok else "分享不可用，文件在: " + self.state["zip"])


class BRRApp(App):
    def build(self):
        self.title = "合成表生成器"
        return MainView()


if __name__ == "__main__":
    BRRApp().run()
