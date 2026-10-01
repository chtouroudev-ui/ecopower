# Nelyio ARCH V60.5 RC8 — synchronisation WAV multi-racines Hermes

RC8 corrige le dernier défaut de couverture observé avec RC7.

## Cause confirmée

La fenêtre **Fichiers enregistrés** ne possède pas une seule racine RECORD. Elle contient plusieurs dossiers de premier niveau, par exemple :

- `76430929 - CH GISORS`
- `76430994 - CIMVES-ST MARTIN`
- `76431213 - CIMVES-HABERGES`

Chaque racine suit ensuite la hiérarchie :

`racine cabinet -> année -> mois -> jour -> ID agent -> WAV`

RC7 ancrait correctement la session sur un clic réel du jour mais ne couvrait qu'une seule racine. Le résultat pouvait donc annoncer 93 dossiers agents et seulement quelques WAV, alors que d'autres cabinets contenaient les autres enregistrements.

## RC8

Après la saisie des dates :

1. laisser `SYNC_RECORDING_SIZES.bat` ouvert ;
2. cliquer une seule fois sur le dossier du jour demandé quand Nelyio le demande ;
3. ne cliquer sur aucun cabinet supplémentaire, aucun agent et aucun WAV.

Nelyio découvre ensuite automatiquement toutes les racines RECORD chargées dans la fenêtre Enregistrements et les parcourt pour la date demandée.

Le résultat affiche désormais notamment :

- `racines RECORD`
- `racines avec WAV`
- `dossiers agents parcourus`
- `dossiers agents vus au clic jour`
- `fichiers WAV`
- `stockés`

Aucun fichier audio n'est téléchargé. Seules les métadonnées `Nom/Indice/Date/Heure/Size` sont stockées.

## Appels suspects

La logique RC4/RC3 reste inchangée : la densité média sert uniquement d'indice de contenu faible, et les transferts/consultations/reroutages, mises en attente et Indices multi-WAV sont exclus de cette heuristique.
