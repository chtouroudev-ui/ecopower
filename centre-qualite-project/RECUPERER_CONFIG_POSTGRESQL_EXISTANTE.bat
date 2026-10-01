@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RECUPERER_CONFIG_POSTGRESQL_EXISTANTE.ps1"
