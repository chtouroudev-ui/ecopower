# NELYIO V60.5-ARCH-RC2 — À lire avant validation

Cette archive est un **candidat de validation production**, construit sur Nelyio-ARCH.

## Ce qui change

- service parent configurable pour les groupes ;
- Pilotage Qualité ;
- Actions et évolution avant/après ;
- Appels suspects ;
- compteur **Appels traités** de Qualité agents corrigé par Stats.AGENT / SessionID unique (transferts conservés) ;
- `<10 s` retiré de Qualité agents et centralisé ;
- ODCalls enrichi de façon rétrocompatible ;
- Supervision Live et Recherche d'appels Live séparées ;
- permission ANI indépendante ;
- diagnostic admin Live ;
- historique factuel des observations Live finalisées ;
- protection contre la purge d'une preuve Live non synchronisée.

## Ce qui ne change pas

- la formule QoS validée ;
- les imports SIMPLIFY2 comme source autoritative des KPI historiques ;
- PostgreSQL comme persistance de production ;
- le principe Groupe -> files -> agents ACTIVE ;
- Policies / Déclarations ;
- l'isolation Web / Analytics / Live / Importer.

## Important

Aucun groupe n'est automatiquement classé MEDICAL ou IMAGERIE. Renseignez le **Service parent** dans l'éditeur Groupes.

L'historique Live ne remplace pas ODCalls : il conserve seulement des observations factuelles finalisées et ne contient pas d'ANI.

## Validation déjà effectuée

- 91/91 tests Python ;
- 18/18 JS valides ;
- compileall ;
- import réel 21/09/2026 ;
- 15 507 appels + 15 507 détails ;
- 11 051 interactions Qualité agents Stats.AGENT vs 10 952 records attribués Stats.INBOUND sur 21/09, sans changement de QoS ;
- re-import idempotent ;
- benchmark 5 lecteurs simultanés en laboratoire.

## Validation obligatoire avant production

- PostgreSQL réel + préflight ;
- sauvegarde préalable ;
- test HTTPS/Caddy ;
- 5 utilisateurs réels ;
- plusieurs semaines d'historique pour les baselines ;
- cycle Live réel Hermes.

Voir `docs/history/validation/NELYIO_FINALISATION_REPORT.md` et `docs/current/NELYIO_DATA_DICTIONARY.md`.
