#!/usr/bin/env python
"""把「会进入合成表的原版素材」全部下到本地，供打进 APK。

用核心自带的 VanillaSource.sync_all()：它按 item_texture.json / terrain_texture.json
索引抓取全部被引用的贴图 —— 正是配方卡可能用到的那些。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "android-kivy"))

from mcrender.vanilla import VanillaSource          # noqa: E402

OUT = os.path.join(HERE, "android-kivy", "vanilla")


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    print("下载目标:", OUT, flush=True)
    src = VanillaSource(local_dirs=[OUT], cache_dir=OUT, allow_download=True)
    t0 = time.time()

    def log(msg):
        print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

    rep = src.sync_all(log=log, workers=12)
    print("结果:", rep, flush=True)
    n = sum(len(fs) for _b, _d, fs in os.walk(OUT))
    size = sum(os.path.getsize(os.path.join(b, f))
               for b, _d, fs in os.walk(OUT) for f in fs)
    print(f"落地文件 {n} 个，共 {size/1048576:.1f} MB", flush=True)
    for rel in ("textures/item_texture.json", "textures/terrain_texture.json",
                "blocks.json"):
        print("  索引", rel, os.path.isfile(os.path.join(OUT, rel)), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
