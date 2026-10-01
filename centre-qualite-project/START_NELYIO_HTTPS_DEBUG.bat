@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo NELYIO RC29.3 HTTPS - DIAGNOSTIC
echo ============================================================
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0START_NELYIO_HTTPS.ps1" -Diagnostics
set "RC=%ERRORLEVEL%"
echo.
echo Code retour: %RC%
echo.
echo Journaux : logs\https_launcher.log
if exist "%~dp0logs\https_launcher.log" type "%~dp0logs\https_launcher.log"
echo.
echo Autres journaux utiles :
echo logs\backend_9051_stdout.log
echo logs\backend_9051_stderr.log
echo logs\startup_progress.log
echo logs\startup_error.log
echo logs\https_backend_start_stderr.log
echo logs\https_caddy_start_stderr.log
echo logs\caddy_validate.log
echo logs\caddy_stderr.log
if not "%RC%"=="0" (
  echo.
  if exist "%~dp0logs\startup_progress.log" (
    echo --- STARTUP_PROGRESS.LOG ---
    powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%~dp0logs\startup_progress.log' -Tail 80"
  )
  if exist "%~dp0logs\backend_9051_stdout.log" (
    echo.
    echo --- BACKEND_9051_STDOUT.LOG ---
    powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%~dp0logs\backend_9051_stdout.log' -Tail 80"
  )
  if exist "%~dp0logs\backend_9051_stderr.log" (
    echo.
    echo --- BACKEND_9051_STDERR.LOG ---
    powershell.exe -NoProfile -Command "Get-Content -LiteralPath '%~dp0logs\backend_9051_stderr.log' -Tail 80"
  )
)
pause
exit /b %RC%
