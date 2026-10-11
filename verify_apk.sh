#!/usr/bin/env bash
# 构建后核对：内置原版素材 / 应用代码 / 权限
set -u
APK=$(ls -t /root/brr/bin/*.apk | head -1)
echo "APK: $(basename "$APK")  $(du -h "$APK" | cut -f1)"

cd /tmp && rm -rf chk && mkdir chk && cd chk
unzip -o -q "$APK" assets/private.tar AndroidManifest.xml
mkdir app && tar -xf assets/private.tar -C app

echo
echo "=== 内置原版素材 ==="
echo "  vanilla 文件数: $(find app/vanilla -type f 2>/dev/null | wc -l)"
for f in textures/item_texture.json textures/terrain_texture.json blocks.json \
         textures/items/stick.png textures/items/beef_cooked.png textures/items/chicken_cooked.png; do
    if [ -f "app/vanilla/$f" ]; then echo "  有 $f"; else echo "  缺 $f"; fi
done

echo
echo "=== 应用代码 ==="
for f in main.pyc platform_layer/browser.pyc platform_layer/perm.pyc platform_layer/picking.pyc; do
    [ -f "app/$f" ] && echo "  有 $f" || echo "  缺 $f"
done

echo
echo "=== 权限 ==="
AAPT2=$(find /root/.buildozer/android/platform/android-sdk -maxdepth 3 -name aapt2 2>/dev/null | head -1)
if [ -n "${AAPT2:-}" ]; then
    "$AAPT2" dump permissions "$APK" 2>&1 | grep MANAGE_EXTERNAL_STORAGE || echo "  未见 MANAGE_EXTERNAL_STORAGE"
fi
