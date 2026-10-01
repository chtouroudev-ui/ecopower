@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONUNBUFFERED=1"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "nelyio_importer_app.py"
  exit /b 0
)
if exist "venv\Scripts\pythonw.exe" (
  start "" "venv\Scripts\pythonw.exe" "nelyio_importer_app.py"
  exit /b 0
)
where pyw.exe >nul 2>&1
if %errorlevel%==0 (
  start "" pyw.exe -3 "nelyio_importer_app.py"
  exit /b 0
)
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
  start "" pythonw.exe "nelyio_importer_app.py"
  exit /b 0
)
where py.exe >nul 2>&1
if %errorlevel%==0 (
  py.exe -3 "nelyio_importer_app.py"
  exit /b %errorlevel%
)
python.exe "nelyio_importer_app.py"
exit /b %errorlevel%
