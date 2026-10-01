@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "DAY=%~1"
if exist ".venv\Scripts\python.exe" (
  if "%DAY%"=="" ( ".venv\Scripts\python.exe" quality_precision_check.py --json "logs\quality_precision.json" ) else ( ".venv\Scripts\python.exe" quality_precision_check.py --date "%DAY%" --json "logs\quality_precision.json" )
) else (
  if "%DAY%"=="" ( py -3 quality_precision_check.py --json "logs\quality_precision.json" ) else ( py -3 quality_precision_check.py --date "%DAY%" --json "logs\quality_precision.json" )
)
set "CODE=%ERRORLEVEL%"
echo.
if "%CODE%"=="0" echo [OK] Coherence interne Qualite validee.
if not "%CODE%"=="0" echo [ERREUR] Ne pas valider les chiffres Qualite avant correction. Voir logs\quality_precision.json
pause
exit /b %CODE%
