# NELYIO V60.3 — Validation finale

Build : **60.3-PROD-FINAL**  
Date : **24/09/2026**

## Validation effectuée

- **64/64 tests Python : OK** ;
- syntaxe **15/15** fichiers JavaScript : OK ;
- compilation Python complète : OK ;
- test single-flight Analytics : 5 requêtes identiques à froid → **1 calcul réel** : OK ;
- import staged/snapshot + conservation de l'ancien snapshot sur échec : OK ;
- Live dédié/current-day : OK ;
- Groupe → Files → Agents ACTIVE et multi-groupe : OK ;
- Qualité Agents : Travail, Moy. appel entrant et **Appels < 10 s** : OK ;
- pagination Recherche d'appels multi-jours sans doublon/trou : OK ;
- migration performance non destructive : OK ;
- manifeste code-only final : **243 fichiers** vérifiés ;
- `requirements.txt` exige `requests==2.33.0` (l’environnement de construction avait 2.32.5, donc le preflight local signale logiquement un avertissement jusqu’à installation des dépendances du paquet) ;
- benchmark synthétique 60 000 appels / 50 agents / 30 jours : OK ;
- 5 vues mixtes concurrentes synthétiques : médiane **0.5023 s** sur 3 runs, résultats valides ;
- smoke multi-processus Web + Live + Analytics : `services_ok=true`, Analytics `max_concurrency=5` : OK ;
- arrêt gracieux Web + Live + Analytics : OK.

## Exactitude métier protégée

Aucune formule QoS n'a été modifiée silencieusement. Les règles de groupe restent basées sur les files et les affectations ACTIVE. Les imports restent digest/idempotence protégés. Le compteur `Appels < 10 s` utilise une durée entrante valide strictement inférieure à 10 secondes.

## Bases et données

Cette release ne requiert **aucun reset** de PostgreSQL. Aucun `DROP DATABASE`, `DROP TABLE`, `TRUNCATE` ou effacement de données de production n'est utilisé par la migration performance.

Avant packaging final, les bases locales livrées sont restaurées depuis la baseline V60.2 et les artefacts runtime (`-wal`, `-shm`, PID, logs de test, caches Python) sont supprimés.

## Limites volontaires

Le serveur Windows/PostgreSQL/Caddy réel de l'utilisateur n'est pas accessible depuis l'environnement de construction. Sont donc explicitement **NON MESURÉS** ici :

- `EXPLAIN (ANALYZE, BUFFERS)` PostgreSQL production ;
- `pg_stat_statements` production ;
- locks/IO/CPU/RAM Windows pendant un vrai import + Live ;
- benchmark HTTP 5 utilisateurs contre PostgreSQL production ;
- latence HTTPS/Caddy réelle après déploiement ;
- temps réel des étapes d'un vrai import SIMPLIFY2 production.

Les outils inclus permettent de capturer ces preuves en lecture seule ou via la migration d'index idempotente documentée.
