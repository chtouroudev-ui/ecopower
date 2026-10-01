# RC29.4 LIVE CENTER FIX5.2 — Validation Detection automatique

## Objet

FIX5.2 corrige le cas signale ou **Detection automatique** reste affichee sur
`En attente de la plage horaire` alors que la plage configuree est deja active.

Le correctif est cumulatif avec FIX5.1 : les corrections **Ouvrir la supervision
Hermes** et **Diagnostic Hermes** sont conservees.

## Cause confirmee dans le code

Le frontend associait toujours `connection_state=waiting` au libelle
`En attente de la plage horaire`, sans verifier l'heure serveur ni la plage
effective. Ainsi, une session armee mais non encore prise en charge par le worker
Live pouvait etre presentee comme une simple attente horaire, meme une fois la
plage commencee.

Le service Live relancait bien `resume()` periodiquement, mais le diagnostic ne
separait pas clairement :

- attente avant le debut de plage ;
- session due dans une plage deja active ;
- attente Edge / onglet Hermes.

## Corrections appliquees

### Etat de plage explicite

`collection_service.auto_window_state()` expose maintenant :

- heure serveur Europe/Paris ;
- jour actif ou non ;
- heure de debut / fin ;
- phase `before_window`, `active_window`, `after_window`, `inactive_day` ou
  `disabled` ;
- eligibilite immediate de l'automatisme.

### Interface Collecteur Live

L'interface n'affiche plus systematiquement `En attente de la plage horaire`
pour une session `waiting`.

Pendant une plage deja active elle affiche maintenant :

`Plage active - demarrage automatique en cours`

avec **Heure serveur** et **Plage auto** visibles dans le bloc d'etat.

### Auto-recovery cible

Le worker Live :

1. tente toujours `resume()` avant l'auto-armement ;
2. verifie l'auto-armement ;
3. retente systematiquement `resume()` apres cette verification ;
4. si une session du jour reste anormalement en `waiting` plus de 12 secondes
   alors que sa plage est deja active, un watchdog demande une reprise propre.

Le watchdog ne vole jamais un bail valide a un autre worker et ne touche pas a
`waiting_browser`, qui conserve sa boucle de reconnexion Edge/Hermes 5-10 s.

## Validation

- Tests Detection automatique cibles : **25/25 passes**.
- Suite complete : **343/343 passes**.
- Syntaxe Python : OK.
- Syntaxe JavaScript : OK.
- Bases SQLite restaurees apres tests et strictement identiques a FIX5.1.

### SHA-256 bases inchangees

- `NELYIO_Supervision.db` : `6af62dcc211d1b4bdde98aeacc355d61f346b8b99d8ff7a1abe74a10c5b34175`
- `Nelyio_Details.db` : `859947ff7912879caa06cf06b22c2f06e624b4723ed25f2c7cc6dbe9c2455610`
- `Nelyio_Live.db` : `285ee7bebf86ff0174833b3bc42f1c5cc96b7d50be2199f0d21d8ac24afa8e2e`
- `Nelyio_Services.db` : `8cfab256b675709de4bb2a899024e04aca2e09b581b3bbe5db266afac7a6dd2d`
- `TECHIN_Stock_Manager.db` : `52c511ce7dfe269fa33e6e405065595da65fc7b02c0a66915bd948c0e59d8cfc`

## Controle serveur recommande

Apres redemarrage, dans **Administration > Collecteur Live** :

1. verifier `Heure serveur` ;
2. verifier `Plage auto` ;
3. si l'heure est comprise dans la plage, l'etat ne doit plus rester sur
   `En attente de la plage horaire` ;
4. il doit passer vers `Connexion au navigateur`, puis `En attente d'Edge / de
   l'onglet de supervision` ou `Donnees recues` selon la disponibilite Hermes.

Si la capture ne progresse toujours pas, le nouvel affichage permet de distinguer
un probleme horaire d'un probleme worker/Edge/Hermes au lieu de les confondre.
