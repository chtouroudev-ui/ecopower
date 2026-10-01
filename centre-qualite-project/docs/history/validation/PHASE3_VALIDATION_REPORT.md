# PHASE 3 — Rapport de validation RC14

## Base

- Source : V60.5-ARCH-RC13 Live Quality Phase 2
- Cible : V60.5-ARCH-RC14 Centre Qualité Live Phase 3

## Régressions

- Suite Python complète : **117/117 réussis** au dernier passage avant packaging.
- Tests Phase 2 Qualité Live : **6/6 réussis**.
- Tests Phase 2 + Phase 3 ciblés : **11/11 réussis**.
- Syntaxe JavaScript : **19 fichiers / 19 valides**.

## Tests Phase 3 ajoutés

1. une collecte périmée ne peut pas produire un statut global `NORMAL` ;
2. zéro règle active produit `INDÉTERMINÉ`, jamais un faux vert ;
3. Campagne et Groupe restent deux scopes distincts ;
4. la couleur et les raisons d'un incident actif sont conservées dans le cockpit ;
5. waiting/P90/abandon/QoS Live non certifiés restent `value=null`, `quality=unavailable`.

## Smoke test backend

Sur la base livrée sans historique d'appels :

- `/api/live/supervision` construit son snapshot même sans session Live ;
- état cockpit : `COLLECTE NON DÉMARRÉE` ;
- `waiting_now.value = null` ;
- `waiting_now.reason = semantics_not_certified` ;
- aucune exception du moteur Qualité.

Mesure locale indicative : environ **10 ms** pour la construction complète sur la base de démonstration vide.

## Benchmark synthétique cockpit

Scénario :

- 114 agents ;
- 30 campagnes ;
- 60 files ;
- 6 groupes ;
- 2 services.

100 constructions de `quality_center()` :

- médiane ~**2,8 ms** ;
- P95 ~**3,0 ms** ;
- payload `center` ~**159 KB**.

Le calcul est réalisé à partir du snapshot déjà chargé ; il n'effectue pas de boucle SQL par campagne/file/agent.

## Performance historique

Le bloc Stats.INBOUND n'est pas exécuté dans la boucle Live 5 s :

- chargement navigateur : maximum une fois par 60 s ;
- endpoint existant `quality_pilotage` ;
- Analytics worker : cache partagé 120 s.

## Sécurité / CSP

- aucune dépendance externe ajoutée ;
- aucune règle `unsafe-inline` ajoutée ;
- les couleurs configurables utilisent l'insertion CSSOM déjà employée par l'administration Qualité Live ;
- droits existants conservés : Collection pour le Centre Live, Quality pour le contexte Stats.INBOUND, Config pour l'éditeur des règles.

## Validation restant obligatoire en production

- HTTPS via Caddy ;
- worker Live réel ;
- session Hermes réelle ;
- PostgreSQL réel ;
- au moins 5 utilisateurs simultanés ;
- mesure payload/latence avec le vrai nombre de campagnes/files ;
- contrôle visuel 1440 px et mobile ≤390 px ;
- validation de la fraîcheur Stats.INBOUND selon le rythme réel d'import.

## Préflight / déploiement code-only

- `preflight.py` : intégrité du code **OK**, syntaxe Python **OK**, quick-check SQLite **OK**.
- Avertissement conservé : `requests 2.32.5` est inférieur à 2.33.0 ; le projet n'appelle pas directement la fonction vulnérable signalée par le préflight. Une mise à niveau doit être suivie d'une recette séparée.
- Recette Windows/HTTPS/Hermes reste explicitement manuelle.
- `deploy_release.py` en simulation vers une extraction RC13 : **succès** ; RC13 est reconnue comme base d'upgrade.
- Le manifeste RC14 protège toujours les `.db`, `data/`, Caddy, certificats, logs et imports lors d'un déploiement code-only.
