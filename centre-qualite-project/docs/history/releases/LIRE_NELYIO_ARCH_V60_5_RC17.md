# Nelyio-ARCH V60.5 RC17 - Phase 6 Incidents / Actions

## Base
RC17 derive exclusivement de **RC16 Live Drilldown Phase 5**.

## Objectif
Transformer les signaux Qualite Live en incidents réellement exploitables par un superviseur, sans permettre a l utilisateur de masquer un probleme encore actif.

## Cycle de vie
- `NOUVEAU` : ouverture automatique apres persistance du signal.
- `VU` : accusé de reception humain.
- `EN_INVESTIGATION` : investigation en cours.
- `ACTION_EN_COURS` : une action operationnelle explicite a ete declaree.
- `RETABLI` : retour a la normale constate automatiquement par le moteur Qualite Live.
- `CLOTURE` : fermeture humaine uniquement apres `RETABLI`.

Le passage a `RETABLI` reste automatique. Un superviseur ne peut pas declarer manuellement un incident actif comme resolu afin d eviter un faux vert.

## Tracabilite
Chaque ouverture, transition, commentaire, action, retour normal et cloture est conserve dans `Nelyio_Live.db` avec :
- utilisateur / SYSTEM ;
- date/heure ;
- statut avant / apres ;
- commentaire ;
- action ;
- snapshot des metriques lorsque pertinent.

Aucune nouvelle base n est creee.

## Avant / apres action
Lorsque `ACTION_EN_COURS` est selectionne, Nelyio enregistre les metriques disponibles au moment de l action. Lors du retour automatique a la normale, un second snapshot est conserve.

L interface peut alors afficher :
- valeur avant action ;
- valeur apres ;
- ecart ;
- auteur et heure de l action ;
- heure du retour a la normale.

Le texte reste volontairement non causal :

> Amelioration observee apres l action.

avec la precision :

> La chronologie montre une evolution apres l action ; elle ne prouve pas que l action a cause cette evolution.

## Interface
Nouvelle vue : **LIVE -> Incidents / Alertes**.

Elle contient :
- incidents actifs ;
- historique retabli / cloture ;
- niveau et couleur ;
- statut humain ;
- raisons et valeurs observees ;
- chronologie ;
- commentaires ;
- action ;
- comparaison avant / apres ;
- liens vers Recherche Live lorsque le perimetre le permet.

Le Centre Qualite Live propose egalement un bouton **Gerer l incident** sur chaque signal actif.

## Permissions
- Lecture `collection` : consultation des incidents et de leur historique.
- Modification `collection` : changement de statut humain, commentaire, action et cloture.
- Les regles / couleurs restent gerees dans la configuration Qualite Live avec leurs droits existants.

## Validation
- 135/135 tests Python PASS.
- 19/19 fichiers JavaScript syntaxe PASS.
- audit frontend de concurrence PASS.
- compileall PASS.
- benchmark synthetique SQLite : detail incident mediane ~0,46 ms / P95 ~0,62 ms ; liste 200 incidents mediane ~2,40 ms / P95 ~2,71 ms.

## Point d arret sur
RC17 constitue le point d arret apres Phase 6. La prochaine phase est la refonte des Analytiques selon le cahier des charges.
