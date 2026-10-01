# Nelyio RC2K - STARTUP FIX3

## Cause racine

Le préflight PostgreSQL pouvait réussir, puis `app.py` exécutait encore plusieurs tâches avant d'entrer dans `serve_forever()` :

- `ensure_schema()` une seconde fois ;
- synchronisation annuaire Support ;
- migration legacy ;
- récupération F4.1 des groupes ;
- import diagnostic de démarrage.

Tant que ces tâches n'étaient pas terminées, le processus Python restait vivant mais le port 9051 ne répondait pas. Le lanceur finissait donc en code 14 sans traceback Python.

## Correctifs

1. `START_NELYIO.ps1` marque le préflight PostgreSQL validé via `NELYIO_POSTGRES_PREFLIGHT_OK=1`.
2. `app.py` ne rejoue plus `ensure_schema()` lorsque le préflight PostgreSQL vient de valider le runtime.
3. Les tâches non critiques sont déplacées dans un thread post-démarrage ; elles ne bloquent plus `/healthz`.
4. `startup_progress.log` trace chaque étape avec sa durée.
5. La sortie Python est non bufferisée.
6. Le timeout du wrapper HTTPS passe à 300 s pour le mode silencieux.
7. Le code retour HTTPS est forcé en entier pour éviter un faux `Code retour: 0`.
8. Le DEBUG affiche automatiquement `startup_progress.log`, `backend_9051_stdout.log` et `backend_9051_stderr.log` en cas d'échec.

## Validation

- 37 tests Python : PASS.
- Test de démarrage isolé SQLite : `/healthz` HTTP 200.
- Le serveur est mis en écoute avant les tâches de maintenance non critiques.
- Aucune base de données n'est incluse ou modifiée dans le patch.

## Après installation

Lancer :

`START_NELYIO_HTTPS_DEBUG.bat`

En cas de problème, consulter en priorité :

- `logs/startup_progress.log`
- `logs/backend_9051_stdout.log`
- `logs/backend_9051_stderr.log`
- `logs/startup_error.log`
