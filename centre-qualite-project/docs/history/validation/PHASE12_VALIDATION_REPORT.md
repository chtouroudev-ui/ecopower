# Phase 12 — Validation RC23

## Fait

- Permissions fines pour toutes les interfaces Nelyio.
- Périmètre métier par groupe d'accès : ALL ou SELECTED.
- Liste de groupes autorisés, groupe par défaut et filtre verrouillé/modifiable.
- Filtre Groupe dans Centre Qualité Live avec projection serveur.
- Filtrage serveur des campagnes, incidents, recherches Live et catalogues métier concernés.
- `Priorités Support` isolé derrière une API et un droit d'interface dédiés.
- Navigation masquée et redirection vers la première interface réellement autorisée.
- ANI reste une permission sensible indépendante des interfaces.

## Vérifié

- 174/174 tests Python PASS avant packaging.
- 12/12 tests spécifiques Phase 12 PASS.
- 21/21 fichiers JavaScript : syntaxe PASS.
- compileall PASS.
- preflight PASS sur le build propre RC23.
- dry-run RC22 -> RC23 PASS.
- upgrade applique sur copie RC22 PASS.
- cinq bases SQLite et Caddyfile preserves bit-a-bit.

## Garde-fous

- Un filtre verrouillé force le groupe configuré côté serveur.
- Un périmètre SELECTED refuse tout groupe hors liste même si l'URL est modifiée manuellement.
- Un utilisateur sans groupe autorisé ne reçoit pas un fallback implicite vers tous les groupes.
- Les agrégats Live GLOBAL/SERVICE ne sont pas présentés à un utilisateur restreint comme s'ils représentaient uniquement son groupe.
- Les administrateurs système restent non restreints.

## À valider sur le serveur réel

- scénario superviseur MED/IMG avec filtre verrouillé ;
- scénario responsable multi-groupes avec filtre modifiable ;
- scénario direction avec tous les groupes ;
- vérification des droits Lecture/Modification sur les interfaces utilisées au quotidien.
