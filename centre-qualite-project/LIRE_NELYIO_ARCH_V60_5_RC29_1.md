# Nelyio V60.5 RC29.1 — À lire avant production

## Version

- Version : **60.5-ARCH-RC29.1**
- Build : **V60.5-RC29.1**
- Base de travail : RC28 → phases RC29 validées → corrective RC29.1

## Règle QoS à retenir

La formule officielle Nelyio est :

**QoS = Appels traités / (Appels reçus - Appels clôturés - Raccrochés avant file d'attente) × 100**

Si le dénominateur est nul ou négatif, la QoS doit rester indisponible (`—`).

Ne pas utiliser `Traités / (Traités + Abandonnés)` comme QoS Nelyio.

## Centre de supervision

Sur desktop, le Centre Live est organisé comme un poste de supervision dense :

- Agents à gauche ;
- Campagnes / Périmètres à droite ;
- en-têtes fixes ;
- zones à défilement indépendant ;
- filtres/recherches conservés ;
- panneaux secondaires repliables pour ne pas pousser la supervision principale vers le bas.

Sur tablette/mobile, l'affichage revient en mode empilé responsive.

## Groupes analytiques

- Groupe = files configurées ;
- membres = agents avec affectation **ACTIVE** à au moins une file du groupe ;
- un agent peut appartenir à plusieurs groupes ;
- `partial`, `inactive`, `unknown` ne donnent pas l'appartenance analytique ;
- groupes d'accès Administration et groupes analytiques restent distincts.

## Live

- agent configuré mais non vu actuellement par Hermes = **Non observé** ;
- absence d'observation ≠ Déconnecté ;
- `inactive_context` reste distinct de `other` ;
- HOLD explicite reste un état d'appel/agent et n'est pas assimilé à l'attente patient en file ;
- métriques non certifiées restent indisponibles au lieu d'être forcées à zéro.

## Avant bascule production

1. Extraire RC29.1 dans un **nouveau dossier**.
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

## Documents de référence

- `RC29_SPEC.md` : spécification consolidée finale ;
- `RC29_PHASE1_VALIDATION.md` à `RC29_PHASE7_VALIDATION.md` : preuves par phase ;
- `RC29_1_QOS_SUPERVISION_VALIDATION.md` : corrective RC29.1 ;
- `LIRE_AVANT_PRODUCTION.md` : procédure historique détaillée PostgreSQL/production ;
- `RECETTE_PRODUCTION.bat` : recette cible réelle.

## À propos des anciens rapports PHASE8+

L'archive conserve des rapports historiques `PHASE8_VALIDATION_REPORT.md`, `PHASE9...`, etc. Ils proviennent d'une ancienne séquence de développement et sont conservés comme historique. Ils **ne prolongent pas le plan RC29 actuel**.
