# NELYIO V60.1 — Validation Analytics

Build : **60.1-PROD-ARCH-FIX**

## Tests effectués
- Compilation `analytics_service.py` / `analytics_rpc.py` : OK.
- Suite `audit_regression_test.py` : return code 0.
- Contrat HTTP interne : `details_view`, `calls_view`, `quality_overview` => HTTP 200 avec moteur simulé.
- Concurrence Analytics : défaut 5.
- Erreurs RPC : 400 / 503 / 500 distinguées correctement.

## Limite
Le PostgreSQL réel et le Caddy Windows de production ne sont pas exécutés dans cet environnement. Le test final reste à faire sur le serveur Nelyio réel.
