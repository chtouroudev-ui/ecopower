@echo off
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0VALIDER_APRES_DEMARRAGE.ps1"
set "CODE=%ERRORLEVEL%"
pause
exit /b %CODE%
