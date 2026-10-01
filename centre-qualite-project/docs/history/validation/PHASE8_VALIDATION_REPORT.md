# PHASE 8 - VALIDATION

## Fait
- Ajout `RECETTE_PRODUCTION.bat` / `RECETTE_PRODUCTION.ps1`.
- Ajout `tools/production_acceptance.py`.
- Rapport JSON + Markdown sans mot de passe.
- Controle statique + PostgreSQL read-only + health + HTTPS + auth + services + groupes + Live + campagnes + Qualite + 5 utilisateurs + requetes lentes.
- Aucune reparation automatique et aucune mutation metier.

## Verifie
- 144/144 tests Python PASS.
- 5/5 tests specifiques Phase 8 PASS.
- 20/20 fichiers JavaScript valides.
- audit frontend de concurrence PASS.
- compileall PASS.

## Validation upgrade
- Dry-run RC18 -> RC19 PASS.
- Upgrade applique sur copie RC18 PASS.
- TECHIN_Stock_Manager.db, NELYIO_Supervision.db, Nelyio_Details.db, Nelyio_Live.db, Nelyio_Services.db et Caddyfile verifies bit-a-bit inchanges.
- Preflight apres upgrade PASS (hors avertissements connus).

## Restant
- Executer la recette sur le vrai serveur Windows avec PostgreSQL/Hermes/Caddy actifs.
- Verifier l URL HTTPS depuis un autre poste du LAN.
- Rejouer une journee SIMPLIFY2 connue et comparer aux references externes de meme perimetre.

## Risque maitrise
Les checks distinguent PASS/WARN/FAIL/SKIP. Une source absente, un Live perime ou une recette sans identifiants ne devient jamais un faux GO.
