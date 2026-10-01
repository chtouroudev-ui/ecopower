param([switch]$NoAutoStart)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PSExe = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$BackendStart = Join-Path $Root 'START_NELYIO.ps1'
$BackendStop = Join-Path $Root 'STOP_NELYIO_BACKEND.ps1'
$CaddyHelper = Join-Path $Root 'NELYIO_CADDY.ps1'
$LogDir = Join-Path $Root 'logs'
$LocalUrl = 'http://127.0.0.1:9051/'
$HttpsUrl = 'https://stock-manager.nelyio.local:9050/'
$LocalHttpsUrl = 'https://localhost:9050/'
$DiagScript = Join-Path $Root 'DIAGNOSTIC_9050_9051_V50.ps1'

function Test-TcpPort([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $a = $client.BeginConnect('127.0.0.1',$Port,$null,$null)
        if(-not $a.AsyncWaitHandle.WaitOne(350,$false)){ return $false }
        $client.EndConnect($a); return $true
    } catch { return $false } finally { $client.Close() }
}
function Test-BackendHealth {
    try { $r=Invoke-WebRequest -UseBasicParsing -Uri ($LocalUrl+'healthz') -TimeoutSec 2; return $r.StatusCode -eq 200 } catch { return $false }
}
function Test-DnsName {
    try { return ([System.Net.Dns]::GetHostAddresses('stock-manager.nelyio.local').Count -gt 0) } catch { return $false }
}
function Test-FrontendHealth {
    if(-not (Test-TcpPort 9050)){ return $false }
    $old=[System.Net.ServicePointManager]::ServerCertificateValidationCallback
    try {
        [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
        $r=Invoke-WebRequest -UseBasicParsing -Uri ($LocalHttpsUrl+'healthz') -TimeoutSec 3
        return $r.StatusCode -eq 200
    } catch { return $false } finally { [System.Net.ServicePointManager]::ServerCertificateValidationCallback=$old }
}
function Quote-ProcessArg([string]$Value) {
    if($null -eq $Value){ return '""' }
    return '"' + $Value.Replace('"','\"') + '"'
}
function Run-Script([string]$Path,[string[]]$Extra=@()) {
    if(-not (Test-Path $Path)){ throw "Script introuvable: $Path" }
    $argList=@('-NoProfile','-ExecutionPolicy','Bypass','-File',(Quote-ProcessArg $Path))+$Extra
    $p=Start-Process -FilePath $PSExe -ArgumentList $argList -WorkingDirectory $Root -Wait -PassThru -WindowStyle Hidden
    return $p.ExitCode
}
$form = New-Object System.Windows.Forms.Form
$form.Text = 'NELYIO - Controle des services'
$form.Size = New-Object System.Drawing.Size(760,610)
$form.MinimumSize = New-Object System.Drawing.Size(720,570)
$form.StartPosition = 'CenterScreen'
$form.Font = New-Object System.Drawing.Font('Segoe UI',10)
$form.BackColor = [System.Drawing.Color]::FromArgb(246,248,252)

$title=New-Object System.Windows.Forms.Label
$title.Text='NELYIO Control Center'
$title.Font=New-Object System.Drawing.Font('Segoe UI Semibold',18)
$title.AutoSize=$true;$title.Location=New-Object System.Drawing.Point(24,18)
$form.Controls.Add($title)
$sub=New-Object System.Windows.Forms.Label
$sub.Text='Backend HTTP 9051 + Frontend HTTPS Caddy 9050'
$sub.ForeColor=[System.Drawing.Color]::DimGray;$sub.AutoSize=$true;$sub.Location=New-Object System.Drawing.Point(27,53)
$form.Controls.Add($sub)

function New-ServiceCard([string]$name,[string]$endpoint,[int]$y){
    $panel=New-Object System.Windows.Forms.Panel;$panel.Location=New-Object System.Drawing.Point(24,$y);$panel.Size=New-Object System.Drawing.Size(695,128);$panel.BackColor=[System.Drawing.Color]::White;$panel.BorderStyle='FixedSingle'
    $n=New-Object System.Windows.Forms.Label;$n.Text=$name;$n.Font=New-Object System.Drawing.Font('Segoe UI Semibold',13);$n.AutoSize=$true;$n.Location=New-Object System.Drawing.Point(16,13);$panel.Controls.Add($n)
    $ep=New-Object System.Windows.Forms.Label;$ep.Text=$endpoint;$ep.ForeColor=[System.Drawing.Color]::DimGray;$ep.AutoSize=$true;$ep.Location=New-Object System.Drawing.Point(18,43);$panel.Controls.Add($ep)
    $badge=New-Object System.Windows.Forms.Label;$badge.Text='...';$badge.TextAlign='MiddleCenter';$badge.Font=New-Object System.Drawing.Font('Segoe UI Semibold',10);$badge.Size=New-Object System.Drawing.Size(92,30);$badge.Location=New-Object System.Drawing.Point(580,15);$panel.Controls.Add($badge)
    $detail=New-Object System.Windows.Forms.Label;$detail.Text='Verification...';$detail.ForeColor=[System.Drawing.Color]::DimGray;$detail.AutoSize=$true;$detail.Location=New-Object System.Drawing.Point(18,72);$panel.Controls.Add($detail)
    $start=New-Object System.Windows.Forms.Button;$start.Text='Start';$start.Size=New-Object System.Drawing.Size(86,30);$start.Location=New-Object System.Drawing.Point(395,78);$panel.Controls.Add($start)
    $stop=New-Object System.Windows.Forms.Button;$stop.Text='Stop';$stop.Size=New-Object System.Drawing.Size(86,30);$stop.Location=New-Object System.Drawing.Point(488,78);$panel.Controls.Add($stop)
    $restart=New-Object System.Windows.Forms.Button;$restart.Text='Restart';$restart.Size=New-Object System.Drawing.Size(86,30);$restart.Location=New-Object System.Drawing.Point(581,78);$panel.Controls.Add($restart)
    $form.Controls.Add($panel)
    return @{Panel=$panel;Badge=$badge;Detail=$detail;Start=$start;Stop=$stop;Restart=$restart}
}
$backend=New-ServiceCard 'Backend Nelyio' 'http://127.0.0.1:9051' 88
$frontend=New-ServiceCard 'Frontend HTTPS / Caddy' 'https://stock-manager.nelyio.local:9050' 226

$status=New-Object System.Windows.Forms.Label;$status.Text='Pret.';$status.AutoEllipsis=$true;$status.Size=New-Object System.Drawing.Size(695,24);$status.Location=New-Object System.Drawing.Point(27,366);$status.ForeColor=[System.Drawing.Color]::DimGray;$form.Controls.Add($status)

$startAll=New-Object System.Windows.Forms.Button;$startAll.Text='START ALL';$startAll.Size=New-Object System.Drawing.Size(120,36);$startAll.Location=New-Object System.Drawing.Point(24,402);$form.Controls.Add($startAll)
$stopAll=New-Object System.Windows.Forms.Button;$stopAll.Text='STOP ALL';$stopAll.Size=New-Object System.Drawing.Size(120,36);$stopAll.Location=New-Object System.Drawing.Point(152,402);$form.Controls.Add($stopAll)
$restartAll=New-Object System.Windows.Forms.Button;$restartAll.Text='RESTART ALL';$restartAll.Size=New-Object System.Drawing.Size(128,36);$restartAll.Location=New-Object System.Drawing.Point(280,402);$form.Controls.Add($restartAll)
$openHttps=New-Object System.Windows.Forms.Button;$openHttps.Text='Ouvrir HTTPS';$openHttps.Size=New-Object System.Drawing.Size(122,36);$openHttps.Location=New-Object System.Drawing.Point(416,402);$form.Controls.Add($openHttps)
$openLocal=New-Object System.Windows.Forms.Button;$openLocal.Text='Ouvrir Local';$openLocal.Size=New-Object System.Drawing.Size(110,36);$openLocal.Location=New-Object System.Drawing.Point(546,402);$form.Controls.Add($openLocal)
$logs=New-Object System.Windows.Forms.Button;$logs.Text='Logs';$logs.Size=New-Object System.Drawing.Size(58,36);$logs.Location=New-Object System.Drawing.Point(663,402);$form.Controls.Add($logs)

$diag=New-Object System.Windows.Forms.Button;$diag.Text='Diagnostic HTTPS';$diag.Size=New-Object System.Drawing.Size(145,34);$diag.Location=New-Object System.Drawing.Point(24,452);$form.Controls.Add($diag)
$trust=New-Object System.Windows.Forms.Button;$trust.Text='Installer certificat';$trust.Size=New-Object System.Drawing.Size(145,34);$trust.Location=New-Object System.Drawing.Point(177,452);$form.Controls.Add($trust)
$dns=New-Object System.Windows.Forms.Label;$dns.Text='DNS: verification...';$dns.AutoSize=$true;$dns.Location=New-Object System.Drawing.Point(27,500);$dns.ForeColor=[System.Drawing.Color]::DimGray;$form.Controls.Add($dns)
$hint=New-Object System.Windows.Forms.Label;$hint.Text='Fermer cette fenetre ne coupe pas les services. START_NELYIO_HTTPS.bat demarre sans console.';$hint.AutoSize=$true;$hint.Location=New-Object System.Drawing.Point(27,526);$hint.ForeColor=[System.Drawing.Color]::Gray;$form.Controls.Add($hint)

$script:busy=$false
function Set-Activity([string]$text){ $status.Text=$text;[System.Windows.Forms.Application]::DoEvents() }
function Paint-State($card,[bool]$up,[string]$detail){
    if($up){
        $card.Badge.Text='UP'
        $card.Badge.BackColor=[System.Drawing.Color]::FromArgb(225,246,234)
        $card.Badge.ForeColor=[System.Drawing.Color]::FromArgb(22,101,52)
    } else {
        $card.Badge.Text='DOWN'
        $card.Badge.BackColor=[System.Drawing.Color]::FromArgb(255,231,231)
        $card.Badge.ForeColor=[System.Drawing.Color]::FromArgb(169,29,29)
    }
    $card.Detail.Text=$detail
}
function Refresh-State {
    if($script:busy){return}
    $b=Test-BackendHealth;$fp=Test-TcpPort 9050;$fh=$false;if($fp){$fh=Test-FrontendHealth}
    if($b){ $backendDetail='Health /healthz = HTTP 200' } elseif(Test-TcpPort 9051){ $backendDetail='Port 9051 occupe mais health check KO' } else { $backendDetail='Aucun service sur 9051' }
    if($fh){ $frontendDetail='Caddy local HTTPS /healthz = HTTP 200' } elseif($fp){ $frontendDetail='Port 9050 en ecoute, mais Caddy/reverse proxy KO' } else { $frontendDetail='Aucun service sur 9050' }
    Paint-State $backend $b $backendDetail
    Paint-State $frontend $fh $frontendDetail
    $backend.Start.Enabled=-not $b;$backend.Stop.Enabled=(Test-TcpPort 9051);$backend.Restart.Enabled=$true
    $frontend.Start.Enabled=-not $fp;$frontend.Stop.Enabled=$fp;$frontend.Restart.Enabled=$true
    if(Test-DnsName){
        $dns.Text='DNS stock-manager.nelyio.local : OK'
        try{$r=Invoke-WebRequest -UseBasicParsing -Uri ($HttpsUrl+'healthz') -TimeoutSec 3;if($r.StatusCode -eq 200){$dns.Text+=' | Certificat : approuve'}}catch{$dns.Text+=' | Certificat : a verifier'}
    } else { $dns.Text='DNS stock-manager.nelyio.local : NON RESOLU | Caddy local peut quand meme etre UP' }
}
function With-Busy([scriptblock]$action,[string]$message){
    if($script:busy){return};$script:busy=$true;$timer.Stop();Set-Activity $message
    try{& $action}catch{[System.Windows.Forms.MessageBox]::Show($_.Exception.Message,'NELYIO',[System.Windows.Forms.MessageBoxButtons]::OK,[System.Windows.Forms.MessageBoxIcon]::Error)|Out-Null}
    finally{$script:busy=$false;Refresh-State;$timer.Start();Set-Activity 'Pret.'}
}
function Start-Backend { if(Test-BackendHealth){return};$c=Run-Script $BackendStart @('-NoBrowser','-NoPause');if($c -ne 0){throw "Backend: echec code $c. Consultez logs\\backend_9051_stderr.log"} }
function Stop-Backend { Run-Script $BackendStop @()|Out-Null;Start-Sleep -Milliseconds 500 }
function Start-Frontend { if(Test-FrontendHealth){return};$c=Run-Script $CaddyHelper @('-Action','Start','-NoPause');if($c -eq 41){throw 'Caddy est introuvable. Placez caddy.exe a la racine, dans tools\, dans PATH ou definissez NELYIO_CADDY_EXE.'};if($c -ne 0){throw "Caddy: echec code $c. Consultez logs\caddy_stderr.log"} }
function Stop-Frontend { Run-Script $CaddyHelper @('-Action','Stop','-NoPause')|Out-Null;Start-Sleep -Milliseconds 500 }

$backend.Start.Add_Click({With-Busy {Start-Backend} 'Demarrage backend...'})
$backend.Stop.Add_Click({With-Busy {Stop-Backend} 'Arret backend...'})
$backend.Restart.Add_Click({With-Busy {Stop-Backend;Start-Backend} 'Redemarrage backend...'})
$frontend.Start.Add_Click({With-Busy {Start-Frontend} 'Demarrage Caddy...'})
$frontend.Stop.Add_Click({With-Busy {Stop-Frontend} 'Arret Caddy...'})
$frontend.Restart.Add_Click({With-Busy {Stop-Frontend;Start-Frontend} 'Redemarrage Caddy...'})
$startAll.Add_Click({With-Busy {Start-Backend;Start-Frontend} 'Demarrage complet NELYIO...'})
$stopAll.Add_Click({With-Busy {Stop-Frontend;Stop-Backend} 'Arret complet NELYIO...'})
$restartAll.Add_Click({With-Busy {Stop-Frontend;Stop-Backend;Start-Backend;Start-Frontend} 'Redemarrage complet NELYIO...'})
$openHttps.Add_Click({Start-Process $HttpsUrl})
$openLocal.Add_Click({Start-Process $LocalUrl})
$logs.Add_Click({if(-not(Test-Path $LogDir)){New-Item -ItemType Directory -Force -Path $LogDir|Out-Null};Start-Process explorer.exe $LogDir})
$diag.Add_Click({if(Test-Path $DiagScript){Start-Process -FilePath $PSExe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Quote-ProcessArg $DiagScript)) -WorkingDirectory $Root}})
$trust.Add_Click({With-Busy {$c=Run-Script $CaddyHelper @('-Action','Trust','-NoPause');if($c -ne 0){throw "Installation certificat: code $c"}} 'Installation du certificat Caddy...'})

$timer=New-Object System.Windows.Forms.Timer;$timer.Interval=3000;$timer.Add_Tick({Refresh-State})
$form.Add_Shown({Refresh-State;$timer.Start();if(-not $NoAutoStart){$form.BeginInvoke([Action]{if(-not(Test-BackendHealth) -or -not(Test-FrontendHealth)){With-Busy {Start-Backend;Start-Frontend} 'Demarrage automatique NELYIO...'}})|Out-Null}})
$form.Add_FormClosed({$timer.Stop()})
[void]$form.ShowDialog()
