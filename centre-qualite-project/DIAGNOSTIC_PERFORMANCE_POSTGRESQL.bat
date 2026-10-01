@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
python tools\diagnose_postgresql.py --output logs\postgresql_diagnostic.json
set RC=%ERRORLEVEL%
echo.
echo Rapport: logs\postgresql_diagnostic.json
exit /b %RC%
