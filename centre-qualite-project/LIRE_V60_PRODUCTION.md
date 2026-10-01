# NELYIO V60 — Mise en production

Build : **60.0-PROD-ARCH**

## Pourquoi V60

Les mesures réelles du 24/09/2026 montraient des blocages globaux, pas seulement une requête SQL lente : `POST /api/login` pouvait passer d'environ 1,2 s à plus de 60–80 s, pendant que des vues Support/Qualité/Groupes attendaient plusieurs dizaines de secondes. Le second HAR montrait aussi 17 appels à `/api/collection/summary`, avec un maximum d'environ 25 s, ce qui confirmait que le Live continuait à participer à la charge des écrans historiques.

V60 sépare les responsabilités afin qu'un import ou le Live ne puisse plus monopoliser le Web.

## Architecture V60

### 1. Web/API

- `app.py`
- heartbeats Web/Live/Analytics dans `Nelyio_Services.db` SQLite local, indépendant de PostgreSQL ;
- authentification, navigation, administration, parc et API légère ;
- ne scanne plus le dossier `import` en production ;
- ne reçoit plus les gros fichiers SIMPLIFY2 en production ;
- ne calcule plus localement les vues lourdes si Analytics est indisponible ;
- reste disponible même si Importer ou Live ont un problème.

### 2. Importer local

Lancer : **`OPEN_NELYIO_IMPORTER.bat`**

- application Tk locale indépendante ;
- priorité système réduite ;
- un import à la fois ;
- accepte ZIP SIMPLIFY2, Stats.AGENT.csv et `group.har` ;
- réutilise le pipeline d'import existant ;
- aucune boucle de scan toutes les secondes dans le Web ;
- la source n'est pas supprimée par l'application locale en cas d'erreur.

### 3. Live Nelyio

- service : `live_service.py` ;
- base : **`Nelyio_Live.db`**, SQLite/WAL locale et indépendante ;
- `db_compat` ne route plus cette base vers PostgreSQL ;
- aucune écriture Live vers PostgreSQL Support/Détails/Qualité ;
- aucune actualisation globale Support/Détails/Appels déclenchée par Live ;
- rétention brute : **journée Europe/Paris courante uniquement** ;
- purge + compactage automatique au changement de date ou au redémarrage après changement de date.

### 4. Analytics

- service local loopback sur 9052 ;
- concurrence lourde bornée à 3 requêtes ;
- cache des résultats ;
- délai RPC Web borné à 20 s ;
- **aucun fallback lourd dans le processus Web**.

## Qualité Agents corrigée

### Travail

`Travail` = **présence observée - pauses - coaching**.

Les états productifs explicites de Stats.AGENT restent disponibles pour diagnostic, mais un libellé Hermes non reconnu ne peut plus transformer un agent présent et actif en `0 s` de travail.

### Moy. appel entrant

La moyenne utilise en priorité **`CallDuration` de Stats.INBOUND** pour les appels attribués à l'agent. Si cette donnée n'est pas disponible, Stats.AGENT reste le repli.

Cela corrige le cas observé où un agent pouvait avoir des dizaines d'appels traités et plusieurs heures de présence tout en affichant `Travail = 0` et `Moy. appel entrant = null`.

## Groupes

Règle conservée : **Groupe -> Files -> Agents avec affectation ACTIVE**.

V60 ajoute une protection : un export incomplet qui annonce une section agents/files mais ne contient aucune affectation exploitable ne peut plus effacer la dernière projection ACTIVE valide. Un reset volontaire des affectations doit être une opération d'administration explicite.

## Installation recommandée

1. Extraire V60 dans un **nouveau dossier**.
2. Copier votre `data/postgres.env` de production si nécessaire.
3. Conserver votre `caddy.exe` externe comme sur V59.
4. Lancer `START_NELYIO.bat` ou `START_NELYIO_HTTPS.bat`.
5. Vérifier `/healthz` : `services_ok=true` et `web/live/analytics=true`.
6. Ouvrir **Live Nelyio** : vérifier la base dédiée et la capture du jour.
7. Pour un import, lancer **`OPEN_NELYIO_IMPORTER.bat`** sur le serveur.
8. Tester Qualité Agents sur un agent connu : Travail non nul si présence réelle, moyenne entrante issue de Stats.INBOUND lorsque disponible.
9. Tester au moins deux groupes et un agent multi-groupe.
10. Vérifier `logs/http_slow.log` après une session réelle de navigation.

## Ne pas faire

- Ne pas remettre `import_service.py` dans le démarrage permanent.
- Ne pas réactiver le scan automatique du dossier import dans le Web.
- Ne pas réinjecter Live dans Support/Détails/Recherche d'appels.
- Ne pas réactiver le fallback local des requêtes Analytics lourdes.
- Ne pas reset toute la base PostgreSQL pour corriger une lenteur : Live peut être jeté/recréé sans toucher aux utilisateurs, groupes, permissions ou historique importé.
