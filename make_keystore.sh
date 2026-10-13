#!/usr/bin/env bash
# 生成 release 签名用的 keystore（放在项目里，密码固定，仅本机自用）
set -u
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
KS="/mnt/d/合成表生成器移动端/android-compose/brr-release.jks"

if [ -f "$KS" ]; then
    echo "已存在: $KS"
    ls -la "$KS"
    exit 0
fi

"$JAVA_HOME/bin/keytool" -genkeypair -v \
    -keystore "$KS" \
    -alias brr \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass brr-release -keypass brr-release \
    -dname "CN=BRR, OU=Personal, O=NewBeeBar, L=CN, ST=CN, C=CN" 2>&1 | tail -4

if [ -f "$KS" ]; then
    echo "OK: $KS"
    ls -la "$KS"
else
    echo "FAILED"
    exit 1
fi
