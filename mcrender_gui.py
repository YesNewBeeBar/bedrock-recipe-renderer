"""合成表生成器 —— 把 recipe json / 文件夹 / .mcaddon .mcpack .zip 拖进来，直接出合成表图片。

- 拖 recipe json → 用 config.json 里配置的 BP/RP 出这一条
- 选 BP 文件夹 → 自动找配套的 RP（同一个 com.mojang 下的 development_resource_packs）
- 选 RP 文件夹 → 只把它设为纹理来源
- 拖 .mcaddon / .mcpack / .mcworld / .zip → 自动解包（支持压缩套压缩），按 manifest.json 分出 BP/RP 再出图
- 输出落在「输出目录\\合成表\\」里，路径、版式、缩放、wiki 开关都写回 config.json（记住上次选择）

命令行（无窗口）：
    mcrender_gui.exe --headless <文件或目录> [...]
    mcrender_gui.exe --sync-vanilla <行为包目录>
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """配置和缓存所在目录（打包成 exe 后就是 exe 所在目录）。"""
    if _frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return HERE


def bundle_dir() -> str:
    """打包进去的只读数据所在目录。"""
    if _frozen():
        return getattr(sys, "_MEIPASS", app_dir())
    return HERE


def icon_path() -> str | None:
    """窗口 / exe 图标：用工具自己渲染的工作台。"""
    for root in (app_dir(), bundle_dir(), HERE):
        p = os.path.join(root, "assets", "icon.ico")
        if os.path.isfile(p):
            return p
    return None


def set_window_icon(window) -> None:
    path = icon_path()
    if not path:
        return
    try:
        window.iconbitmap(default=path)
        return
    except Exception:
        pass
    try:
        import tkinter as tk
        png = path[:-4] + ".png"
        if os.path.isfile(png):
            window.iconphoto(True, tk.PhotoImage(file=png))
    except Exception:
        pass


def seed_caches() -> None:
    """打包成 exe 时，把随包携带的缓存拷到 exe 旁边（第一次运行时做一次）。"""
    if not _frozen():
        return
    for name in ("vanilla_cache", "wiki_cache"):
        src = os.path.join(bundle_dir(), name)
        dst = os.path.join(app_dir(), name)
        if os.path.isdir(src) and not os.path.isdir(dst):
            try:
                shutil.copytree(src, dst)
            except Exception:
                pass
    icon_src = os.path.join(bundle_dir(), "assets")
    icon_dst = os.path.join(app_dir(), "assets")
    if os.path.isdir(icon_src) and not os.path.isdir(icon_dst):
        try:
            shutil.copytree(icon_src, icon_dst)
        except Exception:
            pass


from mcrender import icon as icon_mod                     # noqa: E402
from mcrender.assets import Assets                        # noqa: E402
from mcrender.recipes import parse                        # noqa: E402
from mcrender.render import Renderer                      # noqa: E402

CONFIG_PATH = os.path.join(app_dir(), "config.json")
ARCHIVE_EXTS = (".mcaddon", ".mcpack", ".mcworld", ".zip", ".mcproject")
DEFAULTS = {
    # every path starts empty on purpose: the tool ships with no personal paths, and
    # config.json (written next to the exe) is meant to stay out of version control
    "bp": "",
    "rp": "",
    "vanilla": "",
    "out": "",
    "out_subdir": "合成表",
    "scale": 4,
    "layout": "modern",
    "cube_shading": "vanilla",
    "wiki_icons": "auto",
    "wiki_language": "en",
    "vanilla_download": True,
    # turned on automatically once "补全原版资源" has fetched everything: from then on
    # rendering reads only local files and never waits for the network again
    "local_only": False,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as fh:
                cfg.update({k: v for k, v in json.load(fh).items() if v is not None})
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --------------------------------------------------------------------- packs
def is_archive(path: str) -> bool:
    return path.lower().endswith(ARCHIVE_EXTS)


def pack_kinds(root: str) -> set:
    """Which pack types a folder is, from its manifest.json modules."""
    manifest = os.path.join(root, "manifest.json")
    if not os.path.isfile(manifest):
        return set()
    try:
        with open(manifest, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        return set()
    kinds = set()
    for module in data.get("modules", []) or []:
        kind = str(module.get("type", "")).lower()
        if kind == "data":
            kinds.add("bp")
        elif kind in ("resources", "client_data"):
            kinds.add("rp")
    return kinds


def manifest_info(root: str) -> dict:
    path = os.path.join(root, "manifest.json")
    try:
        with open(path, encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except Exception:
        return {}
    return data or {}


def find_matching_rp(bp_path: str) -> str | None:
    """找一个行为包配套的资源包：先按 com.mojang 目录约定，再按 manifest 依赖 uuid。"""
    bp_path = os.path.abspath(bp_path.rstrip("\\/"))
    base = os.path.basename(bp_path)
    parent = os.path.dirname(bp_path)

    names = []
    for old, new in (("(BP)", "(RP)"), ("(bp)", "(rp)"), ("_BP", "_RP"), ("_bp", "_rp"),
                     ("-BP", "-RP"), ("-bp", "-rp"), ("BP", "RP"), ("bp", "rp")):
        if old in base:
            names.append(base.replace(old, new))
    names.append(base)

    roots = []
    if "development_behavior_packs" in parent:
        roots.append(parent.replace("development_behavior_packs", "development_resource_packs"))
    roots.append(parent)
    roots.append(os.path.join(os.path.dirname(parent), "development_resource_packs"))

    for root in roots:
        for name in names:
            cand = os.path.join(root, name)
            if os.path.isdir(cand) and "rp" in pack_kinds(cand):
                return cand

    # fall back to the uuid link: an RP that depends on this BP's header uuid
    uuid = (manifest_info(bp_path).get("header") or {}).get("uuid")
    if uuid:
        for root in roots:
            if not os.path.isdir(root):
                continue
            try:
                entries = os.listdir(root)
            except OSError:
                continue
            for name in entries:
                cand = os.path.join(root, name)
                if not os.path.isdir(cand) or cand == bp_path:
                    continue
                for dep in (manifest_info(cand).get("dependencies") or []):
                    if isinstance(dep, dict) and dep.get("uuid") == uuid:
                        return cand
    return None


def unpack_archive(path: str, workroot: str, depth: int = 0) -> tuple:
    """Extract an add-on archive, unpacking nested archives too.

    Many ``.mcaddon`` / ``.mcpack`` downloads are zipped twice: the outer archive
    holds another ``.mcpack``/``.zip`` (or the packs sit in a subfolder), so every
    nested archive is extracted as well, up to a sane depth.
    """
    dest = tempfile.mkdtemp(prefix=f"mcaddon{depth}_", dir=workroot)
    nested = []
    try:
        with zipfile.ZipFile(path) as zf:
            zf.extractall(dest)
    except zipfile.BadZipFile:
        return [], [], dest
    for root, _dirs, files in os.walk(dest):
        for name in files:
            if name.lower().endswith(ARCHIVE_EXTS):
                nested.append(os.path.join(root, name))

    bp, rp = [], []
    for root, _dirs, files in os.walk(dest):
        if "manifest.json" in files:
            kinds = pack_kinds(root)
            if "bp" in kinds:
                bp.append(root)
            if "rp" in kinds:
                rp.append(root)

    if depth < 4:
        for inner in nested:
            if os.path.abspath(inner) == os.path.abspath(path):
                continue
            sub_bp, sub_rp, _ = unpack_archive(inner, workroot, depth + 1)
            bp += sub_bp
            rp += sub_rp
    return bp, rp, dest


def find_recipes(root: str) -> list:
    """All recipe jsons under a folder (prefers a 'recipes' subfolder when present)."""
    preferred = os.path.join(root, "recipes")
    base = preferred if os.path.isdir(preferred) else root
    out = []
    for r, _dirs, files in os.walk(base):
        out += [os.path.join(r, f) for f in sorted(files) if f.lower().endswith(".json")]
    return out


# ----------------------------------------------------------------------- core
class Generator:
    """解析配方 → 出图；纹理索引按（BP, RP）组合缓存，批量很快。"""

    def __init__(self, cfg: dict, log=print):
        self.cfg = cfg
        self.log = log
        self._assets_cache: dict = {}
        self._tmp: list = []

    # -- assets
    def assets_for(self, bp=None, rp=None):
        bp = list(bp) if bp else ([self.cfg["bp"]] if self.cfg.get("bp") else [])
        rp = list(rp) if rp else ([self.cfg["rp"]] if self.cfg.get("rp") else [])
        key = (tuple(bp), tuple(rp))
        if key not in self._assets_cache:
            self.log("读取资源包索引…")
            local_only = bool(self.cfg.get("local_only"))
            self._assets_cache[key] = Assets(
                bp_dir=bp, rp_dir=rp, vanilla_dir=self.cfg.get("vanilla"),
                wiki_root=app_dir(), wiki_icons=self.cfg.get("wiki_icons", "auto"),
                wiki_language=self.cfg.get("wiki_language", "en"),
                vanilla_download=bool(self.cfg.get("vanilla_download", True)),
                local_only=local_only,
                tool_root=app_dir(), bundle_root=bundle_dir())
            src = self._assets_cache[key].vanilla
            self.log(f"原版资源：{src.status()}"
                     + ("（只用本地，不联网）" if local_only else ""))
        return self._assets_cache[key]

    # -- output
    def out_root(self) -> str:
        """导出根目录：在用户选的输出目录里再建一个「合成表」子文件夹。

        输出目录本身就叫「合成表」时不再嵌套，避免出现 合成表\\合成表。
        """
        base = (self.cfg.get("out") or "").strip()
        if not base:
            return ""
        sub = (self.cfg.get("out_subdir") or "").strip()
        if sub and os.path.basename(os.path.normpath(base)) != sub:
            return os.path.join(base, sub)
        return base

    # -- batch
    def run(self, paths) -> list:
        results = []
        for path in paths:
            try:
                results += self._run_one(path)
            except Exception:
                self.log("✗ " + str(path) + "：\n" + traceback.format_exc())
        if results:
            self.log(f"\n完成：{len(results)} 张 → {self.out_root()}")
        else:
            self.log("\n没有生成任何图片")
        return results

    def _run_one(self, path: str) -> list:
        if not os.path.exists(path):
            self.log(f"跳过 {path}：路径不存在")
            return []
        if is_archive(path):
            work = tempfile.mkdtemp(prefix="mcwork_", dir=tempfile.gettempdir())
            self._tmp.append(work)
            bp, rp, dest = unpack_archive(path, work)
            self.log(f"解包 {os.path.basename(path)}：BP {len(bp)} 个、RP {len(rp)} 个")
            if not bp and not rp:
                self.log("  ↳ 里面没有 manifest.json，按普通压缩包处理")
                return self.render_files(find_recipes(dest), bp or None, rp or None)
            files = []
            for root in bp:
                files += find_recipes(root)
            return self.render_files(files, bp or None, rp or None)

        if os.path.isdir(path):
            kinds = pack_kinds(path)
            if kinds:
                self.log(f"{os.path.basename(path)} 是一个"
                         f"{'行为包' if 'bp' in kinds else ''}"
                         f"{'资源包' if 'rp' in kinds else ''}")
                if "bp" not in kinds:
                    return []                # 只是资源包，里面没有配方
                bp = [path]
                rp = [path] if "rp" in kinds else None
                if rp is None:
                    paired = find_matching_rp(path)
                    if paired:
                        self.log(f"自动配对的资源包：{paired}")
                        rp = [paired]
                    elif self.cfg.get("rp"):
                        self.log(f"使用配置里的资源包：{self.cfg['rp']}")
                return self.render_files(find_recipes(path), bp, rp)
            return self.render_files(find_recipes(path), None, None)

        if path.lower().endswith(".json"):
            return self.render_files([path], None, None)
        self.log(f"跳过 {os.path.basename(path)}：不认识的文件类型")
        return []

    def render_files(self, files: list, bp=None, rp=None) -> list:
        cfg = self.cfg
        if not (cfg.get("out") or "").strip():
            self.log("还没有选输出目录 —— 请点「输出目录」那一行的「选择…」后再出图")
            return []
        out_dir = self.out_root()
        os.makedirs(out_dir, exist_ok=True)
        if not files:
            self.log("没有找到 recipe json")
            return []
        icon_mod.set_shading(cfg.get("cube_shading", "vanilla"))
        renderer = Renderer(self.assets_for(bp, rp), scale=int(cfg.get("scale", 4)),
                            layout=cfg.get("layout", "modern"), background=None)
        done = []
        for path in files:
            rel = self._relative(path)
            try:
                rec = parse(path)
            except Exception as exc:
                self.log(f"✗ {os.path.basename(path)}：JSON 读不了（{exc}）")
                continue
            if rec is None or rec.kind == "unknown":
                self.log(f"· {os.path.basename(path)}：不是合成表配方，跳过")
                continue
            target = os.path.join(out_dir, os.path.splitext(rel)[0] + ".png")
            try:
                img, _lay = renderer.render(rec)
            except Exception as exc:
                self.log(f"✗ {os.path.basename(path)}：{exc}")
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            img.save(target)
            done.append(target)
            self.log(f"✓ {rec.identifier or os.path.basename(path)}  →  {target}")
        for warning in sorted(set(renderer.warnings)):
            self.log("   ! " + warning)
        renderer.warnings.clear()
        return done

    def _relative(self, path: str) -> str:
        path = os.path.abspath(path)
        folder = os.path.dirname(path)
        for _ in range(4):
            if os.path.basename(folder).lower() == "recipes":
                return os.path.relpath(path, folder)
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
        return os.path.basename(path)

    def prefetch(self, pack_root: str) -> dict:
        """把某个包所有配方要用到的贴图先下好（省得正式出图时一张一张下）。"""
        files = find_recipes(pack_root)
        kinds = pack_kinds(pack_root)
        rp = None
        if "rp" not in kinds:
            paired = find_matching_rp(pack_root)
            rp = [paired] if paired else None
            if paired:
                self.log(f"预取用配套资源包：{paired}")
        assets = self.assets_for([pack_root], rp)
        ids = set()
        recipes = 0
        for path in files:
            try:
                rec = parse(path)
            except Exception:
                continue
            if rec is None or rec.kind == "unknown":
                continue
            recipes += 1
            ids.update(i for i in rec.items() if i)
        before = assets.vanilla.downloaded
        missing = []
        for ident in sorted(ids):
            try:
                icon = assets.resolve(ident)
                icon.render(16)
                if icon.kind == "missing":
                    missing.append(ident)
            except Exception:
                missing.append(ident)
        return {"recipes": recipes, "items": len(ids),
                "downloaded": assets.vanilla.downloaded - before, "missing": missing}

    def cleanup(self):
        for tmp in self._tmp:
            shutil.rmtree(tmp, ignore_errors=True)
        self._tmp.clear()


# ----------------------------------------------------------------------------- gui
def run_gui(paths):
    import tkinter as tk
    from tkinter import filedialog, ttk

    cfg = load_config()
    root = tk.Tk()
    root.title("合成表生成器")
    set_window_icon(root)
    root.geometry("880x660")
    root.minsize(760, 540)

    state = {"busy": False}

    tk.Label(root, text="合成表生成器", font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(10, 2))
    tk.Label(root, text="选好 BP 和 RP，再拖配方进来（或点开始出图）", fg="#555555").pack()
    drop = tk.Label(root, text="↓  将 [json / .mcaddon / .mcpack / zip / 文件夹] 拖入窗口  ↓",
                    height=2, relief="ridge", bd=2,
                    font=("Microsoft YaHei UI", 11), bg="#eeeeee")
    drop.pack(fill="x", padx=12, pady=8)

    paths_frame = tk.Frame(root)
    paths_frame.pack(fill="x", padx=12)
    paths_frame.columnconfigure(1, weight=1)
    entries = {}

    log = tk.Text(root, height=15, wrap="word")
    log.pack(fill="both", expand=True, padx=12, pady=8)
    scroll = tk.Scrollbar(log, command=log.yview)
    scroll.pack(side="right", fill="y")
    log.config(yscrollcommand=scroll.set)

    def write(msg):
        log.insert("end", str(msg) + "\n")
        log.see("end")
        try:
            root.update_idletasks()
        except Exception:
            pass

    def apply_cfg(save=False):
        cfg.update(bp=entries["bp"].get(), rp=entries["rp"].get(), out=entries["out"].get(),
                   vanilla=entries["vanilla"].get(), layout=layout_var.get(),
                   scale=int(scale_var.get() or 4), cube_shading=shade_var.get(),
                   wiki_icons=wiki_var.get(), local_only=bool(local_var.get()))
        if save:
            save_config(cfg)
        return cfg

    def add_path_row(row, key, label, initial, picker):
        tk.Label(paths_frame, text=label, width=10, anchor="w").grid(row=row, column=0, sticky="w")
        var = tk.StringVar(value=initial)
        tk.Entry(paths_frame, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4)
        entries[key] = var
        tk.Button(paths_frame, text="选择…", command=picker).grid(row=row, column=2)

    def pick_dir(title, var, after=None):
        p = filedialog.askdirectory(title=title, initialdir=var.get() or os.getcwd())
        if p:
            var.set(os.path.normpath(p))
            apply_cfg(save=True)
            if after:
                after(p)

    def ready_hint():
        bp, rp = entries["bp"].get(), entries["rp"].get()
        if bp and rp:
            write("BP / RP 都已就绪 → 点「▶ 开始出图（当前 BP + RP 的全部配方）」")
        elif bp:
            write("已设置 BP。请再点 RP 那一行的「选择…」选资源包（否则自定义纹理会是紫黑方块）")
        elif rp:
            write("已设置 RP。请再点 BP 那一行的「选择…」选行为包")

    def pick_bp():
        def after(p):
            paired = find_matching_rp(p)
            if paired:
                entries["rp"].set(paired)
                apply_cfg(save=True)
                write(f"自动找到配套资源包：{paired}")
            else:
                write("没找到配套资源包，请手动选 RP")
            ready_hint()
        pick_dir("选择行为包 BP 文件夹（里面有 manifest.json 和 recipes）", entries["bp"], after)

    def pick_rp():
        def after(p):
            write(f"资源包已设为：{p}")
            ready_hint()
        pick_dir("选择资源包 RP 文件夹（textures / models 所在）", entries["rp"], after)

    add_path_row(0, "bp", "行为包 BP", cfg.get("bp", ""), pick_bp)
    add_path_row(1, "rp", "资源包 RP", cfg.get("rp", ""), pick_rp)
    add_path_row(2, "out", "输出目录", cfg.get("out", ""),
                 lambda: pick_dir("选择输出目录", entries["out"]))
    def pick_vanilla():
        """原版包可以是文件夹，也可以是 .zip / .mcpack / .mcaddon。"""
        from tkinter import filedialog as fd
        path = fd.askopenfilename(
            title="选择原版包：文件夹里的资源包，或资源包压缩文件",
            filetypes=[("资源包压缩文件", "*.zip *.mcpack *.mcaddon"), ("所有文件", "*.*")])
        if not path:
            path = fd.askdirectory(title="或者选择原版资源包文件夹")
        if not path:
            return
        entries["vanilla"].set(os.path.normpath(path))
        check_vanilla_pack()

    def check_vanilla_pack():
        """有有效原版包（文件夹或压缩文件）时直接进本地模式，不等下载。"""
        value = entries["vanilla"].get().strip()
        if not value:
            return
        from mcrender.vanilla import VanillaSource
        source = VanillaSource(local_dirs=[value] if os.path.isdir(value) else [],
                               zip_files=[value] if os.path.isfile(value) else [],
                               cache_dir=os.path.join(app_dir(), "vanilla_cache"),
                               allow_download=False)
        if not source.has_pack():
            write(f"原版包无效（找不到 textures/item_texture.json）：{value}")
            return
        kind = "文件夹" if os.path.isdir(value) else "压缩文件"
        write(f"原版包（{kind}）可用，已切到本地模式，不再联网。")
        local_var.set(True)
        apply_cfg(save=True)

    add_path_row(3, "vanilla", "原版包", cfg.get("vanilla", ""), pick_vanilla)

    out_hint = tk.Label(paths_frame, text="", fg="#666666", anchor="w",
                        font=("Microsoft YaHei UI", 9))
    out_hint.grid(row=4, column=1, columnspan=2, sticky="w", padx=4)

    def refresh_hint(*_):
        base = entries["out"].get()
        sub = (cfg.get("out_subdir") or "").strip()
        if sub and os.path.basename(os.path.normpath(base or ".")) != sub:
            out_hint.config(text=f"图片会放在：{os.path.join(base, sub)}")
        else:
            out_hint.config(text=f"图片会放在：{base}")

    entries["out"].trace_add("write", refresh_hint)
    refresh_hint()

    opts = tk.Frame(root)
    opts.pack(fill="x", padx=12, pady=(8, 0))
    tk.Label(opts, text="版式").grid(row=0, column=0, sticky="w")
    layout_var = tk.StringVar(value=cfg.get("layout", "modern"))
    ttk.Combobox(opts, textvariable=layout_var, values=("modern", "classic"), width=9,
                 state="readonly").grid(row=0, column=1, padx=(4, 14))
    tk.Label(opts, text="缩放").grid(row=0, column=2, sticky="w")
    scale_var = tk.StringVar(value=str(cfg.get("scale", 4)))
    ttk.Combobox(opts, textvariable=scale_var, values=("2", "3", "4", "6", "8"), width=4,
                 state="readonly").grid(row=0, column=3, padx=(4, 14))
    tk.Label(opts, text="方块阴影").grid(row=0, column=4, sticky="w")
    shade_var = tk.StringVar(value=cfg.get("cube_shading", "vanilla"))
    ttk.Combobox(opts, textvariable=shade_var, values=("vanilla", "reference"), width=10,
                 state="readonly").grid(row=0, column=5, padx=(4, 14))
    tk.Label(opts, text="wiki 图标").grid(row=0, column=6, sticky="w")
    wiki_var = tk.StringVar(value=cfg.get("wiki_icons", "auto"))
    ttk.Combobox(opts, textvariable=wiki_var, values=("auto", "always", "never"), width=7,
                 state="readonly").grid(row=0, column=7, padx=4)
    local_var = tk.BooleanVar(value=bool(cfg.get("local_only")))
    tk.Checkbutton(opts, text="只用本地（不联网）", variable=local_var,
                   command=lambda: apply_cfg(save=True)).grid(row=0, column=8, padx=(10, 0))

    def process(paths_):
        if state["busy"]:
            write("还在处理上一条，稍等…")
            return
        paths_ = [p for p in paths_ if p]
        if not paths_:
            return
        state["busy"] = True
        write("─" * 62)
        for p in paths_:
            write("收到：" + str(p))
        gen = Generator(apply_cfg(save=True), log=write)
        try:
            gen.run(paths_)
        except Exception:
            write("出错了：\n" + traceback.format_exc())
        finally:
            gen.cleanup()
            state["busy"] = False

    def on_thread(paths_):
        threading.Thread(target=process, args=(paths_,), daemon=True).start()

    def start_all():
        """只有 BP + RP 都选好了才出图。"""
        bp, rp = entries["bp"].get(), entries["rp"].get()
        if not bp:
            write("还没选 BP 文件夹")
            return
        if not rp:
            paired = find_matching_rp(bp)
            if paired:
                entries["rp"].set(paired)
                apply_cfg(save=True)
                write(f"自动找到配套资源包：{paired}")
                rp = paired
            else:
                write("还没选 RP 文件夹 —— 请先选资源包，否则自定义纹理会是紫黑方块")
                return
        on_thread([bp])

    def pick_files():
        fs = filedialog.askopenfilenames(
            title="选择 recipe json 或压缩包",
            filetypes=[("配方/压缩包", "*.json *.mcaddon *.mcpack *.zip"), ("所有文件", "*.*")])
        if fs:
            on_thread(list(fs))

    def pick_recipe_folder():
        d = filedialog.askdirectory(title="选择含 recipes 的文件夹（普通文件夹也行）")
        if d:
            on_thread([d])

    def gen_out_dir():
        base = (apply_cfg(save=True)["out"] or "").strip()
        if not base:
            write("还没选输出目录")
            return None
        sub = (cfg.get("out_subdir") or "").strip()
        if sub and os.path.basename(os.path.normpath(base)) != sub:
            return os.path.join(base, sub)
        return base

    def open_out():
        d = gen_out_dir()
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)                                    # noqa: S606
        except Exception:
            subprocess.Popen(["explorer", d])

    def sync_vanilla():
        def job():
            from mcrender.vanilla import VanillaSource
            cfg_now = apply_cfg(save=True)
            src = VanillaSource(
                local_dirs=[cfg_now.get("vanilla")] if cfg_now.get("vanilla") else [],
                cache_dir=os.path.join(app_dir(), "vanilla_cache"), allow_download=True,
                log=write)
            write("开始补全原版资源：把原版全部物品/方块纹理下载到本地（只增不删）…")
            try:
                report = src.sync_all(log=write)
                core = report.get("core", {}) or {}
                write(f"清单 {report.get('listed', 0)} 个纹理；新下载 {report.get('fetched', 0)} 个，"
                      f"失败 {report.get('failed', 0)} 个；缓存共 {src.cache_size_mb()} MB")
                if report.get("failed"):
                    for rel in report.get("failed_list", [])[:10]:
                        write("  ✗ 下载失败：" + rel)
                # 索引只列出一部分贴图（石头工具、骨粉这类是直接以文件名引用的），
                # 所以再按配方走一遍，把它们也拉下来，之后本地模式才不会缺件。
                if cfg_now.get("bp") and os.path.isdir(cfg_now["bp"]):
                    write("按配方预取贴图（索引里没有的文件也在这一步补齐）")
                    gen = Generator(dict(cfg_now, local_only=False), log=write)
                    info = gen.prefetch(cfg_now["bp"])
                    gen.cleanup()
                    write(f"配方 {info['recipes']} 条 / 物品 {info['items']} 个，"
                          f"新下载 {info['downloaded']} 个，仍缺 {len(info['missing'])} 个")
                    for ident in info["missing"][:10]:
                        write("  缺：" + ident)
                    if not report.get("failed") and info["missing"]:
                        report["failed"] = len(info["missing"])
                if not report.get("failed"):
                    cfg_now["local_only"] = True
                    save_config(cfg_now)
                    local_var.set(True)
                    write("以后出图只用本地文件，不会再联网（含 wiki 图标）。")
                    self_cache = None
                else:
                    write("有下载失败的条目，暂不切换到纯本地模式；可以再点一次补全。")
            except Exception as exc:
                write("补全出错：" + str(exc))
        threading.Thread(target=job, daemon=True).start()

    def clear_texture_cache():
        from tkinter import messagebox
        cache = os.path.join(app_dir(), "vanilla_cache")
        size = 0
        if os.path.isdir(cache):
            for root, _dirs, files in os.walk(cache):
                for f in files:
                    try:
                        size += os.path.getsize(os.path.join(root, f))
                    except OSError:
                        pass
        if not messagebox.askyesno(
                "删除本地纹理缓存",
                f"确定删除本地原版纹理缓存吗？\n\n{cache}\n"
                f"（约 {round(size / 1048576, 1)} MB）\n\n"
                "删除后下次出图会重新按需联网下载，或从本地原版包读取。"):
            return

        def job():
            import shutil
            shutil.rmtree(cache, ignore_errors=True)
            cfg_now = load_config()
            cfg_now["local_only"] = False
            save_config(cfg_now)
            try:
                local_var.set(False)
            except Exception:
                pass
            write(f"已删除本地纹理缓存：{cache}")
            write("已切回按需联网模式（缺什么补什么）。")
        threading.Thread(target=job, daemon=True).start()

    bar = tk.Frame(root)
    bar.pack(fill="x", padx=12, pady=(0, 6))
    tk.Button(bar, text="选择配方文件…", command=pick_files).pack(side="left")
    tk.Button(bar, text="选择配方文件夹…", command=pick_recipe_folder).pack(side="left", padx=6)

    bar2 = tk.Frame(root)
    bar2.pack(fill="x", padx=12, pady=(0, 10))
    tk.Button(bar2, text="▶ 开始出图（当前 BP + RP 的全部配方）", command=start_all,
              font=("Microsoft YaHei UI", 9, "bold")).pack(side="left")
    tk.Button(bar2, text="补全原版资源（下载全部纹理）", command=sync_vanilla).pack(side="left", padx=6)
    tk.Button(bar2, text="删除本地纹理缓存", command=clear_texture_cache).pack(side="left")
    tk.Button(bar2, text="打开输出文件夹", command=open_out).pack(side="left")
    tk.Button(bar2, text="清空日志", command=lambda: log.delete("1.0", "end")).pack(side="right")

    try:
        import ctypes
        from ctypes import wintypes

        WM_DROPFILES = 0x0233
        GWLP_WNDPROC = -4
        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32
        hwnd = wintypes.HWND(root.winfo_id())
        shell32.DragAcceptFiles(hwnd, True)
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint,
                                     wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowLongPtrW.restype = ctypes.c_void_p
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, ctypes.c_uint,
                                           wintypes.WPARAM, wintypes.LPARAM]
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR,
                                           wintypes.UINT]
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        def wndproc(h, msg, wparam, lparam):
            if msg == WM_DROPFILES:
                hdrop = wintypes.HANDLE(wparam)
                count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                picked = []
                for i in range(count):
                    need = shell32.DragQueryFileW(hdrop, i, None, 0)
                    buf = ctypes.create_unicode_buffer(need + 1)
                    shell32.DragQueryFileW(hdrop, i, buf, need + 1)
                    picked.append(buf.value)
                shell32.DragFinish(hdrop)
                on_thread(picked)
                return 0
            return user32.CallWindowProcW(old_proc, h, msg, wparam, lparam)

        proc = WNDPROC(wndproc)
        old_proc = user32.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, proc)
        drop.config(text="↓  将 [json / .mcaddon / .mcpack / zip / 文件夹] 拖入窗口  ↓",
                    bg="#dff0d8")
    except Exception as exc:                                    # pragma: no cover
        write(f"（窗口拖放不可用，请用下面的按钮：{exc}）")

    if paths:
        root.after(200, lambda: on_thread(paths))
    write(f"输出目录：{cfg.get('out')}")
    if entries["vanilla"].get().strip():
        check_vanilla_pack()
    root.mainloop()


def main(argv) -> int:
    args = list(argv[1:])
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    seed_caches()
    if args and args[0] == "--sync-vanilla":
        from mcrender.vanilla import VanillaSource
        cfg = load_config()
        bundled = [os.path.join(b, "assets", n) for b in (app_dir(), bundle_dir())
                   for n in ("ui", "vanilla_extra")]
        src = VanillaSource(local_dirs=[d for d in bundled if os.path.isdir(d)] +
                                       ([cfg["vanilla"]] if cfg.get("vanilla") else []),
                            cache_dir=os.path.join(app_dir(), "vanilla_cache"),
                            allow_download=True, log=print)
        report = src.sync_all(log=print)
        passed = not report.get("failed")
        if passed:
            cfg["local_only"] = True
            save_config(cfg)
        print(f"纹理：清单 {report.get('listed', 0)}，新下载 {report.get('fetched', 0)}，"
              f"失败 {report.get('failed', 0)}，跳过 {len(report.get('skipped', []))}；"
              f"缓存 {src.cache_size_mb()} MB")
        for rel in (report.get("failed_list") or [])[:20]:
            print("  ✗ " + rel)
        print("已切换为纯本地模式（不再联网）" if passed else "仍有失败条目，未切换纯本地模式")
        for folder in [a for a in args[1:] if os.path.isdir(a)]:
            gen = Generator(cfg)
            info = gen.prefetch(folder)
            print(f"预取 {os.path.basename(folder)}：{info['recipes']} 条配方 / "
                  f"{info['items']} 个物品，新下载 {info['downloaded']} 个文件，"
                  f"仍未找到 {len(info['missing'])} 个")
            for ident in info["missing"][:15]:
                print("  ? " + ident)
            gen.cleanup()
        return 0
    if args and args[0] == "--headless":
        cfg = load_config()
        gen = Generator(cfg)
        try:
            ok = gen.run(args[1:])
        finally:
            gen.cleanup()
        return 0 if ok else 1
    run_gui(args)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
