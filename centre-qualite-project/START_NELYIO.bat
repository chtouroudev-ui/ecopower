@echo off
setlocal
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_NELYIO.ps1"
set ERR=%ERRORLEVEL%
if not "%ERR%"=="0" (
  echo.
  echo [NELYIO] Le demarrage a echoue. Code: %ERR%
  echo Consultez le dossier logs\ dans ce dossier.
  pause
)
exit /b %ERR%
