"""自解压安装器（纯 Python，不含 PySide6，所以启动很快）。

内嵌 app.zip（整个程序目录），双击后：
  1) 解压到 %LOCALAPPDATA%\\BRR（已存在且版本一致就跳过）
  2) 建桌面快捷方式
  3) 启动主程序
之后用户从快捷方式启动，速度与文件夹版一致（约 1 秒）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile

APP_NAME = "合成表生成器.exe"
#: 打包目录里可能是原始文件名，安装时统一改名成中文名
ALT_NAMES = ("bedrock-recipe-renderer-fluent.exe",)
TARGET = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "BRR")
STAMP = os.path.join(TARGET, ".installed")


def base_dir() -> str:
    """PyInstaller onefile 会把数据解到 sys._MEIPASS。"""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def find_payload() -> str:
    root = base_dir()
    for cand in ("app.zip", os.path.join("payload", "app.zip")):
        p = os.path.join(root, cand)
        if os.path.isfile(p):
            return p
    return ""


def extract(payload: str) -> bool:
    try:
        os.makedirs(TARGET, exist_ok=True)
        with zipfile.ZipFile(payload) as z:
            z.extractall(TARGET)
        with open(STAMP, "w", encoding="utf-8") as fh:
            fh.write("ok")
        return True
    except Exception as exc:
        print("解压失败:", exc)
        return False


def make_shortcut(exe: str) -> None:
    ps = (
        "$s=New-Object -ComObject WScript.Shell;"
        "$l=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\\合成表生成器.lnk');"
        f"$l.TargetPath='{exe}';$l.WorkingDirectory='{TARGET}';"
        f"$l.IconLocation='{exe}';$l.Description='Minecraft 基岩版合成表出图工具';$l.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       creationflags=0x08000000, timeout=30)
    except Exception:
        pass


def ensure_named() -> str:
    """把解压出来的 exe 统一成中文名（打包目录里可能还是英文名）。"""
    want = os.path.join(TARGET, APP_NAME)
    if os.path.isfile(want):
        return want
    for alt in ALT_NAMES:
        src = os.path.join(TARGET, alt)
        if os.path.isfile(src):
            try:
                os.replace(src, want)
                return want
            except Exception:
                return src
    return want


def main() -> int:
    exe = os.path.join(TARGET, APP_NAME)
    payload = find_payload()

    need = (not os.path.isfile(exe)) or (not os.path.isfile(STAMP))
    if need:
        if not payload:
            print("找不到内嵌的程序包")
            return 1
        print("正在安装到", TARGET)
        if not extract(payload):
            return 1
        exe = ensure_named()
        make_shortcut(exe)
        print("安装完成（桌面已创建快捷方式）")
    else:
        print("已安装过，直接启动")
    exe = ensure_named()

    if os.path.isfile(exe):
        subprocess.Popen([exe], cwd=TARGET)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
