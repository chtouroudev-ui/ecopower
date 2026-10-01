# Nelyio RC2L — correctifs et mise en service

Version préparée le 23 septembre 2026 à partir de Stock_manager_Project.7z.
**Candidat corrigé, à valider sur Windows/PostgreSQL avant production.**

## Installer sur ton installation existante

1. Conserver l'archive d'origine. Sauvegarder la base PostgreSQL avec `SAUVEGARDER_POSTGRESQL.bat` et vérifier que la commande a réussi. La sauvegarde du dossier seule ne sauvegarde pas PostgreSQL.
2. Extraire ce paquet dans un NOUVEAU dossier, séparé de l'installation utilisée. Ne pas lancer une seconde copie de l'application sur la même base.
3. Suspendre les tâches de redémarrage automatique et la capture Hermes pendant la mise à jour. Dans l'ancienne installation, lancer `STOP_NELYIO_HTTPS.bat` : l'ancien `STOP_NELYIO_ALL.bat` ne stoppait pas les workers. Vérifier l'arrêt Import, Live, Analytics et backend.
4. Depuis le NOUVEAU paquet, lancer `MISE_A_JOUR_PRODUCTION.bat`, sélectionner le dossier de l'installation existante et examiner la simulation. Le programme vérifie les empreintes, sauvegarde le dossier cible et ne copie que le code autorisé. Il préserve data/, les bases, les comptes, le Caddyfile et les certificats. Il refuse une version locale modifiée non reconnue : ne pas contourner ce contrôle.
5. Dans l'installation mise à jour, lancer `VALIDATION_PRODUCTION.bat` puis `START_NELYIO_HTTPS_DEBUG.bat` pour le premier démarrage. La validation PostgreSQL peut compléter les objets de schéma manquants; elle ne réinitialise pas les données.
6. Lancer `VALIDER_APRES_DEMARRAGE.bat`. Le build affiché doit être **56.18-MS1-RC2L** et les quatre services doivent être sains. URL habituelle : https://stock-manager.nelyio.local:9050/ ; test local : http://127.0.0.1:9051/.
7. Après recette, réactiver les tâches automatiques. Pour les démarrages habituels, utiliser `START_NELYIO_HTTPS.bat` ou le lanceur silencieux existant.

Le nouveau STOP_NELYIO_ALL.bat arrête désormais aussi les trois workers.
Aucun identifiant administrateur ni mot de passe n'a été créé ou modifié.
Les fichiers de données/configuration inclus sont ceux de l'archive d'origine; ils ne remplacent pas la base PostgreSQL de ton serveur.

## Défauts identifiés et corrections

| Point | Constat | Correction |
|---|---|---|
| Verrou Windows | `os.kill(pid, 0)` utilisé pour vérifier un PID; sous Windows il peut terminer le processus. | Interrogation Windows par handle, sans signal. Un accès refusé ne fait pas supprimer le verrou. |
| Démarrage HTTPS | Journaux : backend devenu indisponible, réponses 502, échecs de validation du lancement. | Correction du contrôle PID; son lien avec chaque arrêt historique ne peut pas être établi à partir des journaux seuls. Sonde HTTP sans proxy; lancement des workers dans un processus enfant borné. |
| Contrôle de santé | Écritures/lectures SQLite de heartbeats dans chaque requête /healthz, avec attente possible. | Heartbeat de fond, réponse HTTP en mémoire; un état vieux de plus de 12 s est déclaré non sain. |
| Arrêt global | STOP ALL ne stoppait que Caddy et le backend. | Arrêt des workers Import, Live et Analytics également. |
| Filtres | Construction complète des appartenances pour chaque ligne. | Index réutilisé jusqu'au changement du scope; résolution unique pour un tableau. |
| Repli erroné | En cas d'erreur du résolveur, un tableau pouvait utiliser le groupe administratif. | L'erreur remonte; aucun résultat analytique fabriqué à partir du groupe administratif. |
| Détails | Synchronisation SQL ligne par ligne; concurrence possible entre processus. | Lots de 500 événements, executemany sans recherche de lastrowid inutile; verrou transactionnel PostgreSQL pour sérialiser les synchronisations. |
| Erreur SQL | Une erreur de synchronisation était masquée par la mise à jour du journal dans une transaction déjà en échec. | Rollback, journal d'échec séparé, puis propagation de l'erreur initiale. Aucune écriture partielle de la synchronisation conservée. |
| Attentes SQL | Connexion/attente de verrou runtime non bornées explicitement. | Connexion 5 s et attente de verrou 5 s; les imports longs ne reçoivent pas de limite générale de durée de requête. |

Le journal fourni montre une synchronisation échouée après **661,39 s**. Il ne donne pas la cause SQL initiale, masquée par le gestionnaire d'erreur. La correction permettra de la conserver si elle se reproduit. Je ne peux pas affirmer que toute erreur SQL de tes données réelles a été éliminée.

Référence du comportement Windows : https://docs.python.org/3/library/os.html#os.kill

## Filtres et chiffres

La logique déjà présente est conservée : **groupe → files configurées → agents affectés ACTIVE uniquement**. Un agent peut appartenir à plusieurs groupes; inactive/partial/unknown ne lui donnent pas d'appartenance. Les identifiants 1001/S1001 sont normalisés.

Pour les appels sans agent, le rattachement passe par les campagnes liées aux files. Stats.INBOUND ne fournit pas directement l'identifiant de file : les groupes qui partagent des agents ou campagnes ne sont donc pas additionnables. Il s'agit d'un périmètre des membres actuellement actifs, pas d'une reconstitution de l'affectation historique de chaque appel à une file.

La formule QoS de cette archive n'a pas été changée : (traités par agent + reroutés sans agent) / (reçus − clôturés − raccrochés avant file). Ce correctif ne constitue pas une validation métier de cette formule par Vocalcom. La règle de dates/dimanches existante n'a pas été modifiée.

## Vérifications réalisées

- **49 tests Python réussis**, dont 12 nouveaux : PID/verrous, index des groupes et invalidation, absence de repli administratif, idempotence des insertions Détails, rollback et conservation de l'erreur, santé HTTP indépendante du disque, expiration des heartbeats, filtres croisés et HTTP concurrent.
- **1 test JavaScript réussi** : changement de filtre pendant une requête; ancien résultat ignoré et dernier filtre relancé.
- 25 réponses /healthz correctes avec **5 clients concurrents**. Ce test ne mesure pas cinq analyses lourdes simultanées.
- Démarrage réel du backend dans une copie temporaire, schémas SQLite vides : **0,408 s**; HTML et JavaScript servis correctement. Ce temps ne prédit pas le démarrage Windows/PostgreSQL.
- Intégrité des fichiers et syntaxe Python : OK; quick_check des quatre bases SQLite de l'archive : OK.
- Microbenchmark : 10 000 contrôles d'appartenance, 10 groupes, 114 identifiants, scope en mémoire : **2,8357 s avant / 0,0534 s après**, 5 280 correspondances dans les deux cas (environ 53× sur cette opération). Pas un facteur d'accélération global de l'application.

Tests effectués sur Linux / Python 3.12.14 avec dépendances disponibles (requests 2.34.2). Le fichier requirements.txt du projet conserve ses versions initiales. Les API Windows ont une branche vérifiée par simulation; leur exécution native, PowerShell 5.1, Caddy Windows, PostgreSQL réel, import volumineux et connexion Hermes restent à valider sur le serveur. Aucun serveur PostgreSQL de production n'a été contacté.

Pour rejouer les tests dans une COPIE DE TEST après installation de pytest :

    python -m pytest audit_regression_test.py quality_rc2i_test.py group_filter_global_test.py production_stability_test.py -q
    node audit_frontend_test.js

## Recette avant présentation

- Ouvrir l'application, se connecter, puis vérifier Parc, Diagnostic, Détails, Qualité agents, Qualité de service et Distributions.
- Choisir une journée disposant d'un export SIMPLIFY2 et deux groupes aux membres différents. Vérifier les files configurées et les affectations ACTIVE avant d'interpréter un zéro.
- Comparer groupe seul, groupe + agent, groupe + campagne, puis 09:00–10:00. Les totaux reçus/traités de Qualité et Distributions doivent correspondre pour un même périmètre.
- Tester un agent multi-groupes, un groupe vide, la réinitialisation des filtres et plusieurs changements rapides. Un groupe vide doit rester vide; il ne doit pas revenir implicitement à « tous ».
- Importer un export représentatif. Contrôler le statut completed, la disponibilité des Détails et l'absence de nouveau RUNNING abandonné/ERROR dans la synchronisation.
- Ouvrir cinq sessions et répéter les mêmes filtres, puis des filtres différents, pendant un import. Relever les temps dans logs/http_slow.log, la durée d'import, les erreurs SQL et les heartbeats. Ce test sur les volumes réels conditionne le feu vert production.

Si la recette échoue : arrêter la nouvelle pile, conserver les journaux, restaurer le dossier depuis NELYIO_BACKUPS si nécessaire. Ne restaurer PostgreSQL que depuis une sauvegarde vérifiée et en tenant compte des nouvelles écritures depuis la mise à jour. Ne pas faire tourner simultanément ancien et nouveau code sur la même base.
