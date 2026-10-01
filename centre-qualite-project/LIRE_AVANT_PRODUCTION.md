> **RC29.1 — RÈGLE COURANTE (28/09/2026)** : la QoS Nelyio à utiliser partout est **Appels traités / (Appels reçus - Appels clôturés - Raccrochés avant file d’attente) × 100**. Si le dénominateur est nul ou négatif, afficher `—`. Toute formule historique différente ci-dessous doit être lue comme historique et non comme la règle RC29.1. Voir `LIRE_NELYIO_ARCH_V60_5_RC29_1.md` et `RC29_SPEC.md`.

> **RC29.1 — Centre Live desktop** : Agents à gauche et Campagnes/Périmètres à droite, zones indépendantes et en-têtes fixes. Les blocs secondaires sont repliables afin de conserver la supervision principale dans la fenêtre.

> **RC28 — Centre Qualité Live complet** : le Centre s'appuie désormais sur les groupes/files configurés comme référence de couverture. Toutes les campagnes/files configurées et tous les agents ACTIVE restent visibles même sans état Hermes courant ; ces agents sont marqués **Non observé**. Les métriques d'attente affichées sont séparées entre Live réellement observable et statistiques certifiées `Stats.INBOUND`. Le HOLD explicite reste un détail d'appel et n'est jamais présenté comme attente de file globale.

> **RC26 — Live opérationnel enrichi** : Centre Qualité Live affiche maintenant les appels Live observés par agent, les temps d’état observés, le temps non disponible (pause + déconnecté + autres états indisponibles), ainsi que les volumes Live par campagne. Une mise en attente pendant appel n’est affichée que si Hermes fournit un libellé explicite `Mise en attente` / `HOLD`; l’absence de preuve reste `Non certifiée` et n’est jamais transformée en zéro.

> **RC25 — UI Utilisateurs & accès** : l’administration est désormais organisée en onglets Comptes / Groupes d’accès / Profils / Droits effectifs. Un seul groupe est édité à la fois, les sections sont repliables et l’affectation en masse est disponible. Le modèle de sécurité serveur RC23/RC24 reste inchangé.

> **RC24 — Profils d’accès** : dans **Administration → Utilisateurs & accès**, les profils enregistrent les droits d’interfaces + ANI + périmètre métier sans membres. Appliquer un profil est explicite ; dupliquer un groupe ne copie jamais ses utilisateurs. Les profils qui référencent un groupe métier supprimé sont refusés.

> **RC22 — Analyse performance ciblée** : après `RECETTE_PRODUCTION.bat` et `TEST_CHARGE_PROLONGEE.bat`, exécuter `ANALYSER_PERFORMANCE_PRODUCTION.bat`. Le rapport corrèle les preuves Web/Analytics/charge sans appliquer automatiquement de réglage ni conclure à une cause PostgreSQL non prouvée.


> **RC21 — Durcissement production** : `requests` n'est plus une dépendance runtime. Après `RECETTE_PRODUCTION.bat`, lancer `TEST_CHARGE_PROLONGEE.bat` pour une preuve soutenue à 5 sessions indépendantes, puis contrôler **Administration → Santé de production**. Les seuils de lenteur sont techniques/configurables et ne modifient aucun KPI métier.
> **RC2K — 23/09/2026** : les groupes analytiques sont strictement file-based et ACTIVE-only; la moyenne Appel entrant est reconstruite depuis Stats.AGENT. Voir `LIRE_RC2K_GROUPES_ACTIVE_MOYENNE_APPELS.md`.

> **RC2I (23/09/2026)** : les écrans Qualité utilisent désormais les groupes par files et la vue Qualité agents optimisée. Lire `LIRE_RC2I_OPTIMISATION_QUALITE.md` avant recette.

> **RC19 — 27/09/2026** : utilisez désormais `RECETTE_PRODUCTION.bat` après le démarrage. Il consolide preflight, PostgreSQL read-only, /healthz, HTTPS, droits, Live, campagnes, groupes, Qualité et benchmark 5 utilisateurs dans `logs/RECETTE_PRODUCTION.md`. Une source absente ou une étape ignorée ne peut pas produire GO.

> **RC20 — 27/09/2026** : après démarrage, **Administration → Santé de production** permet de suivre les heartbeats Web/Live/Analytics, PostgreSQL, fraîcheur Hermes, sessions Nelyio, import, dernière recette et journaux lents agrégés. Cet écran est en lecture seule et complète, sans remplacer, `RECETTE_PRODUCTION.bat` ni le test HTTPS depuis un autre poste du LAN.

# Nelyio V56.18 MS1 — PostgreSQL PROD RC1

Cette édition est le candidat de production PostgreSQL. Elle est conçue pour être testée d'abord sur le serveur cible, puis seulement basculée en production après les contrôles ci-dessous.

## 1. Ce qui est désormais la source de vérité

- PostgreSQL : données métier historiques et administratives `admin`, `supervision`, `details`.
- `Nelyio_Live.db` : spool Live courant et incidents Qualité Live, SQLite/WAL local isolé de PostgreSQL.
- `Nelyio_Services.db` : uniquement heartbeats techniques locaux des processus, aucune donnée métier.
- Les anciens fichiers SQLite des schémas migrés restent présents uniquement comme source de migration / copie de sécurité initiale. Nelyio ne doit pas revenir silencieusement dessus.

Le lanceur refuse de démarrer sans `data\postgres.env`.

## 2. Installation sur un nouveau serveur

1. Extraire l'archive dans un nouveau dossier. Ne pas écraser une ancienne version.
2. Installer PostgreSQL et vérifier que le service Windows PostgreSQL est démarré.
3. Lancer `INSTALL_DEPENDENCIES.bat` si l'environnement Python n'est pas déjà préparé.
4. Lancer `CONFIGURER_POSTGRESQL_AUTO.bat`.
   - crée/actualise le compte applicatif ;
   - crée la base `nelyio` ;
   - migre les quatre bases historiques ;
   - installe les objets PostgreSQL nécessaires ;
   - exécute le contrôle runtime PostgreSQL.
5. Lancer `VALIDATION_PRODUCTION.bat`.
6. Lancer `START_NELYIO.bat`.
7. Attendre quelques secondes puis lancer `VALIDER_APRES_DEMARRAGE.bat`.
8. Tester un import SIMPLIFY2 connu.
9. Lancer `VALIDER_QUALITE.bat 2026-09-18` après l'import de la référence du 18/09/2026.
10. Tester ensuite HTTPS/Caddy depuis un autre poste du LAN.

Si une des validations affiche `[ERREUR]`, ne pas basculer en production.

## 3. Barrières de démarrage ajoutées

Avant `app.py`, `START_NELYIO.bat` exécute automatiquement `postgres_runtime_preflight.py --repair`.
Ce contrôle :

- teste la connexion PostgreSQL et le fuseau Europe/Paris ;
- vérifie les schémas et tables indispensables ;
- crée uniquement les objets runtime manquants, sans reset de la base ;
- vérifie les fonctions utilisées par Qualité et les filtres ;
- vérifie les triggers de cache Détails ;
- vérifie les curseurs `ingest_seq` qui remplacent le `rowid` SQLite ;
- lance des requêtes applicatives de fumée sur Qualité, annuaire, import et Détails.

Le rapport est enregistré dans `logs\postgres_runtime_preflight.json`.

## 4. Import

Le processus Web ne doit pas effectuer le gros import lui-même. Le service `import_service.py` consomme la file durable.
Les fichiers sources sont archivés avant traitement et un import incomplet reste reprenable.

Après démarrage, `VALIDER_APRES_DEMARRAGE.bat` exige des heartbeats sains pour :

- Web ;
- Import ;
- Live ;
- Analytics.

## 5. Qualité — règles de précision

### Qualité de service

La définition métier RC2H est alignée sur le diagnostic Vocalcom/SIMPLIFY2 :

- **Reçus** : nombre de lignes `Stats.INBOUND` dans la période réellement filtrée ;
- **Traités** : `AgentId > 0` ;
- **Répondus SIMPLIFY2** : `IsCallAnswered=1`, métrique technique distincte ;
- **QoS RC29.1** : `Traités / (Reçus - Clôturés - Raccrochés avant file) × 100` ; les reroutés sans agent restent une catégorie diagnostique séparée et ne sont pas ajoutés au numérateur QoS ;
- **ASA** : moyenne de `WaitDuration` sur les appels avec `AgentId > 0` ;
- **Traités ≤ 60 s** : `AgentId > 0 AND WaitDuration <= 60`.

`Stats.OUTBOUND` est stocké et compté séparément sous **Appels émis** et ne modifie jamais Reçus, Traités, Abandonnés, QoS ou ASA entrants.

Le contrôle métier vérifie :

- `Complétés + Transférés + Reroutés agent = Traités par agent` ;
- `Reçus = Clôturés + Débordements + Reroutés sans agent + Ignorés + Raccrochés avant file + Abandonnés + Traités par agent` ;
- les doubles classifications et les lignes non classifiées sont exposées, jamais masquées ;
- les durées source négatives restent des avertissements distincts.

La date/heure utilisée est celle de chaque ligne source en **Europe/Paris**. Le mode « Journée entière » utilise une borne de début incluse et le début du jour suivant exclu.

Pour rejouer la référence du 01/09/2026 :

`VALIDER_REFERENCE_QUALITE_20260901.bat "C:\chemin\SIMPLIFY2.2026-09-01.export.zip"`

### Qualité agents

- Travail et présence sont calculés à partir des intervalles Stats.AGENT.
- Les intervalles sont fusionnés avant sommation pour éviter les doubles comptes.
- Une mise en attente identifiée ne rajoute pas artificiellement du temps de présence/travail.
- `Présence - Travail` n'est jamais interprété automatiquement comme une déconnexion.
- La durée déconnectée repose sur des événements explicites `offline`/`departure` de la même référence acceptée.
- Les appels traités ne sont affichés que lorsque la référence appels et la référence activités sont compatibles.
- Les durées négatives ou sous-actions non résolues sont signalées au lieu d'être masquées.

`VALIDER_QUALITE.bat` fait échouer le contrôle si la couverture, la compatibilité ou les réconciliations internes sont incorrectes.

## 6. Référence du 18/09/2026

Le rapport Agent production fourni comme référence indique, sur son propre périmètre :

- 893 appels ;
- Travail total : 63h15m32 ;
- Présence totale : 71h53m11.

Ces valeurs servent de contrôle externe. Elles ne doivent être comparées automatiquement que si Nelyio utilise exactement le même périmètre d'agents, d'horaires et de sources que le rapport.

## 7. Sauvegarde

Avant la première vraie journée de production, exécuter `SAUVEGARDER_POSTGRESQL.bat`.
Le script utilise `pg_dump` au format custom puis vérifie que le dump est relisible par `pg_restore` lorsqu'il est disponible.

Dossier : `backups\postgresql\`.

Le mot de passe applicatif n'est pas passé dans la ligne de commande de `pg_dump`.

## 8. Rétention

La rétention destructive est volontairement bloquée en mode PostgreSQL dans ce candidat. Le dry-run peut rester utilisé. Cette protection évite une purge sans point de rollback PostgreSQL natif validé.

## 9. Validation réalisée avant livraison

- 157 tests ciblés réussis ; 5 ignorés car dépendants de fixtures/environnements externes.
- Compilation de tous les modules Python racine : OK.
- Vérification syntaxique des JavaScript Qualité modifiés : OK.
- Une tentative de suite complète a été lancée ; elle a dépassé la limite de temps de l'environnement de construction sans échec observé avant l'arrêt. Elle ne remplace pas la recette serveur.

## 10. Condition de GO production

GO uniquement si, sur le serveur cible :

- `VALIDATION_PRODUCTION.bat` = OK ;
- `START_NELYIO.bat` = backend + trois services OK ;
- `VALIDER_APRES_DEMARRAGE.bat` = OK ;
- un import SIMPLIFY2 complet arrive à `completed` ;
- `VALIDER_QUALITE.bat <date>` = OK ;
- HTTPS/Caddy est accessible depuis un poste client ;
- un `pg_dump` a été créé et vérifié.


## RC2B - postgres.env absent

Si PostgreSQL est deja migre mais qu'aucun ancien `data\postgres.env` n'est disponible, utilisez `RECREER_CONFIG_POSTGRESQL_EXISTANTE.bat`. Ce script recree les identifiants applicatifs et le fichier local sans supprimer ni re-migrer la base `nelyio`.


## PostgreSQL PROD RC2E

- Corrige le Dashboard PostgreSQL quand `derniere_vue` est un alias de `MAX(date_evenement)`.
- Corrige la meme construction dans le detail PC.
- Le smoke test PostgreSQL execute maintenant exactement les requetes runtime partagees.
- Aucun reset ni nouvelle migration PostgreSQL n est requis pour passer de RC2D a RC2E.
