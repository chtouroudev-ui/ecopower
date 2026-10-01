# RC29 — Phase 4 — Distributions + Périmètres métier

## Périmètre

Phase 4 appliquée sur une copie de `Nelyio-ARCH_RC29_PHASE3_SIGNALISATION.zip`.

Aucun changement volontaire hors du périmètre suivant :

- conserver Reçus / Traités / Abandonnés dans Distributions ;
- ajouter la QoS Nelyio partagée : `Traités / (Traités + Abandonnés) × 100`, `—` si dénominateur nul ;
- ajouter Agents ACTIVE, En pause, Attendus, A travaillé, N’a pas travaillé ;
- population Groupe = agents configurés ACTIVE sur les files du groupe ;
- compter les pauses par `COUNT DISTINCT agent` sur chaque tranche chevauchée ;
- ne déduire une absence que lorsque la population ACTIVE et la couverture Stats.AGENT sont disponibles ;
- conserver Europe/Paris et des fenêtres explicites ;
- fournir un drill-down horaire par jour et agent.

## Décisions appliquées

### Population ACTIVE

La population canonique provient exclusivement de `quality_scope` : agent configuré ACTIVE sur au moins une file du périmètre.

Les relations Administration `user_group_members`, les campagnes seules et les observations Live ne peuvent pas élargir cette population.

Un agent peut appartenir à plusieurs groupes via plusieurs files ACTIVE ; les groupes ne sont donc pas additionnables.

### Attendus / A travaillé / N’a pas travaillé

Ces métriques sont calculées uniquement sur les jours où `coverage` fournit une référence Stats.AGENT.

Preuve positive de travail :

- `quality_agent_facts.kind in (work, inbound, manual, hold)` pour les imports enrichis ;
- pour les anciens imports : états/appels explicites reconnus dans `activities`.

Ne prouvent pas le travail à eux seuls :

- offline / déconnexion ;
- pause ;
- coaching ;
- unknown / état inconnu.

Une fois qu’une preuve positive de travail existe dans la journée/fenêtre avant la fin de la tranche, une déconnexion ultérieure ne transforme pas l’agent en absent.

Si les affectations ACTIVE sont indisponibles ou si la couverture Stats.AGENT est absente, `N’a pas travaillé` n’est pas inventé : état `not_calculable`, valeurs `null` / `—`.

### Pause

`En pause` est un nombre d’agents distincts dont un intervalle Pause chevauche la tranche.

- deux pauses du même agent dans la même tranche = 1 ;
- une pause 10:55–11:10 compte dans 10:00–11:00 et 11:00–12:00 ;
- les intervalles sont bornés à la fenêtre métier et aux limites de journée Europe/Paris.

### Multi-jours

Sur une journée, les compteurs sont des agents.

Sur plusieurs jours, les compteurs horaires Attendus / En pause / A travaillé / N’a pas travaillé / ACTIVE sont explicitement des **agent-jours cumulés**. La carte `Agents ACTIVE · uniques` reste le nombre distinct d’agents configurés du périmètre.

## Fichiers modifiés

- `quality_distributions.py`
- `static/quality-distributions.js`

## Fichiers ajoutés

- `quality_workforce.py`
- `rc29_phase4_distribution_scope_test.py`
- `RC29_PHASE4_VALIDATION.md`

## Fonctionnalités UI ajoutées

Distributions affiche désormais :

- Reçus ;
- Traités ;
- Abandonnés ;
- QoS ;
- Agents ACTIVE ;
- En pause ;
- Attendus ;
- A travaillé ;
- N’a pas travaillé ;
- bouton `Voir` pour le drill-down horaire.

Le drill-down détaille par date et agent : ID, nom, A travaillé, En pause, N’a pas travaillé.

L’interface expose clairement :

- couverture Stats.INBOUND ;
- couverture Stats.AGENT ;
- statut `reliable`, `partial` ou `not_calculable` ;
- unité agents / agent-jours ;
- règle de population et règle de preuve de travail.

## Tests Phase 4

`rc29_phase4_distribution_scope_test.py` : 6/6 contrôles réussis :

1. population Groupe = membres ACTIVE des files ;
2. campagne restreint la population aux files liées ;
3. deux pauses du même agent dans une tranche = 1 ;
4. pause traversant deux tranches visible dans les deux ;
5. agent ayant travaillé puis déconnecté reste travaillé ;
6. MED1 synthétique : 30 ACTIVE, 27 travaillés, 3 n’ayant pas travaillé.

## Régressions

13 suites exécutées avec `NELYIO_FORCE_SQLITE=1` sur une copie de test : 13/13 réussies.

- `rc29_phase1_identity_test.py`
- `rc29_phase2_live_test.py`
- `rc29_phase3_signalisation_test.py`
- `rc29_phase4_distribution_scope_test.py`
- `group_filter_global_test.py`
- `live_center_completeness_test.py`
- `live_campaigns_phase4_test.py`
- `live_campaigns_phase5_test.py`
- `live_quality_phase2_test.py`
- `live_quality_phase3_test.py`
- `live_quality_phase6_test.py`
- `quality_agent_counts_v6_test.py`
- `audit_regression_test.py`

Contrôle `node --check` : 21/21 scripts `static/*.js` valides.

Test d’intégration lecture seule de `quality_distributions.view()` : réponse valide, timezone `Europe/Paris`, QoS présente, statut workforce explicite lorsque les données embarquées sont insuffisantes.

## Préservation

Avant ajout de ce rapport, comparaison byte-à-byte avec la Phase 3 :

- 2 fichiers fonctionnels modifiés ;
- 2 fichiers fonctionnels ajoutés ;
- 0 fichier existant supprimé ;
- bases, WAL/SHM, logs et caches restaurés à leur état Phase 3 après les tests.

Aucune migration SQL, aucun import, aucune modification de base métier et aucune modification du Live central n’a été appliqué.

## Éléments non exécutés / non mesurables ici

- validation sur le vrai groupe MED1 avec 30 agents réels : la livraison ne contient pas les données métier nécessaires ; le cas d’acceptation a été reproduit de façon synthétique ;
- test PostgreSQL production / EXPLAIN ;
- test navigateur réel ;
- mesure de performance à cinq utilisateurs ;
- comparaison avec un planning RH : aucun planning n’est une source de la Phase 4.

## Risques résiduels

- un export Stats.AGENT incomplet peut rendre la population `partial` ou `not_calculable` ; il ne doit pas être interprété comme zéro absence ;
- les périodes multi-jours doivent être lues en agent-jours ;
- une affectation ACTIVE actuelle n’est pas un historique d’affectation daté. Pour analyser des périodes historiques très anciennes, l’application ne peut pas reconstituer une affectation passée qui n’a pas été conservée.

**STOP — ne pas commencer la Phase 5 sans validation utilisateur.**
