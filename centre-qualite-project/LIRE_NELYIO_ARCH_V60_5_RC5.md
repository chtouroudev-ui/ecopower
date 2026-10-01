# Nelyio V60.5 ARCH RC5 — Correctif AutoSync tailles WAV

RC5 est un correctif ciblé de RC4. Les règles Appels suspects / size restent identiques.

## Correction

RC4 pouvait manquer la requête Hermes `folder_info` si l'utilisateur avait ouvert Enregistrements avant la connexion CDP ou si la requête provenait d'une iframe de la supervision.

RC5 :

1. se connecte d'abord à Edge/CDP ;
2. inspecte la page principale et les iframes same-origin ;
3. si aucune requête précédente n'est disponible, reste en écoute 75 secondes ;
4. demande d'ouvrir Enregistrements une seule fois pendant cette écoute ;
5. récupère ensuite automatiquement les métadonnées jour -> dossiers agents -> WAV.

Aucun fichier audio n'est téléchargé. Aucun dossier agent n'a besoin d'être ouvert manuellement.

## Utilisation

- laisser l'onglet Supervision connecté dans l'Edge de collecte ;
- lancer `SYNC_RECORDING_SIZES.bat` ;
- saisir les dates ;
- si le message INFO apparaît, laisser le BAT ouvert et cliquer une seule fois sur Enregistrements ;
- ne pas relancer le BAT après le clic : il doit détecter la requête en direct.

Le `DeprecationWarning` WebSocket observé en RC4 est également corrigé.
