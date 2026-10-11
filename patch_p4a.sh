#!/usr/bin/env bash
# 给 p4a 打补丁（build.py 里的 pip install 那处）：装"无 recipe"的包时带上
# Android 目标平台参数，否则宿主 pip 会以 not a supported wheel 拒绝 android_* 轮子。
set -u
P4A=/root/brr/.buildozer/android/platform/python-for-android
cd "$P4A" || exit 1

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
    print("已打补丁 OK")
else:
    i = s.find("no-deps -r requirements.txt")
    print("仍未匹配，附近内容：")
    print(s[max(0, i - 220):i + 120])
PY

echo "=== 校验 ==="
grep -n "platform android_24_arm64_v8a" pythonforandroid/build.py | head -2

echo "=== 重新构建 ==="
cd /root/brr
. .venv-buildozer/bin/activate
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
export ACLOCAL_PATH=/usr/share/aclocal:/usr/local/share/aclocal
buildozer -v android debug > build.log 2>&1
echo "EXIT=$?"
grep -nE "Error code|BUILD SUCCESSFUL|APK |not a supported wheel" build.log | tail -6
ls -la /root/brr/bin/ 2>/dev/null | tail -4
