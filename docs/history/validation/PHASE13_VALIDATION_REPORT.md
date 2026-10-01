# Phase 13 — Validation RC24

## Fait

- table `access_profiles` ajoutée au schéma Administration ;
- snapshot versionné des droits d’interfaces, ANI et périmètre métier ;
- création / duplication / actualisation / suppression d’un profil ;
- création d’un groupe depuis un profil ;
- duplication d’un groupe sans membres ;
- application explicite d’un profil avec invalidation des sessions du groupe cible ;
- contrôle des références de groupes métier supprimés ;
- preflight PostgreSQL étendu aux tables de contrôle d’accès Phase 12/13 ;
- interface Utilisateurs & accès enrichie sans changer le modèle d’autorisation serveur.

## Vérifié

- 180/180 tests Python PASS ;
- 6/6 tests dédiés Phase 13 PASS ;
- 21/21 JavaScript syntax PASS ;
- audit frontend PASS ;
- compileall PASS ;
- preflight du build propre RC24 PASS ;
- dry-run RC23 -> RC24 PASS ;
- upgrade appliqué sur copie RC23 PASS ;
- `TECHIN_Stock_Manager.db`, `NELYIO_Supervision.db`, `Nelyio_Details.db`, `Nelyio_Live.db`, `Nelyio_Services.db` et `Caddyfile` préservés bit-à-bit.
