# RC29.4 LIVE CENTER FIX3 — Persistance Live et reprise

Date de validation : 2026-09-30
Base : `Nelyio-ARCH_V60.5_RC29.4_LIVE_CENTER_FIX2`
Portée : Centre Qualité Live + persistance du spool Live de la journée. Aucun changement des formules KPI/QoS et aucun reset de base.

## Constat reproduit dans le code

`Nelyio_Live.db` est la base SQLite/WAL locale dédiée au Live. Pendant la journée elle contient notamment :

- `collection_sessions` : sessions de collecte ;
- `collection_responses` : métadonnées des réponses reçues (digest/horodatage/source), sans corps HTTP brut ;
- `collection_events` : événements Hermes normalisés ;
- `collection_catalog` : agents/files/campagnes observés ;
- `collection_call_details` : observations d'appels ;
- `live_quality_rule_state` et `live_quality_incidents` : état/alertes Qualité Live ;
- compteurs journaliers Hermes normalisés (`UpQuH`, `UpAgtH`) dans `collection_events`.

Le corps brut `changes.ashx`, les cookies, mots de passe, audio et corps HTTP complets ne sont volontairement jamais enregistrés.

Avant FIX3, `live_supervision_snapshot()` privilégiait la dernière session/connexion pour les états courants. Une nouvelle session le même jour pouvait donc masquer des faits toujours présents dans `Nelyio_Live.db`. Un arrêt technique `waiting_restart` fermait aussi les observations d'appels encore en cours.

## Correctifs FIX3

1. Le Centre Live reconstruit maintenant les états à partir de **toutes les sessions du jour**.
2. Un état provenant d'une ancienne session/source est conservé comme **Dernier état conservé**.
3. Un état conservé n'est **pas compté** dans Connectés / Disponibles / Déconnectés / En appel tant qu'Hermes ne l'a pas réobservé sur la connexion courante.
4. La connexion doit être réellement en état `receiving` pour qu'un état soit considéré courant ; `connecting`, `connected_waiting_data` et `waiting_browser` ne recyclent pas un ancien état en Live actuel.
5. Un appel encore observé lors d'un redémarrage technique passe en `capture_gap` : dernière preuve conservée, durée figée au dernier instant observé, aucune durée inventée pendant la coupure.
6. `UpQuH` reste journalier et est récupéré sur toutes les sessions de la journée.
7. `UpQuR` reste strictement temps réel : il expire après 30 s s'il n'est pas réobservé.
8. Le rail **Connectés** explique son total avec le détail `dispo · appel · pause · post · autre`.
9. Le rail affiche un indicateur **Données du jour enregistrées** avec nombre d'événements, sessions et états restaurés.

## Rétention

Le Live détaillé reste volontairement un **spool de la journée courante**. Au changement de jour, les sessions/événements opérationnels anciens sont purgés. Les observations d'appels finalisées non encore copiées sont protégées contre la purge ; elles sont copiées dans `live_call_observation_history` avant suppression quand le stockage historique est disponible. Les KPI historiques certifiés restent issus des imports SIMPLIFY2.

Important : `Nelyio_Live.db` se trouve dans le dossier de l'installation Nelyio. Démarrer une autre copie complète de Nelyio dans un autre dossier signifie utiliser une autre base Live. Pour une mise à jour de l'installation existante, utiliser le patch/déploiement qui préserve les `.db`, ne pas remplacer les bases avec celles d'un ZIP complet.

## Validation automatique

- Nouveau test FIX3 : **5/5 PASS**.
- Régressions Live ciblées : **54/54 PASS**.
- Suite complète : **310/310 PASS**.
- Syntaxe Python : OK.
- Syntaxe `static/live-views.js` : OK.
- Preflight release : intégrité **468/468** fichiers de production OK.
- Simulation patch cumulatif sur RC29.4 original : preflight OK.
- Bases `.db` avant/après simulation du patch : SHA-256 identiques.

## Données qui ne doivent pas être interprétées comme courantes après reprise

- Dernier état d'un agent non encore réobservé ;
- appel marqué `capture_gap` ;
- UpQuR plus ancien que 30 s.

Ces faits restent visibles comme contexte/persistance mais sont exclus des KPI Live courants jusqu'à nouvelle preuve Hermes.
