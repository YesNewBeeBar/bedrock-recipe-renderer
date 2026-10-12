[app]
title = 合成表生成器
package.name = bedrockreciperenderer
package.domain = com.yesnewbeebar
source.dir = .
source.include_exts = py,png,jpg,json,ttf,ttc,otf,tga,none
source.exclude_dirs = bin, .buildozer, __pycache__, tests
version = 1.1.4
# Android 的 versionCode：必须递增，否则安装时提示“已安装相同版本”
android.numeric_version = 16

# Pillow 由 python-for-android 的官方 recipe 构建（这是选 Kivy 路线的唯一原因）
# 这一行是**已验证能编过 APK** 的组合，改动前请先在 CI 上试
requirements = python3,kivy,pillow,certifi,plyer,android

orientation = portrait
fullscreen = 0
android.api = 34
android.minapi = 24
# 只编 64 位，构建时间减半；需要老机型再加 armeabi-v7a
android.archs = arm64-v8a
# MANAGE_EXTERNAL_STORAGE：所有文件访问权限（内置浏览器需要；侧载分发没问题）
android.permissions = INTERNET, ACCESS_NETWORK_STATE, MANAGE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, WRITE_EXTERNAL_STORAGE
android.allow_backup = True
android.enable_androidx = True
# SAF 目录读写（DocumentFile）需要它
android.gradle_dependencies = androidx.documentfile:documentfile:1.0.1
android.accept_sdk_license = True
android.logcat_filters = *:S python:D

icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/icon.png


[buildozer]
log_level = 2
warn_on_root = 0
