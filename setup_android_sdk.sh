#!/usr/bin/env bash
# 安装一套可供 AGP/Chaquopy 使用的 Android SDK（放到 D 盘的 WSL 里，不占 C 盘）
set -u
SDK=/root/android-sdk
CMDLINE=$SDK/cmdline-tools/latest
mkdir -p "$SDK/cmdline-tools"

if [ ! -x "$CMDLINE/bin/sdkmanager" ]; then
    echo "== 下载 command-line tools =="
    cd /tmp
    curl -L -o cmdtools.zip \
      https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip \
      || { echo "下载失败"; exit 1; }
    unzip -q -o cmdtools.zip -d "$SDK/cmdline-tools"
    mv "$SDK/cmdline-tools/cmdline-tools" "$CMDLINE" 2>/dev/null || true
    rm -f cmdtools.zip
fi
echo "== sdkmanager 就绪: $($CMDLINE/bin/sdkmanager --version 2>/dev/null | tail -1)"

export ANDROID_SDK_ROOT="$SDK"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"

yes | "$CMDLINE/bin/sdkmanager" --licenses >/dev/null 2>&1
echo "== 安装 platform-tools / platform 34 / build-tools 34 =="
"$CMDLINE/bin/sdkmanager" --install \
    "platform-tools" "platforms;android-34" "build-tools;34.0.0" 2>&1 | tail -4

echo "== 结果 =="
ls "$SDK" | tr '\n' ' '; echo
ls "$SDK/platforms" 2>/dev/null | tr '\n' ' '; echo
ls "$SDK/build-tools" 2>/dev/null | tr '\n' ' '; echo
du -sh "$SDK"
