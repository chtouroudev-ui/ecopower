@echo off
setlocal
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0DIAGNOSTIC_9050_9051_V50.ps1"
exit /b %ERRORLEVEL%
