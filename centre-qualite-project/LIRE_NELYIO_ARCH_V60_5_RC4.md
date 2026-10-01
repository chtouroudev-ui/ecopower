# Nelyio V60.5-ARCH-RC4 — Recording size / contenu faible

RC4 part de RC3 et ajoute la collecte automatique des tailles WAV Hermes sans téléchargement audio.

## Ce qui a été prouvé par le HAR fourni

Le second HAR contient des réponses `folder_info` complètes avec `FileList`.

Exemple réel :

`1079#20260824#085611#781592555.wav` → `Size=237504`.

Le format permet de récupérer directement : agent, date, heure et Indice. L'Indice rejoint `phone_calls.indice`.

Le HAR de validation contient 186 fichiers WAV, 41 jours distincts et 12 agents.

## Synchronisation automatique

1. Ouvrir la fenêtre Edge de collecte Nelyio et se connecter à la supervision.
2. Ouvrir une seule fois la zone Enregistrements pendant cette session navigateur.
3. Lancer `SYNC_RECORDING_SIZES.bat`.
4. Choisir la plage de dates (maximum 31 jours par passage).

Nelyio parcourt automatiquement : jour → dossiers agents → FileList.

Il ne télécharge jamais les WAV. Les paramètres de session `uid`/cookies restent uniquement dans Edge et ne sont pas enregistrés.

Pour un HAR existant, glisser le HAR sur `IMPORT_RECORDING_SIZES_HAR.bat` ou saisir son chemin.

## Appels suspects

La catégorie `Contenu faible / size anormal` est maintenant active dès que des métadonnées WAV existent.

Elle est exclue si :

- l'appel possède une mise en attente ;
- il existe un transfert, une consultation ou un reroutage ;
- plusieurs WAV existent pour le même Indice ;
- la durée média est inférieure à 30 secondes.

Référence initiale : 8 000 octets/s. Seuil faible : 60 %. Seuil critique : 35 %.

Ces valeurs sont conservées dans les paramètres supervision (`recording_reference_bps`, `recording_low_percent`, `recording_critical_percent`, `recording_min_seconds`) et peuvent être ajustées après observation réelle.

## Validation

- 94/94 tests Python ;
- import du HAR fourni : 186 WAV ;
- aucune donnée audio téléchargée ;
- jointure par Indice ;
- exclusion hold/transfert/consultation/reroutage testée ;
- PostgreSQL/HTTPS réel à revalider sur le serveur avant promotion production.
