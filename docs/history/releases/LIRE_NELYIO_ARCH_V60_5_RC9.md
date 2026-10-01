# Nelyio-ARCH V60.5-ARCH-RC9 — Recording hierarchy fix

## Correction
La hiérarchie Hermes observée est :

`SDA / campagne -> année -> mois -> jour -> login / ID agent -> WAV`

RC9 ne demande plus de cliquer sur un dossier nommé `18/09/2026`.

## Utilisation
1. Ouvrir Edge de collecte et la Supervision.
2. Ouvrir la fenêtre **Enregistrements** et rester au niveau des SDA/campagnes.
3. Lancer `SYNC_RECORDING_SIZES.bat`.
4. Saisir la date de début et de fin.
5. Ne pas ouvrir manuellement année, mois, jour, agent ou WAV.

Nelyio détecte les SDA/campagnes puis construit automatiquement, pour chaque racine :

`<SDA>\AAAA\MM\JJ\<agent>`

et récupère uniquement les métadonnées des WAV (`Name`, `Size`, `Indice`), sans télécharger l'audio.

## Validation
- 101/101 tests Python.
- `extract_seed()` accepte maintenant la requête RECORD de niveau racine (`subPath=`).
- test multi-racines sans clic jour ajouté.
