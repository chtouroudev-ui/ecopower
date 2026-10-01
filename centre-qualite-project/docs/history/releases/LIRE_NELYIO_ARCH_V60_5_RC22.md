# Nelyio V60.5 RC22 — Phase 11 — Analyse ciblée des performances

RC22 poursuit RC21 sans ajouter de nouveau moteur métier. La phase exploite les preuves techniques déjà collectées pour aider à localiser les lenteurs réelles avant toute optimisation.

## Fait

- **Administration → Santé de production** contient un bloc **Analyse ciblée des performances**.
- Les entrées de `http_slow.log` restent agrégées par chemin sans query string.
- Les entrées de `analytics_slow.log` restent agrégées par type de calcul.
- Les statistiques détaillées ajoutent moyenne, P95, maximum et durée cumulée des seules entrées ayant dépassé le seuil de journalisation.
- Une correspondance fonctionnelle Web ↔ Analytics est signalée lorsqu'une route et son calcul associé sont tous deux présents dans les journaux lents.
- Une lenteur Web sans trace Analytics correspondante est séparée d'une lenteur Analytics seule.
- Le résultat du test de charge prolongée est exploité scénario par scénario lorsqu'il est disponible.
- `ANALYSER_PERFORMANCE_PRODUCTION.bat` génère :
  - `logs\performance_analysis.md`
  - `logs\performance_analysis.json`

## Interprétation sûre

Une correspondance Web ↔ Analytics **oriente** l'investigation, mais ne prouve pas que PostgreSQL est la cause. Le probe PostgreSQL `SELECT 1` confirme la disponibilité ponctuelle ; il ne suffit pas pour attribuer une lenteur applicative à la base.

L'absence de ligne dans un journal signifie uniquement qu'aucune requête n'a dépassé le seuil correspondant dans la fenêtre disponible. Elle ne signifie pas une latence nulle.

## Aucun réglage automatique

RC22 ne modifie automatiquement aucun :

- index PostgreSQL ;
- timeout ;
- seuil de lenteur ;
- cache ;
- règle Qualité ;
- KPI QoS/abandon/P90 ;
- donnée métier.

## Workflow recommandé

1. `RECETTE_PRODUCTION.bat`
2. `TEST_CHARGE_PROLONGEE.bat`
3. utiliser Nelyio normalement pendant la période d'observation
4. `ANALYSER_PERFORMANCE_PRODUCTION.bat`
5. ouvrir **Administration → Santé de production**
6. optimiser uniquement le parcours soutenu par les preuves

## Point d'arrêt

RC22 est une base sûre pour une optimisation ciblée après collecte de vraies mesures serveur/LAN. Les recommandations restent des prochaines vérifications, jamais des corrections automatiques.
