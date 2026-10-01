# RC29.4 - Validation Phase 2

## Objet
Phase 2/7 - Collecteur : detection et reconnexion du navigateur.

Cette phase part de la copie RC29.4 Phase 1 validee. Elle ne modifie ni les KPI metier, ni la QoS, ni le Centre Qualite Live.

## Modifications minimales

### collection_cdp.py
- `probe()` ne transforme plus l'absence d'Edge en erreur HTTP : il retourne un etat `waiting_browser` avec un message explicite.
- Un seul onglet correspondant est signale `target_detected` et `auto_select=true`.
- Zero onglet correspondant reste un etat d'attente.
- Plusieurs onglets correspondants restent un etat d'attente ambigu, sans selection arbitraire.
- Ajout de `_choose_target()` :
  - target_id explicite encore present -> conserve ;
  - target_id ancien/disparu + un seul onglet correspondant -> reconnexion automatique sur l'unique onglet ;
  - zero ou plusieurs onglets sans cible certaine -> `CaptureError` retryable, gere par `Manager._run()`.
- Le port CDP et le WebSocket restent limites au loopback `127.0.0.1`/localhost/::1.
- Aucun `Runtime.evaluate`, aucun JavaScript injecte dans la page.

### collection_service.py
- Une session creee par `ensure_auto_session()` force `target_id=''`, afin de ne jamais reutiliser l'identifiant CDP d'un onglet de la veille.
- La cadence de reconnexion navigateur est bornee entre 5 et 10 secondes via `_browser_retry_seconds()`.
- Le mecanisme de session/claim/lease de Phase 1 est conserve.

### Autostart Edge
`INSTALL_NELYIO_AUTOSTART.ps1` n'a pas ete modifie dans cette phase. Le lancement automatique de `OPEN_EDGE_CAPTURE.ps1` etait optionnel dans la specification. Il reste volontairement non active : l'objectif demande est que Nelyio detecte automatiquement Edge lorsqu'il est ouvert, sans imposer l'ouverture d'un navigateur supplementaire a chaque connexion Windows.

## Comportements verifies

1. Edge non ouvert : la session reste active et passe en `waiting_browser`; elle n'est pas terminee.
2. Un seul onglet correspondant : selection automatique.
3. Ancien target_id disparu et onglet recree avec un nouvel ID : reconnexion automatique si cet onglet est l'unique correspondance.
4. Plusieurs onglets : aucune cible arbitraire ; la session attend et retente.
5. Reapparition du navigateur dans la meme journee : meme session, nouvelle connexion ; aucune nouvelle session n'est creee.
6. Session automatique : aucun ancien `target_id` persiste dans `settings_json`.
7. Retry navigateur : 5, 6, ... jusqu'a 10 secondes maximum.

## Tests

### Nouveaux tests Phase 1 + Phase 2
Commande :
`pytest -q rc29_4_phase2_browser_reconnect_test.py rc29_4_phase1_auto_capture_test.py`

Resultat : **20 passed**.

### Regression elargie
Commande :
`pytest -q rc29_4_phase1_auto_capture_test.py rc29_4_phase2_browser_reconnect_test.py audit_regression_test.py production_stability_test.py v60_2_regression_test.py rc29_native_live_metrics_test.py rc29_r8_campaign_mapping_test.py`

Resultat : **114 passed, 1 failed**.

L'unique echec est `audit_regression_test.py::test_live_navigation_is_separate_from_collector_admin`, qui recherche encore le texte obsolete `non affichés` dans `static/live-views.js`. Ce meme defaut etait deja present sur RC29.3 avant Phase 1. `static/live-views.js` est byte-identique au ZIP RC29.3 original pendant cette phase (SHA-256 : `040a6253a8c4f36ebad6acada15dd1bb44d749440f839574e4f254f7a76e19e6`). Il n'est donc pas une regression Phase 2.

### Syntaxe
`python -m py_compile collection_cdp.py collection_service.py live_service.py routes_collection.py rc29_4_phase2_browser_reconnect_test.py`

Resultat : OK.

## Invariants verifies
- QoS et calculs metier : inchanges.
- `Inconnu != zero` / `Non observe` : inchanges.
- Permissions : inchangees.
- Une seule journee par session : inchange.
- Donnees brutes limitees au jour courant : inchange.
- CDP local uniquement : conserve.
- Aucun cookie, mot de passe, audio ou corps HTTP arbitraire collecte : inchange.
- ANI uniquement si l'option existante l'autorise : inchange.

## Plan mis a jour
Le chantier demande dans la conversation `Audit phase 0 RC29` est ajoute avant la validation finale. Le plan passe a 7 phases de travail :
- Phase 3 : interface Collecteur Live.
- Phase 4 : lisibilite et informations vitales du Centre Qualite Live.
- Phase 5 : rapidite d'usage du Centre Qualite Live.
- Phase 6 : alignement avec la derniere UI Centre Qualite Live, correction des Campagnes (Traites / Abandonnes / QoS) et ameliorations ergonomiques demandees.
- Phase 7 : tests, regressions et validation finale.
