# Phase 17 — RC28 Centre Qualité Live complet

## Fait

- Couverture Centre basée sur les groupes/files configurés.
- Campagnes/files/agents référencés visibles même sans état Live courant.
- Agents sans état Hermes = `Non observé`, jamais `Déconnecté` par défaut.
- **Qualité maintenant** et **Périmètres Qualité Live** remontés en haut.
- Valeurs Live non certifiées retirées de l'affichage principal.
- **Attente & qualité certifiées · aujourd'hui** séparé via `Stats.INBOUND`.
- HOLD conservé uniquement comme preuve explicite par appel/agent.
- Libellé final : **États Live des agents**.
- Campagnes Live chargées avec `include_inactive=1`.

## Vérifié

- 201 / 201 tests Python : PASS.
- 4 / 4 tests dédiés Centre Qualité Live : PASS.
- 21 / 21 fichiers JavaScript : syntaxe PASS.
- Audit frontend : PASS.
- `compileall` : PASS.
- Preflight / intégrité manifeste : PASS.
- Dry-run RC27 -> RC28 : PASS.
- Dry-run RC27.1 UI -> RC28 : PASS.
- Dry-run RC27.2 Centre -> RC28 : PASS.
- Upgrade appliqué RC27 -> RC28 : PASS.
- `TECHIN_Stock_Manager.db`, `NELYIO_Supervision.db`, `Nelyio_Details.db`, `Nelyio_Live.db`, `Nelyio_Services.db` et `Caddyfile` : SHA-256 inchangés avant/après l'upgrade.

## Risque maîtrisé

Aucun compteur Hermes non documenté n'est requalifié en attente patient. Les données historiques et Live restent séparées. Une absence d'état Hermes ne devient pas une fausse valeur `0` ou `Déconnecté`.

## Restant

La recette Windows/HTTPS/Hermes doit toujours être exécutée sur le serveur cible avec une vraie journée Live.

## Prochaine étape

Comparer en production la couverture `agents référencés / états Live observés` avec les groupes administrés et vérifier les campagnes réellement attendues.
