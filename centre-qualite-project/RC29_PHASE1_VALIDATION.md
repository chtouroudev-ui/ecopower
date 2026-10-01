# RC29 — PHASE 1 — Identités

## Périmètre

Phase 1 limitée aux identités d'affichage agents/campagnes et aux chemins Live/Qualité associés.
Aucun changement de règle « A travaillé », tri, polling, performance, QoS ou attribution de groupe.

## Corrections appliquées

- Ajout de `identity_resolver.py` : résolveur commun et présentation-only.
- Agents : priorité de nom = Administration avec prénom/nom réel → nom observé Hermes/SIMPLIFY2 → nom configuré → fallback → ID technique.
- L'identifiant technique agent n'est jamais remplacé par le nom d'affichage.
- Centre Live : même règle de nom pour agents observés et non observés.
- Recherche d'appels Live : recherche désormais aussi dans le nom agent résolu.
- Aperçu campagne Live : nom agent résolu de façon identique.
- Campagnes : ID configuré prioritaire ; libellé configuré accepté seulement s'il est unique ; une ambiguïté conserve une identité `RAW:` au lieu de fusionner silencieusement.
- `live_campaigns.py` délègue sa résolution campagne au résolveur commun.
- Qualité agents et Distributions utilisent les mêmes règles d'affichage agent/campagne.
- Centre Live conserve le libellé brut `campaign` et ajoute les métadonnées `campaign_id`, `campaign_name`, `campaign_identity_quality` ; le frontend privilégie `campaign_name` pour l'affichage.

## Invariants préservés

- Groupes = files configurées + affectations ACTIVE uniquement : inchangé.
- `other` ≠ `inactive_context` : inchangé.
- inconnu ≠ zéro : aucune nouvelle conversion ajoutée.
- Live et historique restent séparés.
- Aucun calcul KPI modifié.
- Aucun calcul « A travaillé » modifié.
- Aucun moteur de tri modifié.
- Aucun timer/polling modifié.
- Aucun changement de base ou migration.

## Tests exécutés

En environnement d'audit :

`NELYIO_FORCE_SQLITE=1`
`NELYIO_SKIP_STARTUP_DETAILS_SYNC=1`
`PYTHONDONTWRITEBYTECODE=1`

Résultats :

- `rc29_phase1_identity_test.py` : 5/5 contrôles réussis.
- `live_campaigns_phase4_test.py` : 7/7 réussis.
- `live_campaigns_phase5_test.py` : 5/5 réussis.
- `quality_agent_counts_v6_test.py` : réussite ; 8 interactions agent conservées, 7 réponses Stats.INBOUND conservées.
- `group_filter_global_test.py` : réussite.
- `py_compile` sur les fichiers Python modifiés : réussite.
- `node --check` sur tous les `static/*.js` : réussite.

Un premier lancement des tests Live sans `NELYIO_FORCE_SQLITE=1` a échoué parce que l'archive active PostgreSQL et que `psycopg` n'est pas installé dans l'environnement d'audit. Ce résultat n'a pas été traité comme un défaut applicatif ; les tests ont été relancés avec le même mode SQLite d'audit que la Phase 0.

## Fichiers fonctionnels modifiés

- `identity_resolver.py` — nouveau
- `collection_store.py`
- `live_campaigns.py`
- `quality_agents.py`
- `quality_distributions.py`
- `static/live-views.js`
- `rc29_phase1_identity_test.py` — nouveau test

## Préservation

Les journaux générés lors des tests ont été restaurés depuis l'archive source.
Les fichiers WAL/SHM de l'archive ont été restaurés.
Les caches Python générés pendant les tests ont été supprimés.
Les bases de données métier ne font pas partie des différences fonctionnelles de cette phase.

**STOP — ne commence pas la Phase 2 sans validation utilisateur.**
