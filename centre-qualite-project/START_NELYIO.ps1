param(
    [switch]$NoBrowser,
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $Root
. (Join-Path $Root 'NELYIO_LAUNCHER_COMMON.ps1')
$LogDir = Join-Path $Root 'logs'
$RunDir = Join-Path $Root 'run'
New-Item -ItemType Directory -Force -Path $LogDir,$RunDir | Out-Null
$PidFile = Join-Path $RunDir 'backend.pid'
$StdoutLog = Join-Path $LogDir 'backend_9051_stdout.log'
$StderrLog = Join-Path $LogDir 'backend_9051_stderr.log'
$ServiceStart = Join-Path $Root 'START_NELYIO_SERVICES.ps1'
$ServiceStop = Join-Path $Root 'STOP_NELYIO_SERVICES.ps1'

function Write-Step([string]$Text) {
    Write-Host "[NELYIO] $Text" -ForegroundColor Cyan
}
function Write-Ok([string]$Text) {
    Write-Host "[OK] $Text" -ForegroundColor Green
}
function Write-Bad([string]$Text) {
    Write-Host "[ERREUR] $Text" -ForegroundColor Red
}

function Wait-User([string]$Message = 'Appuyez sur Entree pour fermer') {
    if (-not $NoPause) { Read-Host $Message | Out-Null }
}
function Test-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutMs = 800) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) { return $false }
        $client.EndConnect($iar)
        return $true
    } catch { return $false } finally { $client.Close() }
}
function Test-Health {
    $meta = Get-Content -LiteralPath (Join-Path $Root 'VERSION.json') -Raw | ConvertFrom-Json
    $expected = [string]$meta.version
    if ($meta.runtime_revision) { $expected = $expected + '+' + [string]$meta.runtime_revision }
    return Test-NelyioHealth -Url 'http://127.0.0.1:9051/healthz' -ExpectedBuild $expected -TimeoutMilliseconds 2000
}

function Find-Python {
    foreach ($relative in @('.venv\Scripts\python.exe','venv\Scripts\python.exe')) {
        $candidate = Join-Path $Root $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            & $candidate -c "import sys; assert sys.version_info >= (3, 10)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @{ Exe=$candidate; Prefix=@() } }
        }
    }
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & $py.Source -3 -c "import sys; assert sys.version_info >= (3, 10)" | Out-Null
            if ($LASTEXITCODE -eq 0) { return @{ Exe=$py.Source; Prefix=@('-3') } }
        } catch {}
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        try {
            & $python.Source -c "import sys; assert sys.version_info >= (3, 10)" | Out-Null
            if ($LASTEXITCODE -eq 0) { return @{ Exe=$python.Source; Prefix=@() } }
        } catch {}
    }
    return $null
}

Clear-Host
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ' NELYIO V59 - PostgreSQL PROD HARDENED' -ForegroundColor White
Write-Host '============================================================' -ForegroundColor DarkCyan
Write-Host ''

$PgEnv = Join-Path $Root 'data\postgres.env'
if (-not (Test-Path -LiteralPath $PgEnv -PathType Leaf)) {
    Write-Bad 'PostgreSQL n est pas encore configure pour cette edition.'
    Write-Host 'Lancez CONFIGURER_POSTGRESQL_AUTO.bat une seule fois, puis relancez START_NELYIO.bat.' -ForegroundColor Yellow
    Wait-User 'Appuyez sur Entree pour fermer'
    exit 9
}
Write-Ok 'Mode PostgreSQL configure (data\postgres.env).'

if (-not (Test-Path (Join-Path $Root 'app.py'))) {
    Write-Bad "app.py introuvable dans $Root"
    Wait-User 'Appuyez sur Entree pour fermer'
    exit 10
}

# Reverse-proxy mode: Caddy terminates HTTPS on 9050, Python always stays HTTP on 9051.
$env:TECHIN_HOST = '127.0.0.1'
$env:TECHIN_PORT = '9051'
$env:TECHIN_STRICT_PORT = '1'
$env:TECHIN_TLS = '0'
$env:NELYIO_EXTERNAL_SERVICES = '1'
# FIX4: supervision.py initialise son schema a l'import. La synchronisation
# complete de la base Details est couteuse et ne doit jamais bloquer l'ouverture
# du port 9051. Elle sera relancee en arriere-plan par app.py apres /healthz.
$env:NELYIO_SKIP_STARTUP_DETAILS_SYNC = '1'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
# Never inherit a previous graceful-stop request after a crashed launcher.
Remove-Item (Join-Path $RunDir 'backend.stop') -Force -ErrorAction SilentlyContinue

if (Test-Health) {
    try {
        $owner=Get-NetTCPConnection -LocalPort 9051 -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess
        $ownerProc=Get-Process -Id $owner -ErrorAction SilentlyContinue
        if($ownerProc -and $ownerProc.ProcessName -match 'python|py'){Set-Content -Path $PidFile -Value $owner -Encoding ASCII}
    } catch {}
    Write-Ok 'Le backend Nelyio est deja actif sur http://127.0.0.1:9051'
} else {
    if (Test-TcpPort '127.0.0.1' 9051) {
        # Recover a hung/older backend from this exact project. A healthy but
        # old build also lands here because Test-Health validates VERSION.json.
        $owner=$null;$ours=$false;$knownNelyio=$false;$runningBuild=''
        try{
            $owner=Get-NetTCPConnection -LocalPort 9051 -State Listen -ErrorAction Stop | Select-Object -First 1 -ExpandProperty OwningProcess
            $cmd=(Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue).CommandLine
            $ours=[bool]($cmd -and $cmd.IndexOf((Join-Path $Root 'app.py'),[StringComparison]::OrdinalIgnoreCase) -ge 0)
            try {
                $hr=Invoke-RestMethod -UseBasicParsing -Uri 'http://127.0.0.1:9051/healthz' -TimeoutSec 2
                $knownNelyio=[bool]($hr.ok -eq $true -and $hr.service -eq 'nelyio-backend')
                $runningBuild=[string]$hr.build
            } catch {}
        }catch{}
        if($ours -and (Test-Path -LiteralPath (Join-Path $Root 'STOP_NELYIO_BACKEND.ps1'))){
            Write-Step ("Ancien backend Nelyio PID $owner detecte sur 9051; reprise propre ...")
            $stopResult=Invoke-NelyioScript -ScriptPath (Join-Path $Root 'STOP_NELYIO_BACKEND.ps1') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'backend_recovery_stop') -TimeoutSeconds 30
            if($stopResult.ExitCode -ne 0 -or (Test-TcpPort '127.0.0.1' 9051)){
                Write-Bad 'Impossible de liberer proprement le backend Nelyio existant sur 9051.'
                Wait-User 'Appuyez sur Entree pour fermer'
                exit 11
            }
        }elseif($knownNelyio -and $owner){
            Write-Step ("Backend Nelyio d une autre revision detecte sur 9051 (PID $owner, build=$runningBuild). Bascule vers $Root ...")
            try { Stop-Process -Id $owner -Force -ErrorAction Stop } catch {
                Write-Bad ("Impossible d arreter l ancien backend Nelyio PID $owner : "+$_.Exception.Message)
                Wait-User 'Appuyez sur Entree pour fermer'
                exit 11
            }
            $deadline=(Get-Date).AddSeconds(12)
            while((Get-Date) -lt $deadline -and (Test-TcpPort '127.0.0.1' 9051)){ Start-Sleep -Milliseconds 250 }
            if(Test-TcpPort '127.0.0.1' 9051){
                Write-Bad 'L ancien backend Nelyio a ete arrete mais le port 9051 reste occupe.'
                Wait-User 'Appuyez sur Entree pour fermer'
                exit 11
            }
            Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
            Write-Ok 'Ancien backend Nelyio libere; demarrage de la revision courante.'
        }else{
            Write-Bad 'Le port 9051 est occupe par un service qui ne correspond pas au backend Nelyio de ce projet.'
            Write-Host ''
            Write-Host 'Processus detecte sur 9051 :' -ForegroundColor Yellow
            cmd /c 'netstat -ano | findstr :9051'
            Write-Host ''
            Write-Host 'Nelyio ne tue jamais un processus inconnu. Liberez 9051 puis relancez.' -ForegroundColor Yellow
            Wait-User 'Appuyez sur Entree pour fermer'
            exit 11
        }
    }

    $Python = Find-Python
    if (-not $Python) {
        Write-Bad 'Python 3 est introuvable. Ni py -3 ni python ne fonctionne.'
        Write-Host 'Installez Python 3 puis cochez Add Python to PATH, ou rendez py.exe disponible.' -ForegroundColor Yellow
        Wait-User 'Appuyez sur Entree pour fermer'
        exit 12
    }

    Write-Step ("Python detecte : " + $Python.Exe)

    # Avoid reusing a stale db_compat bytecode file after an in-place update.
    $PyCache = Join-Path $Root '__pycache__'
    if (Test-Path -LiteralPath $PyCache) {
        Get-ChildItem -LiteralPath $PyCache -Filter 'db_compat*.pyc' -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    }
    try {
        $CompatInfo = & $Python.Exe @($Python.Prefix) -c "import db_compat; print(db_compat.DB_COMPAT_BUILD + ' | ' + db_compat.__file__)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $CompatInfo) { Write-Ok ("Compatibilite PostgreSQL : " + $CompatInfo) }
    } catch {}

    # Production gate: repair only missing runtime objects, then validate the
    # four PostgreSQL schemas before app.py is allowed to start.
    $PgPreflight = Join-Path $Root 'postgres_runtime_preflight.py'
    $PgPreflightLog = Join-Path $LogDir 'postgres_runtime_preflight.json'
    if (-not (Test-Path -LiteralPath $PgPreflight -PathType Leaf)) {
        Write-Bad 'postgres_runtime_preflight.py est introuvable.'
        Wait-User 'Appuyez sur Entree pour fermer'
        exit 17
    }
    # Fast path: normal startups only validate the PostgreSQL runtime.  DDL
    # repair is attempted only when validation reports a missing/incompatible
    # runtime object.  This avoids replaying schema/index work on every boot.
    $PgPreflightConsoleLog = Join-Path $LogDir 'postgres_runtime_preflight_console.log'
    Remove-Item $PgPreflightConsoleLog -Force -ErrorAction SilentlyContinue
    Write-Step 'Controle PostgreSQL rapide (validation, sans DDL inutile) ...'
    $PgCheckOutput = @(& $Python.Exe @($Python.Prefix) $PgPreflight --startup --json $PgPreflightLog 2>&1)
    $PgCheckCode = $LASTEXITCODE
    if ($PgCheckOutput.Count -gt 0) {
        $PgCheckOutput | Set-Content -LiteralPath $PgPreflightConsoleLog -Encoding UTF8
        $PgCheckOutput | ForEach-Object { Write-Host $_ }
    }
    if ($PgCheckCode -ne 0) {
        Write-Step 'Schema PostgreSQL incomplet ou incompatible : tentative de reparation bornee ...'
        $PgRepairOutput = @(& $Python.Exe @($Python.Prefix) $PgPreflight --repair --startup --json $PgPreflightLog 2>&1)
        $PgRepairCode = $LASTEXITCODE
        if ($PgRepairOutput.Count -gt 0) {
            Add-Content -LiteralPath $PgPreflightConsoleLog -Value '--- REPARATION ---' -Encoding UTF8
            $PgRepairOutput | Add-Content -LiteralPath $PgPreflightConsoleLog -Encoding UTF8
            $PgRepairOutput | ForEach-Object { Write-Host $_ }
        }
        if ($PgRepairCode -ne 0) {
            Write-Bad 'Le controle PostgreSQL a echoue apres tentative de reparation. Nelyio ne sera pas lance avec un schema incomplet.'
            Write-Host ("Rapport JSON : " + $PgPreflightLog) -ForegroundColor Yellow
            Write-Host ("Journal console : " + $PgPreflightConsoleLog) -ForegroundColor Yellow
            if (Test-Path -LiteralPath $PgPreflightLog) {
                Write-Host '--- RAPPORT POSTGRESQL ---' -ForegroundColor Yellow
                Get-Content -LiteralPath $PgPreflightLog -Tail 120
            }
            Wait-User 'Appuyez sur Entree pour fermer'
            exit 18
        }
    }
    Write-Ok 'PostgreSQL pret pour cette version.'

    # Tell app.py that PostgreSQL runtime validation has already succeeded.
    # This prevents app.py from replaying the full schema DDL before opening
    # port 9051.  Also force unbuffered Python output so startup diagnostics
    # are immediately visible in backend_9051_stdout.log.
    $env:NELYIO_POSTGRES_PREFLIGHT_OK = '1'
    $env:PYTHONUNBUFFERED = '1'

    Remove-Item $StdoutLog,$StderrLog -Force -ErrorAction SilentlyContinue

    $ArgList = @()
    $ArgList += $Python.Prefix
    $ArgList += ('"' + (Join-Path $Root 'app.py') + '"')
    Write-Step 'Demarrage de Nelyio sur HTTP 127.0.0.1:9051 ...'
    try {
        $proc = Start-Process -FilePath $Python.Exe -ArgumentList $ArgList -WorkingDirectory $Root -RedirectStandardOutput $StdoutLog -RedirectStandardError $StderrLog -PassThru -WindowStyle Hidden
        Set-Content -Path $PidFile -Value $proc.Id -Encoding ASCII
    } catch {
        Write-Bad ("Impossible de lancer Python : " + $_.Exception.Message)
        Wait-User 'Appuyez sur Entree pour fermer'
        exit 13
    }

    # The application performs safe startup synchronization before binding
    # /healthz.  Fifteen seconds was too short on production data and caused
    # false code 14 failures while Python was still alive.
    $ready = $false
    $StartupWaitSeconds = 120
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $nextProgress = 10
    while ($watch.Elapsed.TotalSeconds -lt $StartupWaitSeconds) {
        Start-Sleep -Milliseconds 1000
        $proc.Refresh()
        if ($proc.HasExited) { break }
        if (Test-Health) { $ready = $true; break }
        $elapsed = [int]$watch.Elapsed.TotalSeconds
        if ($elapsed -ge $nextProgress) {
            $state = if (Test-TcpPort '127.0.0.1' 9051 250) { 'port 9051 ouvert, healthz en initialisation' } else { 'initialisation avant ouverture du port' }
            Write-Step ("Backend en initialisation : ${elapsed}s - $state")
            $nextProgress += 10
        }
    }
    $watch.Stop()
    if (-not $ready -and (Test-Health)) { $ready = $true }

    if (-not $ready) {
        if ($proc -and $proc.HasExited) {
            Write-Bad 'Le processus Python s est arrete avant que le backend soit pret.'
            Write-Host ("Python s est arrete avec le code " + $proc.ExitCode + '.') -ForegroundColor Yellow
        } else {
            Write-Bad ("Le backend n est toujours pas pret apres $StartupWaitSeconds secondes.")
            Write-Host 'Le processus Python lance par Nelyio va etre arrete proprement pour eviter un processus orphelin.' -ForegroundColor Yellow
            try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
        Write-Host ''
        if (Test-Path $StdoutLog) {
            Write-Host '--- SORTIE PYTHON ---' -ForegroundColor Yellow
            Get-Content $StdoutLog -Tail 80
        }
        if (Test-Path $StderrLog) {
            Write-Host ''
            Write-Host '--- ERREUR PYTHON ---' -ForegroundColor Yellow
            Get-Content $StderrLog -Tail 80
        }
        if (Test-Path (Join-Path $LogDir 'startup_error.log')) {
            Write-Host ''
            Write-Host '--- STARTUP_ERROR.LOG ---' -ForegroundColor Yellow
            Get-Content (Join-Path $LogDir 'startup_error.log') -Tail 80
        }
        Write-Host ''
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host ("Logs : " + $LogDir) -ForegroundColor Yellow
        Wait-User 'Appuyez sur Entree pour fermer'
        exit 14
    }
    Write-Ok 'Backend demarre et /healthz = HTTP 200.'
}

if (-not (Test-Path -LiteralPath $ServiceStart -PathType Leaf)) {
    Write-Bad 'START_NELYIO_SERVICES.ps1 est introuvable.'
    Wait-User 'Appuyez sur Entree pour fermer'
    exit 15
}
Write-Step 'Demarrage des services Live et Analytics separes ...'
# IMPORTANT: ne pas utiliser Start-Process -Wait ici. Sous Windows PowerShell,
# -Wait peut attendre tout l'arbre des processus enfants. Comme les workers
# Python sont volontairement persistants, le lanceur restait alors bloque
# indefiniment sur "Demarrage des services...".
try {
    $servicesResult = Invoke-NelyioScript -ScriptPath $ServiceStart -ScriptArguments @('-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'services_start') -TimeoutSeconds 60
    if ($servicesResult.ExitCode -ne 0) {
        throw "Services : code $($servicesResult.ExitCode). Voir logs\services_start_stderr.log"
    }
} catch {
    Write-Bad ('Un service Nelyio n a pas demarre : ' + $_.Exception.Message)
    Write-Host 'Consultez logs\live_service_stderr.log et logs\analytics_service_stderr.log.' -ForegroundColor Yellow
    Wait-User 'Appuyez sur Entree pour fermer'
    exit 16
}
# A Python process that survived 700 ms is not enough for production. Wait for
# the independent heartbeat database to confirm web/live/analytics.
$servicesHealthy=$false
for($i=0;$i -lt 30;$i++){
    try{
        $healthResponse=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9051/healthz' -TimeoutSec 2
        $health=$healthResponse.Content | ConvertFrom-Json
        if($health.services_ok -eq $true){$servicesHealthy=$true;break}
    }catch{}
    Start-Sleep -Seconds 1
}
if(-not $servicesHealthy){
    # A PID-less worker from a previous release can legitimately be adopted by
    # START_NELYIO_SERVICES, but its heartbeat build will not match VERSION.json.
    # Do one bounded self-heal cycle instead of leaving the operator to find and
    # kill stale processes manually.
    Write-Step 'Heartbeats incomplets ou ancienne version detectee; redemarrage borne des workers ...'
    if(Test-Path -LiteralPath $ServiceStop -PathType Leaf){
        try{
            $stopServices=Invoke-NelyioScript -ScriptPath $ServiceStop -ScriptArguments @('-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'services_recovery_stop') -TimeoutSeconds 45
            if($stopServices.ExitCode -ne 0){throw "Arret workers code $($stopServices.ExitCode)"}
            $startServices=Invoke-NelyioScript -ScriptPath $ServiceStart -ScriptArguments @('-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'services_recovery_start') -TimeoutSeconds 60
            if($startServices.ExitCode -ne 0){throw "Redemarrage workers code $($startServices.ExitCode)"}
            for($i=0;$i -lt 20;$i++){
                try{
                    $healthResponse=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9051/healthz' -TimeoutSec 2
                    $health=$healthResponse.Content | ConvertFrom-Json
                    if($health.services_ok -eq $true){$servicesHealthy=$true;break}
                }catch{}
                Start-Sleep -Seconds 1
            }
        }catch{
            Write-Host ('Reprise workers : '+$_.Exception.Message) -ForegroundColor Yellow
        }
    }
    if(-not $servicesHealthy){
        Write-Bad 'Les processus sont lances mais les heartbeats Web/Live/Analytics ne sont pas tous sains.'
        Write-Host 'Voir logs\import_service_stderr.log, logs\live_service_stderr.log et logs\analytics_service_stderr.log.' -ForegroundColor Yellow
        Wait-User 'Appuyez sur Entree pour fermer'
        exit 19
    }
}
Write-Ok 'Web, Live Service et Analytics Service actifs et valides par heartbeat. Import SIMPLIFY2 = application locale separee.'

try {
    $main = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:9051/' -TimeoutSec 3
    Write-Ok ("Interface locale = HTTP " + $main.StatusCode)
} catch {
    Write-Bad 'Le health check fonctionne mais la page principale locale ne repond pas.'
}

Write-Host ''
Write-Host 'TEST LOCAL CORRECT :' -ForegroundColor White
Write-Host '  http://127.0.0.1:9051/' -ForegroundColor Green
Write-Host 'ATTENTION : ne pas utiliser https://127.0.0.1:9051' -ForegroundColor Yellow
Write-Host ''

# Diagnose the HTTPS front-end without making backend startup depend on Caddy.
$dnsOk = $false
try {
    $dns = [System.Net.Dns]::GetHostAddresses('stock-manager.nelyio.local')
    if ($dns.Count -gt 0) {
        $dnsOk = $true
        Write-Ok ("DNS stock-manager.nelyio.local -> " + (($dns | ForEach-Object {$_.IPAddressToString}) -join ', '))
    }
} catch {
    Write-Bad 'Le nom stock-manager.nelyio.local ne se resout pas sur cette machine.'
}

if (Test-TcpPort '127.0.0.1' 9050) {
    Write-Ok 'Un service ecoute localement sur le port 9050.'
} else {
    Write-Bad 'Aucun service n ecoute localement sur le port 9050 : Caddy est probablement arrete/non lance.'
}

if (-not $NoBrowser) {
    Start-Process 'http://127.0.0.1:9051/'
}

Write-Host ''
Write-Host 'Le backend reste lance en arriere-plan.' -ForegroundColor White
Write-Host ("Logs backend : " + $LogDir) -ForegroundColor DarkGray
Write-Host 'Pour HTTPS 9050, lancez NELYIO_CADDY.ps1 -Action Status si necessaire.' -ForegroundColor White
Wait-User 'Appuyez sur Entree pour fermer cette fenetre'
