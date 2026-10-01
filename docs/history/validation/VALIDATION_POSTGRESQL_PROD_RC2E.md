# Validation PostgreSQL PROD RC2E

## Incident corrige

Le smoke test RC2D echouait sur le Dashboard avec :

`la colonne « derniere_vue » n'existe pas`

La requete SQLite utilisait `ORDER BY datetime(derniere_vue)` alors que `derniere_vue` est un alias de `MAX(date_evenement)`. La couche PostgreSQL traduisait cela en `ORDER BY CAST(derniere_vue AS timestamp)`, et PostgreSQL cherchait alors une colonne physique `derniere_vue` dans l entree de la requete.

## Correctif

- Dashboard : `ORDER BY MAX(date_evenement) DESC`.
- Detail PC / historique utilisateurs : meme correction proactive.
- SQL centralise dans `inventory_service.dashboard_transitions_sql()` et `inventory_service.pc_users_sql()`.
- Le preflight PostgreSQL reutilise ces memes fonctions afin que le test soit identique au runtime.

## Verifications build

- Compilation Python du projet racine : OK.
- Smoke SQLite des deux requetes partagees : OK.
- Traduction PostgreSQL : aucune reference `CAST(derniere_vue AS timestamp)` restante.
- Recherche globale : aucune occurrence runtime de `datetime(derniere_vue)` restante.
- Integrite du manifeste recalculee apres patch.

## Validation serveur obligatoire

1. Recuperer/copier le `data\postgres.env` existant.
2. Lancer `VERIFIER_POSTGRESQL.bat`.
3. Exiger zero `ECHEC`, notamment `Smoke test applicatif`.
4. Lancer `VALIDATION_PRODUCTION.bat`.
5. Seulement ensuite lancer `START_NELYIO.bat`.

Aucun reset de la base et aucune re-migration SQLite ne sont necessaires pour RC2E.
