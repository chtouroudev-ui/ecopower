@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo NELYIO - ANALYSE PERFORMANCE PRODUCTION - LECTURE SEULE
echo ============================================================
echo.
python tools\analyze_production_performance.py
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Rapport genere : logs\performance_analysis.md
  echo Donnees JSON    : logs\performance_analysis.json
) else (
  echo Echec de l'analyse. Code retour : %RC%
)
exit /b %RC%
