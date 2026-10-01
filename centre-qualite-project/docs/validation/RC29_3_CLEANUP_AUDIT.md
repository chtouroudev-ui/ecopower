# RC29.3 — AUDIT DE RANGEMENT / NETTOYAGE

Date : 2026-09-28
Base auditée : Nelyio-ARCH V60.5 RC29.3 LIVE_SIMPLE
Mode : **AUDIT UNIQUEMENT — aucun déplacement, aucune suppression**

## 0. Garde-fous appliqués

Aucun fichier `.db`, `.db-wal`, `.db-shm`, `.db-journal` n'a été déplacé ni supprimé.
`TECHIN_Stock_Manager.db` est signalée comme base apparemment extérieure au coeur Nelyio, mais elle est conservée intacte.
Aucun `LIRE_NELYIO_ARCH_V60_5_RC*.md` n'a été supprimé ni déplacé.
Au moment de l'audit initial, aucun `PATCH_BACKUP_*` n'avait encore été supprimé ni déplacé.
Le dossier `files/` n'a pas été supprimé ni déplacé.
Aucun fichier référencé par un `.bat`, `.ps1`, manifeste ou launcher n'a été renommé ou déplacé.

---

## 1. Code applicatif Python à la racine

### Constat

- **144 fichiers `.py`** sont présents à la racine.
- Analyse AST des imports internes : **1 046 relations d'import internes** impliquant **103 modules référencés**.
- Modules fortement centraux observés : `supervision_db.py`, `db_compat.py`, `nelyio_time.py`, `app_db.py`, `error_log.py`, `access_control.py`, `live_quality.py`, `quality_scope.py`, `quality_metrics.py`, `collection_store.py`, `app_config.py`, `supervision_utils.py`, etc.

### Proposition théorique

Une structure cible pourrait conceptuellement séparer :

- `routes/` : `routes_*.py`, `supervision_routes.py`, `http_handler.py` ;
- `services/` : services transverses, auth, import, rétention ;
- `live/` : modules Live, capture, campagnes, qualité Live ;
- `quality/` : moteurs qualité, distributions, agents, scope ;
- `analytics/` : analytics/pilotage/rapports ;
- `tests/` : tests et benchmarks.

### Décision recommandée pour RC29.3

**NE PAS EFFECTUER cette restructuration dans RC29.3.**

Motif : déplacer ces modules imposerait une mise à jour massive et atomique des imports Python, imports dynamiques, launchers, tests, manifestes et potentiellement des chemins d'exécution Windows. Dans un chantier de gel/consolidation, le risque de régression dépasse largement le bénéfice de rangement.

Recommandation : conserver la topologie Python actuelle pendant le gel RC29.3. Une refonte de packaging ne devrait être envisagée que dans une branche/version dédiée avec suite consolidée verte avant/après.

---

## 2. Documentation `.md`

### Référence opérateur actuelle

- `docs/current/LIRE_NELYIO_ARCH_V60_5_RC29_3.md` : **référence opérateur courante**.
- `docs/current/RC29_SPEC.md` : spécification consolidée RC29.
- `docs/validation/RC29_3_CONSOLIDATED_VALIDATION.md` : preuve de validation consolidée.
- `docs/validation/RC29_3_CENTRE_LIVE_SIMPLE_VALIDATION.md` : preuve UI RC29.3.
- `docs/validation/RC29_3_STEP1_TEST_REALIGNMENT.md` : preuve du réalignement des 3 tests.

### Historique à conserver

Les familles suivantes doivent être conservées comme historique et **ne sont pas des candidats à suppression** :

- tous les `LIRE_NELYIO_ARCH_V60_5_RC*.md` ;
- `RC29_PHASE*_VALIDATION.md` ;
- `PHASE*_VALIDATION_REPORT.md` ;
- `V59*_VALIDATION_REPORT.md`, `V60*_VALIDATION_REPORT.md` ;
- `VALIDATION_POSTGRESQL_*.md`, `VALIDATION_RECUPERATION_POSTGRES_*.md` ;
- documents de diagnostic/performance ayant servi de preuve de migration ou de stabilisation.

`docs/history/releases/LIRE_NELYIO_ARCH_V60_5_RC29_1.md` est **remplacé opérationnellement** par RC29.3, mais reste un historique obligatoire conformément aux règles du chantier.

### Proposition de rangement future, sans suppression

Après validation, une structure documentaire sûre serait :

- `docs/current/` : `docs/current/LIRE_NELYIO_ARCH_V60_5_RC29_3.md`, `docs/current/RC29_SPEC.md`, documents de production actuels ;
- `docs/validation/` : rapports RC29.3 et validations actuellement utiles ;
- `docs/history/releases/` : anciens `LIRE_NELYIO_ARCH_V60_5_RC*.md` ;
- `docs/history/validation/` : anciens rapports PHASE/V59/V60/PostgreSQL ;
- `docs/history/performance/` : anciens diagnostics/benchmarks.

**Aucune suppression documentaire n'est proposée dans cet audit.** Le critère « contenu entièrement remplacé » n'est pas suffisant pour supprimer une preuve historique de release ou de validation.

---

## 3. Scripts `.bat` / `.ps1` / `.cmd` / `.vbs`

### Inventaire

**68 scripts** à la racine ont été recensés.

Recherche effectuée pour chaque script :

1. référence exacte du nom dans tous les autres `.bat/.ps1/.cmd/.vbs` ;
2. référence exacte dans tous les `LIRE_*.md` ;
3. pour les candidats sans référence dans ces deux catégories, recherche globale complémentaire dans Python, JS, documentation, tests, `SHA256_FILES.txt` et `MANIFEST_PRODUCTION.json`.

### Scripts sans appel par un autre script ET sans mention dans `LIRE_*.md`

Les 14 fichiers suivants satisfont uniquement ce premier filtre :

- `AJOUTER_EXEMPLES_DEMO.cmd`
- `APPLIQUER_INDEX_PERFORMANCE_POSTGRESQL.bat`
- `CHECK_NELYIO_HTTPS.bat`
- `DIAGNOSE_POSTGRESQL.bat`
- `DIAGNOSTIC_FRONTEND.cmd`
- `EXPLAIN_POSTGRESQL_PERFORMANCE.bat`
- `INSTALL_CAPTURE_DEPENDENCIES.bat`
- `INSTALL_NELYIO_AUTOSTART.bat`
- `INSTALL_PATCH.bat`
- `OPEN_EDGE_CAPTURE.bat`
- `OPEN_LOCAL.bat`
- `OPEN_NELYIO_CONTROL_PANEL.bat`
- `RECUPERER_CONFIG_POSTGRESQL_EXISTANTE.bat`
- `RUN_BACKEND_9051_V46.bat`

### Preuve complémentaire et conclusion

Aucun de ces 14 scripts n'est proposé à la suppression :

- **tous les 14** sont référencés par `SHA256_FILES.txt` et/ou `MANIFEST_PRODUCTION.json` ;
- `APPLIQUER_INDEX_PERFORMANCE_POSTGRESQL.bat` est aussi cité dans `docs/history/performance/BENCHMARK_PERFORMANCE.md` ;
- `INSTALL_CAPTURE_DEPENDENCIES.bat` est référencé par `recording_sizes.py`, `collection_cdp.py` et `static/collection.js` ;
- `INSTALL_PATCH.bat` est cité par les README de patch ;
- `OPEN_EDGE_CAPTURE.bat` est référencé par `static/collection.js`.

Donc, au sens strict du critère de suppression demandé (« aucun import Python, aucun script, aucun manifeste, aucun test »), **aucun fichier de ce groupe n'est supprimable aujourd'hui**.

### Recommandation

- Ne supprimer aucun script dans RC29.3.
- Après validation, on peut éventuellement **archiver** certains diagnostics historiques dans `tools/history/`, mais uniquement en mettant à jour dans le même lot toutes les références de manifeste/launcher/documentation concernées et en relançant la suite consolidée.

---

## 4. Dossier `files/`

### Contenu Python observé

`files/` contient notamment :

- `calls.py`
- `nelyio_importer_app.py`
- `quality_importer.py`
- `quality_service.py`
- `supervision_db.py`
- `supervision_routes.py`
- `supervision_utils.py`

ainsi qu'un sous-dossier `files/static/`.

### Comparaison avec les modules racine

Les doublons apparents **ne sont pas identiques** aux modules racine :

- `calls.py` : version `files/` plus ancienne ; elle ne contient pas plusieurs correctifs récents présents à la racine, notamment masquage/visibilité ANI, scopes agents et tri serveur RC29.
- `supervision_db.py` : version `files/` plus ancienne ; elle ne contient pas plusieurs schémas/configurations ajoutés ensuite (par exemple historique Live et paramètres d'enregistrement visibles dans le diff).
- `supervision_routes.py` : version `files/` plus ancienne ; les contrôles d'accès/scopes et plusieurs routes diffèrent sensiblement de la racine.
- `supervision_utils.py` : version `files/` plus ancienne ; elle ne contient notamment pas la reconnaissance explicite HOLD et `inactive_context` ajoutée en RC29.

### Usage identifié

Le dossier n'est pas totalement orphelin :

- `INSTALL_PATCH.ps1` référence explicitement `files\quality_importer.py` et `files\static\groups.js` comme sources de patch.
- `OPEN_NELYIO_IMPORTER.bat` lance `nelyio_importer_app.py` à la **racine**, pas `files/nelyio_importer_app.py`.
- plusieurs modules et documents font référence au workflow Importer autonome, mais cela ne prouve pas à lui seul l'usage runtime des quatre doublons `calls.py/supervision_*.py` dans `files/`.

### Conclusion

**NE PAS supprimer `files/`.**

Il existe un doute légitime sur son rôle exact : bundle historique de patch/importer ou source de réparation. Comme certains éléments sont explicitement consommés par `INSTALL_PATCH.ps1`, supprimer le dossier casserait au minimum ce workflow. Avant toute réduction future, il faudrait cartographier fichier par fichier ce que `INSTALL_PATCH.ps1` et les éventuels packages de mise à jour consomment réellement.

---

## 5. `PATCH_BACKUP_*`

Dossiers recensés :

- `PATCH_BACKUP_GROUPS_CALLS_20260925_123737`
- `PATCH_BACKUP_GROUPS_CALLS_IMPORT_20260925_125143`
- `PATCH_BACKUP_V3_GROUPS_MULTI_IMPORT_20260925_130512`
- `PATCH_BACKUP_V4_DIAGNOSTIC_CALLS_20260925_133945`
- `PATCH_BACKUP_V5_CAMPAIGNS_20260925_135356`

Conformément aux règles du chantier : **aucune suppression n'est proposée**.

Proposition de rangement future uniquement : déplacer ces dossiers, après validation, sous `backups/patches/` en conservant leurs noms intacts. Ce déplacement devra être réalisé dans un lot dédié, puis suivi de la suite consolidée avant toute autre opération.

---

## 6. Bases runtime

Bases/fichiers runtime visibles à la racine, notamment :

- `NELYIO_Supervision.db` et WAL/SHM associés ;
- `Nelyio_Live.db` ;
- `Nelyio_Details.db` et fichiers associés ;
- `TECHIN_Stock_Manager.db`.

**Aucune action proposée.**

`TECHIN_Stock_Manager.db` paraît extérieure au coeur fonctionnel Nelyio d'après son nom, mais aucune conclusion de suppression ou déplacement n'est autorisée sans preuve d'usage et les règles interdisent de déplacer/supprimer les bases runtime.

---

## 7. Candidats à suppression

**AUCUN.**

L'audit n'a identifié aucun fichier satisfaisant simultanément les preuves exigées pour une suppression sûre. En particulier, les scripts apparemment non utilisés par d'autres scripts restent présents dans les manifestes ou sont référencés ailleurs.

Cette absence de candidat est volontairement conservatrice et cohérente avec un chantier de gel.

---

## 8. Plan de rangement proposé pour validation, catégorie par catégorie

### Lot A — Documentation

Proposition : créer `docs/current/`, `docs/validation/`, `docs/history/releases/`, `docs/history/validation/`, `docs/history/performance/`, puis **déplacer uniquement** les documents validés, jamais les effacer.

Risque : faible à moyen, car certains `.md` sont cités dans d'autres documents/manifeste. Toutes les références devront être mises à jour dans le même lot.

### Lot B — PATCH_BACKUP

Proposition : créer `backups/patches/` et déplacer les cinq `PATCH_BACKUP_*` sans suppression.

Risque : faible, mais recherche de références à refaire juste avant déplacement.

### Lot C — Scripts historiques

Proposition : **aucun déplacement maintenant**. Faire d'abord une validation manuelle de la liste des 14 scripts sans lien script/LIRE. Certains restent manifestés ou utilisés indirectement. Une éventuelle archive devra mettre à jour les manifestes/références dans le même lot.

### Lot D — `files/`

Proposition : **aucune action** tant que le rôle de bundle/patch n'est pas résolu fichier par fichier.

### Lot E — Code Python racine

Proposition : **aucune action dans RC29.3**. Reporter toute restructuration de package à une version dédiée.

---

## 9. Règle de validation après chaque lot futur

Après chaque lot explicitement validé :

1. mettre à jour toutes les références dans le même changement ;
2. exécuter la suite consolidée de `docs/validation/RC29_3_CONSOLIDATED_VALIDATION.md` ;
3. restaurer les bases/WAL/SHM/logs après tests ;
4. comparer les artefacts runtime avant/après ;
5. documenter le lot dans ce fichier ;
6. ne jamais supprimer un fichier dans le même lot que son déplacement initial.

---

## 10. Verdict audit

Le projet contient beaucoup d'historique, mais le principal risque serait de confondre **encombrement** et **inutilité**.

Recommandation de gel :

- **oui** au rangement documentaire par déplacement contrôlé ;
- **oui** à l'archivage des `PATCH_BACKUP_*` par déplacement uniquement ;
- **non** à une restructuration Python dans RC29.3 ;
- **non** à la suppression de `files/` ;
- **non** à toute suppression de script à ce stade ;
- **aucune base runtime à toucher**.

Aucune modification physique n'a été effectuée pendant cet audit.


---

## 11. Lot A1 applique — documentation RC29.3 non manifestee

Validation utilisateur recue le 2026-09-28 via « continuer pour la phase suivante ».

Deplacements effectues, sans suppression :

- `LIRE_NELYIO_ARCH_V60_5_RC29_3.md` -> `docs/current/LIRE_NELYIO_ARCH_V60_5_RC29_3.md`
- `RC29_3_CONSOLIDATED_VALIDATION.md` -> `docs/validation/RC29_3_CONSOLIDATED_VALIDATION.md`
- `RC29_3_STEP1_TEST_REALIGNMENT.md` -> `docs/validation/RC29_3_STEP1_TEST_REALIGNMENT.md`
- `RC29_3_CLEANUP_AUDIT.md` -> `docs/validation/RC29_3_CLEANUP_AUDIT.md`

Ces quatre fichiers ne figuraient pas dans `MANIFEST_PRODUCTION.json`; aucun changement de `deploy_release.py` ni du manifeste de production n'a donc ete necessaire pour ce lot. Les references textuelles internes ont ete remplacees par les nouveaux chemins.

Aucun document historique manifeste n'a ete deplace dans A1. Le sous-lot A2 reste en attente, car `deploy_release.py` n'autorise pas encore `docs/` pour les fichiers manifestes.

### Validation du lot A1

Suite consolidée relancée après déplacement : **237 PASS / 2 FAIL / 0 SKIP**. Les deux FAIL sont strictement les deux assertions UI historiques déjà documentées avant le lot (`Groupe surveillé` et `États Live des agents`) ; **aucun nouvel échec n'a été introduit par le rangement A1**.

Gate local : syntaxe Python OK, 4 SQLite `quick_check` OK. L'intégrité du manifeste reste en échec sur `audit_regression_test.py` et `live_operations_phase15_test.py`, déjà modifiés à l'étape 1 et non ré-empreintés ; ce point préexistait au lot A1.

Après tests, bases/WAL/SHM/logs restaurés et comparaison SHA-256 : **RESTORE_OK**.

Statut : **Lot A1 validé techniquement, A2 non commencé**.


## 9. Journal des lots appliqués

### Lot A1 — documentation RC29.3 non manifestée

- Déplacée vers `docs/current/` et `docs/validation/`.
- Aucun contenu supprimé.
- Validation consolidée après lot : état identique à avant rangement (237 PASS / 2 FAIL historiques connus / 0 SKIP).

### Lot A2 — documentation manifestée

- Documents manifestés déplacés vers `docs/current/`, `docs/validation/` et `docs/history/...` selon leur rôle.
- `deploy_release.py` autorise désormais uniquement les fichiers `.md` sous `docs/`.
- `MANIFEST_PRODUCTION.json`, `SHA256_FILES.txt` et les références textuelles ont été mis à jour dans le même lot.
- `upgrade_from` conserve les chemins historiques afin de rester compatible avec les installations antérieures.
- Aucune suppression effectuée.
- Validation consolidée après lot : **237 PASS / 2 FAIL historiques connus / 0 SKIP** ; aucun nouvel échec lié au déplacement.
- Préflight local : **PASS** (intégrité, syntaxe Python, 4 SQLite `quick_check OK`).
- Restauration bases/WAL/SHM/logs : **RESTORE_OK**.
- Simulation `deploy_release.py` avec chemins `docs/...` : **PASS**.

---

## Lot B — Archivage des PATCH_BACKUP_* — EXÉCUTÉ

Validation utilisateur : accord reçu via « continuer pour la phase suivante ».

Actions réalisées, sans suppression :

- `PATCH_BACKUP_GROUPS_CALLS_20260925_123737/` → `backups/patches/PATCH_BACKUP_GROUPS_CALLS_20260925_123737/`
- `PATCH_BACKUP_GROUPS_CALLS_IMPORT_20260925_125143/` → `backups/patches/PATCH_BACKUP_GROUPS_CALLS_IMPORT_20260925_125143/`
- `PATCH_BACKUP_V3_GROUPS_MULTI_IMPORT_20260925_130512/` → `backups/patches/PATCH_BACKUP_V3_GROUPS_MULTI_IMPORT_20260925_130512/`
- `PATCH_BACKUP_V4_DIAGNOSTIC_CALLS_20260925_133945/` → `backups/patches/PATCH_BACKUP_V4_DIAGNOSTIC_CALLS_20260925_133945/`
- `PATCH_BACKUP_V5_CAMPAIGNS_20260925_135356/` → `backups/patches/PATCH_BACKUP_V5_CAMPAIGNS_20260925_135356/`

`INSTALL_PATCH.ps1` a été mis à jour dans le même lot afin que les futures sauvegardes V5 soient créées sous `backups/patches/` au lieu de la racine. Le nom `PATCH_BACKUP_V5_CAMPAIGNS_<timestamp>` reste inchangé.

Aucun contenu des sauvegardes historiques n'a été modifié. Aucun fichier de base de données n'a été déplacé ou supprimé.

La validation consolidée et le préflight sont relancés après ce lot ; leurs résultats sont consignés ci-dessous après exécution.

Résultat du Lot B :

- suite consolidée : **237 PASS / 2 FAIL historiques connus / 0 SKIP** ;
- aucun nouvel échec lié au déplacement `PATCH_BACKUP_*` ;
- les deux FAIL restent `Groupe surveillé` et `États Live des agents` ;
- snapshot/restauration des bases, WAL/SHM et logs : **RESTORE_OK** ;
- préflight final après mise à jour des empreintes : **PASS** ;
- intégrité du contenu des 5 sauvegardes après déplacement : **BACKUP_CONTENT_OK** (17 fichiers identiques octet pour octet).
