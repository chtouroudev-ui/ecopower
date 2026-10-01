@echo off
setlocal
cd /d "%~dp0"
if "%NELYIO_BENCH_USER%"=="" (
  echo ERREUR: definir NELYIO_BENCH_USER dans cette console avant le test.
  exit /b 2
)
if "%NELYIO_BENCH_PASSWORD%"=="" (
  echo ERREUR: definir NELYIO_BENCH_PASSWORD dans cette console avant le test.
  exit /b 2
)
echo === NELYIO - TEST DE CHARGE PROLONGEE ===
echo Lecture seule metier. Les connexions creent seulement les sessions/audits normaux.
echo Par defaut: 5 utilisateurs virtuels pendant 5 minutes.
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" "%~dp0tools\soak_test.py" --base-url http://127.0.0.1:9051 --users 5 --duration 300 --interval 2 --output "%~dp0logs\soak_test_production.json"
  goto done
)
where py.exe >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0tools\soak_test.py" --base-url http://127.0.0.1:9051 --users 5 --duration 300 --interval 2 --output "%~dp0logs\soak_test_production.json"
  goto done
)
python "%~dp0tools\soak_test.py" --base-url http://127.0.0.1:9051 --users 5 --duration 300 --interval 2 --output "%~dp0logs\soak_test_production.json"
:done
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" echo Rapport: logs\soak_test_production.json
exit /b %RC%
