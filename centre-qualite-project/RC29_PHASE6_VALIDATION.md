# RC29 — PHASE 6 — Performance / optimisation globale

Date : 28/09/2026  
Source : `Nelyio-ARCH_RC29_PHASE5_TRI_GLOBAL.zip`  
Mode : copie de travail ; aucune base métier modifiée.

## 1. Périmètre

Phase limitée à la performance et à l'observabilité après stabilisation fonctionnelle des Phases 1 à 5.

Contraintes respectées :

- aucune métrique inventée ;
- aucune optimisation sans cause ou coût identifiable ;
- PostgreSQL production / HTTPS / Caddy / navigateur réel = **NON MESURÉ** dans cet environnement ;
- pas de reset, migration destructive, `DROP`, `TRUNCATE` ou suppression de données ;
- aucun changement de KPI, de groupes, de QoS, d'identités, de règles Live ou de tri métier ;
- conservation du single-flight et des caches existants ;
- validation à cinq clients simultanés lorsque le scénario est exécutable localement.

## 2. Cause prouvée et correction ciblée

### Écriture de session sur chaque requête authentifiée

Avant Phase 6, `Handler.session_user()` exécutait systématiquement :

1. lecture de la session ;
2. `UPDATE sessions SET last_seen_at=...` ;
3. `COMMIT` ;

à **chaque requête authentifiée**, y compris les appels de polling Live.

Cela créait une écriture transactionnelle globale inutile sur le chemin commun de toutes les API.

Correction :

- ajout du paramètre `NELYIO_SESSION_TOUCH_SECONDS`, défaut **60 s** ;
- bornes autorisées : 5 à 300 s ;
- le timeout d'inactivité métier reste inchangé ;
- `last_seen_at` n'est persisté que si le dernier heartbeat stocké dépasse le seuil ;
- une session fraîche reste valide sans provoquer d'UPDATE/COMMIT à chaque polling.

### Validation du contrat

Tests Phase 6 :

- session fraîche : **0 UPDATE / 0 COMMIT** ;
- session vieille de 2 minutes avec seuil 60 s : **1 UPDATE / 1 COMMIT**.

Le gain de latence de production associé est **NON MESURÉ** ici ; la réduction du nombre d'écritures est, elle, directement vérifiée.

## 3. Instrumentation ajoutée

`perf_trace.py` distingue maintenant :

- `total_ms` ;
- `auth_ms` ;
- `db_acquire_ms` ;
- `sql_ms` / `sql_count` / `sql_max_ms` ;
- `worker_ms` ;
- `compute_ms` ;
- `json_ms` ;
- `response_bytes` ;
- `python_other_ms` ;
- `cache_hit`.

Aucune valeur de filtre, ANI, paramètre SQL ou contenu patient n'est écrite dans la trace.

### Raccordements

- Web : temps d'authentification et taille JSON de réponse ;
- appel Web → worker Analytics : `worker_ms` ;
- worker Analytics : temps `_run_query` isolé dans `compute_ms` ;
- SQL/connexion : instrumentation existante conservée ;
- sérialisation JSON : instrumentation existante conservée ;
- cache Analytics : instrumentation existante conservée ;
- Importer : instrumentation détaillée existante conservée (`core_performance`, `zip_cache`).

`tools/analyze_performance_log.py` expose maintenant les médianes Auth / Worker / Compute / JSON / taille réponse en plus de SQL.

Les anciens journaux restent compatibles : les nouveaux champs absents sont lus comme zéro.

## 4. Single-flight / concurrence

Le mécanisme Analytics existant n'a pas été remplacé.

Test exécuté : 5 requêtes identiques à froid.

Résultat :

- calculs réels : **1** ;
- réponses réutilisées via single-flight/cache : **4** ;
- test : **PASS**.

Aucune mise en cache inter-périmètre ou mélange de filtres n'a été introduit.

## 5. Test local 5 utilisateurs

Scénario exécutable localement : serveur HTTP threadé, endpoint `/healthz`, 5 clients simultanés, 10 vagues, soit 50 requêtes.

### Phase 5 — baseline locale

- requêtes : 50 ;
- concurrence : 5 ;
- HTTP 200 : 50/50 ;
- médiane : **2,988 ms** ;
- P95 : **22,104 ms** ;
- max : **23,866 ms**.

### Phase 6 — même scénario local

- requêtes : 50 ;
- concurrence : 5 ;
- HTTP 200 : 50/50 ;
- médiane : **2,552 ms** ;
- P95 : **13,802 ms** ;
- max : **16,782 ms**.

### Interprétation

Ces chiffres sont **MESURÉS**, mais ne constituent **pas une preuve de gain Phase 6** :

- `/healthz` ne passe pas par l'authentification optimisée ;
- le benchmark est local, très court, sans PostgreSQL réel, sans TLS/Caddy, sans réseau et sans volume métier ;
- une seule série avant/après ne permet pas d'attribuer la différence à la Phase 6.

Il sert uniquement à vérifier l'absence de régression évidente du serveur HTTP threadé à cinq clients.

Le fichier `RC29_PHASE6_LOCAL_BENCHMARK.json` contient la mesure Phase 6.

## 6. PostgreSQL / production

Les preuves historiques embarquées montrent notamment des anciens hotspots :

- `/api/quality/agent-activity` jusqu'à ~29,9 s ;
- Support jusqu'à ~23 s ;
- ancien Analytics avec jusqu'à 997 requêtes SQL ;
- anciens scans de catalogue de l'ordre de 607k lignes.

Ces valeurs sont des traces antérieures de l'archive ; elles ne sont pas présentées comme l'état actuel après Phase 6.

Sont **NON MESURÉS** pendant cette intervention :

- `EXPLAIN (ANALYZE, BUFFERS)` PostgreSQL production après Phase 6 ;
- `pg_stat_statements` production ;
- contention/verrous réels ;
- CPU/RAM/IO Windows ;
- vrai import SIMPLIFY2 concurrent au Live ;
- benchmark API authentifié 5 utilisateurs contre PostgreSQL réel ;
- HTTPS/Caddy ;
- temps navigateur, Long Tasks et rendu DOM réel.

Aucun index ou réglage PostgreSQL n'a donc été ajouté spéculativement.

## 7. Tests exécutés

Suite finale : **73 tests PASS**.

Comprend notamment :

- Phases RC29 1 à 6 ;
- groupes ;
- Qualité agents ;
- campagnes Live ;
- stabilité production ;
- single-flight Analytics ;
- observabilité/performance ;
- 5 clients HTTP simultanés.

Validation syntaxique :

- Python racine : **142 fichiers AST, 0 erreur** ;
- JavaScript `static/*.js` : **0 erreur `node --check`**.

## 8. Intégrité des données

Après les tests, les artefacts runtime touchés par l'exécution ont été restaurés depuis la Phase 5.

Comparaison finale Phase 5 → Phase 6 :

- `*.db` : inchangés ;
- `*.db-wal` : inchangés ;
- `*.db-shm` : inchangés ;
- logs runtime existants : inchangés.

Aucune migration de données n'est requise.

## 9. Fichiers fonctionnels modifiés / ajoutés

- `perf_trace.py` ;
- `http_handler.py` ;
- `analytics_rpc.py` ;
- `analytics_service.py` ;
- `tools/analyze_performance_log.py` ;
- `rc29_phase6_performance_test.py` ;
- `RC29_PHASE6_LOCAL_BENCHMARK.json` ;
- `RC29_PHASE6_VALIDATION.md`.

## 10. Rollback

Rollback Phase 6 : restaurer les cinq fichiers de code depuis la Phase 5 :

- `perf_trace.py` ;
- `http_handler.py` ;
- `analytics_rpc.py` ;
- `analytics_service.py` ;
- `tools/analyze_performance_log.py`.

Aucune restauration de base ou migration inverse n'est nécessaire.

## 11. Verdict Phase 6

- instrumentation détaillée : **PASS** ;
- suppression des écritures répétitives de heartbeat session : **PASS** ;
- single-flight Analytics : **PASS** ;
- 5 clients HTTP locaux : **PASS** ;
- non-régression Phases 1–5 : **PASS** ;
- intégrité bases/runtime : **PASS** ;
- performance PostgreSQL/HTTPS réelle après correction : **NON MESURÉ**.

**STOP — ne pas commencer la Phase 7 sans validation utilisateur.**
