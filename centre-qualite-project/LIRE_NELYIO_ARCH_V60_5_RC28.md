# Nelyio V60.5 RC28 — Centre Qualité Live complet

## Objectif

RC28 améliore uniquement la supervision opérationnelle Live au-dessus de RC27. Les règles d'accès, les KPI historiques et les bases existantes sont conservés.

## Ce qui change

- **Qualité maintenant** et **Périmètres Qualité Live** sont placés en haut du Centre.
- Le catalogue des **groupes/files configurés** devient la référence de couverture du Centre.
- Toutes les campagnes configurées du périmètre sont visibles, y compris sans activité courante.
- Tous les agents avec affectation **ACTIVE** aux files du périmètre sont référencés.
- Un agent configuré sans état Hermes courant est affiché **Non observé** ; il n'est pas assimilé à Déconnecté.
- Le bloc final s'appelle **États Live des agents**.
- Les cartes Live non certifiées (attente instantanée, P90 Live, abandon Live, QoS Live) ne sont plus affichées comme `Non disponible`.
- Les métriques d'attente certifiées disponibles sont affichées séparément depuis `Stats.INBOUND` dans **Attente & qualité certifiées · aujourd'hui**.
- La **mise en attente / HOLD** explicite reste disponible uniquement au niveau agent/appel lorsqu'elle est effectivement observée.
- La vue campagnes demande également les campagnes configurées inactives (`include_inactive=1`).

## Principe de fiabilité

RC28 ne transforme toujours pas un compteur Hermes non documenté en attente patient. Une donnée absente n'est pas remplacée par zéro. Les valeurs Live, les références de configuration et les métriques historiques certifiées restent identifiées séparément.

## Filtre Groupe

Le filtre **Groupe surveillé** reste appliqué côté serveur. Avec `Tous les groupes`, le superviseur voit toute la couverture autorisée. Avec un groupe précis, campagnes, files, agents et métriques sont restreints à ce groupe.

## Mise à niveau

Utiliser `deploy_release.py` ou installer la version complète dans un nouveau dossier. Les bases SQLite, `Caddyfile`, certificats et journaux ne sont pas remplacés par l'upgrade code-only.
