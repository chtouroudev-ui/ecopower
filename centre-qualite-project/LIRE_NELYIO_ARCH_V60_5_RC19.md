# Nelyio-ARCH V60.5 RC19 - Phase 8 Recette production assistee

## Base
RC19 derive exclusivement de **RC18 Analytiques Phase 7**.

## Objectif
Ne pas ajouter une nouvelle architecture. RC19 consolide la recette finale sur le serveur cible avec un controle rejouable et documente avant bascule production.

## Nouveau parcours
Lancer :

`RECETTE_PRODUCTION.bat`

Le script PowerShell demande :
- l URL HTTPS Nelyio a verifier ;
- un compte Nelyio possedant au minimum la lecture Live, Qualite, Groupes et Configuration ;
- le mot de passe de facon masquee.

Le mot de passe n est jamais ecrit dans les rapports et est efface de l environnement du processus a la fin.

## Controles consolides
La recette appelle ou verifie :
- le preflight statique de l archive ;
- le preflight PostgreSQL **sans --repair** ;
- `/healthz` interne avec build, PostgreSQL, architecture services et heartbeats ;
- l acces HTTPS public et la confiance TLS ;
- une authentification Nelyio et les droits minimum du compte de recette ;
- `/api/services/status` ;
- `/api/groups/status` ;
- `/api/live/supervision` ;
- `/api/live/campaigns` ;
- `/api/quality/pilotage` ;
- la disponibilite de la source Agents/Queues pour les groupes ;
- la fraicheur Hermes sans transformer l absence de donnee en succes ;
- la coherence Qualite de la journee disponible ;
- un benchmark de 5 sessions authentifiees independantes ;
- les nouvelles entrees `logs/http_slow.log` creees pendant la recette.

## Resultat
Rapports generes localement :
- `logs/recette_production.json` ;
- `logs/RECETTE_PRODUCTION.md` ;
- `logs/recette_postgres_runtime.json`.

Etats :
- **GO** : aucun FAIL et aucune etape automatisee ignoree ;
- **INCOMPLET** : pas d echec bloquant, mais une preuve requise n a pas ete executee ;
- **BLOQUE** : au moins un controle bloquant a echoue.

La verification depuis **un autre poste du LAN** reste une preuve externe obligatoire lorsque la recette est lancee directement sur le serveur.

## Securite / effets de bord
- aucune regle, groupe, appel, incident ou KPI n est modifie ;
- `postgres_runtime_preflight.py` est lance sans mode repair ;
- la connexion de recette cree uniquement les sessions et lignes d audit habituelles de Nelyio ;
- aucune reponse API contenant ANI/appels n est copiee en entier dans le rapport ; seules des syntheses techniques sont conservees.

## Performance
Le seuil de surveillance du benchmark est configurable avec `NELYIO_ACCEPT_WARN_SECONDS` ou `--warn-seconds`.
Il sert uniquement a signaler une latence a examiner ; il ne change aucune regle metier et un WARN n est jamais interprete comme un resultat positif.

## Point d arret sur
RC19 est la base de recette production assistee. Les ecarts observes sur le serveur reel doivent ensuite etre corriges de facon ciblee, sans nouvelle rearchitecture speculative.
