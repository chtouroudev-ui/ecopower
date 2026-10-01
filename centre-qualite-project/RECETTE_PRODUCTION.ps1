$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Find-Python {
    $venv = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }
    $venv2 = Join-Path $PSScriptRoot 'venv\Scripts\python.exe'
    if (Test-Path $venv2) { return $venv2 }
    return 'py'
}

Write-Host ''
Write-Host '=== NELYIO - RECETTE PRODUCTION RC ===' -ForegroundColor Cyan
Write-Host 'Cette recette ne modifie pas les donnees metier.' -ForegroundColor DarkGray
Write-Host 'Les connexions de test creent seulement les sessions/audits normaux.' -ForegroundColor DarkGray
Write-Host ''

$defaultUrl = if ($env:NELYIO_PUBLIC_URL) { $env:NELYIO_PUBLIC_URL } else { 'https://stock-manager.nelyio.local:9050' }
$public = Read-Host "URL HTTPS a tester [$defaultUrl]"
if ([string]::IsNullOrWhiteSpace($public)) { $public = $defaultUrl }

$user = if ($env:NELYIO_BENCH_USER) { $env:NELYIO_BENCH_USER } else { Read-Host 'Compte Nelyio de recette (lecture Live + Qualite + Groupes + Configuration)' }
if ([string]::IsNullOrWhiteSpace($user)) {
    Write-Host '[ERREUR] Un compte de recette est requis pour une validation complete.' -ForegroundColor Red
    exit 1
}

$plain = $env:NELYIO_BENCH_PASSWORD
if ([string]::IsNullOrWhiteSpace($plain)) {
    $secure = Read-Host 'Mot de passe' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

$env:NELYIO_BENCH_USER = $user
$env:NELYIO_BENCH_PASSWORD = $plain
$python = Find-Python
$arguments = @()
if ($python -eq 'py') { $arguments += '-3' }
$arguments += @('tools\production_acceptance.py','--public-url',$public)
if ($public -match '^https://(localhost|127\.0\.0\.1)(:|/)') { $arguments += '--allow-untrusted-local' }

try {
    & $python @arguments
    $code = $LASTEXITCODE
}
finally {
    $env:NELYIO_BENCH_PASSWORD = $null
    $plain = $null
}

Write-Host ''
if ($code -eq 0) {
    Write-Host '[GO AUTOMATISE] Les controles automatisables sont valides.' -ForegroundColor Green
    Write-Host 'Effectuez encore la verification HTTPS depuis un autre poste du LAN.' -ForegroundColor Yellow
} elseif ($code -eq 2) {
    Write-Host '[INCOMPLET] Consultez logs\RECETTE_PRODUCTION.md avant toute bascule.' -ForegroundColor Yellow
} else {
    Write-Host '[BLOQUE] Ne pas basculer en production avant correction.' -ForegroundColor Red
}
Write-Host 'Rapport : logs\RECETTE_PRODUCTION.md'
exit $code
