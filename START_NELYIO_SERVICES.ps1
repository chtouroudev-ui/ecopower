param([switch]$NoPause)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir=Join-Path $Root 'run'
$LogDir=Join-Path $Root 'logs'
New-Item -ItemType Directory -Force -Path $RunDir,$LogDir | Out-Null
$env:NELYIO_EXTERNAL_SERVICES='1'
$env:NELYIO_SKIP_STARTUP_DETAILS_SYNC='1'
$env:PYTHONUTF8='1'
$env:PYTHONUNBUFFERED='1'

function Find-Python {
    foreach($relative in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')){
        $candidate=Join-Path $Root $relative
        if(Test-Path -LiteralPath $candidate -PathType Leaf){return @{Exe=$candidate;Prefix=@()}}
    }
    $py=Get-Command py.exe -ErrorAction SilentlyContinue
    if($py){return @{Exe=$py.Source;Prefix=@('-3')}}
    $python=Get-Command python.exe -ErrorAction SilentlyContinue
    if($python){return @{Exe=$python.Source;Prefix=@()}}
    return $null
}
function Process-Matches([int]$Id,[string]$ScriptPath){
    $p=Get-Process -Id $Id -ErrorAction SilentlyContinue
    if(-not $p -or $p.ProcessName -notmatch 'python|py'){return $false}
    $cmd=(Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction SilentlyContinue).CommandLine
    return [bool]($cmd -and $cmd.IndexOf($ScriptPath,[StringComparison]::OrdinalIgnoreCase) -ge 0)
}
function Find-ServicePids([string]$ScriptPath){
    $ids=@()
    foreach($row in (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)){
        if($row.Name -notmatch '^(python|pythonw|py)(\.exe)?$'){continue}
        if($row.CommandLine -and $row.CommandLine.IndexOf($ScriptPath,[StringComparison]::OrdinalIgnoreCase) -ge 0){$ids+=([int]$row.ProcessId)}
    }
    return @($ids | Sort-Object -Unique)
}
function Start-ServiceProcess([string]$Name,[string]$Script,[hashtable]$Python){
    $scriptPath=Join-Path $Root $Script
    $pidFile=Join-Path $RunDir ($Name+'.pid')
    $stopFile=Join-Path $RunDir ($Name+'.stop')
    # A clean start must never inherit a stop request from a previous crash.
    Remove-Item $stopFile -Force -ErrorAction SilentlyContinue
    if(Test-Path $pidFile){
        $raw=(Get-Content $pidFile -First 1 -ErrorAction SilentlyContinue).Trim()
        if($raw -match '^\d+$' -and (Process-Matches ([int]$raw) $scriptPath)){
            Write-Host "[OK] Service $Name deja actif (PID $raw)." -ForegroundColor Green
            return
        }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    # Recover an orphaned worker if the PID file was lost. Do not launch a
    # duplicate importer/live worker because they would contend on the same DB.
    $existing=@(Find-ServicePids $scriptPath)
    if($existing.Count -eq 1){
        $adopt=[int]$existing[0]
        Set-Content -Path $pidFile -Value $adopt -Encoding ASCII
        Write-Host "[OK] Service $Name retrouve et adopte (PID $adopt)." -ForegroundColor Green
        return
    }
    if($existing.Count -gt 1){
        # Duplicate workers are unsafe (double imports/live publication). Ask
        # every exact matching worker to stop, then start one clean instance.
        Set-Content -LiteralPath $stopFile -Value ((Get-Date).ToString('o')) -Encoding ASCII
        Write-Host "[AVERTISSEMENT] $($existing.Count) processus $Name dupliques detectes; consolidation." -ForegroundColor Yellow
        for($i=0;$i -lt 40;$i++){
            $remaining=@($existing | Where-Object {Get-Process -Id $_ -ErrorAction SilentlyContinue})
            if(-not $remaining.Count){break}
            Start-Sleep -Milliseconds 250
        }
        foreach($procId in $existing){
            if((Get-Process -Id $procId -ErrorAction SilentlyContinue) -and (Process-Matches $procId $scriptPath)){
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $stopFile -Force -ErrorAction SilentlyContinue
    }
    $out=Join-Path $LogDir ($Name+'_stdout.log')
    $err=Join-Path $LogDir ($Name+'_stderr.log')
    $args=@();$args+=$Python.Prefix;$args+=('"'+$scriptPath+'"')
    $proc=Start-Process -FilePath $Python.Exe -ArgumentList $args -WorkingDirectory $Root -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -WindowStyle Hidden
    Set-Content -Path $pidFile -Value $proc.Id -Encoding ASCII
    Start-Sleep -Milliseconds 700
    $proc.Refresh()
    if($proc.HasExited){
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
        Write-Host "[ERREUR] Service $Name arrete au demarrage. Voir $err" -ForegroundColor Red
        throw "Service $Name indisponible"
    }
    Write-Host "[OK] Service $Name demarre (PID $($proc.Id))." -ForegroundColor Green
}

$Python=Find-Python
if(-not $Python){throw 'Python 3 introuvable pour les services Nelyio.'}
Start-ServiceProcess 'live_service' 'live_service.py' $Python
Start-ServiceProcess 'analytics_service' 'analytics_service.py' $Python
Write-Host '[INFO] Import SIMPLIFY2 desactive en service permanent. Utilisez OPEN_NELYIO_IMPORTER.bat.' -ForegroundColor Cyan
if(-not $NoPause){Read-Host 'Services Nelyio actifs. Appuyez sur Entree pour fermer' | Out-Null}
