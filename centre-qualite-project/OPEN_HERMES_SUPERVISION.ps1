param(
    [ValidateRange(1024,65535)]
    [int]$Port = 9222,
    [string]$DirectSupervisionUrl = "https://fr06-supervision.vocalcom.com/hermes360/Supervision/Login.aspx?Id_Admin=1&Culture_inf=fr-FR&Oid_Company=hzKSeX0K&Oid_Network=&Oid_Network_Agent=WAN&Station=&Phone=&COLOR=LIGHT&Tz=Romance%20Standard%20Time",
    [ValidateRange(5,60)]
    [int]$WaitSeconds = 20
)

$ErrorActionPreference = 'Stop'
$Profile = Join-Path $env:LOCALAPPDATA 'TECH-IN\Nelyio\CaptureBrowser'
$CdpBase = "http://127.0.0.1:$Port"

function Get-EdgePath {
    $candidates = @(
        (Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe')
    )
    return $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}

function Get-CdpTargets {
    try { return @(Invoke-RestMethod -Uri "$CdpBase/json/list" -TimeoutSec 3) }
    catch { return @() }
}

function Test-CdpPort {
    try {
        $v = Invoke-RestMethod -Uri "$CdpBase/json/version" -TimeoutSec 2
        return [bool]$v.webSocketDebuggerUrl
    }
    catch { return $false }
}

function Get-NelyioEdgeProcesses {
    $needleProfile = [IO.Path]::GetFullPath($Profile).TrimEnd('\')
    $rows = @(Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue)
    return @($rows | Where-Object {
        $cmd = [string]$_.CommandLine
        $cmd -and ($cmd -like "*$needleProfile*")
    })
}

function Test-NelyioEdgeProcess {
    $rows = Get-NelyioEdgeProcesses
    foreach ($row in $rows) {
        $cmd = [string]$row.CommandLine
        if ($cmd -like "*remote-debugging-port=$Port*") { return $true }
    }
    return $false
}

function Stop-StaleNelyioEdge {
    $rows = Get-NelyioEdgeProcesses
    if (-not $rows) { return }
    Write-Host "Profil Edge Nelyio deja present sans CDP valide : redemarrage du profil dedie uniquement." -ForegroundColor Yellow
    foreach ($row in $rows) {
        try { Stop-Process -Id ([int]$row.ProcessId) -Force -ErrorAction Stop }
        catch { Write-Warning ("Impossible d'arreter le processus Edge Nelyio PID " + $row.ProcessId + ': ' + $_.Exception.Message) }
    }
    Start-Sleep -Milliseconds 800
}

function Wait-Cdp([int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        if (Test-CdpPort) { return $true }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Find-HermesTarget {
    return Get-CdpTargets | Where-Object {
        $_.type -eq 'page' -and (
            ([string]$_.url) -like '*fr06-supervision.vocalcom.com*' -or
            ([string]$_.url) -like '*fr06-cloud.vocalcom.com*'
        )
    } | Select-Object -First 1
}

function Wait-HermesTarget([int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $target = Find-HermesTarget
        if ($target) { return $target }
        Start-Sleep -Milliseconds 400
    } while ((Get-Date) -lt $deadline)
    return $null
}

$browser = Get-EdgePath
if (-not $browser) {
    Write-Error 'Microsoft Edge introuvable.'
    exit 1
}

New-Item -ItemType Directory -Path $Profile -Force | Out-Null

if (Test-CdpPort) {
    if (-not (Test-NelyioEdgeProcess)) {
        Write-Error "Le port CDP local $Port est utilise par un navigateur qui ne correspond pas au profil Nelyio. Aucun processus tiers ne sera modifie."
        exit 2
    }

    $target = Find-HermesTarget
    if ($target -and ([string]$target.url) -like '*fr06-supervision.vocalcom.com*') {
        try { Invoke-WebRequest -UseBasicParsing -Uri "$CdpBase/json/activate/$($target.id)" -TimeoutSec 3 | Out-Null } catch { }
        Write-Host 'Supervision Hermes deja ouverte dans Edge Nelyio.' -ForegroundColor Green
        exit 0
    }

    $openArgs = @("--user-data-dir=$Profile", '--new-tab', $DirectSupervisionUrl)
    Start-Process -FilePath $browser -ArgumentList $openArgs | Out-Null
    $target = Wait-HermesTarget $WaitSeconds
    if (-not $target) {
        Write-Error 'Edge Nelyio repond en CDP mais aucun onglet Hermes n est apparu dans le delai.'
        exit 4
    }
    Write-Host ('Onglet Hermes ouvert : ' + [string]$target.url) -ForegroundColor Green
    exit 0
}

# If the dedicated profile is already running but without the expected CDP port,
# a second Edge process normally forwards the URL to the stale profile and ignores
# the new remote-debugging flags. Restart ONLY this dedicated Nelyio profile.
Stop-StaleNelyioEdge

$launchArgs = @(
    '--remote-debugging-address=127.0.0.1',
    "--remote-debugging-port=$Port",
    "--user-data-dir=$Profile",
    '--no-first-run',
    '--new-window',
    $DirectSupervisionUrl
)
Start-Process -FilePath $browser -ArgumentList $launchArgs | Out-Null

if (-not (Wait-Cdp $WaitSeconds)) {
    Write-Error "Edge a ete lance mais le port CDP 127.0.0.1:$Port ne repond pas. Verifiez logs et session Windows interactive."
    exit 3
}

$target = Wait-HermesTarget $WaitSeconds
if (-not $target) {
    Write-Error 'CDP est disponible mais aucun onglet Hermes n a ete detecte.'
    exit 4
}

Write-Host ('Edge Nelyio et Hermes sont disponibles : ' + [string]$target.url) -ForegroundColor Green
exit 0
