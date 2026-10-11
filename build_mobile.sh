#!/usr/bin/env bash
# 移动端构建：把工程同步到 WSL 的 /root/brr → buildozer 出 APK → 拷到 D:\演示
# 用法（在 Windows 侧）：wsl -d Ubuntu -u root -- bash /root/build_mobile.sh
set -u

SRC=/mnt/d/合成表生成器移动端/android-kivy
OUT=/mnt/d/演示
cd /root/brr || exit 1

echo "=== 1) 同步源码 ==="
[ -d "$SRC/vanilla" ] && { rm -rf vanilla; cp -r "$SRC/vanilla" .; }
cp -f "$SRC/main.py" .
cp -f "$SRC/buildozer.spec" .
mkdir -p platform_layer mcrender
cp -f "$SRC/platform_layer/"*.py platform_layer/
cp -f "$SRC/mcrender/"*.py mcrender/
[ -d "$SRC/fonts" ] && { mkdir -p fonts; cp -f "$SRC/fonts/"* fonts/ 2>/dev/null || true; }
find . -maxdepth 2 -name '*.py' -exec sed -i 's/\r$//' {} + 2>/dev/null || true
echo "  vanilla 文件数: $(find vanilla -type f 2>/dev/null | wc -l)"
echo "  platform_layer: $(ls platform_layer/*.py | wc -l) 个模块"

echo "=== 2) 构建 ==="
# shellcheck disable=SC1091
. .venv-buildozer/bin/activate
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export ACLOCAL_PATH=/usr/share/aclocal:/usr/local/share/aclocal
buildozer -v android debug > build.log 2>&1
if ! grep -q 'BUILD SUCCESSFUL' build.log; then
    echo "!! 构建失败，日志尾部："
    tail -25 build.log | sed 's/\x1b\[[0-9;]*m//g'
    exit 1
fi
grep -E 'BUILD SUCCESSFUL' build.log | tail -1

APK=$(ls -t bin/*.apk | head -1)
echo "=== 3) 输出 ==="
echo "  APK: $APK  ($(du -h "$APK" | cut -f1))"
mkdir -p "$OUT"
rm -f "$OUT"/*.apk
cp -f "$APK" "$OUT"/
cp -f "$APK" "$OUT/合成表生成器-内置浏览器版.apk"
ls -la "$OUT"/*.apk
