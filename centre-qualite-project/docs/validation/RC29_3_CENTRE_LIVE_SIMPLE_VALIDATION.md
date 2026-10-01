# RC29.3 — Centre Qualité Live simplifié

## Objectif
Réduire l'encombrement du Centre Qualité Live et privilégier une supervision immédiate, sans modifier les KPI, la QoS, les périmètres ou les règles métier.

## Nouvelle disposition desktop
- **Agents** est la vue par défaut et occupe l'espace principal.
- **Campagnes / périmètres** devient une vue alternative dans le même espace.
- **Double vue** reste disponible lorsque la corrélation simultanée est nécessaire.
- Statut Qualité et KPI sont regroupés dans un **rail latéral compact**.
- Qualité détaillée, qualité certifiée, alertes et limites sont regroupées sous un seul **Détails**.
- Analyse et Règles sont rangés sous **Plus**.
- Recherche, sélection de groupe et changement de vue restent accessibles en permanence.
- Chaque liste conserve son propre scroll; le Centre reste en hauteur fixe sur desktop.

## Invariants
- QoS inchangée : Traités / (Reçus - Clôturés - Raccrochés avant file d'attente) × 100.
- Aucun calcul métier modifié.
- Aucun schéma de base ou donnée runtime modifié.
- Tri, identités, groupes, signalisation et distributions conservés.

## Validation
- Test UI RC29.3 : 3/3.
- Régressions RC29 Phases 1–6 : OK sur suites autonomes exécutées.
- Centre Live / campagnes : OK.
- Contrôle Qualité agents : 8 interactions / 7 répondus / distribution 8.
- Syntaxe JavaScript : OK.
- L'ancien test `rc29_qos_supervision_patch_test.py` contient une assertion UI obsolète sur un libellé supprimé avant RC29.3; ses assertions QoS restent valides.
