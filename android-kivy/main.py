"""合成表生成器 · Android（Kivy + Buildozer）

界面层。核心渲染逻辑与桌面版共用同一份代码（mcrender/）。

文件/目录选择已改为**内置浏览器**（platform_layer/browser.py）：
Android 的 SAF 选择器在部分 ROM（realme/OPPO 等）会黑屏、返回键退出 App、
只能选单文件 —— 拿到「所有文件访问权限」后用 os.listdir 自己浏览即可，
不跳 Activity、不碰 SAF，稳定可控。
"""
from __future__ import annotations

import os
import threading
import traceback

# ---------------------------------------------------------------------------
# Kivy 默认字体不含中文 → 界面会显示成方框。注册随包字体必须在建控件之前。
import os as _os


def _install_ui_font() -> str:
    try:
        from kivy.core.text import DEFAULT_FONT, LabelBase
    except Exception:
        return ""
    here = _os.path.dirname(_os.path.abspath(__file__))
    for name in ("NotoSansSC-Regular.ttf", "NotoSansSC-Regular.otf"):
        path = _os.path.join(here, "fonts", name)
        if _os.path.isfile(path):
            LabelBase.register(DEFAULT_FONT, fn_regular=path)
            return path
    return ""


UI_FONT = _install_ui_font()

from kivy.app import App                                    # noqa: E402
from kivy.clock import Clock                                # noqa: E402
from kivy.metrics import dp                                 # noqa: E402
from kivy.uix.boxlayout import BoxLayout                    # noqa: E402
from kivy.uix.button import Button                          # noqa: E402
from kivy.uix.label import Label                            # noqa: E402
from kivy.uix.progressbar import ProgressBar                # noqa: E402
from kivy.uix.spinner import Spinner                        # noqa: E402
from kivy.uix.switch import Switch                          # noqa: E402
from kivy.uix.textinput import TextInput                    # noqa: E402

from platform_layer import browser as browser_mod           # noqa: E402
from platform_layer import crashlog, paths as p_paths, perm, picking, storage  # noqa: E402

ARCHIVE_EXT = (".zip", ".mcaddon", ".mcpack", ".mcworld", ".mcproject")


class MainView(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(6), spacing=dp(4), **kw)
        self.state = {
            "bp": "", "rp": "", "vanilla": "", "out": "", "files": [],
            "offline": False, "zip": "", "scale": "4", "layout": "modern",
        }
        self._build()
        if not perm.has_all_files() and not perm.can_read_public():
            Clock.schedule_once(lambda *_: self._ask_permission(), 1.0)

    # -------------------------------------------------------------------- UI
    def _btn(self, text, cb, **kw):
        b = Button(text=text, size_hint_y=None, height=dp(44), font_size=dp(12), **kw)
        b.bind(on_release=cb)
        return b

    def _row(self, *widgets, height=46):
        row = BoxLayout(size_hint_y=None, height=dp(height), spacing=dp(4))
        for w in widgets:
            row.add_widget(w)
        return row

    def _build(self) -> None:
        self.add_widget(Label(text="合成表生成器", size_hint_y=None, height=dp(32),
                              bold=True))
        self.perm_btn = self._btn("① 授予「所有文件访问」权限", self._ask_permission)
        self.add_widget(self.perm_btn)

        self.add_widget(self._row(
            self._btn("选配方/压缩包", lambda *_: self._pick("files")),
            self._btn("选 BP", lambda *_: self._pick("bp")),
            self._btn("选 RP", lambda *_: self._pick("rp")),
        ))
        self.add_widget(self._row(
            self._btn("选原版包(zip)", lambda *_: self._pick("vanilla")),
            self._btn("补全原版资源", self.on_sync),
        ))
        self.add_widget(self._row(
            Label(text="缩放", size_hint_x=None, width=dp(44)),
            Spinner(text="4", values=("2", "3", "4", "6", "8"), size_hint_x=None,
                    width=dp(70), on_text=lambda _s, t: self.state.update(scale=t)),
            Label(text="版式", size_hint_x=None, width=dp(44)),
            Spinner(text="modern", values=("modern", "classic"),
                    on_text=lambda _s, t: self.state.update(layout=t)),
        ))
        self.add_widget(self._row(
            Label(text="只用本地(不联网)", size_hint_x=None, width=dp(140)),
            Switch(active=False,
                   on_active=lambda _w, v: self.state.update(offline=bool(v))),
            self._btn("选择出图目录", lambda *_: self._pick("out")),
        ))
        self.add_widget(self._row(
            self._btn("▶ 开始出图", self.on_start),
            self._btn("导出 ZIP", self.on_zip),
            self._btn("分享 ZIP", self.on_share),
        ))
        self.bar = ProgressBar(max=1.0, size_hint_y=None, height=dp(12))
        self.add_widget(self.bar)
        self.status = Label(text="", size_hint_y=None, height=dp(30), font_size=dp(11))
        self.add_widget(self.status)
        self.log = TextInput(text="", readonly=True, font_size=dp(11))
        self.add_widget(self.log)
        self._msg("就绪。先点①授权，再用上面的按钮选文件/文件夹。")
        self._msg("出图会直接写你选的真实目录（其下建「合成表」）。")

    # ------------------------------------------------------------------ 基础
    def _msg(self, text: str) -> None:
        line = str(text)
        Clock.schedule_once(
            lambda *_: setattr(self.log, "text", (self.log.text + "\n" + line).strip()))

    def _ask_permission(self, *_a) -> None:
        if perm.has_all_files():
            self.perm_btn.text = "① 已获得所有文件访问权限 ✓"
            self._msg("权限已就绪，可以浏览文件了。")
            return
        self._msg("请在系统页面允许「管理所有文件」，返回后重新打开 App。")
        perm.request_all_files()

    # ------------------------------------------------------------------ 选择
    def _start_dir(self) -> str:
        for cand in ("/sdcard/Download", "/sdcard/Documents", "/sdcard"):
            if os.path.isdir(cand):
                return cand
        return "/sdcard"

    def _pick(self, key: str) -> None:
        mode = "dir" if key in ("bp", "rp", "out") else "file"
        title = {"bp": "选择行为包 BP 文件夹", "rp": "选择资源包 RP 文件夹",
                 "out": "选择出图目录", "vanilla": "选择原版包 zip",
                 "files": "选择配方 / 压缩包"}.get(key, "选择")

        def done(path: str) -> None:
            if not path:
                return
            if key == "files":
                self.state["files"] = [path]
                self._msg("已选：" + os.path.basename(path))
            else:
                self.state[key] = path
                self._msg(f"{key}: {path}")
                if key == "vanilla":
                    self.state["offline"] = True
                    self._msg("已切到本地模式（不再联网）")

        kwargs = {"start": self._start_dir(), "mode": mode, "on_pick": done,
                  "title": title}
        if key == "files":
            kwargs["filter_ext"] = (".json",) + ARCHIVE_EXT
        elif key == "vanilla":
            kwargs["filter_ext"] = ARCHIVE_EXT
        browser_mod.FileBrowser(**kwargs).open()

    # ------------------------------------------------------------------ 出图
    def on_start(self, *_a) -> None:
        self.bar.value = 0
        threading.Thread(target=self._render, daemon=True).start()

    def _collect(self) -> list[str]:
        from mcrender.recipes import collect
        st = self.state
        out: list[str] = []
        for path in st["files"]:
            if os.path.isdir(path):
                out += collect(path)
            elif path.lower().endswith(ARCHIVE_EXT):
                out += picking.unpack_recipes(path, p_paths.work_dir())
            elif path.lower().endswith(".json"):
                out.append(path)
        if not out and st["bp"] and os.path.isdir(st["bp"]):
            out = collect(st["bp"])
        return sorted(dict.fromkeys(out))

    def _render(self) -> None:
        try:
            from mcrender.assets import Assets
            from mcrender.recipes import parse
            from mcrender.render import Renderer

            from platform_layer import fonts as p_fonts
            p_fonts.install()

            st = self.state
            if not st["out"]:
                self._msg("请先点「选择出图目录」")
                return
            out_root = os.path.join(st["out"], "合成表")
            os.makedirs(out_root, exist_ok=True)

            recipes = self._collect()
            if not recipes:
                self._msg("没找到配方：选一个 .mcaddon/.zip，或选 BP 文件夹")
                return
            self._msg(f"开始出图，共 {len(recipes)} 条 → {out_root}")

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
                    rec = parse(path)
                    if rec is None or getattr(rec, "kind", "unknown") == "unknown":
                        continue
                    img, _lay = renderer.render(rec)
                    dest = os.path.join(out_root, self._relname(path))
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    img.save(dest)
                    done += 1
                except Exception as exc:
                    failed += 1
                    if failed <= 5:
                        self._msg(f"! {os.path.basename(path)}: {exc}")
                Clock.schedule_once(
                    lambda *_a, v=i / max(1, len(recipes)): setattr(self.bar, "value", v))
            for w in renderer.warnings[:5]:
                self._msg("! " + str(w))
            self._msg(f"完成 {done}/{len(recipes)}，失败 {failed}")
            self._msg("输出：" + out_root)
        except Exception as exc:
            crashlog.report("渲染失败", exc)

    def _relname(self, path: str) -> str:
        st = self.state
        for base in (st["bp"], st["out"], *(f for f in st["files"] if os.path.isdir(f))):
            if base and path.startswith(base):
                return os.path.relpath(path, base)
        return os.path.basename(path)

    # -------------------------------------------------------- 补全原版资源
    def on_sync(self, *_a) -> None:
        def job():
            try:
                from mcrender.vanilla import VanillaSource
                src = VanillaSource(
                    local_dirs=[p_paths.tool_root()],
                    cache_dir=os.path.join(p_paths.tool_root(), "vanilla_cache"),
                    allow_download=True, log=self._msg)
                rep = src.sync_all(log=self._msg)
                self._msg(f"补全完成：清单 {rep.get('listed', 0)}，"
                          f"新下载 {rep.get('fetched', 0)}，失败 {rep.get('failed', 0)}")
            except Exception as exc:
                crashlog.report("补全失败", exc)
        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------------------ 导出/分享
    def on_zip(self, *_a) -> None:
        def job():
            st = self.state
            if not st["out"]:
                self._msg("还没有输出目录")
                return
            out_root = os.path.join(st["out"], "合成表")
            if not os.path.isdir(out_root):
                self._msg("还没有出图")
                return
            zpath = storage.zip_outputs(out_root, os.path.join(st["out"], "合成表.zip"))
            self.state["zip"] = zpath
            self._msg("已打包：" + (zpath or "没有 PNG"))
        threading.Thread(target=job, daemon=True).start()

    def on_share(self, *_a) -> None:
        if not self.state.get("zip"):
            self.on_zip()
            Clock.schedule_once(lambda *_: self._share_later(), 2.0)
            return
        self._do_share()

    def _share_later(self) -> None:
        if self.state.get("zip"):
            self._do_share()

    def _do_share(self) -> None:
        ok = storage.share(self.state.get("zip", ""))
        self._msg("已调起系统分享" if ok
                  else "分享不可用，文件在：" + self.state.get("zip", ""))


class BRRApp(App):
    def build(self):
        self.title = "合成表生成器"
        view = MainView()
        crashlog.install(view)
        return view


if __name__ == "__main__":
    BRRApp().run()
