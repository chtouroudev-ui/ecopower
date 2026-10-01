# RC29.4 LIVE CENTER FIX5.1 — Validation Hermes

## Objet

FIX5.1 corrige les deux anomalies constatées après déploiement de FIX5 :

1. **Ouvrir la supervision Hermes** pouvait retourner une demande acceptée alors qu'Edge/CDP ou l'onglet Supervision n'était finalement pas disponible.
2. Dans **Diagnostic Hermes**, les boutons pouvaient sembler sans effet, car le worker était lancé en arrière-plan sans progression suffisamment visible et les gestionnaires de clic dépendaient du DOM réaffiché.

FIX5.1 ne modifie aucune formule QoS/KPI et ne réinitialise aucune base.

## Corrections appliquées

### Ouverture Supervision Hermes

- `OPEN_HERMES_SUPERVISION.ps1` vérifie désormais réellement :
  - la présence d'Edge ;
  - la disponibilité du port CDP local ;
  - la présence d'un onglet Hermes/Supervision.
- Si le profil Edge dédié `TECH-IN\Nelyio\CaptureBrowser` est déjà lancé mais sans CDP exploitable, seuls les processus `msedge.exe` correspondant exactement à ce profil dédié peuvent être redémarrés.
- Les sessions Edge utilisateur ordinaires ne sont jamais ciblées.
- Les erreurs d'ouverture/CDP/onglet sont remontées au worker et à l'interface au lieu d'être masquées.
- Les domaines `fr06-supervision.vocalcom.com` et `fr06-cloud.vocalcom.com` sont reconnus comme cibles Hermes valides.

### Worker et statut Supervision

- `hermes_supervision_worker.py` publie un état dans `run/hermes_supervision_state.json` :
  - `opening_browser`
  - `browser_ready`
  - `auto_login`
  - `completed`
  - `error`
- `hermes_supervision_launcher.py` attend un état réel du worker et ne considère plus le simple `Popen()` comme un succès.
- Une route admin dédiée expose le statut de l'ouverture au frontend.
- Aucun mot de passe ni secret DPAPI n'est écrit dans le fichier d'état ou les journaux.

### Diagnostic Hermes

- Les étapes suivantes sont maintenant visibles dans l'interface :
  - Préparation
  - Vérification Edge
  - Ouverture Edge
  - Attente Hermes
  - Analyse en cours
  - Terminé
  - Erreur
- Les actions admin utilisent une délégation d'événements stable côté document : un réaffichage de la carte ne détache plus les boutons.
- Le statut est interrogé toutes les secondes pendant une opération active.
- Le scanner vérifie la dépendance `websockets` avant de lancer le worker et renvoie une erreur explicite si elle manque.
- Si l'option d'ouverture automatique est désactivée et qu'aucun onglet Supervision n'est détecté, l'utilisateur reçoit immédiatement une erreur explicite.
- Les états intermédiaires sont traités comme états actifs et ne sont plus nettoyés comme verrou obsolète.

## Validation automatique

- Tests Hermes ciblés : **33/33 passés**.
- Tests spécifiques FIX5.1 : **3/3 passés**.
- Suite complète : **338/338 passés**.
- Syntaxe JavaScript validée avec Node.
- Bases restaurées après les tests et vérifiées bit-à-bit par SHA-256.

## SHA-256 des bases inchangées

- `NELYIO_Supervision.db` : `6af62dcc211d1b4bdde98aeacc355d61f346b8b99d8ff7a1abe74a10c5b34175`
- `Nelyio_Details.db` : `859947ff7912879caa06cf06b22c2f06e624b4723ed25f2c7cc6dbe9c2455610`
- `Nelyio_Live.db` : `285ee7bebf86ff0174833b3bc42f1c5cc96d7d50be2199f0d21d8ac24afa8e2e`
- `Nelyio_Services.db` : `8cfab256b675709de4bb2a899024e04aca2e09b581b3bbe5db266afac7a6dd2d`
- `TECHIN_Stock_Manager.db` : `52c511ce7dfe269fa33e6e405065595da65fc7b02c0a66915bd948c0e59d8cfc`

## Contrôle à effectuer sur le serveur Windows

Le comportement réel d'Edge/CDP et de la session Hermes doit encore être testé sur le serveur Nelyio, car l'environnement de génération n'est pas Windows et ne possède pas la session Vocalcom réelle.

En cas d'échec, FIX5.1 doit désormais afficher l'étape précise dans l'interface. Les journaux utiles sont notamment :

- `logs/open_hermes_supervision_error.log`
- `logs/hermes_supervision_auto.jsonl`
- les journaux du Diagnostic Hermes affichés dans Administration > Collecteur Live.

Cette limitation est explicitement conservée : les tests automatisés valident le code et les garde-fous, pas une authentification réelle contre le site Vocalcom du client.

## Gate de livraison

- Manifeste production final : **483 fichiers**.
- Vérification SHA-256 du manifeste : **483/483 OK**.
- Simulation du patch FIX5 -> FIX5.1 sur une copie de FIX5 : **OK**.
- Après simulation, les cinq bases `.db` sont restées strictement inchangées.
- Le patch ne contient aucune base SQLite et aucun fichier secret DPAPI.
