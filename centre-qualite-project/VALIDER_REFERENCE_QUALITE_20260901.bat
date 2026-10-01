@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage : %~nx0 "C:\chemin\SIMPLIFY2.2026-09-01.export.zip"
  exit /b 2
)
python quality_reference_20260901_test.py --zip "%~1" --json "audit_results\quality_reference_20260901.json"
exit /b %ERRORLEVEL%
