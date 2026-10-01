# NELYIO V60.5-ARCH-RC3 — À lire avant validation

## Correctifs RC3 Appels suspects

- **Mise en attente** = hold pendant l'appel, pas `ODCalls.WaitDuration`.
- Source hold : `Stats.AGENT` + preuve `ODActions State=1003`, avec `SessionID = CallID`.
- `ODRelations` est importé et les reroutages/transferts/consultations sont exclus des heuristiques durée/hold/contenu faible.
- Sur l'export réel du 21/09/2026 : 413 appels bruts >=30 % de hold, dont 25 flux complexes exclus -> **388 suspects** ; 160 bruts >=50 %, dont 7 exclus -> **153 suspects**.
- Le critère **Contenu faible / size anormal** est visible mais désactivé tant qu'une source fiable de taille média reliée au CallID n'est pas disponible.
- Références utilisateur non ambiguës observées sur appels normaux sans hold : 388,59 KB / 49 s ≈ **7,93 KB/s** et 905,34 KB / 113 s ≈ **8,01 KB/s**. Elles ne définissent pas encore un seuil de production.

---

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

- 93/93 tests Python ;
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