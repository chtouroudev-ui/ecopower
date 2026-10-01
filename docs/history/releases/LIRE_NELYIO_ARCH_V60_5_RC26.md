# Nelyio-ARCH V60.5 RC26 — Phase 15 · Live opérationnel enrichi

## Objectif

Rendre la partie LIVE réellement exploitable par les superviseurs sans inventer de métriques Hermes.

## Centre Qualité Live

Pour chaque agent observé, RC26 affiche :

- état actuel et durée de l’état ;
- appels Live observés sur 15 minutes, 60 minutes et aujourd’hui ;
- temps observé en appel, HOLD explicite, disponible, post-appel, pause et déconnecté ;
- couverture totale observée ;
- **Temps non disponible observé** = Pause + Déconnecté + autres états indisponibles ;
- file / campagne courante ;
- appel actuel ;
- durée de mise en attente pendant l’appel uniquement si un état explicite `Mise en attente`, `On Hold` ou `HOLD` est réellement reçu.

Disponible et Post-appel ne sont pas classés comme temps perdu.

## Campagnes Live

Le tableau et le drill-down campagne ajoutent :

- appels Live observés sur 15 min ;
- appels Live observés sur 60 min ;
- appels Live observés aujourd’hui ;
- nombre d’agents actuellement en mise en attente explicite ;
- par agent : appels Live, temps non disponible, appel actuel et HOLD observé.

Les KPI historiques certifiés restent séparés :

- Stats.INBOUND pour les KPI de service ;
- Stats.AGENT pour le contexte agent / HOLD historique importé.

## Mise en attente : règle de preuve

RC26 distingue strictement :

- `Waiting` / `Disponible` : disponibilité de l’agent ;
- `Mise en attente` / `On Hold` / `HOLD` : mise en attente explicite pendant l’appel.

Le parser garde désormais le segment d’appel actif pendant un état HOLD explicite.

Si aucun libellé HOLD explicite n’est présent dans la timeline, Nelyio affiche **Non certifiée**. Il ne conclut pas à `0 seconde`.

Les compteurs Hermes `arg_n` restent non mappés tant que leur sémantique n’est pas certifiée. Les métriques suivantes restent donc indisponibles en Live si aucune autre source certifiée n’existe : attente en file, P90 attente, QoS Live, abandon Live et attente patient individuelle.

## Compatibilité

Phase 15 ne change pas les bases métier, les règles QoS historiques, les droits RC23-RC25 ni la configuration Caddy. L’upgrade est code-only.
