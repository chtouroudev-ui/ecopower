> **Note RC2K (23/09/2026)** : la règle finale est ACTIVE uniquement. `partial`, `inactive` et `unknown` sont exclus de l’appartenance analytique. Voir `docs/history/releases/LIRE_RC2K_GROUPES_ACTIVE_MOYENNE_APPELS.md`.

# Nelyio V56.18 MS1 — PostgreSQL RC2J GROUPES GLOBAL

## Cause racine

Le projet utilisait trois notions incompatibles de groupe selon les écrans :

- `user_group_members` : groupe administratif unique ;
- `quality_group_campaigns` : campagnes liées manuellement ;
- `quality_group_lines` : files réelles du groupe.

Cela cassait les filtres dès qu’un agent appartenait à plusieurs files/groupes ou lorsqu’une campagne n’était pas liée manuellement.

## Correction

Le périmètre analytique est maintenant unique :

`Groupe -> files configurées -> affectations agents ACTIVE + campagnes observées sur ces files`.

Les groupes administratifs restent utilisés uniquement pour les droits/annuaire. Un agent peut appartenir à plusieurs groupes analytiques simultanément.

Interfaces alignées : Qualité de service, Qualité agents, Distributions, Support/Diagnostic, Déconnexions, Détails/Live, Analytics et Rapports.

## Validation

- `pytest -q` : **36 passed** ;
- `node audit_frontend_test.js` : **PASS** ;
- référence 01/09/2026 : Reçus **12 115**, Traités **9 087**, QoS **81,30 %**, ASA **115,93 s**, cohérence **0** ;
- test multi-groupes : un même agent présent dans deux groupes reste visible avec chacun des deux filtres ;
- test Distributions : le catalogue groupe vient des files, pas des campagnes manuelles.

## Fichiers modifiés / ajoutés

- `analysis_groups.py` (nouveau résolveur global)
- `quality_scope.py`
- `quality_summary.py`
- `agent_directory.py`
- `disconnects.py`
- `support_views.py`
- `collection_views.py`
- `report_data.py`
- `unified_filters.py`
- `details_store.py`
- `group_filter_global_test.py`

## Important

Aucune base n’est réinitialisée. Les permissions ne changent pas. Le correctif concerne uniquement la définition analytique des groupes.
