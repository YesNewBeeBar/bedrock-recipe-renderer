# 桌面端 1.1.0 一条龙：主程序(onedir) -> app.zip -> 自解压安装器 -> 交付到 D:\演示
$ErrorActionPreference = "Stop"
Set-Location "D:\合成表生成器"
$py = "C:\Python314\python.exe"

Write-Output "=== ① 主程序 onedir（含 panel/物品判定/动态纹理修复）==="
$excl = @(
  "PySide6.QtWebEngineCore","PySide6.QtWebEngineWidgets","PySide6.QtWebEngineQuick",
  "PySide6.QtQuick","PySide6.QtQuick3D","PySide6.QtQml",
  "PySide6.Qt3DCore","PySide6.Qt3DRender","PySide6.Qt3DAnimation","PySide6.Qt3DExtras",
  "PySide6.QtCharts","PySide6.QtDataVisualization","PySide6.QtMultimedia",
  "PySide6.QtMultimediaWidgets","PySide6.QtBluetooth","PySide6.QtPositioning",
  "PySide6.QtSerialPort","PySide6.QtTest","PySide6.QtSql","PySide6.QtNfc",
  "PySide6.QtPdf","PySide6.QtPdfWidgets","PySide6.QtRemoteObjects","PySide6.QtSensors",
  "PySide6.QtWebSockets","PySide6.QtWebChannel","PySide6.QtDesigner","PySide6.QtHelp",
  "PySide6.QtOpenGL","PySide6.QtOpenGLWidgets","PySide6.QtSpatialAudio",
  "tkinter","matplotlib","numpy","pandas","scipy"
)
$a = @("-m","PyInstaller","--noconfirm","--clean","--windowed",
  "--name","bedrock-recipe-renderer-fluent",
  "--icon","assets\icon.ico",
  "--add-data","vanilla_cache;vanilla_cache",
  "--add-data","wiki_cache;wiki_cache",
  "--add-data","wiki_pinned;wiki_pinned",
  "--add-data","assets;assets",
  "--add-data","tags_be.json;.",
  "--add-data","vanilla_kinds.json;.")
foreach ($m in $excl) { $a += @("--exclude-module", $m) }
$a += "mcrender_fluent.py"
& $py @a 2>&1 | Select-Object -Last 3
$main = "dist\bedrock-recipe-renderer-fluent\bedrock-recipe-renderer-fluent.exe"
if (-not (Test-Path $main)) { Write-Output "[FAILED] 主程序未产出"; exit 1 }
Write-Output ("  主程序 OK: {0:N1} MB" -f ((Get-Item $main).Length/1MB))

Write-Output "=== ② 压成 app.zip ==="
Remove-Item "_sfx\app.zip" -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "dist\bedrock-recipe-renderer-fluent\*" -DestinationPath "_sfx\app.zip" -CompressionLevel Optimal
Write-Output ("  app.zip: {0:N1} MB" -f ((Get-Item "_sfx\app.zip").Length/1MB))

Write-Output "=== ③ 自解压安装器 ==="
$b = @("-m","PyInstaller","--noconfirm","--clean","--onefile","--windowed",
  "--name","bedrock-recipe-renderer-installer","--icon","assets\icon.ico",
  "--add-data","_sfx\app.zip;.",
  "--exclude-module","PySide6","--exclude-module","tkinter","--exclude-module","matplotlib",
  "--exclude-module","numpy","--exclude-module","pandas","--exclude-module","PIL",
  "installer_stub.py")
& $py @b 2>&1 | Select-Object -Last 3

$ins = "dist\bedrock-recipe-renderer-installer.exe"
if (-not (Test-Path $ins)) { Write-Output "[FAILED] 安装器未产出"; exit 1 }
Copy-Item $ins "D:\演示\bedrock-recipe-renderer-installer.exe" -Force
Write-Output ("=== 完成: D:\演示\bedrock-recipe-renderer-installer.exe  {0:N1} MB ===" -f ((Get-Item $ins).Length/1MB))
