# RC29 — PHASE 3 — Signalisation Qualité Live

Date : 28 septembre 2026
Base de travail : copie de `Nelyio-ARCH_RC29_PHASE2_LIVE_TRI.zip`

## Périmètre appliqué

Phase 3 uniquement. Aucun travail des phases suivantes n'a été anticipé.

### Règles et cibles
- Types de cible conservés : `GLOBAL`, `SERVICE`, `GROUP`, `CAMPAIGN`, `QUEUE`, `AGENT`.
- Multi-cibles conservé et validé.
- Logiques `ALL` / `ANY` conservées et validées.
- Anti-bruit conservé : `min_duration_seconds`, `recovery_seconds`, `cooldown_seconds`, `min_sample_size`, `allow_partial`.
- Les valeurs absentes ou non fiables ne sont jamais converties en zéro pour déclencher une alerte.

### inactive_context
- Ajout d'un état Live distinct `inactive_context`.
- `inactive_context` n'est produit que pour des libellés Hermes explicites : `Aucun contexte démarré`, `Contexte inactif`, `Inactive context` (et variante sans accent).
- `Unknown state`, `Sonnerie` et tout autre état non reconnu restent `other`.
- `other` n'est donc jamais réinterprété comme `inactive_context`.
- Nouvelles métriques Live :
  - `agents_inactive_context`
  - `inactive_context_percent`
  - `max_inactive_context_seconds`

### Agents non observés
- Un agent configuré mais absent du Live reste `Non observé`.
- Il n'est jamais transformé en offline, pause ou contexte inactif.
- Pour un périmètre configuré sans observation Live, les métriques d'état restent indisponibles (`null`) et non zéro.

### Presets Phase 3
Les presets sont exposés comme modèles et ne sont jamais créés silencieusement :
1. Pause longue
2. Post-appel long
3. Contexte inactif long
4. Déconnexion prolongée
5. Aucun disponible
6. Trop d'agents en pause
7. Trop d'agents en contexte inactif

Les seuils et cibles restent modifiables avant enregistrement.

### Modes UI
- Mode **Simple** : presets guidés + règles compactes.
- Mode **Avancé** : configuration complète, niveaux/couleurs, conditions, ALL/ANY et anti-bruit.
- Le mode est mémorisé dans `sessionStorage`.

### Incidents agrégés
- Les incidents stockent maintenant les agents contributeurs réellement observés.
- Les contributeurs incluent : ID agent, nom affiché, état Hermes, `kind`, âge de l'état, campagne et file.
- Aucune identité d'agent non observé n'est inventée dans cette liste.
- Le Centre Live et le détail Incident affichent ces contributeurs.

## Compatibilité / stockage

La migration Live est additive : ajout de `contributor_agents_json` à `live_quality_incidents` uniquement lorsqu'il manque.

Aucune base livrée n'a été modifiée dans l'archive finale. Hashes Phase 2 = Phase 3 :

- `Nelyio_Live.db` : `39d57c0bc3d2448add32e651b8f3e905900aeee3537bc0c22c18b007b8288186`
- `Nelyio_Services.db` : `8cfab256b675709de4bb2a899024e04aca2e09b581b3bbe5db266afac7a6dd2d`
- `Nelyio_Details.db` : `859947ff7912879caa06cf06b22c2f06e624b4723ed25f2c7cc6dbe9c2455610`
- `TECHIN_Stock_Manager.db` : `52c511ce7dfe269fa33e6e405065595da65fc7b02c0a66915bd948c0e59d8cfc`

## Fichiers fonctionnels modifiés

- `supervision_utils.py`
- `collection_store.py`
- `live_quality.py`
- `static/live-quality-admin.js`
- `static/live-views.js`
- `static/collection.css`

Ajout :
- `rc29_phase3_signalisation_test.py`
- `RC29_PHASE3_VALIDATION.md`

## Tests exécutés

### Phase 3 + moteur anti-bruit existant
Commande :

`python -m pytest -q -p no:cacheprovider rc29_phase3_signalisation_test.py live_quality_phase2_test.py`

Résultat : **13 tests réussis**.

Cela couvre notamment :
- `other` != `inactive_context`
- métriques contexte inactif
- configuré mais non observé
- presets et modes
- multi-cibles
- `ALL` / `ANY`
- `allow_partial`
- agents contributeurs
- `min_duration_seconds`
- `recovery_seconds`
- `cooldown_seconds`
- absence de doublon incident
- données indisponibles ne provoquant pas une récupération automatique

### Régressions Phase 1 / Phase 2 / Live
Commande exécutée sur une copie de test isolée :

`python -m pytest -q -p no:cacheprovider rc29_phase3_signalisation_test.py live_quality_phase2_test.py rc29_phase1_identity_test.py rc29_phase2_live_test.py group_filter_global_test.py live_campaigns_phase4_test.py live_campaigns_phase5_test.py live_quality_phase3_test.py live_quality_phase6_test.py`

Résultat : **48 tests réussis**.

### JavaScript
`node --check` sur tous les fichiers `static/*.js` : **0 erreur de syntaxe**.

### Test historique non aligné avec RC29
`audit_regression_test.py::test_source_totals_filters_and_distribution` attend encore l'ancienne QoS (~66,67 %) fondée sur une formule historique. Depuis la Phase 2 validée, la QoS Nelyio est `traités / (traités + abandonnés)` ; sur la fixture de ce test le résultat RC29 est donc **50 %**. Ce test historique n'a pas été modifié pendant la Phase 3.

## Éléments non modifiés

- définition de « A travaillé »
- tri Phase 2
- polling / DOM incrémental Phase 2
- formule QoS Phase 2
- logique des groupes/files ACTIVE
- imports historiques
- PostgreSQL
- données métiers de production

## Conclusion

La Signalisation Qualité Live dispose maintenant d'une taxonomie stricte, de presets guidés, de modes simple/avancé, d'un anti-bruit testé, de cibles multiples et d'incidents agrégés explicables par les agents contributeurs observés.

**STOP — ne pas commencer la Phase 4 sans validation utilisateur.**
