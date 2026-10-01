$ErrorActionPreference='Stop'
function Good($t){Write-Host "[OK] $t" -ForegroundColor Green}
function Bad($t){Write-Host "[ERREUR] $t" -ForegroundColor Red}
$ok=$true
try{
  Start-Sleep -Seconds 4
  $h=Invoke-RestMethod -Uri 'http://127.0.0.1:9051/healthz' -TimeoutSec 5
  if($h.ok -and $h.service -eq 'nelyio-backend' -and $h.database -eq 'postgresql'){
    Good "Backend /healthz - build $($h.build) - PostgreSQL"
  }else{Bad 'Réponse /healthz invalide ou backend non PostgreSQL';$ok=$false}
  if($h.architecture -eq 'services' -and $h.services_ok -eq $true){
    Good 'Web + Live + Analytics : heartbeats OK (Import optionnel)'
  }else{
    Bad 'Un ou plusieurs services ne sont pas sains.';$ok=$false
    if($h.services){$h.services.PSObject.Properties | ForEach-Object {Write-Host ("  {0}: healthy={1}" -f $_.Name,$_.Value)}}
  }
}catch{Bad ("Contrôle /healthz indisponible : "+$_.Exception.Message);$ok=$false}
if($ok){Write-Host '';Write-Host '[OK] Nelyio a passé le contrôle post-démarrage.' -ForegroundColor Green;exit 0}
Write-Host '';Write-Host '[ERREUR] Ne pas basculer en production.' -ForegroundColor Red;exit 1
