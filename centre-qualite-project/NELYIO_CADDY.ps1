#requires -Version 5.1
param(
    [ValidateSet('Start','Stop','Status','Validate','Trust')][string]$Action='Status',
    [switch]$NoPause
)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir=Join-Path $Root 'logs'
$RunDir=Join-Path $Root 'run'
$Config=Join-Path $Root 'Caddyfile'
$PidFile=Join-Path $RunDir 'caddy.pid'
$VersionMeta=(Get-Content -LiteralPath (Join-Path $Root 'VERSION.json') -Raw | ConvertFrom-Json)
$ExpectedBuild=[string]$VersionMeta.version
if($VersionMeta.runtime_revision){$ExpectedBuild=$ExpectedBuild+'+'+[string]$VersionMeta.runtime_revision}
New-Item -ItemType Directory -Force -Path $LogDir,$RunDir | Out-Null
. (Join-Path $Root 'NELYIO_LAUNCHER_COMMON.ps1')

function Resolve-CaddyExe {
    $candidates=New-Object System.Collections.Generic.List[string]
    if($env:NELYIO_CADDY_EXE){$candidates.Add($env:NELYIO_CADDY_EXE)}
    $candidates.Add((Join-Path $Root 'caddy.exe'))
    $candidates.Add((Join-Path $Root 'tools\caddy.exe'))
    $cmd=Get-Command caddy.exe -ErrorAction SilentlyContinue
    if($cmd -and $cmd.Source){$candidates.Add($cmd.Source)}
    foreach($candidate in $candidates){
        if($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)){return (Resolve-Path -LiteralPath $candidate).Path}
    }
    return $null
}
function Test-Frontend {
    return (Test-NelyioHealth -Url 'https://localhost:9050/healthz' -ExpectedBuild $ExpectedBuild -DiagnosticLocalTls -TimeoutMilliseconds 2500)
}
function Read-CaddyPid {
    if(-not(Test-Path -LiteralPath $PidFile -PathType Leaf)){return $null}
    $raw=(Get-Content -LiteralPath $PidFile -First 1 -ErrorAction SilentlyContinue).Trim()
    if($raw -match '^\d+$'){return [int]$raw}
    return $null
}

function Get-PortOwner([int]$Port){
    try{return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess}
    catch{return $null}
}
function Test-NelyioCaddyPid([int]$Id){
    $proc=Get-Process -Id $Id -ErrorAction SilentlyContinue
    if(-not $proc -or $proc.ProcessName -notmatch '^caddy$'){return $false}
    $cmd=(Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction SilentlyContinue).CommandLine
    if(-not $cmd){return $false}
    return ($cmd.IndexOf($Config,[StringComparison]::OrdinalIgnoreCase) -ge 0)
}
function Resolve-NelyioCaddyPid {
    $pidValue=Read-CaddyPid
    if($null -ne $pidValue -and (Test-NelyioCaddyPid $pidValue)){return $pidValue}
    if(Test-Path -LiteralPath $PidFile){Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue}
    $owner=Get-PortOwner 9050
    if($owner -and (Test-NelyioCaddyPid ([int]$owner))){
        Set-Content -LiteralPath $PidFile -Value ([int]$owner) -Encoding ASCII
        return [int]$owner
    }
    return $null
}
function Stop-TrackedCaddy {
    $pidValue=Resolve-NelyioCaddyPid
    if($null -eq $pidValue){return $false}
    if(-not(Test-NelyioCaddyPid $pidValue)){return $false}
    # Ask Caddy's loopback admin endpoint to shut itself down first so sockets
    # and certificates are released cleanly. Fall back to the exact tracked PID
    # only if the admin stop command cannot complete.
    try{
        $exe=Resolve-CaddyExe
        if($exe){
            $stop=Invoke-NelyioChildProcess -Executable $exe -ProcessArguments @('stop','--address','127.0.0.1:2019') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'caddy_stop') -TimeoutSeconds 15
        }
    }catch{}
    for($i=0;$i -lt 30;$i++){
        if(-not(Get-Process -Id $pidValue -ErrorAction SilentlyContinue)){break}
        Start-Sleep -Milliseconds 150
    }
    if(Get-Process -Id $pidValue -ErrorAction SilentlyContinue){
        Stop-Process -Id $pidValue -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 300
    }
    if(Get-Process -Id $pidValue -ErrorAction SilentlyContinue){Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue}
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    return $true
}
function Run-CaddyCommand([string[]]$Arguments,[string]$Prefix,[int]$Timeout=45){
    $exe=Resolve-CaddyExe
    if(-not $exe){Write-Host '[ERREUR] Caddy introuvable. Placez caddy.exe a cote de START_NELYIO_HTTPS.bat, dans tools\, dans PATH, ou definissez NELYIO_CADDY_EXE.' -ForegroundColor Red;return 41}
    $result=Invoke-NelyioChildProcess -Executable $exe -ProcessArguments $Arguments -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir $Prefix) -TimeoutSeconds $Timeout
    if($result.ExitCode -ne 0){Write-Host ("[ERREUR] Caddy code {0}. Voir {1} et {2}." -f $result.ExitCode,$result.StdoutPath,$result.StderrPath) -ForegroundColor Red}
    return [int]$result.ExitCode
}

$code=1
try {
    switch($Action){
        'Status' {
            if(Test-Frontend){$adopted=Resolve-NelyioCaddyPid;Write-Host '[OK] HTTPS Nelyio repond sur https://localhost:9050/' -ForegroundColor Green;$code=0}
            elseif(Test-NelyioPort -Port 9050){Write-Host '[ERREUR] Le port 9050 est occupe mais /healthz Nelyio ne repond pas.' -ForegroundColor Red;$code=2}
            else{Write-Host '[INFO] Caddy Nelyio est arrete.' -ForegroundColor Yellow;$code=1}
        }
        'Validate' {
            if(-not(Test-Path -LiteralPath $Config -PathType Leaf)){throw "Caddyfile introuvable : $Config"}
            $code=Run-CaddyCommand @('validate','--config',$Config,'--adapter','caddyfile') 'caddy_validate' 45
            if($code -eq 0){Write-Host '[OK] Caddyfile valide.' -ForegroundColor Green}
        }
        'Start' {
            if(Test-Frontend){$adopted=Resolve-NelyioCaddyPid;Write-Host '[OK] Caddy deja actif.' -ForegroundColor Green;$code=0;break}
            if(Test-NelyioPort -Port 9050){
                # A previous Nelyio Caddy may still own 9050 after a launcher or
                # PID-file failure. Recover only our exact Caddy command line;
                # never kill an unrelated listener.
                $existing=Resolve-NelyioCaddyPid
                if($existing){
                    Write-Host ("[INFO] Ancien Caddy Nelyio PID {0} detecte sur 9050; redemarrage propre." -f $existing) -ForegroundColor Yellow
                    Stop-TrackedCaddy | Out-Null
                    Start-Sleep -Milliseconds 300
                }else{
                    throw 'Port 9050 deja utilise par un autre service. Arretez ce service avant de lancer Nelyio HTTPS.'
                }
            }
            if(Test-NelyioPort -Port 9050){throw 'Le port 9050 reste occupe apres la tentative de reprise Caddy.'}
            if(-not(Test-Path -LiteralPath $Config -PathType Leaf)){throw "Caddyfile introuvable : $Config"}
            $exe=Resolve-CaddyExe
            if(-not $exe){Write-Host '[ERREUR] Caddy introuvable. Placez caddy.exe a cote de START_NELYIO_HTTPS.bat, dans tools\, dans PATH, ou definissez NELYIO_CADDY_EXE.' -ForegroundColor Red;$code=41;break}
            $validation=Run-CaddyCommand @('validate','--config',$Config,'--adapter','caddyfile') 'caddy_validate' 45
            if($validation -ne 0){$code=42;break}
            Stop-TrackedCaddy | Out-Null
            $stdout=Join-Path $LogDir 'caddy_stdout.log';$stderr=Join-Path $LogDir 'caddy_stderr.log'
            $args=((@('run','--config',$Config,'--adapter','caddyfile') | ForEach-Object { ConvertTo-NelyioProcessArgument $_ }) -join ' ')
            $proc=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $Root -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
            Set-Content -LiteralPath $PidFile -Value $proc.Id -Encoding ASCII
            $healthy=$false
            for($i=0;$i -lt 50;$i++){
                if($proc.HasExited){break}
                if(Test-Frontend){$healthy=$true;break}
                Start-Sleep -Milliseconds 200
                $proc.Refresh()
            }
            if(-not $healthy){
                try{if(-not $proc.HasExited){Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue}}catch{}
                Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
                Write-Host '[ERREUR] Caddy a demarre mais le reverse proxy Nelyio ne repond pas. Voir logs\caddy_stderr.log.' -ForegroundColor Red
                $code=43
            }else{Write-Host ("[OK] Caddy actif (PID {0}) sur HTTPS 9050." -f $proc.Id) -ForegroundColor Green;$code=0}
            $proc.Dispose()
        }
        'Stop' {
            if(Stop-TrackedCaddy){Write-Host '[OK] Caddy Nelyio arrete.' -ForegroundColor Green;$code=0}
            elseif(-not(Test-NelyioPort -Port 9050)){Write-Host '[OK] Aucun Caddy Nelyio actif.' -ForegroundColor Green;$code=0}
            else{Write-Host '[ERREUR] Port 9050 actif mais aucun PID Caddy Nelyio valide n est enregistre; aucun processus inconnu n a ete tue.' -ForegroundColor Red;$code=44}
        }
        'Trust' {
            if(-not(Test-Frontend)){throw 'Demarrez d abord Caddy afin de creer son autorite locale.'}
            $code=Run-CaddyCommand @('trust') 'caddy_trust' 60
            if($code -eq 0){Write-Host '[OK] Autorite locale Caddy approuvee pour ce poste/utilisateur.' -ForegroundColor Green}
            else{Write-Host '[INFO] Si Windows demande des droits, relancez cette action en administrateur.' -ForegroundColor Yellow}
        }
    }
} catch {
    Write-Host ('[ERREUR] '+$_.Exception.Message) -ForegroundColor Red
    try{Add-Content -LiteralPath (Join-Path $LogDir 'caddy_manager.log') -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss')+' '+$_.Exception.Message) -Encoding UTF8}catch{}
    $code=49
}
if(-not $NoPause -and $Host.Name -match 'ConsoleHost' -and $Action -in @('Validate','Trust')){Read-Host 'Appuyez sur Entree pour fermer' | Out-Null}
exit ([int]$code)
