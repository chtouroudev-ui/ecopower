# NELYIO V60.2 — Rapport de validation

Build : **60.2-PROD-PERF-LIVE-SNAPSHOT**  
Date : **24/09/2026**

## Sources de diagnostic

- HAR réel `stock-manager.nelyio.local(1).har`.
- V60.1 comme base de code.
- Le HAR analysé provenait encore de `NELYIO_V60_0_PROD_ARCH`.

Mesures importantes du HAR :

- `/api/supervision/support` : jusqu'à ~31,5 s sur 01→23 septembre, environ 3,4 Mo de réponse ;
- `/api/supervision/calls` : ~9,1 s sur la période mensuelle ;
- Support sur un seul jour : encore ~7–8 s ;
- Qualité Agents : ~2,5 s ;
- Distributions : ~1 s.

Le temps est dominé par l'attente serveur, pas par TLS/Caddy.

## Causes trouvées

1. `disconnect_statistics` pouvait charger tous les ODCalls d'un jour uniquement pour enrichir quelques coupures.
2. `support_view` rechargeait ensuite tous les appels de toute la période avant de garder uniquement EndReason/durées invalides.
3. Le payload Support interactif transportait plusieurs centaines d'événements avec contrats de gouvernance imbriqués.
4. Recherche d'appels recalculait quatre fois un scope mensuel et appliquait un `ROW_NUMBER` global redondant.
5. Le Live V60 était isolé en base, mais l'interface ne lisait pas réellement cette base dédiée.
6. L'import changeait historiquement trop tôt la référence active ; V60.2 introduit un état `staged` et une bascule atomique finale.

## Validation exécutée

- 53 tests Python : OK (51 existants + 2 V60.2).
- Test snapshot : un échec d'enrichissement conserve l'ancienne `coverage`, y compris après `init()`.
- Test Live : événement agent + file + `call_observation` visible directement dans `live_snapshot()`.
- Benchmark Support 207 000 appels / 23 jours : ~2,84 s V60.1 → ~0,19 s V60.2 dans SQLite isolé.
- Payload Support synthétique : ~2,06 Mo → ~0,56 Mo.
- Benchmark Calls 207 000 appels / 23 jours : ~3,77 s → ~0,66 s dans SQLite isolé.
- Les résultats métier du benchmark sont conservés : 667 signaux Support et 207 000 appels comptés.

## Limites

L'environnement de validation n'est pas votre Windows/PostgreSQL/Caddy réel. Les temps absolus doivent être remesurés sur le serveur. V60.2 ajoute `logs/analytics_slow.log` afin que toute requête restant >2 s soit immédiatement identifiable sans exposer les filtres ou numéros.
