# Nelyio ARCH V60.5 RC7 — ancrage réel sur le jour Hermes

RC7 corrige le diagnostic des tailles WAV lorsque le crawl automatique retourne trop peu de fichiers.

## Utilisation
1. Ouvrir Edge de collecte et la Supervision.
2. Lancer `SYNC_RECORDING_SIZES.bat`.
3. Saisir la date, par exemple `2026-09-18`.
4. Laisser le BAT ouvert.
5. Dans Enregistrements, naviguer Année -> Mois puis cliquer **une seule fois sur le jour 18** quand le BAT le demande.
6. Ne cliquer sur aucun ID utilisateur ni aucun WAV.

RC7 capture la requête et la réponse `folder_info` réellement générées par Hermes pour le jour sélectionné. Il utilise directement cette `FolderList` comme niveau racine, puis parcourt automatiquement les utilisateurs et les WAV.

Le résumé affiche `dossiers agents vus au clic jour`. Cette valeur permet de distinguer une liste de jour incomplète renvoyée par Hermes d'un problème de crawl Nelyio.

Aucun fichier audio n'est téléchargé.
