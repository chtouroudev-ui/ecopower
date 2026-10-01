# NELYIO V60.4 — Rapport de validation

Build : **60.4-POSTGRES-HOTFIX**

## Données de diagnostic utilisées

Les fichiers de diagnostic PostgreSQL réels fournis le 25/09/2026 ont montré :

- `details_view`: 133321.8 ms total, 132941.1 ms SQL, 49 requêtes, requête max 92130.6 ms ;
- autre `details_view`: 13817.3 ms total, 13574.0 ms SQL, 39 requêtes, requête max 8944.3 ms ;
- `analytics`: 26531 ms, 19134 ms SQL, **997 requêtes** ;
- `support_view`: ~7.7 s ;
- `diagnostic_incidents`: jusqu'à ~19.1 s ;
- roster agents : ~607k activités triées pour ~103 agents, external merge sur disque ;
- PostgreSQL 18.6, `shared_buffers=128MB`, `work_mem=4MB`, `effective_cache_size=4GB` ;
- aucune transaction longue ni session bloquée au moment du diagnostic ;
- `pg_stat_statements` absent ; aucune activation automatique n'a été faite.

## Correctifs validés localement

- catalogue agents non filtré borné au dernier import ACTIVE ;
- Détails : une seule lecture `active_days` par période ;
- suppression du N+1 avant/après pour les fermetures/pause probables ;
- index PostgreSQL V60.4 idempotents/non destructifs ;
- outil EXPLAIN mis à jour avec roster dernier import + Détails ;
- outil diagnostic vérifie la présence des nouveaux index.

## Tests

- les 15 scripts frontend sont servis avec des cache-busters `V60_4-<hash>` pour empêcher la réutilisation d’un ancien frontend RC2G ;

- suite complète finale : **69/69 tests Python passés** ;
- tests ciblés V60.4 inclus dans ces 69 tests : **5/5 passés** ;
- classification fermeture probable : nouveau chemin batch = ancien fallback SQL ;
- Détails 3 jours / deux sources : une seule requête `active_days` ;
- migration : aucun `DROP TABLE`, `DROP DATABASE`, `TRUNCATE` ou `DELETE FROM`.

## Smoke multi-processus final

- Web : `127.0.0.1:9351` → `ok=true`, build `60.4-POSTGRES-HOTFIX` ;
- Analytics : `127.0.0.1:9352` → `ok=true`, `max_concurrency=5` ;
- Live : heartbeat `healthy=true` ;
- `/healthz` Web : `services_ok=true`, services `web/live/analytics=true`.

## Benchmark synthétique de contrôle

Dataset isolé SQLite : 60 000 appels, 50 agents, 30 jours, 5 répétitions.

V60.4 : Support ~0.0985 s, Recherche appels ~0.1123 s, Diagnostic ~0.0366 s, Équipe/Files/Priorités froid ~0.0114 s. Les résultats fonctionnels du benchmark sont corrects.

Ce benchmark ne remplace **pas** la mesure PostgreSQL de production : les corrections V60.4 ciblent précisément les plans et N+1 observés uniquement sur PostgreSQL réel.

## Après production

À fournir pour validation finale :

- `logs\explain_after.json`
- `logs\postgresql_diagnostic.json`
- `logs\performance.jsonl`
- `logs\analytics_slow.log`
- si possible un nouveau HAR de la même période lente.

La colonne “Après PostgreSQL production” reste **NON MESURÉE** jusqu'à cette recette.

## Preflight final

- intégrité manifeste : **OK** ;
- syntaxe Python : **OK** ;
- `PRAGMA quick_check` des 4 bases SQLite : **OK** ;
- `requirements.txt` exige `requests==2.33.0`; l’environnement de construction utilise encore 2.32.5, donc l’installation production doit exécuter `INSTALL_DEPENDENCIES.bat` ;
- recette Windows/Caddy/Hermes : à rejouer sur le serveur cible.
