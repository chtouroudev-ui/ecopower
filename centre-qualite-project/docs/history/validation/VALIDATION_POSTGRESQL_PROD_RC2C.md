# Nelyio V56.18 MS1 - PostgreSQL PROD RC2C

## Correctifs issus du preflight serveur du 22/09/2026

### 1. `InFailedSqlTransaction` pendant la reparation runtime
Cause identifiee : la couche `db_compat` tentait d emuler `last_insert_rowid()` apres chaque `INSERT`. Sur une table a cle primaire texte telle que `supervision.settings(key)`, `pg_get_serial_sequence()` ne renvoie aucune sequence ; l ancien probe `currval(...)` pouvait echouer puis etre masque, tout en laissant la transaction PostgreSQL en etat `failed`. La requete suivante produisait ensuite `InFailedSqlTransaction`.

Correction RC2C : le probe lastrowid est limite aux PK ayant une sequence et entierement isole dans un `SAVEPOINT`. Un echec du probe ne peut plus contaminer la transaction applicative.

### 2. `KeyError: export_offset` dans le smoke test
Cause : une reparation precedente interrompue pouvait laisser `supervision.settings` sans toutes les valeurs historiques attendues.

Correction RC2C :
- `supervision.init()` peut de nouveau terminer ses INSERT de defaults ;
- le preflight insere de facon idempotente tous les defaults requis et `bridge_key` ;
- `supervision_db.config()` retombe sur les valeurs de `DEFAULTS` au lieu de faire planter l application si une cle legacy manque ;
- le preflight controle explicitement les parametres supervision requis.

### 3. Diagnostic de production
La reparation runtime est maintenant decoupee par etapes et commit. Si une nouvelle incompatibilite existe, le rapport affichera l etape racine (`supervision.init`, `quality inbound index`, `postgres helpers/triggers`, etc.) au lieu d un simple `InFailedSqlTransaction`. Le smoke test indique egalement le module en cause (`Qualite service overview`, `Workflow import`, etc.).

## Validations locales effectuees
- syntaxe Python de tous les modules racine : OK ;
- regression du splitter SQL avec `;` dans les commentaires : OK ;
- fallback `export_offset=120` avec cle absente : OK ;
- simulation du probe lastrowid : PK sans sequence, currval indisponible et currval valide : OK ;
- manifest de production recalcule apres correctifs.

## Validation serveur obligatoire
1. Recuperer ou recreer `data\postgres.env`.
2. Executer `VERIFIER_POSTGRESQL.bat`.
3. Le resultat attendu est zero ligne `ECHEC`.
4. Executer ensuite `VALIDATION_PRODUCTION.bat`.
5. Seulement apres, lancer `START_NELYIO.bat`.
