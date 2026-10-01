# RC29.3 — VALIDATION CONSOLIDÉE

Date : 28/09/2026  
Base : `Nelyio-ARCH V60.5 RC29.3 LIVE_SIMPLE` mise à jour après l'étape 1.  
Périmètre : étape 2 du chantier **GEL, CONSOLIDATION ET RANGEMENT**.  
Aucune fonctionnalité applicative, formule QoS, règle ACTIVE, distribution, signalisation, schéma ou donnée BDD n'a été modifié pendant cette étape.

## 1. Exécution globale

Toutes les suites `*test.py` présentes à la racine ont été passées à **une seule invocation pytest**, dans le même environnement, avec :

- `NELYIO_FORCE_SQLITE=1`
- `NELYIO_SKIP_STARTUP_DETAILS_SYNC=1`
- `PYTHONDONTWRITEBYTECODE=1`
- cache pytest désactivé (`-p no:cacheprovider`)

Cela inclut notamment :

- `rc29_phase1_identity_test.py`
- `rc29_phase2_live_test.py`
- `rc29_phase3_signalisation_test.py`
- `rc29_phase4_distribution_scope_test.py`
- `rc29_phase5_sort_test.py`
- `rc29_phase6_performance_test.py`
- `rc29_qos_supervision_patch_test.py`
- `rc29_3_live_simple_ui_test.py`
- `audit_regression_test.py`
- `group_filter_global_test.py`
- `live_campaigns_phase4_test.py`
- `live_campaigns_phase5_test.py`
- `live_center_completeness_test.py`
- `live_operations_phase15_test.py`
- `live_quality_phase2_test.py`
- `live_quality_phase3_test.py`
- `live_quality_phase6_test.py`
- `phase16_signalisation_test.py`
- `production_acceptance_phase8_test.py`
- `production_hardening_phase10_test.py`
- `production_observability_phase9_test.py`
- `production_performance_phase11_test.py`
- `production_stability_test.py`
- `access_scope_phase12_test.py`
- `access_profiles_phase13_test.py`
- `users_ui_phase14_test.py`
- `analytics_phase7_test.py`
- `v60_2_regression_test.py`
- `v60_3_regression_test.py`
- `v60_4_regression_test.py`
- `quality_agent_counts_v6_test.py`

Les fichiers `quality_rc2i_test.py` et `quality_reference_20260901_test.py` ont également été fournis à pytest, mais ne définissent **aucun test pytest collectable** : ce sont des validateurs autonomes qui exigent `--zip` avec un export SIMPLIFY2 réel. Ils ne sont donc pas comptés comme PASS/FAIL/SKIP et ne sont **pas silencieusement exclus**. Aucun export de référence n'étant présent dans cette archive, leur exécution autonome n'a pas été simulée.

### Résultat global

- **PASS : 237**
- **FAIL : 2**
- **SKIP : 0**
- durée locale : **4,20 s**

Commande :

```text
python -m pytest -q -p no:cacheprovider <les 33 fichiers *test.py de la racine>
```

## 2. Les 2 FAIL restants

### FAIL 1 — `access_scope_phase12_test.py`

Test :

```text
test_frontend_contains_group_filter_and_full_interface_access_editor
```

Assertion historique en échec :

```python
assert 'Groupe surveillé' in live
```

Constat : la RC29.3 conserve le sélecteur de groupe dans le cockpit Live, mais le libellé textuel exact `Groupe surveillé` n'est plus présent depuis la simplification de l'interface.

Le test vérifie donc un **texte de présentation historique**, et non l'existence fonctionnelle du filtre de groupe. Il n'a pas été modifié pendant cette étape, car l'étape 1 autorisait uniquement les trois tests explicitement nommés par l'utilisateur.

### FAIL 2 — `live_center_completeness_test.py`

Test :

```text
test_live_center_ui_uses_requested_agent_label_and_hides_uncertified_cards
```

Assertion historique en échec :

```python
assert 'États Live des agents' in js
```

Constat : le texte exact `États Live des agents` a été retiré lors de la simplification RC29.3 du Centre Live. Les données/états agents restent rendus dans la vue Agents ; c'est le titre de présentation qui a changé/disparu.

Ce test n'a pas été modifié pour la même raison : il ne faisait pas partie des trois réalignements autorisés à l'étape 1.

## 3. Aucun test silencieusement exclu

- Les **33 fichiers `*test.py` racine** ont été passés à la même commande pytest.
- Aucun `-k`, `--ignore`, `--deselect` ou exclusion ciblée n'a été utilisé.
- Aucun test collecté n'a été SKIP.
- Les deux validateurs autonomes nécessitant `--zip` sont documentés ci-dessus ; pytest les reçoit mais collecte 0 test, car ils ne définissent pas de fonction `test_*`.
- Les 2 FAIL sont laissés visibles dans le verdict consolidé ; ils ne sont ni masqués ni reclassés en PASS.

## 4. Gate RC29 Phase 7 — vérifications locales

Le préflight local a été exécuté dans le même environnement.

Résultats :

- Python >= 3.10 : **PASS**
- dépendance `reportlab` : **PASS**
- dépendance `websockets` : **PASS**
- client HTTP standard : **PASS**
- syntaxe Python : **PASS**
- `TECHIN_Stock_Manager.db` : `quick_check=ok`
- `NELYIO_Supervision.db` : `quick_check=ok`
- `Nelyio_Details.db` : `quick_check=ok`
- `Nelyio_Live.db` : `quick_check=ok`
- configuration Caddy locale : préservée
- recette Windows/HTTPS/Hermes : **NON VÉRIFIÉE EN PRODUCTION**, conformément aux limites du chantier

### Intégrité manifeste : FAIL attendu après étape 1

Le préflight signale :

```text
ECHEC - Integrite du code : audit_regression_test.py; live_operations_phase15_test.py
```

Cause prouvée : ces deux tests ont été modifiés volontairement à l'étape 1, alors que `MANIFEST_PRODUCTION.json` contient encore leurs empreintes antérieures.

Ce résultat n'est pas masqué. Le manifeste n'a pas été régénéré pendant l'étape 2, qui est une étape de **validation**, pas de packaging. Son réalignement devra être effectué dans un changement de packaging/documentation explicitement validé, après stabilisation des fichiers finaux.

## 5. Restauration BDD / WAL / SHM / logs

Avant les tests, un snapshot exact a été réalisé de :

- tous les `*.db`
- tous les `*.db-wal`
- tous les `*.db-shm`
- tous les `*.db-journal`
- tous les fichiers présents dans `logs/`

Les tests ont effectivement modifié temporairement :

- `NELYIO_Supervision.db`
- `Nelyio_Live.db`
- `logs/nelyio_errors.log`

Après l'exécution, ces artefacts ont été restaurés depuis le snapshot initial.

Contrôle SHA-256 final :

```text
runtime_before.sha256 == runtime_restored.sha256
```

Résultat : **RESTORE_OK**.

Aucune donnée de test, aucun WAL/SHM temporaire et aucune trace runtime nouvelle ne reste dans la copie de travail.

## 6. Verdict étape 2

### Validation consolidée

**237 PASS / 2 FAIL / 0 SKIP**.

Les 2 FAIL restants correspondent à deux assertions de **libellés UI historiques RC29.2/antérieurs** qui ne reflètent plus les intitulés du cockpit RC29.3. Ils sont explicitement conservés comme FAIL tant que l'utilisateur n'autorise pas leur réalignement.

### Gate local

Les contrôles Python/SQLite passent. Le gate d'intégrité du manifeste reste **FAIL** car deux fichiers de test volontairement modifiés à l'étape 1 n'ont pas encore leurs nouvelles empreintes dans `MANIFEST_PRODUCTION.json`.

### Production

Les points suivants restent inchangés et **NON MESURÉS / NON VÉRIFIÉS EN PRODUCTION** :

- PostgreSQL réel ;
- `EXPLAIN (ANALYZE, BUFFERS)` ;
- contention/verrous PostgreSQL réels ;
- HTTPS/Caddy sur le serveur cible ;
- réseau LAN/VPN ;
- Hermes réel ;
- import SIMPLIFY2 réel en parallèle ;
- 5 utilisateurs authentifiés sur données métier réelles ;
- rendu navigateur / Long Tasks en production.

## STOP

L'étape 3 (document opérateur `docs/current/LIRE_NELYIO_ARCH_V60_5_RC29_3.md`) n'a pas été commencée.

Attente de validation utilisateur avant toute suite.
