# Phase 14 — Validation RC25

## Fait

- écran `Utilisateurs & accès` restructuré en quatre onglets ;
- recherche et filtres des comptes ;
- sélection multiple et affectation en masse à un groupe d’accès ;
- formulaires de création repliables ;
- navigateur compact des groupes d’accès avec un seul éditeur ouvert ;
- droits d’interfaces regroupés en sections repliables ;
- périmètre métier et groupes autorisés repliables ;
- profils d’accès compactés avec actions repliées ;
- vue `Droits effectifs` calculée depuis les données renvoyées par le backend ;
- responsive mobile/tablette ajouté ;
- aucune modification du modèle d’autorisation serveur RC23/RC24.

## Vérifié

- 187/187 tests Python PASS ;
- 7/7 tests dédiés Phase 14 PASS ;
- 21/21 JavaScript syntax PASS ;
- audit frontend PASS ;
- compileall PASS.

- preflight du build propre RC25 PASS ;
- dry-run RC24 -> RC25 PASS ;
- upgrade appliqué sur copie RC24 PASS ;
- `TECHIN_Stock_Manager.db`, `NELYIO_Supervision.db`, `Nelyio_Details.db`, `Nelyio_Live.db`, `Nelyio_Services.db` et `Caddyfile` préservés bit-à-bit.
