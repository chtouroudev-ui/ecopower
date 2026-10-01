# NELYIO V60.3 — Mise en production et recette finale

Build : **60.3-PROD-FINAL**

## Important

- **Ne pas wipe PostgreSQL.**
- Ne pas `DROP`, `TRUNCATE` ou recréer les bases métier.
- Installer V60.3 dans un **nouveau dossier**.
- Copier votre `data\postgres.env` de production et votre configuration Caddy/certificat selon l'installation actuelle.
- Faire une sauvegarde PostgreSQL avant d'appliquer la migration d'index.

## 1. Mesure PostgreSQL AVANT migration

```bat
DIAGNOSTIC_PERFORMANCE_POSTGRESQL.bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat before
```

Conserver :

```text
logs\postgresql_diagnostic.json
logs\explain_before.json
```

`pg_stat_statements` est lu s'il existe déjà ; V60.3 ne l'active jamais automatiquement.

## 2. Migration performance

Script :

```text
migrations\performance_indexes.sql
```

Il est idempotent et non destructif. Il ajoute seulement les index justifiés par les hot paths mesurés. Les deux index trigram ANI/téléphone ne sont créés que si `pg_trgm` est **déjà installé**.

Après application :

```bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
```

Comparer `logs\explain_before.json` et `logs\explain_after.json`.

## 3. Démarrage

HTTP :

```bat
START_NELYIO.bat
```

ou HTTPS :

```bat
START_NELYIO_HTTPS.bat
```

Vérifier :

```powershell
Invoke-RestMethod http://127.0.0.1:9051/healthz
Invoke-RestMethod http://127.0.0.1:9052/healthz
```

Attendu : build **60.3-PROD-FINAL**, `services_ok=true`, Web/Live/Analytics sains et Analytics `max_concurrency=5`.

## 4. Import SIMPLIFY2 / group.har

Ne pas réactiver l'ancien scan automatique.

```bat
OPEN_NELYIO_IMPORTER.bat
```

Le site continue à lire l'ancien snapshot stable pendant la préparation. La nouvelle référence n'est activée qu'après validation des données critiques. L'Importer affiche les temps de :

- lecture/extraction ;
- parsing + normalisation + déduplication Stats.AGENT ;
- parsing ODCalls ;
- enrichissement ODActions ;
- transaction staging ;
- Quality / Détails / Annuaire / Groupes.

Un échec critique conserve l'ancien snapshot. Réimporter le même fichier reste idempotent.

## 5. Live Nelyio

La vue Live lit directement `Nelyio_Live.db` et doit afficher la journée courante : événements, appels observés, agents, files et campagnes. La base locale Live est en WAL, indépendante des tables historiques PostgreSQL et purgée au changement de date.

## 6. Recette métier

Vérifier au minimum :

- Login / Dashboard ;
- Qualité de service ;
- Qualité Agents : Traités, **Appels < 10 s**, Moy. appel entrant, Travail, Déconnecté, Pauses ;
- Distribution ;
- Diagnostic ;
- Recherche ANI/appels ;
- Détails / coupures ;
- Groupes et Équipe & Files ;
- Administration ;
- Live ;
- HTTP puis HTTPS.

Pour Groupes : contrôler deux groupes, un agent multi-groupe et une affectation inactive qui ne doit pas apparaître.

## 7. Benchmark 5 utilisateurs

Dans une console temporaire :

```bat
set NELYIO_BENCH_USER=compte_test
set NELYIO_BENCH_PASSWORD=mot_de_passe_test
BENCHMARK_5_UTILISATEURS.bat
```

Résultat : `BENCHMARK_API_RUNTIME.json`.

## 8. Si une page reste lente

```bat
ANALYSER_PERFORMANCE_HTTP.bat
```

Fournir ensuite :

```text
logs\postgresql_diagnostic.json
logs\explain_before.json
logs\explain_after.json
BENCHMARK_API_RUNTIME.json
logs\performance.jsonl
un nouveau HAR
```

Ces fichiers permettent de distinguer acquisition connexion PostgreSQL, SQL, Python, JSON et attente navigateur, sans reset de base.
