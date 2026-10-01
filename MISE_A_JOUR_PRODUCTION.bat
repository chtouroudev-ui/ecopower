@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0MISE_A_JOUR_PRODUCTION.ps1"
exit /b %ERRORLEVEL%
