@echo off
setlocal
cd /d "%~dp0"
set TECHIN_HOST=127.0.0.1
set TECHIN_PORT=9051
set TECHIN_STRICT_PORT=1
python app.py
if errorlevel 1 (
  echo.
  echo Le backend Nelyio n'a pas pu demarrer sur 127.0.0.1:9051.
  echo Verifiez si un ancien processus Python utilise deja le port 9051.
  pause
)
