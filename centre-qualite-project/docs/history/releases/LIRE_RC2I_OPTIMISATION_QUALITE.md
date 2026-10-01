# Nelyio V56.18 MS1 — PostgreSQL RC2I QUALITÉ OPTIMISÉE

## Fait

- **Qualité de service — Groupe** : le filtre n'utilise plus les campagnes enregistrées directement sur un groupe comme définition du périmètre. Il part des **files configurées du groupe**, puis utilise les correspondances file → campagne fournies par la configuration SIMPLIFY2.
- **Qualité de service — Agent** : ajout d'un filtre Agent côté serveur. Le calcul porte réellement sur l'agent choisi, ce n'est pas un simple filtre visuel.
- **Qualité agents — performance** : remplacement de la boucle de requêtes par jour par des lectures groupées sur la période ; suppression du chargement du catalogue Priorités complet pour cette vue ; filtrage SQL des membres lorsqu'un groupe est sélectionné.
- **Qualité agents — Jours actifs** : +1 pour chaque journée où l'agent possède au moins une donnée de durée positive ou au moins un appel traité. Il ne dépend plus uniquement du temps « travail ».
- **Qualité agents — Moy. appel entrant** : calcul depuis Stats.AGENT. Pour les imports historiques qui n'ont pas `quality_agent_facts`, Nelyio reconstruit la valeur depuis les activités déjà stockées, sans réimport obligatoire.
- **Qualité agents — Détail** : chaque agent possède un bouton `Voir` avec présence, travail, déconnexion, pauses, coaching, appels, ASA et mise en attente.
- **Distribution par files** : le détail agent affiche les appels traités par file. L'attribution n'est faite que si le lien campagne → file est suffisamment précis. Sinon la ligne est marquée `File ambiguë` ou `File non identifiée`.
- **Index** : ajout de `activities(import_id, agent, campaign)` pour les lectures Qualité et limitation des associations historiques aux imports encore couverts.
- Le cache léger des files/groupes est invalidé immédiatement après un changement de groupe ou un import de configuration Qualité.

## Vérifié

Validation avec `SIMPLIFY2.2026-09-01.export.zip` :

- file de test réelle : **547** ; campagne rattachée : **86653783** ; **10 agents actifs/partiels** ;
- filtre Groupe Qualité de service : **37 appels** sur ce périmètre, identique au calcul direct de la base ;
- filtre Agent serveur : contrôle effectué sur un agent à **237 appels traités** ;
- Qualité agents : **90 agents** affichés ; **88** disposent d'une moyenne `Appel entrant` calculable dans la source ;
- somme `file exacte + ambiguë + non rattachée` = total des appels traités pour chaque agent ;
- Jours actifs : aucun écart détecté avec la règle « donnée positive/appel traité = 1 jour » ;
- intégrité Qualité agents : **OK** ;
- référence métier RC2H conservée : Reçus 12 115, Traités 9 087, QoS 81,30 %, ASA 115,93 s, OUTBOUND 79 séparés.

Tests :

```text
pytest audit_regression_test.py : 34 passed
node audit_frontend_test.js     : PASS
quality_reference_20260901_test : PASS
quality_rc2i_test.py            : PASS
```

Benchmark isolé SQLite, 60 000 appels / 30 jours / 50 agents :

```text
                         RC2H                 RC2I
Qualité agents SQL      117 requêtes          28 requêtes
Qualité service SQL      40 requêtes          24 requêtes
Qualité agents médiane   ~0,04 s              ~0,07 s
Qualité service médiane  ~0,45 s              ~0,44 s
RC2I distribution                              ~0,26 s
5 vues agents concurrentes ~0,51 s             ~0,54 s, 5/5 correctes
```

RC2I réduit donc surtout les **allers-retours SQL** (important avec PostgreSQL distant/local via pilote) tout en calculant davantage de détails par agent. Le benchmark SQLite local ne montre pas un gain de CPU brut sur toutes les vues ; la validation de vitesse finale doit être faite sur le PostgreSQL du serveur réel.

## Précision / limite source

`Stats.INBOUND` contient la campagne mais **pas l'identifiant de file** dans l'export de référence (`DistributionGroup` y est vide). Nelyio ne peut donc pas fabriquer une file par appel. La distribution utilise la configuration file → campagne et, pour un agent, ses affectations de files actives/partielles afin de réduire les ambiguïtés.

Sur l'export du 01/09/2026 utilisé pour la validation, les **126 correspondances campagne → file observées sont univoques**. Si une future configuration rattache une même campagne à plusieurs files, l'interface le signalera au lieu de répartir arbitrairement les appels.

Aucune donnée fiable d'**ancienneté/expérience** des agents n'est présente dans les sources actuelles du projet. RC2I ajoute donc le filtre **Agent**, mais n'invente pas un filtre « expérience ». Un tel filtre pourra être ajouté si une source d'ancienneté est définie dans l'annuaire Administration.

## Risque maîtrisé

- aucune réinitialisation PostgreSQL/SQLite ;
- aucun historique supprimé ;
- logique QoS RC2H conservée ;
- Capture Live RC2H conservée ;
- groupes Administration conservés : seule leur utilisation analytique dans Qualité est modifiée ;
- les distributions ambiguës restent visibles comme ambiguës.

## Fichiers principaux modifiés / ajoutés

- `quality_scope.py` — nouveau scope léger groupes/files ;
- `quality_metrics.py` — groupe par files + filtre agent ;
- `quality_agents.py` — agrégats précis, fallback historique, jours actifs, distribution files, requêtes groupées ;
- `quality_service.py` — lecture historique plus bornée + invalidation du scope ;
- `supervision_db.py` — index de lecture ;
- `routes_groups.py` — invalidation du scope après modification ;
- `static/quality-overview.js` — UI Groupe(files) + Agent ;
- `static/quality-activity.js` — nouvelle interface et détail agent ;
- `static/quality.css` — styles du détail ;
- `audit_regression_test.py` — test fallback/Jours actifs ;
- `quality_rc2i_test.py` — validation rejouable sur export réel.

## Prochaine étape

1. Extraire RC2I dans un **nouveau dossier**.
2. Réutiliser/configurer `data\postgres.env` selon la procédure de production existante.
3. Lancer `VALIDATION_PRODUCTION.bat`.
4. Importer une journée SIMPLIFY2 connue et tester Qualité de service puis Qualité agents.
5. Mesurer les temps de réponse sur PostgreSQL avec 5 utilisateurs réels avant remplacement de RC2H.
