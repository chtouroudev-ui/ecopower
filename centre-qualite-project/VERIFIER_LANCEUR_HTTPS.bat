@echo off
setlocal
cd /d "%~dp0"
echo NELYIO V59 HTTPS - verification locale sans demarrer les services
echo.
"%SystemRoot%\System32\cscript.exe" //nologo "%~dp0START_NELYIO_HTTPS_SILENT.vbs" /check
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" goto finish
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0TEST_HTTPS_LAUNCHER.ps1"
set "RC=%ERRORLEVEL%"
:finish
echo.
echo Code de verification : %RC%
echo Aucun service Nelyio ou Caddy n'a ete demarre par ce controle.
pause
exit /b %RC%
