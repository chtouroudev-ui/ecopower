@echo off
setlocal
cd /d "%~dp0"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0START_NELYIO_HTTPS.ps1" -ControlPanel -NoAutoStart
exit /b %ERRORLEVEL%
