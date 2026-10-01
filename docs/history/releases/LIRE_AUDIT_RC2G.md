# Nelyio RC2G — diagnostic, corrections et mesures

**22 septembre 2026 — base examinée : archive RC2F fournie.**

## Conclusion

Le diagnostic a mis en évidence des défauts réels de compatibilité PostgreSQL, des contrôles qualité trop permissifs et des requêtes répétées inutiles. Cette version les corrige et fournit des tests reproductibles.

**Les chiffres de votre production ne sont pas certifiés.** Les quatre bases jointes ne contiennent aucun historique métier : zéro activité, appel, événement live et fait Qualité. Les validations effectuées reposent sur des données synthétiques aux résultats connus. Le moteur PostgreSQL Windows, Hermes, HTTPS et vos volumes réels n'ont pas été exécutés ici. Les tests PostgreSQL effectués sont des tests de contrat/adaptation, pas une recette d'un serveur PostgreSQL.

## Défauts et corrections

| Priorité | Constat dans RC2F | Correction RC2G |
|---|---|---|
| Critique | `PgRow` itérait sur les noms des colonnes. `dict(cursor)` pouvait produire `{'key':'value'}` au lieu des paramètres réels. Même problème pour les compteurs d'import, la rétention et les totaux par jour. | Itération sur les valeurs, accès par nom et conversion `dict(row)` conservés. Tests de compatibilité avec SQLite. |
| Critique | Les insertions live sans liste de colonnes ne correspondaient plus aux tables enrichies de `ingest_seq`. | Colonnes explicites pour états et signaux techniques ; test avec colonne supplémentaire et réessai sans double compte. |
| Haute | `MAX(a,b)` utilisé pour le heartbeat et la référence d'appels correspond à SQLite, pas à l'agrégat PostgreSQL. | Expressions `CASE` portables ; les timestamps anciens ne remplacent pas les récents. |
| Haute | La recherche d'appels additionnait des expressions booléennes avec `SUM`, non prises en charge ainsi par PostgreSQL. | Comptages explicites par `CASE WHEN … THEN 1 ELSE 0 END`. Ajout de la recherche d'appels au contrôle de démarrage. |
| Haute | Les sommes PostgreSQL sur BIGINT reviennent en `Decimal`, non sérialisable par l'API JSON standard. | Normalisation au point de lecture : entiers exacts, nombres fractionnaires compatibles avec les durées SQLite. Test JSON et compteur supérieur à 2⁵³ sans arrondi Python. |
| Haute | Configuration, annuaire, priorités, live et initialisation Détails dépendaient encore de la présence de fichiers SQLite locaux. | Détection du moteur réel et identité PostgreSQL pour ces chemins. Une panne de connexion reste une erreur ; l'existence logique ne prétend pas vérifier sa santé. |
| Haute | La création de nouvelles tables PostgreSQL pouvait utiliser `REAL` 32 bits pour les timestamps, ou une clé entière sans génération automatique. | Nouvelles créations en double précision et clés générées. Le preflight signale les anciennes colonnes temporelles 32 bits. **Il ne reconstitue pas une précision déjà perdue** : un réimport source sera nécessaire si ce cas est détecté. |
| Haute | Une erreur SQL interceptée pouvait annuler les premières écritures, puis laisser valider la suite du traitement. | Transaction marquée en échec : validation refusée jusqu'au rollback explicite ; les erreurs ALTER ne sont plus ignorées. |
| Haute | Les indicateurs « traité » et « abandonné » contradictoires, ou des durées invalides, pouvaient coexister avec un contrôle affiché OK. | Contrôles source supplémentaires. Les drapeaux d'origine restent visibles ; aucune correction arbitraire des volumes. |
| Moyenne | L'agent non renseigné `0` n'était pas normalisé de la même façon dans Distribution sous PostgreSQL et SQLite. | Même valeur vide pour `0`, `S0` et absence d'identifiant. |
| Performance | Qualité agents recalculait toutes les campagnes, les heures et le QoS pour obtenir seulement les appels traités par agent. | Lecture dédiée aux comptes agents, dans le même instantané de supervision que les durées. |
| Performance | La couverture des journées était relue jour par jour ; les notes étaient relues événement par événement. | Couvertures lues par période et notes lues en un lot par page. |
| Performance | Chaque insertion PostgreSQL pouvait refaire les recherches de clés et séquences. | Métadonnées mémorisées par connexion ; pas de sondage de séquence pour les tables sans clé générée. |
| Performance | Le service Analytics traitait une requête à la fois ; son cache dépendait uniquement des filtres. | Huit requêtes au maximum en parallèle, regroupement des calculs identiques, invalidation après changement de données/configuration et fenêtre temporelle de cinq secondes. Surcharge refusée avec HTTP 503. |
| Performance | Le cache de projections Détails était entièrement désactivé sous PostgreSQL. | Réactivation sur identité du moteur, révision par triggers et filtres, avec lecture en instantané. |
| Interface | Un filtre modifié pendant le chargement de Supervision pouvait être ignoré. | L'ancien résultat est ignoré et le dernier filtre demandé est relancé. |

## Mesures comparatives

Banc isolé **SQLite**, 60 000 lignes d'appels, 50 agents, 30 jours et 1 500 intervalles d'activité. Cinq répétitions ; médiane par vue. Même jeu de données, même environnement, résultat attendu de 48 000 appels traités. Les temps excluent navigateur, réseau et serveur Windows.

| Mesure | RC2F | RC2G | Lecture |
|---|---:|---:|---|
| Qualité agents | 166,2 ms | 42,1 ms | Environ 75 % de temps en moins sur ce cas |
| Instructions SQL — Qualité agents | 223 | 109 | Réduction des accès répétés |
| Qualité de service | 150,1 ms | 148,1 ms | Pas de gain significatif démontré en local |
| Instructions SQL — Qualité de service | 61 | 31 | Moins d'allers-retours ; effet réseau PostgreSQL à mesurer |
| Distribution | 207,7 ms | 203,3 ms | Pas de gain significatif démontré |
| Cinq consultations Qualité agents simultanées | 2,0532 s | 0,7691 s | Les cinq résultats sont corrects |

Le test à cinq consultations utilise cinq threads appelant les vraies fonctions métier. Ce n'est pas un test de cinq sessions navigateur authentifiées. Aucun gain global sur toutes les interfaces, ni débit d'import PostgreSQL, n'est annoncé. Les 32 Go de RAM ne suffisent pas à déduire un gain : les chemins séquentiels et les requêtes répétées identifiés expliquent des attentes indépendantes de la RAM libre.

Reproduction sans toucher aux données installées : `python audit_benchmark.py --json benchmark.json`. Le script utilise uniquement les schémas vides embarqués dans `audit_empty_schemas.zip`, dans un répertoire temporaire. Les résultats avant/après figurent dans `audit_results/`.

## Vérification des données

**31 tests Python réussis**, plus un test JavaScript du changement de filtre pendant une requête. Ils couvrent notamment :

- totaux attendus reçus/traités/abandons/perdus, QoS, temps d'attente et répartition horaire ;
- bornes horaires exclusives, jours manquants distincts des zéros, campagne inexistante ;
- alias `S1001`/`1001`, identifiants avec domaine et agent non renseigné ;
- réimport identique, remplacement d'un instantané et rejet d'un import invalide sans perdre le précédent ;
- durées tronquées aux horaires, fusion des chevauchements, pauses et moyenne d'appel ;
- doublons live, heartbeat monotone et tables enrichies d'une colonne d'ingestion ;
- invalidation du cache, cinq demandes identiques calculées une seule fois ;
- journées de 23/24/25 heures lors des changements d'heure ;
- import complet puis réimport du même ZIP, lecture et JSON des principales vues à vide ;
- contrôles de transaction et adaptation des résultats PostgreSQL.

Commandes :

```text
python -m pytest audit_regression_test.py -q
node audit_frontend_test.js
```

Le test utilise des bases temporaires vides, jamais votre historique. Pytest est dans `requirements-test.txt` ; Node est nécessaire uniquement pour le test JavaScript.

La formule existante est conservée : **traités / (traités + abandonnés + perdus)**. Un perdu est une ligne ni traitée ni abandonnée portant overflow, rerouted ou before_queue ; ces drapeaux ne sont pas additionnés entre eux. Une ligne à la fois traitée et abandonnée provoque maintenant un échec de cohérence. Cela ne prouve toujours pas que Stats.INBOUND possède exactement le même périmètre qu'un rapport externe Hermes : ce rapprochement nécessite vos exports réels.

Les heures du contrôle Qualité sont maintenant communes aux vues Service, Agents et Distribution. Les totaux traités et les trois volumes de Distribution sont rapprochés entre interfaces. Les appartenances aux groupes restent celles de la configuration actuelle ; il n'y a pas d'historisation nouvelle des équipes. Les règles organisationnelles et la distinction diagnostic technique / performance métier ne sont pas redéfinies.

## Installation sur votre serveur

1. Conservez votre dossier actuel. Lancez `SAUVEGARDER_POSTGRESQL.bat` et vérifiez la sauvegarde avant mise à jour. La copie de fichiers effectuée par le programme de mise à jour **n'est pas une sauvegarde PostgreSQL**.
2. Décompressez RC2G dans un **autre dossier**. Les bases de cette archive sont les bases vides fournies : ne les copiez pas sur vos bases existantes.
3. Arrêtez Nelyio et ses services, les imports, la capture et Caddy. Depuis le nouveau dossier, lancez `MISE_A_JOUR_PRODUCTION.bat`, puis indiquez votre dossier installé. La mise à jour est limitée aux fichiers autorisés ; elle préserve les bases, `data/`, les paramètres PostgreSQL, comptes, certificats et Caddyfile. Elle reconnaît les fichiers exacts de l'archive RC2F fournie et refuse une cible inconnue/modifiée.
4. Dans le dossier installé, lancez `VALIDATION_PRODUCTION.bat`. Cette commande applique les réparations de schéma déjà prévues par le projet et vérifie les fonctions PostgreSQL. **Ne lancez pas de migration avec `--reset`.** Une alerte sur des timestamps 32 bits doit être examinée avant validation des chiffres.
5. Redémarrez avec `START_NELYIO.bat`, puis lancez `VALIDER_APRES_DEMARRAGE.bat`.
6. Après la fin des imports, lancez `AUDIT_DONNEES.bat`. Par défaut, il contrôle la dernière journée d'appels disponible. Pour une période :

```text
AUDIT_DONNEES.bat --date-from 2026-09-18 --date-to 2026-09-22
```

Le rapport est écrit dans `logs/audit_donnees.json`. Ce contrôle lit les données sans importer, réparer ni purger. Les journées manquantes, sources contradictoires, écarts entre interfaces et imports actifs empêchent la validation. Relancez après toute modification de référence pendant le contrôle. Pour une comparaison définitive, fournissez le rapport Hermes et l'export SIMPLIFY2 du même jour avec les mêmes horaires, agents et campagnes.

## Limites et suite de recette

Restent à valider sur votre serveur : exécution des SQL sur PostgreSQL, import représentatif de votre volume, navigation HTTPS à cinq personnes, callbacks Hermes réels, délais SQL et plans des requêtes lentes. Les corrections PostgreSQL n'ont pas été exécutées sur un moteur PostgreSQL ici : le serveur de test n'a pas pu être démarré dans cet environnement. N'appliquez donc pas l'étiquette « production validée » sur la seule base de ces tests locaux.

Les lectures de supervision utilisent un instantané cohérent par vue concernée. Administration et live utilisent encore des connexions distinctes : il n'existe pas de photographie transactionnelle unique de toute l'application. Le cache Analytics limite la réutilisation temporelle à cinq secondes ; les réponses live restent des observations provisoires. Le backend ouvre encore des connexions PostgreSQL à la demande : aucun pool non éprouvé ni réglage global mémoire de votre serveur n'a été ajouté.

Les quatre fichiers de bases et la configuration `data/` fournis sont conservés à l'identique. Les scripts/tests ajoutés, les empreintes du code et la simulation de mise à jour sont vérifiés. Cette archive contient le projet complet et le présent rapport.
