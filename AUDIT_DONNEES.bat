@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" audit_production.py --json "logs\audit_donnees.json" %*
) else if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" audit_production.py --json "logs\audit_donnees.json" %*
) else (
  py -3 audit_production.py --json "logs\audit_donnees.json" %*
)
set "CODE=%ERRORLEVEL%"
echo Rapport : logs\audit_donnees.json
pause
exit /b %CODE%
