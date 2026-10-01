param([switch]$Remove)
$ErrorActionPreference='Stop'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName='NELYIO HTTPS Launcher'
if($Remove){
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host '[OK] Tache de demarrage Nelyio supprimee.' -ForegroundColor Green
    exit 0
}
$Script=Join-Path $Root 'START_NELYIO_HTTPS.ps1'
$PSExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$action=New-ScheduledTaskAction -Execute $PSExe -Argument ('-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+$Script+'" -NoBrowser') -WorkingDirectory $Root
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
$principal=New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Demarre Nelyio backend 9051 et Caddy HTTPS 9050 silencieusement a la connexion utilisateur.' -Force | Out-Null
Write-Host '[OK] Demarrage automatique Nelyio installe (a la connexion, fenetre cachee).' -ForegroundColor Green
Write-Host 'Pour supprimer: .\INSTALL_NELYIO_AUTOSTART.ps1 -Remove' -ForegroundColor Cyan
