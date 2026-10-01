# Nelyio V60.5-ARCH-RC23 — Phase 12 : Accès par interface et périmètre métier

RC23 part de RC22 et renforce `Administration > Utilisateurs & accès`.

## Objectif

Un groupe d'accès contrôle désormais deux dimensions indépendantes :

1. **Interfaces Nelyio** : aucun accès, lecture seule, ou lecture + modification lorsque l'interface supporte l'écriture.
2. **Périmètre métier** : tous les groupes, ou seulement une liste de groupes autorisés, avec groupe par défaut et filtre Groupe éventuellement verrouillé.

Les administrateurs système conservent l'accès total permanent.

## Centre Qualité Live

Le Centre Qualité Live expose un filtre **Groupe surveillé**.

- `Tous les groupes` : possible uniquement si le périmètre d'accès l'autorise.
- `Groupes sélectionnés` : seuls les groupes autorisés sont proposés.
- `Filtre verrouillé` : le groupe par défaut est imposé et l'utilisateur ne peut pas changer de périmètre.

Le filtrage est appliqué côté serveur aux agents, KPI et incidents retournés. Un groupe non autorisé ne peut pas être récupéré en modifiant manuellement l'URL.

## Toutes les interfaces

L'écran `Utilisateurs & accès` permet de régler les droits pour toutes les vues de navigation : Parc, Live, Support, Analytiques et Administration.

Les droits frontend ne sont qu'une projection visuelle. Les endpoints API correspondants appliquent également les droits d'interface côté serveur.

`Priorités Support` possède une API dédiée et ne nécessite plus d'exposer toute la configuration `Règles de classement` à un utilisateur autorisé uniquement sur cet écran.

## Périmètre métier

Le périmètre métier est indépendant des groupes de sécurité :

- groupe d'accès = sécurité / droits ;
- groupe métier = équipes / files / agents utilisés dans les analyses.

Les écrans concernés filtrent selon les groupes autorisés : Live, campagnes, incidents, recherche Live, Qualité, groupes/agents/files et autres vues métier déjà compatibles.

## Compatibilité

Les anciens droits par module sont conservés comme compatibilité technique et pour la capacité ANI. Les nouveaux droits d'interface sont prioritaires pour la navigation et les routes dédiées.

Les bases de données ne sont pas remplacées par l'upgrade code-only ; les nouvelles tables d'accès sont créées/mises à niveau par le schéma applicatif existant.
