NELYIO V60.4 - PATCH V5 CAMPAGNES DANS GROUPES

Ce patch corrige l'affichage et l'import des campagnes dans Administration > Groupes.

1. La relation automatique reste : Groupe -> Files -> Campagnes observees sur ces files.
2. ODCalls n'a plus besoin de la colonne InitPriority pour fournir FirstQueue -> FirstCampaign.
3. Les campagnes automatiques restent visibles dans l'onglet Campagnes meme lorsque tu cliques Modifier.
4. Elles sont affichees en lecture seule avec la/les file(s) d'origine et ne sont pas enregistrees comme liens manuels.

Installation :
- extraire le patch dans le dossier Nelyio contenant app.py ;
- lancer INSTALL_PATCH.bat ;
- redemarrer Nelyio ;
- Ctrl+F5 dans le navigateur ;
- reimporter le ZIP SIMPLIFY2 du jour (ou ODCalls.csv) afin de recalculer File -> Campagne.

Le patch est compatible avec les correctifs V3/V4 et ne remplace pas supervision_utils.py / supervision_db.py.
