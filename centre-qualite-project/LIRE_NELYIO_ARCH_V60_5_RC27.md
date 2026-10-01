# Nelyio V60.5 ARCH RC27

## Correctif critique RC26

RC27 corrige les erreurs observées après RC26 :

- `scope_query() takes 2 positional arguments but 3 were given` ;
- HTTP 400 sur `/api/quality/agent-activity` et `/api/quality/pilotage` ;
- HTTP 500 sur `/api/supervision/support`, `/api/supervision/details` et `/api/supervision/analytics`.

La cause était un appel positionnel vers une API devenue volontairement keyword-only : `scope_query(user, query, *, param="group")`. Tous les appels concernés utilisent maintenant `param="group"`.

## Signalisation Qualité Live

L'éditeur permet désormais de cibler :

- un ou plusieurs groupes ;
- un ou plusieurs agents ;
- une ou plusieurs campagnes ;
- une ou plusieurs files ;
- un ou plusieurs services ;
- ou toutes les cibles d'un type en laissant la sélection vide.

Les anciennes règles mono-cible restent compatibles. Plusieurs cibles sont sérialisées dans le champ existant `target_key`; aucune migration de schéma n'est nécessaire.

### UI guidée

Une seule règle est ouverte à la fois. L'éditeur sépare :

1. la règle et son niveau ;
2. le type de cible ;
3. les cibles avec recherche et sélection multiple ;
4. les conditions ;
5. l'anti-bruit et les temporisations.

Les champs de durée indiquent explicitement l'unité avec des exemples gris, par exemple `120 s = 2 min` et `300 s = 5 min`. Les métriques en secondes, pourcentage ou nombre affichent également un exemple adapté.

### Sécurité

Pour un compte non-admin, les cibles `GROUP`, `AGENT` et `QUEUE` sont vérifiées côté serveur contre le périmètre métier autorisé lors de l'enregistrement d'une règle.

## Déploiement

RC27 est un upgrade code-only depuis RC26. Les bases SQLite, Caddyfile, certificats, journaux et imports restent protégés.
