"""系统字体：核心的 mcrender/fonts.py 里只有一处 Windows 专属代码
（_SYSTEM_FONTS 指向 C:\\Windows\\Fonts），Android 上要换成系统 CJK 字体。

核心文件不做修改：这里只**在导入后替换那个模块级常量**，核心其余逻辑照旧。
"""
from __future__ import annotations

import glob
import os


# 随 APK 一起打包的中文字体（Noto Sans SC，OFL）：所有机型字形一致，
# 不再依赖各家 ROM 的系统字体路径（真我/OPPO、部分定制 ROM 曾出现方框）
BUNDLED_FONTS = (
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts",
                 "NotoSansSC-Regular.ttf"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts",
                 "NotoSansSC-Regular.otf"),
)

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
    "/system/fonts/OPPOSans-R.ttf", "/system/fonts/OPPOSans-Regular.ttf",
    "/system/fonts/NotoSansCJKsc-VF.otf", "/system/fonts/SourceHanSansSC-Regular.otf",
    "/system/fonts/DroidSansChinese.ttf", "/system/fonts/ColorOSans-Regular.ttf",
)
# 桌面开发时的回退
DESKTOP_CANDIDATES = (
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)


def find_fonts() -> tuple[str, ...]:
    found = [p for p in BUNDLED_FONTS if os.path.isfile(p)]
    found += [p for p in ANDROID_CANDIDATES if os.path.isfile(p)]
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
