@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0INSTALL_PATCH.ps1"
if errorlevel 1 (
  echo.
  echo ECHEC DU PATCH.
  pause
  exit /b 1
)
echo.
pause
