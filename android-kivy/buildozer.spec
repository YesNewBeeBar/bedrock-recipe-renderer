[app]
title = 合成表生成器
package.name = bedrockreciperenderer
package.domain = com.yesnewbeebar
source.dir = .
source.include_exts = py,png,jpg,json,ttf,ttc,otf
source.exclude_dirs = bin, .buildozer, __pycache__, tests
version = 1.0.0

# Pillow 由 python-for-android 的官方 recipe 构建（这是选 Kivy 路线的唯一原因）
# 只留必需项：certifi 非必需（net.py 有系统证书回退）、plyer 非必需
# （picking.py 会退回 jnius 的 ACTION_OPEN_DOCUMENT）
requirements = python3,kivy,pillow,android

orientation = portrait
fullscreen = 0
android.api = 34
android.minapi = 24
# 只编 64 位，构建时间减半；需要老机型再加 armeabi-v7a
android.archs = arm64-v8a
android.permissions = INTERNET, ACCESS_NETWORK_STATE
android.allow_backup = True
android.enable_androidx = True
android.accept_sdk_license = True
android.logcat_filters = *:S python:D

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png

# p4a 新版修了大量 Python 3.13+/NDK r28 的 wheel 标签问题
p4a.branch = develop

[buildozer]
log_level = 2
warn_on_root = 0
