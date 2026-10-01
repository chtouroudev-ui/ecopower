# Nelyio V60.5 ARCH RC21 — Durcissement production Phase 10

RC21 continue directement RC20. Cette phase réduit la surface de dépendances et transforme les seuils de performance en paramètres techniques explicites, sans toucher aux KPI métier.

## Dépendance HTTP externe supprimée

Le seul usage direct de `requests` se trouvait dans l'ancienne capture locale Edge DevTools pour lire `http://127.0.0.1:9222/json`. RC21 utilise désormais `urllib.request`, inclus dans Python.

Conséquences :

- `requests` sort de `requirements.txt` ;
- le preflight n'exige plus cette bibliothèque ;
- aucun changement du protocole Hermes/CDP ni des données capturées ;
- le composant Live conserve `websockets` comme dépendance dédiée.

## Seuils de performance configurables

Les valeurs par défaut restent prudentes et peuvent être ajustées uniquement par environnement :

- `NELYIO_HTTP_SLOW_SECONDS=1.0` : journalisation Web lente ;
- `NELYIO_ANALYTICS_SLOW_SECONDS=2.0` : journalisation Analytics lente ;
- `NELYIO_OBS_SLOW_EVENTS_PER_HOUR=5` : passage **À SURVEILLER** ;
- `NELYIO_OBS_CRITICAL_SLOW_EVENTS_PER_HOUR=20` : volume critique ;
- `NELYIO_OBS_CRITICAL_SLOW_SECONDS=10.0` : latence ponctuelle critique.

Ces seuils pilotent uniquement l'observabilité technique. Ils ne changent ni QoS, ni abandon, ni P90, ni règles de qualité métier.

## Test de charge prolongée

`TEST_CHARGE_PROLONGEE.bat` utilise par défaut 5 sessions authentifiées indépendantes pendant 5 minutes et interroge des endpoints agrégés bornés : Live, Campagnes, Pilotage Qualité, Groupes et Qualité de service.

Le rapport est écrit dans :

`logs\soak_test_production.json`

Le test :

- vérifie `/healthz` avant et après ;
- compte toutes les erreurs HTTP ;
- calcule médiane, P95 et maximum ;
- garde un résumé par scénario ;
- ne modifie aucune donnée métier ;
- crée uniquement les sessions/audits de connexion Nelyio habituels.

Le résultat le plus récent apparaît dans **Administration → Santé de production**.

## Recette recommandée

1. `VALIDATION_PRODUCTION.bat`
2. démarrer Nelyio
3. `RECETTE_PRODUCTION.bat`
4. `TEST_CHARGE_PROLONGEE.bat`
5. vérifier **Administration → Santé de production**
6. tester HTTPS depuis un autre poste du LAN

Les seuils ne doivent être ajustés qu'après observation de mesures réelles et documentées sur votre serveur.
