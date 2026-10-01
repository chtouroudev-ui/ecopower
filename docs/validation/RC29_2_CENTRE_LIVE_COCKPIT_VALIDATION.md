# RC29.2 — Centre Qualité Live cockpit

## Objectif
Réduire l'encombrement visuel du Centre Qualité Live et privilégier la supervision immédiate sur écran desktop.

## Changements UI
- Une seule barre de commande compacte : état Live, groupe, disposition et raccourcis.
- Une seule bande KPI compacte avant les listes.
- Trois dispositions persistantes dans la session : **Agents**, **Double vue**, **Campagnes**.
- En mode Agents ou Campagnes, le panneau opposé est masqué afin d'utiliser toute la largeur disponible sans changer de route.
- En double vue, Agents et Campagnes/Périmètres restent côte à côte avec scroll interne indépendant.
- Densité des lignes renforcée, en-têtes sticky, descriptions secondaires réduites.
- Qualité détaillée, historique certifié, alertes et limites restent accessibles dans les tiroirs secondaires.
- Le responsive tablette/mobile reste empilé.

## Non modifié
- Formule QoS RC29.1 : `Traités / (Reçus - Clôturés - Raccrochés avant file d'attente) * 100`.
- Calculs KPI, groupes, affectations ACTIVE, signalisation, historique et bases de données.
- Endpoints Live et cadence de polling.

## Validation
- `node --check` : tous les scripts JavaScript OK.
- Tests ciblés Live/campagnes/tri/identités/distributions exécutés sans échec.
- Aucun changement de schéma ou de base de données requis.
