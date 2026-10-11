#!/usr/bin/env bash
# 在 WSL / Linux 里准备 Buildozer 环境（Ubuntu 22.04+ 实测）
# 用法：  bash setup_wsl_buildozer.sh
set -e

echo "==> 安装系统依赖"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    git zip unzip openjdk-17-jdk python3-pip python3-venv \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev automake build-essential ccache

echo "==> 建虚拟环境 + 安装 buildozer / cython"
cd "$(dirname "$0")"
python3 -m venv .venv-buildozer
. .venv-buildozer/bin/activate
pip install -q --upgrade pip setuptools wheel
pip install -q buildozer cython

echo
echo "完成。之后执行："
echo "  cd $(pwd)"
echo "  . .venv-buildozer/bin/activate"
echo "  buildozer -v android debug 2>&1 | tee build.log"
echo
echo "首次构建会自动下载 Android SDK/NDK（约 2~4 GB，耗时较长）。"
echo "国内加速：export BUILDOZER_ANDROID_SDK_HOME 指向已装好的 SDK；"
echo "         pip 用清华源；Gradle 用腾讯镜像（见 buildozer.spec 旁的说明）。"
