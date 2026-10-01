NELYIO V60.4 - PATCH V3 REEL : GROUPES + IMPORT MULTIPLE + RECHERCHE D'APPELS

Pourquoi V2 ne se voyait pas
-----------------------------
V60.4 n'utilise plus l'ancien import Web comme interface principale.
L'outil reel est :
  OPEN_NELYIO_IMPORTER.bat -> nelyio_importer_app.py
V2 modifiait surtout static/supervision.js, donc le changement n'etait pas visible dans l'importer V60.

Chemin projet
-------------
C:\Users\AD#\Desktop\Nelyio stock manager\NELYIO_V60_4_Demo\NELYIO_V60_4_PROD_FINAL

Installation
------------
1. Extraire ce ZIP directement dans le dossier ci-dessus.
2. Lancer INSTALL_PATCH.bat.
3. Verifier le message "PATCH V3 APPLIQUE AVEC SUCCES".
4. Redemarrer Nelyio.
5. Lancer OPEN_NELYIO_IMPORTER.bat.

Verification visuelle
---------------------
Le nouvel importer doit afficher :
- "Import multiple separe du Web"
- bouton "Importer la selection"
- Parcourir permet de selectionner plusieurs ZIP / CSV / HAR

Correction groupes
------------------
Le probleme V60.4 a deux causes :
1. le snapshot Agents.csv -> Queues peut etre absent ;
2. reimporter le meme ZIP est traite comme doublon et pouvait ne pas rejouer quality_import.

V3 rejoue explicitement l'extraction Agents.csv -> Queues apres chaque ZIP, meme si le ZIP est deja connu.
Il accepte aussi directement Agents.csv et les CSV de configuration.
Le cache Groupe -> Files -> Agents ACTIVE est invalide immediatement apres l'import.

Import multiple
---------------
Plusieurs fichiers peuvent etre selectionnes en une fois.
Ils sont traites sequentiellement dans un worker unique : c'est volontaire, car le pipeline Nelyio utilise un verrou d'ecriture global. Cela donne un vrai import de masse sans lancer plusieurs ecritures concurrentes dangereuses.
Un echec n'arrete pas les fichiers suivants.

Fichiers modifies
-----------------
- nelyio_importer_app.py
- supervision_utils.py
- quality_service.py
- calls.py
- static\support.js
