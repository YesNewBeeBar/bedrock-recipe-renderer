"""平台适配层：Android / 桌面上都能跑的差异都收在这里，核心模块不感知平台。

- paths   应用私有目录（数据 / 缓存 / 配置）与导出目录
- fonts   系统 CJK 字体探测（Android 的 /system/fonts），供 mcrender.fonts 使用
- picker  文件 / 文件夹选择（Toga 对话框 → Android SAF）
- storage 导出：写 ZIP、逐张另存、系统分享
- net     TLS 证书与离线开关
"""
from . import fonts, net, paths, picker, storage  # noqa: F401

__all__ = ["fonts", "net", "paths", "picker", "storage"]
