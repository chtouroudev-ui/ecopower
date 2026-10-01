NELYIO V60.4 - PATCH V4 DIAGNOSTIC : COUPURES PENDANT APPEL

Cause corrigee
---------------
Les exports SIMPLIFY2 recents utilisent notamment les ActionName anglais :
- Inbound call
- Manual call
- Outbound call
- Dialing
- Consultation

V60.4 classait ces etats en "other". Diagnostic Nelyio cherchait uniquement
les activites kind='call', ce qui pouvait afficher 0 coupure pendant appel.

Corrections
-----------
1. supervision_utils.py reconnait les etats d'appel anglais.
2. supervision_db.py repare automatiquement les lignes DEJA IMPORTEES au
   prochain demarrage. Il n'est pas necessaire de reimporter les exports.
3. Ringing reste exclu : une sonnerie ne prouve pas qu'une conversation a commence.
4. supervision_utils.py conserve aussi la correction V3 du catalogue agents/groupes.

Validation sur SIMPLIFY2.2026-09-24.export.zip
---------------------------------------------
Apres correction, 8 748 activites sont classees comme call dans Stats.AGENT.
La correction n'assimile pas les 515 lignes Ringing a des appels etablis.

Installation
------------
Extraire ce patch dans le dossier Nelyio contenant app.py puis lancer :
INSTALL_PATCH.bat

Chemin utilisateur connu :
C:\Users\AD#\Desktop\Nelyio stock manager\NELYIO_V60_4_Demo\NELYIO_V60_4_PROD_FINAL

Redemarrer completement Nelyio apres installation puis Ctrl+F5.
