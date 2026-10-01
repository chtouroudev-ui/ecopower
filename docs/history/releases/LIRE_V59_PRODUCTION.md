# NELYIO V59.1 — démarrage production

Version : **59.1-PROD-STABLE**

Lire d’abord `docs/history/validation/V59_VALIDATION_REPORT.md`.

## HTTP local / recette

Utiliser `START_NELYIO.bat` ou `START_NELYIO_9051.bat`.

Le stack attendu est :

- Backend Web/API : `127.0.0.1:9051`
- Analytics Worker : `127.0.0.1:9052`
- Import Worker : processus séparé
- Live Service : processus séparé

Vérifier `http://127.0.0.1:9051/healthz`. Le build doit être **59.1-PROD-STABLE** et `services_ok` doit être `true`.

## HTTPS

Caddy reste volontairement externe au ZIP. Fournir `caddy.exe` via la racine du projet, `tools\`, le `PATH`, ou `NELYIO_CADDY_EXE`.

1. `VERIFIER_LANCEUR_HTTPS.bat`
2. `START_NELYIO_HTTPS.bat`
3. ouvrir `https://stock-manager.nelyio.local:9050/`

Le HTTPS est un reverse proxy : Python reste uniquement sur HTTP local 9051.

## Arrêt

Utiliser `STOP_NELYIO_ALL.bat`. V59.1 demande d’abord un arrêt gracieux aux workers et au backend; un kill forcé n’est utilisé qu’en secours et uniquement pour les processus identifiés comme appartenant au projet.

## Groupes

Règle unique : **Groupe -> files du Groupe -> agents ACTIVE sur ces files**. Les affectations `partial`, `inactive` et `unknown` sont exclues. Un agent peut appartenir à plusieurs Groupes.

Si le snapshot Agents.csv manque, la récupération est faite par l’Import Worker hors des requêtes Web puis le scope Groupe est invalidé/reconstruit.
