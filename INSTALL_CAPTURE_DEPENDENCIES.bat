@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_CAPTURE_DEPENDENCIES.ps1"
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
