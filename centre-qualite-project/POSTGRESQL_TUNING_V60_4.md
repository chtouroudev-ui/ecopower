# PostgreSQL — réglage mémoire après V60.4

Le diagnostic réel indique PostgreSQL 18.6 avec environ :

```text
max_connections      100
shared_buffers       128MB
work_mem             4MB
effective_cache_size 4GB
```

Le serveur dispose d'environ 32 Go de RAM. Ces paramètres sont très conservateurs, mais **la requête doit être corrigée avant d'augmenter la mémoire**. V60.4 supprime d'abord les scans/N+1 mesurés.

## Point de départ prudent à tester ensuite

Si le serveur est principalement dédié à Nelyio/PostgreSQL et après sauvegarde :

```text
shared_buffers       4GB
effective_cache_size 16GB
work_mem             8MB
maintenance_work_mem 512MB
max_connections      100  # ne pas augmenter pour l'instant
```

`work_mem` s'applique par opération de tri/hash et par connexion, pas une fois pour tout PostgreSQL. Ne pas le mettre à 64/128 MB globalement sans test de concurrence.

## Ne pas modifier sans preuve

- `random_page_cost`
- `effective_io_concurrency`
- JIT
- autovacuum thresholds
- checkpoint/WAL settings

Le type de stockage n'a pas été établi par le diagnostic fourni.

## Mesure avant/après

Après V60.4 + index, refaire :

```bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
DIAGNOSTIC_PERFORMANCE_POSTGRESQL.bat
BENCHMARK_5_UTILISATEURS.bat
```

Si les requêtes restent CPU/tri/disque limitées, ajuster ensuite la configuration PostgreSQL avec mesure avant/après.
