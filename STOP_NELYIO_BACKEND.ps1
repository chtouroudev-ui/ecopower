param([switch]$NoPause)
$ErrorActionPreference='SilentlyContinue'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$RunDir=Join-Path $Root 'run'
$PidFile=Join-Path $RunDir 'backend.pid'
$ExpectedApp=Join-Path $Root 'app.py'
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Port-Owner {
    try { return Get-NetTCPConnection -LocalPort 9051 -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess }
    catch { return $null }
}
function Confirm-BackendProcess([int]$Id) {
    if($Id -le 0){return $false}
    $p=Get-Process -Id $Id -ErrorAction SilentlyContinue
    if(-not $p -or $p.ProcessName -notmatch '^(python|pythonw|py)$'){return $false}
    $cmd=(Get-CimInstance Win32_Process -Filter "ProcessId=$Id" -ErrorAction SilentlyContinue).CommandLine
    return [bool]($cmd -and $cmd.IndexOf($ExpectedApp,[StringComparison]::OrdinalIgnoreCase) -ge 0)
}
function Matching-BackendPids {
    $ids=New-Object System.Collections.Generic.List[int]
    try {
        foreach($w in Get-CimInstance Win32_Process -ErrorAction Stop){
            if($w.ProcessId -and $w.Name -match '^(python|pythonw|py)(\.exe)?$' -and $w.CommandLine -and
               $w.CommandLine.IndexOf($ExpectedApp,[StringComparison]::OrdinalIgnoreCase) -ge 0){
                if(-not $ids.Contains([int]$w.ProcessId)){$ids.Add([int]$w.ProcessId)}
            }
        }
    } catch {}
    return @($ids)
}
function Stop-Verified([int]$Id) {
    if(-not (Confirm-BackendProcess $Id)){return $false}
    Write-Host "Arret du backend Nelyio PID $Id"
    Stop-Process -Id $Id -ErrorAction SilentlyContinue
    for($i=0;$i -lt 25;$i++){
        if(-not(Get-Process -Id $Id -ErrorAction SilentlyContinue)){return $true}
        Start-Sleep -Milliseconds 120
    }
    if(Get-Process -Id $Id -ErrorAction SilentlyContinue){Stop-Process -Id $Id -Force -ErrorAction SilentlyContinue}
    return -not [bool](Get-Process -Id $Id -ErrorAction SilentlyContinue)
}

$candidates=New-Object System.Collections.Generic.List[int]
if(Test-Path -LiteralPath $PidFile -PathType Leaf){
    $raw=(Get-Content -LiteralPath $PidFile -First 1 -ErrorAction SilentlyContinue).Trim()
    if($raw -match '^\d+$'){$candidates.Add([int]$raw)}
}
$owner=Port-Owner
if($owner -and -not $candidates.Contains([int]$owner)){$candidates.Add([int]$owner)}
foreach($id in Matching-BackendPids){if(-not $candidates.Contains([int]$id)){$candidates.Add([int]$id)}}

$verifiedBefore=@($candidates | Where-Object {Confirm-BackendProcess ([int]$_)})
if($verifiedBefore.Count -gt 0){
    Set-Content -LiteralPath (Join-Path $RunDir 'backend.stop') -Value ((Get-Date).ToString('o')) -Encoding ASCII
    Write-Host '[INFO] Arret propre demande au backend Nelyio.'
    for($i=0;$i -lt 40;$i++){
        $alive=@($verifiedBefore | Where-Object {Get-Process -Id $_ -ErrorAction SilentlyContinue})
        if(-not $alive.Count){break}
        Start-Sleep -Milliseconds 200
    }
}
$stopped=0;$unsafe=$false
foreach($id in @($candidates)){
    if(Confirm-BackendProcess $id){if(Stop-Verified $id){$stopped++}}
    elseif($owner -and $id -eq [int]$owner){$unsafe=$true}
}
Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $RunDir 'backend.stop') -Force -ErrorAction SilentlyContinue
$ownerAfter=Port-Owner
if($ownerAfter){
    if(Confirm-BackendProcess ([int]$ownerAfter)){
        if(Stop-Verified ([int]$ownerAfter)){$stopped++}
        $ownerAfter=Port-Owner
    }
}
if($ownerAfter){
    Write-Host '[AVERTISSEMENT] Le port 9051 reste occupe par un processus qui ne correspond pas a ce projet. Aucun processus arbitraire n a ete tue.' -ForegroundColor Yellow
    exit 2
}
if($stopped -gt 0){Write-Host "[OK] Backend Nelyio arrete ($stopped processus verifie(s))." -ForegroundColor Green}
else{Write-Host '[OK] Aucun backend Nelyio actif.' -ForegroundColor Green}
exit 0
