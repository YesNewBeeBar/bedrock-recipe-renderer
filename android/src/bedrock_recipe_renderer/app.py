"""Android / 桌面 GUI：Toga 版（替代桌面版的 Tkinter mcrender_gui.py）。

与桌面版一致的能力：
    选配方 / 选 BP+RP / 选输出目录 / 缩放与版式 / 只用本地 / 补全原版资源
    / 开始出图（后台线程 + 进度）/ 导出 ZIP / 分享

核心渲染逻辑全部走 mcrender 包（与桌面版同一份代码），本文件只做
「选文件 → 调核心 → 报进度 → 导出」。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import threading
import traceback

import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW

from bedrock_recipe_renderer.mcrender.assets import Assets
from bedrock_recipe_renderer.mcrender.recipes import collect, parse
from bedrock_recipe_renderer.mcrender.render import Renderer
from bedrock_recipe_renderer.platform import fonts as platform_fonts
from bedrock_recipe_renderer.platform import net as platform_net
from bedrock_recipe_renderer.platform import paths, picker, storage

LETTER = Pack(flex=1)
ROW_STYLE = Pack(direction=ROW, margin=2)
COL_STYLE = Pack(direction=COLUMN, margin=4)


class RenderJob:
    """一次批量渲染任务（在后台线程跑）。"""

    def __init__(self, on_log, on_progress):
        self.on_log = on_log
        self.on_progress = on_progress
        self.stop_flag = False

    def run(self, *, bp: str, rp: str, out_root: str, scale: int, layout: str,
            wiki_icons: str, local_only: bool, vanilla: str, files: list[str]) -> dict:
        platform_fonts.install()
        if not local_only:
            platform_net.prepare_tls()

        assets = Assets(
            bp_dir=bp or None, rp_dir=rp or None,
            vanilla_dir=vanilla or None,
            wiki_root=paths.tool_root(), wiki_icons=wiki_icons, wiki_language="en",
            vanilla_download=not local_only, local_only=local_only,
            tool_root=paths.tool_root(), bundle_root=paths.tool_root(),
        )
        renderer = Renderer(assets, scale=scale, layout=layout, background=None)

        recipe_files = self._collect(files, bp)
        total = len(recipe_files)
        self.on_log(f"待渲染 {total} 条配方")

        done = 0
        failed = []
        for path in recipe_files:
            if self.stop_flag:
                self.on_log("已取消")
                break
            try:
                rec = parse(path)
                img, _lay = renderer.render(rec)
                rel = self._relative(path, bp, files)
                dest = os.path.join(out_root, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                img.save(dest)
                done += 1
            except Exception as exc:                     # 单条失败不影响整批
                failed.append(f"{os.path.basename(path)}: {exc}")
            if total:
                self.on_progress(done / total)
        for w in renderer.warnings[:10]:
            self.on_log("! " + w)
        for f in failed[:10]:
            self.on_log("! " + f)
        return {"done": done, "total": total, "failed": len(failed),
                "out_root": out_root, "warnings": renderer.warnings}

    # ---------------------------------------------------------------- helpers
    def _collect(self, files: list[str], bp: str) -> list[str]:
        out: list[str] = []
        for path in files:
            if os.path.isdir(path):
                out += collect(path)
            elif picker.is_archive(path):
                out += self._unpack(path)
            elif path.lower().endswith(".json"):
                out.append(path)
        if bp and os.path.isdir(bp) and not out:
            out = collect(bp)
        return sorted(dict.fromkeys(out))

    def _unpack(self, archive: str) -> list[str]:
        """压缩包（含双层）解到私有目录，再找出所有配方 JSON。"""
        target = os.path.join(paths.work_dir(), "unpack", os.path.basename(archive))
        shutil.rmtree(target, ignore_errors=True)
        os.makedirs(target, exist_ok=True)
        import zipfile
        found: list[str] = []
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(target)
        for root, _dirs, fs in os.walk(target):
            for f in fs:
                full = os.path.join(root, f)
                if f.lower().endswith((".zip", ".mcpack", ".mcaddon", ".mcworld")):
                    try:
                        with zipfile.ZipFile(full) as inner:
                            sub = full + "_x"
                            inner.extractall(sub)
                        found += self._json_under(sub)
                    except Exception:
                        pass
                elif f.lower().endswith(".json"):
                    found.append(full)
        return sorted(dict.fromkeys(found))

    @staticmethod
    def _json_under(root: str) -> list[str]:
        return [os.path.join(r, f)
                for r, _d, fs in os.walk(root) for f in fs if f.endswith(".json")]

    @staticmethod
    def _relative(path: str, bp: str, files: list[str]) -> str:
        for base in (bp, *(f for f in files if os.path.isdir(f))):
            if base and os.path.isdir(base) and path.startswith(base):
                return os.path.relpath(path, base)
        return os.path.basename(path)


class BedrockRecipeRenderer(toga.App):
    def startup(self) -> None:
        self.state = {
            "bp": "", "rp": "", "vanilla": "", "out": paths.default_output_dir(),
            "scale": 4, "layout": "modern", "wiki_icons": "auto", "local_only": False,
            "files": [],
        }
        self._build_ui()
        self.log("就绪。先选配方（或整包），再点「开始出图」。")
        self.log("输出目录：" + self.state["out"])

    # -------------------------------------------------------------------- ui
    def _build_ui(self) -> None:
        self.log_view = toga.MultilineTextInput(readonly=True, style=Pack(flex=1))
        self.progress = toga.ProgressBar(max=1.0, style=Pack(margin_top=6))
        self.path_label = toga.Label("未选择配方", style=Pack(margin=6))
        self.status = toga.Label("", style=Pack(margin=6))

        self.scale_select = toga.Selection(
            items=["2", "3", "4", "6", "8"], value="4", style=Pack(width=70))
        self.layout_select = toga.Selection(
            items=["modern", "classic"], value="modern", style=Pack(width=110))
        self.wiki_select = toga.Selection(
            items=["auto", "always", "never"], value="auto", style=Pack(width=100))
        self.offline_switch = toga.Switch("只用本地（不联网）", value=False)

        buttons = [
            toga.Button("选配方 / 压缩包", on_press=self.on_pick_files, style=LETTER),
            toga.Button("选 BP", on_press=self.on_pick_bp, style=LETTER),
            toga.Button("选 RP", on_press=self.on_pick_rp, style=LETTER),
        ]
        buttons2 = [
            toga.Button("选原版包", on_press=self.on_pick_vanilla, style=LETTER),
            toga.Button("补全原版资源", on_press=self.on_sync_vanilla, style=LETTER),
        ]
        actions = [
            toga.Button("▶ 开始出图", on_press=self.on_start, style=LETTER),
            toga.Button("导出 ZIP", on_press=self.on_export_zip, style=LETTER),
            toga.Button("分享 zip", on_press=self.on_share, style=LETTER),
        ]

        self.main_window = toga.MainWindow(title="合成表生成器", size=(420, 760))
        self.main_window.content = toga.Box(
            style=COL_STYLE,
            children=[
                toga.Box(style=ROW_STYLE, children=buttons),
                toga.Box(style=ROW_STYLE, children=buttons2),
                self.path_label,
                toga.Box(style=ROW_STYLE, children=[
                    toga.Label("缩放"), self.scale_select,
                    toga.Label("版式"), self.layout_select,
                    toga.Label("wiki"), self.wiki_select,
                ]),
                self.offline_switch,
                toga.Box(style=ROW_STYLE, children=actions),
                self.progress,
                self.status,
                self.log_view,
            ],
        )

    # ------------------------------------------------------------------- log
    def log(self, text: str) -> None:
        line = str(text)
        self.log_view.value = (self.log_view.value + "\n" + line).strip()

    def _ui(self, fn, *args) -> None:
        """从后台线程回到 UI 线程。"""
        self.loop.call_soon_threadsafe(fn, *args)

    # ---------------------------------------------------------------- pickers
    async def on_pick_files(self, _widget) -> None:
        files = await picker.pick_files(self.main_window.dialog, multiple=True)
        if not files:
            return
        self.state["files"] = picker.ensure_local(files, paths.work_dir())
        self.path_label.text = f"已选 {len(self.state['files'])} 个文件"
        self.log(f"选择：{', '.join(os.path.basename(f) for f in self.state['files'][:4])}")

    async def on_pick_bp(self, _widget) -> None:
        folder = await picker.pick_folder(self.main_window.dialog)
        if folder:
            self.state["bp"] = folder
            self.log("BP：" + folder)

    async def on_pick_rp(self, _widget) -> None:
        folder = await picker.pick_folder(self.main_window.dialog)
        if folder:
            self.state["rp"] = folder
            self.log("RP：" + folder)

    async def on_pick_vanilla(self, _widget) -> None:
        files = await picker.pick_files(self.main_window.dialog, multiple=False)
        if files:
            self.state["vanilla"] = files[0]
            self.state["local_only"] = True
            self.offline_switch.value = True
            self.log("原版包：" + files[0] + "（已切到本地模式）")

    # ----------------------------------------------------------------- 出图
    async def on_start(self, _widget) -> None:
        self.state["scale"] = int(self.scale_select.value)
        self.state["layout"] = self.layout_select.value
        self.state["wiki_icons"] = self.wiki_select.value
        self.state["local_only"] = bool(self.offline_switch.value)

        out_root = os.path.join(self.state["out"], "合成表")
        os.makedirs(out_root, exist_ok=True)
        self.progress.value = 0
        self.status.text = "渲染中…"
        self.log("开始出图 → " + out_root)

        job = RenderJob(self._ui_log, self._ui_progress)
        try:
            result = await asyncio.to_thread(
                job.run, bp=self.state["bp"], rp=self.state["rp"], out_root=out_root,
                scale=self.state["scale"], layout=self.state["layout"],
                wiki_icons=self.state["wiki_icons"], local_only=self.state["local_only"],
                vanilla=self.state["vanilla"], files=self.state["files"])
        except Exception:
            self.log("失败：\n" + traceback.format_exc(limit=3))
            self.status.text = "失败"
            return
        self.progress.value = 1
        self.last_zip = ""
        self.status.text = f"完成 {result['done']}/{result['total']}，失败 {result['failed']}"
        self.log(self.status.text)

    def _ui_log(self, text: str) -> None:
        self.loop.call_soon_threadsafe(self.log, str(text))

    def _ui_progress(self, value: float) -> None:
        self.loop.call_soon_threadsafe(setattr, self.progress, "value", float(value))

    # --------------------------------------------------------------- 导出
    async def on_export_zip(self, _widget) -> None:
        out_root = os.path.join(self.state["out"], "合成表")
        if not os.path.isdir(out_root):
            self.log("还没有输出目录")
            return
        zip_path = await asyncio.to_thread(
            storage.zip_outputs, out_root,
            os.path.join(paths.exports_dir(), "合成表.zip"))
        if not zip_path:
            self.log("没有可导出的 PNG")
            return
        self.last_zip = zip_path
        self.log("已打包：" + zip_path)

    async def on_share(self, _widget) -> None:
        path = getattr(self, "last_zip", "")
        if not path:
            await self.on_export_zip(_widget)
            path = getattr(self, "last_zip", "")
        if path and await storage.share(self, path):
            self.log("已调起系统分享")
        else:
            self.log("分享不可用，文件在：" + path)


main_app = BedrockRecipeRenderer()


def main() -> toga.App:
    return main_app


if __name__ == "__main__":
    main_app.main_loop()
