# Nelyio RC2M - correctif Groupes, durees et performances production

## Probleme confirme sur les groupes

`group.har` contient les groupes Hermes et leurs **files**, mais pas une liste fiable d'agents ni de campagnes. La regle analytique Nelyio reste donc :

**Groupe -> files configurees -> affectations Agents.csv ACTIVE -> agents du groupe**

Les campagnes sont derivees de la correspondance des files avec les campagnes. `user_group_members` reste reserve a l'Administration et aux permissions ; il ne sert pas a elargir artificiellement les KPI.

Le bug venait du fait que l'ecran Groupes et certains chargements utilisaient la projection Qualite complete sans declencher la recuperation du dernier `Agents.csv` autoritatif. Il etait donc possible de voir `7 files / 0 agent / 0 campagne`, alors que les filtres devaient utiliser ces files.

### Correction

- apres import `group.har`, le cache est invalide et la projection analytique est reconstruite immediatement ;
- si le snapshot courant a perdu les affectations agents, Nelyio tente une recuperation conservative depuis la derniere archive SIMPLIFY2 valide contenant `Agents.csv` ;
- seuls les etats `ACTIVE` donnent une appartenance analytique ; `partial`, `inactive` et `unknown` restent exclus ;
- un agent peut appartenir a plusieurs groupes s'il est ACTIVE sur des files de plusieurs groupes ;
- l'ecran Groupes utilise maintenant exactement le meme scope canonique que Support, Qualite, Distribution, Analytics et Rapports ;
- les campagnes visibles dans le groupe sont derivees des files configurees.

## Correction des durees

Quand un groupe resolvait 0 agent, Qualite agents sautait logiquement les lignes `Stats.AGENT`. Cela mettait a zero ou vide les valeurs comme :

- travail cumule ;
- pauses ;
- duree deconnectee ;
- moyenne appel entrant ;
- jours actifs.

Le scope groupe corrige alimente maintenant ces calculs. Un test de regression verifie qu'un agent membre garde ses durees tandis qu'un agent hors groupe est exclu.

## Optimisations production

- HTTP/1.1 active sur le backend et le worker Analytics pour reutiliser les connexions au lieu de recreer une connexion pour chaque requete.
- Cache Analytics : fenetre de fraicheur par defaut 15 s (`NELYIO_ANALYTICS_FRESH_SECONDS`), avec TTL borne a 30 s.
- Administration : un simple affichage ne lance plus une synchronisation en ecriture de tout l'annuaire Support. Le bouton **Synchroniser maintenant** garde cette fonction.
- Les candidats Support ont un petit cache de 15 s ; une synchronisation manuelle force toujours une lecture fraiche.
- Support / Recherche d'appels / Analytics / Rapports / Qualite : le dernier nom d'un agent utilise en PostgreSQL `DISTINCT ON` et l'index `(agent, import_id DESC, id DESC)` au lieu de trier toute la table `activities` dans chaque module.
- Dashboard / Parc : la derniere observation de chaque PC utilise en PostgreSQL `DISTINCT ON` avec l'index `(ordinateur, date_evenement DESC, id DESC)`.
- Le journal d'acces Caddy JSON est desactive par defaut pour eviter une ecriture disque par requete. Les requetes backend >= 1 s restent journalisees dans `logs/http_slow.log`.

## Validation rejouee

- 51/51 tests Python : OK.
- Verification syntaxe JavaScript `groups.js` et `app.js` : OK.
- Smoke HTTP local : `/healthz` repond `HTTP/1.1 200 OK` avec le build `56.18-MS1-RC2M-CSP-GROUP-PERF`.
- Benchmark synthetique : 60 000 appels, 50 agents, 30 jours, 5 repetitions.
  - Qualite agents : mediane ~0,069 s.
  - Qualite de service : mediane ~0,431 s.
  - Distribution : mediane ~0,248 s.
  - 5 vues agents concurrentes : ~0,589 s, resultats corrects.

Ces chiffres valident le moteur dans le sandbox. La latence exacte PostgreSQL/Windows/Caddy doit etre mesuree sur le serveur reel ; `logs/http_slow.log` permet d'identifier tout endpoint restant au-dessus de 1 seconde.
