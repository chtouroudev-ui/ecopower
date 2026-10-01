#requires -Version 5.1
param(
    [switch]$ControlPanel,
    [switch]$NoBrowser,
    [switch]$NoTrust,
    [switch]$NoAutoStart,
    [switch]$Diagnostics,
    [switch]$NoInstall
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$VersionMeta = Get-Content -LiteralPath (Join-Path $Root 'VERSION.json') -Raw | ConvertFrom-Json
$ExpectedBuild = [string]$VersionMeta.version
if ($VersionMeta.runtime_revision) { $ExpectedBuild = $ExpectedBuild + '+' + [string]$VersionMeta.runtime_revision }
$LogDir = Join-Path $Root 'logs'
$LauncherLog = Join-Path $LogDir 'https_launcher.log'
$RunDir = Join-Path $Root 'run'
$BackendStart = Join-Path $Root 'START_NELYIO.ps1'
$CaddyHelper = Join-Path $Root 'NELYIO_CADDY.ps1'
$Panel = Join-Path $Root 'NELYIO_CONTROL_PANEL.ps1'
$HttpsUrl = 'https://stock-manager.nelyio.local:9050/'
$LocalHttps = 'https://localhost:9050/'
$LocalHttp = 'http://127.0.0.1:9051/'
$startupLock = $null
$exitCode = 1
. (Join-Path $Root 'NELYIO_LAUNCHER_COMMON.ps1')

function Log([string]$Text) {
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $Text
    Add-Content -LiteralPath $LauncherLog -Value $line -Encoding UTF8
    if ($Diagnostics) { Write-Host $line }
}
function Open-HttpFallback([string]$Reason) {
    Log ('FALLBACK HTTP local : ' + $Reason)
    if (-not $NoBrowser -and (Test-NelyioHealth -Url ($LocalHttp+'healthz') -ExpectedBuild $ExpectedBuild)) {
        try { Start-Process $LocalHttp | Out-Null } catch { Log ('Navigateur non ouvert : '+$_.Exception.Message) }
    }
}
function Write-StepResult([string]$Name, $Result) {
    Log ("$Name : code="+$Result.ExitCode+' timeout='+$Result.TimedOut)
    Log ('  sortie : '+$Result.StdoutPath)
    Log ('  erreurs : '+$Result.StderrPath)
}
function Start-HttpsStack {
    if ($ControlPanel) {
        if (-not (Test-Path -LiteralPath $Panel)) { throw "Panneau introuvable : $Panel" }
        $panelArguments = @('-NoProfile','-STA','-ExecutionPolicy','Bypass','-File',$Panel)
        if ($NoAutoStart) { $panelArguments += '-NoAutoStart' }
        $panelLine = (($panelArguments | ForEach-Object { ConvertTo-NelyioProcessArgument $_ }) -join ' ')
        Start-Process -FilePath (Get-NelyioPowerShell) -ArgumentList $panelLine -WorkingDirectory $Root | Out-Null
        return 0
    }
    Log '=== START HTTPS - V59 production hardened ==='
    if (-not (Test-NelyioHealth -Url ($LocalHttp+'healthz') -ExpectedBuild $ExpectedBuild)) {
        Log 'Demarrage du backend 9051.'
        if ($Diagnostics) {
            # Run the backend launcher in a CHILD PowerShell attached to this
            # console.  START_NELYIO.ps1 uses exit codes; running it directly
            # in this host could terminate the HTTPS parent script and make the
            # displayed return code misleading.
            Write-Host '--- Progression backend 9051 ---' -ForegroundColor Cyan
            $backendPs = Get-NelyioPowerShell
            & $backendPs -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $BackendStart -NoBrowser -NoPause
            $backendCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
            Log ('Backend diagnostic : code='+$backendCode)
            if ($backendCode -ne 0 -or -not (Test-NelyioHealth -Url ($LocalHttp+'healthz') -ExpectedBuild $ExpectedBuild)) {
                Log 'ERREUR : backend non valide. Voir les journaux backend et startup_error.log.'
                return 31
            }
        } else {
            $step = Invoke-NelyioScript -ScriptPath $BackendStart -ScriptArguments @('-NoBrowser','-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'https_backend_start') -TimeoutSeconds 300
            Write-StepResult 'Backend' $step
            if ($step.ExitCode -ne 0 -or -not (Test-NelyioHealth -Url ($LocalHttp+'healthz') -ExpectedBuild $ExpectedBuild)) {
                Log 'ERREUR : backend non valide. Voir les journaux backend et startup_error.log.'
                return 31
            }
        }
    }
    Log 'Backend Nelyio 9051 OK.'
    if (-not (Test-NelyioHealth -Url ($LocalHttps+'healthz') -ExpectedBuild $ExpectedBuild -DiagnosticLocalTls)) {
        if (-not (Test-Path -LiteralPath $CaddyHelper -PathType Leaf)) {
            Log 'ERREUR : gestionnaire Caddy Nelyio absent.'
            Open-HttpFallback 'Gestionnaire Caddy absent'
            return 33
        }
        Log 'Demarrage du frontend Caddy externe sur 9050.'
        $step = Invoke-NelyioScript -ScriptPath $CaddyHelper -ScriptArguments @('-Action','Start','-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'https_caddy_start') -TimeoutSeconds 120
        Write-StepResult 'Caddy' $step
        if ($step.ExitCode -eq 41) {
            Log 'ERREUR : caddy.exe introuvable. Placez-le a la racine du projet, dans tools\, dans PATH, ou definissez NELYIO_CADDY_EXE.'
            Open-HttpFallback 'Caddy externe absent'
            return 33
        }
        if ($step.ExitCode -ne 0 -or -not (Test-NelyioHealth -Url ($LocalHttps+'healthz') -ExpectedBuild $ExpectedBuild -DiagnosticLocalTls)) {
            Open-HttpFallback 'Frontend HTTPS indisponible'
            return 32
        }
    }
    Log 'HTTPS local Nelyio OK (controle de diagnostic, confiance verifiee ensuite).'
    if (-not $NoTrust -and -not (Test-NelyioHealth -Url ($LocalHttps+'healthz') -ExpectedBuild $ExpectedBuild) -and (Test-Path -LiteralPath $CaddyHelper)) {
        try {
            $step = Invoke-NelyioScript -ScriptPath $CaddyHelper -ScriptArguments @('-Action','Trust','-NoPause') -WorkingDirectory $Root -LogPrefix (Join-Path $LogDir 'https_certificate_trust') -TimeoutSeconds 60
            Write-StepResult 'Confiance certificat utilisateur' $step
        } catch { Log ('Confiance certificat non installee : '+$_.Exception.Message) }
    }
    $named = Test-NelyioHealth -Url ($HttpsUrl+'healthz') -ExpectedBuild $ExpectedBuild
    $localTrusted = Test-NelyioHealth -Url ($LocalHttps+'healthz') -ExpectedBuild $ExpectedBuild
    if ($named) { Log 'URL nommee et certificat valides.' }
    else { Log 'AVERTISSEMENT : nom DNS/certificat non valide pour stock-manager.nelyio.local. HTTPS local repond.' }
    if (-not $localTrusted) { Log 'AVERTISSEMENT : le certificat local reste non approuve pour ce compte Windows. Ne pas desactiver la verification dans le navigateur.' }
    if (-not $NoBrowser) {
        $target = if ($named) { $HttpsUrl } else { $LocalHttps }
        try { Start-Process $target | Out-Null } catch { Log ('Ouverture navigateur impossible : '+$_.Exception.Message) }
    }
    Log 'Demarrage termine. Python et Caddy externe restent en arriere-plan.'
    return 0
}

try {
    New-Item -ItemType Directory -Force -Path $LogDir,$RunDir | Out-Null
    Set-Location -LiteralPath $Root
    # An open file lock prevents two double-clicks from spawning duplicate stacks.
    # It is released automatically by Windows after a crash; no stale PID lock.
    try {
        $startupLock = [IO.File]::Open((Join-Path $RunDir 'https_start.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    } catch [IO.IOException] {
        if (Test-NelyioHealth -Url ($LocalHttp+'healthz') -ExpectedBuild $ExpectedBuild -TimeoutMilliseconds 1500) {
            Log 'Nelyio est deja actif; aucun doublon demarre.'
            exit 0
        }
        Log 'Un lancement HTTPS est deja en cours mais le backend 9051 n est pas encore pret.'
        if ($Diagnostics) {
            Log 'DIAGNOSTIC : lancement encore en cours. Retour 38 tant que /healthz ne repond pas.'
            $pgLog = Join-Path $LogDir 'postgres_runtime_preflight_console.log'
            if (Test-Path -LiteralPath $pgLog) {
                Write-Host '--- POSTGRES PREFLIGHT (dernieres lignes) ---' -ForegroundColor Yellow
                Get-Content -LiteralPath $pgLog -Tail 60
            }
            exit 38
        }
        exit 0
    }
    # Capture all pipeline output defensively and use only the explicit final
    # numeric return code from Start-HttpsStack.  This avoids Windows
    # PowerShell coercing an accidental output array to exit code 0.
    $stackResult = @(Start-HttpsStack)
    if ($stackResult.Count -gt 0) {
        $exitCode = [int]$stackResult[$stackResult.Count - 1]
    } else {
        $exitCode = 39
    }
} catch {
    try { Log ('ERREUR LANCEUR : '+$_.Exception.Message); Log ($_.ScriptStackTrace) } catch {}
    $exitCode = 39
    if ($Diagnostics) { Write-Host $_.Exception.Message -ForegroundColor Red }
} finally {
    if ($startupLock) { $startupLock.Dispose() }
}
exit ([int]$exitCode)
