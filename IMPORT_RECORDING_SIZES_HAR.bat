@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
set "HAR=%~1"
if "%HAR%"=="" set /p HAR=Chemin du fichier HAR : 
if "%HAR%"=="" exit /b 1
"%PY%" recording_sizes.py --har "%HAR%"
echo.
pause
