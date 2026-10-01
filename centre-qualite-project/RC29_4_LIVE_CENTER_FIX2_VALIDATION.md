# RC29.4 — Centre Qualité Live FIX2

## Objet
Différencier visuellement les états de pause réellement transmis par Hermes sans modifier les KPI, la QoS ou les règles métier, et ajouter un signal progressif sur le Post-appel / Post-travail.

## Comportement ajouté
- Pause normale : badge jaune doux.
- Pause déjeuner / Lunch : badge bleu.
- Coaching : badge violet dédié.
- General Break / pause générale : badge orange.
- Post-appel / Post-travail : badge orange en régime normal.
- Post-appel 10 à <15 s : surveillance jaune.
- Post-appel 15 à 25 s : alerte renforcée orange.
- Post-appel >25 s : badge rouge et ligne agent rouge.
- Le signal est recalculé chaque seconde à partir de la durée d'état existante, sans reconstruction complète du tableau.
- Les termes de pause sont dérivés du libellé Hermes brut déjà présent dans le payload. Une valeur inconnue reste inconnue : aucune pause n'est inventée.
- Le filtre Déconnectés existant est conservé ; aucun filtre supplémentaire n'est ajouté pour chaque type de pause.

## Invariants
- Aucun changement de formule QoS.
- Aucun changement des KPI Hermes UpQuR / UpQuH.
- Aucun reset ou migration de base.
- `kind` Hermes reste inchangé : la taxonomie ajoutée est une présentation Centre Live, pas une reclassification métier globale.
- Non observé reste distinct de Déconnecté.

## Validation ciblée
- `node --check static/live-views.js` : PASS.
- `rc29_4_live_pause_visual_test.py` : 4/4 PASS.
- Régressions Centre Live ciblées : 38/38 PASS.
- Suite complète sur copie isolée : **305/305 PASS**.
- Manifeste production : **468/468 fichiers** vérifiés après mise à jour des empreintes.
- Les 5 bases SQLite de la release sont bit-à-bit inchangées par rapport à FIX1.

## Simulation du patch cumulatif
- Patch appliqué sur une copie de `Nelyio-ARCH_V60.5_RC29.4` d'origine : **11 fichiers copiés**.
- Vérification `MANIFEST_PRODUCTION.json` après patch : **468/468 OK**.
- SHA-256 des 5 bases `.db` avant/après patch : **strictement identiques**.
- Le patch est donc cumulatif : il peut être appliqué sur RC29.4 original ou sur FIX1.
