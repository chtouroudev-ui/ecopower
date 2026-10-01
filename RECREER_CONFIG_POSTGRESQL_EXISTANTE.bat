@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECREER_CONFIG_POSTGRESQL_EXISTANTE.ps1"
set "RC=%ERRORLEVEL%"
exit /b %RC%
