@echo off
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SAUVEGARDER_POSTGRESQL.ps1"
pause
