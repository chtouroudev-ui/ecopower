param([string]$Target = '')
$ErrorActionPreference = 'Stop'
$PatchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Find-NelyioRoot {
    param([string]$Candidate)
    if($Candidate -and (Test-Path (Join-Path $Candidate 'app.py'))){ return (Resolve-Path $Candidate).Path }
    $here = Split-Path -Parent $PatchRoot
    foreach($c in @($PatchRoot,$here,(Get-Location).Path)){
        if($c -and (Test-Path (Join-Path $c 'app.py'))){ return (Resolve-Path $c).Path }
    }
    return ''
}

$Target = Find-NelyioRoot $Target
if([string]::IsNullOrWhiteSpace($Target)){
    $Target = Read-Host 'Dossier racine Nelyio V60.4 (celui qui contient app.py)'
    $Target = Find-NelyioRoot $Target
}
if([string]::IsNullOrWhiteSpace($Target)){ throw 'Dossier Nelyio non valide ou app.py introuvable.' }

Write-Host "Projet Nelyio : $Target" -ForegroundColor Cyan
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupRoot = Join-Path $Target "backups\patches"
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
$backup = Join-Path $backupRoot "PATCH_BACKUP_V5_CAMPAIGNS_$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $backup 'static') -Force | Out-Null

$files = @(
    @{src='files\quality_importer.py'; dst='quality_importer.py'},
    @{src='files\static\groups.js'; dst='static\groups.js'}
)
foreach($f in $files){
    $src = Join-Path $PatchRoot $f.src
    $dst = Join-Path $Target $f.dst
    if(!(Test-Path $src)){ throw "Fichier patch manquant: $src" }
    if(Test-Path $dst){
        $backupDst = Join-Path $backup $f.dst
        $backupDir = Split-Path -Parent $backupDst
        New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        Copy-Item -LiteralPath $dst -Destination $backupDst -Force
    }
    $dstDir = Split-Path -Parent $dst
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "OK - $($f.dst)" -ForegroundColor Green
}

Write-Host ''
Write-Host 'PATCH V5 APPLIQUE AVEC SUCCES.' -ForegroundColor Green
Write-Host 'Correction : campagnes derivees automatiquement des files via ODCalls.'
Write-Host 'Amelioration : les campagnes automatiques restent visibles aussi en mode Modifier.'
Write-Host "Sauvegarde : $backup"
Write-Host 'Redemarre Nelyio puis fais Ctrl+F5.'
