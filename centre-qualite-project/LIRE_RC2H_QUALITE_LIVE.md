# Nelyio V56.18 MS1 — PostgreSQL RC2H QUALITÉ + LIVE

## Fait

### Qualité de service

- `Traités` utilise désormais **AgentId > 0** ; `IsCallAnswered` reste disponible comme **Répondus SIMPLIFY2**.
- La QoS utilise une seule formule métier : **(traités par agent + reroutés sans agent) / (reçus - clôturés - raccrochés avant file)**.
- ASA et `Traités <= 60 s` utilisent la même population `AgentId > 0`.
- Les catégories sont explicites : clôturés, débordements, reroutés sans agent, ignorés, raccrochés avant file, abandonnés, traités par agent.
- Les sous-catégories des traités sont contrôlées : complétés + transférés + reroutés agent = traités par agent.
- `IsCallLost` est conservé comme diagnostic `Lost avec agent`; il n’est plus assimilé automatiquement à un appel non traité.
- `Stats.OUTBOUND` est importé séparément et n’entre jamais dans les agrégats entrants.
- Le calcul reste SQL/agrégé et respecte date, heure, campagne, groupe et Europe/Paris.
- La migration est non destructive : les imports historiques restent lisibles. Pour obtenir `Lost avec agent` et OUTBOUND sur une ancienne journée, réimporter le ZIP source de cette journée.

### Capture Live

- `Arrêter` rend immédiatement toute session active **stopped/closed**, même si `live_service` ne tourne plus.
- En mode multi-processus, le démarrage est refusé si le service Live n’est pas réellement sain : l’interface ne doit plus afficher une fausse capture active.
- Les buffers DevTools sont restaurés à **100 MiB par ressource / 200 MiB total** et la file WebSocket à **512**, afin de limiter les pertes de réponses `changes.ashx` sous charge.

## Vérifié

Référence réelle `SIMPLIFY2.2026-09-01.export.zip`, filtrée sur la **date réelle des lignes** du 01/09/2026 :

| Indicateur | Résultat RC2H |
|---|---:|
| Reçus | 12 115 |
| Clôturés | 599 |
| Débordements | 20 |
| Reroutés sans agent | 2 |
| Raccrochés avant file | 337 |
| Abandonnés | 2 070 |
| Traités par agent | 9 087 |
| Répondus IsCallAnswered | 8 650 |
| Lost avec agent | 163 |
| Reroutés avec agent | 274 |
| Transférés | 65 |
| Complétés | 8 748 |
| QoS numerator | 9 089 |
| QoS denominator | 11 179 |
| QoS | 81,30 % |
| ASA | 115,93 s (~01:56) |
| Traités <= 60 s | 5 071 / 9 087 = 55,80 % |
| OUTBOUND séparé | 79 |
| Écart de cohérence | 0 |

Contrôle exact : `599 + 20 + 2 + 0 + 337 + 2 070 + 9 087 = 12 115`.

Tests exécutés dans le paquet :

- `python -m pytest audit_regression_test.py -q` → **33 passed** ;
- `node audit_frontend_test.js` → **PASS** ;
- `python quality_reference_20260901_test.py --zip <export>` → **PASS** ;
- benchmark SQLite isolé : 60 000 appels, 5 lectures concurrentes correctes.

Le test Live isolé vérifie également l’arrêt terminal sans worker et le refus de démarrage lorsqu’un worker externe est déclaré indisponible.

## Restant

La logique et les régressions sont validées hors production. Une recette finale doit encore être faite sur le serveur Windows réel avec **PostgreSQL + Edge/Hermes + service Live** afin de confirmer la connectivité DevTools et les heartbeats dans l’environnement de production.

## Risque maîtrisé

- aucune réinitialisation de base ;
- aucune suppression d’historique ;
- ajout de colonnes/tables compatible avec les données existantes ;
- ancien `IsCallAnswered` conservé, mais séparé du KPI Traités ;
- les appels OUTBOUND restent physiquement et fonctionnellement séparés ;
- les 3 lignes du 31/08 présentes dans le ZIP du 01/09 sont exclues du filtre 01/09 ;
- l’écart Vocalcom de +1 clôturé n’est pas inventé par Nelyio.

## Prochaine étape

1. Extraire RC2H dans un **nouveau dossier**.
2. Réutiliser/recréer `data\postgres.env` selon votre procédure actuelle.
3. Lancer `VALIDATION_PRODUCTION.bat` puis `START_NELYIO.bat`.
4. Réimporter le ZIP du 01/09/2026 pour enrichir `IsCallLost` et OUTBOUND si cette journée existait déjà en version historique.
5. Lancer `VALIDER_REFERENCE_QUALITE_20260901.bat "C:\\...\\SIMPLIFY2.2026-09-01.export.zip"`.
6. Vérifier Capture Live : démarrer, observer des réponses, puis arrêter ; l’état doit passer immédiatement à arrêté.

## Fichiers modifiés / ajoutés dans RC2H

- `collection_cdp.py`
- `collection_service.py`
- `collection_store.py`
- `static/collection.js`
- `quality_metrics.py`
- `quality_rules.py` (nouveau)
- `quality_summary.py`
- `quality_distributions.py`
- `quality_precision_check.py`
- `static/quality-overview.js`
- `static/quality-distributions.js`
- `audit_regression_test.py`
- `audit_benchmark.py`
- `quality_reference_20260901_test.py` (nouveau)
- `VALIDER_REFERENCE_QUALITE_20260901.bat` (nouveau)
- `VERSION.json`
- `README.md`
- `LIRE_AVANT_PRODUCTION.md`
- `LIRE_RC2H_QUALITE_LIVE.md` (nouveau)
- `MANIFEST_PRODUCTION.json`
- `SHA256_FILES.txt`
