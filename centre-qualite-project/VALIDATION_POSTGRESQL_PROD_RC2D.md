# Validation PostgreSQL PROD RC2D

## Correctifs

- Port PostgreSQL standard conserve : `127.0.0.1:5432`.
- Dashboard : calcul des jours et statut de suivi en SQL PostgreSQL natif (`CURRENT_DATE`, `GREATEST`) pour supprimer la dependance aux semantiques SQLite `julianday` / `MAX(x,y)`.
- Classification : requetes groupees rendues strictes PostgreSQL et sous-sections isolees. Une source optionnelle en erreur ne fait plus tomber toute la page en HTTP 500.
- Retention : lecture des parametres, gels et executions isolee ; les erreurs de plan sont renvoyees comme avertissement sans casser l'API de configuration.
- Preflight : ajout des tables runtime utilisees par ces interfaces et smoke tests Dashboard / Classification / Retention.
- Imports Python : suppression d une dependance circulaire supervision_db/details_store/agent_directory detectee par le smoke autonome.

## Verifications effectuees dans l'environnement de build

- Compilation Python des fichiers modifies : OK.
- Smoke SQLite sur Dashboard, Classification et plan de retention : OK.
- Traduction PostgreSQL du SQL Dashboard : aucune occurrence restante de `julianday(`, `date('now'...)` ou `MAX(0,...)`.
- Le script d'auto-configuration et le script de recreation utilisent deja le port 5432 par defaut.

## Validation obligatoire sur le serveur Windows

1. Recuperer/recreer `data\postgres.env`.
2. Executer `VERIFIER_POSTGRESQL.bat`.
3. Exiger zero `ECHEC`, notamment le `Smoke test applicatif`.
4. Executer `VALIDATION_PRODUCTION.bat`.
5. Lancer Nelyio puis verifier `/api/dashboard`, `/api/classification` et `/api/retention`.

Le build ne peut pas reproduire le serveur PostgreSQL Windows reel ; ce test cible reste obligatoire avant production.
