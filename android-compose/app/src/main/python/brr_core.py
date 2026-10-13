"""Android 原生版（Kotlin + Compose）与 Python 渲染核心之间的适配层。

**这里不做任何生图逻辑**：只负责把 Kotlin 传来的参数翻译成对核心的调用 ——
与旧的 Kivy 版调用的是同一批函数（Assets / collect / Renderer / output_dir_for / taggif），
参数含义也保持一致。文件访问完全由 Kotlin 侧用 SAF 完成，这里只接收真实路径。
"""
from __future__ import annotations

import os
import sys
import traceback

VERSION = "2.0.0"


def _bootstrap(work_root: str, ext_root: str) -> None:
    """把当前目录（Chaquopy 解出来的 python 源码）放进 sys.path 顶部。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (here, os.path.join(here, "mcrender")):
        if p not in sys.path:
            sys.path.insert(0, p)


def _roots(work_root: str, ext_root: str):
    """核心需要的几个根目录：内置素材、wiki 缓存、人工钉死图标。"""
    here = os.path.dirname(os.path.abspath(__file__))
    vanilla = os.path.join(here, "vanilla")
    wiki = here
    pinned = os.path.join(here, "wiki_pinned")
    return here, vanilla, wiki, pinned


def render(bp_path, rp_path, vanilla_path, files, out_dir,
           scale, layout, shading, wiki_icons, local_only, logger, progress,
           work_root, ext_root):
    """出图主入口。返回生成的图片数量。"""
    try:
        _bootstrap(work_root, ext_root)
        from mcrender.assets import Assets
        from mcrender.recipes import collect
        from mcrender.render import Renderer
        from mcrender import output as out_mod
        from mcrender import taggif
        from mcrender import icon as icon_mod
    except Exception:
        logger.log("!! 核心导入失败:\n" + traceback.format_exc())
        return 0

    here, vanilla, wiki, pinned = _roots(work_root, ext_root)
    log = (lambda s: logger.log(str(s))) if logger is not None else print

    # ---- 素材（与 Kivy 版同一批参数；离线时只读本地缓存）
    try:
        assets = Assets(
            bp_dir=bp_path or None, rp_dir=rp_path or None,
            vanilla_dir=vanilla if os.path.isdir(vanilla) else None,
            wiki_root=wiki, wiki_icons=wiki_icons or "auto", wiki_language="zh",
            vanilla_download=not local_only, local_only=bool(local_only),
            tool_root=here, bundle_root=here)
    except Exception:
        logger.log("!! 素材初始化失败:\n" + traceback.format_exc())
        return 0

    log("素材状态: item_texture %d 个, terrain %d 个, blocks %d 个"
        % (len(assets.item_texture), len(assets.terrain_texture), len(assets.blocks)))

    try:
        icon_mod.set_shading(shading or "vanilla")
    except Exception:
        pass

    # ---- 配方：目录直接 collect；压缩包由 Kotlin 侧解好后再传目录（沿用旧版行为）
    recipes = []
    for path in files or []:
        try:
            if os.path.isdir(path):
                recipes += collect(path)
            else:
                log("跳过（不是目录）: " + os.path.basename(path))
        except Exception:
            log("!! 读取失败 %s:\n%s" % (path, traceback.format_exc()))

    recipes = [r for r in recipes if getattr(r, "kind", "unknown") != "unknown"]
    total = len(recipes)
    log("共识别 %d 条配方" % total)
    if not total:
        return 0

    pack_name = os.path.basename(os.path.normpath(bp_path or out_dir))
    target_root = out_mod.output_dir_for(out_dir, pack_name)
    os.makedirs(target_root, exist_ok=True)
    log("输出目录: " + target_root)

    renderer = Renderer(assets, scale=int(scale or 4), layout=layout or "modern",
                        background=None)
    done = 0
    for i, rec in enumerate(recipes, 1):
        try:
            img, _lay = renderer.render(rec)
            name = getattr(rec, "identifier", None) or "recipe_%d" % i
            safe = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in str(name))
            dest = os.path.join(target_root, safe + ".png")
            img.save(dest)
            done += 1
            try:                                   # 同标签轮播 GIF（核心能力）
                taggif.render_gif(renderer, rec, dest, log=log)
            except Exception:
                pass
            log("✓ %s" % safe)
        except Exception:
            log("✗ 第 %d 条失败:\n%s" % (i, traceback.format_exc()))
        if progress is not None:
            try:
                progress.onProgress(i, total)
            except Exception:
                pass
    log("完成 %d/%d，输出在 %s" % (done, total, target_root))
    return done


def render_files(bp_path, rp_path, vanilla_path, files, out_dir,
                 scale, layout, shading, wiki_icons, local_only, logger, progress,
                 work_root, ext_root):
    """以「文件列表」出图：压缩包在这里解开（与旧版同一套解包与包识别逻辑）。"""
    import tempfile
    here, _v, _w, _p = _roots(work_root, ext_root)
    if here not in sys.path:
        sys.path.insert(0, here)
    dirs = []
    try:
        from picking import unpack_archive          # 与旧版完全相同的解包实现
    except Exception:
        unpack_archive = None
        logger.log("!! 找不到解包模块 picking")

    parent = os.path.dirname(here)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    for path in files or []:
        if os.path.isdir(path):
            dirs.append(path)
            continue
        low = path.lower()
        if low.endswith((".mcaddon", ".mcpack", ".mcworld", ".zip")):
            try:
                work = tempfile.mkdtemp(prefix="brr_", dir=work_root or None)
                root = unpack_archive(path, work) if unpack_archive else work
                logger.log("解包 " + os.path.basename(path))
                dirs.append(root if isinstance(root, str) else work)
            except Exception:
                logger.log("!! 解包失败 %s:" + chr(10) + traceback.format_exc() % os.path.basename(path))
        elif low.endswith(".json"):
            dirs.append(os.path.dirname(path))

    if not dirs:
        logger.log("没有可处理的输入")
        return 0
    return render(bp_path or dirs[0], rp_path, vanilla_path, dirs, out_dir,
                  scale, layout, shading, wiki_icons, local_only, logger, progress,
                  work_root, ext_root)
