# RC2A - recuperation PostgreSQL

Le script `RECUPERER_CONFIG_POSTGRESQL_EXISTANTE.ps1` a ete renforce :
- accepte une configuration deja presente ;
- recherche recursivement sous le dossier parent, le niveau superieur, Desktop et Documents ;
- valide que le fichier contient `NELYIO_DATABASE_ENGINE=postgresql` et `NELYIO_DATABASE_URL=postgresql://...` ;
- permet de saisir manuellement soit l'ancien dossier Nelyio soit le chemin exact de `postgres.env` ;
- copie le fichier dans `data\postgres.env` et rappelle de lancer `VERIFIER_POSTGRESQL.bat`.
