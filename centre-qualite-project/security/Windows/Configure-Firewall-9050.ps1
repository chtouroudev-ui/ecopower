# Run once in an elevated PowerShell if LAN clients must reach Nelyio HTTPS.
$ErrorActionPreference='Stop'
$Name='Nelyio HTTPS 9050'
$id=[Security.Principal.WindowsIdentity]::GetCurrent()
$p=New-Object Security.Principal.WindowsPrincipal($id)
if(-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
    throw 'Ce script doit etre lance en PowerShell Administrateur.'
}
$old=Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue
if($old){
    Set-NetFirewallRule -DisplayName $Name -Enabled True -Direction Inbound -Action Allow -Profile Domain,Private | Out-Null
    Get-NetFirewallPortFilter -AssociatedNetFirewallRule $old | Set-NetFirewallPortFilter -Protocol TCP -LocalPort 9050 | Out-Null
    Write-Host '[OK] Regle pare-feu Nelyio 9050 mise a jour.' -ForegroundColor Green
}else{
    New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort 9050 -Profile Domain,Private | Out-Null
    Write-Host '[OK] Regle pare-feu Nelyio 9050 creee.' -ForegroundColor Green
}
Write-Host '[SECURITE] Le backend 9051 reste lie a 127.0.0.1 et ne doit pas etre ouvert au LAN.' -ForegroundColor Cyan
