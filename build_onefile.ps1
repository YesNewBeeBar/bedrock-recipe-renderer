# Build a TRUE single-file exe (everything inside, nothing beside it).
# Note: onefile unpacks to a temp dir on first run; later runs reuse it.
$ErrorActionPreference = "Stop"
Set-Location "D:\合成表生成器"
$py = "C:\Python314\python.exe"
$name = "合成表生成器"

$excl = @(
  "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
  "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml",
  "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
  "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
  "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth", "PySide6.QtPositioning",
  "PySide6.QtSerialPort", "PySide6.QtTest", "PySide6.QtSql", "PySide6.QtNfc",
  "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtRemoteObjects", "PySide6.QtSensors",
  "PySide6.QtWebSockets", "PySide6.QtWebChannel", "PySide6.QtDesigner", "PySide6.QtHelp",
  "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSpatialAudio",
  "tkinter", "matplotlib", "numpy", "pandas", "scipy"
)

$a = @(
  "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
  "--name", $name,
  "--icon", "assets\icon.ico",
  "--add-data", "vanilla_cache;vanilla_cache",
  "--add-data", "wiki_cache;wiki_cache",
  "--add-data", "wiki_pinned;wiki_pinned",
  "--add-data", "assets;assets",
  "--add-data", "tags_be.json;.",
  "--add-data", "vanilla_kinds.json;."
)
foreach ($m in $excl) { $a += @("--exclude-module", $m) }
$a += "mcrender_fluent.py"

& $py @a 2>&1 | Select-Object -Last 5
$exe = "dist\$name.exe"
if (Test-Path $exe) {
  "=== OK: $exe  ({0:N1} MB) ===" -f ((Get-Item $exe).Length/1MB)
} else { "=== FAILED ==="; exit 1 }
