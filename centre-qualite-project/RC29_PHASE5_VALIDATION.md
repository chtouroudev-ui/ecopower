# RC29 — Phase 5 — Tri global typé et cohérent

Date : 2026-09-28
Base de travail : `Nelyio-ARCH_RC29_PHASE4_DISTRIBUTIONS_PERIMETRES.zip`

## Périmètre

Phase 5 uniquement : déploiement du contrat de tri validé en Phase 2 sur les tableaux non-Live concernés. Aucun changement de formule métier, de population, de QoS, de collecte Hermes, de signalisation ou de modèle de données.

Contrat appliqué :

- cycle `ASC → DESC → ordre par défaut` ;
- valeurs absentes / inconnues toujours en bas, y compris en DESC ;
- tri typé : texte, nombres, pourcentages, durées, dates/horodatages et états ;
- persistance de l’état de tri dans `sessionStorage` lorsque la vue le permet ;
- ordre stable en cas d’égalité ;
- lorsqu’une vue est paginée côté serveur : `dataset → filtres → tri → pagination`, jamais tri de la seule page visible ;
- clés SQL strictement autorisées par liste blanche, aucune expression SQL fournie par le navigateur n’est exécutée directement.

## Changements

### Qualité agents / Qualité de service / Distributions

Le helper historique `qualityMakeSortable` a été remplacé par le contrat RC29 typé.

Corrections notamment validées :

- `59 s` est inférieur à `2m 00s` ;
- `1h 01m` est interprété comme 3660 s ;
- `01:30` est interprété comme 90 s ;
- les pourcentages sont triés sur leur valeur numérique ;
- les dates sont triées chronologiquement ;
- les cellules `—`, `Non observé`, `Non calculable`, etc. restent en bas ;
- le troisième clic restaure l’ordre initial.

### Administration Qualité — Agents / Files

Le tri est effectué sur l’ensemble filtré avant la pagination déjà existante.

- cycle trois états ;
- persistance par vue ;
- valeurs absentes en bas ;
- état d’activation classé selon un ordre métier (`Actif > Partiel > Inactif`, inconnu en bas) au lieu d’un ordre alphabétique.

Les écrans Groupes/Campagnes qui sont rendus sous forme de cartes/listes et non de dataset tabulaire paginé ne reçoivent pas de faux moteur de tri de tableau. Les campagnes liées visibles dans les tableaux Agents/Files continuent d’utiliser les identifiants et résolveurs validés en Phase 1.

### Recherche d’appels Nelyio

Ajout d’un tri serveur global pour :

- Date / heure ;
- Agent ;
- ANI ;
- Durée totale ;
- Conversation ;
- Attente ;
- Indice.

Le backend valide `sort` et `sort_dir` par liste blanche. Pour un tri actif, les lignes des jours couverts sont unies puis triées avant `LIMIT/OFFSET`. Le chemin optimisé historique par journées reste utilisé pour l’ordre par défaut.

### Appels suspects

Ajout d’un tri serveur global pour :

- Date / heure ;
- Agent ;
- File ;
- Campagne ;
- ANI ;
- Durée ;
- Mise en attente ;
- origine de fin disponible.

Le tri est appliqué à la requête complète filtrée avant la pagination de 100 lignes.

### Support / Diagnostic

- cycle trois états sur les tableaux Support déjà dotés de clés brutes ;
- valeurs absentes toujours en bas ;
- conservation du tri en session ;
- tableau Diagnostic agents : tri avant la pagination locale, cycle trois états, retour au classement par défaut.

## Sécurité

Deux validateurs backend refusent explicitement :

- une clé de tri inconnue ;
- une direction autre que `asc` ou `desc` ;
- une tentative telle que `start DESC; DROP TABLE phone_calls;--`.

Les expressions `ORDER BY` proviennent exclusivement de dictionnaires internes de colonnes autorisées.

## Tests exécutés

### Tests spécifiques Phase 5

`rc29_phase5_sort_test.py` : **4/4 réussis**

- listes blanches backend ;
- rejet d’injection ;
- ordre serveur avant pagination ;
- présence du cycle trois états et des types ;
- test runtime JavaScript du parseur de durées ;
- valeurs absentes en bas en DESC ;
- tri numérique des pourcentages.

### Régressions antérieures

- `rc29_phase1_identity_test.py` : **5 tests OK** ;
- `rc29_phase2_live_test.py` : OK ;
- `rc29_phase3_signalisation_test.py` : OK ;
- `rc29_phase4_distribution_scope_test.py` : **6/6 OK** ;
- `quality_agent_counts_v6_test.py` : **8 interactions**, **7 répondus**, distribution 8, source Stats.AGENT conservée ;
- `live_campaigns_phase4_test.py` : **7/7 OK** ;
- `node --check static/*.js` : **tous les scripts OK** ;
- AST Python racine : **0 erreur**.

## Préservation

Les bases `.db`, `.db-wal`, `.db-shm` de la Phase 4 ont été restaurées bit à bit après les tests. Les journaux runtime éventuellement touchés par les tests ont également été restaurés.

Fichiers fonctionnels modifiés :

- `calls.py`
- `suspicious_calls.py`
- `static/app.js`
- `static/quality.js`
- `static/support.js`
- `static/suspicious-calls.js`

Fichiers ajoutés :

- `rc29_phase5_sort_test.py`
- `RC29_PHASE5_VALIDATION.md`

## Éléments volontairement hors Phase 5

Aucune modification de :

- définition « A travaillé » ;
- population ACTIVE ;
- QoS ;
- signalisation Live ;
- `other` / `inactive_context` ;
- collecte/polling Centre Live ;
- instrumentation performance ;
- schéma PostgreSQL/SQLite ;
- import SIMPLIFY2 ;
- règles de groupes ;
- identité agents/campagnes.

**STOP — ne pas commencer la Phase 6 sans validation utilisateur.**
