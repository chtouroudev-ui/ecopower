# Nelyio V60.5-ARCH-RC2 — Rapport de finalisation

Date : 25/09/2026

## AUDIT INITIAL

Base retenue : **Nelyio-ARCH**, identifiée comme la version la plus récente et stable fournie par l'utilisateur. Les anciennes branches V60.4/V3/V4/V5 ont servi uniquement de références de logique ; elles n'ont pas remplacé l'architecture ARCH.

Architecture trouvée :

- Web/API séparé ;
- worker Analytics loopback ;
- service Live séparé ;
- Importer manuel séparé ;
- PostgreSQL comme persistance de production ;
- `Nelyio_Live.db` comme spool opérationnel Live local SQLite/WAL ;
- `Nelyio_Services.db` pour l'état/heartbeat des services.

L'archive de départ compilait et passait 69 tests. Les anciennes lenteurs monolithiques ne se reproduisent pas de la même manière sur ARCH.

## FAIT

### Modèle métier

- ajout non destructif du service parent configurable des groupes (`service_name`) ;
- aucune attribution MEDICAL/IMAGERIE inventée ;
- maintien de la règle Groupe -> files -> agents ACTIVE ;
- agents multi-groupes conservés ;
- service propagé aux scopes/filtres/export-import de configuration.

### Pilotage Qualité

Ajout de **Analytiques > Pilotage Qualité** :

- Aujourd'hui ;
- Analyse ;
- Actions ;
- Évolution ;
- baselines même jour de semaine ;
- médiane/références comparables ;
- volume minimum ;
- 3 à 5 signaux maximum ;
- faits/hypothèses séparés ;
- améliorations observées ;
- actions traçables ;
- comparaison avant/après sans affirmer de causalité ;
- respect Policies/Déclarations ;
- signaux globaux calculés indépendamment par service parent.

### Appels suspects

Ajout de **Analytiques > Appels suspects** :

- appels < 10 s ;
- appels >=10 s suspects ;
- attente initiale >=30 % ;
- attente initiale >=50 % ;
- fin par agent prouvée ;
- origine de fin indéterminée si non prouvée ;
- indices techniques ;
- filtres service/groupe/file/agent/campagne/période ;
- détail d'appel ;
- ANI selon permission ;
- appels exclus statistiquement annotés sans supprimer la preuve.

`Appels < 10 s` est retiré de Qualité agents pour éviter la double logique métier.

### Enrichissement ODCalls

Ajout de `phone_call_details`, sans casser la table historique `phone_calls` :

- CallDuration ;
- WaitDuration ;
- TotalWaitDuration ;
- FirstQueue / LastQueue ;
- FirstCampaign / LastCampaign ;
- LastTransfer.

Re-import idempotent : une archive déjà connue peut enrichir les détails manquants sans dupliquer les appels.

### Live

Création/consolidation de l'univers LIVE :

- Supervision Live ;
- Recherche d'appels Live ;
- Collecteur Live conservé dans Administration ;
- timers incrémentés côté navigateur ;
- référence Live explicitement distincte d'un Call ID ;
- santé Live basée sur session + fraîcheur Hermes + worker ;
- worker arrêté -> compteurs gelés + Collecte interrompue ;
- permission ANI séparée ;
- diagnostic administrateur Live.

### Historisation Live factuelle

Ajout de `live_call_observation_history` :

- observations finalisées uniquement ;
- idempotence par clé Live stable ;
- aucun ANI ;
- aucun faux Call ID ;
- aucune attente/conversation inventée ;
- aucune alimentation automatique des KPI historiques ;
- purge différée si la persistance n'a pas réussi.

## ARCHITECTURE RETENUE

```text
Hermes / Hermes360
        |
        v
Collecteur Live unique
        |
        v
Nelyio_Live.db (spool courant SQLite/WAL)
        |                     \
        |                      -> Supervision Live / Recherche Live
        v
observations finalisées
        |
        v
live_call_observation_history (PostgreSQL supervision)
        |
        `-> preuve technique uniquement

SIMPLIFY2 exports
        |
        v
Importer
        |
        v
PostgreSQL
  |        |        |
Qualité  ODCalls  Stats.AGENT
  |        |        |
  +--------+--------+
           |
           v
Pilotage / Appels suspects / Historique
```

Le Live et l'historique analytique restent isolés. Une panne PostgreSQL n'empêche pas le spool Live de recevoir les données ; une observation non persistée empêche sa purge silencieuse.

## DONNÉES

Voir `NELYIO_DATA_DICTIONARY.md`.

Validation sur l'export réel `SIMPLIFY2 2026-09-21` :

- 15 507 appels ODCalls ;
- 15 507 détails enrichis ;
- 14 619 appels entrants Stats.INBOUND ;
- premier import laboratoire : ~9,24 s ;
- re-import identique : ~0,04 s ;
- aucun doublon créé.

Sur 08:00–19:00, Appels suspects :

- total suspects : 7 943 ;
- <10 s : 1 874 ;
- >=10 s suspects : 6 069 ;
- attente >=30 % : 6 073 ;
- attente >=50 % : 4 497 ;
- fin par agent confirmée : 3 499 ;
- fin par appelant confirmée : 0 ;
- signal technique sur cet export : 0.

Pilotage sur ce fichier unique :

- reçus : 14 568 ;
- traités par agent : 10 952 ;
- abandonnés : 1 534 ;
- QoS : 87,4621 % ;
- baseline : données insuffisantes, comportement attendu avec une seule journée.

Qualité agents RC2 sur la même fenêtre 08:00–19:00 :

- interactions traitées Stats.AGENT / SessionID : **11 051** ;
- lignes finales attribuées Stats.INBOUND : **10 952** ;
- écart : **+99 interactions agent**, attendu notamment lors des transferts ;
- 37 couples agent/campagne diffèrent, concernant 25 agents et 25 campagnes ;
- la QoS globale ci-dessus reste inchangée car elle continue à utiliser la source service `Stats.INBOUND`.

Un test permanent reproduit aussi le cas fonctionnel V6 : 8 sessions `Inbound call` côté Stats.AGENT contre 7 records finaux Stats.INBOUND donnent bien **8 Appels traités** dans Qualité agents, tout en conservant 7 pour les indicateurs Stats.INBOUND.

## RÈGLES MÉTIER

- MEDICAL / IMAGERIE : services parents indépendants ;
- groupes : files configurées -> agents ACTIVE ;
- campagne : dimension analytique, pas substitut du groupe ;
- QoS : formule actuelle validée, centralisée dans `quality_rules.py` ;
- appels suspects : règles explicites ;
- fin appelant : jamais déduite de `EndByAgent=0` ;
- Policies/Déclarations : exclusions respectées dans les KPI, preuve brute conservée ;
- ANI : permission indépendante ;
- Live : observation factuelle, jamais promue en appel historique certifié sans import source.

## POSTGRESQL

Nouvelles/évolutions principales :

- `admin.user_groups.service_name` ;
- `admin.quality_actions` ;
- `supervision.phone_call_details` ;
- `supervision.live_call_observation_history` ;
- index associés ;
- préflight PostgreSQL mis à jour pour contrôler la nouvelle table d'historique Live.

Le spool `Nelyio_Live.db` reste SQLite local et gagne `collection_call_history_sync` pour l'accusé de persistance.

Aucun reset de base n'est requis : les migrations sont additives/idempotentes.

## API

Principales routes ajoutées/consolidées :

- `GET /api/quality/pilotage` ;
- `GET /api/quality/actions` ;
- `POST /api/quality/action/save` ;
- `GET /api/quality/action-compare` ;
- `GET /api/quality/suspicious-calls` ;
- `GET /api/live/supervision` ;
- `GET /api/live/search` ;
- `GET /api/live/diagnostic`.

Les analyses lourdes passent par le worker Analytics ; elles ne sont pas réintroduites dans le processus Web.

## PERFORMANCE

Benchmark laboratoire, export réel 21/09/2026, 5 lectures concurrentes, 8 tours :

- Supervision Live 1 : médiane 5,17 ms ;
- Supervision Live 2 : médiane 4,45 ms ;
- Recherche Live 1 : médiane 3,58 ms ;
- Recherche Live 2 : médiane 5,45 ms ;
- Pilotage Qualité : médiane 254,9 ms, max 293,46 ms ;
- tour concurrent complet : médiane 257,43 ms, max 296,39 ms.

**Limite :** benchmark direct fonctions + SQLite laboratoire, sans HTTP/TLS et sans PostgreSQL. Il prouve l'absence de contention évidente dans cette configuration, pas la performance finale du serveur de production.

## TESTS

État du candidat :

- 91/91 tests Python ;
- 18/18 fichiers JavaScript valides (`node --check`) ;
- compilation Python complète ;
- replay réel SIMPLIFY2 21/09 ;
- re-import idempotent ;
- test V6 Qualité agents : 8 interactions Stats.AGENT vs 7 records Stats.INBOUND ;
- tests Service parent ;
- tests Pilotage / baseline / per-service ;
- tests Actions / avant-après ;
- tests Appels suspects ;
- tests ANI ;
- tests Policies/Déclarations ;
- tests Live worker stale/down ;
- tests historique Live idempotent ;
- test panne base historique sans perte du spool ;
- test purge différée puis autorisée après persistance ;
- benchmark 5 lecteurs simultanés en laboratoire.

## LIMITATIONS

- aucun serveur PostgreSQL de production n'était disponible dans cet environnement pour `EXPLAIN ANALYZE` réel et test de charge ;
- aucun test Caddy/TLS/réseau réel ;
- une seule journée SIMPLIFY2 a servi à la validation finale des nouveaux écrans, donc aucune baseline historique réelle ne pouvait être produite ;
- l'origine « fin par appelant » reste indisponible sans preuve source ;
- le nombre de navigateurs Live connectés n'est pas mesuré par le polling actuel ;
- les compteurs Hermes non documentés ne sont pas convertis en attente patient certifiée.

## RISQUES RESTANTS

1. Valider le préflight/migrations sur une copie PostgreSQL de production.
2. Mesurer les nouvelles requêtes Pilotage/Appels suspects sur le volume PostgreSQL réel avec `EXPLAIN ANALYZE`.
3. Tester 5 utilisateurs via HTTPS/Caddy, pas seulement au niveau fonctions.
4. Valider une capture Hermes complète couvrant le cycle d'appel pour documenter davantage les compteurs Live.
5. Renseigner explicitement le service parent des groupes existants ; aucune migration ne devine MEDICAL/IMAGERIE.

## FICHIERS MODIFIÉS PRINCIPAUX

Backend / données :

- `analysis_groups.py`
- `analytics_rpc.py`
- `analytics_service.py`
- `app_config.py`
- `app_db.py`
- `auth_service.py`
- `calls.py`
- `collection_calls.py`
- `collection_store.py`
- `export_import.py`
- `group_workspace.py`
- `http_handler.py`
- `import_workflow.py`
- `live_service.py`
- `pilotage_quality.py` (nouveau)
- `postgres_migrate.py`
- `postgres_runtime_preflight.py`
- `quality_agents.py`
- `quality_distributions.py`
- `quality_metrics.py`
- `quality_scope.py`
- `quality_summary.py`
- `retention_service.py`
- `routes_admin_config.py`
- `routes_collection.py`
- `routes_quality.py`
- `supervision_db.py`
- `supervision_routes.py`
- `suspicious_calls.py` (nouveau)

Frontend :

- `index.html`
- `static/app.js`
- `static/collection.css`
- `static/collection.js`
- `static/groups.js`
- `static/live-views.js` (nouveau)
- `static/pilotage-quality.js` (nouveau)
- `static/quality-activity.js`
- `static/quality-distributions.js`
- `static/quality-overview.js`
- `static/quality.css`
- `static/support.js`
- `static/suspicious-calls.js` (nouveau)

Tests / version :

- `audit_regression_test.py`
- `quality_agent_counts_v6_test.py` (nouveau, régression 8 vs 7)
- `v60_2_regression_test.py`
- `v60_4_regression_test.py` (cache-buster rendu compatible avec les versions ultérieures)
- `VERSION.json`

Les bases métier de laboratoire et les logs de test ne font pas partie des modifications livrées.

## RESTE À FAIRE

Avant bascule production :

1. sauvegarde PostgreSQL ;
2. installer le candidat sur une copie/recette ;
3. lancer le préflight PostgreSQL avec réparation additive ;
4. affecter les services parents aux groupes ;
5. importer plusieurs semaines afin de valider les baselines ;
6. rejouer les tests de cohérence Qualité ;
7. lancer le benchmark HTTP/HTTPS 5 utilisateurs ;
8. vérifier le Live pendant un cycle réel d'appel ;
9. seulement après ces contrôles, remplacer la version production.

## VERDICT TECHNIQUE DU CANDIDAT

Le candidat satisfait les grands axes fonctionnels du prompt maître sans remplacer l'architecture Nelyio-ARCH ni inventer de données. Il est **prêt pour validation de recette/production**, mais n'est pas déclaré « validé production » tant que PostgreSQL + HTTPS + charge réelle n'ont pas été testés sur l'environnement cible.

## Addendum RC4 — Taille WAV / contenu faible

Le second HAR Hermes a permis de valider une source fiable de taille média : `folder_info` sur `RECORD/*.wav` renvoie `Name` et `Size`. Le nom suit `Agent#Date#Heure#Indice.wav` et l'Indice rejoint directement les appels Nelyio.

RC4 ajoute :

- table `call_recordings` ;
- synchronisation automatique depuis la session Edge authentifiée ;
- import HAR de secours ;
- densité média octets/seconde ;
- catégorie Appels suspects `Contenu faible / size anormal` ;
- exclusions strictes des hold, transferts, consultations, reroutages et appels multi-WAV.

Validation du HAR utilisateur : 186 WAV / 41 jours / 12 agents. Aucun audio n'a été téléchargé.


## V60.5 ARCH RC8 — Enregistrements Hermes multi-racines

Validation terrain RC7 : le clic réel sur le 18/09/2026 renvoie 93 dossiers agents mais seulement 6 WAV dans la racine ancrée, alors que la fenêtre Hermes affiche plusieurs racines cabinet de premier niveau. RC8 ne considère plus la racine du clic comme l’ensemble du stockage RECORD. Il découvre toutes les racines cabinet chargées dans la fenêtre Enregistrements, puis parcourt automatiquement `racine -> année -> mois -> jour -> agent -> WAV`.

Le clic utilisateur reste limité à une seule ouverture du jour demandé pour ancrer la session authentifiée. Aucun cabinet, agent ou WAV n’a besoin d’être ouvert manuellement. Le résultat expose séparément le nombre de racines détectées, les racines avec WAV, les dossiers agents parcourus et le total des WAV.

La régression locale complète passe à **100/100 tests Python**. Le test terrain Hermes du 18/09 reste à rejouer sur la session réelle après installation RC8.

## V60.5 ARCH RC10 — Historique complet / Indice + Size uniquement

RC10 simplifie le contrat d'enregistrement conformément à la validation métier : seule la jointure **Indice -> Size** est utile à Appels suspects. La table active devient `call_recording_sizes(indice, size_bytes)` et les nouvelles synchronisations n'enregistrent plus nom WAV, agent, date, heure, chemin ni racine SDA/campagne. Ces éléments restent transitoires en mémoire uniquement pour parcourir Hermes.

Le synchroniseur ajoute un mode **TOUT l'historique**. À partir de la fenêtre Enregistrements laissée au niveau SDA/campagne, Nelyio découvre automatiquement toutes les racines, leurs années, mois et jours, puis parcourt les dossiers agents et les WAV sans télécharger l'audio. Les WAV partageant le même Indice sont dédoublonnés par nom pendant le crawl puis leurs tailles sont additionnées avant persistance.

Une reprise par journée est conservée dans `data/recording_size_sync_state.json` afin qu'une synchronisation interrompue ne recommence pas tout l'historique. Ce fichier est un état technique de progression ; il ne contient aucune donnée d'appel. Les jours récents sont rescannés pour récupérer les enregistrements arrivés tardivement.

Compatibilité : les données RC4-RC9 déjà présentes dans `call_recordings` sont agrégées une fois vers `call_recording_sizes`. Appels suspects lit ensuite uniquement la nouvelle table. Le signal « contenu faible » continue d'exclure les mises en attente ainsi que les transferts/consultations/reroutages certifiés.

Validation locale RC10 : **104/104 tests Python**. Le HAR utilisateur réel contient 185 WAV exploitables (l'Indice 0 est ignoré) agrégés en 182 Indices uniques ; la table résultante possède exactement les colonnes `indice`, `size_bytes`.

## RC11 - Correctif Size sans conversation

Le signal `Contenu faible / size` exige desormais `ConvDuration > 0`. La densite est calculee uniquement comme `Size / ConvDuration`; `CallDuration` ne sert plus de fallback. Si `Conversation = 0 s`, l appel est considere non analysable par Size et aucun motif Size n est genere.


## RC12 - Size Hermes vérifié

RC12 invalide les anciennes tailles non vérifiées et reconstruit `Indice -> Size` uniquement à partir de WAV Hermes dont l'Indice correspond à un appel SIMPLIFY2 unique, sur la même journée de référence, avec `Conversation > 0` et un agent cohérent. Les métadonnées de validation (nom WAV, date, agent, chemin) restent transitoires et ne sont pas persistées. Appels suspects n'affiche le Size que si cette validation est acquise.
