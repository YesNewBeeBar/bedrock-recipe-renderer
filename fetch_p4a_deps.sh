#!/usr/bin/env bash
# 把 p4a 需要的、在国内被墙的源码包预先放进它的下载缓存。
# 缓存目录：$HOME/.buildozer/android/packages，文件名必须是 URL 的 basename。
set -u
CACHE="${HOME}/.buildozer/android/packages"
mkdir -p "$CACHE"
cd "$CACHE"

fetch() {   # fetch <文件名> <url1> [url2...]
    name="$1"; shift
    if [ -s "$name" ]; then echo "[skip] $name 已存在"; return 0; fi
    for u in "$@"; do
        echo "[get ] $name  <-  $u"
        if timeout 180 curl -fL --retry 2 -o "$name.part" "$u" 2>/dev/null && [ -s "$name.part" ]; then
            mv "$name.part" "$name"
            echo "[ok  ] $name  $(du -h "$name" | cut -f1)"
            return 0
        fi
        rm -f "$name.part"
    done
    echo "[FAIL] $name 所有镜像都失败"
    return 1
}

# openssl：openssl.org 国内被重置，走清华/阿里镜像
fetch openssl-3.3.1.tar.gz \
    "https://mirrors.tuna.tsinghua.edu.cn/openssl/source/openssl-3.3.1.tar.gz" \
    "https://mirrors.aliyun.com/openssl/source/openssl-3.3.1.tar.gz" \
    "https://mirrors.cloud.tencent.com/openssl/source/openssl-3.3.1.tar.gz"

# GitHub 上的一般能下，但先用镜像更稳
fetch libjpeg-turbo-2.0.1.tar.gz \
    "https://ghfast.top/https://github.com/libjpeg-turbo/libjpeg-turbo/archive/2.0.1.tar.gz" \
    "https://github.com/libjpeg-turbo/libjpeg-turbo/archive/2.0.1.tar.gz"

fetch libffi-3.4.2.tar.gz \
    "https://ghfast.top/https://github.com/libffi/libffi/archive/v3.4.2.tar.gz" \
    "https://github.com/libffi/libffi/archive/v3.4.2.tar.gz"

ls -la "$CACHE" | head -20
