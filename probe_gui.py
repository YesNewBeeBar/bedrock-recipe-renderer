#!/usr/bin/env python
"""不开窗口，直接跑 GUI 的 render_files —— 验证桌面端的输出结构与 GIF 分支。

做法：把 mcrender_gui 当模块导入（导入期不会建窗口，窗口只在 main() 里创建），
然后用一个"桩对象"调用真实的 RenderMixin.render_files（未绑定方法），
给它提供 cfg / log / out_root / assets_for / _relative，其余全走真实代码。
"""
import importlib.util
import os
import sys
import tempfile
import types
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PIL import Image                      # noqa: E402
from mcrender.assets import Assets         # noqa: E402

ARC = r"C:\Users\NewBee_Bar\Downloads\更多投掷球-v0.0.2.mcaddon.zip"
VAN = r"D:\合成表生成器移动端\android-kivy\vanilla"
WIKI = r"D:\合成表生成器移动端\android-kivy"


def load_gui():
    spec = importlib.util.spec_from_file_location("mcrender_gui_probe",
                                                  os.path.join(HERE, "mcrender_gui.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)           # 只定义类，不建窗口
    return mod


def main() -> int:
    gui = load_gui()
    # 找到持有 render_files 的类
    holder = None
    for name in dir(gui):
        obj = getattr(gui, name)
        if isinstance(obj, type) and hasattr(obj, "render_files"):
            holder = obj
            break
    if holder is None:
        print("!! 没找到含 render_files 的类")
        return 1
    print("使用类:", holder.__name__)

    work = tempfile.mkdtemp()
    out = os.path.join(work, "用户的输出目录")
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(ARC) as z:
        z.extractall(work)
    bp = rp = None
    for base, _d, fs in os.walk(work):
        if "manifest.json" not in fs:
            continue
        if os.path.isdir(os.path.join(base, "recipes")):
            bp = base
        if os.path.isdir(os.path.join(base, "textures")):
            rp = base

    stub = types.SimpleNamespace()
    stub.cfg = {"out": out, "scale": "3", "layout": "modern", "tag_gif": True}
    stub.log = lambda text: print("   ", text)
    stub.out_root = lambda: os.path.join(out, "合成表")

    def assets_for(bp_dir, rp_dir):
        return Assets(bp_dir=bp_dir, rp_dir=rp_dir, vanilla_dir=VAN, wiki_root=WIKI,
                      wiki_icons="auto", wiki_language="en", vanilla_download=False,
                      local_only=True, tool_root=WIKI, bundle_root=WIKI)
    stub.assets_for = assets_for
    stub._relative = lambda path: os.path.basename(path)
    stub._tag_gif = types.MethodType(holder._tag_gif, stub)

    # 拿两条配方：一条普通、一条带标签（自己造一条放进临时 BP）
    files = []
    for base, _d, fs in os.walk(bp):
        for f in fs:
            if f.endswith(".json") and "recipes" in base:
                files.append(os.path.join(base, f))
    files = files[:2]
    tag_bp = os.path.join(work, "tagpack", "recipes")
    os.makedirs(tag_bp, exist_ok=True)
    import json
    tag_rec = os.path.join(tag_bp, "planks_test.json")
    json.dump({"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": "probe:planks"}, "tags": ["crafting_table"],
        "pattern": ["##", "##"], "key": {"#": {"tag": "minecraft:planks"}},
        "result": {"item": "minecraft:stick"}}},
        open(tag_rec, "w", encoding="utf-8"))
    files.append(tag_rec)

    print(f"\n调用真实的 render_files（{len(files)} 条配方，pack='我的测试包'）…")
    done = holder.render_files(stub, files, bp, rp, pack="我的测试包")
    print(f"\n产出 {len(done)} 个文件：")
    for d in done:
        print("   ", os.path.relpath(d, work))
        if d.endswith(".gif"):
            im = Image.open(d)
            print(f"      GIF: {im.size} 帧数={im.n_frames} 循环={im.info.get('loop')}")
    expect = os.path.join(out, "合成表", "我的测试包")
    print("\n是否落在 <输出>/合成表/我的测试包/ 下:",
          all(os.path.abspath(d).startswith(expect) for d in done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
