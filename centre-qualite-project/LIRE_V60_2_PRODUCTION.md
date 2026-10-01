# NELYIO V60.2 — Performance, Live et import snapshot

Build : **60.2-PROD-PERF-LIVE-SNAPSHOT**

## Ce que corrige cette version

### Analytics / Support

Le HAR réel transmis le 24/09/2026 montre que la latence est serveur : Support monte à environ **31,5 s** sur la période 01→23 septembre et renvoie environ **3,4 Mo**, tandis que Recherche d'appels monte à environ **9,1 s**. La trace testée provenait encore du dossier V60.0.

V60.2 retire deux scans complets ODCalls dans Support :

- une déconnexion n'entraîne plus le chargement de tous les appels du jour ;
- Support ne recharge plus tous les appels du mois avant de garder seulement les EndReason/durées invalides ;
- les événements interactifs sont compacts et bornés ;
- les rapports détaillés conservent leur chemin dédié ;
- Recherche d'appels combine ses agrégats au lieu de rescanner la période plusieurs fois ;
- le cache Analytics historique reste chaud plus longtemps, mais est invalidé par les vraies révisions de données/configuration.

Un fichier `logs/analytics_slow.log` enregistre uniquement les calculs Analytics dépassant 2 s : type, durée et hash technique. Aucun numéro, ANI/DNIS ou filtre utilisateur n'y est journalisé.

### Live Nelyio

Le Live reste totalement séparé de PostgreSQL historique. L'écran **Live Nelyio** lit maintenant directement `Nelyio_Live.db` via `/api/collection/live` et affiche :

- nombre d'événements du jour ;
- appels observés ;
- agents détectés ;
- files détectées ;
- campagnes détectées ;
- derniers événements, agent, file, campagne, état et numéro lorsque la capture est configurée pour le conserver ;
- pagination du journal Live.

La rétention reste **jour courant uniquement**. Le Live n'est pas réinjecté dans Support/Détails/Qualité.

### Import snapshot

L'import SIMPLIFY2 ne remplace plus la référence visible au début du traitement.

1. l'ancienne référence reste active pour le site ;
2. le nouvel import est enregistré avec l'état `staged` ;
3. Qualité/Agents/Détails nécessaires sont préparés sur cet import ;
4. si une étape critique échoue, l'ancienne référence reste active ;
5. si tout réussit, `coverage` et `call_coverage` basculent dans une transaction courte vers la nouvelle référence.

Le site ne voit donc jamais un import partiel. Un redémarrage ne peut pas activer accidentellement un import `staged`.

`OPEN_NELYIO_IMPORTER.bat` utilise désormais une priorité Windows normale par défaut. Pour un serveur CPU très contraint seulement, définir `NELYIO_IMPORT_PRIORITY=low`.

L'Importer affiche aussi les durées de chaque étape à la fin de l'import. C'est la mesure à transmettre si un import réel reste lent.

## Installation

1. arrêter proprement l'ancienne version ;
2. extraire V60.2 dans un **nouveau dossier** ;
3. recopier votre `data/postgres.env` de production ;
4. ne pas wipe PostgreSQL ;
5. `Nelyio_Live.db` peut repartir vide si souhaité ;
6. démarrer Nelyio et vérifier `/healthz` ;
7. ouvrir Live Nelyio et vérifier que les événements apparaissent directement ;
8. lancer un import via `OPEN_NELYIO_IMPORTER.bat` ;
9. pendant cet import, vérifier que le Web reste utilisable ;
10. après navigation, consulter `logs/http_slow.log` et `logs/analytics_slow.log`.

## Mesures isolées V60.2

Jeu synthétique : **207 000 appels / 23 jours**.

- Support V60.1 : ~2,84 s / ~2,06 Mo JSON ;
- Support V60.2 : ~0,19 s / ~0,56 Mo JSON ;
- Recherche d'appels avant optimisation V60.2 : ~3,77 s ;
- Recherche d'appels après optimisation V60.2 : ~0,66 s.

Ces mesures prouvent la suppression des scans inutiles, mais ne remplacent pas la recette sur votre PostgreSQL réel.
