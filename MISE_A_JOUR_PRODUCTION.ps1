#requires -Version 5.1
param([string]$Target)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONUTF8='1'
try {
    if(-not $Target){$Target=Read-Host 'Dossier EXISTANT Nelyio contenant app.py (ne pas choisir ce nouveau paquet)'}
    if([string]::IsNullOrWhiteSpace($Target)){throw 'Dossier vide. Aucune modification.'}
    $Target=(Resolve-Path -LiteralPath $Target.Trim().Trim('"')).Path
    $Exe=$null;$Prefix=@()
    foreach($relative in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')){
        $candidate=Join-Path $Target $relative
        if(Test-Path -LiteralPath $candidate){$Exe=$candidate;break}
    }
    if(-not $Exe){$cmd=Get-Command py.exe -ErrorAction SilentlyContinue;if($cmd){$Exe=$cmd.Source;$Prefix=@('-3')}}
    if(-not $Exe){$cmd=Get-Command python.exe -ErrorAction SilentlyContinue;if($cmd){$Exe=$cmd.Source}}
    if(-not $Exe){throw 'Python introuvable.'}
    $Script=Join-Path $Root 'deploy_release.py'
    & $Exe @Prefix $Script --target $Target
    if($LASTEXITCODE -ne 0){throw 'La simulation a echoue. Aucune copie effectuee.'}
    Write-Host 'Arretez Nelyio, Caddy, la collecte live et les imports, y compris les taches automatiques.' -ForegroundColor Yellow
    $answer=Read-Host 'Tapez OUI pour confirmer ces arrets, sauvegarder et appliquer la mise a jour'
    if($answer -cne 'OUI'){Write-Host 'Annule. Aucune copie.';exit 0}
    & $Exe @Prefix $Script --target $Target --apply --confirm-stopped
    if($LASTEXITCODE -ne 0){throw 'Mise a jour non validee. Consultez le message ci-dessus et la sauvegarde.'}
    Write-Host 'Code mis a jour. Lancez VALIDATION_PRODUCTION.bat dans votre dossier Nelyio habituel.' -ForegroundColor Green
    Write-Host 'Le rapport et le guide sont dans le nouveau paquet. Aucun service demarre automatiquement.'
    Read-Host 'Entree pour fermer' | Out-Null
} catch {
    Write-Host ('ECHEC : '+$_.Exception.Message) -ForegroundColor Red
    Read-Host 'Entree pour fermer' | Out-Null
    exit 1
}
