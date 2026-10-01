# Nelyio-ARCH V60.5 RC14 — Centre Qualité Live (Phase 3)

Base stricte : **V60.5-ARCH-RC13_LIVE_QUALITY_PHASE2**.

Cette version réalise uniquement la **PHASE 3 — Centre Qualité Live** du cahier des charges de continuité. Elle ne remplace ni Hermes/Vocalcom, ni le moteur Qualité historique, ni la hiérarchie métier existante.

## Objectif

Le Live Nelyio ne doit pas être une seconde supervision qui répète seulement « connecté / disponible / en appel ». RC14 place en premier :

- l'état Qualité Live explicable ;
- les incidents actifs et leurs preuves ;
- les métriques Live réellement certifiées ;
- les périmètres Service → Groupe → Campagne → File ;
- le contexte Qualité certifié Stats.INBOUND, clairement séparé du temps réel ;
- les agents comme preuves de drill-down, repliés par défaut.

## Ce qui change

### 1. `#live-supervision` devient **Centre Qualité Live**

Le hash et les droits restent inchangés afin de ne casser aucun favori, rôle ou route existante. Seul le contenu opérationnel évolue.

Le haut d'écran expose :

- état Qualité Live ;
- nombre d'incidents actifs ;
- nombre de règles actives ;
- fraîcheur des données ;
- état du moteur de signalisation ;
- agents connectés / disponibles / en appel / wrap-up / pause ;
- appels actuellement observés.

### 2. Aucun faux vert

`NORMAL` n'est affiché que lorsque :

- la donnée Live est fraîche ;
- le moteur de signalisation n'est pas déclaré KO ;
- au moins une règle Qualité Live est active ;
- aucune règle applicable n'est déclenchée.

Sinon l'interface affiche explicitement, selon le cas :

- `COLLECTE NON DÉMARRÉE` ;
- `EN ATTENTE DE DONNÉES` ;
- `COLLECTE INTERROMPUE` ;
- `SIGNALISATION INDISPONIBLE` ;
- `INDÉTERMINÉ`.

Un incident actif n'est pas effacé lorsqu'une donnée devient indisponible. Le dernier statut opérationnel reste visible comme contexte, mais l'état global n'est plus présenté comme confirmé.

### 3. Signaux explicables

Chaque incident visible dans le Centre Qualité Live conserve :

- niveau et couleur configurés ;
- règle déclenchée ;
- type de périmètre ;
- périmètre concerné ;
- durée ;
- métriques observées ;
- opérateur ;
- seuil ;
- source ;
- qualité de donnée.

Aucun score opaque n'est ajouté.

### 4. Périmètres Qualité Live

Une table filtrable affiche séparément :

- Services ;
- Groupes ;
- Campagnes ;
- Files.

Pour chaque ligne :

- statut ;
- nombre de règles applicables ;
- agents connectés ;
- agents disponibles ;
- agents en appel ;
- wrap-up ;
- pause ;
- appels observés ;
- nombre d'incidents.

**Campagne ≠ Groupe** reste une règle contractuelle. Une campagne est issue de l'activité observée ; un groupe reste défini par ses files configurées et ses agents ACTIVE.

### 5. Qualité maintenant

Les métriques réellement démontrées par le snapshot Hermes sont affichées normalement.

Les métriques non certifiées restent visibles mais avec la valeur **Non disponible** :

- appels actuellement en attente ;
- plus ancienne attente ;
- médiane d'attente Live ;
- P90 d'attente Live ;
- abandon Live ;
- QoS Live.

RC14 ne transforme toujours aucun `arg_n` Hermes en KPI métier sans preuve.

### 6. Contexte Qualité certifié Stats.INBOUND

Le Centre Qualité Live réutilise l'API existante `quality_pilotage` pour afficher, lorsque l'utilisateur possède le droit Qualité :

- reçus ;
- traités ;
- abandonnés ;
- taux d'abandon ;
- QoS ;
- attente moyenne ;
- P90 ;
- agents ayant traité ;
- référence historique comparable ;
- signaux historiques déjà calculés par Pilotage Qualité.

Ce bloc porte explicitement la mention **Stats.INBOUND importé — pas Live Hermes**.

Il est chargé séparément du rafraîchissement Live. Le navigateur ne le redemande pas plus d'une fois par minute ; l'Analytics worker conserve par ailleurs son cache partagé de 120 s.

### 7. Agents = preuves, pas écran principal

La table Agents Live reste présente et inchangée dans son principe, mais elle est repliée par défaut sous **Preuves agents / états Live**.

### 8. Drill-down vers Recherche Live

Les liens depuis campagnes, files et incidents réutilisent `#live-search` et son moteur existant. Le hash accepte maintenant :

- `q` ;
- `agent` ;
- `window` ;
- `reference`.

Aucun second moteur de recherche n'est créé.

## Architecture

RC14 conserve :

```text
Hermes
  ↓
collecteur central
  ↓
Nelyio_Live.db
  ↓
snapshot Live unique
  ↓
moteur Qualité central (5 s)
  ↓
/api/live/supervision
  ↓
plusieurs utilisateurs
```

Le contexte Stats.INBOUND reste séparé :

```text
SIMPLIFY2 importé
  ↓
PostgreSQL
  ↓
Analytics worker
  ↓
quality_pilotage (cache 120 s)
```

## Performance

Aucun `SELECT` n'est exécuté par campagne, file ou agent pour construire le cockpit Live. Les périmètres sont agrégés en mémoire depuis le snapshot déjà chargé.

Benchmark synthétique local RC14 :

- 114 agents ;
- 30 campagnes ;
- 60 files observées ;
- 6 groupes ;
- 2 services ;
- 100 constructions du cockpit.

Résultat observé dans le laboratoire de validation :

- médiane : **~2,8 ms** ;
- P95 : **~3,0 ms** ;
- payload `center` : **~159 KB** pour ce scénario.

Ces mesures ne remplacent pas la recette Windows/Hermes/PostgreSQL réelle.

## Fichiers principaux modifiés

- `live_quality.py`
- `static/live-views.js`
- `static/collection.css`
- `index.html`
- `VERSION.json`

Ajout :

- `live_quality_phase3_test.py`
- `docs/history/validation/PHASE3_VALIDATION_REPORT.md`
- `docs/history/releases/LIRE_NELYIO_ARCH_V60_5_RC14.md`

## Non réalisé volontairement dans cette phase

- certification `UpQuR / UpQuCB / UpQuMR / UpCaR` ;
- vraie vue Campagnes complète avec `live_now / last_15m / today / reference` dans un seul contrat backend ;
- drill-down Campagne → File → Agent → Appel complet ;
- cycle manuel incident `VU → EN INVESTIGATION → ACTION EN COURS → RÉTABLI → CLÔTURÉ` ;
- causalité automatique ;
- Redis / Kafka / nouveau microservice / nouveau framework frontend.

Ces points appartiennent aux phases suivantes.

## 🟢 POINT D'ARRÊT SÛR

### FAIT

Centre Qualité Live Phase 3 intégré à RC13 sans remplacer l'architecture existante.

### VÉRIFIÉ

- tests Phase 2 conservés ;
- nouveaux tests Phase 3 ;
- suite Python complète ;
- syntaxe JavaScript ;
- compilation Python ;
- absence de faux vert sur données périmées ;
- `0` reste distinct de `non disponible` ;
- Campagne reste distincte de Groupe ;
- absence de N+1 campagne/file/agent dans le cockpit.

### RESTANT

Phase 4 : vue Campagnes Live structurée et contrat backend agrégé.

### RISQUE MAÎTRISÉ

Les KPI de service Live non certifiés restent explicitement indisponibles et ne déclenchent aucune règle par accident.

### PROCHAINE ÉTAPE

**PHASE 4 — Campagnes à surveiller**, avec agrégation bornée, concentration par file et fenêtres `maintenant / 15 min / aujourd'hui / référence` sans rafales frontend.
