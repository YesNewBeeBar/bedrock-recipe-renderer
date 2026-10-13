# 把 DSH 的数据目录整体迁到 D 盘（保留插件、记忆、会话，只是换位置）
# 必须在**完全退出 DSH**（含后台托盘）之后运行。
$ErrorActionPreference = "Continue"

$running = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ProcessName -match "dsh|DeepSeek|electron" }
if ($running) {
    Write-Output "检测到 DSH 仍在运行，请先完全退出："
    $running | Select-Object ProcessName, Id | Format-Table -AutoSize
    exit 1
}

$src = "$env:USERPROFILE\.dsh"
$dstRoot = "D:\dsh-data"
$dst = "$dstRoot\.dsh"

New-Item -ItemType Directory -Force -Path $dstRoot | Out-Null

if ((Test-Path $src) -and -not (Get-Item $src -Force).LinkType) {
    $sz = ((Get-ChildItem $src -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object Length -Sum).Sum) / 1MB
    Write-Output ("开始迁移 {0:N0} MB ..." -f $sz)
    robocopy $src $dst /E /MOVE /NFL /NDL /NJH /NJS /R:1 /W:1 | Out-Null
    if (Test-Path $src) { Remove-Item $src -Recurse -Force -ErrorAction SilentlyContinue }
    cmd /c mklink /J "$src" "$dst" | Out-Null
    if (Test-Path "$src\sessions") {
        Write-Output "✓ 迁移完成：$src -> $dst（会话/插件/记忆都保留）"
    } else {
        Write-Output "✗ 软链接异常，请检查 $src"
    }
} elseif ((Get-Item $src -Force).LinkType) {
    Write-Output "已经是链接：$((Get-Item $src -Force).Target)"
} else {
    Write-Output "未找到 $src"
}

Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Name -in "C","D" } |
    Select-Object Name, @{n='FreeGB';e={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize
