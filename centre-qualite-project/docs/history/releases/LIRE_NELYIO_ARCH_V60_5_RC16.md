# Nelyio-ARCH V60.5 RC16 - Phase 5 Live Drilldown

Base: RC15 Live Campaigns Phase 4.

## Fait
- Drilldown borne campagne -> file -> agent -> appel -> timeline/diagnostic.
- Une seule reponse backend pour le detail campagne; les filtres file/agent sont ensuite appliques cote navigateur.
- Contexte agent historique Stats.AGENT charge en batch.
- Appels Live recents issus uniquement du spool Live observe.
- ANI masque selon permission.
- Deep-link vers Appels suspects avec campagne/file/agent.
- Tous les libelles visibles wrap-up/wrap/Post-travail du Live sont standardises en **Post-appel**. Les cles internes wrap/wrap_up ne changent pas.

## Regles de fiabilite
- Une metrique historique absente reste `non disponible`; elle ne devient jamais 0.
- Un agent ACTIVE sans etat Hermes courant est `Non observe`, pas `Deconnecte`.
- La timeline n invente aucun evenement absent.
- Campagne reste distincte de Groupe.

## Performance
- Pas de SELECT dans une boucle par file ou par agent.
- Preview appels Live bornee.
- Benchmark synthetique de composition (114 agents, 20 files, 100 appels): mediane ~0.97 ms, P95 ~1.09 ms.
- Ce benchmark ne remplace pas la recette Windows/Hermes/PostgreSQL reelle.

## Validation
- 129/129 tests Python.
- 19/19 fichiers JavaScript: syntaxe OK.
- Audit frontend de concurrence: PASS.
- compileall: OK.

## Point d arret sur
RC16 est un point de reprise code-only. La prochaine phase est le cycle de vie Alertes/Incidents/Actions, sans modifier les sources historiques certifiees.
