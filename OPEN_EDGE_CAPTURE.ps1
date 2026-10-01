param([ValidateRange(1024,65535)][int]$Port = 9222)
$ErrorActionPreference = 'Stop'
# Dedicated local profile: never reuse an agent's everyday browser profile.
$Profile = Join-Path $env:LOCALAPPDATA 'TECH-IN\Nelyio\CaptureBrowser'
$Candidates = @(
    (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
    (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
)
$Browser = $Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Browser) {
    Write-Host 'Microsoft Edge introuvable. Installez Edge sur le PC du serveur Nelyio.' -ForegroundColor Yellow
    Read-Host 'Entree pour fermer' | Out-Null
    exit 1
}
$Client = New-Object System.Net.Sockets.TcpClient
try {
    $Result = $Client.BeginConnect('127.0.0.1', $Port, $null, $null)
    $Busy = $Result.AsyncWaitHandle.WaitOne(600, $false) -and $Client.Connected
} finally { $Client.Close() }
if ($Busy) {
    Write-Host "Le port local $Port est deja utilise. Aucun processus n'a ete arrete." -ForegroundColor Yellow
    Write-Host 'Utilisez la fenetre de collecte deja ouverte, puis Tester le navigateur dans Nelyio.'
    Write-Host 'Sinon fermez uniquement cette fenetre de collecte et relancez ce fichier.'
    Read-Host 'Entree pour fermer' | Out-Null
    exit 2
}
New-Item -ItemType Directory -Path $Profile -Force | Out-Null
$Arguments = @(
    '--remote-debugging-address=127.0.0.1',
    "--remote-debugging-port=$Port",
    ('--user-data-dir="' + $Profile + '"'),
    '--no-first-run', '--new-window', 'about:blank'
)
Start-Process -FilePath $Browser -ArgumentList $Arguments | Out-Null
Write-Host 'Fenetre Edge de collecte ouverte.' -ForegroundColor Green
Write-Host 'Connectez-vous a votre telephonie avec votre compte autorise, puis ouvrez la supervision.'
Write-Host 'Dans Nelyio : Administration > Collecte live > Tester le navigateur > Demarrer.'
Write-Host 'Le port de diagnostic doit rester local : ne creez aucune redirection ou regle Internet.'
Write-Host 'La fenetre et la session telephonie doivent rester ouvertes pendant cette journee.'
