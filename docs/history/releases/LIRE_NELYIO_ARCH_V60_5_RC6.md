# Nelyio V60.5 ARCH RC6 — Synchronisation WAV exhaustive

RC6 corrige le cas observé le 18/09/2026 où RC5 ne trouvait que 6 WAV alors que la Supervision en contient davantage.

## Cause traitée

Hermes peut renvoyer un `FolderList` incomplet pour une journée. RC5 suivait correctement les dossiers retournés, mais ne pouvait pas découvrir un dossier agent absent de cette liste.

## Correctif

`recording_sizes.py` effectue maintenant deux passes automatiques :

1. parcours récursif de toute l'arborescence réellement retournée par Hermes ;
2. sondage des dossiers de tous les agents numériques connus de Nelyio via le catalogue SIMPLIFY2, même si l'agent est absent du `FolderList` du jour.

Les résultats sont fusionnés et dédupliqués par nom de WAV. Aucun fichier audio n'est téléchargé ou ouvert.

Des garde-fous limitent la profondeur et le nombre total de requêtes.

## Nouveau résultat affiché

La synchronisation indique désormais notamment :

- agents connus ;
- agents sondés automatiquement ;
- agents supplémentaires ayant réellement des WAV ;
- nombre total de WAV trouvés et stockés.

## Test recommandé

Relancer :

`SYNC_RECORDING_SIZES.bat`

pour :

- début : `2026-09-18`
- fin : `2026-09-18`

Il ne faut ouvrir aucun dossier agent ni aucun fichier WAV manuellement. Si le script demande d'ouvrir Enregistrements, ouvrir uniquement la zone Enregistrements une fois pendant que le BAT reste ouvert.

Le nombre final de WAV doit maintenant être supérieur aux 6 obtenus avec RC5 si les dossiers supplémentaires correspondent à des agents déjà connus de Nelyio.

## Validation

- 96/96 tests Python passent.
- Test dédié : dossier agent absent du `FolderList` mais présent dans l'annuaire Nelyio → WAV récupéré automatiquement.
- Parcours récursif testé sur un sous-dossier supplémentaire.
