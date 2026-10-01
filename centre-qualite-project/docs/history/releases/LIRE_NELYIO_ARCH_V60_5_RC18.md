# Nelyio-ARCH V60.5 RC18 - Phase 7 Refonte Analytiques

## Base
RC18 derive exclusivement de **RC17 Incidents / Actions Phase 6**.

## Objectif
Transformer l entree Analytiques en parcours de decision :

`Signal -> Explication -> Perimetre -> Preuves -> Drilldown -> Action`.

La phase ne remplace aucun moteur metier. La synthese reutilise exclusivement `/api/quality/pilotage` pour les faits, baselines, signaux, files a investiguer, fiabilite et actions a verifier.

## Interface
Nouvelle vue : **Analytiques -> Synthese Analytiques**.

Elle contient :
- 4 reperes principaux : QoS, taux d abandon, P90 attente, agents ayant traite ;
- maximum 5 signaux explicables ;
- faits observes separes des hypotheses a verifier ;
- perimetre et fenetre temporelle explicites ;
- preuves files limitees aux relations certifiees existantes ;
- drilldowns vers Analyse detaillee, Qualite de service, Qualite agents, Distributions et Appels suspects ;
- creation d une action Qualite depuis le signal selectionne ;
- actions deja au statut A verifier ;
- affichage clair du niveau de fiabilite et des limitations.

## Principes conserves
- MEDICAL et IMAGERIE ne sont jamais compares entre eux ; chaque service reste compare a son propre historique.
- Agents ayant traite n est jamais presente comme agents connectes Live.
- Les files a investiguer restent basees sur ODCalls.FirstQueue ; elles ne remplacent pas la QoS officielle Stats.INBOUND.
- Les hypotheses restent des pistes de verification, jamais des causes affirmees.
- Aucun score cache de performance n est ajoute.
- Les anciens ecrans detailles restent disponibles et deviennent les drilldowns specialises.

## Performance
La page Synthese effectue une seule lecture analytique : `/api/quality/pilotage`. Aucun nouvel endpoint analytique lourd, aucune requete par signal/file/agent et aucun nouveau service ne sont introduits.

## Validation
- 139/139 tests Python PASS.
- 4/4 tests Phase 7 PASS.
- JavaScript syntaxe PASS.
- audit frontend de concurrence PASS.
- compileall PASS.

## Point d arret sur
RC18 constitue le point d arret apres Phase 7. La prochaine phase doit porter sur la recette production et/ou les optimisations finales identifiees par des mesures reelles, sans rearchitecture speculative.
