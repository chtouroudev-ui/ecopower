# RC29 — Phase 2 — Live / agents / périmètres / tri

Date : 2026-09-28  
Base : `Nelyio-ARCH_RC29_PHASE1_IDENTITES.zip`  
Travail effectué sur une copie uniquement.

## 1. Périmètre traité

Phase 2 uniquement :

- vue agents Live compacte ;
- suppression visuelle de la colonne Service / Groupe dans cette vue, sans changer les appartenances métier ;
- colonnes agents Live : **Agent, ID, État, Durée état, Campagne, File, Fraîcheur** ;
- tri centralisé avec cycle **ASC → DESC → défaut** ;
- valeurs absentes / inconnues / non observées / non calculables toujours placées en bas, y compris en DESC ;
- persistance du tri Live via `sessionStorage` ;
- DOM incrémental des agents, clé stable `agent_id` ;
- conservation de la recherche, filtre groupe, onglet Périmètre, tri, `<details>` et scroll lors du refresh ;
- garde contre les réponses Live hors ordre lors de changements rapides de groupe ;
- séparation du refresh Hermes fréquent et du refresh historique Stats.INBOUND ;
- Périmètres : Observés, Disponibles, En appel, Pause, Traités, Abandonnés, QoS ;
- période historique explicitement affichée ;
- QoS Nelyio partagée : `Traités / (Traités + Abandonnés) × 100`, `—` si le dénominateur vaut 0 ;
- formule externe historique conservée séparément comme `reference_qos_percent` ;
- contrat backend de tri allowlisté avec clé secondaire déterministe avant pagination.

## 2. Architecture Live modifiée

Le premier chargement du Centre Live crée la structure DOM. Les refresh suivants ne remplacent plus `app.innerHTML` pour toute la page.

Les blocs dynamiques sont mis à jour séparément et les lignes agents sont réconciliées avec :

- `data-live-agent-id` ;
- réutilisation du même `<tr>` quand l'identité et le contenu structurel ne changent pas ;
- simple mise à jour de la base du ticker de durée lorsque seul le temps d'état avance.

Une séquence locale `requestSeq` empêche une ancienne réponse du même écran d'écraser une sélection plus récente.

## 3. Tri RC29

Frontend Live :

- premier clic : ASC ;
- deuxième clic : DESC ;
- troisième clic : retour au tri par défaut ;
- types supportés : texte, nombre, pourcentage, durée, timestamp, état métier ;
- valeurs manquantes toujours en bas ;
- égalités départagées par ID stable ;
- tri sauvegardé dans la session.

Backend : `sort_contract.py` refuse toute clé ou direction non allowlistée. `live_call_search` applique le tri avant pagination et départage par référence Live.

## 4. QoS

### QoS Nelyio

`Traités / (Traités + Abandonnés) × 100`

Lorsque `Traités + Abandonnés = 0`, la valeur reste `None` côté backend et s'affiche `—` côté UI.

### Référence externe conservée

L'ancienne formule n'est pas supprimée :

`(Traités + reroutés sans agent) / (Reçus - clôturés - raccrochés avant file) × 100`

Elle est exposée séparément via :

- `reference_qos_numerator` ;
- `reference_qos_denominator` ;
- `reference_qos_percent`.

## 5. Historique des Périmètres

Nouveau endpoint : `/api/live/scope-quality`.

Il utilise Stats.INBOUND sur une période explicite. Par défaut, la configuration actuelle donne **08:00–19:00** dans la copie testée.

La requête historique est cachée côté frontend pendant 60 s et ne fait pas partie du cycle Hermes 5 s.

Pour les files, une métrique historique n'est attribuée que si la relation campagne → file configurée est unique. Une relation ambiguë reste indisponible au lieu d'être devinée.

## 6. Fichiers fonctionnels modifiés

- `collection_store.py`
- `http_handler.py`
- `quality_metrics.py`
- `quality_reference_20260901_test.py`
- `quality_rules.py`
- `routes_collection.py`
- `static/collection.css`
- `static/live-views.js`
- `static/quality-overview.js`

## 7. Nouveaux fichiers

- `live_scope_quality.py`
- `sort_contract.py`
- `rc29_phase2_live_test.py`
- `RC29_PHASE2_VALIDATION.md`

## 8. Tests exécutés

### Nouveau test Phase 2

`rc29_phase2_live_test.py`

Résultats :

- QoS 8 / (8 + 2) = 80 % : OK ;
- QoS 0 / 0 = non calculable : OK ;
- référence externe séparée : OK ;
- allowlist backend : OK ;
- tentative de clé de tri `duration;DROP TABLE users` rejetée : OK ;
- valeurs manquantes en bas ASC : OK ;
- valeurs manquantes en bas DESC : OK ;
- persistance sessionStorage présente : OK ;
- DOM agents clé `agent_id` : OK ;
- endpoint historique protégé par scope serveur : OK.

### Régressions exécutées

- `rc29_phase1_identity_test.py` : **5/5 OK** ;
- `live_center_completeness_test.py` : OK ;
- `live_campaigns_phase4_test.py` : OK ;
- `live_campaigns_phase5_test.py` : OK ;
- `live_operations_phase15_test.py` : OK ;
- `live_quality_phase2_test.py` : OK ;
- `live_quality_phase3_test.py` : OK ;
- `live_quality_phase6_test.py` : OK ;
- `group_filter_global_test.py` : **7 tests OK** ;
- `audit_regression_test.py` : **5 tests OK** ;
- `quality_agent_counts_v6_test.py` : OK, avec **8 interactions** conservées et **7 réponses Stats.INBOUND** conservées ;
- import des modules modifiés en mode SQLite : OK ;
- `node --check` sur tous les `static/*.js` : OK.

## 9. Test non exécuté

`quality_rc2i_test.py` exige obligatoirement un export réel via `--zip`. Aucun export correspondant n'a été fourni dans cette phase, donc aucun résultat n'est revendiqué.

Le test de référence `quality_reference_20260901_test.py` a été mis à jour pour vérifier séparément la QoS Nelyio et la formule externe, mais il nécessite lui aussi l'export SIMPLIFY2 du 01/09/2026 pour être rejoué.

## 10. Préservation

Comparaison avec la Phase 1 validée :

- les 4 bases principales ont exactement le même SHA-256 avant/après ;
- WAL/SHM restaurés à l'identique ;
- log de test restauré ;
- aucune base de données n'est incluse dans les différences fonctionnelles ;
- aucun fichier n'a été supprimé.

## 11. Hors Phase 2

Non traité ici :

- définition métier « A travaillé » ;
- Signalisation Phase 3 ;
- Distributions Phase 4 ;
- migration du tri des autres tableaux Phase 5 ;
- optimisation / benchmarks de performance Phase 6.

**STOP — ne pas commencer la Phase 3 sans validation.**
