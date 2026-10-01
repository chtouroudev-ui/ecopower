# PostgreSQL PROD RC2B - recreation de configuration

## Cas traite

`data\postgres.env` est absent de toutes les anciennes copies alors que la base PostgreSQL `nelyio` existe deja.

## Nouveau workflow

`RECREER_CONFIG_POSTGRESQL_EXISTANTE.bat` :

- ne supprime pas la base `nelyio` ;
- ne relance pas `postgres_migrate.py --reset` ;
- demande le mot de passe administrateur PostgreSQL (`postgres`) ;
- detecte la base `nelyio` existante ;
- cree ou reinitialise le compte `nelyio_app` avec un nouveau mot de passe aleatoire ;
- recree localement `data\postgres.env` ;
- verifie la connexion avec `nelyio_app` ;
- lance `postgres_runtime_preflight.py --repair` ;
- bloque le demarrage si le preflight reste en echec.

Le fichier `postgres.env` n'est pas fourni dans les ZIP de livraison car il contient le secret de connexion PostgreSQL propre a la machine.
