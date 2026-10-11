"""系统字体：核心的 mcrender/fonts.py 里只有一处 Windows 专属代码
（_SYSTEM_FONTS 指向 C:\\Windows\\Fonts），Android 上要换成系统 CJK 字体。

核心文件不做修改：这里只**在导入后替换那个模块级常量**，核心其余逻辑照旧。
"""
from __future__ import annotations

import glob
import os

# Android 常见 CJK 字体（不同厂商 ROM 路径略有差异，全部枚举一遍）
ANDROID_CANDIDATES = (
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansCJKsc-Regular.otf",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/system/fonts/NotoSansHans-Regular.otf",
    "/system/fonts/DroidSansFallbackFull.ttf",
    "/system/fonts/DroidSansFallback.ttf",
    "/system/fonts/MiSans-Regular.ttf",
    "/system/fonts/HarmonyOS_Sans_SC.ttf",
    "/system/fonts/msyh.ttf",
)
# 桌面开发时的回退
DESKTOP_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def find_fonts() -> tuple[str, ...]:
    found = [p for p in ANDROID_CANDIDATES if os.path.isfile(p)]
    if not found:
        found += [p for p in DESKTOP_CANDIDATES if os.path.isfile(p)]
    if not found:                      # 广撒网再找一遍
        for pattern in ("/system/fonts/*CJK*", "/system/fonts/*Fallback*",
                        "/system/fonts/*SC*", "/system/fonts/NotoSans*.ttf"):
            found += sorted(glob.glob(pattern))
    return tuple(dict.fromkeys(found))


def install() -> tuple[str, ...]:
    """把探测到的字体列表注入核心模块；必须在首次渲染前调用。"""
    from mcrender import fonts as core_fonts

    fonts = find_fonts()
    core_fonts._SYSTEM_FONTS = fonts or core_fonts._SYSTEM_FONTS
    core_fonts._FONT_CACHE.clear()          # 丢掉可能已缓存的 None
    core_fonts._SYSTEM_GLYPH_CACHE.clear()
    return fonts
