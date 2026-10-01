@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================================
echo NELYIO V60.4 - INDEX PERFORMANCE POSTGRESQL
echo ============================================================
echo Cette operation est NON destructive mais peut utiliser CPU/IO.
echo Faire une sauvegarde PostgreSQL avant de continuer.
echo.
choice /C ON /N /M "Continuer ? [O/N] "
if errorlevel 2 exit /b 0
python tools\apply_performance_indexes.py --apply
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo ECHEC - index non appliques completement. Code %RC%.
  pause
  exit /b %RC%
)
echo OK. Lancez maintenant EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
pause
exit /b 0
