# Nelyio RC2K — Groupes ACTIVE + Moyenne appel entrant

Date : 23/09/2026

## Cause racine

Le filtre Groupe avait encore plusieurs chemins de calcul : certaines vues utilisaient les membres de files, d'autres des campagnes, et certaines conservaient le groupe administratif. De plus, le résolveur RC2J acceptait encore `partial` dans certains chemins et `analysis_groups.py` n'était pas inclus dans le manifeste de déploiement, ce qui pouvait laisser un ancien moteur lors d'une mise à jour sur place.

La colonne **Moy. appel entrant** pouvait rester vide lorsque l'enrichissement `quality_agent_facts` était absent ou incomplet sur des imports historiques, alors que les activités `Stats.AGENT` existaient déjà dans la table principale.

## Règle finale des groupes

La règle est volontairement simple et unique :

1. un groupe possède une ou plusieurs **files** (`quality_group_lines`) ;
2. les affectations agents/files viennent du dernier catalogue SIMPLIFY2 ;
3. un agent appartient au groupe uniquement s'il est affecté à au moins une file du groupe avec `activation_state = active` ;
4. `partial`, `inactive` et `unknown` sont exclus ;
5. un agent peut appartenir à plusieurs groupes s'il est ACTIVE sur des files de plusieurs groupes ;
6. `user_group_members` reste réservé à l'Administration / aux permissions et ne définit pas le périmètre analytique.

Pour les appels entrants, Stats.INBOUND ne fournit pas toujours directement l'identifiant de file. Les appels possédant un agent sont donc filtrés par les membres ACTIVE. La correspondance file → campagne n'est utilisée qu'en complément pour les appels sans agent (abandonnés, clôturés, avant file, etc.) lorsqu'elle est connue.

## Moy. appel entrant

`Moy. appel entrant` est désormais calculée directement à partir des activités `Stats.AGENT` déjà importées dont l'état correspond à **Appel entrant**, sur la période et la plage horaire sélectionnées. La compatibilité des identifiants `1001` / `S1001` est assurée.

Si un agent n'a aucune activité Appel entrant dans la sélection, la valeur reste `—` : Nelyio n'invente pas de moyenne.

## Interfaces alignées

Le résolveur commun est utilisé par Qualité de service, Qualité agents, Distributions, Support / Diagnostic, Déconnexions, Détails / Live, Analytics et Rapports. Gestion du parc applique également le groupe analytique aux utilisateurs au lieu du `groupe_id` administratif historique. Les permissions Administration ne sont pas modifiées.

## Validation sur l'export réel du 01/09/2026

- groupe de test : file 547 ;
- membres ACTIVE détectés : **5** ;
- Qualité de service avec ce groupe : **532 reçus / 530 traités** ;
- Distributions avec ce groupe : **532 reçus / 530 traités** ;
- agents affichés en Qualité agents : **90** ;
- agents avec une Moy. appel entrant calculable : **88** ;
- agents possédant des activités Appel entrant mais sans moyenne : **0** ;
- Traités global : **9 087** ;
- QoS : **81,30 %** ;
- ASA : **115,93 s** ;
- cohérence : **écart 0**.

Les 2 agents sans moyenne sur cette journée n'ont pas d'activité `Appel entrant` dans la source sélectionnée.

## Tests

- `pytest -q` : **37 passed** ;
- `quality_rc2i_test.py` sur l'export réel : **PASS** ;
- `quality_reference_20260901_test.py` : **PASS** ;
- `audit_frontend_test.js` : **PASS** ;
- benchmark synthétique : 60 000 appels / 30 jours / 50 agents, 5 vues agents concurrentes correctes.

## Fichiers métier modifiés

- `quality_scope.py`
- `analysis_groups.py`
- `quality_summary.py`
- `quality_metrics.py`
- `quality_distributions.py`
- `quality_agents.py`
- `group_workspace.py`
- `routes_inventory.py`
- `static/quality-activity.js`
- `static/quality-overview.js`
- tests de régression associés

## Important pour une mise à jour sur place

RC2K ajoute explicitement `analysis_groups.py` au `MANIFEST_PRODUCTION.json`. Une mise à jour RC2J qui n'avait pas remplacé ce fichier pouvait continuer à utiliser l'ancien comportement malgré les autres correctifs.

## Restant à vérifier sur le serveur

La recette réelle PostgreSQL/Windows/Hermes doit être rejouée avec les groupes et files de production. Les bases et historiques ne sont pas réinitialisés par cette correction.
