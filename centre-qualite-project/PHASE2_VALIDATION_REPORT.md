# Nelyio-ARCH V60.5 RC13 — Rapport de validation Phase 2

## Base vérifiée

- Base officielle : Nelyio-ARCH V60.5 RC12.
- RC13 est une évolution ciblée de RC12 ; aucune ancienne branche n'a été utilisée comme base.
- Les bases métier livrées sont reprises depuis RC12 proprement, sans données créées par les tests.

## Fonctionnalités Phase 2

- moteur central `live_quality.py` ;
- niveaux, rangs, libellés et couleurs configurables ;
- règles GLOBAL / SERVICE / GROUP / CAMPAIGN / QUEUE / AGENT ;
- conditions multiples AND / OR ;
- durée minimale, hystérésis de retour et cooldown ;
- incidents persistants et dédupliqués dans `Nelyio_Live.db` ;
- évaluation centralisée par le Live worker toutes les 5 secondes ;
- fiabilité des métriques `reliable / partial / unavailable` ;
- séparation statut opérationnel / état de la collecte ;
- interface Administration `Signalisation Qualité Live` ;
- export/import de la configuration Live Quality ;
- APIs de lecture et configuration avec les permissions Nelyio existantes.

## Garde-fous métier

- une valeur Live absente n'est jamais convertie en zéro ;
- `waiting_now`, `oldest_waiting_seconds`, médiane/P90 attente, abandon et QoS Live restent indisponibles tant que la sémantique Hermes n'est pas certifiée ;
- une donnée périmée n'ouvre pas un faux incident ;
- une donnée devenue indisponible ne clôture pas automatiquement un incident actif ;
- une règle + un périmètre ne peut produire qu'un seul incident actif ;
- la suppression volontaire de toutes les règles n'entraîne pas leur recréation au redémarrage.

## Validation automatisée

Commande exécutée sur une arborescence reconstruite depuis RC12 propre puis patchée avec RC13 :

`python -m pytest -q`

Résultat :

**112 passed**

Contrôles complémentaires :

- `python -m compileall -q .` : OK ;
- `node --check static/live-quality-admin.js` : OK ;
- `node --check static/app.js` : OK.

## Nouveaux tests Phase 2

`live_quality_phase2_test.py` couvre notamment :

1. `waiting_now` indisponible n'est jamais interprété comme `0` ;
2. niveaux/couleurs/règles configurables ;
3. durée minimale + hystérésis + cooldown + absence de duplication ;
4. séparation qualité opérationnelle / qualité de données ;
5. données périmées ou indisponibles sans faux retour à la normale ;
6. suppression volontaire de toutes les règles conservée.

## Fichiers principaux ajoutés

- `live_quality.py`
- `live_quality_phase2_test.py`
- `static/live-quality-admin.js`
- `LIRE_NELYIO_ARCH_V60_5_RC13.md`
- `PHASE2_VALIDATION_REPORT.md`

## Fichiers principaux étendus

- `collection_store.py`
- `live_service.py`
- `routes_collection.py`
- `http_handler.py`
- `routes_admin_config.py`
- `app_db.py`
- `postgres_runtime_preflight.py`
- `static/app.js`
- `static/collection.css`
- `index.html`
- `VERSION.json`

## Limite volontaire

La Phase 2 met en place le moteur et la configuration. La Phase 3 doit maintenant transformer `Supervision Live` en véritable **Centre Qualité Live** consommant ces métriques, statuts, couleurs et incidents, avec campagnes/files à surveiller et drilldown.

## 🟢 POINT D'ARRÊT SÛR

- FAIT : moteur Qualité Live configurable et persistant.
- VÉRIFIÉ : 112/112 tests.
- RESTANT : Centre Qualité Live et visualisation opérationnelle Phase 3.
- RISQUE MAÎTRISÉ : aucun KPI Hermes non certifié n'est inventé.
- PROCHAINE ÉTAPE : PHASE 3 — Centre Qualité Live.
