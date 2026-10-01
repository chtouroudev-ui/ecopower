# Nelyio V60.5-ARCH-RC24 — Phase 13 : Profils d’accès réutilisables

RC24 part de RC23 et améliore `Administration > Utilisateurs & accès` sans changer les règles de sécurité introduites en Phase 12.

## Nouveau

- créer un profil depuis un groupe d’accès existant ;
- dupliquer un profil sans utilisateur ;
- actualiser un profil depuis un groupe d’accès ;
- créer un nouveau groupe d’accès depuis un profil ;
- dupliquer un groupe d’accès sans copier ses membres ;
- appliquer explicitement un profil à un groupe existant.

Un profil contient uniquement :

- les droits de toutes les interfaces Nelyio ;
- le droit sensible ANI ;
- le mode de périmètre métier `ALL` ou `SELECTED` ;
- les groupes métier autorisés ;
- le groupe par défaut ;
- l’état verrouillé ou modifiable du filtre Groupe.

## Sécurité

Créer ou modifier un profil ne modifie aucun utilisateur. Lorsqu’un profil est appliqué à un groupe d’accès existant, les membres restent dans ce groupe, mais leurs autres sessions sont invalidées pour recharger immédiatement les nouveaux droits.

La duplication d’un groupe copie la configuration de sécurité, jamais les membres. Un profil qui référence un groupe métier supprimé est refusé : Nelyio ne bascule jamais automatiquement vers `Tous les groupes`.

## Exemples d’usage

Vous pouvez préparer des profils comme `Superviseur MEDICAL`, `Superviseur IMAGERIE`, `Direction`, `Support technique` ou `Lecture seule`, puis créer rapidement les groupes réels à partir de ces modèles. Les profils ne sont pas imposés automatiquement : l’administrateur choisit toujours quand les appliquer.
