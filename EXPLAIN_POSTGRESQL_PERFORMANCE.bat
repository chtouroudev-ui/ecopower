@echo off
setlocal
cd /d "%~dp0"
python tools\explain_performance_queries.py --label production --output logs\explain_production.json
if errorlevel 1 (
  echo.
  echo ECHEC EXPLAIN PostgreSQL.
  pause
  exit /b 1
)
echo.
echo Rapport: logs\explain_production.json
endlocal
