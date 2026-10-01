# Nelyio V60.5 ARCH RC20 — Observabilité production

RC20 continue directement RC19. Cette phase n'ajoute aucun nouveau moteur métier : elle rend visible, dans l'application, l'état technique réellement utile à l'administrateur.

## Nouveau

Dans **Administration → Santé de production**, Nelyio affiche en lecture seule :

- état Web / Live / Analytics à partir des heartbeats locaux ;
- disponibilité et latence du probe PostgreSQL ;
- fraîcheur de la collecte Hermes lorsqu'une session Live est active ;
- nombre de sessions Nelyio valides et vues dans les 10 dernières minutes ;
- mode de l'import et nombre de fichiers en attente ;
- dernière recette `RECETTE_PRODUCTION.bat` détectée ;
- requêtes Web lentes agrégées par endpoint, sans query string ;
- calculs Analytics lents agrégés par type de calcul.

## Confidentialité

L'écran n'expose ni ANI, ni numéro patient, ni valeur de filtre, ni mot de passe. Il ne fait aucune écriture métier et ne lance/arrête aucun service.

## Anti-charge

Le backend partage un snapshot de 5 secondes entre tous les administrateurs. Le navigateur actualise toutes les 10 secondes avec une seule boucle active. Un rafraîchissement manuel ne crée pas une deuxième boucle.

## Lecture des statuts

- **OK** : services requis + PostgreSQL disponibles, aucun signal technique agrégé.
- **À surveiller** : par exemple Live actif mais périmé ou répétition de lenteurs.
- **Dégradé** : service requis ou PostgreSQL indisponible.

Une session Live inactive n'est pas déclarée en panne simplement parce qu'aucune collecte n'est en cours.

## Limites assumées

- les sessions authentifiées ne sont pas un compteur exact d'utilisateurs humains simultanés ;
- l'absence de ligne dans `http_slow.log` ne prouve pas que le LAN ou le navigateur est rapide ;
- le test HTTPS depuis un autre poste du LAN reste une preuve externe ;
- la recette RC19 reste la procédure de validation avant feu vert production.
