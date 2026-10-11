#!/usr/bin/env bash
# 构建后核对：新代码是否进包、权限是否声明
set -u
APK=$(ls -t /root/brr/bin/*.apk | head -1)
echo "APK: $(basename "$APK")  $(du -h "$APK" | cut -f1)"

cd /tmp && rm -rf chk && mkdir chk && cd chk
unzip -o -q "$APK" assets/private.tar AndroidManifest.xml

echo
echo "=== 1) 应用代码是否为最新 ==="
mkdir app && tar -xf assets/private.tar -C app
echo -n "  picking 有 unpack_archive ？ "
if strings app/platform_layer/picking.pyc | grep -q unpack_archive; then echo "是 OK"; else echo "否 FAIL"; fi
echo -n "  main 有 _collect ？ "
if strings app/main.pyc | grep -q "_collect"; then echo "是 OK"; else echo "否 FAIL"; fi
echo -n "  browser/perm 模块在包内 ？ "
if [ -f app/platform_layer/browser.pyc ] && [ -f app/platform_layer/perm.pyc ]; then echo "是 OK"; else echo "否 FAIL"; fi

echo
echo "=== 2) 权限声明 ==="
for p in MANAGE_EXTERNAL_STORAGE INTERNET WRITE_EXTERNAL_STORAGE; do
    n=$(strings -el AndroidManifest.xml 2>/dev/null | grep -c "$p")
    n2=$(strings AndroidManifest.xml | grep -c "$p")
    echo "  $p : utf16=$n utf8=$n2"
done

echo
echo "=== 3) aapt2 精确列出（若有）==="
AAPT2=$(find /root/.buildozer/android/platform/android-sdk -maxdepth 3 \( -name aapt2 -o -name aapt \) 2>/dev/null | head -1)
if [ -n "${AAPT2:-}" ]; then
    echo "  使用 $AAPT2"
    "$AAPT2" dump permissions "$APK" 2>&1 | head -10
else
    echo "  未找到 aapt2（看上面 utf16 结果）"
fi
