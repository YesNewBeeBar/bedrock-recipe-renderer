#!/usr/bin/env bash
set -u
export ANDROID_SDK_ROOT=/root/android-sdk
export ANDROID_HOME=/root/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
cd "/mnt/d/合成表生成器移动端/android-compose" || exit 1
/root/gradle-8.7/bin/gradle :app:testDebugUnitTest --tests "com.yesnewbeebar.brr.UiScreenshotTest" \
    --no-daemon --console=plain 2>&1 | tail -22
echo "== 截图产物 =="
find app -name "ui-*.png" 2>/dev/null | head -4
ls -la app/build/ui-*.png 2>/dev/null | head -4
