"""合成表生成器 · 桌面端（WinUI 3 / Fluent Design 界面）

界面用 PySide6 + PySide6-Fluent-Widgets 重写；**渲染核心（mcrender/）与业务逻辑
（mcrender_gui.py 里的 Generator / 解包 / 配置）完全复用，没有任何改动**。

相较 tkinter 版的好处：
- 控件是系统级抗锯齿绘制，不再有手绘圆角的毛边
- 明暗主题是整套样式表一次替换，不会出现"切换途中半成品画面"
- 原生拖放（Qt 的 drag&drop），不需要 Windows 消息钩子
- Win11 支持 Mica 云母材质
"""
from __future__ import annotations

import os
import sys
import threading
import traceback
import zipfile

from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from qfluentwidgets import (
    BodyLabel, CaptionLabel, CardWidget, ComboBox, FluentIcon as FIF, HeaderCardWidget,
    InfoBar, InfoBarPosition, LineEdit, MessageBox, PrimaryPushButton, ProgressBar,
    PushButton, SubtitleLabel, SwitchButton, TextEdit, Theme, TitleLabel,
    setTheme, setThemeColor, isDarkTheme,
)

# ---- 复用现有逻辑（核心与业务，均未改动）------------------------------------
from mcrender_app import (
    Generator, app_dir, bundle_dir, find_matching_rp, find_recipes, icon_path,
    is_archive, load_config, pack_kinds, save_config, seed_caches, unpack_archive,
)
import gui_theme as gui_theme
import updater

APP_VERSION = "1.1.1"
BASE = app_dir()

DROP_HINT = "↓  将 [json / .mcaddon / .mcpack / zip / 文件夹] 拖入窗口  ↓"


class Bridge(QObject):
    """工作线程 → 界面的信号桥（Qt 要求 UI 只在主线程动）。"""
    logged = Signal(str)
    progress = Signal(int, int)      # 已完成, 总数
    finished = Signal(int)           # 生成张数
    updateReady = Signal(object)     # 更新检查结果（dict）或异常（str）


class DropCard(CardWidget):
    """拖放区：整块可接收文件，点击也能选文件。"""

    dropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(112)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 18, 16, 18)
        self.title = SubtitleLabel(DROP_HINT, self)
        self.sub = CaptionLabel("拖放就绪 —— 松手即出图（也可以点这里选文件）", self)
        self.sub.setTextColor("#606060", "#c8c8c8")
        lay.addStretch(1)
        lay.addWidget(self.title, 0, Qt.AlignHCenter)
        lay.addWidget(self.sub, 0, Qt.AlignHCenter)
        lay.addStretch(1)

    # --- 原生拖放
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.setBorderRadius(12)

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.clicked.emit()


class PathRow(QWidget):
    """一行：标签 + 输入框 + 选择按钮。"""

    def __init__(self, label: str, value: str, placeholder: str, on_pick, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(10)
        self.label = BodyLabel(label, self)
        self.label.setFixedWidth(74)
        self.edit = LineEdit(self)
        self.edit.setText(value or "")
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.btn = PushButton("选择…", self)
        self.btn.clicked.connect(lambda: on_pick(self))
        lay.addWidget(self.label)
        lay.addWidget(self.edit, 1)
        lay.addWidget(self.btn)

    def value(self) -> str:
        return self.edit.text().strip()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self.bridge = Bridge()
        self.bridge.logged.connect(self._log)
        self.bridge.progress.connect(self._progress)
        self.bridge.finished.connect(self._finished)
        self.bridge.updateReady.connect(self._show_update)
        self.busy = False

        # 普通 QWidget 不会被 Fluent 主题自动上底色 —— 不设的话浅色模式下
        # 窗口仍是系统深色，深色文字就糊在深底上了
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setWindowTitle(f"合成表生成器 v{APP_VERSION}")
        ip = icon_path()
        if ip and os.path.isfile(ip):
            self.setWindowIcon(QIcon(ip))
        self.resize(1040, 820)

        self._build()
        self._restore_theme()

    # ------------------------------------------------------------------ 界面
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ① 顶部：标题 + 副标题 + 主题开关
        head = QHBoxLayout()
        logo = QLabel(self)
        ip = icon_path()
        if ip and os.path.isfile(ip):
            logo.setPixmap(QPixmap(ip).scaled(34, 34, Qt.KeepAspectRatio,
                                              Qt.SmoothTransformation))
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(TitleLabel("合成表生成器", self))
        col.addWidget(CaptionLabel("基岩版配方 → 游戏内界面 PNG", self))
        self.theme_sw = SwitchButton(self)
        self.theme_sw.setChecked(isDarkTheme())
        self.theme_sw.setOnText("深色")
        self.theme_sw.setOffText("浅色")
        self.theme_sw.checkedChanged.connect(self._toggle_theme)
        head.addWidget(logo)
        head.addLayout(col)
        head.addStretch(1)
        head.addWidget(BodyLabel("深色模式", self))
        head.addWidget(self.theme_sw)
        root.addLayout(head)

        # ② 拖放卡
        self.drop = DropCard(self)
        self.drop.dropped.connect(self._on_dropped)
        self.drop.clicked.connect(self.pick_files)
        root.addWidget(self.drop)

        # ③ 路径卡
        paths = CardWidget(self)
        pl = QVBoxLayout(paths)
        pl.setContentsMargins(16, 12, 16, 12)
        pl.setSpacing(6)
        self.row_bp = PathRow("行为包 BP", self.cfg.get("bp", ""),
                              "选择行为包文件夹（含 manifest.json）", self._pick_dir, self)
        self.row_rp = PathRow("资源包 RP", self.cfg.get("rp", ""),
                              "选择资源包文件夹（含 textures/）", self._pick_dir, self)
        self.row_out = PathRow("输出目录", self.cfg.get("out", ""),
                               "选一个目录，图片会放在它下面的「合成表」里", self._pick_dir, self)
        self.row_vanilla = PathRow("原版包", self.cfg.get("vanilla", ""),
                                   "可选：自己指定原版包（留空用内置素材）", self._pick_dir, self)
        self.hint = CaptionLabel("", self)
        for r in (self.row_bp, self.row_rp, self.row_out, self.row_vanilla):
            pl.addWidget(r)
            r.edit.editingFinished.connect(self._save_cfg)
        pl.addWidget(self.hint)
        root.addWidget(paths)

        # ④ 参数卡
        opts = CardWidget(self)
        ol = QHBoxLayout(opts)
        ol.setContentsMargins(16, 10, 16, 10)
        ol.setSpacing(8)
        self.cb_layout = ComboBox(self)
        self.cb_layout.addItems(["modern", "classic"])
        self.cb_layout.setCurrentText(self.cfg.get("layout", "modern"))
        self.cb_scale = ComboBox(self)
        self.cb_scale.addItems(["2", "3", "4", "6", "8"])
        self.cb_scale.setCurrentText(str(self.cfg.get("scale", 4)))
        self.cb_shade = ComboBox(self)
        self.cb_shade.addItems(["vanilla", "reference"])
        self.cb_shade.setCurrentText(self.cfg.get("cube_shading", "vanilla"))
        self.cb_wiki = ComboBox(self)
        self.cb_wiki.addItems(["auto", "always", "never"])
        self.cb_wiki.setCurrentText(self.cfg.get("wiki_icons", "auto"))
        self.sw_local = SwitchButton(self)
        self.sw_local.setChecked(bool(self.cfg.get("local_only", False)))
        self.sw_local.setOnText("开")
        self.sw_local.setOffText("关")
        for w in (BodyLabel("版式", self), self.cb_layout,
                  BodyLabel("缩放", self), self.cb_scale,
                  BodyLabel("方块阴影", self), self.cb_shade,
                  BodyLabel("wiki 图标", self), self.cb_wiki):
            ol.addWidget(w)
        ol.addStretch(1)
        ol.addWidget(BodyLabel("只用本地（不联网）", self))
        ol.addWidget(self.sw_local)
        for cb in (self.cb_layout, self.cb_scale, self.cb_shade, self.cb_wiki):
            cb.currentTextChanged.connect(lambda *_: self._save_cfg())
        self.sw_local.checkedChanged.connect(lambda *_: self._save_cfg())
        root.addWidget(opts)

        # ⑤ 操作按钮
        acts = QHBoxLayout()
        acts.setSpacing(8)
        self.btn_start = PrimaryPushButton(FIF.PLAY, "开始出图（当前 BP + RP 的全部配方）", self)
        self.btn_start.clicked.connect(self.start_all)
        self.btn_zip = PushButton(FIF.ZIP_FOLDER, "导出 ZIP", self)
        self.btn_zip.clicked.connect(self.on_zip)
        self.btn_share = PushButton(FIF.SHARE, "分享 ZIP", self)
        self.btn_share.clicked.connect(self.on_share)
        self.btn_open = PushButton(FIF.FOLDER, "打开输出文件夹", self)
        self.btn_open.clicked.connect(self.open_out)
        acts.addWidget(self.btn_start, 2)
        for b in (self.btn_zip, self.btn_share, self.btn_open):
            acts.addWidget(b, 1)
        root.addLayout(acts)

        more = QHBoxLayout()
        more.setSpacing(8)
        self.btn_update = PushButton(FIF.SYNC, "检查更新", self)
        self.btn_update.clicked.connect(self.check_updates)
        more.addWidget(self.btn_update)
        for text, slot in (("选择配方文件…", self.pick_files),
                           ("选择配方文件夹…", self.pick_folder),
                           ("补全原版资源（下载全部纹理）", self.sync_vanilla),
                           ("删除本地纹理缓存", self.clear_cache)):
            b = PushButton(text, self)
            b.clicked.connect(slot)
            more.addWidget(b)
        more.addStretch(1)
        root.addLayout(more)

        # ⑥ 进度 + 日志
        self.bar = ProgressBar(self)
        self.bar.setValue(0)
        root.addWidget(self.bar)
        self.log = TextEdit(self)
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("日志会显示在这里")
        root.addWidget(self.log, 1)

        self._refresh_hint()
        self._log(f"合成表生成器 v{APP_VERSION} 就绪。")
        self._log("出图会直接写你选的目录（其下建「合成表」）。")
        QTimer.singleShot(1500, self.check_updates_silent)

    # ------------------------------------------------------------------ 主题
    def _restore_theme(self):
        """首次启动跟随设备；之后一律尊重用户自己的选择。"""
        t = self.cfg.get("theme")
        if t not in ("dark", "light"):
            t = "dark" if gui_theme.system_is_dark() else "light"
            self.cfg["theme"] = t
            save_config(self.cfg)
        setTheme(Theme.DARK if t == "dark" else Theme.LIGHT)
        self.theme_sw.setChecked(t == "dark")
        self._paint_bg()

    def _paint_bg(self):
        """窗口底色：浅色用近白，深色用近黑（可由这里统一调整）。"""
        bg = "#202020" if isDarkTheme() else "#fbfbfd"
        self.setStyleSheet(f"MainWindow {{ background: {bg}; }}")
        try:
            self.drop.setStyleSheet("")
            self.update()
        except Exception:
            pass

    def _toggle_theme(self, dark: bool):
        setTheme(Theme.DARK if dark else Theme.LIGHT)
        self.cfg["theme"] = "dark" if dark else "light"
        save_config(self.cfg)
        self._paint_bg()

    # ------------------------------------------------------------------ 工具
    def _log(self, text: str):
        self.log.append(str(text).rstrip())
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def _toast(self, title: str, body: str, ok=True):
        try:
            InfoBar.success if ok else InfoBar.warning
            (InfoBar.success if ok else InfoBar.warning)(
                title=title, content=body, orient=Qt.Horizontal, isClosable=True,
                position=InfoBarPosition.TOP_RIGHT, duration=3500, parent=self)
        except Exception:
            self._log(f"{title}：{body}")

    def _progress(self, done: int, total: int):
        self.bar.setValue(int(done * 100 / max(1, total)))

    def _finished(self, count: int):
        self.busy = False
        self.btn_start.setEnabled(True)
        self.bar.setValue(100 if count else 0)
        self._toast("完成" if count else "没有生成图片",
                    f"共 {count} 张 → {self.generator().out_root()}" if count else "请检查日志")
        self._refresh_hint()

    def _save_cfg(self):
        c = self.cfg
        c["bp"] = self.row_bp.value()
        c["rp"] = self.row_rp.value()
        c["out"] = self.row_out.value()
        c["vanilla"] = self.row_vanilla.value()
        c["layout"] = self.cb_layout.currentText()
        c["scale"] = int(self.cb_scale.currentText() or 4)
        c["cube_shading"] = self.cb_shade.currentText()
        c["wiki_icons"] = self.cb_wiki.currentText()
        c["local_only"] = bool(self.sw_local.isChecked())
        c["out_subdir"] = c.get("out_subdir") or "合成表"
        save_config(c)
        self._refresh_hint()

    def generator(self) -> Generator:
        self._save_cfg()
        return Generator(self.cfg, log=self.bridge.logged.emit)

    def _refresh_hint(self):
        out = self.row_out.value()
        sub = self.cfg.get("out_subdir") or "合成表"
        where = os.path.join(out, sub) if out and os.path.basename(os.path.normpath(out)) != sub else out
        self.hint.setText(f"图片会放在：{where or '（还没选输出目录）'}")

    # ------------------------------------------------------------------ 选择
    def _pick_dir(self, row: PathRow):
        p = QFileDialog.getExistingDirectory(self, "选择文件夹", row.value() or BASE)
        if p:
            row.edit.setText(os.path.normpath(p))
            self._save_cfg()

    def pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择配方 / 压缩包", self.cfg.get("last_dir") or BASE,
            "配方或附加包 (*.json *.mcaddon *.mcpack *.zip);;所有文件 (*)")
        if files:
            self.cfg["last_dir"] = os.path.dirname(files[0])
            self._save_cfg()
            self._start(files)

    def pick_folder(self):
        p = QFileDialog.getExistingDirectory(self, "选择配方文件夹",
                                             self.cfg.get("last_dir") or BASE)
        if p:
            self._start([p])

    def _on_dropped(self, paths):
        self._start(paths)

    # ------------------------------------------------------------------ 出图
    def start_all(self):
        if not self.row_bp.value():
            self._toast("还没选行为包", "请先选「行为包 BP」，或把 .mcaddon 拖进窗口", ok=False)
            return
        self._start([self.row_bp.value()])

    def _start(self, paths):
        if self.busy:
            self._toast("还在出图", "请等这一批完成", ok=False)
            return
        if not self.row_out.value():
            self._toast("还没选输出目录", "请先选「输出目录」", ok=False)
            return
        self.busy = True
        self.btn_start.setEnabled(False)
        self.bar.setValue(0)
        gen = self.generator()

        def work():
            try:
                total = len(paths)
                for i, p in enumerate(paths):
                    self.bridge.logged.emit(f"\n=== 处理 {os.path.basename(p)} ===")
                    gen.run([p])
                    self.bridge.progress.emit(i + 1, total)
                self.bridge.finished.emit(len(gen.out_root() and os.listdir(gen.out_root()) or []))
            except Exception:
                self.bridge.logged.emit("✗ 出图失败：\n" + traceback.format_exc())
                self.bridge.finished.emit(0)
            finally:
                gen.cleanup()

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ 其他
    def _zip_path(self) -> str:
        out = self.generator().out_root()
        if not out or not os.path.isdir(out):
            return ""
        base = os.path.join(os.path.dirname(out), os.path.basename(out.rstrip("\\/")))
        return base + ".zip"

    def on_zip(self):
        out = self.generator().out_root()
        if not out or not os.path.isdir(out):
            self._toast("没有可导出的图片", "先出一次图", ok=False)
            return
        target = self._zip_path()
        try:
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
                for root, _d, fs in os.walk(out):
                    for f in fs:
                        full = os.path.join(root, f)
                        z.write(full, os.path.relpath(full, os.path.dirname(out)))
            self._toast("已导出 ZIP", target)
        except Exception as exc:
            self._toast("导出失败", str(exc), ok=False)

    def on_share(self):
        target = self._zip_path()
        if not target or not os.path.isfile(target):
            self.on_zip()
        if target and os.path.isfile(target):
            try:
                os.startfile(target)          # 交给系统默认程序（可复制到别的 App）
            except Exception as exc:
                self._toast("分享失败", str(exc), ok=False)

    def open_out(self):
        out = self.generator().out_root()
        if out and os.path.isdir(out):
            os.startfile(out)
        else:
            self._toast("目录还不存在", "先出一次图", ok=False)

    def sync_vanilla(self):
        self.cfg["vanilla_download"] = True
        self._save_cfg()
        self._toast("开始补全", "正在下载缺失的原版纹理，请看日志")
        self._start([self.row_bp.value()] if self.row_bp.value() else [])

    # ------------------------------------------------------------------ 更新
    def _show_update(self, info):
        """检查结果回到界面线程。"""
        if isinstance(info, str):                      # 检查失败
            self._log(f"检查更新失败：{info}")
            return
        if not info.get("newer"):
            self._toast("已是最新版本",
                        f"当前 v{APP_VERSION}，GitHub 最新 {info.get('asset_version')}")
            return
        asset = info.get("asset") or {}
        if not asset:
            self._toast("有新版本但没有可用的安装包", str(info.get("latest")), ok=False)
            return
        size = asset.get("size", 0) / 1048576
        self._log(f"发现新版本 {info.get('asset_version')}（{size:.1f} MB），开始下载…")
        threading.Thread(target=self._download_and_run, args=(asset,), daemon=True).start()

    def _download_and_run(self, asset):
        try:
            path = updater.download(
                asset["url"], name=asset["name"],
                progress=lambda d, t: self.bridge.logged.emit(
                    f"下载中 {d / 1048576:.1f}/{t / 1048576:.1f} MB"
                    if t else f"下载中 {d / 1048576:.1f} MB"))
        except Exception as exc:
            self.bridge.logged.emit(f"✗ 下载失败：{exc}")
            return
        self.bridge.logged.emit(f"✓ 已下载：{path}，即将启动安装器")
        # 安装器看到 .installed 就会跳过解压，先删掉它才能覆盖旧版本
        stamp = os.path.join(os.environ.get("LOCALAPPDATA", ""), "BRR", ".installed")
        try:
            os.remove(stamp)
        except OSError:
            pass
        try:
            os.startfile(path)
        except Exception as exc:
            self.bridge.logged.emit(f"✗ 无法启动安装器：{exc}")
            return
        # 让安装器接管：本进程退出，否则 exe / dll 被占用无法替换
        QTimer.singleShot(1200, QApplication.quit)

    def check_updates(self):
        self.btn_update.setEnabled(False)
        self._log("正在检查 GitHub 最新版本…")

        def work():
            try:
                info = updater.check(APP_VERSION, platform="windows")
            except Exception as exc:
                self.bridge.updateReady.emit(str(exc))
            else:
                self.bridge.updateReady.emit(info)
            finally:
                QTimer.singleShot(0, lambda: self.btn_update.setEnabled(True))

        threading.Thread(target=work, daemon=True).start()

    def check_updates_silent(self):
        """启动时静默检查：有新版本才提示，失败不打扰。"""

        def work():
            try:
                info = updater.check(APP_VERSION, platform="windows")
            except Exception:
                return
            if info.get("newer"):
                self.bridge.updateReady.emit(info)

        threading.Thread(target=work, daemon=True).start()

    def clear_cache(self):
        box = MessageBox("确认", "删除本地下载的原版纹理缓存？\n（已内置的素材不受影响）", self)
        if not box.exec():
            return
        import shutil
        for name in ("vanilla_cache", "wiki_cache"):
            p = os.path.join(bundle_dir() if getattr(sys, "frozen", False) else BASE, name)
            shutil.rmtree(p, ignore_errors=True)
        self._toast("已删除", "本地纹理缓存已清空")


def main(argv=None) -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(argv if argv is not None else sys.argv)
    setThemeColor("#2f7cf6")
    try:
        seed_caches()          # 首次运行把内置缓存铺到数据目录（与 tkinter 版一致）
    except Exception:
        pass
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
