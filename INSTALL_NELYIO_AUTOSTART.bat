@echo off
setlocal
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_NELYIO_AUTOSTART.ps1"
pause
