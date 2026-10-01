@echo off
setlocal
cd /d "%~dp0"
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
echo Synchronisation des tailles WAV Hermes - aucun fichier audio n'est telecharge.
echo La fenetre Edge de collecte doit etre ouverte et connectee a la Supervision.
echo Laissez cette fenetre ouverte pendant toute la synchronisation.
echo Ouvrez seulement la zone Enregistrements et restez au niveau des SDA/campagnes.
echo Nelyio parcourt automatiquement SDA/campagne ^> annee ^> mois ^> jour ^> login agent ^> WAV.
echo Seuls INDICE + SIZE sont conserves dans la base.
echo.
set /p MODE=Mode [TOUT/PLAGE] [TOUT] : 
if "%MODE%"=="" goto ALL
if /I "%MODE%"=="TOUT" goto ALL
if /I "%MODE%"=="T" goto ALL
if /I "%MODE%"=="PLAGE" goto RANGE
if /I "%MODE%"=="P" goto RANGE
echo Mode inconnu.
goto END
:ALL
"%PY%" recording_sizes.py --all
goto END
:RANGE
set /p DATE_FROM=Date debut AAAA-MM-JJ : 
set /p DATE_TO=Date fin AAAA-MM-JJ [meme date] : 
if "%DATE_FROM%"=="" goto END
if "%DATE_TO%"=="" set "DATE_TO=%DATE_FROM%"
"%PY%" recording_sizes.py --from "%DATE_FROM%" --to "%DATE_TO%"
:END
echo.
pause
