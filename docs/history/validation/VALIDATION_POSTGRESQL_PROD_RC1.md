# Validation — PostgreSQL PROD RC1

Date de construction : 2026-09-21.

## Vérifications automatiques effectuées dans l'environnement de construction

- 157 tests ciblés : **réussis**.
- 5 tests : ignorés par leurs conditions de fixture/environnement.
- Tous les modules Python racine : compilation **OK**.
- `static/quality-overview.js` : syntaxe **OK**.
- `static/quality-activity.js` : syntaxe **OK**.
- Préflight statique / intégrité du paquet : **OK**.
- Les quatre SQLite de migration : `PRAGMA quick_check` **OK**.

Une exécution de la suite pytest complète a été tentée ; la limite de temps de l'environnement a été atteinte après le début de la suite, sans échec observé avant l'arrêt. Le résultat complet n'est donc pas revendiqué.

## Durcissements spécifiques PostgreSQL

- conversion SQLite `AUTOINCREMENT` -> identity PostgreSQL ;
- protection du nom historique réservé `end` ;
- source PostgreSQL pour l'annuaire et analytics ;
- allocation des IDs d'import depuis Details PostgreSQL ;
- fonctions PostgreSQL pour les heures Qualité et Distribution ;
- curseur `ingest_seq` à la place de `rowid` pour Live/signaux ;
- triggers de révision Détails complets ;
- préflight runtime exécuté avant chaque démarrage ;
- sauvegarde `pg_dump` vérifiable ;
- rétention destructive bloquée tant que son rollback PostgreSQL natif n'est pas validé.

## Qualité

Part traitée : `Traités / (Traités + Abandonnés + Disséminés/perdus) × 100`.

Des contrôles de réconciliation empêchent désormais l'interface de présenter silencieusement un total incohérent entre total, campagnes, agents et heures.

## Ce qui doit encore être validé sur le serveur Windows cible

- connexion au PostgreSQL réel ;
- `postgres_runtime_preflight.py --repair` ;
- démarrage des quatre processus ;
- import réel SIMPLIFY2 ;
- résultat `VALIDER_QUALITE.bat` ;
- HTTPS/Caddy depuis un poste client ;
- création et relecture d'un `pg_dump`.

Ce candidat ne doit être déclaré production qu'après ces contrôles serveur.
