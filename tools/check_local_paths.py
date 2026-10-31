r"""在提交前跑一遍，防止把个人机器上的绝对路径、本机目录名带进公开仓库
（issue #12 就是这么来的）。

python tools/check_local_paths.py            # 检查当前仓库已跟踪的文件
python tools/check_local_paths.py --all      # 检查工作区全部文件（含未跟踪）

命中即视为失败（退出码 1）。二进制文件自动跳过；`C:\Windows\...` 这类
系统路径不算泄漏，可在 `ALLOW` 里豁免。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

#: 本机路径特征
PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/](?:Users|Documents|Desktop|Downloads|AppData)\b", re.I),
    re.compile(r"[A-Za-z]:[\\/](?!Windows\b)(?:[\w\-. ]+[\\/]){1,}", re.I),
    re.compile(r"/mnt/[a-z]/", re.I),
    re.compile(r"/home/[a-z_][\w.-]*/", re.I),
    re.compile(r"C:\\\\?Users\\\\?", re.I),
]

#: 允许出现的系统路径（不是个人信息）
ALLOW = [
    re.compile(r"[A-Za-z]:[\\/]Windows[\\/]", re.I),
    re.compile(r"[A-Za-z]:[\\/]Program Files", re.I),
    re.compile(r"/(?:usr|opt|etc|var|tmp|bin|sbin|lib|root)/", re.I),
    re.compile(r"/mnt/c/", re.I),
]

BINARY_EXT = (".png", ".jpg", ".jpeg", ".ttf", ".otf", ".ico", ".zip", ".apk",
              ".exe", ".bin", ".jar", ".7z", ".ttc", ".wav", ".mp3")

SKIP_DIRS = {".git", "__pycache__", "build", "dist", ".gradle", "node_modules"}


def tracked(root: str) -> list:
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode == 0 and out.stdout.strip():
        return [l for l in out.stdout.splitlines() if l.strip()]
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            found.append(os.path.relpath(os.path.join(base, f), root))
    return found


def scan(root: str, files: list) -> list:
    problems = []
    for rel in files:
        if rel.lower().endswith(BINARY_EXT):
            continue
        path = os.path.join(root, rel)
        if not os.path.isfile(path) or os.path.getsize(path) > 4 * 1024 * 1024:
            continue
        try:
            text = open(path, encoding="utf-8", errors="strict").read()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if any(a.search(line) for a in ALLOW):
                continue
            for pat in PATTERNS:
                m = pat.search(line)
                if m:
                    problems.append((rel, i, m.group(0)))
                    break
    return problems


def main() -> int:
    args = set(sys.argv[1:])
    roots = args_roots() if hasattr(sys, "argv") else [os.getcwd()]
    rc = 0
    for root in roots:
        files = tracked(root)
        probs = scan(root, files)
        if probs:
            rc = 1
            print(f"[!] {root}: {len(probs)} 处疑似本机路径")
            for rel, ln, frag in probs[:40]:
                # 只打印文件与行号，不回显路径内容
                print(f"    {rel}:{ln}  ({len(frag)} 字符)")
        else:
            print(f"[ok] {root}: 未发现本机路径")
    return rc


def args_roots() -> list:
    roots = [a for a in sys.argv[1:] if not a.startswith("-")]
    return roots or [os.getcwd()]


if __name__ == "__main__":
    raise SystemExit(main())
