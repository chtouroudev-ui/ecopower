@echo off
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs
set LABEL=%~1
if "%LABEL%"=="" set LABEL=measurement
python tools\explain_performance_queries.py --label %LABEL% --output logs\explain_%LABEL%.json
set RC=%ERRORLEVEL%
echo.
echo Rapport: logs\explain_%LABEL%.json
exit /b %RC%
