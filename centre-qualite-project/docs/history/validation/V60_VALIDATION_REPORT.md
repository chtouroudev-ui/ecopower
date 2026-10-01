# NELYIO V60 — Rapport de validation

Build : **60.0-PROD-ARCH**  
Date : **24/09/2026**

## 1. Diagnostic réel utilisé

### `http_slow.log`

Des requêtes simples étaient périodiquement bloquées :

- login : jusqu'à ~83 s ;
- dashboard : jusqu'à ~56 s ;
- supervision : ~89 s ;
- collection summary : ~84 s ;
- groupes : ~76 s ;
- Qualité Agents : ~67 s.

Le fait que le login lui-même soit touché exclut une explication limitée à une formule Qualité ou à Caddy.

### `stock-manager.nelyio.local.har`

Mesure du second HAR, maximums observés :

| Endpoint | Max |
|---|---:|
| `/api/quality/agent-activity` | ~53.1 s |
| `/api/quality/priorities` | ~36.0 s |
| `/api/collection/status` | ~34.1 s |
| `/api/supervision/view` | ~32.1 s |
| `/api/quality/overview` | ~29.4 s |
| `/api/dashboard` | ~26.6 s |
| `/api/collection/summary` | ~25.1 s |
| `/api/supervision/support` | ~20.6 s |
| `/api/groups/workspace` | ~18.4 s |

`/api/collection/summary` apparaissait 17 fois dans la trace : le Live participait encore aux rafraîchissements d'écrans historiques.

## 2. Causes corrigées

1. Import permanent + scan de dossier + hashing/lecture de sources lourdes.
2. Import et Live pouvant tous deux synchroniser Détails / écrire dans les bases historiques.
3. Live intégré aux écrans Support/Détails/Appels avec polling global.
4. Requêtes Analytics lourdes pouvant retomber dans le processus Web en fallback.
5. Trop de requêtes Analytics lourdes concurrentes pouvant saturer PostgreSQL.
6. Live routé vers le schéma PostgreSQL `live` via la couche de compatibilité au lieu d'une base réellement indépendante.
7. Qualité Agents dépendant trop des libellés Stats.AGENT pour `Travail` et `Moy. appel entrant`.
8. Un snapshot d'affectations incomplet pouvait vider la projection groupes.

## 3. Changements V60 validés

- services requis : Web + Live + Analytics ; Import est optionnel/manuel ;
- `START_NELYIO_SERVICES.ps1` ne lance plus `import_service.py` ;
- `OPEN_NELYIO_IMPORTER.bat` + `nelyio_importer_app.py` ajoutés ;
- endpoints Web d'import lourd refusés en mode services ;
- `auto_import_status()` ne scanne plus le dossier import depuis un GET production ;
- Live utilise `sqlite3` natif et `Nelyio_Live.db` local ;
- `db_compat` ne route plus `Nelyio_Live.db` vers PostgreSQL, même si `postgres.env` est actif ;
- les heartbeats `Nelyio_Services.db` utilisent aussi SQLite natif et ne dépendent pas de PostgreSQL ;
- PostgreSQL migration ne migre plus Live ;
- Live ne publie plus dans Support/Détails ;
- Live n'est plus injecté dans Recherche d'appels/Qualité/Détails ;
- polling global Live des écrans historiques supprimé ;
- rétention Live quotidienne + WAL checkpoint + VACUUM après purge ;
- fallback Analytics -> Web supprimé ;
- Details et Calls également délégués à Analytics en mode services ;
- concurrence Analytics lourde bornée à 3 ;
- délais RPC bornés à 20 s ;
- `Travail` Qualité Agents dérivé de présence moins pause/coaching ;
- `Moy. appel entrant` calculée depuis Stats.INBOUND `CallDuration` en priorité ;
- snapshot groupes incomplet ne détruit plus les affectations ACTIVE existantes.

## 4. Tests

### Régression

`pytest` : **51 tests passés** (`audit_regression_test.py`, `group_filter_global_test.py`, `production_stability_test.py`).

### Live

Test isolé :

- création base Live ;
- événements jour courant + J-1 ;
- accusé local sans publication Support ;
- purge J-1 ;
- conservation du jour courant ;
- compactage ;
- SQLite `journal_mode=wal`.

Résultat : **OK**.

### Qualité Agents

Tests ciblés :

- présence 100 s, pauses/coaching 20 s -> Travail 80 s ;
- intervalles recouvrants correctement fusionnés ;
- `CallDuration` Stats.INBOUND 45.5 s + 14.5 s -> moyenne 30.0 s.

Résultat : **OK**.

### Isolation base de données

- `schema_for_database(Nelyio_Live.db) = None` en mode PostgreSQL ;
- `service_state` utilise le module `sqlite3` natif ;
- les données et heartbeats Live/services ne peuvent donc pas retomber sur la base PostgreSQL métier.

Résultat : **OK**.

### Smoke multi-processus

Copie isolée, mode services :

- Web démarre ;
- Live démarre ;
- Analytics démarre ;
- `/healthz` : `services_ok=true` ;
- services : `web=true`, `live=true`, `analytics=true` ;
- Import Worker absent des services requis ;
- Live DB indépendante SQLite/WAL créée.

Résultat : **OK**.

### Arrêt

Stop flags Web/Live/Analytics puis attente :

- Web : code 0 ;
- Live : code 0 ;
- Analytics : code 0.

Résultat : **OK**.

## 5. Limite de validation

Le conteneur de validation n'est pas votre Windows de production et n'exécute pas votre Caddy ni votre instance PostgreSQL réelle avec toute votre volumétrie. V60 corrige cependant les chemins architecturaux qui permettaient à Import/Live/Analytics de bloquer le Web. La validation finale doit donc être faite sur le serveur réel avec `http_slow.log` et un nouveau HAR après déploiement.
