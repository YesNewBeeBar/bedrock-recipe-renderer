# Official desktop build: PySide6 + Fluent widgets (mcrender_fluent.py).
# The tkinter UI is archived under legacy/ and is no longer built.
$ErrorActionPreference = "Stop"
Set-Location "D:\合成表生成器"
$py = "C:\Python314\python.exe"
$a = @("-m","PyInstaller","--noconfirm","--clean","--windowed",
 "--name","bedrock-recipe-renderer",
 "--icon","assets\icon.ico",
 "--add-data","vanilla_cache;vanilla_cache",
 "--add-data","wiki_cache;wiki_cache",
 "--add-data","wiki_pinned;wiki_pinned",
 "--add-data","assets;assets",
 "--add-data","tags_be.json;.",
 "--add-data","vanilla_kinds.json;.",
 "--exclude-module","PySide6.QtWebEngineCore","--exclude-module","PySide6.QtQuick",
 "--exclude-module","PySide6.QtQml","--exclude-module","PySide6.Qt3DCore",
 "--exclude-module","PySide6.QtCharts","--exclude-module","PySide6.QtMultimedia",
 "--exclude-module","PySide6.QtSql","--exclude-module","PySide6.QtPdf",
 "--exclude-module","tkinter","--exclude-module","matplotlib",
 "--exclude-module","numpy","--exclude-module","pandas",
 "mcrender_fluent.py")
& $py @a 2>&1 | Select-Object -Last 5
$exe = "dist\bedrock-recipe-renderer\bedrock-recipe-renderer.exe"
if (Test-Path $exe) { "=== OK: $exe  ({0:N1} MB exe) ===" -f ((Get-Item $exe).Length/1MB) }
else { "=== FAILED ==="; exit 1 }
