# Migration totale PostgreSQL — Nelyio V56.18 MS1 PROD RC1

PostgreSQL est la source de vérité des données métier avec quatre schémas : `admin`, `supervision`, `details`, `live`.

`CONFIGURER_POSTGRESQL_AUTO.bat` réalise la création du compte/base, la migration initiale et le durcissement runtime. Il conserve les SQLite historiques sans les utiliser comme backend métier après activation.

Après la migration, `postgres_runtime_preflight.py` vérifie automatiquement les tables, fonctions, triggers, index et requêtes applicatives indispensables. Le lancement normal exécute le même contrôle avant le backend.

Pour vérifier manuellement : `VERIFIER_POSTGRESQL.bat`.
Pour sauvegarder : `SAUVEGARDER_POSTGRESQL.bat`.

Ne jamais copier les fichiers internes du répertoire de données PostgreSQL pendant que le service tourne comme méthode de sauvegarde applicative. Utiliser `pg_dump`.
