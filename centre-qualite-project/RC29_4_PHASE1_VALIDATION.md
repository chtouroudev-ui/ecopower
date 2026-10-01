# RC29.4 — Validation Phase 1

## Périmètre

Phase 1 uniquement : moteur backend de démarrage automatique du Collecteur Live.
Aucun changement de `collection_cdp.py`, du frontend, des KPI, de la QoS, des règles de signalisation ou des bases métier.

## Implémentation

- `auto_capture` ajouté à la configuration du collecteur, activé par défaut.
- `active_days` ajouté à la configuration, valeur par défaut `[1,2,3,4,5,6,7]` (ISO lundi=1 ... dimanche=7).
- `start_time` / `end_time` existants deviennent la plage persistante utilisée par l'auto-démarrage.
- Migration additive du JSON `collection_settings/config` : seules les clés absentes sont ajoutées ; aucun reset ni ALTER de base métier.
- `live_service.py` vérifie l'auto-démarrage toutes les 5 s, après `resume()` afin de clôturer d'abord une éventuelle session expirée.
- Si la politique est éligible, création de la session du jour avec `actor="auto"`.
- La création automatique et le stop manuel sont arbitrés sous `BEGIN IMMEDIATE` dans `Nelyio_Live.db`.
- La session créée reste `owner=NULL` jusqu'au `claim()` existant ; le lease existant reste l'autorité de possession du worker.
- Un stop manuel écrit `auto_capture_suppressed_day=<jour Europe/Paris>` et empêche tout redémarrage automatique ce jour-là.
- Le lendemain, le verrou daté ne bloque plus la nouvelle session.
- Une réactivation explicite est disponible via `POST /api/collection/auto` avec `{ "enabled": true }`, qui efface le verrou du jour.
- `status()` expose `auto_capture_suppressed_day` et `auto_capture_blocked_today` pour préparer l'interface de Phase 3.
- Les appels manuels existants conservent les préférences `auto_capture` / `active_days` même lorsqu'un ancien frontend ne les envoie pas.

## Fichiers modifiés

- `collection_service.py`
- `collection_store.py`
- `live_service.py`
- `routes_collection.py`

Test ajouté :

- `rc29_4_phase1_auto_capture_test.py`

## Tests Phase 1

Commande : `pytest -q rc29_4_phase1_auto_capture_test.py`

Résultat : **10 passed**.

Cas couverts :

- migration additive de la configuration ;
- création automatique dans la plage ;
- absence de doublon ;
- jours actifs ;
- plage horaire ;
- `auto_capture=false` ;
- stop manuel même jour ;
- nouveau jour ;
- réactivation explicite ;
- deux workers concurrents ;
- claim/lease unique ;
- session expirée de la veille clôturée avant création du jour ;
- course concurrente Stop manuel / auto-démarrage (10 itérations), sans session active résiduelle.

## Régressions ciblées

- Syntaxe Python (`py_compile`) : **OK**.
- `audit_regression_test.py -k 'live and not live_navigation_is_separate_from_collector_admin'` : **13 passed**.
- `v60_2_regression_test.py -k 'collection or live'` : **1 passed**.

Un test UI historique, `test_live_navigation_is_separate_from_collector_admin`, échoue aussi sur le ZIP RC29.3 original car il recherche encore le texte `non affichés`. Il n'est pas causé par Phase 1 et n'a pas été modifié ici.

## Invariants vérifiés par hash contre RC29.3

Inchangés :

- `quality_metrics.py`
- `quality_rules.py`
- `live_quality.py`
- `collection_cdp.py`
- `static/collection.js`
- `static/live-views.js`
- `static/collection.css`

Donc Phase 1 ne modifie ni formule QoS, ni calcul métier, ni signalisation, ni détection CDP/onglet, ni interface Centre Live.

## Important avant production

`VERSION.json`, `MANIFEST_PRODUCTION.json` et `SHA256_FILES.txt` ne sont volontairement pas régénérés pendant cette phase intermédiaire. La spécification prévoit le gate de régression et la validation finale en Phase 6 ; le refresh des empreintes de release sera effectué à ce moment-là.
