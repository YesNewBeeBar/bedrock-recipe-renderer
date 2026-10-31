#!/usr/bin/env bash
# 构建 Kotlin + Compose + Chaquopy 的 APK
set -u
export ANDROID_SDK_ROOT=/root/android-sdk
export ANDROID_HOME=/root/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
GRADLE=/root/gradle-8.7/bin/gradle
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJ="$ROOT/android-compose"

cd "$PROJ" || exit 1
echo "== 构建开始 $(date +%H:%M:%S) =="
"$GRADLE" assembleDebug --no-daemon --console=plain 2>&1 | tail -45

APK=$(ls -t app/build/outputs/apk/debug/*.apk 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    echo
    echo "== 产出: $APK ($(du -h "$APK" | cut -f1)) =="
    mkdir -p "${OUT_DIR:-$ROOT/release}"; cp -f "$APK" "${OUT_DIR:-$ROOT/release}/合成表生成器-Compose版-debug.apk" && echo "已复制到 ${OUT_DIR:-$ROOT/release}"
else
    echo
    echo "== 没有产出 APK（见上面的错误）=="
    exit 1
fi
