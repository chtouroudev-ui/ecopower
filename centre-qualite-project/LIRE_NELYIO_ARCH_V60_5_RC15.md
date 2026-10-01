# Nelyio-ARCH V60.5 RC15 — Campagnes à surveiller (Phase 4)

Base stricte : **V60.5-ARCH-RC14_LIVE_QUALITY_CENTER_PHASE3**.

Cette version réalise la **PHASE 4 — Campagnes à surveiller** du cahier des charges. Elle ne remplace ni le Centre Qualité Live, ni Hermes/Vocalcom, ni Stats.INBOUND, ni le modèle de groupes existant.

## Objectif

Donner au superviseur une vue campagne exploitable pour répondre rapidement à :

- quelle campagne concentre la charge ;
- sur quelles files ;
- quelle couverture agent est réellement disponible ;
- ce qui se passe maintenant ;
- ce qui s'est passé sur les 15 dernières minutes ;
- le cumul d'aujourd'hui ;
- la référence comparable ;
- si le volume ou la concentration sont inhabituels ;
- quelles files, agents et appels ouvrir ensuite.

## Contrat de sources

RC15 sépare explicitement les fenêtres :

### `live_now`

Source : **Hermes Live + configuration files/agents**.

Contient notamment :

- agents configurés ;
- agents ACTIVE sur les files de la campagne ;
- connectés ;
- disponibles ;
- en appel ;
- wrap-up ;
- pause ;
- appels actuellement observés ;
- statut Qualité Live / incidents.

Les métriques Hermes non certifiées restent `unavailable`, en particulier :

- `waiting_now` ;
- `oldest_waiting_seconds` ;
- médiane/P90 attente réellement Live ;
- abandon réellement Live ;
- QoS réellement Live.

### `last_15m`

Source : **Stats.INBOUND importé** sur la tranche disponible des 15 dernières minutes.

Cette fenêtre est présentée comme historique/importée, jamais comme un compteur instantané Hermes.

### `today`

Source : **Stats.INBOUND importé** entre l'ouverture métier et l'heure courante.

### `reference`

Source : médiane de jours comparables de **Stats.INBOUND**, jusqu'à quatre mêmes jours de semaine lorsque les données existent.

### Distribution par file

Source : **ODCalls.FirstQueue**.

Cette relation sert uniquement à expliquer la répartition et la concentration du trafic par file. Elle ne remplace pas Stats.INBOUND comme source officielle de la Qualité de service.

## Campagne ≠ Groupe

RC15 conserve strictement la règle :

```text
GROUPE = files configurées -> agents ACTIVE
CAMPAGNE = dimension d'activité issue des appels / Hermes / SIMPLIFY2
```

Une campagne peut toucher plusieurs files et plusieurs groupes. Le backend expose séparément `service`, `groups` et `queues` au lieu de déduire artificiellement `Campagne = Groupe`.

## Couverture agents

Pour une campagne :

- **configurés** = agents affectés à au moins une file configurée de la campagne, quel que soit l'état d'activation ;
- **ACTIVE sur files** = union des agents ACTIVE sur ces files ;
- un agent ACTIVE sur 3 files de la même campagne compte **une seule fois** ;
- connectés/disponibles/en appel/wrap/pause sont mesurés sur cette couverture lorsque la cartographie est connue.

## Concentration par file

La vue indique :

- nombre de files configurées ;
- files actives ;
- files avec appels ;
- files avec agents ACTIVE ;
- files sous tension ;
- part du volume par file ;
- file principale et pourcentage de concentration.

Le cas de référence **72 % du trafic sur une file** est couvert par un test métier dédié.

Le détail d'une campagne affiche aussi pour chaque file principale :

- statut Qualité Live ;
- reçus ;
- part de campagne ;
- traités ;
- abandonnés ;
- agents ACTIVE ;
- connectés ;
- disponibles ;
- agents ayant traité dans la fenêtre historique.

## Fiabilité des données

RC15 conserve la règle `0 != donnée absente`.

Exemples :

- si `waiting_now` n'est pas certifié, `value=null`, `quality=unavailable` ;
- si une campagne est absente des données importées sur les 15 dernières minutes et que la couverture de cette tranche n'est pas démontrée, elle n'est pas transformée automatiquement en zéro ;
- si Analytics/PostgreSQL est temporairement indisponible, le cockpit **Live continue à fonctionner** et les fenêtres historiques deviennent explicitement `unavailable` avec `reason=analytics_unavailable`.

## API

Nouvelle route :

```text
GET /api/live/campaigns
```

Le frontend ne recalcule pas les agrégats métier. Le backend renvoie un payload prêt à afficher avec :

- `generated_at` ;
- `windows.live_now` ;
- `windows.last_15m` ;
- `windows.today` ;
- `windows.reference` ;
- `campaigns[]` ;
- plan de requêtes borné ;
- source/qualité/raison sur les valeurs importantes.

La partie historique est calculée par l'Analytics worker lorsque les services externes sont actifs et mise en cache. Le snapshot Live reste fourni par le service Live central.

## Performance / absence de N+1

Le backend ne fait pas :

```text
for campaign: SELECT ...
for queue: SELECT ...
for agent: SELECT ...
```

Les données historiques sont agrégées en batch. Le plan historique reste borné indépendamment du nombre de campagnes :

- Stats.INBOUND : nombre fixe de fenêtres/jours de référence ;
- ODCalls/FirstQueue : deux agrégations de distribution ;
- configuration/groupes : chargés globalement ;
- Live : un snapshot central déjà existant.

Benchmark synthétique local Phase 4 :

- 12 000 appels/jour ;
- 5 jours de contexte ;
- 30 campagnes ;
- 60 000 lignes Stats.INBOUND synthétiques ;
- 12 000 appels ODCalls cible.

Résultat observé dans le laboratoire SQLite isolé :

- médiane : **~0,35 s** ;
- P95 : **~0,37 s** ;
- 30 campagnes agrégées ;
- nombre de SELECT observé constant dans le scénario, sans croissance par campagne.

Ces mesures sont indicatives et ne remplacent pas la recette PostgreSQL/Windows réelle.

## Interface

Le menu LIVE contient maintenant :

- Centre Qualité Live ;
- **Campagnes à surveiller** ;
- Recherche d'appels Live.

La vue Campagnes possède :

- recherche ;
- filtre Service ;
- filtre Groupe ;
- filtre Statut ;
- filtre « incidents uniquement » ;
- tableau résumé ;
- détail repliable par campagne ;
- cartes Maintenant / 15 min / Aujourd'hui / Référence ;
- concentration par file ;
- liens vers Recherche Live et Pilotage Qualité.

## Fichiers principaux modifiés

- `quality_scope.py`
- `analytics_service.py`
- `analytics_rpc.py`
- `routes_collection.py`
- `http_handler.py`
- `static/live-views.js`
- `static/app.js`
- `static/collection.css`
- `index.html`

Ajouts :

- `live_campaigns.py`
- `live_campaigns_phase4_test.py`
- `live_campaigns_phase4_benchmark.py`
- `PHASE4_VALIDATION_REPORT.md`
- `LIRE_NELYIO_ARCH_V60_5_RC15.md`

## Non réalisé volontairement dans cette phase

- certification des compteurs d'attente Hermes `UpQuR/UpQuCB/UpQuMR/UpCaR` ;
- drill-down complet Campagne -> File -> Agent -> Appel dans une seule réponse bornée (Phase 5) ;
- timeline enrichie par campagne/file ;
- cycle manuel complet des incidents ;
- causalité automatique ;
- nouveau microservice, Redis, Kafka ou framework frontend.

## 🟢 POINT D'ARRÊT SÛR

RC15 constitue le point d'arrêt de la Phase 4 avant le drill-down complet de Phase 5.
