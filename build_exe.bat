@echo off
rem Rebuild the executables with PyInstaller.
rem Output: dist\bedrock-recipe-renderer.exe (GUI) and dist\bedrock-recipe-renderer-cli.exe
rem This file is ASCII-only on purpose: cmd reads .bat in the OEM codepage.
setlocal
cd /d "%~dp0"

rem PyInstaller needs these data folders to exist; a fresh clone has no caches yet
if not exist "vanilla_cache" mkdir "vanilla_cache"
if not exist "wiki_cache" mkdir "wiki_cache"
if not exist "assets\ui" mkdir "assets\ui"

set PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe
if not exist "%PY%" set PY=C:\Python314\python.exe
if not exist "%PY%" set PY=python

echo [1/2] building GUI exe ...
"%PY%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "bedrock-recipe-renderer" --icon "assets/icon.ico" ^
  --add-data "mcrender/glyphs.json;mcrender" ^
  --add-data "mcrender/sprites.json;mcrender" ^
  --add-data "assets;assets" ^
  --add-data "vanilla_cache;vanilla_cache" ^
  --add-data "wiki_cache;wiki_cache" ^
  --exclude-module matplotlib --exclude-module numpy --exclude-module pandas ^
  mcrender_gui.py
if errorlevel 1 goto fail

echo [2/2] building CLI exe ...
"%PY%" -m PyInstaller --noconfirm --onefile --console ^
  --name "bedrock-recipe-renderer-cli" --icon "assets/icon.ico" ^
  --add-data "mcrender/glyphs.json;mcrender" ^
  --add-data "mcrender/sprites.json;mcrender" ^
  --add-data "assets;assets" ^
  --add-data "vanilla_cache;vanilla_cache" ^
  --add-data "wiki_cache;wiki_cache" ^
  --exclude-module matplotlib --exclude-module numpy --exclude-module pandas ^
  mcrender_gui.py
if errorlevel 1 goto fail

echo.
echo Done. See dist\
goto :eof

:fail
echo.
echo Build failed.
exit /b 1
