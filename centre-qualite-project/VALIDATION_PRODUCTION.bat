@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "CODE=0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" preflight.py --json "logs\preflight_production.json"
  if errorlevel 1 set "CODE=1"
  ".venv\Scripts\python.exe" postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_validation.json"
  if errorlevel 1 set "CODE=1"
) else if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" preflight.py --json "logs\preflight_production.json"
  if errorlevel 1 set "CODE=1"
  "venv\Scripts\python.exe" postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_validation.json"
  if errorlevel 1 set "CODE=1"
) else (
  py -3 preflight.py --json "logs\preflight_production.json"
  if errorlevel 1 set "CODE=1"
  py -3 postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_validation.json"
  if errorlevel 1 set "CODE=1"
)
echo.
if "%CODE%"=="0" (
  echo [OK] Validation statique + PostgreSQL reussie.
  echo Lancez ensuite START_NELYIO.bat puis RECETTE_PRODUCTION.bat.
) else (
  echo [ERREUR] Ne pas basculer en production avant correction.
  echo Consultez logs\preflight_production.json et logs\postgres_runtime_preflight_validation.json.
)
pause
exit /b %CODE%
