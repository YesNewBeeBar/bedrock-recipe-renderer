# Build the Fluent (PySide6) desktop exe. No Chinese in this file on purpose:
# cmd/PowerShell both choke on mixed encodings with line continuations.
$ErrorActionPreference = "Stop"
Set-Location "D:\合成表生成器"

$py = "C:\Python314\python.exe"
$name = "bedrock-recipe-renderer-fluent"

$excl = @(
  "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
  "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml",
  "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DAnimation",
  "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
  "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth", "PySide6.QtPositioning",
  "PySide6.QtSerialPort", "PySide6.QtTest", "PySide6.QtSql",
  "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtNfc",
  "PySide6.QtRemoteObjects", "PySide6.QtSensors", "PySide6.QtWebSockets",
  "PySide6.QtWebChannel", "PySide6.QtDesigner", "PySide6.QtHelp",
  "tkinter", "matplotlib", "numpy", "pandas", "scipy", "PIL.ImageQt"
)

$args = @(
  "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
  "--name", $name,
  "--icon", "assets\icon.ico",
  "--add-data", "vanilla_cache;vanilla_cache",
  "--add-data", "wiki_cache;wiki_cache",
  "--add-data", "wiki_pinned;wiki_pinned",
  "--add-data", "assets;assets",
  "--add-data", "tags_be.json;.",
  "--add-data", "vanilla_kinds.json;."
)
foreach ($m in $excl) { $args += @("--exclude-module", $m) }
$args += "mcrender_fluent.py"

Write-Output "=== PyInstaller start ==="
& $py @args 2>&1 | Select-Object -Last 12
if ($LASTEXITCODE -ne 0) { Write-Output "[FAILED] exit=$LASTEXITCODE"; exit 1 }
$exe = "dist\$name.exe"
if (Test-Path $exe) {
  $f = Get-Item $exe
  Write-Output ("=== OK: {0}  {1:N1} MB ===" -f $exe, ($f.Length / 1MB))
} else {
  Write-Output "[FAILED] exe not produced"
  exit 1
}
