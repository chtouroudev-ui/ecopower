# RC29.4 Live Center Fix 1 — Validation

Date : 2026-09-30
Base : Nelyio-ARCH V60.5 RC29.4 · Live Native R10
Portée : Centre Qualité Live uniquement ; aucune réinitialisation de base, aucune modification de formule métier QoS.

## Demande traitée

Le rail gauche est simplifié et affiche désormais les informations opérationnelles demandées : Connectés, Disponibles, Déconnectés, En appel, Reçus, Traités, Abandonnés et QoS. Le bouton/tiroir « Détails » est supprimé. Le filtre rapide « Déconnectés » est ajouté aux filtres agents existants.

La vue Campagnes / périmètres est corrigée afin d'afficher Reçus, Traités, Abandonnés et QoS lorsque Hermes fournit réellement UpQuH. Les vues Groupe et Service agrègent les files exactes configurées. Les compteurs inconnus ne deviennent jamais zéro.

## Cause racine des tirets dans Campagnes

`build_scopes()` calculait déjà `native_calls` depuis les compteurs Hermes UpQuH/UpQuR. Cependant `quality_center()` reconstruisait son payload de périmètres sans recopier `native_calls` ni `line_ids`. Les compteurs existaient donc côté backend mais étaient supprimés avant l'envoi au navigateur. C'est la raison pour laquelle le pied de page pouvait afficher « stats jour UpQuH : 83 » tandis que chaque campagne affichait « — ».

Le correctif propage maintenant `native_calls` jusqu'au payload final et agrège les files exactes pour GLOBAL / SERVICE / GROUP / QUEUE / CAMPAIGN. Aucune correspondance approximative n'est ajoutée.

## Règles de fiabilité

- UpQuH complet sur toutes les files d'un périmètre : KPI journalier affiché avec couverture complète.
- UpQuH partiel : les valeurs réellement reçues peuvent être présentées avec l'indication explicite « partiel » et le ratio de couverture.
- Aucun UpQuH : valeur « — » ; aucun zéro n'est inventé.
- QoS reste calculée selon la formule canonique existante et reste « — » si son dénominateur n'est pas exploitable.
- « Non observé » reste distinct de « Déconnecté » ; un agent absent des faits Live n'est pas artificiellement transformé en offline.

## Validation rejouable

- Suite complète : **301 tests passés**.
- Syntaxe JavaScript : `node --check static/live-views.js` OK.
- Syntaxe Python des fichiers modifiés : OK.
- Preflight release : intégrité du code OK ; SQLite quick_check OK ; Caddyfile présent.
- Scénario contrôlé : les métriques UpQuH traversent correctement `build_scopes()` puis `quality_center()` pour Campagne, Groupe et périmètre global.

## Fichiers fonctionnels principaux modifiés

- `live_quality.py`
- `collection_store.py`
- `access_control.py`
- `static/live-views.js`
- `static/collection.css`
- `index.html` (cache-busting CSS/JS)

Les tests de contrat UI concernés et le manifeste de production ont été alignés avec le nouveau comportement demandé.

## Simulation du patch léger

Le patch a été appliqué sur une copie intacte de RC29.4 : 11 fichiers remplacés, preflight d'intégrité OK et validation JavaScript OK. Les empreintes SHA-256 de `TECHIN_Stock_Manager.db`, `NELYIO_Supervision.db`, `Nelyio_Details.db` et `Nelyio_Live.db` sont restées strictement identiques avant/après le patch.
