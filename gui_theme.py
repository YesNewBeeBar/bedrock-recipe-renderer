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


def apply_later(root, dark: bool, skip=(), times=(60, 400, 1200)) -> None:
    """控件是边建边出现的，延后多刷几次，保证晚建的也被覆盖。"""
    for delay in times:
        try:
            root.after(delay, lambda d=dark: apply(root, d, skip))
        except Exception:
            pass


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
        # ttk 只看 state map —— 不写这些，输入框/下拉框永远是系统白
        for name in ("TEntry", "TSpinbox"):
            style.map(name, fieldbackground=[("!disabled", c["panel"])],
                      foreground=[("!disabled", c["fg"])],
                      background=[("!disabled", c["panel"])])
        style.map("TCombobox",
                  fieldbackground=[("readonly", c["panel"]), ("!disabled", c["panel"])],
                  foreground=[("readonly", c["fg"]), ("!disabled", c["fg"])],
                  background=[("readonly", c["panel"]), ("!disabled", c["panel"])],
                  arrowcolor=[("!disabled", c["fg"])],
                  selectbackground=[("readonly", c["panel"])],
                  selectforeground=[("readonly", c["fg"])])
        style.map("TCheckbutton",
                  background=[("!disabled", c["bg"])],
                  foreground=[("!disabled", c["fg"])],
                  indicatorbackground=[("!disabled", c["panel"])])
        style.map("TButton", background=[("!disabled", c["panel"])],
                  foreground=[("!disabled", c["fg"])])
        # 下拉列表本身
        root.option_add("*TCombobox*Listbox.background", c["panel"])
        root.option_add("*TCombobox*Listbox.foreground", c["fg"])
        root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        root.option_add("*TCombobox*Listbox.selectForeground", c["accent_fg"])
    except Exception:
        pass

    def walk(w):
        yield w
        for child in w.winfo_children():
            for sub in walk(child):
                yield sub

    # ttk 的样式按**类名**生效；有些控件用的是自定义 style，这里统一兜一遍
    try:
        for name in ("TFrame", "TLabelframe", "TLabelframe.Label", "TLabel", "TButton",
                     "TEntry", "TCombobox", "TCheckbutton", "TSpinbox", "TNotebook"):
            style.configure(name, background=c["bg"], foreground=c["fg"])
        style.configure("TCombobox", fieldbackground=c["panel"], foreground=c["fg"],
                        selectbackground=c["panel"], selectforeground=c["fg"])
        style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"],
                        indicatorbackground=c["panel"])
        # 下拉弹窗（Listbox）也要跟着暗，否则点开还是一块白
        root.option_add("*TCombobox*Listbox.background", c["panel"])
        root.option_add("*TCombobox*Listbox.foreground", c["fg"])
        root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        root.option_add("*TCombobox*Listbox.selectForeground", c["accent_fg"])
    except Exception:
        pass

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
            elif cls in ("Checkbutton", "Radiobutton"):
                w.configure(bg=c["bg"], fg=c["fg"], activebackground=c["bg"],
                            activeforeground=c["fg"], selectcolor=c["panel"],
                            highlightbackground=c["bg"], highlightthickness=0)
            elif cls in ("Entry", "Spinbox"):
                w.configure(bg=c["panel"], fg=c["fg"], insertbackground=c["fg"])
        except Exception:
            pass
    return c


# ------------------------------------------------------------------ 现代控件
def round_rect(canvas, x1, y1, x2, y2, r, fill=None, outline=None, width=1, dash=None):
    """在 Canvas 上画圆角矩形（tkinter 没有原生圆角）；dash 给虚线卡片用。"""
    import tkinter as tk
    items = []
    if fill:
        items.append(canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline=""))
        items.append(canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline=""))
        for cx, cy, start in ((x1 + r, y1 + r, 90), (x2 - r, y1 + r, 0),
                              (x1 + r, y2 - r, 180), (x2 - r, y2 - r, 270)):
            items.append(canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                           start=start, extent=90, fill=fill, outline=""))
    if outline:
        # create_line 只认 fill（outline 是 arc/rectangle 的参数）
        kw = {"fill": outline, "width": width}
        if dash:
            kw["dash"] = dash
        items.append(canvas.create_line(x1 + r, y1, x2 - r, y1, **kw))
        items.append(canvas.create_line(x1 + r, y2, x2 - r, y2, **kw))
        items.append(canvas.create_line(x1, y1 + r, x1, y2 - r, **kw))
        items.append(canvas.create_line(x2, y1 + r, x2, y2 - r, **kw))
        # 四角用实线弧（虚线弧在 tk 上会断断续续、看着毛糙）
        for cx, cy, start in ((x1 + r, y1 + r, 90), (x2 - r, y1 + r, 0),
                              (x1 + r, y2 - r, 180), (x2 - r, y2 - r, 270)):
            items.append(canvas.create_arc(cx - r, cy - r, cx + r, cy + r,
                                           start=start, extent=90, style="arc",
                                           outline=outline, width=width))
    return items


def pill(parent, text, command, dark=False, kind="ghost"):
    """胶囊按钮：kind=primary(蓝底白字) / ghost(面板底描边)。

    颜色一律以控件自身的 _dark 为准（**不靠闭包**）—— 否则切换主题后会残留旧色。
    """
    import tkinter as tk
    cv = tk.Canvas(parent, height=34, highlightthickness=0, bd=0,
                   bg=palette(dark)["bg"])
    cv._dark = bool(dark)
    cv._text = text
    cv._kind = kind

    def redraw(_e=None):
        c = palette(cv._dark)
        bg = c["accent"] if cv._kind == "primary" else c["panel"]
        fg = c["accent_fg"] if cv._kind == "primary" else c["fg"]
        cv.configure(bg=c["bg"])
        cv.delete("all")
        w = cv.winfo_width() or 120
        round_rect(cv, 1, 1, w - 1, 33, 17, fill=bg,
                   outline=None if cv._kind == "primary" else c["border"])
        cv.create_text(w / 2, 17, text=cv._text, fill=fg,
                       font=("Microsoft YaHei UI", 10))

    cv.bind("<Configure>", redraw)
    cv.bind("<Button-1>", lambda _e: command())
    cv.bind("<Enter>", lambda _e: cv.configure(cursor="hand2"))

    def set_text(t):
        cv._text = t
        redraw()

    def set_theme(is_dark):
        cv._dark = bool(is_dark)
        redraw()

    cv._set_text = set_text
    cv._set_theme = set_theme
    redraw()
    return cv


def card(parent, dark=False, radius=12, pad=10):
    """一张圆角卡片，返回 (canvas, 内容 frame)。

    - 颜色以 **cv._dark** 为准（不能用创建时的闭包值，否则切主题后边框仍是旧色，
      亮色下就出现"黑框"）
    - Canvas 必须显式给高，所以内容 frame 尺寸一变就同步高度
    - 内嵌窗口宽度跟随 Canvas
    """
    import tkinter as tk
    cv = tk.Canvas(parent, highlightthickness=0, bd=0, bg=palette(dark)["bg"], height=40)
    cv._dark = bool(dark)
    inner = tk.Frame(cv, bg=palette(dark)["panel"])
    win = cv.create_window(pad, pad, window=inner, anchor="nw")

    def redraw(_e=None):
        cc = palette(cv._dark)
        cv.configure(bg=cc["bg"])
        try:
            inner.configure(bg=cc["panel"])
        except Exception:
            pass
        w, h = cv.winfo_width() or 600, cv.winfo_height() or 40
        cv.delete("shape")
        round_rect(cv, 1, 1, w - 1, h - 1, radius, fill=cc["panel"], outline=cc["border"])
        cv.tag_lower("shape")
        cv.itemconfigure(win, width=max(1, w - 2 * pad))

    def fit(_e=None):
        cv.configure(height=max(40, inner.winfo_reqheight() + 2 * pad))

    def set_theme(is_dark):
        cv._dark = bool(is_dark)
        redraw()

    cv.bind("<Configure>", redraw)
    inner.bind("<Configure>", fit)
    inner.bind("<Configure>", redraw, add="+")
    cv._set_theme = set_theme
    redraw()
    return cv, inner


def switch(parent, value=False, command=None, dark=False, width=54, height=28):
    """自绘开关（替代 tkinter 的 ✓ 方框）。轨道=两端半圆+中间矩形，旋钮=整圆。"""
    import tkinter as tk
    cv = tk.Canvas(parent, width=width, height=height, highlightthickness=0, bd=0,
                   bg=palette(dark)["bg"])
    cv._dark = bool(dark)
    cv._on = bool(value)
    cv._command = command

    def redraw(_e=None):
        c = palette(cv._dark)
        cv.configure(bg=c["bg"])
        cv.delete("all")
        w = cv.winfo_width() or width
        h = cv.winfo_height() or height
        r = (h - 2) / 2.0
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        track = c["accent"] if cv._on else c["border"]
        # 轨道：中间矩形 + 两端半圆（比圆角矩形更平滑）
        cv.create_oval(x1, y1, x1 + 2 * r, y2, fill=track, outline="")
        cv.create_oval(x2 - 2 * r, y1, x2, y2, fill=track, outline="")
        cv.create_rectangle(x1 + r, y1, x2 - r, y2, fill=track, outline="")
        # 旋钮：整圆，略内缩，带一圈浅描边更顺眼
        kr = r - 2
        cx = (x2 - r - 1) if cv._on else (x1 + r + 1)
        cy = (y1 + y2) / 2.0
        cv.create_oval(cx - kr, cy - kr, cx + kr, cy + kr,
                       fill="#ffffff", outline="#c9ccd2")

    def toggle(_e=None):
        cv._on = not cv._on
        redraw()
        if callable(cv._command):
            try:
                cv._command(cv._on)
            except Exception:
                pass

    def set_theme(is_dark):
        cv._dark = bool(is_dark)
        redraw()

    cv.bind("<Button-1>", toggle)
    cv.bind("<Configure>", redraw)
    cv.bind("<Enter>", lambda _e: cv.configure(cursor="hand2"))
    cv._set_theme = set_theme
    cv.get = lambda: cv._on
    redraw()
    return cv
