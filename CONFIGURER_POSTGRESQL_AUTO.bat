@echo off
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CONFIGURER_POSTGRESQL_AUTO.ps1"
if errorlevel 1 pause
