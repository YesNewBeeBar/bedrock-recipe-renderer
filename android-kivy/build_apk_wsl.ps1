# 在 Windows 里一键驱动 WSL 完成 Kivy/Buildozer 构建。
# 前置：已安装 WSL2 + Ubuntu（管理员 PowerShell 跑一次：wsl --install -d Ubuntu）
#
# 用法：pwsh -File build_apk_wsl.ps1
#       pwsh -File build_apk_wsl.ps1 -Distro Ubuntu-22.04 -Clean

param(
    [string]$Distro = "",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# ---- 0. 检查 WSL ----
$wslOk = $true
try { wsl.exe -l -q 2>$null | Out-Null } catch { $wslOk = $false }
if (-not $wslOk) {
    Write-Host "没有可用的 WSL。请先用【管理员】PowerShell 执行：" -ForegroundColor Yellow
    Write-Host "    wsl --install -d Ubuntu" -ForegroundColor White
    Write-Host "装完重启，再跑一次本脚本。" -ForegroundColor Yellow
    exit 1
}
if (-not $Distro) {
    $Distro = (wsl.exe -l -q 2>$null | Select-Object -First 1)
    if (-not $Distro) { Write-Host "没有已安装的发行版，请先 wsl --install -d Ubuntu"; exit 1 }
    $Distro = $Distro.Trim()
}
Write-Host "[wsl] 发行版：$Distro" -ForegroundColor Cyan

# ---- 1. 把工程路径换算成 WSL 路径 ----
$drive = $here.Substring(0, 1).ToLower()
$rest = $here.Substring(2).Replace('\', '/')
$wslPath = "/mnt/$drive$rest"
Write-Host "[wsl] 工程路径：$wslPath" -ForegroundColor Cyan

# ---- 2. 准备环境（幂等）----
$setup = @"
set -e
cd '$wslPath'
if [ ! -x "`$HOME/brr/.venv-buildozer/bin/buildozer" ]; then
  bash wsl_prepare.sh                      # 换源 + 装依赖 + 复制到 ~/brr + 装 buildozer
fi
"@
Write-Host "[wsl] 准备构建环境（首次会装系统依赖并复制工程到 ~/brr，需要 sudo 密码）" -ForegroundColor Cyan
wsl.exe -d $Distro -- bash -lc $setup

# ---- 3. 构建 ----
if ($Clean) {
    Write-Host "[wsl] 清理旧的构建产物" -ForegroundColor Yellow
    wsl.exe -d $Distro -- bash -lc "cd '$wslPath' && . .venv-buildozer/bin/activate && buildozer android clean"
}
$build = @"
cd "`$HOME/brr"
. .venv-buildozer/bin/activate
export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
buildozer -v android debug 2>&1 | tail -80
ls -la bin/ 2>/dev/null || true
"@
Write-Host "[wsl] 开始构建（首次 30~60 分钟，会下载 SDK/NDK）" -ForegroundColor Cyan
wsl.exe -d $Distro -- bash -lc $build

# ---- 4. 把 APK 拷回 Windows ----
$src = Join-Path $here "bin"
if (Test-Path $src) {
    Write-Host "[ok] APK 目录：$src" -ForegroundColor Green
    Get-ChildItem $src -Filter *.apk | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}} | Format-Table -AutoSize
    Write-Host "把 APK 传到手机安装即可（Android 需允许「安装未知来源应用」）。" -ForegroundColor Green
} else {
    Write-Host "[warn] 没找到 bin/ 目录，请检查上面的构建日志" -ForegroundColor Yellow
}
