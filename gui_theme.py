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
    "track_off": "#9aa0aa",
    "log_bg": "#ffffff", "log_fg": "#111318",
}
DARK = {
    "bg": "#16181c", "panel": "#1e2126", "fg": "#eef0f4", "dim": "#b9bec7",
    "accent": "#3d6fbf", "accent_fg": "#ffffff", "border": "#2c3138",
    "track_off": "#7b8390",
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


def apply_later(root, dark: bool, skip=(), times=(80, 350)) -> list:
    """控件是边建边出现的，延后补刷一两次；返回 job id 供调用方取消。"""
    jobs = []
    for delay in times:
        try:
            jobs.append(root.after(delay, lambda d=dark: apply(root, d, skip)))
        except Exception:
            pass
    return jobs


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
        # Combobox 在 readonly 状态下会用到一堆子选项，少配一个就露白
        for opt, val in (("fieldbackground", c["panel"]), ("background", c["panel"]),
                         ("foreground", c["fg"]), ("arrowcolor", c["fg"]),
                         ("bordercolor", c["border"]), ("lightcolor", c["panel"]),
                         ("darkcolor", c["panel"]), ("selectbackground", c["panel"]),
                         ("selectforeground", c["fg"]), ("insertcolor", c["fg"])):
            try:
                style.configure("TCombobox", **{opt: val})
            except Exception:
                pass
        style.map("TCombobox",
                  fieldbackground=[("disabled", c["panel"]), ("readonly", c["panel"]),
                                   ("active", c["panel"]), ("!disabled", c["panel"])],
                  background=[("disabled", c["panel"]), ("readonly", c["panel"]),
                              ("active", c["panel"]), ("!disabled", c["panel"])],
                  foreground=[("disabled", c["dim"]), ("readonly", c["fg"]),
                              ("!disabled", c["fg"])],
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

    def walk(w, on_card=False):
        """on_card=True 表示"我在圆角卡片里"，底色要用 panel。"""
        yield w, on_card
        inside = on_card or bool(getattr(w, "_is_card", False))
        for child in w.winfo_children():
            for sub in walk(child, inside):
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

    for w, on_card in walk(root):
        if w in skip or getattr(w, "_dsh_theme", None) == dark:
            continue                      # 同主题不重复刷（切换才需要重画）
        w._dsh_theme = dark
        base = c["panel"] if on_card else c["bg"]   # 卡片内用面板色
        cls = w.winfo_class()
        try:
            if cls in ("Frame", "Toplevel", "Labelframe"):
                w.configure(bg=base)
            elif cls == "Label":
                w.configure(bg=base, fg=c["fg"])
            elif cls == "Button":
                w.configure(bg=c["panel"], fg=c["fg"],
                            activebackground=c["accent"], activeforeground=c["accent_fg"],
                            highlightbackground=c["border"])
            elif cls in ("Text", "Listbox"):
                w.configure(bg=c["log_bg"], fg=c["log_fg"], insertbackground=c["fg"])
            elif cls in ("Checkbutton", "Radiobutton"):
                w.configure(bg=base, fg=c["fg"], activebackground=base,
                            activeforeground=c["fg"], selectcolor=c["panel"],
                            highlightbackground=base, highlightthickness=0)
            elif cls == "Scrollbar":
                w.configure(bg=c["panel"], troughcolor=base,
                            activebackground=c["accent"],
                            highlightbackground=base, highlightthickness=0,
                            bd=0, relief="flat", elementborderwidth=0)
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


def _draw_icon(cv, store, cx, cy, colour, dark, kind_bg=None):
    """在胶囊里画"太阳/月亮"：不依赖字体，避免 emoji 变成方框。

    dark=True（当前是深色，按钮提示切到浅色）→ 画太阳
    dark=False → 画月亮（缺角圆）
    """
    if dark:
        r = 4
        store.append(cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=colour, outline=""))
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0),
                       (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7)):
            store.append(cv.create_line(cx + dx * 6, cy + dy * 6,
                                        cx + dx * 8, cy + dy * 8,
                                        fill=colour, width=1))
    else:
        # 月牙 = 实心圆 + 用按钮底色再画一个偏右的圆盖住一部分
        r = 6
        bg = kind_bg or palette(dark)["panel"]
        store.append(cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill=colour, outline=""))
        store.append(cv.create_oval(cx - r + 4, cy - r - 1, cx + r + 4, cy + r - 1,
                                    fill=bg, outline=bg))
    return store


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

    ids = {}

    def redraw(_e=None):
        c = palette(cv._dark)
        bg = c["accent"] if cv._kind == "primary" else c["panel"]
        fg = c["accent_fg"] if cv._kind == "primary" else c["fg"]
        cv.configure(bg=c["bg"])
        w = cv.winfo_width() or 120
        if not ids:                                   # 首次建图元
            shape = round_rect(cv, 1, 1, w - 1, 33, 17, fill=bg,
                               outline=None if cv._kind == "primary" else c["border"])
            ids["shape"] = shape
            ids["icon"] = []                          # 图标图元（自己画，不用 emoji）
            ids["text"] = cv.create_text(w / 2 + 10, 17, text=cv._text, fill=fg,
                                         font=("Microsoft YaHei UI", 10))
            _draw_icon(cv, ids["icon"], 20, 17, fg, dark, bg)
            return
        for it in ids["shape"]:                       # 之后只改颜色
            try:
                if cv.type(it) == "arc":
                    cv.itemconfigure(it, fill=bg)
                    if cv._kind != "primary":
                        cv.itemconfigure(it, outline=c["border"])
                else:
                    cv.itemconfigure(it, fill=bg)
            except Exception:
                pass
        for it in ids["shape"]:                       # 宽度可能变，坐标一并更新
            try:
                if cv.type(it) == "arc":
                    cx0, cy0, cx1, cy1 = cv.coords(it)
                    r = (cy1 - cy0) / 2.0
                    if cx0 < w / 2:                   # 左半的两个角
                        cv.coords(it, 1, 1, 1 + 2 * r, 33)
                    else:
                        cv.coords(it, w - 1 - 2 * r, 1, w - 1, 33)
                elif cv.type(it) == "rectangle":
                    x0, y0, x1_, y1_ = cv.coords(it)
                    if y0 <= 1:
                        cv.coords(it, x0, 1, x1_, 33)
                    else:
                        cv.coords(it, 1, y0, w - 1, y1_)
            except Exception:
                pass
        cv.itemconfigure(ids["text"], text=cv._text, fill=fg)
        cv.coords(ids["text"], w / 2 + 10, 17)
        for it in ids["icon"]:
            cv.delete(it)
        ids["icon"] = []
        _draw_icon(cv, ids["icon"], 20, 17, fg, cv._dark, bg)

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


def card(parent, dark=False, radius=12, pad=16):
    """圆角卡片，返回 (canvas, 内容 frame)。

    切主题时**只改颜色、不删除重建**（删除会露出一帧空白，切换时看着像"先白一下"）。
    内容留 pad 的内边距，原生直角控件（Text/Combobox）就不会顶到圆角上。
    """
    import tkinter as tk
    c0 = palette(dark)
    # 底色直接用 panel：内层 Frame 的方角万一露在圆角外，也是同色，不会出现白方块
    cv = tk.Canvas(parent, highlightthickness=0, bd=0, bg=c0["panel"], height=40)
    cv._dark = bool(dark)
    cv._is_card = True                      # 让主题遍历知道"里面要用 panel 底色"
    inner = tk.Frame(cv, bg=c0["panel"], highlightthickness=0, bd=0)
    win = cv.create_window(pad, pad, window=inner, anchor="nw")
    ids = {"fill": None, "line": []}

    def draw(_e=None):
        cc = palette(cv._dark)
        cv.configure(bg=cc["panel"])       # 与填充同色，缝不可见
        try:
            inner.configure(bg=cc["panel"])
        except Exception:
            pass
        w, h = cv.winfo_width() or 600, cv.winfo_height() or 40
        cv.itemconfigure(win, width=max(1, w - 2 * pad))
        if ids["fill"] is None:                       # 首次：建好所有图元
            items = round_rect(cv, 0, 0, w, h, radius, fill=cc["panel"])
            ids["fill"] = items[0]
            ids["line"] = round_rect(cv, 1, 1, w - 1, h - 1, radius, outline=cc["border"])
            cv.tag_lower(ids["fill"])
            for it in ids["line"]:
                cv.tag_raise(it, ids["fill"])
            return
        # 之后：只改颜色和几何，绝不删除（没有空白帧）
        cv.coords(ids["fill"], 0, 0, w, h) if False else None
        cv.itemconfigure(ids["fill"], fill=cc["panel"])
        col = cc["border"]
        for it in ids["line"]:
            try:
                if cv.type(it) == "arc":
                    cv.itemconfigure(it, outline=col)
                else:
                    cv.itemconfigure(it, fill=col)
            except Exception:
                pass

    def refit(_e=None):
        cv.configure(height=max(40, inner.winfo_reqheight() + 2 * pad))

    def set_theme(is_dark):
        cv._dark = bool(is_dark)
        draw()

    cv.bind("<Configure>", draw)
    inner.bind("<Configure>", refit)
    inner.bind("<Configure>", draw, add="+")
    cv._set_theme = set_theme
    draw()
    return cv, inner


def switch(parent, value=False, command=None, dark=False, width=54, height=28):
    """自绘开关（替代 tkinter 的 ✓ 方框）。轨道=两端半圆+中间矩形，旋钮=整圆。"""
    import tkinter as tk
    cv = tk.Canvas(parent, width=width, height=height, highlightthickness=0, bd=0,
                   bg=palette(dark)["bg"])
    cv._dark = bool(dark)
    cv._on = bool(value)
    cv._command = command

    ids = {}

    def redraw(_e=None):
        c = palette(cv._dark)
        cv.configure(bg=c["bg"])
        w = cv.winfo_width() or width
        h = cv.winfo_height() or height
        r = (h - 2) / 2.0
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        track = c["accent"] if cv._on else c.get("track_off", "#8a8f98")
        kr = r - 2
        cx = (x2 - r - 1) if cv._on else (x1 + r + 1)
        cy = (y1 + y2) / 2.0
        if not ids:                                   # 首次建图元
            ids["l"] = cv.create_oval(x1, y1, x1 + 2 * r, y2, fill=track, outline="")
            ids["r"] = cv.create_oval(x2 - 2 * r, y1, x2, y2, fill=track, outline="")
            ids["m"] = cv.create_rectangle(x1 + r, y1, x2 - r, y2, fill=track, outline="")
            ids["knob"] = cv.create_oval(cx - kr, cy - kr, cx + kr, cy + kr,
                                         fill="#ffffff", outline="#c9ccd2")
            return
        # 关键：布局完成后尺寸才会变（首次 redraw 时 width 可能只有 1px），
        # 所以这里必须**连坐标一起更新**，不能只改颜色。
        cv.coords(ids["l"], x1, y1, x1 + 2 * r, y2)
        cv.coords(ids["r"], x2 - 2 * r, y1, x2, y2)
        cv.coords(ids["m"], x1 + r, y1, x2 - r, y2)
        for k in ("l", "r", "m"):
            cv.itemconfigure(ids[k], fill=track)
        cv.coords(ids["knob"], cx - kr, cy - kr, cx + kr, cy + kr)

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
