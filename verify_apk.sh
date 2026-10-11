#!/usr/bin/env bash
# 校验 APK：权限是否声明、应用模块是否齐全
set -u
APK=$(ls -t /root/brr/bin/*.apk | head -1)
echo "APK: $APK"
echo "大小: $(du -h "$APK" | cut -f1)"

echo
echo
echo "=== 解出 AndroidManifest.xml 后查权限 ==="
cd /tmp && rm -rf apkchk && mkdir apkchk && cd apkchk
unzip -o -q "$APK" AndroidManifest.xml
for p in MANAGE_EXTERNAL_STORAGE INTERNET ACCESS_NETWORK_STATE WRITE_EXTERNAL_STORAGE; do
    a=$(strings AndroidManifest.xml | grep -c "$p" || true)
    b=$(strings -el AndroidManifest.xml 2>/dev/null | grep -c "$p" || true)
    echo "  $p : utf8=$a utf16=$b"
done
cd /tmp/apkv 2>/dev/null || cd /tmp
echo
echo "=== 直接扫 APK（压缩内容，预期为 0，仅作对照）==="
for p in MANAGE_EXTERNAL_STORAGE INTERNET ACCESS_NETWORK_STATE READ_EXTERNAL_STORAGE; do
    n=$(strings "$APK" 2>/dev/null | grep -c "$p" || true)
    echo "  $p : $n"
done

echo
echo "=== 应用模块（private.tar 内）==="
cd /tmp && rm -rf apkv && mkdir apkv && cd apkv
unzip -o -q "$APK" assets/private.tar
tar -tf assets/private.tar | grep -E 'main.pyc|platform_layer/|fonts/Noto' || true

echo
echo "=== 构建日志末尾 ==="
grep -E "BUILD SUCCESSFUL|APK " /root/brr/build.log | tail -2
