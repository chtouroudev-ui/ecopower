param(
  [string]$PgAdminUser = 'postgres',
  [string]$Database = 'nelyio',
  [string]$AppUser = 'nelyio_app'
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
function Step($t){Write-Host "[NELYIO] $t" -ForegroundColor Cyan}
function Ok($t){Write-Host "[OK] $t" -ForegroundColor Green}
function Fail($t){Write-Host "[ERREUR] $t" -ForegroundColor Red}
function Find-Python {
  foreach($p in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')){if(Test-Path $p){return (Resolve-Path $p).Path}}
  $py=Get-Command py.exe -ErrorAction SilentlyContinue;if($py){return $py.Source}
  $p=Get-Command python.exe -ErrorAction SilentlyContinue;if($p){return $p.Source}
  return $null
}
function Find-Psql {
  $p=Get-Command psql.exe -ErrorAction SilentlyContinue;if($p){return $p.Source}
  $roots=@("$env:ProgramFiles\PostgreSQL","${env:ProgramFiles(x86)}\PostgreSQL")
  foreach($r in $roots){if(Test-Path $r){$x=Get-ChildItem $r -Directory | Sort-Object Name -Descending | ForEach-Object {Join-Path $_.FullName 'bin\psql.exe'} | Where-Object {Test-Path $_} | Select-Object -First 1;if($x){return $x}}}
  return $null
}
Clear-Host
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ' NELYIO - Migration totale PostgreSQL' -ForegroundColor White
Write-Host '============================================================' -ForegroundColor DarkCyan
$Python=Find-Python;if(-not $Python){Fail 'Python 3 introuvable.';exit 10}
$Psql=Find-Psql;if(-not $Psql){Fail 'psql.exe introuvable. Verifiez installation PostgreSQL et Command Line Tools.';exit 11}
Step "Python: $Python"
Step "psql: $Psql"
Step 'Installation du pilote PostgreSQL psycopg...'
if((Split-Path $Python -Leaf) -ieq 'py.exe'){& $Python -3 -m pip install --disable-pip-version-check "psycopg[binary]>=3.2,<4"}else{& $Python -m pip install --disable-pip-version-check "psycopg[binary]>=3.2,<4"}
if($LASTEXITCODE -ne 0){Fail 'Installation psycopg impossible.';exit 12}
$sec=Read-Host "Mot de passe PostgreSQL du compte $PgAdminUser" -AsSecureString
$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
try{$AdminPassword=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)}
$chars='abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
$rng=[System.Security.Cryptography.RandomNumberGenerator]::Create();$bytes=New-Object byte[] 40;$rng.GetBytes($bytes)
$AppPassword=-join ($bytes | ForEach-Object {$chars[$_ % $chars.Length]})
$env:PGPASSWORD=$AdminPassword
$HostName='127.0.0.1';$Port='5432'
Step 'Test de connexion PostgreSQL...'
& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -tAc 'SELECT version();' | Out-Null
if($LASTEXITCODE -ne 0){Fail 'Connexion PostgreSQL impossible. Verifiez mot de passe/service/port 5432.';exit 13}
$roleExists=& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$AppUser'"
if(-not ($roleExists -match '1')){& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE ROLE $AppUser LOGIN PASSWORD '$AppPassword';" | Out-Null}
else{& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "ALTER ROLE $AppUser WITH LOGIN PASSWORD '$AppPassword';" | Out-Null}
$dbExists=& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$Database'"
if(-not ($dbExists -match '1')){& $Psql -h $HostName -p $Port -U $PgAdminUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $Database OWNER $AppUser ENCODING 'UTF8';" | Out-Null}
& $Psql -h $HostName -p $Port -U $PgAdminUser -d $Database -v ON_ERROR_STOP=1 -c "ALTER DATABASE $Database OWNER TO $AppUser; GRANT ALL ON DATABASE $Database TO $AppUser;" | Out-Null
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
$data=Join-Path $Root 'data';New-Item -ItemType Directory -Force -Path $data | Out-Null
$envFile=Join-Path $data 'postgres.env'
@("NELYIO_DATABASE_ENGINE=postgresql","NELYIO_DATABASE_URL=postgresql://$AppUser`:$AppPassword@$HostName`:$Port/$Database") | Set-Content -LiteralPath $envFile -Encoding UTF8
Ok 'Configuration PostgreSQL creee dans data\postgres.env'
try { & icacls $envFile /inheritance:r /grant:r "$env:USERNAME`:(R,W)" "SYSTEM:(F)" | Out-Null } catch { Write-Host '[WARN] ACL postgres.env non modifiee.' -ForegroundColor Yellow }
Step 'Migration des quatre bases SQLite vers PostgreSQL...'
if((Split-Path $Python -Leaf) -ieq 'py.exe'){& $Python -3 (Join-Path $Root 'postgres_migrate.py') --reset}else{& $Python (Join-Path $Root 'postgres_migrate.py') --reset}
if($LASTEXITCODE -ne 0){Fail 'Migration interrompue. Les bases SQLite originales restent intactes.';exit 14}
Step 'Durcissement et verification du schema runtime PostgreSQL...'
$Preflight=Join-Path $Root 'postgres_runtime_preflight.py'
$PreflightLog=Join-Path $Root 'logs\postgres_runtime_preflight.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $PreflightLog) | Out-Null
if((Split-Path $Python -Leaf) -ieq 'py.exe'){& $Python -3 $Preflight --repair --json $PreflightLog}else{& $Python $Preflight --repair --json $PreflightLog}
if($LASTEXITCODE -ne 0){Fail 'PostgreSQL est migre mais le controle runtime a echoue. Ne lancez pas Nelyio avant correction.';exit 15}
Ok 'Migration totale et schema runtime PostgreSQL verifies.'
Write-Host ''
Write-Host 'Vous pouvez maintenant lancer START_NELYIO.bat.' -ForegroundColor Green
Write-Host 'Les fichiers SQLite sont conserves uniquement comme sauvegarde/migration.' -ForegroundColor Yellow
Read-Host 'Appuyez sur Entree pour fermer' | Out-Null
