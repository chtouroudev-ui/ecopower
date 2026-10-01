# NELYIO V60.5 RC29.3 — version courante

Build courant : **60.5-ARCH-RC29.3 / V60.5-RC29.3**. Commencer par **`docs/history/releases/LIRE_NELYIO_ARCH_V60_5_RC29_1.md`** puis **`docs/current/RC29_SPEC.md`**.

RC29.3 simplifie le **Centre Qualité Live** : vue Agents par défaut en pleine largeur, KPI dans un rail latéral compact, Campagnes/Périmètres en vue alternative et Double vue optionnelle. Les détails qualité/alertes/limites sont regroupés derrière un seul bouton. La QoS et les règles métier RC29.1 restent inchangées.

RC29.1 consolide les phases RC29 validées et corrige la règle QoS globale : **Traités / (Reçus - Clôturés - Raccrochés avant file d’attente) × 100**. Le Centre Live desktop est organisé en poste de supervision dense avec **Agents à gauche** et **Campagnes/Périmètres à droite**, afin d’éviter le défilement vertical global permanent.

Le plan RC29 est terminé. Les anciens rapports `PHASE8+` présents dans l’archive sont historiques et ne constituent pas la suite du plan RC29. La prochaine étape est la **recette réelle sur serveur Windows/PostgreSQL/Caddy/Hermes**, pas une nouvelle phase fonctionnelle implicite.

---

# NELYIO V60.4 — correctif PostgreSQL mesuré

Build courant : **60.4-POSTGRES-HOTFIX**. Commencer par **`docs/history/releases/LIRE_V60_4_POSTGRES_FIX.md`**, **`docs/history/validation/V60_4_VALIDATION_REPORT.md`** et **`docs/history/performance/POSTGRESQL_TUNING_V60_4.md`**.

V60.4 cible les goulots mesurés sur le PostgreSQL réel du 25/09/2026 : **Détails jusqu’à 133 s / requête SQL max 92 s**, **Analytics à 997 requêtes SQL**, et **roster Équipe & Files triant ~607 000 lignes pour ~103 agents**. Le correctif borne le catalogue agents au dernier import ACTIVE, charge les références `active_days` en une seule requête par période, supprime le N+1 avant/après des fermetures probables et ajoute deux index ciblés non destructifs.

Les fichiers JavaScript utilisent maintenant des cache-busters **V60_4-<hash>** afin qu’un navigateur ne conserve pas un ancien frontend `RC2G` après mise à jour. **Aucune base métier n’est reset.**

---

# NELYIO V60.3 — production finale mesurée

Build courant : **60.3-PROD-FINAL**. Commencer par **`docs/history/releases/LIRE_V60_3_PRODUCTION.md`**, **`docs/history/performance/DIAGNOSTIC_PERFORMANCE.md`** et **`docs/history/performance/BENCHMARK_PERFORMANCE.md`**.

V60.3 finalise le chantier performance avec diagnostic HAR mesuré, instrumentation Backend/SQL/JSON, requêtes Support/Recherche d’appels set-based et paginées, polling Groupes léger, optimisation Équipe & Files/Priorités, import snapshot/staging, Live isolé et visible directement, et outils PostgreSQL read-only pour capturer `pg_stat_statements`, locks et `EXPLAIN (ANALYZE, BUFFERS)` sur le vrai serveur. **Aucune base métier n’est reset.**

Qualité Agents conserve les corrections `Travail` / `Moy. appel entrant` et ajoute **`Appels < 10 s`** (CallDuration valide strictement inférieur à 10 secondes).

---

# NELYIO V60 - architecture production isolée

Build courant : **60.0-PROD-ARCH**. Commencer par **`docs/history/releases/LIRE_V60_PRODUCTION.md`** puis **`docs/history/validation/V60_VALIDATION_REPORT.md`**.

V60 sépare les trois charges qui se bloquaient mutuellement : **Web/API**, **Importer local** et **Live Nelyio**. En production, le Web ne scanne plus le dossier import, n'exécute plus d'import lourd et ne reprend plus un calcul Analytics lourd en fallback. Le Live utilise sa propre base SQLite/WAL et ne conserve que la journée courante.

Pour importer un ZIP SIMPLIFY2 ou `group.har`, lancer **`OPEN_NELYIO_IMPORTER.bat`** directement sur le serveur.

---

# NELYIO V59 - production hardened

Build courant : **59.1-PROD-STABLE**. Commencer par **`docs/history/releases/LIRE_V59_PRODUCTION.md`** puis **`docs/history/validation/V59_VALIDATION_REPORT.md`**.

V59 durcit le cycle Start/Stop/HTTPS, isole les lectures Qualite/Support lourdes dans le worker Analytics, corrige la projection Groupes `files -> agents ACTIVE`, deplace la recuperation d archives hors des requetes Web et ajoute les index PostgreSQL requis.

---

# NELYIO RC2M - demarrage HTTPS et performances

Correctif production groupes/durees/performance : `docs/history/releases/LIRE_OPTIMISATION_PROD_RC2M.md`.

**Caddy n'est plus embarque dans ce ZIP.** Placez `caddy.exe` soit a la racine du projet, soit dans `tools/`, soit dans le `PATH`, ou definissez `NELYIO_CADDY_EXE`. Lancez ensuite `START_NELYIO_HTTPS.bat`. Le fichier `Caddyfile` a la racine publie HTTPS sur 9050 et reverse-proxy le backend local 9051. `NELYIO_CADDY.ps1` permet `Start`, `Stop`, `Status`, `Validate` et `Trust`.

Le lanceur verifie maintenant le meme identifiant de build que `/healthz`, ce qui evite de tuer un backend sain a cause d'un decalage VERSION/backend.

---

> **Version RC2K GROUPES ACTIVE + MOYENNE APPELS — 23/09/2026** : lire `docs/history/releases/LIRE_RC2K_GROUPES_ACTIVE_MOYENNE_APPELS.md`.

# Nelyio V56.18 MS1 — PostgreSQL RC2K GROUPES ACTIVE + MOYENNE APPELS

Commencer par **docs/current/LIRE_AVANT_PRODUCTION.md**.

Ordre recommandé sur un nouveau serveur :

1. `INSTALL_DEPENDENCIES.bat`
2. `CONFIGURER_POSTGRESQL_AUTO.bat`
3. `VALIDATION_PRODUCTION.bat`
4. `START_NELYIO.bat`
5. `VALIDER_APRES_DEMARRAGE.bat`
6. importer un SIMPLIFY2 de contrôle
7. `VALIDER_QUALITE.bat YYYY-MM-DD`
8. `SAUVEGARDER_POSTGRESQL.bat`

Ne pas écraser une ancienne installation : extraire chaque candidat dans un nouveau dossier.


## RC2B - postgres.env absent

Si PostgreSQL est deja migre mais qu'aucun ancien `data\postgres.env` n'est disponible, utilisez `RECREER_CONFIG_POSTGRESQL_EXISTANTE.bat`. Ce script recree les identifiants applicatifs et le fichier local sans supprimer ni re-migrer la base `nelyio`.


## PROD RC2C
RC2C corrige le `InFailedSqlTransaction` observe pendant la reparation PostgreSQL et le `KeyError: export_offset`. Sur une base PostgreSQL deja creee, ne relancez pas une migration reset : reutilisez/recreez `data\postgres.env`, puis lancez `VERIFIER_POSTGRESQL.bat` et `VALIDATION_PRODUCTION.bat`.


## PROD RC2D — API PostgreSQL runtime

PostgreSQL utilise le port standard **5432** par defaut. Si l'interface se charge et qu'une route `/api/...` repond en HTTP 500, le port n'est pas la cause : le backend et le proxy sont deja joignables. RC2D corrige les requetes Dashboard incompatibles avec PostgreSQL, durcit Classification/Retention, et ajoute ces trois domaines au preflight.

Avant demarrage : `VERIFIER_POSTGRESQL.bat`, puis `VALIDATION_PRODUCTION.bat`. Le smoke test doit mentionner Dashboard, Classification et Retention sans echec.


## PostgreSQL PROD RC2E

- Corrige le Dashboard PostgreSQL quand `derniere_vue` est un alias de `MAX(date_evenement)`.
- Corrige la meme construction dans le detail PC.
- Le smoke test PostgreSQL execute maintenant exactement les requetes runtime partagees.
- Aucun reset ni nouvelle migration PostgreSQL n est requis pour passer de RC2D a RC2E.

## RC2J — Groupes analytiques globaux

Tous les filtres métier Groupe utilisent désormais les files configurées et les affectations actives/partielles. `user_group_members` reste réservé à l’Administration et aux permissions. Voir `docs/history/releases/LIRE_RC2J_GROUPS_GLOBAL.md`.



## RC2K — groupes analytiques et Moy. appel entrant

- Groupe analytique = files configurées du groupe.
- Membre = agent affecté à au moins une de ces files avec statut **ACTIVE uniquement**.
- `partial`, `inactive` et `unknown` ne donnent pas l’appartenance au groupe.
- Cette règle est utilisée par les filtres analytiques; les groupes de permissions Administration restent séparés.
- `Moy. appel entrant` est reconstruite depuis les activités `Stats.AGENT` déjà importées.
- Voir `docs/history/releases/LIRE_RC2K_GROUPES_ACTIVE_MOYENNE_APPELS.md` pour les tests et limites.
