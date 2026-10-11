# Android 工具链一键安装（Windows / PowerShell 7）
# 全程不需要管理员权限：JDK 与 Android SDK 都用「绿色压缩包 + 解压」装到 D 盘。
# 用法：pwsh -File setup_android_toolchain.ps1
#       pwsh -File setup_android_toolchain.ps1 -SkipSdk      # 只装 briefcase + JDK
# 结果：D:\android-toolchain\{venv, jdk17, sdk}

param(
    [string]$Root = "D:\android-toolchain",
    [switch]$SkipSdk
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Info($m) { Write-Host "[setup] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ ok  ] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[warn ] $m" -ForegroundColor Yellow }

New-Item -ItemType Directory -Force -Path $Root | Out-Null
Info "工具链目录：$Root"

# ---------------------------------------------------------------- 1. briefcase
$venv = Join-Path $Root "venv"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) {
    Info "创建虚拟环境 $venv"
    & C:\Python314\python.exe -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

# curl.exe 在本机受 schannel 吊销检查限制（CRYPT_E_NO_REVOCATION_CHECK），用 Python 下载器
$downloader = Join-Path $PSScriptRoot "android_download.py"
function Get-File($urls, $dest) {
    if ($urls -is [string]) { $urls = @($urls) }
    $args = @($downloader) + $urls + @($dest)
    Info "下载 -> $dest"
    & $py @args
    if (-not (Test-Path $dest)) { throw "下载失败: $($urls -join ' | ')" }
}

Info "安装 briefcase"
& $py -m pip install --quiet --upgrade pip
& $py -m pip install --quiet briefcase
$bc = Join-Path $venv "Scripts\briefcase.exe"
if (Test-Path $bc) { Ok ("briefcase " + (& $bc --version)) }
else { Warn "briefcase 安装失败：Python 3.14 太新时可换 3.12/3.13 建 venv（不影响 APK 内的版本）" }

# ---------------------------------------------------------------- 2. JDK 17
$jdkHome = Join-Path $Root "jdk17"
if (-not (Test-Path (Join-Path $jdkHome "bin\java.exe"))) {
    $zip = Join-Path $Root "jdk17.zip"
    Get-File @(
        "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse",
        "https://mirrors.tuna.tsinghua.edu.cn/Adoptium/17/jdk/x64/windows/" +
            "OpenJDK17U-jdk_x64_windows_hotspot_17.0.13_11.zip",
        "https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.zip"
    ) $zip
    Info "解压 JDK"
    $tmp = Join-Path $Root "jdk-tmp"
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    Move-Item $inner.FullName $jdkHome -Force
    Remove-Item $tmp, $zip -Recurse -Force -ErrorAction SilentlyContinue
}
$env:JAVA_HOME = $jdkHome
$env:PATH = "$jdkHome\bin;$env:PATH"
Ok ("JAVA_HOME = " + $env:JAVA_HOME)
& "$jdkHome\bin\java.exe" -version 2>&1 | Select-Object -First 1

if ($SkipSdk) { Info "跳过 Android SDK（-SkipSdk）"; exit 0 }

# ---------------------------------------------------------------- 3. Android SDK
$sdk = Join-Path $Root "sdk"
$cmdline = Join-Path $sdk "cmdline-tools\latest"
if (-not (Test-Path (Join-Path $cmdline "bin\sdkmanager.bat"))) {
    Info "从 Google 仓库索引里取最新 command-line-tools 地址"
    $url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    try {
        $xml = Invoke-RestMethod "https://dl.google.com/android/repository/repository2-1.xml"
        $found = ($xml.sdkRepository.remotePackage |
                  Where-Object { $_.path -eq "cmdline-tools;latest" } |
                  ForEach-Object { $_.archives.archive | Where-Object { $_.hostOs -eq "windows" } } |
                  Select-Object -First 1).complete.url
        if ($found) { $url = $found }
    } catch { Warn "索引解析失败，用默认地址" }
    $zip = Join-Path $Root "cmdtools.zip"
    Get-File @($url) $zip
    $tmp = Join-Path $Root "cmdtools-tmp"
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    New-Item -ItemType Directory -Force -Path (Split-Path $cmdline) | Out-Null
    Move-Item (Join-Path $tmp "cmdline-tools") $cmdline -Force
    Remove-Item $tmp, $zip -Recurse -Force -ErrorAction SilentlyContinue
}
$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
Ok ("ANDROID_HOME = " + $env:ANDROID_HOME)

$sdkmanager = Join-Path $cmdline "bin\sdkmanager.bat"
Info "接受 SDK 许可协议"
$yes = ("y" + [Environment]::NewLine) * 50
$yes | & $sdkmanager --sdk_root="$sdk" --licenses 2>&1 | Select-Object -Last 3

Info "安装 SDK 组件（platform-tools / android-34 / build-tools / ndk，约 2~4 GB，较慢）"
& $sdkmanager --sdk_root="$sdk" "platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;26.1.10909125" 2>&1 |
    Select-Object -Last 12

# ---------------------------------------------------------------- 4. 自检
Info "运行 briefcase doctor"
& $bc doctor 2>&1 | Select-Object -First 40

Write-Host ""
Ok "完成。请在新终端里设置一次环境变量（或每次跑本脚本都会自动设置）："
Write-Host "    setx JAVA_HOME `"$jdkHome`"" -ForegroundColor DarkGray
Write-Host "    setx ANDROID_HOME `"$sdk`"" -ForegroundColor DarkGray
Write-Host "然后：cd D:\合成表生成器移动端\android ; briefcase create android" -ForegroundColor DarkGray
