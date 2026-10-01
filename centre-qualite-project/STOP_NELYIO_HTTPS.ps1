$ErrorActionPreference='Continue'
$Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$PSExe=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$CaddyHelper=Join-Path $Root 'NELYIO_CADDY.ps1'
$BackendStop=Join-Path $Root 'STOP_NELYIO_BACKEND.ps1'
$ServicesStop=Join-Path $Root 'STOP_NELYIO_SERVICES.ps1'
function Quote-ProcessArg([string]$Value){return '"'+$Value.Replace('"','\"')+'"'}
function Run([string]$Path){if(Test-Path $Path){$p=Start-Process -FilePath $PSExe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Quote-ProcessArg $Path)) -WorkingDirectory $Root -Wait -PassThru -WindowStyle Hidden;return $p.ExitCode};return 1}
# Stop producers first so Live can publish/flush while the backend and databases
# are still available. Stop the HTTPS front only after the application is down.
$s=Run $ServicesStop
$b=Run $BackendStop
$c=if(Test-Path $CaddyHelper){$p=Start-Process -FilePath $PSExe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Quote-ProcessArg $CaddyHelper),'-Action','Stop','-NoPause') -WorkingDirectory $Root -Wait -PassThru -WindowStyle Hidden;$p.ExitCode}else{1}
if($c -eq 0 -and $b -eq 0 -and $s -eq 0){exit 0}else{exit 1}
