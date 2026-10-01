# RC29.1 — Correctif QoS + poste de supervision

## Règle QoS canonique

La seule formule QoS exposée par Nelyio est désormais :

**QoS = Appels traités / (Appels reçus - Appels clôturés - Raccrochés avant file d'attente) × 100**

- Numérateur : appels traités avec AgentId affecté.
- Dénominateur : reçus - clôturés - raccrochés avant file d'attente.
- Si le dénominateur est inférieur ou égal à 0 : valeur non calculable (`—`), jamais 0 inventé.
- Les anciens champs `reference_qos_*` restent uniquement comme alias de compatibilité et retournent la même QoS ; aucune deuxième formule n'est affichée.

Chemins alignés : `quality_rules.py`, `quality_metrics.py`, `quality_distributions.py`, `live_scope_quality.py`, Pilotage via les agrégats canoniques, Centre Live historique, Qualité de service et Distributions.

## Centre Qualité Live — poste de supervision

Sur desktop (>= 1100 px), la première interface devient un poste de supervision à hauteur de fenêtre :

- Agents à gauche.
- Campagnes/Périmètres à droite ; l'onglet Campagnes reste sélectionné par défaut.
- En-têtes de tableaux fixes.
- Défilement indépendant à l'intérieur des deux listes : plus besoin de faire défiler toute la page pour passer des agents aux campagnes.
- Bandeau état/KPI fortement compacté.
- Qualité maintenant, qualité certifiée, alertes et limites deviennent des panneaux repliables qui s'ouvrent en surimpression.
- Tablette/mobile : conservation du rendu empilé responsive.

Aucun calcul d'appartenance aux groupes, aucune règle Live et aucune base métier n'ont été modifiés par la refonte UI.

## Validation

- Tests RC29 phases 1 à 6 exécutés : OK sur les suites autonomes disponibles.
- Test spécifique RC29.1 QoS/UI : 3/3 OK.
- `audit_regression_test.py` : OK.
- Python racine : 143 fichiers analysés par AST, 0 erreur.
- JavaScript `static/*.js` : `node --check` OK.
- Bases, WAL/SHM et logs comparés à `Nelyio-ARCH_V60.5_RC29_FINAL.zip` : 0 modification.
- Le test de référence `quality_reference_20260901_test.py` exige l'export ZIP du 01/09/2026 et n'a pas été rejoué sans ce fichier ; ses attentes embarquées ont été réalignées sur la formule canonique.

## Limite de validation

L'ergonomie desktop a été validée statiquement (structure DOM/CSS et syntaxe), mais pas avec votre écran réel, vos 114 agents et votre navigateur de production. Une recette visuelle sur le serveur cible reste nécessaire pour ajuster éventuellement la densité à la résolution exacte des écrans de supervision.
