$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DestDir = Join-Path $Root 'data'
$Dest = Join-Path $DestDir 'postgres.env'
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

function Test-NelyioPgEnv([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    try {
        $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
        return (($raw -match '(?im)^\s*NELYIO_DATABASE_ENGINE\s*=\s*postgresql\s*$') -and
                ($raw -match '(?im)^\s*NELYIO_DATABASE_URL\s*=\s*postgresql://'))
    } catch { return $false }
}

function Copy-NelyioPgEnv([string]$Source) {
    if (-not (Test-NelyioPgEnv $Source)) {
        throw "Le fichier selectionne n'est pas un postgres.env Nelyio valide : $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Dest -Force
    try { & icacls $Dest /inheritance:r /grant:r "$env:USERNAME`:(R,W)" "SYSTEM:(F)" | Out-Null } catch {}
    Write-Host ('[OK] Configuration PostgreSQL copiee depuis : ' + $Source) -ForegroundColor Green
    Write-Host ('[OK] Destination : ' + $Dest) -ForegroundColor Green
    Write-Host '[SUITE] Lancez VERIFIER_POSTGRESQL.bat puis VALIDATION_PRODUCTION.bat.' -ForegroundColor Cyan
}

if (Test-NelyioPgEnv $Dest) {
    Write-Host '[OK] data\postgres.env est deja present et valide dans ce dossier.' -ForegroundColor Green
    Write-Host '[SUITE] Lancez VERIFIER_POSTGRESQL.bat.' -ForegroundColor Cyan
    Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
    exit 0
}

$searchRoots = New-Object System.Collections.Generic.List[string]
function Add-SearchRoot([string]$Path) {
    if (-not $Path) { return }
    try { $full = [System.IO.Path]::GetFullPath($Path) } catch { return }
    if ((Test-Path -LiteralPath $full -PathType Container) -and (-not $searchRoots.Contains($full))) {
        $searchRoots.Add($full)
    }
}

$parent = Split-Path -Parent $Root
Add-SearchRoot $parent
Add-SearchRoot (Split-Path -Parent $parent)
if ($env:USERPROFILE) {
    Add-SearchRoot (Join-Path $env:USERPROFILE 'Desktop')
    Add-SearchRoot (Join-Path $env:USERPROFILE 'Documents')
}

$candidates = @()
foreach ($sr in $searchRoots) {
    Write-Host ('[NELYIO] Recherche de postgres.env sous : ' + $sr) -ForegroundColor DarkGray
    try {
        $found = Get-ChildItem -LiteralPath $sr -Filter 'postgres.env' -File -Recurse -ErrorAction SilentlyContinue |
            Where-Object {
                $_.FullName -ne $Dest -and
                $_.Directory -and $_.Directory.Name -ieq 'data' -and
                (Test-NelyioPgEnv $_.FullName)
            }
        if ($found) { $candidates += $found }
    } catch {}
}

$candidates = $candidates | Sort-Object FullName -Unique | Sort-Object LastWriteTime -Descending
if ($candidates.Count -gt 0) {
    $src = $candidates[0].FullName
    if ($candidates.Count -gt 1) {
        Write-Host '[NELYIO] Plusieurs configurations valides trouvees. La plus recente sera utilisee :' -ForegroundColor Yellow
        $candidates | Select-Object -First 5 | ForEach-Object { Write-Host ('  - ' + $_.FullName) }
    }
    Copy-NelyioPgEnv $src
    Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
    exit 0
}

Write-Host '[INFO] Aucune ancienne configuration PostgreSQL valide trouvee automatiquement.' -ForegroundColor Yellow
Write-Host 'Vous pouvez indiquer soit le dossier de votre ancienne version Nelyio, soit le fichier postgres.env.' -ForegroundColor Cyan
$manual = Read-Host 'Chemin complet (laisser vide pour annuler)'
if ($manual) {
    $manual = $manual.Trim('"')
    $source = $manual
    if (Test-Path -LiteralPath $manual -PathType Container) {
        $source = Join-Path $manual 'data\postgres.env'
    }
    try {
        Copy-NelyioPgEnv $source
        Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
        exit 0
    } catch {
        Write-Host ('[ERREUR] ' + $_.Exception.Message) -ForegroundColor Red
    }
}

Write-Host '[ERREUR] Aucune configuration PostgreSQL n a pu etre recuperee.' -ForegroundColor Red
Write-Host 'Alternative : lancez CONFIGURER_POSTGRESQL_AUTO.bat dans ce dossier.' -ForegroundColor Yellow
Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
exit 1
