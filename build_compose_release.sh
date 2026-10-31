#!/usr/bin/env bash
set -u
export ANDROID_SDK_ROOT=/root/android-sdk
export ANDROID_HOME=/root/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/android-compose" || exit 1
/root/gradle-8.7/bin/gradle assembleRelease --no-daemon --console=plain 2>&1 | tail -20
APK=$(ls -t app/build/outputs/apk/release/*.apk 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    mkdir -p "${OUT_DIR:-$ROOT/release}"; cp -f "$APK" "${OUT_DIR:-$ROOT/release}/合成表生成器-Compose版-release.apk"
    echo "== release: $APK ($(du -h "$APK" | cut -f1)) 已复制到 ${OUT_DIR:-$ROOT/release} =="
else
    echo "== release 未产出 =="; exit 1
fi
