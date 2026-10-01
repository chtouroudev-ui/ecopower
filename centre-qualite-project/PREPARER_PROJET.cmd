@echo off
setlocal
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0OUTILS_PROJET.ps1" -Action Prepare
set ERR=%ERRORLEVEL%
echo.
pause
exit /b %ERR%
