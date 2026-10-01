# Validation PostgreSQL PROD RC2F

## Correction principale

RC2F corrige la compatibilite entre le SQL historique SQLite et le protocole de parametres psycopg lorsque les requetes contiennent des signes `%` litteraux.

Le symptome observe etait :

`only '%s', '%b', '%t' are allowed as placeholders, got '%''`

La cause etait l'appel `cursor.execute(sql, ())` meme pour une requete sans parametres. Avec psycopg, fournir une sequence de parametres active l'analyse pyformat et transforme un `%` litteral de `LIKE 'inventory_followup_%'` en pseudo-placeholder invalide.

## Correctif

- les requetes sans parametres sont executees avec `cursor.execute(sql)` ;
- les requetes avec parametres echappent les `%` litteraux en `%%` tout en preservant `%s`, `%b` et `%t` ;
- `executemany()` applique la meme protection ;
- le preflight controle explicitement un `LIKE ... %` sans parametre et avec parametre ;
- le smoke applicatif continue de controler Classification et Retention.

## Validation locale

- compilation Python : OK ;
- tests de traduction `? -> %s` et d'echappement des pourcentages : OK ;
- test du chemin `execute()` sans parametre : OK ;
- test du chemin `execute()` parametre avec wildcard SQL : OK ;
- aucune modification destructive du schema ou des donnees PostgreSQL.

## Validation serveur requise

Executer `VERIFIER_POSTGRESQL.bat`. Le resultat attendu contient :

- `OK - Mode PostgreSQL : PRODRC2F-PG-PERCENT-SAFE`
- `OK - Compatibilite pourcent psycopg`
- `OK - Smoke test applicatif`

avec zero `ECHEC` avant de lancer Nelyio.
