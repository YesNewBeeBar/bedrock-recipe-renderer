#!/usr/bin/env python
"""改版本号：main.py 的 APP_VERSION + buildozer.spec 的 version / numeric_version。"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "android-kivy")


def main() -> int:
    ver = sys.argv[1] if len(sys.argv) > 1 else "1.0.6"
    code = sys.argv[2] if len(sys.argv) > 2 else str(int(ver.split(".")[-1]) + 1)

    p = os.path.join(APP, "main.py")
    s = io.open(p, encoding="utf-8").read()
    s = re.sub(r'APP_VERSION = "[^"]*"', f'APP_VERSION = "{ver}"', s, count=1)
    io.open(p, "w", encoding="utf-8").write(s)

    p = os.path.join(APP, "buildozer.spec")
    t = io.open(p, encoding="utf-8").read()
    t = re.sub(r"^version\s*=\s*.*$", f"version = {ver}", t, count=1, flags=re.M)
    t = re.sub(r"^android\.numeric_version\s*=\s*.*$",
               f"android.numeric_version = {code}", t, count=1, flags=re.M)
    io.open(p, "w", encoding="utf-8").write(t)

    for line in t.splitlines():
        if line.startswith("version") or "numeric_version" in line:
            print("  ", line)
    print("APP_VERSION =", ver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
