@echo off
rem ===========================================================
rem  Crafting-recipe renderer launcher.
rem  Drag recipe json files (or a whole recipes folder) onto this
rem  file; the images go to the folder set in config.json.
rem  Comments are ASCII on purpose: cmd parses .bat files in the
rem  OEM codepage, so Chinese text here breaks the parser.
rem ===========================================================
setlocal
set "HERE=%~dp0"

set "PYW=pythonw.exe"
if exist "C:\Python314\pythonw.exe" set "PYW=C:\Python314\pythonw.exe"

if "%~1"=="" (
  start "" "%PYW%" "%HERE%mcrender_gui.py"
) else (
  start "" "%PYW%" "%HERE%mcrender_gui.py" %*
)
exit /b
