@echo off
setlocal
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0STOP_NELYIO_HTTPS.ps1"
exit /b %ERRORLEVEL%
