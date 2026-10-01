@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
pushd "%~dp0"
echo NELYIO - Reparation frontend F2 - sans bases de donnees
set "TARGET="
set /p "TARGET=Dossier Nelyio contenant app.py : "
if not defined TARGET goto annuler
set "TARGET=%TARGET:"=%"
set "PYEXE="
set "PYARGS="
if exist "%TARGET%\.venv\Scripts\python.exe" set "PYEXE=%TARGET%\.venv\Scripts\python.exe"
if not defined PYEXE if exist "%TARGET%\venv\Scripts\python.exe" set "PYEXE=%TARGET%\venv\Scripts\python.exe"
if defined PYEXE goto lancer
python --version >nul 2>&1
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE goto lancer
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYEXE=py"
if defined PYEXE set "PYARGS=-3"
if not defined PYEXE goto sanspython
:lancer
if /i "%~1"=="diagnostic" goto diagnostic
"%PYEXE%" %PYARGS% "%~dp0REPARER_FRONTEND.py" --package "%~dp0." --target "%TARGET%" --interactive --report "%~dp0DIAGNOSTIC_FRONTEND_F2.json"
goto fin
:diagnostic
set "BASEURL=http://127.0.0.1:9051"
set /p "BASEURL=Adresse du serveur demarre [http://127.0.0.1:9051] : "
"%PYEXE%" %PYARGS% "%~dp0REPARER_FRONTEND.py" --package "%~dp0." --url "%BASEURL%" --report "%~dp0DIAGNOSTIC_HTTP_FRONTEND_F2.json"
goto fin
:sanspython
echo Python 3 introuvable. Utilisez le Python de votre installation Nelyio.
goto fin
:annuler
echo Annule. Aucun fichier modifie.
:fin
pause
popd
endlocal
