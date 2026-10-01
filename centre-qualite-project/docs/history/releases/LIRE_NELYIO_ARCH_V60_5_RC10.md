# Nelyio-ARCH V60.5-ARCH-RC10 — Historique complet, Indice + Size

## Objectif

Synchroniser les métadonnées d'enregistrements Hermes pour **tout l'historique**, sans télécharger aucun WAV, et ne conserver que ce qui est nécessaire à Nelyio :

- `Indice`
- `Size` en octets

La hiérarchie Hermes est utilisée seulement pour le parcours :

`SDA/campagne -> année -> mois -> jour -> login agent -> WAV`

Elle n'est pas persistée.

## Utilisation

Ouvrir Edge de collecte, se connecter à la Supervision, puis ouvrir **Enregistrements** et rester au niveau des SDA/campagnes.

Lancer `SYNC_RECORDING_SIZES.bat`.

Le mode par défaut est **TOUT**. Nelyio découvre toutes les journées disponibles et les traite automatiquement. Le mode `PLAGE` reste disponible pour rescanner une période précise.

## Reprise

Le mode TOUT enregistre uniquement sa progression technique dans `data/recording_size_sync_state.json`. Après interruption, il reprend les anciennes journées déjà terminées et rescane les jours récents.

## Stockage

Table active : `call_recording_sizes`.

| Colonne | Rôle |
|---|---|
| `indice` | jointure avec l'appel SIMPLIFY2 |
| `size_bytes` | taille WAV totale agrégée de cet Indice |

Si plusieurs WAV correspondent au même Indice, leur taille est additionnée. `Indice=0` est ignoré.

Aucun audio, nom WAV, agent, date/heure de fichier, chemin, SDA/campagne, cookie, UID ou mot de passe n'est persisté.

## Compatibilité

Les anciennes lignes RC4-RC9 de `call_recordings` sont migrées par agrégation vers la nouvelle table. Elles restent en place uniquement pour compatibilité ; RC10 n'y écrit plus.

## Validation

- 104/104 tests Python ;
- syntaxe Python/JavaScript vérifiée ;
- HAR utilisateur réel : 185 WAV exploitables -> 182 Indices uniques ;
- table active vérifiée avec exactement `indice` + `size_bytes`.
