$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
# Same resolution order as START_NELYIO.ps1. No change to the Nelyio launcher.
$Exe = $null
$Prefix = @()
foreach ($relative in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')) {
    $candidate = Join-Path $Root $relative
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        & $candidate -c "import sys; assert sys.version_info >= (3, 10)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Exe=$candidate; break }
    }
}
$Py = Get-Command py.exe -ErrorAction SilentlyContinue
if (-not $Exe -and $Py) {
    & $Py.Source -3 -c "import sys; assert sys.version_info >= (3, 10)" 2>$null
    if ($LASTEXITCODE -eq 0) { $Exe = $Py.Source; $Prefix = @('-3') }
}
if (-not $Exe) {
    $Py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Py) {
        & $Py.Source -c "import sys; assert sys.version_info >= (3, 10)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Exe = $Py.Source }
    }
}
if (-not $Exe) {
    Write-Host 'Python 3.10 ou plus recent est requis. Utilisez le Python qui lance Nelyio.' -ForegroundColor Red
    exit 1
}
Write-Host 'Installation du composant de capture dans le Python du lanceur Nelyio...'
& $Exe @Prefix -m pip install -r (Join-Path $Root 'requirements-capture.txt')
if ($LASTEXITCODE -ne 0) { Write-Host 'Installation non terminee. Verifiez Internet et les droits du compte.'; exit 2 }
& $Exe @Prefix -c "from websockets.sync.client import connect; import websockets; print('Capture disponible - websockets ' + websockets.__version__)"
if ($LASTEXITCODE -ne 0) { exit 3 }
Write-Host 'Redemarrez Nelyio. Rien n a ete connecte a la telephonie par cette installation.' -ForegroundColor Green
