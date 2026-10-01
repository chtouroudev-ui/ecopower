# PHASE 4 — Rapport de validation RC15

## Base

- Source : V60.5-ARCH-RC14 Centre Qualité Live Phase 3
- Cible : V60.5-ARCH-RC15 Campagnes à surveiller Phase 4

## Régressions avant packaging final

- Suite Python complète : **124/124 réussis**.
- Tests Phase 4 dédiés : **7/7 réussis**.
- Syntaxe JavaScript : **19/19 fichiers valides**.
- Test frontend `audit_frontend_test.js` : **PASS**.
- Compilation Python `compileall` : **OK**.

## Tests Phase 4 ajoutés

1. campagne -> service/groupes correctement résolue et agent ACTIVE multi-files compté une seule fois ;
2. concentration de **72 %** sur une file exposée explicitement ;
3. `waiting_now` non certifié reste `null/unavailable`, jamais `0` ;
4. fenêtres 15 min / aujourd'hui / référence restent distinctes et la variation utilise la référence ;
5. statut campagne/file réutilise la signalisation Qualité Live explicable ;
6. historique indisponible ne fabrique aucun zéro ;
7. panne Analytics/PostgreSQL : `/api/live/campaigns` conserve le Live et marque l'historique `analytics_unavailable` au lieu de produire un HTTP 500 global.

## Benchmark historique synthétique

Scénario isolé, sans données de production :

- 12 000 appels par jour ;
- 5 jours de contexte (jour cible + quatre références) ;
- 30 campagnes ;
- 60 000 faits Stats.INBOUND synthétiques ;
- 12 000 appels ODCalls sur le jour cible ;
- 7 exécutions mesurées.

Résultats indicatifs :

- médiane : **~0,35 s** ;
- P95 : **~0,37 s** ;
- 30 campagnes retournées ;
- plan déclaré borné ;
- aucun SELECT exécuté dans une boucle par campagne/file/agent.

Le nombre total de SELECT observé dans ce laboratoire inclut configuration/gouvernance et références, mais reste indépendant du nombre de campagnes. La production PostgreSQL délègue ce calcul au worker Analytics et le met en cache.

## Contrat de données vérifié

- `live_now` : Hermes Live / état central ;
- `last_15m` : Stats.INBOUND importé ;
- `today` : Stats.INBOUND importé ;
- `reference` : jours comparables Stats.INBOUND ;
- concentration : ODCalls.FirstQueue ;
- Groupes : files configurées + agents ACTIVE ;
- Campagnes : dimension d'activité distincte ;
- QoS historique : source Stats.INBOUND existante ;
- attente/QoS réellement Live : non certifiées et donc non inventées.

## Dégradation maîtrisée

La vue campagne ne dépend pas de la disponibilité simultanée de toutes les sources :

- si Hermes Live est disponible mais Analytics est KO, l'utilisateur conserve Maintenant ;
- les fenêtres historiques sont marquées indisponibles ;
- si la donnée Live est périmée, la qualité Live existante conserve les garde-fous RC14 ;
- aucune absence de source n'est convertie silencieusement en `0` ou `NORMAL`.

## Validation restant obligatoire en production

- PostgreSQL réel avec volume de production ;
- worker Analytics 9052 réel ;
- worker Live/Hermes réel ;
- cohérence des campagnes Hermes avec Stats.INBOUND sur plusieurs journées ;
- vérification FirstQueue sur appels transférés/consultés ;
- 5 utilisateurs simultanés ;
- temps API `/api/live/campaigns` réel ;
- contrôle visuel 1440 px et mobile <=390 px ;
- certification séparée des compteurs Hermes d'attente avant toute activation de waiting/P90 Live.

## Packaging final

La release RC15 a été reconstruite depuis une extraction propre de RC14 puis a reçu uniquement les fichiers Phase 4 validés. Les bases/logs éventuellement touchés pendant le développement n'ont donc pas été repris depuis le worktree.

Validation sur cette release propre :

- suite Python : **124/124 réussis** ;
- JavaScript : **19/19 syntaxiquement valides** ;
- audit frontend : **PASS** ;
- `preflight.py` : intégrité code **OK**, syntaxe Python **OK**, quick-check des bases SQLite **OK** ;
- avertissement conservé sur `requests 2.32.5` (<2.33.0), sans appel direct détecté à la fonction concernée ;
- simulation `deploy_release.py` vers une extraction RC14 : **succès**, 284 fichiers code-only, données/configuration/certificats/logs protégés.

La recette réelle Windows/HTTPS/Hermes/PostgreSQL reste volontairement manuelle.
