#!/usr/bin/env bash
# 重建 p4a（用 Windows 侧完好副本）+ 只把文本脚本转 LF + 重打 pip 平台补丁 + 构建
set -u
P4A=/root/brr/.buildozer/android/platform/python-for-android

echo "=== 1) 用 Windows 侧副本重建 p4a ==="
rm -rf "$P4A"
cp -r /mnt/d/android-toolchain/p4a "$P4A"
cd "$P4A"
git log --oneline -1

echo "=== 2) 只转文本文件为 LF（不动 .git 与二进制）==="
find . -path ./.git -prune -o -type f \
     \( -name '*.sh' -o -name 'gradlew' -o -name '*.gradle' \
        -o -name '*.properties' -o -name '*.template' -o -name '*.py' \) \
     -exec sed -i 's/\r$//' {} + 2>/dev/null
echo "已完成"

echo "=== 3) 重打 pip 平台补丁 ==="
python3 - <<'PY'
import io
p = "pythonforandroid/build.py"
s = io.open(p, encoding="utf-8").read()
old = '"install -v --target \'{0}\' --no-deps -r requirements.txt"'
new = ('"install -v --target \'{0}\' --no-deps '
       '--platform android_24_arm64_v8a --python-version 3.14 '
       '--implementation cp --abi cp314 --only-binary=:all: '
       '-r requirements.txt"')
if old in s:
    io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
    print("pip 平台补丁 OK")
else:
    print("补丁未应用（可能已打过）")
PY

echo "=== 4) 构建 ==="
cd /root/brr
. .venv-buildozer/bin/activate
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export ACLOCAL_PATH=/usr/share/aclocal:/usr/local/share/aclocal
buildozer -v android debug > build.log 2>&1
echo "buildozer 退出码: $?"
grep -nE "BUILD SUCCESSFUL|APK |Error code|not a supported wheel" build.log | tail -6
mkdir -p /mnt/d/演示
if ls bin/*.apk >/dev/null 2>&1; then
    cp -v bin/*.apk /mnt/d/演示/
    echo "APK 已复制到 D:\\演示\\"
else
    echo "本轮未产出 APK，最后 15 行日志："
    tail -15 build.log | sed 's/\x1b\[[0-9;]*m//g'
fi
