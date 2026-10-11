#!/usr/bin/env bash
# 交付：最新 APK 以正式名字拷到 D:\演示，并核对包内内容
set -u
APK=$(ls -t /root/brr/bin/*.apk | head -1)
VER=$(basename "$APK" | sed -E 's/.*-([0-9]+\.[0-9]+\.[0-9]+)-arm64.*/\1/')
OUT="/mnt/d/演示/合成表生成器-v${VER}-Android.apk"

mkdir -p /mnt/d/演示
rm -f /mnt/d/演示/*.apk
cp -f "$APK" "$OUT"
echo "交付: 合成表生成器-v${VER}-Android.apk  ($(du -h "$OUT" | cut -f1))"

echo
echo "=== 包内核对 ==="
cd /tmp && rm -rf fin && mkdir fin && cd fin
unzip -o -q "$APK" assets/private.tar
mkdir a && tar -xf assets/private.tar -C a
echo "  版本:      $(strings a/main.pyc | grep -o '1\.0\.[0-9]' | head -1)"
echo "  原版素材:  $(find a/vanilla -type f | wc -l) 个"
echo "  wiki 图标: $(find a/wiki_cache -type f | wc -l) 个 (png $(find a/wiki_cache -name '*.png' | wc -l))"
echo "  平台模块:  $(ls a/platform_layer/*.pyc | wc -l) 个"
echo "  中文字体:  $([ -f a/fonts/NotoSansSC-Regular.ttf ] && echo 有 || echo 无)"
ls -la /mnt/d/演示/*.apk
