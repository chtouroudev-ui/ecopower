@echo off
setlocal
cd /d "%~dp0"
python tools\diagnose_postgresql.py --output logs\postgresql_diagnostic.json
if errorlevel 1 (
  echo.
  echo ECHEC diagnostic PostgreSQL.
  pause
  exit /b 1
)
echo.
echo Rapport: logs\postgresql_diagnostic.json
endlocal
