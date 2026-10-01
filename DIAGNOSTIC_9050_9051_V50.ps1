param([switch]$NoPause)
$ErrorActionPreference='Continue'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$CaddyHelper=Join-Path $Root 'NELYIO_CADDY.ps1'
$CaddyConfig=Join-Path $Root 'Caddyfile'
function Tcp([string]$HostName,[int]$Port){$c=New-Object Net.Sockets.TcpClient;try{$a=$c.BeginConnect($HostName,$Port,$null,$null);if(-not $a.AsyncWaitHandle.WaitOne(1000,$false)){return $false};$c.EndConnect($a);return $true}catch{return $false}finally{$c.Close()}}
function Https([string]$Url,[bool]$IgnoreCert=$false){$old=[Net.ServicePointManager]::ServerCertificateValidationCallback;try{if($IgnoreCert){[Net.ServicePointManager]::ServerCertificateValidationCallback={$true}};$r=Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5;return @{Ok=($r.StatusCode -eq 200);Text=('HTTP '+$r.StatusCode)}}catch{return @{Ok=$false;Text=$_.Exception.Message}}finally{[Net.ServicePointManager]::ServerCertificateValidationCallback=$old}}
function Owner([int]$Port){try{$id=Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop|Select-Object -First 1 -ExpandProperty OwningProcess;$p=Get-Process -Id $id -ErrorAction SilentlyContinue;return "PID $id / $($p.ProcessName)"}catch{return 'aucun'}}
Write-Host '=== NELYIO HTTPS DIAGNOSTIC v50 ===' -ForegroundColor Cyan
$backend=Tcp '127.0.0.1' 9051
Write-Host ('1. Backend 9051 TCP : '+$(if($backend){'OK'}else{'ECHEC'})+' ('+(Owner 9051)+')') -ForegroundColor $(if($backend){'Green'}else{'Red'})
try{$h=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:9051/healthz' -TimeoutSec 3;Write-Host ('2. Backend /healthz  : HTTP '+$h.StatusCode) -ForegroundColor Green}catch{Write-Host ('2. Backend /healthz  : ECHEC - '+$_.Exception.Message) -ForegroundColor Red}
$front=Tcp '127.0.0.1' 9050
Write-Host ('3. Caddy 9050 TCP    : '+$(if($front){'OK'}else{'ECHEC'})+' ('+(Owner 9050)+')') -ForegroundColor $(if($front){'Green'}else{'Red'})
$local=Https 'https://localhost:9050/healthz' $true
Write-Host ('4. HTTPS local        : '+$local.Text) -ForegroundColor $(if($local.Ok){'Green'}else{'Red'})
$dnsOk=$false
try{$ips=[Net.Dns]::GetHostAddresses('stock-manager.nelyio.local')|ForEach-Object{$_.IPAddressToString};$dnsOk=$ips.Count -gt 0;Write-Host ('5. DNS Nelyio         : '+($ips -join ', ')) -ForegroundColor Green}catch{Write-Host ('5. DNS Nelyio         : ECHEC - '+$_.Exception.Message) -ForegroundColor Yellow}
if($dnsOk){$named=Https 'https://stock-manager.nelyio.local:9050/healthz' $false;Write-Host ('6. HTTPS + certificat : '+$named.Text) -ForegroundColor $(if($named.Ok){'Green'}else{'Yellow'})}else{$named=@{Ok=$false;Text='non teste'}}
$fw=Get-NetFirewallRule -DisplayName 'Nelyio HTTPS 9050' -ErrorAction SilentlyContinue
Write-Host ('7. Pare-feu 9050      : '+$(if($fw){'regle presente'}else{'regle absente'})) -ForegroundColor $(if($fw){'Green'}else{'Yellow'})
$caUser=$false
try{$roots=Get-ChildItem Cert:\CurrentUser\Root -ErrorAction Stop;$caUser=($roots|Where-Object{$_.Subject -like '*Caddy*' -or $_.Issuer -like '*Caddy*'}|Measure-Object).Count -gt 0}catch{}
Write-Host ('8. CA Caddy utilisateur: '+$(if($caUser){'presente'}else{'non detectee'})) -ForegroundColor $(if($caUser){'Green'}else{'Yellow'})
if(Test-Path $CaddyHelper){
    $caddyExe=$null
    if($env:NELYIO_CADDY_EXE -and (Test-Path $env:NELYIO_CADDY_EXE)){$caddyExe=$env:NELYIO_CADDY_EXE}
    elseif(Test-Path (Join-Path $Root 'caddy.exe')){$caddyExe=Join-Path $Root 'caddy.exe'}
    elseif(Test-Path (Join-Path $Root 'tools\caddy.exe')){$caddyExe=Join-Path $Root 'tools\caddy.exe'}
    else{$cmd=Get-Command caddy.exe -ErrorAction SilentlyContinue;if($cmd){$caddyExe=$cmd.Source}}
    Write-Host ('9. Caddy binaire       : '+$(if($caddyExe){$caddyExe}else{'ABSENT'})) -ForegroundColor $(if($caddyExe){'Green'}else{'Red'})
    $p=Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',('"'+$CaddyHelper+'"'),'-Action','Validate','-NoPause') -WorkingDirectory $Root -Wait -PassThru -WindowStyle Hidden
    Write-Host ('10. Caddyfile          : '+$(if($p.ExitCode -eq 0){'VALIDE'}else{'INVALIDE / CADDY ABSENT'})) -ForegroundColor $(if($p.ExitCode -eq 0){'Green'}else{'Red'})
}else{Write-Host '9. Gestionnaire Caddy : ABSENT' -ForegroundColor Red}
Write-Host ''
if(-not $backend){Write-Host 'CONCLUSION: demarrer/corriger le backend 9051.' -ForegroundColor Red}
elseif(-not $front -or -not $local.Ok){Write-Host 'CONCLUSION: backend OK, probleme Caddy local/configuration 9050.' -ForegroundColor Red}
elseif(-not $dnsOk){Write-Host 'CONCLUSION: Caddy fonctionne; corriger uniquement le DNS stock-manager.nelyio.local.' -ForegroundColor Yellow}
elseif(-not $named.Ok){Write-Host 'CONCLUSION: Caddy + DNS fonctionnent; installer/deployer la CA Caddy sur les postes clients.' -ForegroundColor Yellow}
elseif(-not $fw){Write-Host 'CONCLUSION: local OK; ajouter la regle pare-feu 9050 pour les autres postes.' -ForegroundColor Yellow}
else{Write-Host 'CONCLUSION: backend, Caddy, DNS, certificat et pare-feu sont coherents sur ce serveur.' -ForegroundColor Green}
if(-not $NoPause){Read-Host 'Appuyez sur Entree pour fermer'|Out-Null}
