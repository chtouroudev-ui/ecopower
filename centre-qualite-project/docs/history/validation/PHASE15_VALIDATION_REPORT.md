# Phase 15 — Validation RC26

## Fait
- Détails opérationnels par agent dans Centre Qualité Live.
- Volumes d’appels Live observés 15 min / 60 min / aujourd’hui.
- Décomposition des temps d’état observés.
- Temps non disponible observé conservateur.
- HOLD explicite séparé de Waiting/Disponible.
- Mise en attente par appel uniquement sur preuve explicite dans la timeline.
- Volumes Live par campagne et enrichissement du drill-down agent.

## Vérifié
- 193/193 tests Python.
- 6/6 tests Phase 15.
- 21/21 JavaScript syntax.
- audit frontend PASS.
- compileall PASS.
- preflight du paquet propre PASS.
- dry-run RC25 -> RC26 PASS.
- upgrade appliqué RC25 -> RC26 PASS.
- cinq bases SQLite et Caddyfile préservés bit-à-bit.

## Restant
- Valider sur le serveur réel quels libellés Hermes sont reçus lors d’une vraie mise en attente.
- Si Hermes n’émet pas de libellé explicite HOLD, conserver la métrique par appel indisponible jusqu’à preuve supplémentaire.

## Risque maîtrisé
- Aucun compteur `arg_n` n’est renommé en attente/HOLD sans certification.
- Absence de HOLD explicite != zéro seconde.
- Les appels Live sont des observations du spool courant, pas un remplacement des KPI certifiés SIMPLIFY2.
