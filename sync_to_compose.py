#!/usr/bin/env python
"""把渲染核心与素材同步到 android-compose 项目里。

核心与素材都来自现有的 Kivy 版目录，**保证两端用的是同一份 mcrender/**。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "android-kivy")
DST = os.path.join(HERE, "android-compose", "app", "src", "main", "python")

#: 需要整体复制的目录（核心 + 素材）
DIRS = ("mcrender", "vanilla", "wiki_cache", "wiki_pinned")
#: 单文件模块（解包实现，与旧版共用）
#: 需要复制的单文件
FILES = ("tags_be.json", "vanilla_kinds.json")
EXTRA = (("platform_layer/picking.py", "picking.py"),)


def main() -> int:
    os.makedirs(DST, exist_ok=True)
    for name in DIRS:
        s = os.path.join(SRC, name)
        d = os.path.join(DST, name)
        if not os.path.isdir(s):
            print(f"  跳过 {name}（不存在于 {SRC}）")
            continue
        if os.path.isdir(d):
            shutil.rmtree(d)
        shutil.copytree(s, d)
        n = sum(len(fs) for _b, _d, fs in os.walk(d))
        print(f"  ✓ {name}: {n} 个文件")
    for name in FILES:
        s = os.path.join(SRC, name)
        if os.path.isfile(s):
            shutil.copyfile(s, os.path.join(DST, name))
            print(f"  ✓ {name}")
        else:
            # 桌面端也有一份，兜底从那里找
            alt = os.path.join(os.path.dirname(HERE), "合成表生成器", name)
            if os.path.isfile(alt):
                shutil.copyfile(alt, os.path.join(DST, name))
                print(f"  ✓ {name}（取自桌面端）")
            else:
                print(f"  ✗ 缺少 {name}")
    for src_rel, dst_name in EXTRA:
        s = os.path.join(SRC, src_rel)
        if os.path.isfile(s):
            shutil.copyfile(s, os.path.join(DST, dst_name))
            print(f"  ✓ {dst_name}（自 {src_rel}）")
    total = sum(len(fs) for _b, _d, fs in os.walk(DST))
    size = sum(os.path.getsize(os.path.join(b, f))
               for b, _d, fs in os.walk(DST) for f in fs) / 1048576
    print(f"合计 {total} 个文件 / {size:.1f} MB -> {DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
