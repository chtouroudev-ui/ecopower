# Nelyio V60.5-ARCH-RC25 — Phase 14 : UI Utilisateurs & accès simplifiée

RC25 part de RC24 et refond uniquement l’expérience d’administration de `Utilisateurs & accès`. Le modèle de sécurité RC23/RC24 reste inchangé côté serveur.

## Nouvelle organisation

L’écran est séparé en quatre onglets :

- `Comptes` : recherche, filtres, création repliable, affectation directe et affectation en masse à un groupe d’accès ;
- `Groupes d’accès` : liste compacte à gauche et un seul groupe ouvert en édition à droite ;
- `Profils` : cartes compactes avec actions repliées ;
- `Droits effectifs` : vue en lecture seule des interfaces et du périmètre réellement calculés par le backend pour un utilisateur.

## Réduction de l’encombrement

Les droits d’un groupe ne sont plus tous affichés simultanément. Les interfaces sont regroupées par section (Parc, Live, Support, Analytiques, Administration) dans des blocs repliables. Le périmètre métier et la liste des groupes autorisés sont également repliables.

Les formulaires `Créer un compte`, `Créer un groupe` et `Créer un profil` sont fermés par défaut et ne prennent de place que lorsqu’ils sont utilisés.

## Administration en masse

Dans l’onglet Comptes, l’administrateur peut sélectionner plusieurs comptes visibles après filtrage et les affecter au même groupe d’accès. L’opération réutilise l’API serveur existante pour chaque compte ; elle ne contourne donc aucune validation ou invalidation de session existante.

## Droits effectifs

La vue `Droits effectifs` affiche les droits calculés par le backend : niveau par interface, droit ANI, groupe d’accès et périmètre métier effectif. Cette vue n’est pas un simulateur local et ne modifie aucune donnée.
