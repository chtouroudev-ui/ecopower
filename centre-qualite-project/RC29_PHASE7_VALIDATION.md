# RC29 — PHASE 7 — Validation production / gate final

Date : 28/09/2026  
Source : `Nelyio-ARCH_RC29_PHASE6_PERFORMANCE.zip`  
Release finale : `60.5-ARCH-RC29` / `V60.5-RC29`  
Mode : copie de travail ; aucune migration métier appliquée.

## FAIT

- Gate final exécuté sur la Phase 6 validée.
- Release stamp final passé de RC28 à **RC29** dans `VERSION.json`, le branding visible et le manifeste de production.
- `MANIFEST_PRODUCTION.json` régénéré sur l’état RC29 réellement livré.
- Préflight final : intégrité du code, syntaxe Python et `PRAGMA quick_check` des SQLite = PASS.
- Bootstrap SQLite depuis des bases vides validé en environnement isolé pour :
  - `TECHIN_Stock_Manager.db` ;
  - `NELYIO_Supervision.db` ;
  - `Nelyio_Details.db` ;
  - `Nelyio_Live.db`.
- Suite de régression finale : **231 tests PASS**, **2 tests historiques explicitement écartés** car leurs assertions sont antérieures aux contrats RC29 validés.
- Contrat QoS RC29 revérifié séparément : 1 traité + 1 abandonné => **50 %**.
- Sémantique HOLD revérifiée séparément : HOLD reste distinct de l’attente patient, compte comme appel en cours et reste exposé dans les métriques/écrans qui lui sont dédiés.
- Intégrité finale des bases, WAL/SHM et logs restaurée **octet pour octet** depuis la Phase 6 source.

## NON MODIFIÉ

Aucun changement fonctionnel n’a été ajouté pendant la Phase 7 :

- aucun KPI ;
- aucune formule métier en dehors du stamp de release ;
- aucun groupe ni rattachement ;
- aucune règle « A travaillé » ;
- aucune règle Live ;
- aucun tri ;
- aucune route API métier ;
- aucun schéma SQL ;
- aucun index PostgreSQL ;
- aucune base de données ;
- aucune configuration Caddy locale ;
- aucun historique d’appels.

Les seules modifications de release sont les métadonnées RC29, le manifeste et ce rapport.

## PREUVES

### Préflight final

Résultat : PASS pour toutes les vérifications automatisables locales :

- Python >= 3.10 : PASS ;
- `reportlab` : PASS ;
- `websockets` : PASS ;
- intégrité des empreintes du manifeste : PASS ;
- syntaxe Python : PASS ;
- `TECHIN_Stock_Manager.db` : `quick_check=ok` ;
- `NELYIO_Supervision.db` : `quick_check=ok` ;
- `Nelyio_Details.db` : `quick_check=ok` ;
- `Nelyio_Live.db` : `quick_check=ok` ;
- Caddyfile local préservé.

Avertissement attendu : la recette Windows/HTTPS/Hermes doit être exécutée sur la cible réelle.

### Régressions

Commande finale : suites RC29 1→6 + accès + Live + campagnes + signalisation + production + stabilité + Qualité + versions historiques applicables.

Résultat :

- **231 passed** ;
- **2 deselected** ;
- durée locale : ~3,7 s.

Les deux assertions historiques non utilisées pour le verdict final sont :

1. `audit_regression_test.py::test_source_totals_filters_and_distribution`
   - attend encore l’ancienne QoS ~66,67 % ;
   - RC29 validé utilise `traités / (traités + abandonnés)` ;
   - contrôle RC29 séparé : **50,0 % PASS**.

2. `live_operations_phase15_test.py::test_live_ui_exposes_operational_agent_and_campaign_detail`
   - attend encore le texte `Mise en attente appel` dans la liste compacte du Centre Live ;
   - Phase 2 RC29 a volontairement compacté cette liste ;
   - le HOLD reste présent dans la classification backend, les métriques Live et l’interface Appels suspects ;
   - contrôle séparé : `agents_on_hold=1`, `agents_in_call=2`, `max_hold_seconds=42` = PASS.

Ces deux tests doivent être réalignés ultérieurement ; ils ne constituent pas des défauts produit RC29.

### Bootstrap SQLite isolé

Création depuis zéro et `quick_check` :

| Base | Tables créées | quick_check |
|---|---:|---|
| `TECHIN_Stock_Manager.db` | 43 | ok |
| `NELYIO_Supervision.db` | 33 | ok |
| `Nelyio_Details.db` | 9 | ok |
| `Nelyio_Live.db` | 11 | ok |

Aucune de ces bases temporaires n’est incluse dans la livraison.

## FICHIERS

Fichiers modifiés pendant la Phase 7 :

- `VERSION.json` — stamp final `60.5-ARCH-RC29` ;
- `index.html` — branding visible `V60.5 RC29` ;
- `MANIFEST_PRODUCTION.json` — version/build/empreintes RC29 finales ;
- `RC29_PHASE7_VALIDATION.md` — présent rapport.

Aucun fichier Python/JavaScript fonctionnel n’a été modifié pendant la Phase 7.

## BDD

État final par rapport à la Phase 6 source :

- `*.db` : **identiques** ;
- `*.db-wal` : **identiques** ;
- `*.db-shm` : **identiques** ;
- logs runtime existants : **identiques**.

Les suites de tests ont temporairement ouvert certaines bases ; tous les artefacts concernés ont été restaurés depuis l’archive Phase 6 avant packaging final.

Aucune migration RC29 n’est requise par la Phase 7.

## PERFORMANCE

Mesures disponibles et déjà validées en Phase 6 :

- benchmark local `/healthz`, 5 clients × 10 vagues :
  - 50/50 HTTP 200 ;
  - médiane : **2,552 ms** ;
  - P95 : **13,802 ms** ;
  - max : **16,782 ms** ;
- single-flight Analytics : 5 demandes identiques à froid => **1 calcul + 4 réutilisations** ;
- session fraîche : **0 UPDATE / 0 COMMIT** du heartbeat ;
- heartbeat expiré : **1 UPDATE / 1 COMMIT**.

Ces mesures sont locales et ne prouvent pas la performance du serveur de production.

**NON MESURÉ EN PRODUCTION pendant Phase 7 :**

- PostgreSQL réel ;
- `EXPLAIN (ANALYZE, BUFFERS)` ;
- contention/verrous réels ;
- HTTPS/Caddy ;
- réseau LAN/VPN ;
- Hermes réel ;
- vrai import SIMPLIFY2 en parallèle ;
- 5 utilisateurs authentifiés sur données métier réelles ;
- rendu navigateur/Long Tasks.

## RISQUES

1. **Recette cible non exécutée ici.** Un PASS local ne remplace pas Windows + PostgreSQL + Caddy + Hermes.
2. **Deux tests historiques obsolètes.** Ils devront être réalignés aux contrats RC29 pour qu’une future exécution brute de toutes les suites ne produise pas de faux négatifs.
3. **Données métier absentes de l’archive.** Les KPI réels ne peuvent pas être recalculés sur une journée représentative dans ce package.
4. **PostgreSQL réel non profilé après RC29.** Aucun gain ou P95 production n’est affirmé.
5. **HTTPS/LAN à confirmer.** Le certificat, Caddy, le firewall et l’accès depuis un autre poste doivent être testés sur votre infrastructure.

## RESTE

Avant de déclarer **GO production**, exécuter sur le serveur cible :

1. `RECETTE_PRODUCTION.bat` avec PostgreSQL, Web, Live et Analytics démarrés ;
2. vérifier `/healthz` : build **60.5-ARCH-RC29**, PostgreSQL, services requis sains ;
3. tester une connexion avec un compte de recette possédant les droits Live / Qualité / Groupes / Configuration ;
4. vérifier Centre Live, campagnes, groupes et Pilotage Qualité sur des données réelles ;
5. exécuter le benchmark 5 utilisateurs authentifiés ;
6. vérifier HTTPS/Caddy depuis **un autre poste du LAN** ;
7. contrôler les nouveaux `http_slow.log`, `analytics_slow.log` et `performance.jsonl` ;
8. ne déclarer GO que si la recette ne contient aucun FAIL/SKIP bloquant et si les WARN sont explicitement acceptés.

## VERDICT

**PACKAGE RC29 : VALIDÉ LOCALEMENT.**

**GO PRODUCTION : EN ATTENTE DE RECETTE SUR LE SERVEUR CIBLE.**

Cette distinction est volontaire : aucun résultat PostgreSQL/HTTPS/Hermes réel n’est inventé.
