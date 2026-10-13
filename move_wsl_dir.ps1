# 直接把 WSL 的数据目录移到 D 盘并软链接（比 export/import 快且稳）
$ErrorActionPreference = "Continue"
$guid = "{9906f4a6-6cb2-4042-831f-fe652bfcfa70}"
$src = "$env:LOCALAPPDATA\wsl\$guid"
$dstRoot = "D:\wsl"
$dst = "$dstRoot\$guid"

Write-Output "== 1) 关闭 WSL 并确认已停 =="
wsl --shutdown
Start-Sleep -Seconds 5
$still = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match "wsl|vmmem|wslhost" }
if ($still) {
    Write-Output "仍有 WSL 进程，先等它们退出："
    $still | Select-Object ProcessName, Id | Format-Table -AutoSize
    Start-Sleep -Seconds 10
}

if (-not (Test-Path $src)) { Write-Output "找不到 $src"; exit 1 }
$sz = ((Get-ChildItem $src -Recurse -Force -ErrorAction SilentlyContinue |
        Measure-Object Length -Sum).Sum) / 1GB
Write-Output ("== 2) 搬运 {0:N2} GB 到 D 盘 ==" -f $sz)
New-Item -ItemType Directory -Force -Path $dstRoot | Out-Null
robocopy $src $dst /E /MOVE /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null

if (Test-Path "$dst\ext4.vhdx") {
    if (Test-Path $src) { Remove-Item $src -Recurse -Force -ErrorAction SilentlyContinue }
    cmd /c mklink /J "$src" "$dst" | Out-Null
    Write-Output "== 3) 软链接建立：$src -> $dst"
} else {
    Write-Output "== ✗ 目标缺少 ext4.vhdx，未建立链接，请检查 $dst"
    exit 1
}

Write-Output "== 4) 启动 WSL 验证 =="
wsl -d Ubuntu -u root -- bash -lc "echo WSL_OK; ls /root/brr/main.py >/dev/null 2>&1 && echo BUILD_TREE_OK; python3 --version"
Write-Output "== 5) 磁盘现状 =="
Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in "C","D" } |
    Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize
