# NELYIO V60.1 — Correctif Analytics

## Cause confirmée
Le service Analytics pouvait être sain sur `127.0.0.1:9052` tout en affichant « Analytics Service indisponible » dans le Web. V60 masquait plusieurs causes sous le même message et rejetait aussi `details_view` / `calls_view` sur l’endpoint `/query`.

## Corrections
- `details_view` et `calls_view` autorisés côté Analytics.
- Timeout RPC par défaut : 90 s (`NELYIO_ANALYTICS_TIMEOUT`).
- Concurrence Analytics par défaut : 5 (`NELYIO_ANALYTICS_MAX_CONCURRENCY`).
- Retry court en cas de saturation 503.
- Messages distincts : timeout, occupé, requête refusée, erreur interne, service réellement indisponible.
- Aucun fallback lourd dans le processus Web.

## Vérification rapide
```powershell
Invoke-RestMethod http://127.0.0.1:9052/healthz
Get-NetTCPConnection -LocalPort 9052 -State Listen
Get-Content .\logs\analytics_service_stderr.log -Tail 100
Get-Content .\logs\nelyio_errors.log -Tail 100
```

Après remplacement par V60.1, redémarrer Nelyio pour charger le nouveau worker Analytics.
