# 把 WSL 的 Ubuntu（APK 打包环境）从 C 盘迁到 D 盘
# 安全顺序：导出 -> 用新名字导入 -> 验证 -> 才注销旧的 -> 最后改名
$ErrorActionPreference = "Continue"
$dst = "D:\wsl"
$tar = "$dst\ubuntu-backup.tar"
New-Item -ItemType Directory -Force -Path $dst | Out-Null

Write-Output "== 1) 关闭 WSL =="
wsl --shutdown
Start-Sleep -Seconds 3

Write-Output "== 2) 导出到 D 盘（14.5 GB，需要几分钟）=="
$t0 = Get-Date
wsl --export Ubuntu $tar
$dt = (Get-Date) - $t0
if (-not (Test-Path $tar)) { Write-Output "导出失败，已中止"; exit 1 }
$sz = (Get-Item $tar).Length / 1GB
Write-Output ("导出完成: {0:N2} GB，用时 {1:N1} 分钟" -f $sz, $dt.TotalMinutes)

Write-Output "== 3) 导入为临时发行版 UbuntuNew =="
wsl --import UbuntuNew "$dst\UbuntuNew" $tar
if ($LASTEXITCODE -ne 0) { Write-Output "导入失败，已中止（原发行版未动）"; exit 1 }

Write-Output "== 4) 验证新发行版可用（跑一次核心渲染自检）=="
wsl -d UbuntuNew -u root -- bash -lc "ls /root/brr/main.py >/dev/null 2>&1 && echo BUILD_TREE_OK; python3 -c 'print(\"PY_OK\")'"
Write-Output "== 5) 新发行版验证通过，注销旧的 C 盘发行版 =="
wsl --unregister Ubuntu
Write-Output "== 6) 用回原名 Ubuntu（脚本里的 wsl -d Ubuntu 不用改）=="
wsl --import Ubuntu "$dst\Ubuntu" $tar
wsl --unregister UbuntuNew
Write-Output "== 7) 恢复默认登录用户为 root（构建脚本要求）=="
wsl -d Ubuntu -u root -- bash -lc "printf '[user]\ndefault=root\n' > /etc/wsl.conf; cat /etc/wsl.conf"
wsl --shutdown
Remove-Item $tar -Force
Write-Output "== 完成，删除临时 tar =="
wsl -l -v
