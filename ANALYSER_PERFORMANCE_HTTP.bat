@echo off
setlocal
cd /d "%~dp0"
if not exist logs\performance.jsonl (
  echo Aucun fichier logs\performance.jsonl trouve.
  exit /b 2
)
python tools\analyze_performance_log.py logs\performance.jsonl
exit /b %ERRORLEVEL%
