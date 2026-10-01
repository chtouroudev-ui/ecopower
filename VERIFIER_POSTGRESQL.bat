@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_manual.json"
) else if exist "venv\Scripts\python.exe" (
  "venv\Scripts\python.exe" postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_manual.json"
) else (
  py -3 postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_manual.json"
  if errorlevel 1 python postgres_runtime_preflight.py --repair --json "logs\postgres_runtime_preflight_manual.json"
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" (
  echo [OK] PostgreSQL est pret pour Nelyio.
) else (
  echo [ERREUR] PostgreSQL n est pas pret. Voir logs\postgres_runtime_preflight_manual.json
)
pause
exit /b %CODE%
