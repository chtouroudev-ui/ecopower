#requires -Version 5.1
param([ValidateSet('Prepare','Demo')][string]$Action='Prepare')
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
$Exe=$null; $Prefix=@()
foreach($Relative in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')) {
    $Candidate=Join-Path $Root $Relative
    if(Test-Path -LiteralPath $Candidate -PathType Leaf) {
        & $Candidate -c "import sys; assert sys.version_info >= (3,10)" 2>$null
        if($LASTEXITCODE -eq 0) {$Exe=$Candidate; break}
    }
}
if(-not $Exe) {
    foreach($Name in @('py.exe','python.exe')) {
        $Found=Get-Command $Name -ErrorAction SilentlyContinue
        if(-not $Found) {continue}
        $TestPrefix=@(); if($Name -eq 'py.exe') {$TestPrefix=@('-3')}
        & $Found.Source @TestPrefix -c "import sys; assert sys.version_info >= (3,10)" 2>$null
        if($LASTEXITCODE -eq 0) {$Exe=$Found.Source; $Prefix=$TestPrefix; break}
    }
}
try {
    if(-not $Exe) {throw 'Python 3.10 ou plus recent est requis. Installer Python puis relancer.'}
    if($Action -eq 'Prepare') {
        $VenvPython=Join-Path $Root '.venv\Scripts\python.exe'
        if(-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
            Write-Host 'Creation du Python isole de cette installation...'
            & $Exe @Prefix -m venv (Join-Path $Root '.venv')
            if($LASTEXITCODE -ne 0) {throw 'Creation du venv impossible.'}
        }
        & $VenvPython -m pip install -r (Join-Path $Root 'requirements.txt')
        if($LASTEXITCODE -ne 0) {throw 'Dependances non installees. Verifier Internet et relancer.'}
        & $VenvPython -c "import reportlab; from websockets.sync.client import connect; print('Dependances OK')"
        if($LASTEXITCODE -ne 0) {throw 'Controle des dependances non termine.'}
        Write-Host 'PREPARATION TERMINEE. Lancer START_NELYIO.bat ou START_NELYIO_HTTPS.bat.' -ForegroundColor Green
    } else {
        Write-Host 'EXEMPLES FICTIFS : ne pas utiliser pour de vraies statistiques.' -ForegroundColor Yellow
        Write-Host 'Arretez Nelyio et les imports. Les bases metier doivent etre vides.'
        $Answer=Read-Host 'Tapez DEMO pour ajouter les exemples, ou Entree pour annuler'
        if($Answer -cne 'DEMO') {Write-Host 'Annule. Aucun exemple ajoute.'; exit 0}
        & $Exe @Prefix (Join-Path $Root 'demo_dataset.py') --confirm-stopped
        if($LASTEXITCODE -ne 0) {throw 'Exemples non ajoutes. Voir le message ci-dessus; aucune copie manuelle necessaire.'}
    }
    exit 0
} catch {
    Write-Host ('ERREUR : '+$_.Exception.Message) -ForegroundColor Red
    exit 1
}
