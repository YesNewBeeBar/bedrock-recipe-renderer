#!/usr/bin/env bash
set -u
export ANDROID_SDK_ROOT=/root/android-sdk
export ANDROID_HOME=/root/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd "/mnt/d/合成表生成器移动端/android-compose" || exit 1
/root/gradle-8.7/bin/gradle :app:testDebugUnitTest --no-daemon --console=plain 2>&1 | tail -35
echo "== 产出的截图 =="
find . -name "ui_*.png" 2>/dev/null | head -5
