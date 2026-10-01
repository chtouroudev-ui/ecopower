@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0START_NELYIO_HTTPS_SILENT.vbs" (
  echo Fichier START_NELYIO_HTTPS_SILENT.vbs absent. Recopiez le correctif complet.
  pause
  exit /b 40
)
if not exist "%SystemRoot%\System32\wscript.exe" (
  echo Windows Script Host indisponible. Utilisez START_NELYIO_HTTPS_DEBUG.bat.
  pause
  exit /b 41
)
"%SystemRoot%\System32\wscript.exe" //nologo "%~dp0START_NELYIO_HTTPS_SILENT.vbs"
exit /b %ERRORLEVEL%
