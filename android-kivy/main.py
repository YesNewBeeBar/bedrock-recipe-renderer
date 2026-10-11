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
APP_VERSION = "1.0.5"          # 界面会显示，用来确认手机上跑的是哪一版


class MainView(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(6), spacing=dp(4), **kw)
        self.state = {
            "bp": "", "rp": "", "vanilla": "", "out": "", "files": [],
            # 默认离线：日志证明 offline=False 时会去联网，手机上每条都卡到超时
            "offline": True, "zip": "", "scale": "4", "layout": "modern",
        }
        self._diag_lines: list[str] = []
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
        self.add_widget(Label(text=f"合成表生成器 v{APP_VERSION}", size_hint_y=None,
                              height=dp(32), bold=True))
        self.perm_btn = self._btn("① 授予「所有文件访问」权限", self._ask_permission)
        self.add_widget(self.perm_btn)

        self.add_widget(self._row(
            self._btn("选配方/压缩包", lambda *_: self._pick("files")),
            self._btn("选 BP", lambda *_: self._pick("bp")),
            self._btn("选 RP", lambda *_: self._pick("rp")),
        ))
        self.add_widget(self._row(
            self._btn("选原版包(zip)", lambda *_: self._pick("vanilla")),
            self._btn("内置原版素材 ✓", lambda *_: self._msg(
                "原版素材已随 App 内置，无需下载；只有想用别的版本时才点左边的按钮。")),
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
            # 默认打开：手机上网易超时，离线模式才快（要补全素材时再关掉它）
            Switch(active=True,
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
        """诊断：既写界面日志，也追加到「出图目录/合成表诊断.log」，方便直接发出来。"""
        line = str(text)
        self._msg(line)
        self._diag_lines.append(line)
        path = self.state.get("out")
        if path and os.path.isdir(path):
            try:
                with open(os.path.join(path, "合成表诊断.log"), "a",
                          encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass

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
        bps, rps = [], []
        for base, _dirs, files in os.walk(root):
            if "manifest.json" not in files:
                continue
            has_bp = any(os.path.isdir(os.path.join(base, d)) for d in
                         ("recipes", "entities", "loot_tables", "scripts",
                          "behavior_packs"))
            has_rp = os.path.isdir(os.path.join(base, "textures"))
            if has_bp and not has_rp:
                bps.append(base)
            elif has_rp and not has_bp:
                rps.append(base)
            elif has_bp and has_rp:
                bps.append(base)
                rps.append(base)
        if not bps:                                  # 没有 manifest 就退回整个解包目录
            bps = [root]
        self._diag(f"解包 {os.path.basename(archive)}（{size_mb:.1f} MB）"
                   f"→ 落到 {root}，文件 {total} 个，BP {len(bps)} 个，RP {len(rps)} 个")
        if rps and not self.state.get("rp"):
            self.state["rp"] = rps[0]
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
            out_root = os.path.join(st["out"], "合成表")
            os.makedirs(out_root, exist_ok=True)

            import time as _time
            t0 = _time.time()
            self._diag(f"===== v{APP_VERSION} 出图开始 =====")
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
                bp_dir=st["bp"] or None, rp_dir=st["rp"] or None,
                vanilla_dir=vanilla_dir,
                # 离线时连 Wiki 图标也别去查：手机上每次查询都会卡到超时
                wiki_root=p_paths.tool_root(),
                wiki_icons="off" if offline else "auto", wiki_language="en",
                vanilla_download=not offline, local_only=offline,
                tool_root=p_paths.tool_root(), bundle_root=p_paths.tool_root())
            renderer = Renderer(assets, scale=int(st.get("scale", 4)),
                                layout=st.get("layout", "modern"), background=None)

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
        self.title = "合成表生成器"
        view = MainView()
        crashlog.install(view)
        return view


if __name__ == "__main__":
    BRRApp().run()
