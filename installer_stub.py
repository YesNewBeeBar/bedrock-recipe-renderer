"""自解压安装器（纯 Python，不含 PySide6，所以启动很快）。

内嵌 app.zip（整个程序目录），双击后：
  1) 解压到 %LOCALAPPDATA%\\BRR（已安装过就跳过）
  2) 建桌面快捷方式
  3) 启动主程序
之后用户从快捷方式启动，速度与文件夹版一致（约 1 秒）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
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


def make_shortcut(exe: str) -> bool:
    """建桌面快捷方式。

    直接拼 `powershell -Command` 会在中文路径 + 引号上翻车（实测建不出来），
    改成先写一个带 BOM 的 .ps1 再执行 —— 路径原样交给 PowerShell，最稳。
    """
    lines = [
        "$ws = New-Object -ComObject WScript.Shell",
        "$desktop = [Environment]::GetFolderPath('Desktop')",
        "$lnk = Join-Path $desktop '合成表生成器.lnk'",
        "$s = $ws.CreateShortcut($lnk)",
        "$s.TargetPath = '" + exe + "'",
        "$s.WorkingDirectory = '" + TARGET + "'",
        "$s.IconLocation = '" + exe + "'",
        "$s.Description = 'Minecraft 基岩版合成表出图工具'",
        "$s.Save()",
        "Write-Output ('OK ' + $lnk)",
    ]
    script = os.path.join(tempfile.gettempdir(), "brr_shortcut.ps1")
    try:
        # utf-8-sig：PowerShell 5 认 BOM，没有 BOM 时中文会乱码
        with open(script, "w", encoding="utf-8-sig") as fh:
            fh.write("\n".join(lines) + "\n")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
            capture_output=True, text=True, timeout=60,
            creationflags=0x08000000)
        out = (r.stdout or "") + (r.stderr or "")
        if "OK" in out:
            return True
        print("快捷方式输出:", out.strip()[:200])
    except Exception as exc:
        print("快捷方式创建失败:", exc)
    return False


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
        ok = make_shortcut(exe)
        print("桌面快捷方式:", "已创建" if ok else "创建失败（可从安装目录直接启动）")
        print("安装完成")
    else:
        print("已安装过，直接启动")
        exe = ensure_named()

    if os.path.isfile(exe):
        subprocess.Popen([exe], cwd=TARGET)
        return 0
    print("找不到主程序:", exe)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
