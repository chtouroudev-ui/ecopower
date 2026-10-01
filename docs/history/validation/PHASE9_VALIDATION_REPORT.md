# PHASE 9 — Validation RC20

## Fait

- Nouvelle interface **Administration → Santé de production**.
- Nouveau endpoint read-only `/api/production/observability`, droit `config` lecture requis.
- Agrégation Services / PostgreSQL / Live / sessions / import / recette / lenteurs.
- Confidentialité stricte : aucun identifiant métier, aucune query string, aucun secret.
- Cache backend partagé 5 s et rafraîchissement frontend unique 10 s.
- Lecture des heartbeats et de l'import sans création de ressources manquantes.

## Vérifié dans la branche Phase 9

- 150/150 tests Python PASS.
- 6/6 tests spécifiques Phase 9 PASS.
- 21/21 JavaScript syntax PASS.
- `compileall` PASS.
- Preflight RC20 PASS.
- Dry-run RC19 → RC20 PASS.
- Upgrade appliqué sur copie RC19 PASS ; 5 bases SQLite + Caddyfile inchangés bit-à-bit.

## Risques maîtrisés

- Un Live inactif n'est pas assimilé à une panne ; seul un Live actif mais périmé déclenche une surveillance.
- Le probe PostgreSQL est partagé entre onglets administrateur via cache serveur afin d'éviter un effet multiplicateur.
- Les logs lents sont bornés à une lecture de queue de fichier et agrégés avant exposition.

## Restant avant production réelle

- Exécuter `RECETTE_PRODUCTION.bat` sur Windows avec PostgreSQL/Hermes réels.
- Vérifier HTTPS depuis un autre poste du LAN.
- Utiliser Santé de production pendant la recette multi-utilisateurs pour corréler lenteurs et heartbeats.
