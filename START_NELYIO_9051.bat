@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo  NELYIO V59 - HTTP local production
echo ========================================
echo.
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0START_NELYIO.ps1" -NoBrowser -NoPause
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo [ERREUR] Le stack Nelyio local n'a pas pu demarrer. Code: %RC%
  echo Consultez le dossier logs\.
  pause
  exit /b %RC%
)
echo.
echo [OK] Backend + Import + Live + Analytics actifs.
echo Ouvrez: http://127.0.0.1:9051/
exit /b 0
