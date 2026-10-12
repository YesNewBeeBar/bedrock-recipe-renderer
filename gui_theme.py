"""桌面端主题：明亮 / 深色，支持"首次启动跟随设备"，之后一律尊重用户设置。

规则（用户要求）：
- 只有**第一次启动**（配置里还没有 theme 键）才根据系统深色模式决定；
- 之后无论重启还是升级，都用用户自己的选择。
"""
from __future__ import annotations

import sys

LIGHT = {
    "bg": "#f7f7f9", "panel": "#ffffff", "fg": "#000000", "dim": "#3a3d44",
    "accent": "#2f7cf6", "accent_fg": "#ffffff", "border": "#d8dade",
    "log_bg": "#ffffff", "log_fg": "#111318",
}
DARK = {
    "bg": "#16181c", "panel": "#1e2126", "fg": "#eef0f4", "dim": "#b9bec7",
    "accent": "#3d6fbf", "accent_fg": "#ffffff", "border": "#2c3138",
    "log_bg": "#14161a", "log_fg": "#dfe3ea",
}


def system_is_dark() -> bool:
    """跟随设备：Windows 读注册表；其它平台看环境变量，拿不到就当明亮。"""
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            try:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return int(value) == 0            # 0 = 深色
            finally:
                key.Close()
    except Exception:
        pass
    return False


def initial_dark(cfg: dict) -> bool:
    """配置里没有 theme 时按设备决定（仅首次）；有则原样尊重。"""
    theme = cfg.get("theme")
    if theme == "dark":
        return True
    if theme == "light":
        return False
    dark = system_is_dark()
    cfg["theme"] = "dark" if dark else "light"     # 写回，之后不再改
    return dark


def palette(dark: bool) -> dict:
    return DARK if dark else LIGHT


def apply(root, dark: bool, skip=()) -> dict:
    """遍历 tkinter 控件刷主题；skip 里的控件（如主按钮）保持自己的配色。"""
    import tkinter as tk
    from tkinter import ttk
    c = palette(dark)
    try:
        root.configure(bg=c["bg"])
    except Exception:
        pass
    try:
        style = ttk.Style(root)
        try:
            style.theme_use("clam")               # clam 才吃颜色
        except Exception:
            pass
        style.configure(".", background=c["bg"], foreground=c["fg"],
                        fieldbackground=c["panel"], bordercolor=c["border"])
        style.configure("TFrame", background=c["bg"])
        style.configure("TLabel", background=c["bg"], foreground=c["fg"])
        style.configure("TButton", background=c["panel"], foreground=c["fg"])
        style.configure("TEntry", fieldbackground=c["panel"], foreground=c["fg"])
        style.configure("TCombobox", fieldbackground=c["panel"], foreground=c["fg"])
        style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
        style.map("TCombobox", fieldbackground=[("readonly", c["panel"])])
    except Exception:
        pass

    def walk(w):
        yield w
        for child in w.winfo_children():
            for sub in walk(child):
                yield sub

    for w in walk(root):
        if w in skip:
            continue
        cls = w.winfo_class()
        try:
            if cls in ("Frame", "Toplevel", "Labelframe"):
                w.configure(bg=c["bg"])
            elif cls == "Label":
                w.configure(bg=c["bg"], fg=c["fg"])
            elif cls == "Button":
                w.configure(bg=c["panel"], fg=c["fg"],
                            activebackground=c["accent"], activeforeground=c["accent_fg"],
                            highlightbackground=c["border"])
            elif cls in ("Text", "Listbox"):
                w.configure(bg=c["log_bg"], fg=c["log_fg"], insertbackground=c["fg"])
            elif cls in ("Entry", "Spinbox"):
                w.configure(bg=c["panel"], fg=c["fg"], insertbackground=c["fg"])
        except Exception:
            pass
    return c
