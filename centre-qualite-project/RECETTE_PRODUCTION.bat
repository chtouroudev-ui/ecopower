@echo off
cd /d "%~dp0"
PowerShell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECETTE_PRODUCTION.ps1"
set "CODE=%ERRORLEVEL%"
echo.
pause
exit /b %CODE%
