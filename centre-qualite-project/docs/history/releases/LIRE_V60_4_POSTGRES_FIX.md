# NELYIO V60.4 — Correctif PostgreSQL prioritaire

Build : **60.4-POSTGRES-HOTFIX**  
Date : **25/09/2026**

## Pourquoi ce hotfix

V60.4 ne part pas d'une supposition. Il cible les mesures recueillies sur le PostgreSQL de production via les outils V60.3.

### Preuves production avant correctif

- `Détails`: une requête Analytics a duré **133.3 s** dont **132.9 s SQL**. La requête SQL la plus lente de ce run a pris **92.1 s**. Le Web a abandonné à 90 s alors que le worker Analytics continuait encore.
- Un second `Détails` a pris **13.8 s**, dont **13.6 s SQL** et 39 requêtes SQL.
- `Analytics`: **26.5 s**, **997 requêtes SQL** sur une seule vue : pattern N+1 avéré.
- Catalogue agents/Équipe & Files : le plan PostgreSQL triait environ **607 174 lignes** d'activités pour retourner environ **103 agents**, avec `external merge` sur disque (~24.5 MB), soit environ **2.5–3.6 s** pour ce seul catalogue.
- `Support`: ~7.8 s dans la trace réelle.
- `Diagnostic`: jusqu'à ~19.1 s dans la trace réelle.
- `Recherche d'appels`: ~2.7 s dans la trace réelle.

À l'inverse, les plans Appels paginés, ANI partiel et faits Qualité du dernier jour étaient déjà courts. Cela ne justifie pas un reset de base.

## Corrections V60.4

### 1. Catalogue agents / Équipe & Files

Avant, `latest_agent_names()` pouvait faire un `DISTINCT ON` historique sur toute la table `activities`.

V60.4 utilise, pour le catalogue non filtré, uniquement le **dernier import ACTIVE** de `coverage`. Un lookup explicite de quelques agents conserve le chemin historique exact.

Index ajouté :

```sql
CREATE INDEX IF NOT EXISTS supervision_activity_import_agent_latest
ON supervision.activities(import_id, agent, id DESC);
```

### 2. Détails — références de jours

Avant, Détails relisait `active_days` deux fois par jour/source et répétait cette préparation sur plusieurs sous-chemins. Une période longue générait donc des dizaines de petites requêtes avant même la requête lourde.

V60.4 charge les pointeurs `active_days` **en une seule requête pour toute la période** puis construit les fenêtres en mémoire.

Test ciblé : 3 jours / 2 sources -> **1 lecture `active_days`**.

### 3. Détails — chemin de page PostgreSQL

Index ajouté pour le chemin métier réel : source + import autoritaire + ordre temporel.

```sql
CREATE INDEX IF NOT EXISTS details_detail_event_source_import_page
ON details.detail_events(event_source, source_import_id, start DESC, id DESC);
```

Les filtres de sélection restent appliqués aux données brutes `detail_events` : aucun journal n'est remplacé par une statistique synthétique.

### 4. Analytics / Support — suppression du N+1 de fermeture probable

Avant, chaque coupure ressemblant à une fermeture/pause probable pouvait exécuter deux requêtes SQL : activité juste avant + activité juste après. Sur une grande période, cela produisait des centaines de requêtes.

V60.4 :

1. détecte d'abord les candidats avec le même prédicat métier ;
2. charge les activités voisines avec **au plus une requête bornée par jour** ;
3. construit un index mémoire par agent ;
4. applique exactement le même contrôle avant/après.

Un test de non-régression compare l'ancien fallback SQL et le nouvel index mémoire : même classification.

## Migration PostgreSQL

Faire une sauvegarde puis exécuter :

```text
migrations\performance_indexes.sql
```

La migration est idempotente et non destructive : aucun `DROP`, `TRUNCATE`, reset ou suppression de données.

## Recette production

1. Sauvegarder PostgreSQL.
2. Appliquer `migrations\performance_indexes.sql`.
3. Arrêter l'ancienne version Nelyio.
4. Extraire V60.4 dans un **nouveau dossier**.
5. Copier votre vrai `data\postgres.env`.
6. Démarrer V60.4.
7. Recharger le navigateur avec **Ctrl+F5**.
8. Vérifier `/healthz` : build V60.4, Web/Live/Analytics verts.
9. Lancer :

```bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
DIAGNOSTIC_PERFORMANCE_POSTGRESQL.bat
```

10. Tester en priorité : Détails 1 jour puis 23/30 jours, Diagnostic, Support, Équipe & Files et Recherche d'appels.

## Ce qui reste à mesurer sur le serveur

Le gain **PostgreSQL réel après V60.4** est volontairement marqué **NON MESURÉ** tant que `explain_after.json` et les nouvelles traces `performance.jsonl` ne sont pas rejouées sur le serveur. Les chiffres avant ci-dessus viennent, eux, de la trace production fournie.
