# Validation — PostgreSQL PROD RC2

## Correctifs issus du preflight serveur

Trois defauts reels detectes par `postgres_runtime_preflight.py` ont ete corriges :

1. **DDL coupe dans un commentaire SQL** : le separateur `executescript()` ne coupe plus sur un point-virgule present dans un commentaire `--` ou `/* ... */`. Le texte `they are evaluated after` ne peut plus etre execute comme SQL.
2. **Fonction `public.user_key()`** : suppression du second `split_part(..., '\\', 2)` qui renvoyait une chaine vide. Les probes attendus sont maintenant `distribution_agent('S1001') = '1001'` et `user_key('DOMAIN\\1001') = '1001'`.
3. **Predicats SQLite `WHERE 0/1`** : les requetes Qualite utilisent maintenant `FALSE/TRUE`, valides PostgreSQL. Le CTE vide de Distribution emet en PostgreSQL des NULL explicitement types sans casser le fallback SQLite.

## Durcissement complementaire

- suppression des hints SQLite `INDEXED BY` lors de la traduction PostgreSQL ;
- cache Détails base sur l'identite d'un fichier SQLite desactive en mode PostgreSQL ;
- requetes de dernier nom agent rendues deterministes avec `ROW_NUMBER()` au lieu du raccourci SQLite `GROUP BY ... HAVING MAX(import_id)` ;
- `VALIDATION_PRODUCTION.bat` execute maintenant le preflight PostgreSQL avec `--repair` (mise a niveau non destructive) avant validation ;
- build `db_compat`: `PRODRC2-PG-HARDENED`.

## Verifications hors serveur

- compilation de tous les modules Python racine ;
- test du splitter SQL avec commentaires contenant des points-virgules ;
- test de traduction `AUTOINCREMENT`, `INDEXED BY` et colonne reservee `end` ;
- smoke test SQLite des vues Qualite de service, Qualite agents, Distribution, Details et workflow import ;
- scan : aucun `WHERE 0`, `WHERE 1`, `AND 0` ni `HAVING MAX(import_id)` restant dans les modules runtime.

## Validation obligatoire sur le serveur

Le feu vert production exige :

1. `VERIFIER_POSTGRESQL.bat` ou `VALIDATION_PRODUCTION.bat` = OK ;
2. `START_NELYIO.bat` = backend + services sains ;
3. `VALIDER_APRES_DEMARRAGE.bat` = OK ;
4. import d'un SIMPLIFY2 reel termine en `completed` ;
5. `VALIDER_QUALITE.bat 2026-09-18` et controle contre le rapport de reference sur un perimetre identique.
