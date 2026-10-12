"""合成表生成器 · Android（Kivy + Buildozer）

界面层。核心渲染逻辑与桌面版共用同一份代码（mcrender/）。

文件/目录选择已改为**内置浏览器**（platform_layer/browser.py）：
Android 的 SAF 选择器在部分 ROM（realme/OPPO 等）会黑屏、返回键退出 App、
只能选单文件 —— 拿到「所有文件访问权限」后用 os.listdir 自己浏览即可，
不跳 Activity、不碰 SAF，稳定可控。
"""
from __future__ import annotations

import os as _os_boot
import traceback as _tb_boot


def _boot(step: str) -> None:
    """开机路标：把"走到哪一步"写进 crash.log。

    闪退且无日志时，这几行是唯一能定位的线索（之前完全没有）。
    """
    for path in ("/storage/emulated/0/Android/data/com.yesnewbeebar."
                 "bedrockreciperenderer/files/crash.log",
                 _os_boot.path.join(_os_boot.path.dirname(
                     _os_boot.path.abspath(__file__)), "crash.log")):
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write("[boot] " + step + chr(10))
            return
        except Exception:
            continue
    try:
        _tb_boot.print_exc()
    except Exception:
        pass


_boot("1 开始导入 main.py")

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
_boot("2 字体与 Kivy 导入完成")

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
from platform_layer import remember
from platform_layer import crashlog, paths as p_paths, perm, picking, storage  # noqa: E402

ARCHIVE_EXT = (".zip", ".mcaddon", ".mcpack", ".mcworld", ".mcproject")
APP_VERSION = "1.2.6"          # 界面会显示，用来确认手机上跑的是哪一版


# ---------------------------------------------------------------- 外观（简洁现代）
# 明/暗两套配色；按钮文字恒为白色（在强调色底上永远清晰）
LIGHT = {
    "bg": (0.97, 0.97, 0.98, 1), "fg": (0, 0, 0, 1),               # 标题：纯黑
    "dim": (0, 0, 0, 1), "panel": (1, 1, 1, 1),                     # 操作区文字：纯黑
    "accent": (0.20, 0.51, 0.96, 1),
}
DARK = {
    "bg": (0.09, 0.10, 0.12, 1), "fg": (0.93, 0.94, 0.96, 1),
    "dim": (0.72, 0.74, 0.78, 1), "panel": (0.16, 0.17, 0.20, 1),
    "accent": (0.16, 0.38, 0.78, 1),        # 暗色模式：蓝再暗一点
}
THEME = {"dark": False}


def theme_colors():
    return DARK if THEME["dark"] else LIGHT


def device_is_dark() -> bool:
    """设备当前是不是深色（Android Configuration.uiMode）。拿不到就当浅色。"""
    try:
        from jnius import autoclass
        conf = autoclass("org.kivy.android.PythonActivity").mActivity             .getResources().getConfiguration()
        return bool(conf.uiMode & 0x30 == 0x20)      # UI_MODE_NIGHT_YES
    except Exception:
        return False


def initial_dark(state: dict) -> bool:
    """**只有第一次启动**（没有记忆）才跟随设备；之后一律用用户的设置。"""
    if "dark" in state and isinstance(state["dark"], bool):
        return state["dark"]
    dark = device_is_dark()
    state["dark"] = dark
    return dark


def _round(widget, radius=10, color=(1, 1, 1, 1)):
    """给控件加圆角背景（默认按钮是方角灰块，这里统一成现代扁平样式）。"""
    from kivy.graphics import Color, RoundedRectangle
    with widget.canvas.before:
        Color(*color)
        rect = RoundedRectangle(radius=[dp(radius)])

    def _sync(*_a):
        rect.pos = widget.pos
        rect.size = widget.size

    widget.bind(pos=_sync, size=_sync)
    _sync()
    widget._round_rect = rect
    widget._round_color = widget.canvas.before.children[-1]
    return rect


def apply_theme(root, dark=None):
    """一次遍历刷新样式。切换暗色时重复调用即可（只改颜色，不重建控件）。"""
    from kivy.core.window import Window
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.spinner import Spinner
    from kivy.uix.textinput import TextInput
    if dark is not None:
        THEME["dark"] = bool(dark)
    c = theme_colors()
    Window.clearcolor = c["bg"]

    def walk(w):
        yield w
        for child in getattr(w, "children", []):
            for sub in walk(child):
                yield sub

    for w in walk(root):
        if isinstance(w, Button):
            w.background_normal = ""
            w.background_down = ""
            w.background_color = (0, 0, 0, 0)
            w.color = (1, 1, 1, 1)
            w.bold = True
            if getattr(w, "_round_color", None) is not None:
                w._round_color.rgba = c["accent"]
            else:
                _round(w, 10, c["accent"])
        elif isinstance(w, Spinner):
            w.background_normal = ""
            w.background_color = c["panel"]
            w.color = c["fg"]
        elif isinstance(w, TextInput):
            w.background_normal = ""
            w.background_color = c["panel"]
            w.foreground_color = c["fg"]
            w.cursor_color = c["accent"]
            w.padding = [dp(10), dp(10)]
        elif isinstance(w, Label):
            w.color = c["fg"] if getattr(w, "_is_title", False) else c["dim"]
    return c


class MainView(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(6), spacing=dp(4), **kw)
        self.state = {
            "bp": "", "rp": "", "vanilla": "", "out": "", "files": [],
            "unpack_root": "",
            # 默认离线：日志证明 offline=False 时会去联网，手机上每条都卡到超时
            "offline": True, "zip": "", "scale": "4", "layout": "modern",
        }
        self._diag_lines: list[str] = []
        self._build()
        if not perm.has_all_files() and not perm.can_read_public():
            Clock.schedule_once(lambda *_: self._ask_permission(), 1.0)
        else:
            Clock.schedule_once(lambda *_: self._hide_perm_btn(), 0.3)   # 已有权限就不显示

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
        from kivy.uix.switch import Switch
        # ---- 标题栏：标题 + 右上角暗色开关 ----
        top = self._row()
        try:                                  # 左上角图标（复用 App 自己的 icon.png）
            from kivy.uix.image import Image
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "assets", "icon.png")
            if not os.path.isfile(icon_path):
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")
            if os.path.isfile(icon_path):
                top.add_widget(Image(source=icon_path, size_hint_x=None,
                                     width=dp(28), allow_stretch=True, keep_ratio=True))
        except Exception:
            pass
        title = Label(text="合成表生成器", bold=True,      # 不写版本号（版本进日志）
                      font_size=dp(16), halign="left", valign="middle")
        title.bind(size=lambda w, _v: setattr(w, "text_size", (w.width, None)))
        title._is_title = True
        top.add_widget(title)
        top.add_widget(Label(text="暗色", size_hint_x=None, width=dp(40),
                             font_size=dp(11), halign="right", valign="middle"))
        self.dark_sw = Switch(active=False, size_hint_x=None, width=dp(60))
        self.dark_sw.bind(active=lambda _w, v: self._set_dark(bool(v)))
        top.add_widget(self.dark_sw)
        self.add_widget(top)

        self.perm_btn = self._btn("① 授予「所有文件访问」权限", self._ask_permission)
        self.add_widget(self.perm_btn)

        # ---- 第一排：选择文件 / 出图目录 ----
        self.add_widget(self._row(
            self._btn("选择文件", lambda *_: self._pick("files")),
            self._btn("出图目录", lambda *_: self._pick("out")),
        ))
        # ---- 第二排：BP / RP ----
        self.add_widget(self._row(
            self._btn("选 BP", lambda *_: self._pick("bp")),
            self._btn("选 RP", lambda *_: self._pick("rp")),
        ))
        # ---- 第三排：缩放 / 阴影 ----
        self.add_widget(self._row(
            Label(text="缩放", size_hint_x=None, width=dp(44)),
            Spinner(text="4", values=("2", "3", "4", "6", "8"), size_hint_x=None,
                    width=dp(66), on_text=lambda _s, t: self.state.update(scale=t)),
            Label(text="阴影", size_hint_x=None, width=dp(44)),
            Switch(active=True, size_hint_x=None, width=dp(60),
                   on_active=lambda _w, v: self.state.update(show_counts=bool(v))),
        ))
        # ---- 第四排：使用本地 ----
        self.add_widget(self._row(
            Label(text="使用本地（不联网）", size_hint_x=None, width=dp(150)),
            Switch(active=True, size_hint_x=None, width=dp(60),
                   on_active=lambda _w, v: self.state.update(offline=bool(v))),
        ))
        # ---- 出图 ----
        self.add_widget(self._row(self._btn("▶ 开始出图", self.on_start)))
        # ---- 导出 / 分享 ----
        self.add_widget(self._row(
            self._btn("导出 ZIP", self.on_zip),
            self._btn("分享 ZIP", self.on_share),
        ))
        self.bar = ProgressBar(max=1.0, size_hint_y=None, height=dp(10))
        self.add_widget(self.bar)
        self.status = Label(text="", size_hint_y=None, height=dp(28), font_size=dp(11))
        self.add_widget(self.status)
        self.log = TextInput(text="", readonly=True, font_size=dp(11))
        self.add_widget(self.log)
        self._msg(f"合成表生成器 v{APP_VERSION} 就绪。")
        self._msg("出图会直接写你选的目录（其下建「合成表」）。")

    def _set_dark(self, flag: bool) -> None:
        """切换暗色（只改颜色，不重建控件）。"""
        try:
            apply_theme(self, dark=flag)
            self.state["dark"] = flag
            remember.save(self.state)
        except Exception:
            pass

    # ------------------------------------------------------------------ 基础
    def _msg(self, text: str) -> None:
        line = str(text)
        Clock.schedule_once(
            lambda *_: setattr(self.log, "text", (self.log.text + "\n" + line).strip()))

    def _hide_perm_btn(self) -> None:
        """有权限后把顶部按钮收起来（对象保留，避免别处引用报错）。"""
        try:
            self.perm_btn.height = 0
            self.perm_btn.size_hint_y = None
            self.perm_btn.opacity = 0
            self.perm_btn.disabled = True
        except Exception:
            pass

    def _ask_permission(self, *_a) -> None:
        if perm.has_all_files():
            self.perm_btn.text = "① 已获得所有文件访问权限 ✓"
            self._msg("权限已就绪。")
            self._hide_perm_btn()          # 顶部不再占位
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
        """选择入口：**优先用 Android 官方选择器**，不可用才回退内置浏览器。

        官方接口必须"发起在主线程、结果靠回调"，所以这里用回调式，
        绝不在主线程等待（早先的同步写法会死锁，表现为选了没反应）。
        """
        try:
            from platform_layer import androidfs as a_fs
        except Exception:
            self._browser_pick(key)
            return

        def after_files(got):
            if got is None:                      # 原生弹不出来 → 回退
                self._browser_pick(key)
                return
            if not got:                          # 用户取消：结束，别再弹浏览器
                self._msg("已取消选择")
                return
            self.state["files"] = list(got)
            self._msg(f"已选 {len(got)} 个文件（系统选择器）")
            remember.save(self.state)

        def after_dir(path):
            if path is None:
                self._browser_pick(key)
                return
            if not path:
                self._msg("已取消选择")
                return
            self.state[key] = path
            self._msg(f"{key}: {path}（系统选择器）")
            remember.save(self.state)

        if key == "files":
            a_fs.pick_files_cb(after_files)
        elif key in ("bp", "rp", "out"):
            a_fs.pick_tree_cb(after_dir)
        else:
            self._browser_pick(key)              # vanilla 等仍走浏览器

    def _browser_pick(self, key: str) -> None:
        """内置浏览器（回退用）：只有官方选择器在这台机器上弹不出来时才走这里。"""
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
                remember.save(self.state)
            else:
                self.state[key] = path
                self._msg(f"{key}: {path}")
                remember.save(self.state)          # 记住选择，下次不用再选
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

    def _collect(self):
        """返回**已解析的 Recipe 对象**列表（核心 collect() 的返回类型就是它）。

        逻辑与桌面版一致：解包 → 找带 manifest.json 的包根（BP 出配方、RP 出素材）
        → 对 BP 根递归收集。注意 collect() 内部已经 parse 并过滤，返回值是对象；
        千万不要再把这些对象喂给 parse(path) —— 那样一律变成 kind=unknown。
        """
        from mcrender.recipes import collect, parse
        st = self.state
        out = []
        for path in st["files"]:
            if os.path.isdir(path):
                out += collect(path)
            elif path.lower().endswith(ARCHIVE_EXT):
                bps, rps = self._unpack_packs(path)
                for bp in bps:
                    out += collect(bp)
            elif path.lower().endswith(".json"):
                rec = parse(path)
                if rec is not None:
                    out.append(rec)
        if not out and st["bp"] and os.path.isdir(st["bp"]):
            out = collect(st["bp"])
        seen, uniq = set(), []
        for r in out:
            p = getattr(r, "path", "")
            if p and p not in seen:
                seen.add(p)
                uniq.append(r)
        return uniq

    def _diag(self, text: str) -> None:
        """诊断：写界面日志，并写进「出图目录/合成表/_诊断.log」——
        放在导出目录**里面**，这样导出 zip 里就带着它，直接发我即可。"""
        line = str(text)
        self._msg(line)
        self._diag_lines.append(line)
        base = self.state.get("out")
        if not base or not os.path.isdir(base):
            return
        for sub in (os.path.join("合成表", "_诊断.log"), "合成表诊断.log"):
            try:
                with open(os.path.join(base, sub), "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass

    def _seed_wiki_cache(self) -> int:
        """把随包内置的 wiki 图标缓存并进可写缓存（只补缺失，不动已有）。

        头颅/头、床、旗帜、告示牌、潜影盒、花盆、植物、药水、失水恶魂等，
        桌面端是靠 wiki 图标（= 游戏的库存图标）渲染的；手机离线又没缓存时会退回
        "内置几何体"，画出来与游戏不一致。把缓存随包带上即可与桌面版表现一致。
        """
        import shutil
        here = os.path.dirname(os.path.abspath(__file__))
        src = os.path.join(here, "wiki_cache")
        if not os.path.isdir(src):
            return 0
        dst = os.path.join(p_paths.tool_root(), "wiki_cache")
        copied = 0
        for base, _dirs, files in os.walk(src):
            rel = os.path.relpath(base, src)
            target = dst if rel == "." else os.path.join(dst, rel)
            try:
                os.makedirs(target, exist_ok=True)
            except Exception:
                continue
            for f in files:
                fp = os.path.join(target, f)
                if os.path.exists(fp):
                    continue
                try:
                    shutil.copyfile(os.path.join(base, f), fp)
                    copied += 1
                except Exception:
                    pass
        return copied

    def _unpack_packs(self, archive: str):
        """解包并把里面的 BP / RP 根目录找出来（与桌面版同样的判定方式）。"""
        size_mb = os.path.getsize(archive) / 1048576
        work = p_paths.work_dir()
        self._diag(f"解包目标目录: {work}  可写={os.access(work, os.W_OK)}")
        try:
            root = picking.unpack_archive(archive, work)
        except Exception as exc:
            import traceback as _tb
            self._diag("!! 解包失败: " + "".join(_tb.format_exception_only(type(exc), exc)))
            root = os.path.join(work, "unpack", os.path.basename(archive))
        total = sum(len(fs) for _b, _d, fs in os.walk(root))
        # 与桌面端**同一套**判定：按 manifest 的模块类型分 BP/RP，
        # 并用 find_matching_rp（名字替换 + manifest uuid 依赖）给 BP 配 RP。
        # 不再用"看有没有 textures/ 目录"的启发式 —— 那会让多面方块/自定义模型读不到。
        from mcrender import packs as _packs
        pairs, bps, rps = _packs.scan_packs(root)
        self._diag(f"包识别: BP {len(bps)} 个, RP {len(rps)} 个, 配对 {len(pairs)} 组")
        for _bp, _rp in pairs:
            self._diag("   BP=" + (os.path.basename(_bp) if _bp else "无")
                       + " → RP=" + (os.path.basename(_rp) if _rp else "（没配上）"))
        if pairs:
            # 优先取"配上了 RP"的那一组；BP/RP 都按核心给的精确路径传下去
            _bp, _rp = next(((b, r) for b, r in pairs if r), pairs[0])
            self.state["bp"] = _bp or ""
            self.state["rp"] = _rp or ""
            self._msg("已自动使用包内资源包 RP：" + os.path.basename(rps[0]))
        return bps, rps

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
            # 输出结构：<选的目录>/合成表/<附加包名>/… —— 与桌面端同一套核心规则
            from mcrender import output as output_mod
            source = (st["files"][0] if st["files"] else st["bp"]) or ""
            pack = output_mod.pack_folder_name(source) if source else ""
            out_root = output_mod.output_dir_for(st["out"], pack)
            self._diag(f"输出目录: {out_root}（附加包名 {pack or '未识别'}）")

            import time as _time
            t0 = _time.time()
            seeded = self._seed_wiki_cache()
            self._diag(f"===== v{APP_VERSION} 出图开始 =====")
            self._diag(f"内置 wiki 图标缓存并入 {seeded} 个文件")
            self._diag(f"选择: files={st['files']} bp={st['bp']} rp={st['rp']} "
                       f"vanilla={st['vanilla']} offline={st['offline']}")
            self._diag(f"输出目录: {out_root} 可写={os.access(out_root, os.W_OK)}")

            recipes = self._collect()
            if not recipes:
                self._msg("没找到配方：选一个 .mcaddon/.zip，或选 BP 文件夹")
                self._diag("!! 没找到配方，流程结束")
                return
            self._diag(f"共识别 {len(recipes)} 条配方（耗时 {_time.time()-t0:.1f}s）")
            for r in recipes[:3]:
                self._msg("  · " + os.path.basename(getattr(r, "path", "?")))

            offline = bool(st["offline"])
            # 原版素材随 APK 内置（2121 个贴图，1.5 MB）：离线也能画出木棍、熟肉等原版物品。
            # 用户若自己选了原版包，就用他的。
            bundled_vanilla = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "vanilla")
            vanilla_dir = st["vanilla"] or (bundled_vanilla
                                            if os.path.isdir(bundled_vanilla) else None)
            self._diag(f"原版素材: {vanilla_dir or '（无）'}")
            assets = Assets(
                bp_dir=st["bp"] or None,
                rp_dir=st["rp"] or None,
                vanilla_dir=vanilla_dir,
                # 与桌面端保持一致：图标模式恒为 auto。
                # 离线时由 local_only=True 保证"只读本地缓存、不联网"，
                # 关掉 auto 会让药水等只能用自绘颜色（用户反馈过）。
                wiki_root=p_paths.tool_root(),
                wiki_icons="auto", wiki_language="en",
                vanilla_download=not offline, local_only=offline,
                tool_root=p_paths.tool_root(), bundle_root=p_paths.tool_root())
            renderer = Renderer(assets, scale=int(st.get("scale", 4)),
                                layout=st.get("layout", "modern"), background=None)
            # 关键状态：RP 到底读到没有、贴图索引有多少条
            rp_txt = st["rp"] or "（无）"
            self._diag(f"素材状态: item_texture 键 {len(assets.item_texture)} 个, "
                       f"terrain {len(assets.terrain_texture)} 个, blocks {len(assets.blocks)} 个")
            self._diag(f"RP = {rp_txt} | 存在={os.path.isdir(st["rp"]) if st["rp"] else False}")
            if st["rp"]:
                tex_n = sum(len(fs) for _b, _d, fs in os.walk(os.path.join(st["rp"], "textures")))
                self._diag(f"RP 下 textures 文件数: {tex_n}")

            done = failed = skipped = 0
            slow: list[tuple[float, str]] = []
            for i, rec in enumerate(recipes, 1):
                t_rec = _time.time()
                try:
                    if getattr(rec, "kind", "unknown") == "unknown":
                        skipped += 1
                        continue
                    img, _lay = renderer.render(rec)
                    rel = self._relname(rec.path)
                    if not rel.lower().endswith(".png"):
                        rel = os.path.splitext(rel)[0] + ".png"   # 别存成 .json
                    dest = os.path.join(out_root, rel)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    img.save(dest)
                    done += 1
                    # 同标签物品轮播 GIF（与桌面端同一核心逻辑）
                    try:
                        from mcrender import taggif
                        taggif.render_gif(renderer, rec, dest, log=self._diag)
                    except Exception as exc:
                        self._diag(f"   ! GIF 跳过：{exc}")
                except Exception as exc:
                    failed += 1
                    if failed <= 5:
                        self._diag(f"! {os.path.basename(getattr(rec, 'path', '?'))}: {exc}")
                dt = _time.time() - t_rec
                slow.append((dt, os.path.basename(getattr(rec, "path", "?"))))
                if i % 25 == 0 or i == len(recipes):      # 进度落盘，能看出节奏
                    self._diag(f"进度 {i}/{len(recipes)}，已用 {_time.time()-t0:.0f}s")
                Clock.schedule_once(
                    lambda *_a, v=i / max(1, len(recipes)): setattr(self.bar, "value", v))
            for w in renderer.warnings[:5]:
                self._msg("! " + str(w))
            slow.sort(reverse=True)
            self._diag("最慢的 5 条（秒 | 文件名）：" +
                       "；".join(f"{d:.2f}|{n}" for d, n in slow[:5]))
            miss_ids = sorted({str(w).split("for ", 1)[1] for w in renderer.warnings
                               if str(w).startswith("missing texture for ")})
            self._diag(f"缺失纹理 id 共 {len(miss_ids)} 个: {miss_ids[:15]}")
            self._diag(f"完成 {done}/{len(recipes)}，失败 {failed}，跳过 {skipped}，"
                       f"总耗时 {_time.time()-t0:.1f}s")
            self._msg(f"完成 {done}/{len(recipes)}，失败 {failed}，跳过 {skipped}，"
                      f"耗时 {_time.time()-t0:.0f}s")
            self._msg("输出：" + out_root)
            self._msg("诊断日志：" + os.path.join(st["out"], "合成表诊断.log"))
        except Exception as exc:
            self._diag("!! 渲染异常: " + repr(exc))
            crashlog.report("渲染失败", exc)

    def _relname(self, path: str) -> str:
        # 解包目录形如 /…/unpack/<压缩包名>/HiddenYears(BP).zip_x/recipes/a.json
        # 从内层压缩包名开始保留相对路径，避免不同目录同名配方互相覆盖
        marker = os.sep + "unpack" + os.sep
        if marker in path:
            tail = path.split(marker, 1)[1].split(os.sep)[1:]
            if tail:
                return os.path.join(*tail)
        st = self.state
        for base in (st["bp"], st["out"], *(f for f in st["files"] if os.path.isdir(f))):
            if base and path.startswith(base):
                return os.path.relpath(path, base)
        return os.path.basename(path)

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
        _boot("3 进入 build()")
        try:
            used = remember.merge_into(self.state)
            if used:
                self.state.setdefault("_restored", used)
                self._diag("已恢复上次的选择: " + ", ".join(used))   # 出图目录/BP/RP 等
        except Exception:
            pass
        self.title = "合成表生成器"
        # 先装崩溃日志：这样连"界面构建阶段"的异常也能留下记录（之前闪退无日志）
        try:
            crashlog.install(None)
        except Exception:
            pass
        _boot("4 开始构建界面")
        try:
            view = MainView()
        except Exception as exc:                    # 界面构建失败也不闪退
            import traceback as _tb
            crashlog.report("界面构建", exc)
            try:
                crashlog._write_file("界面构建失败:" + chr(10) + _tb.format_exc())
            except Exception:
                pass
            from kivy.uix.boxlayout import BoxLayout as _BL
            from kivy.uix.label import Label as _L
            view = _BL(orientation="vertical", padding=dp(16))
            view.add_widget(_L(text="界面构建失败，已写入 crash.log" + chr(10) + repr(exc)))
        try:
            crashlog.install(view)
        except Exception:
            pass
        _boot("5 界面构建完成")
        dark0 = initial_dark(self.state)          # 首次跟随设备，之后用记忆
        if not self.state.get("_theme_saved"):
            try:
                remember.save(self.state)
                self.state["_theme_saved"] = True
            except Exception:
                pass

        def _paint(_dt=None):
            try:
                apply_theme(view, dark=dark0)
            except Exception as exc:              # 不再静默：写进诊断日志
                self._diag("!! 主题应用失败: " + repr(exc))

        # 控件是边建边出现的 —— 延后多刷几次，保证都覆盖到
        for _d in (0.05, 0.3, 0.9):
            Clock.schedule_once(_paint, _d)
        _boot("6 build() 返回，界面即将显示")
        return view


if __name__ == "__main__":
    BRRApp().run()
