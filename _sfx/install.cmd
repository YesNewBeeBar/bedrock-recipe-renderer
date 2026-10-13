@echo off
chcp 65001 >nul
rem 由自解压包调用的安装脚本：把程序装到固定目录并建快捷方式，然后启动。
set "TARGET=%LOCALAPPDATA%\BRR"
set "SRC=%~dp0app"

echo 正在安装到 %TARGET% ...
if not exist "%TARGET%" mkdir "%TARGET%"
robocopy "%SRC%" "%TARGET%" /E /NFL /NDL /NJH /NJS /R:1 /W:1 >nul

set "EXE=%TARGET%\合成表生成器.exe"
if not exist "%EXE%" (
  echo 安装失败：找不到 %EXE%
  pause
  exit /b 1
)

rem 桌面快捷方式（用 PowerShell 生成，避免依赖第三方工具）
powershell -NoProfile -Command ^
  "$s=New-Object -ComObject WScript.Shell; $l=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\合成表生成器.lnk'); $l.TargetPath='%EXE%'; $l.WorkingDirectory='%TARGET%'; $l.IconLocation='%EXE%'; $l.Description='Minecraft 基岩版合成表出图工具'; $l.Save()" >nul 2>&1

echo 安装完成，正在启动 ...
start "" "%EXE%"
exit
