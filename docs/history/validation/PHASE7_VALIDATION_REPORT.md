# PHASE 7 - VALIDATION

## Fait
- Nouvelle page Analytiques -> Synthese Analytiques.
- Parcours Signal -> Explication -> Perimetre -> Preuves -> Drilldown -> Action.
- 4 KPI de repere maximum en tete et 5 signaux maximum.
- Une seule source analytique de synthese : `/api/quality/pilotage`.
- Drilldowns vers les vues detaillees existantes sans duplication du calcul metier.
- Creation d action Qualite depuis le signal selectionne.
- Vue responsive jusque 390/520 px.

## Verifie
- 139/139 tests Python PASS.
- 4 tests Phase 7 PASS.
- syntaxe JavaScript PASS.
- audit frontend PASS.
- compileall PASS.

## Restant
- Recette reelle Windows + HTTPS + PostgreSQL + donnees SIMPLIFY2 de production.
- Validation UX avec superviseurs francophones sur ecran reel.

## Risque maitrise
La refonte n ajoute ni nouvelle formule QoS, ni score de performance, ni nouvel endpoint Analytics lourd. Elle reutilise le moteur Pilotage existant.
