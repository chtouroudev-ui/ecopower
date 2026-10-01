# Nelyio-ARCH V60.5 RC13 — Phase 2 Qualité Live

## Base

RC13 dérive exclusivement de **Nelyio-ARCH V60.5 RC12**. Aucune ancienne branche n'a été utilisée comme base et aucune architecture parallèle n'a été créée.

## Objectif de cette phase

Transformer le Live en socle de qualité opérationnelle, sans refaire la supervision Hermes :

- métriques Live avec source et qualité explicites ;
- signalisation configurable ;
- code couleur configurable ;
- anti-bruit durable ;
- incidents persistants ;
- aucune invention pour les données Hermes non certifiées.

## Nouveau moteur `live_quality.py`

Le moteur construit des périmètres :

`GLOBAL → SERVICE → GROUP → CAMPAIGN → QUEUE → AGENT`

Il expose dès maintenant les mesures prouvables depuis RC12 :

- agents connus / connectés / disponibles / en appel / wrap-up / pause / offline ;
- ratios de disponibilité, appel, wrap-up et pause ;
- appels actuellement observés ;
- durée maximale d'un état, wrap-up, pause ou déconnexion ;
- fraîcheur de la dernière réponse Hermes.

Les mesures suivantes restent volontairement `unavailable` :

- `waiting_now` ;
- `oldest_waiting_seconds` ;
- `median_wait_seconds` ;
- `p90_wait_seconds` ;
- `abandon_rate` Live ;
- `qos` Live.

Elles ne deviendront exploitables qu'après certification de la sémantique des compteurs Hermes.

## Signalisation configurable

Nouvelle interface :

**Administration → Signalisation Qualité Live**

Un administrateur autorisé peut configurer :

- nom du niveau ;
- identifiant ;
- rang ;
- couleur ;
- niveau de repli ;
- activation ;
- nom de la règle ;
- périmètre ;
- cible précise facultative ;
- niveau produit ;
- conditions multiples ET / OU ;
- durée minimale ;
- durée de retour normal ;
- cooldown ;
- échantillon minimum ;
- autorisation ou non des données `partial`.

La configuration est incluse dans l'export/import global Nelyio.

## Anti-bruit

Le worker Live évalue la qualité toutes les **5 secondes**.

Un signal n'ouvre pas immédiatement un incident lorsque la règle impose une durée minimale.

Une clé logique :

`rule_id + scope_type + scope_key`

empêche la duplication : une file dégradée pendant 15 minutes produit un seul incident actif, pas une alerte à chaque cycle.

Le retour normal applique une hystérésis puis un cooldown avant de permettre un nouvel incident.

## Fiabilité

Une valeur absente n'est jamais transformée en `0`.

Si une métrique nécessaire devient indisponible ou si le Live devient périmé :

- la règle devient non évaluable ;
- aucun nouveau faux signal n'est produit ;
- un incident actif n'est pas automatiquement déclaré rétabli ;
- le statut de fiabilité des données reste séparé du statut opérationnel.

## Stockage

Aucune nouvelle base n'a été ajoutée.

- configuration niveaux/règles : base Administration existante ;
- état de règle + incidents : `Nelyio_Live.db` existante ;
- PostgreSQL métier historique : inchangé ;
- SIMPLIFY2 reste la source des KPI historiques certifiés.

## APIs ajoutées

Lecture :

- `GET /api/live/quality/config`
- `GET /api/live/incidents`

Configuration :

- `POST /api/live/quality/level`
- `POST /api/live/quality/level-delete`
- `POST /api/live/quality/rule`
- `POST /api/live/quality/rule-delete`

`GET /api/live/supervision` est enrichi par un bloc `quality` comprenant :

- statut opérationnel ;
- couleur ;
- fiabilité des données ;
- nombre d'incidents actifs ;
- incidents actifs.

## Performance

Le calcul est exécuté par **un seul worker central** et non par chaque navigateur.

Un index supplémentaire accélère la recherche du dernier état agent dans le spool Live.

Le moteur n'interroge pas PostgreSQL chaque seconde pour faire évoluer les timers.

## Validation

Suite complète :

**112 tests Python réussis / 112**

Les nouveaux tests couvrent notamment :

- donnée `waiting_now` absente ≠ zéro ;
- couleurs/niveaux/règles configurables ;
- durée minimale ;
- hystérésis ;
- cooldown ;
- absence de duplication ;
- données périmées ne provoquant pas un faux retour normal ;
- suppression volontaire de toutes les règles conservée après relecture du schéma.

La syntaxe JavaScript des nouveaux écrans a également été vérifiée avec `node --check`.

## Limite volontaire de RC13

RC13 construit le moteur et son Administration. La refonte visuelle du **Centre Qualité Live** est la Phase 3 suivante : elle consommera ces statuts, couleurs, incidents et métriques au lieu de recalculer côté frontend.

## 🟢 POINT D'ARRÊT SÛR

### FAIT

Moteur Qualité Live configurable, code couleur, règles, anti-bruit, incidents, Administration et contrat de fiabilité.

### VÉRIFIÉ

112/112 tests réussis.

### RESTANT

Phase 3 : transformer la page Supervision Live en **Centre Qualité Live** avec résumé, signaux prioritaires, campagnes/files à surveiller et drilldown.

### RISQUE MAÎTRISÉ

Les compteurs Hermes dont la sémantique n'est pas certifiée restent indisponibles et ne peuvent déclencher aucune alerte métier.

### PROCHAINE ÉTAPE

PHASE 3 — Centre Qualité Live.
