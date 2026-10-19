#!/usr/bin/env bash
# 交付正式版：改名成官方命名，核对包内版本号，旧的 Kivy 版标记为遗留
set -u
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
BT=$(ls -d /root/android-sdk/build-tools/* 2>/dev/null | head -1)
SRC="/mnt/d/合成表生成器移动端/android-compose/app/build/outputs/apk/release/app-release.apk"
DST=""

# 版本号从 APK 里读，文件名带上它（桌面/手机共用一个 release，文件名要能区分版本）
V=$(ls -d /root/android-sdk/build-tools/* 2>/dev/null | head -1)
if [ -n "$V" ] && [ -x "$V/aapt" ]; then
    VER=$("$V/aapt" dump badging "$SRC" 2>/dev/null | grep -o "versionName='[^']*'" | head -1 | cut -d"'" -f2)
else
    VER=1.0.1
fi
[ -z "$VER" ] && VER=1.0.1
DST="/mnt/d/演示/合成表生成器-v${VER}-Android.apk"
echo "== 交付: $DST ($(du -h "$DST" | cut -f1)) =="
ls -la "$DST"

echo
echo "== 包内版本与签名 =="
if [ -n "$BT" ] && [ -x "$BT/aapt" ]; then
    "$BT/aapt" dump badging "$DST" 2>/dev/null | grep -E "^package|application-label" | head -3
else
    echo "（aapt 不在 $BT，改用 python 读 zip 里的版本串）"
fi

echo
echo "== 旧的 Kivy 版标记为遗留 =="
OLD="/mnt/d/演示/合成表生成器-v1.2.9-Android.apk"
if [ -f "$OLD" ]; then
    mv -f "$OLD" "/mnt/d/演示/合成表生成器-v1.2.9-Android-legacy-kivy.apk"
    echo "  已改名: 合成表生成器-v1.2.9-Android-legacy-kivy.apk"
fi

echo
echo "== D:\\演示\\ 现状 =="
ls -la /mnt/d/演示/ | grep -iE "apk|exe" | awk '{print "  " $5 "  " $9}'
