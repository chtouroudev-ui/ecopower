# NELYIO V59.1 — rapport de durcissement production

Build livré : **59.1-PROD-STABLE**  
Edition : **V59_1_PROD_STABLE_STARTUP_GROUP_LIVE_PERF**  
Source analysée : `NELYIO_V58_RC2M_PROD_OPTIMIZED.zip`  
Trace analysée : `TestSpeed.har`  
Date : **24/09/2026**

## 1. Diagnostic mesuré dans TestSpeed.har

La lenteur n’est pas due à la négociation HTTPS. La connexion/TLS ne représente que quelques millisecondes; l’attente du premier octet serveur domine les requêtes lentes.

| Requête | Max observé | Attente serveur max |
|---|---:|---:|
| `/api/quality/agent-activity` | 69.837 s | 69.834 s |
| `/api/collection/status` | 48.299 s | 48.296 s |
| `/api/supervision/diagnostic-incidents` | 41.578 s | 41.575 s |
| `/api/collection/summary` | 28.048 s | 28.044 s |
| `/api/groups/workspace` | 25.892 s | 25.889 s |
| `/api/quality/priorities` | 21.407 s | 21.404 s |
| `/api/quality/distributions` | 16.265 s | 16.263 s |
| `/api/quality/overview` | 10.780 s | 10.767 s |
| `/api/supervision/support` | 8.509 s | 8.504 s |

Le HAR contient 61 requêtes pour environ **358.3 s** de durée cumulée. Les endpoints lourds montrent aussi une forte variabilité, typique de contention/recalculs côté serveur.

### Preuve du problème Groupe dans le HAR

La réponse `/api/quality/priorities` de la session testée annonce `103` agents mais **0 file configurée / 0 campagne** (`source_type=empty`). Les groupes avaient bien leurs files importées, mais sans projection Agent -> File il était impossible de calculer les agents ACTIVE des groupes. Ce n’était donc pas seulement un bug visuel du filtre.

## 2. Démarrage / arrêt / HTTPS

### Corrigé

- Backend 9051 : détection d’une ancienne instance de **ce projet exact**, reprise/arrêt propre puis redémarrage; un processus inconnu n’est jamais tué.
- Workers Import/Live/Analytics : un PID file manquant n’entraîne plus le lancement silencieux d’un doublon; les processus exacts sont retrouvés/adoptés ou consolidés.
- Arrêt : création de stop flags pour permettre aux processus Python de sortir normalement; kill forcé uniquement après délai borné.
- Caddy 9050 : PID perdu/stale récupérable uniquement si le process `caddy` correspond au `Caddyfile` de ce projet.
- Build `/healthz` lu depuis `VERSION.json`, donc le launcher ne rejette plus un backend sain à cause d’un build codé en dur différent.
- Le préflight PostgreSQL reste le propriétaire du schéma avant démarrage; le Web ne rejoue pas inutilement tout le DDL.

### Caddy

Caddy n’est **pas inclus** dans le ZIP. Le launcher le cherche via `NELYIO_CADDY_EXE`, la racine, `tools\`, puis le `PATH`. Le `Caddyfile` expose HTTPS 9050 et reverse-proxy vers HTTP local 9051.

## 3. Performance — corrections V59.1

- Les vues Qualité lourdes sont déléguées au worker Analytics 9052 avec cache mémoire borné.
- Le cache Analytics PostgreSQL n’utilise plus `pg_current_snapshot()` comme révision : ce token change avec les transactions sans rapport et empêchait la réutilisation fiable du cache. La fraîcheur reste bornée par fenêtre temporelle + TTL par endpoint.
- `quality_agents` et `quality_metrics` n’exécutent plus `CREATE TABLE/INDEX` sur les GET PostgreSQL. Les verrous DDL restent au préflight/import, pas dans les clics utilisateurs.
- Qualité Agents utilise une table virtuelle `selected(import_id,day,lo,hi)` plutôt qu’une très longue chaîne de `OR` pour les appels.
- `collection/status` ne rejoue plus le schéma Live à chaque GET PostgreSQL et lit statut + configuration dans la même transaction/connexion.
- Les récupérations d’archives SIMPLIFY2 ne sont jamais faites depuis `groups/workspace` ou un GET Qualité.
- Les scopes Groupe/Priorités disposent de caches bornés et d’invalidation explicite par révision.

### Benchmark isolé rejoué

Données synthétiques : **60 000 appels, 50 agents, 30 jours, 5 répétitions**.

| Vue | Médiane | Requêtes SQL |
|---|---:|---:|
| Qualité agents | 0.0659 s | 29 |
| Qualité de service | 0.4440 s | 24 |
| Distributions | 0.2505 s | 16 |

Cinq vues Qualité Agents simultanées : **0.8319 s**, résultats cohérents. Ce benchmark SQLite isolé vérifie l’algorithme; il ne remplace pas la mesure PostgreSQL réelle sur votre serveur.

## 4. Groupes — logique corrigée

Règle analytique unique : **Groupe -> files importées/configurées -> agents dont l’affectation est ACTIVE**.

- `partial`, `inactive`, `unknown` et les observations artificielles ne donnent jamais l’appartenance.
- Un agent peut appartenir à plusieurs groupes.
- `group.har` importe les files sélectionnées; les agents sont calculés depuis la configuration Agents.csv/SIMPLIFY2.
- Les campagnes sont dérivées des files/observations et ne remplacent pas la file comme ancre du groupe.
- `user_group_members` reste Administration/permissions, séparé du scope analytique KPI.
- Si la configuration Agents.csv manque, **Import Worker** tente la récupération au démarrage puis périodiquement hors HTTP; une récupération réussie invalide le scope Groupe.
- L’interface Groupes expose `assignment_source_available`, `assignment_recovered` et `assignment_warning` pour rendre ce diagnostic visible.

Test direct du parser HAR Base64 : 2 files actives + 1 inactive -> seules les 2 actives ont été importées.

## 5. Live

Le Live reste un service séparé du Web. V59.1 conserve la session/outbox durable et améliore son impact sur l’application :

- démarrage validé par heartbeat;
- Web refuse une fausse activation si Live n’est pas sain;
- arrêt gracieux avant kill de secours;
- `collection/status` allégé (pas de DDL interactif, une seule lecture DB pour statut + configuration);
- les calculs Qualité/Support lourds sont isolés dans Analytics, ce qui évite d’affamer les petites requêtes Live.

## 6. Validation effectuée dans cette session

- **51/51 tests Python : OK**.
- Compilation Python complète : **OK**.
- Syntaxe des **15 fichiers JavaScript** (`node --check`) : **OK**.
- Test `group.har` Base64 ACTIVE-only : **OK**.
- Aucun binaire Caddy embarqué : **OK**.
- Invariants statiques des launchers (PID exact, Caddy exact, stop flags) : **OK**.
- Smoke stack multi-processus isolé : Web + Import + Live + Analytics `services_ok=true` : **OK**.
- Arrêt par stop flags du smoke test : return code **0/0/0/0** : **OK**.
- Base métier `NELYIO_Supervision.db` restaurée exactement depuis le ZIP source après les tests.

## 7. Limites de validation

Cette session n’exécute pas Windows PowerShell 5.1, votre `caddy.exe`, ni votre PostgreSQL de production. Les scripts PowerShell sont donc contrôlés statiquement ici, mais les trois points suivants doivent être validés sur le serveur Windows réel :

1. `VERIFIER_LANCEUR_HTTPS.bat` puis deux cycles Start/Stop consécutifs;
2. `caddy validate/start/stop` avec votre binaire Caddy réel et le certificat `tls internal`;
3. préflight/index et timings des endpoints sur votre PostgreSQL avec vos données.

## 8. Recette de mise en production recommandée

1. Extraire `NELYIO_V59_1_PROD_STABLE.zip` dans un **nouveau dossier**.
2. Récupérer votre `data\postgres.env` de production sans reset/recréation de la base.
3. Fournir `caddy.exe` via racine, `tools\`, `PATH` ou `NELYIO_CADDY_EXE`.
4. Lancer `VERIFIER_LANCEUR_HTTPS.bat`.
5. Lancer `START_NELYIO_9051.bat`; vérifier `http://127.0.0.1:9051/healthz` et le build **59.1-PROD-STABLE**.
6. Vérifier `services_ok=true` et les quatre services `web/import/live/analytics=true`.
7. Importer votre `group.har`; dans Groupes vérifier que `assignment_source_available=true`, puis contrôler les agents ACTIVE d’au moins deux groupes et un agent multi-groupe.
8. Tester Qualité Agents, Qualité de service, Distributions, Support et Diagnostic sur une plage réelle lourde.
9. Lancer `START_NELYIO_HTTPS.bat`, puis tester `https://stock-manager.nelyio.local:9050/`.
10. Lancer `STOP_NELYIO_ALL.bat`; vérifier qu’aucun ancien processus Nelyio/Caddy ne conserve 9050/9051/9052.
11. Refaire immédiatement un deuxième cycle Start/Stop.
12. Si ces contrôles passent, ouvrir aux utilisateurs.
