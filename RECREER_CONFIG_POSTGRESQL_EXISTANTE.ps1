param(
  [string]$PgAdminUser = 'postgres',
  [string]$Database = 'nelyio',
  [string]$AppUser = 'nelyio_app',
  [string]$HostName = '127.0.0.1',
  [string]$Port = '5432'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Info($t){ Write-Host "[NELYIO] $t" -ForegroundColor Cyan }
function Ok($t){ Write-Host "[OK] $t" -ForegroundColor Green }
function Warn($t){ Write-Host "[WARN] $t" -ForegroundColor Yellow }
function Fail($t){ Write-Host "[ERREUR] $t" -ForegroundColor Red }

function Find-Psql {
  $p = Get-Command psql.exe -ErrorAction SilentlyContinue
  if($p){ return $p.Source }
  foreach($r in @("$env:ProgramFiles\PostgreSQL", "${env:ProgramFiles(x86)}\PostgreSQL")){
    if(Test-Path $r){
      $x = Get-ChildItem $r -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'bin\psql.exe' } |
        Where-Object { Test-Path $_ } |
        Select-Object -First 1
      if($x){ return $x }
    }
  }
  return $null
}

function Find-Python {
  foreach($p in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')){
    if(Test-Path $p){ return (Resolve-Path $p).Path }
  }
  $py = Get-Command py.exe -ErrorAction SilentlyContinue
  if($py){ return $py.Source }
  $p = Get-Command python.exe -ErrorAction SilentlyContinue
  if($p){ return $p.Source }
  return $null
}

Clear-Host
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ' NELYIO - Re-creer postgres.env sans re-migrer les donnees' -ForegroundColor White
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ''
Write-Host 'Ce script ne supprime pas la base nelyio et ne relance pas la migration SQLite.' -ForegroundColor Yellow
Write-Host 'Il reinitialise uniquement le mot de passe du compte nelyio_app, cree postgres.env,' -ForegroundColor Yellow
Write-Host 'puis execute le controle runtime PostgreSQL.' -ForegroundColor Yellow
Write-Host ''

$Psql = Find-Psql
if(-not $Psql){ Fail 'psql.exe introuvable. Installez les Command Line Tools PostgreSQL.'; exit 10 }
$Python = Find-Python
if(-not $Python){ Fail 'Python 3 introuvable.'; exit 11 }
Info "psql : $Psql"
Info "Python : $Python"

$sec = Read-Host "Mot de passe PostgreSQL du compte $PgAdminUser" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try { $AdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }

$env:PGPASSWORD = $AdminPassword
try {
  Info "Test de connexion PostgreSQL sur $HostName`:$Port ..."
  & $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -tAc 'SELECT 1;' | Out-Null
  if($LASTEXITCODE -ne 0){ throw 'Connexion administrateur PostgreSQL impossible.' }

  $dbExists = (& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_database WHERE datname='$Database';") -join ''
  if($dbExists.Trim() -ne '1'){
    Fail "La base '$Database' n existe pas. Utilisez CONFIGURER_POSTGRESQL_AUTO.bat pour une installation/migration complete."
    exit 12
  }
  Ok "Base existante detectee : $Database"

  $chars = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $bytes = New-Object byte[] 48
  $rng.GetBytes($bytes)
  $AppPassword = -join ($bytes | ForEach-Object { $chars[$_ % $chars.Length] })

  $roleExists = (& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM pg_roles WHERE rolname='$AppUser';") -join ''
  if($roleExists.Trim() -eq '1'){
    Info "Reinitialisation securisee du mot de passe de $AppUser ..."
    & $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "ALTER ROLE $AppUser WITH LOGIN PASSWORD '$AppPassword';" | Out-Null
  } else {
    Info "Creation du compte applicatif $AppUser ..."
    & $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE $AppUser LOGIN PASSWORD '$AppPassword';" | Out-Null
  }
  if($LASTEXITCODE -ne 0){ throw "Impossible de creer/modifier le role $AppUser." }

  & $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "ALTER DATABASE $Database OWNER TO $AppUser; GRANT ALL PRIVILEGES ON DATABASE $Database TO $AppUser;" | Out-Null
  if($LASTEXITCODE -ne 0){ throw 'Impossible de mettre a jour les droits de la base.' }

  foreach($schema in @('admin','supervision','details','live')){
    $exists = (& $Psql -h $HostName -p $Port -U $PgAdminUser -d $Database -v ON_ERROR_STOP=1 -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name='$schema';") -join ''
    if($exists.Trim() -eq '1'){
      & $Psql -h $HostName -p $Port -U $PgAdminUser -d $Database -v ON_ERROR_STOP=1 -c "GRANT USAGE, CREATE ON SCHEMA $schema TO $AppUser; GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA $schema TO $AppUser; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA $schema TO $AppUser;" | Out-Null
      if($LASTEXITCODE -ne 0){ throw "Impossible d accorder les droits sur le schema $schema." }
    }
  }
} finally {
  Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

$data = Join-Path $Root 'data'
New-Item -ItemType Directory -Force -Path $data | Out-Null
$envFile = Join-Path $data 'postgres.env'
@(
  'NELYIO_DATABASE_ENGINE=postgresql',
  "NELYIO_DATABASE_URL=postgresql://$AppUser`:$AppPassword@$HostName`:$Port/$Database"
) | Set-Content -LiteralPath $envFile -Encoding UTF8
try { & icacls $envFile /inheritance:r /grant:r "$env:USERNAME`:(R,W)" 'SYSTEM:(F)' | Out-Null }
catch { Warn 'ACL postgres.env non modifiee.' }
Ok 'Nouveau data\postgres.env cree.'

$env:PGPASSWORD = $AppPassword
try {
  Info 'Test du compte applicatif genere ...'
  $who = (& $Psql -h $HostName -p $Port -U $AppUser -d $Database -v ON_ERROR_STOP=1 -tAc 'SELECT current_database() || ''|'' || current_user;') -join ''
  if($LASTEXITCODE -ne 0 -or $who.Trim() -ne "$Database|$AppUser"){
    throw "Le compte applicatif ne peut pas se connecter : $who"
  }
  Ok "Connexion applicative valide : $($who.Trim())"
} finally {
  Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

Info 'Verification du pilote psycopg ...'
if((Split-Path $Python -Leaf) -ieq 'py.exe'){
  & $Python -3 -c 'import psycopg; print(psycopg.__version__)' | Out-Null
} else {
  & $Python -c 'import psycopg; print(psycopg.__version__)' | Out-Null
}
if($LASTEXITCODE -ne 0){
  Warn 'psycopg absent. Installation automatique ...'
  if((Split-Path $Python -Leaf) -ieq 'py.exe'){
    & $Python -3 -m pip install --disable-pip-version-check 'psycopg[binary]>=3.2,<4'
  } else {
    & $Python -m pip install --disable-pip-version-check 'psycopg[binary]>=3.2,<4'
  }
  if($LASTEXITCODE -ne 0){ Fail 'Installation psycopg impossible.'; exit 13 }
}

$Preflight = Join-Path $Root 'postgres_runtime_preflight.py'
$PreflightLog = Join-Path $Root 'logs\postgres_runtime_preflight.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PreflightLog) | Out-Null
Info 'Reparation non destructive et controle runtime PostgreSQL ...'
if((Split-Path $Python -Leaf) -ieq 'py.exe'){
  & $Python -3 $Preflight --repair --json $PreflightLog
} else {
  & $Python $Preflight --repair --json $PreflightLog
}
if($LASTEXITCODE -ne 0){
  Fail 'postgres.env a ete recree, mais le preflight runtime a encore detecte une erreur.'
  Write-Host "Rapport : $PreflightLog" -ForegroundColor Yellow
  Write-Host 'Ne lancez pas Nelyio tant que VERIFIER_POSTGRESQL.bat n est pas vert.' -ForegroundColor Yellow
  Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
  exit 14
}

Ok 'Configuration PostgreSQL recreee SANS re-migration des donnees.'
Ok 'Preflight runtime PostgreSQL valide.'
Write-Host ''
Write-Host 'SUITE :' -ForegroundColor Cyan
Write-Host '  1. VERIFIER_POSTGRESQL.bat' -ForegroundColor White
Write-Host '  2. VALIDATION_PRODUCTION.bat' -ForegroundColor White
Write-Host '  3. START_NELYIO.bat uniquement si les controles sont verts.' -ForegroundColor White
Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
