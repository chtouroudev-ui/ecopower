# RC29.4 LIVE CENTER FIX4 — Signalisation configurable et historique 90 jours

## Objectif
Unifier la Signalisation Qualité Live et le rendu du Centre Qualité Live : les seuils/niveaux/couleurs configurés dans Signalisation Qualité Live pilotent la signalisation visuelle des lignes Agents.

## Ajouts
- Presets AGENT configurables : Post-appel 10/15/>25 s, pause normale, pause déjeuner >1 h, Coaching, General Break, HOLD long, déconnexion >10 min, contexte inactif, HOLD précoce.
- HOLD précoce : métrique `earliest_hold_start_seconds`. Elle reste indisponible si le début réel de l'appel n'est pas connu (`partial_start`) ou si aucune mise en attente explicite n'a été observée.
- Une alerte active de périmètre AGENT colore la ligne de l'agent avec la couleur du niveau configuré. Si plusieurs alertes AGENT sont actives, le rang le plus élevé gagne.
- Les alertes Groupe/Campagne ne colorent pas arbitrairement une ligne Agent.
- Le signal Post-appel 10/15/25 s reste un fallback lorsque aucune règle AGENT configurée n'est active.
- Historique : incidents rétablis/clôturés + journal conservés 90 jours dans `Nelyio_Live.db`; incidents actifs jamais purgés par la rétention. La lecture de l'historique est non destructive; la purge est faite par le worker Qualité Live.
- Vue Agents : filtre rapide `Mise en attente`. Le filtre `En appel` continue d'inclure appel + HOLD.

## Invariants
- Aucun KPI/QoS métier modifié.
- Inconnu ≠ zéro.
- HOLD exige un état explicite réellement observé.
- Aucun contenu HTTP brut/cookie/token/audio ajouté au stockage.
- Pas de reset de base.

## Validation
- Tests FIX4 spécifiques : 6/6 PASS.
- Régressions Live ciblées : 46/46 PASS.
- Suite complète : 316/316 PASS.
- Syntaxe Python/JavaScript : OK.
- Preflight : intégrité production OK (468 fichiers), SQLite quick_check OK.

## Recette serveur recommandée
1. Configurer des niveaux/couleurs dans Signalisation Qualité Live.
2. Créer une ou plusieurs règles AGENT depuis les presets et ajuster les seuils.
3. Vérifier qu'une règle déclenchée colore la ligne Agent avec le niveau choisi.
4. Tester Post-appel 10/15/>25 s, Pause déjeuner >1h, Déconnexion >10 min et Contexte inactif.
5. Provoquer une mise en attente avant 10 s sur un appel dont le début est observé et confirmer le signal dédié.
6. Vérifier le filtre `Mise en attente` dans la vue Agents.
7. Vérifier l'onglet Historique : mention 90 jours, chronologie et résolution conservées après redémarrage.
