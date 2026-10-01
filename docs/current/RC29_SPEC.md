# RC29 — Spécification consolidée

Version consolidée : **V60.5 RC29.1**
Date : **28/09/2026**

Ce document consolide le plan RC29 réellement appliqué à partir de `Nelyio-ARCH V60.5 RC28`, puis la corrective RC29.1. Il prévaut pour l'état final RC29.1 lorsque des documents historiques plus anciens utilisent une règle différente.

## Principes obligatoires

- Ne jamais inventer une donnée absente.
- **Inconnu ≠ zéro**.
- Les groupes analytiques sont construits depuis les **files configurées** et les affectations agents **ACTIVE uniquement**.
- Un agent peut appartenir à plusieurs groupes analytiques.
- Les services **MEDICAL** et **IMAGERIE** sont distincts et ne doivent pas être comparés directement comme un même périmètre métier.
- Les identifiants techniques sont conservés même lorsqu'un nom d'affichage plus lisible est résolu.
- Les migrations doivent rester additives/réversibles et ne doivent jamais reset les bases métier.
- Les valeurs de performance non mesurées sont marquées **NON MESURÉES**.

## Formule QoS canonique RC29.1

La formule unique à utiliser partout où le libellé **QoS** est affiché est :

**QoS = Appels traités / (Appels reçus - Appels clôturés - Raccrochés avant file d'attente) × 100**

Règles :

- numérateur = **appels traités** uniquement ;
- dénominateur = **reçus - clôturés - raccrochés avant file d'attente** ;
- si le dénominateur est nul ou négatif : afficher `—` / indisponible ;
- ne jamais remplacer cette formule par `traités / (traités + abandonnés)` ;
- une métrique externe différente doit être explicitement nommée autrement et ne doit pas reprendre le libellé QoS.

## Phase 0 — Audit

Aucune modification de code.

Audit obligatoire :
- sources permettant de déterminer « A travaillé » sans en choisir une prématurément ;
- tous les tableaux, colonnes, types, pagination, tri et export ;
- sources agents/campagnes et chemins de résolution des noms ;
- timers/polling/refresh/DOM du Centre Live ;
- instrumentation performance ;
- séparation prouvé / supposé / non mesurable.

## Phase 1 — Identités

- centraliser la résolution des noms agents/campagnes ;
- priorité d'affichage agent : Administration, puis source observée, puis configuration, puis ID ;
- conserver l'ID technique comme clé métier ;
- appliquer la même logique au Centre Live, Recherche Live et vues campagnes ;
- ne pas modifier les KPI.

## Phase 2 — Centre Live / DOM / tri initial

- vue compacte agents ;
- état UI conservé entre refreshs ;
- réconciliation des lignes par `agent_id` au lieu d'un remplacement intégral quand possible ;
- séparation du refresh Live et des métriques historiques importées ;
- tri à trois états : ASC → DESC → défaut ;
- valeurs absentes toujours en bas ;
- protection contre les réponses obsolètes.

## Phase 3 — Signalisation Qualité Live

- niveaux GLOBAL / SERVICE / GROUP / CAMPAIGN / QUEUE / AGENT ;
- multi-cibles ;
- ALL / ANY ;
- `min_duration`, `recovery`, `cooldown`, `min_sample`, `allow_partial` ;
- mode simple + presets et mode avancé ;
- `inactive_context` strictement distinct de `other` ;
- agents configurés sans état courant = **Non observé** ;
- incidents agrégés avec agents contributeurs observés.

## Phase 4 — Distributions / populations métier

Conserver :
- Reçus ;
- Traités ;
- Abandonnés.

Ajouter :
- Agents ACTIVE ;
- En pause ;
- Attendus ;
- A travaillé ;
- N'a pas travaillé.

Règles :
- population Groupe = agents ACTIVE dans les files du groupe ;
- absence calculée seulement si la couverture de données et le roster attendu sont fiables ;
- sinon afficher **Non calculable** ;
- une pause traversant deux tranches doit apparaître dans les deux tranches ;
- plusieurs pauses du même agent dans une tranche comptent un seul agent ;
- un agent ayant travaillé puis s'étant déconnecté reste « A travaillé » ;
- sur plusieurs jours, utiliser explicitement l'unité **agent-jours** pour les compteurs temporels.

## Phase 5 — Tri global

Contrat commun :
- ASC → DESC → ordre par défaut ;
- types texte / nombre / pourcentage / durée / date / état ;
- valeurs absentes en bas même en DESC ;
- persistance du tri ;
- pour les vues paginées serveur, tri de l'ensemble filtré **avant** LIMIT/OFFSET ;
- clés de tri backend en liste blanche.

## Phase 6 — Performance

- mesurer avant optimisation ;
- instrumenter auth, DB, SQL, worker/RPC, calcul, JSON, taille de réponse, cache ;
- préserver les caches/single-flight existants ;
- supprimer les écritures répétitives non nécessaires sur le chemin chaud ;
- tester plusieurs utilisateurs lorsque l'environnement le permet ;
- ne pas appliquer d'index ou réglage PostgreSQL spéculatif sans preuve.

## Phase 7 — Validation production / gate final

Aucun nouveau développement fonctionnel.

Vérifier :
- intégrité ;
- syntaxe ;
- régressions RC29 ;
- SQLite bootstrap/quick_check ;
- Web/API ;
- Analytics ;
- Importer ;
- Live ;
- packaging et manifeste.

Tout contrôle nécessitant Windows/PostgreSQL/Caddy/Hermes réel reste **NON VÉRIFIÉ EN PRODUCTION** tant que `RECETTE_PRODUCTION.bat` n'a pas été exécuté sur le serveur cible.

## Corrective RC29.1 — QoS + supervision desktop

RC29.1 corrige deux points sans créer une nouvelle phase métier :

1. **QoS canonique** restaurée avec la formule définie plus haut.
2. **Centre de supervision desktop** réorganisé pour réduire le défilement global :
   - Agents à gauche ;
   - Campagnes/Périmètres à droite ;
   - en-têtes fixes ;
   - zones indépendantes ;
   - blocs secondaires repliables ;
   - comportement responsive empilé sur petits écrans.

## Fin du plan RC29

Le plan RC29 s'arrête après la Phase 7 et la corrective RC29.1. Un ancien fichier `docs/history/validation/PHASE8_VALIDATION_REPORT.md` présent dans l'archive appartient à une séquence historique antérieure et **ne constitue pas une Phase 8 RC29**.

La suite prévue est la recette réelle sur serveur cible et la documentation de livraison, pas l'ajout d'une nouvelle phase fonctionnelle non spécifiée.
