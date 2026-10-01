param([switch]$NoPause)
$ErrorActionPreference='Continue'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir=Join-Path $Root 'run'
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null
$failed=$false

function Matching-ServicePids([string]$ScriptPath){
    $ids=New-Object System.Collections.Generic.List[int]
    try{
        foreach($w in Get-CimInstance Win32_Process -ErrorAction Stop){
            if($w.ProcessId -and $w.Name -match '^(python|pythonw|py)(\.exe)?$' -and $w.CommandLine -and
               $w.CommandLine.IndexOf($ScriptPath,[StringComparison]::OrdinalIgnoreCase) -ge 0){
                if(-not $ids.Contains([int]$w.ProcessId)){$ids.Add([int]$w.ProcessId)}
            }
        }
    }catch{}
    return @($ids)
}
function Stop-ServiceProcess([string]$Name,[string]$Script){
    $pidFile=Join-Path $RunDir ($Name+'.pid')
    $expected=Join-Path $Root $Script
    $ids=New-Object System.Collections.Generic.List[int]
    if(Test-Path -LiteralPath $pidFile -PathType Leaf){
        $raw=(Get-Content -LiteralPath $pidFile -First 1 -ErrorAction SilentlyContinue).Trim()
        if($raw -match '^\d+$'){$ids.Add([int]$raw)}
    }
    foreach($id in Matching-ServicePids $expected){if(-not $ids.Contains([int]$id)){$ids.Add([int]$id)}}
    $validIds=New-Object System.Collections.Generic.List[int]
    foreach($id in @($ids)){
        $p=Get-Process -Id $id -ErrorAction SilentlyContinue
        if(-not $p){continue}
        $cmd=(Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue).CommandLine
        if($p.ProcessName -notmatch '^(python|pythonw|py)$' -or -not $cmd -or $cmd.IndexOf($expected,[StringComparison]::OrdinalIgnoreCase) -lt 0){continue}
        if(-not $validIds.Contains([int]$id)){$validIds.Add([int]$id)}
    }
    $valid=$validIds.Count
    if($valid -gt 0){
        # Workers poll this flag and can commit/flush/close normally. Windows
        # Stop-Process is only the bounded fallback.
        Set-Content -LiteralPath (Join-Path $RunDir ($Name+'.stop')) -Value ((Get-Date).ToString('o')) -Encoding ASCII
        Write-Host "Arret propre demande a $Name ($valid processus verifie(s))"
        for($i=0;$i -lt 30;$i++){
            $alive=@($validIds | Where-Object {Get-Process -Id $_ -ErrorAction SilentlyContinue})
            if(-not $alive.Count){break}
            Start-Sleep -Milliseconds 200
        }
        foreach($id in @($validIds)){
            if(Get-Process -Id $id -ErrorAction SilentlyContinue){
                Write-Host "Arret force de secours $Name PID $id" -ForegroundColor Yellow
                Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
            }
            if(Get-Process -Id $id -ErrorAction SilentlyContinue){$script:failed=$true}
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $RunDir ($Name+'.stop')) -Force -ErrorAction SilentlyContinue
    if($valid -eq 0){Write-Host "[OK] $Name deja arrete."}
    else{Write-Host "[OK] $Name arrete ($valid processus verifie(s))." -ForegroundColor Green}
}
# Importer V60 est une application locale volontaire. import_service.py reste arrete par compatibilite si une ancienne instance subsiste.
Stop-ServiceProcess 'import_service' 'import_service.py'
Stop-ServiceProcess 'live_service' 'live_service.py'
Stop-ServiceProcess 'analytics_service' 'analytics_service.py'
if($failed){exit 1}else{exit 0}
