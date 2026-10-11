#!/usr/bin/env bash
# WSL/Ubuntu 里的一键准备：换国内源 → 装依赖 → 把工程搬到纯 ASCII 路径 → 复用已装的 Android SDK
# 用法（在 WSL 里）：  bash wsl_prepare.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"

# 以 root 直接跑时（跳过用户创建的情况）不需要 sudo
if [ "$(id -u)" = "0" ]; then SUDO=""; else SUDO="sudo"; fi

WIN_SDK="/mnt/d/android-toolchain/sdk"
WORK="$HOME/brr"                     # 纯 ASCII 工程目录，避免 NDK 遇到中文路径

echo "==> 1/4 换 apt 源（清华），失败就跳过"
if [ -f /etc/apt/sources.list ]; then
    ${SUDO:+$SUDO }cp -n /etc/apt/sources.list /etc/apt/sources.list.bak || true
    ${SUDO:+$SUDO }sed -i 's|http://archive.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g;
                 s|http://security.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list || true
fi
if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
    ${SUDO:+$SUDO }sed -i 's|http://archive.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g;
                 s|http://security.ubuntu.com|https://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/ubuntu.sources || true
fi

echo "==> 2/4 安装依赖"
${SUDO:+$SUDO }apt-get update -qq
${SUDO:+$SUDO }apt-get install -y --no-install-recommends \
    git zip unzip rsync openjdk-17-jdk python3-pip python3-venv \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
    cmake libffi-dev libssl-dev automake build-essential ccache

echo "==> 3/4 把工程复制到 $WORK（纯 ASCII 路径）"
mkdir -p "$WORK"
rsync -a --delete \
    --exclude '.venv-buildozer' --exclude '.buildozer' --exclude 'bin' \
    --exclude '__pycache__' "$HERE/" "$WORK/"

echo "==> 4/4 准备 buildozer"
cd "$WORK"
[ -d .venv-buildozer ] || python3 -m venv .venv-buildozer
. .venv-buildozer/bin/activate
pip install -q --upgrade pip setuptools wheel
pip install -q buildozer cython
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >/dev/null

echo
echo "环境就绪。若想复用 Windows 侧已装好的 Android SDK（省 2~4 GB 下载）："
if [ -d "$WIN_SDK" ]; then
    echo "   在 buildozer.spec 的 [app] 段加一行："
    echo "       android.sdk_path = $WIN_SDK"
fi
echo
echo "开始构建："
echo "   cd $WORK && . .venv-buildozer/bin/activate && buildozer -v android debug 2>&1 | tee build.log"
