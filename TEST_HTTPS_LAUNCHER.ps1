#requires -Version 5.1
param([switch]$RunProcessTest)
# Local verification only. Does NOT start Nelyio or Caddy, or change certificates.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$count = 0
function Assert-True([bool]$Condition,[string]$Message) {
    if (-not $Condition) { throw $Message }
    $script:count += 1
    Write-Host ('[OK] '+$Message)
}
$files = @('NELYIO_LAUNCHER_COMMON.ps1','START_NELYIO_HTTPS.ps1','NELYIO_CADDY.ps1','TEST_HTTPS_LAUNCHER.ps1')
Assert-True (Test-Path (Join-Path $Root 'Caddyfile')) 'Caddyfile racine present'
foreach ($relative in $files) {
    $path = Join-Path $Root $relative
    $tokens = $null; $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
    Assert-True ($errors.Count -eq 0) ('Syntaxe PowerShell : '+$relative)
}
. (Join-Path $Root 'NELYIO_LAUNCHER_COMMON.ps1')
Assert-True ((ConvertTo-NelyioProcessArgument '') -ceq '""') 'Argument vide'
Assert-True ((ConvertTo-NelyioProcessArgument 'C:\Nelyio\start.ps1') -ceq 'C:\Nelyio\start.ps1') 'Chemin simple'
Assert-True ((ConvertTo-NelyioProcessArgument 'C:\Nelyio Test (1)\start.ps1') -ceq '"C:\Nelyio Test (1)\start.ps1"') 'Espaces et parentheses'
Assert-True ((ConvertTo-NelyioProcessArgument 'C:\Nelyio Test\') -ceq '"C:\Nelyio Test\\"') 'Antislash final dans argument cite'
Initialize-NelyioProbe
Assert-True ($null -ne ('NelyioHttpsHotfix.HttpProbe' -as [type])) 'Compilation du controle HTTPS local'
$reply = [NelyioHttpsHotfix.HttpProbe]::Read('https://example.invalid/healthz',1000,$true)
Assert-True ($reply.Error -like '*loopback*') 'Le controle sans confiance refuse une adresse externe, avant toute connexion'
if ($RunProcessTest) {
    $temp = Join-Path $env:TEMP ('Nelyio HTTPS Test (1) '+[guid]::NewGuid().ToString('N'))
    $childId = $null
    try {
        New-Item -ItemType Directory -Path $temp | Out-Null
        $pidPath = Join-Path $temp 'test-child.pid'
        $worker = Join-Path $temp 'parent test.ps1'
        @'
param([string]$PidPath)
$child = Start-Process -FilePath (Join-Path $PSHOME 'powershell.exe') -ArgumentList '-NoLogo -NoProfile -NonInteractive -Command "Start-Sleep -Seconds 25"' -PassThru -WindowStyle Hidden
Set-Content -LiteralPath $PidPath -Value $child.Id
exit 7
'@ | Set-Content -LiteralPath $worker -Encoding UTF8
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $result = Invoke-NelyioScript -ScriptPath $worker -ScriptArguments @('-PidPath',$pidPath) -WorkingDirectory $temp -LogPrefix (Join-Path $temp 'test') -TimeoutSeconds 10
        $timer.Stop()
        Assert-True ($result.ExitCode -eq 7 -and -not $result.TimedOut) 'Code du lanceur recupere sans attendre son enfant de 25 secondes'
        $childId = [int]([IO.File]::ReadAllText($pidPath).Trim())
        Assert-True ($null -ne (Get-Process -Id $childId -ErrorAction SilentlyContinue)) 'Le processus enfant cree par le test reste actif'
        Write-Host ('Temps du lanceur de test : '+$timer.Elapsed.TotalSeconds+' s')
    } finally {
        # This PID belongs only to the synthetic process created above.
        if ($childId) { Stop-Process -Id $childId -ErrorAction SilentlyContinue }
        Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
Write-Host ("Validation terminee : $count controle(s) OK.") -ForegroundColor Green
