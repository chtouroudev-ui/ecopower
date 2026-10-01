@echo off
setlocal
cd /d "%~dp0"
if "%NELYIO_BENCH_USER%"=="" (
  echo ERREUR: definir NELYIO_BENCH_USER dans cette console avant de lancer le benchmark.
  exit /b 2
)
if "%NELYIO_BENCH_PASSWORD%"=="" (
  echo ERREUR: definir NELYIO_BENCH_PASSWORD dans cette console avant de lancer le benchmark.
  exit /b 2
)
python tools\benchmark_api.py --base-url http://127.0.0.1:9051 --users 5 --rounds 3 --output BENCHMARK_API_RUNTIME.json
exit /b %ERRORLEVEL%
