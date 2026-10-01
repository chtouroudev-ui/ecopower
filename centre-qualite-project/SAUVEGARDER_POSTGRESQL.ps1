$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile=Join-Path $Root 'data\postgres.env'
if(-not (Test-Path $EnvFile)){Write-Host '[ERREUR] PostgreSQL non configure.' -ForegroundColor Red;exit 2}
$line=Get-Content $EnvFile | Where-Object {$_ -like 'NELYIO_DATABASE_URL=*'} | Select-Object -First 1
if(-not $line){Write-Host '[ERREUR] NELYIO_DATABASE_URL absent.' -ForegroundColor Red;exit 3}
$Url=$line.Substring('NELYIO_DATABASE_URL='.Length)
try{$Uri=[Uri]$Url}catch{Write-Host '[ERREUR] URL PostgreSQL invalide.' -ForegroundColor Red;exit 3}
$pgdump=Get-Command pg_dump.exe -ErrorAction SilentlyContinue
$pgrestore=Get-Command pg_restore.exe -ErrorAction SilentlyContinue
if(-not $pgdump){
  $base="$env:ProgramFiles\PostgreSQL"
  if(Test-Path $base){
    $bin=Get-ChildItem $base -Directory | Sort-Object Name -Descending | ForEach-Object {Join-Path $_.FullName 'bin'} | Where-Object {Test-Path (Join-Path $_ 'pg_dump.exe')} | Select-Object -First 1
    if($bin){$pgdump=@{Source=(Join-Path $bin 'pg_dump.exe')};if(Test-Path (Join-Path $bin 'pg_restore.exe')){$pgrestore=@{Source=(Join-Path $bin 'pg_restore.exe')}}}
  }
}
if(-not $pgdump){Write-Host '[ERREUR] pg_dump.exe introuvable.' -ForegroundColor Red;exit 4}
$user=[Uri]::UnescapeDataString($Uri.UserInfo.Split(':')[0])
$pass=''
if($Uri.UserInfo.Contains(':')){$pass=[Uri]::UnescapeDataString($Uri.UserInfo.Substring($Uri.UserInfo.IndexOf(':')+1))}
$db=$Uri.AbsolutePath.TrimStart('/')
$hostName=$Uri.Host
$port=if($Uri.Port -gt 0){$Uri.Port}else{5432}
$dir=Join-Path $Root 'backups\postgresql';New-Item -ItemType Directory -Force -Path $dir | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss';$out=Join-Path $dir "nelyio_$stamp.dump"
$env:PGPASSWORD=$pass
try{
  & $pgdump.Source --format=custom --no-owner --no-acl --host=$hostName --port=$port --username=$user --dbname=$db --file=$out
  if($LASTEXITCODE -ne 0){Write-Host '[ERREUR] pg_dump a echoue.' -ForegroundColor Red;exit 5}
  if($pgrestore){
    & $pgrestore.Source --list $out | Out-Null
    if($LASTEXITCODE -ne 0){Write-Host '[ERREUR] Le dump cree n est pas relisible par pg_restore.' -ForegroundColor Red;exit 6}
  }
}finally{Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue}
if(-not (Test-Path $out) -or (Get-Item $out).Length -le 0){Write-Host '[ERREUR] Fichier de sauvegarde vide.' -ForegroundColor Red;exit 7}
Write-Host "[OK] Sauvegarde PostgreSQL verifiee : $out" -ForegroundColor Green
