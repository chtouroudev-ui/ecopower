# RC29.4 LIVE CENTER FIX5 — Validation

Date : 2026-09-30
Base : `Nelyio-ARCH V60.5 RC29.4 LIVE CENTER FIX4`

## Objectif

FIX5 complète le chantier Live sans modifier les formules KPI métier :

1. **Incidents / Stat Live** devient une interface d'analyse : historique des incidents Qualité Live sur 90 jours, filtre de période, tableau simple par agent et graphiques de distribution.
2. **Signalisation Qualité Live** reste la source de vérité pour les niveaux/couleurs appliqués au Centre Qualité Live. Les règles AGENT peuvent colorer directement la ligne ; la règle de rang le plus élevé gagne.
3. **Diagnostic Hermes** ajoute un scanner CDP passif réservé aux administrateurs, lancé sur demande ou via une planification explicitement activée.
4. **Ouverture + connexion Hermes automatique** utilise un coffre Windows DPAPI lié au compte Windows qui exécute Nelyio. Le secret n'est jamais renvoyé par l'API ni écrit dans les logs/rapports.
5. Le diagnostic expose la couverture `UpQuH` / `UpQuR` par file afin d'expliquer les écarts entre l'ancienne supervision Hermes et Nelyio avant toute modification de calcul.

## Incidents / Stat Live

L'interface dédiée ne sert plus de workflow opérationnel. Elle affiche :

- **Historique 90 jours** : date/heure, agent ou périmètre, type d'incident, détail de la condition, niveau/couleur, statut et durée ;
- filtre `Du / Au`, intervalle maximal 90 jours ;
- **Statistiques par agent** : total d'incidents et répartition par catégorie ;
- distribution par type d'incident ;
- distribution par jour ;
- incidents collectifs conservés séparément et jamais attribués artificiellement à un agent.

La capture Live opérationnelle reste limitée à la journée courante. Seuls les incidents Qualité Live clos/rétablis sont conservés 90 jours ; un incident encore actif n'est pas supprimé par la rétention.

## Signalisation liée au Centre Live

FIX4 reste inchangé sur le fond :

- couleurs configurées dans **Signalisation Qualité Live** ;
- plusieurs règles possibles pour construire une progression `Surveillance -> Dégradé -> Critique` ;
- Post-appel 10/15/25 s reste un fallback visuel si aucune règle Agent configurée ne prend la main ;
- presets disponibles pour Post-appel, pauses, déjeuner, Coaching, General Break, HOLD, HOLD précoce, déconnexion et contexte inactif ;
- filtre Agents `Mise en attente` conservé ;
- une règle Groupe/Campagne ne colore pas arbitrairement une ligne Agent.

## Auto-login Hermes sécurisé

### Stockage

- coffre : `data/secrets/hermes_credentials.dpapi` ;
- chiffrement : Windows DPAPI `CurrentUser` ;
- le fichier copié sur une autre machine ou sous un autre compte Windows n'est pas utilisable tel quel ;
- le mot de passe n'est jamais renvoyé à l'interface après enregistrement ;
- les audits enregistrent seulement l'action, jamais le secret.

### Exécution

Quand l'auto-login a été explicitement activé :

- Nelyio réutilise d'abord une session Supervision déjà authentifiée ;
- sinon il ouvre le profil Edge Nelyio local sur `127.0.0.1:9222` ;
- les champs de login sont manipulés par CDP `DOM` / `Input` ;
- aucune commande `Runtime.evaluate` n'est utilisée ;
- aucun processus Edge n'est tué ;
- après un échec, nouvelles tentatives suspendues 15 minutes pour limiter le risque de verrouillage du compte.

Le worker Live peut demander cette ouverture uniquement lorsqu'une session Live déjà active est en `waiting_browser` / `connecting`.

## Diagnostic Hermes administrateur

Le module **Diagnostic Hermes** est visible uniquement pour un administrateur.

### Manuel

Bouton `Analyser la supervision Hermes` avec durée 30 / 60 / 120 secondes.

Le scanner :

- observe passivement XHR / Fetch et WebSocket via CDP local ;
- n'active jamais automatiquement une nouvelle source ;
- retire les query strings des URL enregistrées ;
- analyse les corps réseau uniquement en mémoire pour extraire noms de callbacks et schéma ;
- ne persiste jamais corps HTTP/WebSocket bruts, headers, cookies, tokens ou identifiants ;
- classe les fonctions déjà connues et les candidates ;
- compare le catalogue de files du jour aux files disposant réellement de `UpQuH` et `UpQuR`.

### Planification optionnelle

OFF par défaut. L'admin choisit :

- jours ;
- heure ;
- durée ;
- `Ouvrir / auto-login Hermes si absent avant le scan`.

Une seule analyse peut être active. La planification ne transforme jamais une source candidate en source de production.

## Ecart Hermes / Nelyio observé sur la capture utilisateur

La capture fournie montrait :

| Indicateur | Hermes | Nelyio | Ecart Nelyio - Hermes |
| --- | ---: | ---: | ---: |
| Reçus | 7 815 | 7 533 | -282 |
| Traités | 7 052 | 6 799 | -253 |
| Abandonnés | 561 | 545 | -16 |
| Appels en cours | 49 | 44 | -5 |
| QoS | 92,63 % | 96,2 % | +3,57 pts |

Au même instant, Nelyio signalait `UpQuH : 80/137 file(s) · partiel`. Les deux interfaces ne prouvaient donc pas le même périmètre de files. FIX5 ajoute la liste exacte des files sans `UpQuH` / `UpQuR` afin de diagnostiquer cette différence avant de toucher à la formule QoS.

**Aucune formule QoS n'a été modifiée dans FIX5.**

## Validation automatisée

Gate complet sur une copie isolée :

- `335 passed` ;
- 21 fichiers JavaScript : `node --check` OK ;
- 185 fichiers Python de la release : syntaxe AST OK ;
- tests spécifiques FIX5 : coffre DPAPI, auto-login, routes admin/locales, cooldown, scanner passif, planification, couverture de files, historique/statistiques incidents ;
- régressions FIX1/FIX2/FIX3/FIX4 conservées.

## Limites de validation

L'environnement de génération n'est pas Windows et n'est pas connecté à la session Hermes de production. Les éléments suivants sont donc validés par tests unitaires/mocks et audit statique, mais doivent être confirmés sur le serveur :

- appel réel aux APIs Windows DPAPI ;
- saisie réelle du formulaire Hermes courant ;
- scan CDP réel pendant 30/60/120 s ;
- liste exacte des 57 files manquantes de la capture ;
- découverte éventuelle d'un endpoint/callback Hermes supplémentaire.

Le rapport du scanner est précisément prévu pour fournir cette preuve sur le serveur sans modifier le Live.

## Données

- aucune base métier n'est réinitialisée ;
- `data/` est protégé par le mécanisme de déploiement ;
- le patch cumulatif ne doit jamais remplacer les `.db` de l'installation en cours ;
- la capture Live reste journée courante ;
- l'historique d'incidents Qualité Live reste 90 jours.

## Build final livre

- runtime : `60.5-ARCH-RC29.4+LIVE-NATIVE-R11-FIX5-20260930` ;
- coffre Hermes non preconfigure dans le paquet ;
- planification Diagnostic Hermes OFF par defaut ;
- aucune base `.db` modifiee par la generation ;
- aucune formule KPI/QoS modifiee.

## Gate final de livraison

Validation rejouee sur une copie isolee du build final :

- `335 passed` avec `pytest -q` ;
- 21 fichiers JavaScript : `node --check` OK ;
- 185 fichiers Python : parsing AST OK ;
- manifeste production : **481/481 fichiers OK** ;
- simulation puis application `deploy_release.py` reussies depuis une RC29.4 originale et depuis LIVE_CENTER_FIX4 ;
- les 5 bases `.db` conservent exactement leur SHA-256 avant/apres les simulations de mise a jour ;
- aucun coffre Hermes, aucun mot de passe et aucun rapport de scan runtime n est livre preconfigure.
