# Nelyio V60.5 RC29.3 — À lire avant production

## Statut de ce document

Ce document est la **référence opérateur courante** pour `Nelyio-ARCH V60.5 RC29.3 (LIVE_SIMPLE)`.

Il **remplace `docs/history/releases/LIRE_NELYIO_ARCH_V60_5_RC29_1.md` comme référence opérateur**. Le fichier RC29.1 est conservé dans l'archive comme historique et ne doit pas être supprimé.

## Version

- Version : **60.5-ARCH-RC29.3**
- Build : **V60.5-RC29.3**
- Base : RC28 → phases RC29 validées → corrective RC29.1 QoS → cockpit RC29.2 → simplification RC29.3
- Nature de RC29.3 : réorganisation de l'interface de supervision ; les règles métier validées restent inchangées.

## Règle QoS canonique

La formule officielle Nelyio, à conserver partout où le libellé **QoS** est utilisé, est :

**QoS = Appels traités / (Appels reçus - Appels clôturés - Raccrochés avant file d'attente) × 100**

Règles associées :

- si le dénominateur est nul ou négatif, la QoS reste indisponible (`—`) ;
- ne pas utiliser `Traités / (Traités + Abandonnés)` comme QoS Nelyio ;
- une métrique externe reposant sur une autre formule doit porter un autre nom et ne doit pas être affichée sous le libellé QoS.

## Centre Qualité Live — disposition RC29.3 réellement livrée

Le Centre Qualité Live est organisé comme un **poste de supervision**, avec un seul espace de travail principal par défaut afin de réduire l'encombrement.

### Vue par défaut : Agents

- **Agents** est la vue affichée par défaut au chargement du Centre Live.
- La liste agents utilise l'espace principal disponible pour maximiser le nombre d'agents visibles.
- La recherche, le groupe surveillé et le changement de vue restent directement accessibles.
- La liste conserve son propre défilement : l'opérateur n'a pas à faire défiler toute la page pour surveiller les agents.

### Vue alternative : Campagnes / périmètres

- **Campagnes / périmètres** est accessible depuis le sélecteur `Vue`.
- Cette vue utilise le même espace principal à la place de la liste Agents.
- Elle permet de superviser les campagnes/périmètres sans charger en permanence l'écran principal avec les deux listes.

### Double vue optionnelle

- **Double vue** reste disponible pour les situations où l'opérateur doit corréler agents et campagnes simultanément.
- Elle est volontairement optionnelle et n'est plus l'affichage imposé par défaut.

### Rail KPI

Les indicateurs de supervision immédiate sont regroupés dans un **rail KPI compact** (`live-supervision-rail`) au lieu d'occuper plusieurs blocs verticaux.

L'objectif est de garder les états principaux visibles tout en réservant la majorité de l'écran à la liste opérationnelle.

### Tiroir Détails

Les informations secondaires sont regroupées derrière un seul **Détails** (`live-detail-drawer`) :

- Qualité maintenant ;
- Qualité certifiée ;
- Alertes ;
- Fiabilité / limites.

Ces informations restent disponibles sans encombrer en permanence l'espace principal de supervision.

### Menu Plus

Les fonctions moins fréquemment utilisées sont regroupées sous **Plus** :

- Analyse qualité ;
- Règles / alertes, selon les droits de l'utilisateur.

La Recherche reste disponible directement depuis la barre principale.

### Responsive

Sur tablette/mobile, la présentation s'adapte au viewport. La priorité reste la lisibilité et l'accès aux mêmes fonctions ; la disposition desktop pleine hauteur ne doit pas être supposée sur les petits écrans.

## Groupes analytiques / ACTIVE

Les règles définies dans `docs/current/RC29_SPEC.md` restent inchangées :

- un **Groupe analytique** est construit à partir des **files configurées** ;
- les membres sont les agents ayant une affectation **ACTIVE** à au moins une file du groupe ;
- un agent peut appartenir à plusieurs groupes ;
- les statuts `partial`, `inactive` et `unknown` ne donnent pas l'appartenance analytique ACTIVE ;
- les groupes d'accès Administration et les groupes analytiques restent deux notions distinctes ;
- une configuration ACTIVE indique une appartenance/attente de population, pas une preuve qu'un agent a réellement travaillé.

## Règles Live à conserver

- agent configuré mais non vu actuellement par Hermes = **Non observé** ;
- absence d'observation ≠ Déconnecté ;
- `inactive_context` reste distinct de `other` ;
- HOLD / **Mise en attente** explicite reste distinct de l'attente patient en file ;
- métrique non certifiée ou non disponible = `—`/inconnue, jamais zéro inventé ;
- identifiants techniques agents/campagnes restent conservés même lorsqu'un libellé utilisateur est résolu ;
- les changements RC29.3 de disposition ne modifient ni les KPI, ni les distributions, ni les règles de signalisation.

## Avant bascule production

La checklist RC29.1 est conservée dans son intégralité fonctionnelle ; seule la référence de version du package à extraire est actualisée de RC29.1 vers RC29.3.

1. Extraire RC29.3 dans un **nouveau dossier**.
2. Ne pas écraser l'ancienne installation.
3. Vérifier/récupérer la configuration PostgreSQL locale (`data\postgres.env`) selon la procédure existante.
4. Lancer `VALIDATION_PRODUCTION.bat`.
5. Démarrer Nelyio.
6. Lancer `RECETTE_PRODUCTION.bat` sur le serveur Windows cible.
7. Vérifier l'URL HTTPS depuis un autre poste du LAN.
8. Importer une journée SIMPLIFY2 connue et comparer les KPI sur le même périmètre.
9. Vérifier particulièrement la QoS avec les quatre composantes : Reçus, Traités, Clôturés, Raccrochés avant file.
10. Tester le Centre Live avec le volume réel d'agents et de campagnes.

Un WARN/SKIP n'est pas un PASS. Une donnée absente ne doit jamais devenir zéro par défaut.

## Points à vérifier spécifiquement dans le Centre Live RC29.3 lors de la recette cible

Sans remplacer la checklist ci-dessus, contrôler également :

- ouverture initiale sur **Agents** ;
- bascule vers **Campagnes / périmètres** ;
- bascule vers **Double vue** ;
- groupe surveillé et recherches conservés pendant les rafraîchissements ;
- rail KPI visible sans masquer la liste principale ;
- ouverture/fermeture du tiroir **Détails** ;
- accès au menu **Plus** selon les droits ;
- défilement interne des listes sans scroll vertical excessif de toute la page ;
- comportement à la résolution réelle des postes de supervision ;
- fonctionnement avec le volume réel d'agents et de campagnes.

## Documents de référence

- `docs/current/RC29_SPEC.md` : spécification consolidée RC29 et invariants métier ;
- `RC29_PHASE1_VALIDATION.md` à `RC29_PHASE7_VALIDATION.md` : preuves par phase ;
- `RC29_1_QOS_SUPERVISION_VALIDATION.md` : corrective QoS RC29.1 ;
- `docs/validation/RC29_2_CENTRE_LIVE_COCKPIT_VALIDATION.md` : évolution cockpit RC29.2 ;
- `docs/validation/RC29_3_CENTRE_LIVE_SIMPLE_VALIDATION.md` : disposition simplifiée RC29.3 ;
- `docs/validation/RC29_3_STEP1_TEST_REALIGNMENT.md` : réalignement des tests de gel/consolidation ;
- `docs/validation/RC29_3_CONSOLIDATED_VALIDATION.md` : validation consolidée en cours de gel RC29.3 ;
- `docs/current/LIRE_AVANT_PRODUCTION.md` : procédure historique détaillée PostgreSQL/production ;
- `RECETTE_PRODUCTION.bat` : recette cible réelle ;
- `docs/history/releases/LIRE_NELYIO_ARCH_V60_5_RC29_1.md` : ancienne référence opérateur, conservée comme historique.

## À propos des anciens rapports PHASE8+

L'archive conserve des rapports historiques `docs/history/validation/PHASE8_VALIDATION_REPORT.md`, `docs/history/validation/PHASE9_VALIDATION_REPORT.md`, etc. Ils proviennent d'une ancienne séquence de développement et sont conservés comme historique.

Ils **ne constituent pas une Phase 8 fonctionnelle du plan RC29** et ne doivent pas être interprétés comme la suite du chantier de gel RC29.3.

## Limite de validation de ce document

Ce document décrit le package RC29.3 livré et les contrôles attendus. Il ne transforme pas en PASS les éléments nécessitant le serveur cible : Windows, PostgreSQL réel, Caddy/HTTPS, Hermes, réseau LAN et charge réelle restent à vérifier pendant la recette de production.
