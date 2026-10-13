#!/usr/bin/env bash
# 准备 Compose 项目的构建环境：Gradle + 图标资源
set -u
SDK=/root/android-sdk
GRADLE_VER=8.7
GRADLE_DIR=/root/gradle-$GRADLE_VER

if [ ! -x "$GRADLE_DIR/bin/gradle" ]; then
    echo "== 下载 Gradle $GRADLE_VER =="
    cd /tmp
    curl -L -o gradle.zip "https://services.gradle.org/distributions/gradle-$GRADLE_VER-bin.zip" \
        || { echo "下载失败"; exit 1; }
    unzip -q -o gradle.zip -d /root
    rm -f gradle.zip
fi
echo "gradle: $($GRADLE_DIR/bin/gradle --version 2>/dev/null | grep -E '^Gradle')"

PROJ=/mnt/d/合成表生成器移动端/android-compose
# 图标：复用现有 icon.png
mkdir -p "$PROJ/app/src/main/res/mipmap-xxxhdpi"
cp -f "/mnt/d/合成表生成器移动端/android-kivy/icon.png" \
      "$PROJ/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png" 2>/dev/null || true
ls -la "$PROJ/app/src/main/res/mipmap-xxxhdpi/" 2>/dev/null | tail -2

# local.properties 指向 SDK
echo "sdk.dir=$SDK" > "$PROJ/local.properties"
cat "$PROJ/local.properties"
echo "== 完成 =="
