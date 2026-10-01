# NELYIO V60.4 — Diagnostic PostgreSQL réel et correctif prioritaire

Build : **60.4-POSTGRES-HOTFIX**  
Date : **25/09/2026**

## Mesure PostgreSQL réelle fournie par le serveur

Cette section remplace l’ancien statut « PostgreSQL production NON MESURÉ » pour le **diagnostic avant correctif**. Les mesures proviennent des fichiers `performance.jsonl`, `postgresql_diagnostic.json` et des `EXPLAIN (ANALYZE, BUFFERS)` exécutés sur le serveur réel.

| Chemin | Mesure avant V60.4 | Preuve |
|---|---:|---|
| Détails | **133.3 s** total | 132.9 s SQL, 49 SQL, requête max **92.1 s** |
| Détails (autre run) | **13.8 s** | 13.6 s SQL, 39 SQL, max 8.94 s |
| Analytics | **26.5 s** | **997 requêtes SQL**, 19.1 s SQL |
| Diagnostic incidents | jusqu’à **19.1 s** | 38 SQL, max 18.7 s |
| Support | ~**7.8 s** | 48 SQL, max 4.6 s |
| Recherche appels | ~**2.75 s** | 23 SQL, max 2.23 s |
| Roster agents | **2.47–3.63 s** | ~607 174 lignes triées pour 103 agents, `external merge` disque ~24.5 MB |

Le diagnostic ne montrait **aucune transaction longue ni session bloquée** au moment de la capture. `pg_stat_statements` n’était pas installé et n’a pas été activé automatiquement. PostgreSQL 18.6 utilisait `shared_buffers=128MB`, `work_mem=4MB`, `effective_cache_size=4GB`.

## Causes corrigées en V60.4

1. **Roster / Équipe & Files** : le catalogue non filtré ne trie plus toute l’historique `activities`; il lit uniquement le dernier `import_id` ACTIVE de `coverage`.
2. **Détails** : les pointeurs `active_days` sont chargés en une seule requête pour la période, au lieu de lectures répétées par jour/source.
3. **Détails PostgreSQL** : index ciblé `(event_source, source_import_id, start DESC, id DESC)` pour la pagination réelle du journal.
4. **Support/Analytics** : suppression du N+1 « activité juste avant / juste après » pour chaque fermeture probable; chargement batch des voisins.
5. **Frontend** : cache-busters V60.4 sur les 15 scripts JS afin d’éviter un frontend ancien face à un backend nouveau.

## Validation après correctif

- **68/68 tests Python** ;
- **15/15 JavaScript** (`node --check`) ;
- compilation Python complète ;
- bases incluses byte-for-byte identiques à V60.3 ;
- migration `migrations/performance_indexes.sql` : idempotente, non destructive, aucun `DROP/TRUNCATE/DELETE`.

Le **temps PostgreSQL réel après V60.4 reste NON MESURÉ** tant que `EXPLAIN_PERFORMANCE_POSTGRESQL.bat after` et un nouveau `performance.jsonl` ne sont pas rejoués sur le serveur.

---

# NELYIO V60.3 — Diagnostic profond et optimisation performance

Build : **60.3-PROD-FINAL**  
Date : **24/09/2026**  
Priorité : exactitude → stabilité → performance → multi-utilisateur → maintenabilité → nettoyage.

## 1. Inventaire architecture

Architecture finale conservée simple :

```text
Navigateur
   ↓
Web/API Nelyio :9051
   ├─ Core / configuration / administration
   ├─ appels légers / pagination
   └─ RPC analytique
          ↓
     Analytics :9052
          ↓
       PostgreSQL

Hermes → Live Service → Nelyio_Live.db SQLite/WAL local (journée courante)
SIMPLIFY2/group.har → Importer local manuel → staging PostgreSQL → commit snapshot
```

PostgreSQL reste la base métier/historique. SQLite n'est utilisé que pour le buffer Live journalier et les heartbeats locaux afin qu'une panne/latence PostgreSQL ne bloque pas la santé des services.

## 2. Mesure avant modification

Sources réellement analysées :

- HAR utilisateur de gels globaux ;
- HAR utilisateur final `stock-manager.nelyio.local(1).har` ;
- `http_slow.log` ;
- lecture des routes Backend/Frontend et du pipeline SQL ;
- benchmarks synthétiques isolés pour comparer les algorithmes sans toucher aux données utilisateur.

Le PostgreSQL de production n'est pas accessible depuis l'environnement de construction. Donc les plans `EXPLAIN ANALYZE`, `pg_stat_statements`, buffers et temps disque réels sont **NON MESURÉS** ici et aucun résultat n'est inventé.

### HAR final — latence dominante côté serveur

| Endpoint | Médiane observée | Max observé | Observation |
|---|---:|---:|---|
| Support | ~8.04 s | **31.52 s** | attente serveur + payload jusqu'à ~3.42 MB |
| Recherche appels | ~0.78 s | **9.15 s** | attente serveur dominante |
| Supervision | ~5.34 s | ~5.78 s | double chargement initial trouvé |
| Diagnostic incidents | ~3.60 s | ~3.60 s | agrégation historique |
| Qualité Agents | ~2.48 s | ~2.48 s | dernier HAR |
| Distribution | ~1.01 s | ~1.01 s | dernier HAR |

Le HAR de gels avait aussi montré : Qualité Agents ~53 s, Priorités/Équipe & Files ~36 s, Live status ~34 s, Supervision ~32 s, QoS ~29 s, Dashboard ~26 s, Groupes ~18 s. `http_slow.log` montrait Login jusqu'à ~83 s. La cause ne pouvait donc pas être seulement Caddy ou une formule QoS.

## 3. Instrumentation ajoutée

`perf_trace.py` mesure les requêtes lentes et écrit `logs/performance.jsonl` :

```text
total HTTP
connexion PostgreSQL (acquisition)
SQL cumulé
nombre de requêtes SQL
signature de la requête SQL la plus lente
sérialisation JSON
Python / autre
cache hit/miss
```

Les paramètres SQL, ANI, numéros et valeurs de filtres ne sont pas journalisés. Le seuil est configurable via `NELYIO_PERF_SLOW_MS`.

## 4. Dix bottlenecks principaux — preuve / correction / risque

### 1 — Support relisait trop d'appels

**Problème** : jusqu'à 31.52 s et ~3.42 MB.  
**Cause** : chargement d'une grande partie des ODCalls pour enrichir quelques incidents et détecter quelques anomalies.  
**Correction** : requêtes ciblées, anomalies filtrées en SQL, payload interactif compact/paginé.  
**Avant/Après synthétique comparable** : 1.0067 s → **0.0849 s** (x11.86).  
**Risque** : faible ; comptes métier vérifiés par tests/fixtures.

### 2 — Recherche d'appels filtrait/paginait trop tard

**Problème** : jusqu'à 9.15 s.  
**Cause** : mois entier matérialisé puis filtré/paginé côté Python pour plusieurs critères.  
**Correction** : filtres période/ANI/indice/call_id/campagne/motif/type/agent/anomalie/diagnostic poussés SQL ; pagination par jours autoritaires, hydratation seulement des jours nécessaires à la page.  
**Avant/Après synthétique comparable** : 1.0940 s → **0.0855 s** (x12.80).  
**Risque** : contrôlé par test multi-jours sans doublon ni trou.

### 3 — Diagnostic réutilisait des chemins trop génériques

**Problème** : 3.60 s dans le HAR.  
**Correction** : réduction des scans historiques indirects hérités des chemins Support/Appels.  
**Avant/Après synthétique** : 0.4403 s → **0.0264 s** (x16.68).  
**Risque** : résultats d'incidents vérifiés.

### 4 — Priorités / Équipe & Files rescannait l'historique

**Problème** : max ~36 s dans le HAR de gels.  
**Cause** : reconstruction de roster/campagnes depuis les activités même lorsqu'un snapshot ACTIVE Agent→File était disponible.  
**Correction** : source prioritaire = affectations configurées ACTIVE ; historique uniquement en repli diagnostic.  
**V60.3 synthétique** : froid **0.0083 s**, chaud **0.0023 s**.  
**Risque** : règle métier conservée : Groupe → Files → Agents ACTIVE ; campagnes non utilisées comme source primaire.

### 5 — Polling Groupes appelait des vues lourdes

**Cause** : rafraîchissement pouvait demander le workspace/priorités complet juste pour savoir si une révision avait changé.  
**Correction** : `/api/groups/status` léger ; workspace recalculé uniquement si token/révision change.  
**V60.3 synthétique** : **0.0014 s** médian.  
**Risque** : faible ; token change vérifié après modification groupe.

### 6 — Frontend doublait plusieurs requêtes initiales

**Cause** : Support, Recherche d'appels et Supervision chargeaient une première réponse pour construire les filtres puis relançaient immédiatement une seconde requête complète.  
**Correction** : le premier payload sert maintenant aux filtres **et** au premier rendu. Les AbortController existants restent utilisés lors des changements de vue.  
**Risque** : pas de changement des données, seulement suppression de requêtes dupliquées.

### 7 — Import permanent concurrençait le site

**Cause historique** : scan fréquent du dossier, hashing/lecture répétitive et traitements lourds pendant la navigation.  
**Correction** : `OPEN_NELYIO_IMPORTER.bat`, import volontaire, un seul import à la fois, priorité réduite, aucun scan permanent dans Web.  
**Risque** : opération utilisateur explicite au lieu d'un worker caché.

### 8 — Import rendait parfois une référence partielle visible

**Correction** : staging/snapshot. Le site garde l'ancien `coverage/call_coverage`; l'import prépare les données candidates puis commute les références dans une transaction courte après validation critique. Échec critique = ancien snapshot conservé.  
**Instrumentation import** : lecture/extraction, parsing/normalisation/dédup Stats.AGENT, parsing ODCalls, enrichissement ODActions, transaction staging, étapes Quality/Détails/Annuaire/Groupes.  
**Risque** : Détails peut finir après le commit critique sans rendre le KPI principal partiel.

### 9 — Live partageait autrefois des écritures/rafraîchissements historiques

**Correction** : Live service indépendant, `Nelyio_Live.db` SQLite/WAL local, journée courante uniquement, aucune écriture Live dans Support/Détails/Qualité PostgreSQL, vue `/api/collection/live` directe et polling uniquement lorsque l'écran Live est ouvert.  
**Risque** : la donnée brute Live J-1 est volontairement purgée ; l'historique métier provient des imports.

### 10 — Calculs Analytics identiques pouvaient provoquer un stampede

**Correction** : 32 verrous single-flight par clé + cache révisionné + max 5 calculs lourds simultanés.  
**Preuve** : test V60.3, 5 requêtes identiques à froid → **1 seul calcul réel**, 4 réutilisations.  
**Risque** : deux filtres réellement différents restent calculés séparément.

## 5. Audit PostgreSQL / SQL

### Requêtes et patterns corrigés

- scans massifs Support supprimés ;
- filtres Recherche d'appels poussés dans `WHERE` avant pagination ;
- pagination bornée par jours autoritaires ;
- roster Priorités basé sur snapshot ACTIVE au lieu d'un `DISTINCT` historique coûteux ;
- `group.har` en batch `executemany` ;
- import principal conserve les batchs/transactions existants : aucun remplacement aveugle par `COPY` sans preuve PostgreSQL réelle ;
- connexions PostgreSQL réutilisées par `(dsn,schema)` et rollbackées avant réemploi.

### Migration d'index justifiée

`migrations/performance_indexes.sql` est idempotent et non destructif :

1. `supervision.phone_calls(import_id,start)` ;
2. `supervision.phone_calls(indice)` ;
3. `supervision.activities(agent,import_id DESC,id DESC)` ;
4. GIN trigram ANI normalisé **seulement si `pg_trgm` est déjà installé** ;
5. GIN trigram téléphone combiné **seulement si `pg_trgm` est déjà installé**.

Le script n'active aucune extension, ne supprime aucun index/table et exécute `ANALYZE` sur les deux tables concernées.

### EXPLAIN / pg_stat_statements

**NON MESURÉ sur PostgreSQL production** dans cette construction. Outils fournis :

```text
DIAGNOSTIC_PERFORMANCE_POSTGRESQL.bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat before
EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
```

`tools/diagnose_postgresql.py` lit notamment sessions, transactions longues, blocages, scans tables/index, index attendus et `pg_stat_statements` s'il existe déjà. Il ne l'active pas.

`tools/explain_performance_queries.py` exécute des `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` en lecture seule sur les hot paths Appels/ANI/roster/Qualité.

## 6. Pool et concurrence PostgreSQL

`db_compat.py` réutilise les connexions par `(dsn,schema)`, rollbacke une transaction non terminée avant réemploi et limite le nombre de connexions inactives conservées (`NELYIO_PG_POOL_IDLE`, défaut 4, borné). Analytics limite les gros calculs à 5.

La bonne taille du pool sur le serveur réel est **NON MESURÉE** ici ; V60.3 n'augmente donc pas arbitrairement le pool en fonction des 32 Go de RAM.

## 7. Groupes / import group

Règle unique conservée partout :

```text
GROUP
  → FILES configurées/importées
  → AGENTS avec affectation ACTIVE
```

- inactif/partial/unknown n'ajoute pas l'agent ;
- multi-groupe autorisé ;
- campagnes non utilisées pour fabriquer l'appartenance ;
- snapshot incomplet ne remplace pas silencieusement la dernière configuration ACTIVE valide ;
- import `group.har` met les relations files en batch.

## 8. Qualité Agents

Corrections métier explicites :

- `Travail = présence observée - pauses - coaching` ;
- `Moy. appel entrant` prend en priorité `Stats.INBOUND.CallDuration`, puis fallback Stats.AGENT ;
- **Appels < 10 s** = appels entrants attribués à l'agent, durée valide strictement `< 10.000 s`, dans la plage/date/groupe filtrée ; 10.000 s n'est pas compté.

Les tests couvrent la frontière `<10`.

## 9. Benchmark V60.1 → V60.3

Fixture commune 60 000 appels / 50 agents / 30 jours :

| Fonction | V60.1 | V60.3 | Gain |
|---|---:|---:|---:|
| Qualité Agents | 0.0918 s | 0.0751 s | x1.22 |
| Qualité service | 0.5062 s | 0.4787 s | x1.06 |
| Distribution | 0.2625 s | 0.2670 s | x0.98 — stable |
| Support | 1.0067 s | 0.0849 s | **x11.86** |
| Recherche appels | 1.0940 s | 0.0855 s | **x12.80** |
| Diagnostic | 0.4403 s | 0.0264 s | **x16.68** |
| 5 vues mixtes | 3.3879 s | 0.5023 s | **x6.74** |

V60.3 est la médiane de trois runs indépendants pour les chiffres affichés. Voir `docs/history/performance/BENCHMARK_PERFORMANCE.md` et `V60_3_SYNTHETIC_BENCHMARK.json`.

## 10. Tests de non-régression

- **64/64 tests Python : OK** ;
- **15/15 JavaScript : OK** ;
- compileall Python : OK ;
- smoke Web + Live + Analytics : `services_ok=true` ;
- arrêt gracieux des trois processus : OK ;
- import snapshot/rollback : OK ;
- Live journée courante : OK ;
- groupes ACTIVE/multi-groupe : OK ;
- Appels <10 s : OK ;
- pagination Appels : OK ;
- single-flight Analytics : OK ;
- migration SQL : aucune instruction destructive.

## 11. Éléments encore NON MESURÉS

À valider sur le serveur de production :

- plans PostgreSQL avant/après ;
- `pg_stat_statements` réel ;
- acquisition pool réelle ;
- CPU/RAM/IO Windows pendant Import + Live ;
- benchmark HTTP 5 utilisateurs avec PostgreSQL ;
- latence HTTPS/Caddy après déploiement ;
- temps détaillés d'un vrai import SIMPLIFY2.

## 12. Conclusion

Les lenteurs principales mesurées ne provenaient pas d'un seul index : elles venaient d'une combinaison de scans historiques massifs, filtrage/pagination trop tardifs, appels frontend dupliqués, contention Import/Live/Analytics et absence d'instrumentation homogène. V60.3 corrige ces chemins tout en conservant PostgreSQL, les règles métier, l'idempotence des imports et les données existantes. La validation PostgreSQL finale doit maintenant être réalisée sur le vrai serveur avec les outils livrés, plutôt que par hypothèse.
