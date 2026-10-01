# Nelyio RC2M — réparation HTTPS, groupes et performances

## Diagnostic confirmé

### 1. HTTPS ne démarrait pas correctement
`production_http.py` annonçait le build `56.18-MS1-RC2M-CSP-GROUP-PERF`, alors que `VERSION.json` annonçait encore `56.18-MS1-RC2L`.
Le lanceur HTTPS exige une correspondance exacte entre `VERSION.json` et `/healthz` : un backend sain RC2M était donc considéré comme invalide puis arrêté/rejeté.

Le projet embarquait aussi ~48 Mo de Caddy sous `security/Caddy/`. Ce binaire et tous les anciens scripts Caddy embarqués ont été retirés à la demande.

### 2. Les filtres Groupe pouvaient retourner zéro ligne
Deux causes indépendantes ont été trouvées :

- `data/quality_priorities.json` livré dans cette archive ne contient aucune affectation agent → file. Or la règle analytique voulue est strictement `Groupe -> files configurées -> agents ACTIVE sur ces files`.
- Support, Détails et Analyse proposaient parfois les groupes de l'annuaire administratif dans les listes de filtre, alors que le backend filtrait avec les groupes analytiques basés sur les files. Un groupe administratif sans file était donc sélectionnable mais ne pouvait correspondre à aucune ligne.

La réparation conserve la règle métier : les membres administratifs ne sont jamais utilisés pour fabriquer artificiellement les KPI Groupe.

### 3. Lenteurs
Plusieurs coûts cumulatifs ont été trouvés :

- le scope analytique Groupe était reconstruit toutes les 2 secondes malgré des invalidations explicites déjà présentes ;
- en PostgreSQL, une nouvelle connexion TCP était ouverte pour presque chaque `db_connect()` ;
- lors d'un changement rapide d'interface/filtre, le navigateur ignorait visuellement l'ancienne réponse mais ne stoppait pas réellement l'ancienne requête GET, qui continuait à consommer du backend/PostgreSQL ;
- les catalogues Groupe pouvaient être recalculés/relus alors que leur configuration n'avait pas changé.

## Corrections appliquées

- Build runtime aligné partout sur `56.18-MS1-RC2M-CSP-GROUP-PERF`.
- Nouveau `NELYIO_CADDY.ps1` : `Start`, `Stop`, `Status`, `Validate`, `Trust`.
- Caddy devient externe : recherche dans `NELYIO_CADDY_EXE`, la racine, `tools/caddy.exe`, puis le `PATH`.
- Nouveau `Caddyfile` racine : HTTPS 9050 -> backend local 9051.
- Suppression complète de `security/Caddy/` et de `caddy.exe` du paquet.
- Récupération automatique, si possible, du dernier snapshot `Agents.csv` valide dans `import_archive` lorsqu'aucune affectation agent/file n'est disponible localement.
- Refus d'utiliser les affectations observées/demo ou les membres administratifs comme faux membres analytiques.
- Catalogues de filtres Support/Détails/Analyse alignés sur les groupes ayant réellement au moins une file configurée.
- Les agents multi-groupes conservent tous leurs `group_ids` analytiques.
- Cache Groupe porté à 300 s avec empreinte légère + fichier de révision inter-processus ; toute modification/import officiel invalide immédiatement le cache.
- `group.har` invalide maintenant aussi le cache analytique inter-processus après mise à jour.
- Pool PostgreSQL in-process borné (`NELYIO_PG_POOL_IDLE`, 4 connexions inactives par schéma par défaut) pour réutiliser les connexions propres.
- Annulation des GET obsolètes via `AbortController` lors des changements de vue.
- Nettoyage des caches Python/pytest, anciens résultats d'audit/validation, journaux de test et dossier Caddy embarqué.

## Validation locale du paquet réparé

- `pytest -q` : **49/49 tests OK**.
- Test frontend de concurrence/navigation : **PASS**.
- Test synthétique de récupération `Agents.csv` depuis l'archive : **OK**.
- Test synthétique catalogue Groupe : seuls les groupes avec files sont proposés : **OK**.
- Test du pool PostgreSQL acquisition/libération : **OK**.
- `compileall` Python : **OK**.
- Preflight de l'intégrité du paquet : **OK**.
- SQLite `quick_check` sur les quatre bases livrées : **OK**.
- Benchmark isolé, 60 000 appels / 30 jours / 50 agents :
  - Qualité agents médiane : ~0,145 s
  - Qualité de service médiane : ~0,911 s
  - Distributions médiane : ~0,487 s
  - 5 vues Qualité agents concurrentes : ~1,56 s, résultats corrects

Le sandbox de validation est Linux : la syntaxe Python/JS et la logique des lanceurs ont été contrôlées, mais le démarrage natif Windows + Caddy + votre PostgreSQL réel doit être validé sur votre serveur.

## Mise en production

1. Conserver votre vrai `data/postgres.env`, vos données PostgreSQL et vos archives d'import de production.
2. Télécharger `caddy.exe` séparément, puis le placer à la racine du projet, dans `tools/`, dans le `PATH`, ou définir `NELYIO_CADDY_EXE`.
3. Lancer `START_NELYIO_HTTPS.bat`.
4. Pour vérifier : `NELYIO_CADDY.ps1 -Action Status` puis `DIAGNOSTIC_9050_9051_V50.ps1`.
5. Si un groupe correctement configuré avec des files affiche encore 0 agent et qu'aucune archive SIMPLIFY2 exploitable n'existe sur ce serveur, réimporter une fois le dernier export SIMPLIFY2 contenant `Agents.csv`/`Queues`. Ensuite les membres sont recalculés automatiquement depuis les affectations ACTIVE.

`requirements.txt` demande déjà `requests==2.33.0`. Le warning Requests observé pendant le preflight provient uniquement de l'environnement de test, qui utilise encore 2.32.5.
