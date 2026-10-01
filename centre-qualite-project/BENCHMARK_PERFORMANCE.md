# NELYIO V60.4 — Benchmark et mesures PostgreSQL

Build : **60.4-POSTGRES-HOTFIX**  
Date : **25/09/2026**

## Mesure production avant hotfix

| Fonction | Avant V60.4 réel | Après V60.4 réel |
|---|---:|---:|
| Détails | 13.8 s à **133.3 s** | **NON MESURÉ** |
| Analytics | **26.5 s / 997 SQL** | **NON MESURÉ** |
| Diagnostic | jusqu’à **19.1 s** | **NON MESURÉ** |
| Support | ~**7.8 s** | **NON MESURÉ** |
| Recherche appels | ~**2.75 s** | **NON MESURÉ** |
| Roster agents | **2.47–3.63 s** | **NON MESURÉ** |

Les temps « après » ne sont volontairement pas inventés. Pour les obtenir :

```bat
APPLIQUER_INDEX_PERFORMANCE_POSTGRESQL.bat
EXPLAIN_PERFORMANCE_POSTGRESQL.bat after
DIAGNOSTIC_PERFORMANCE_POSTGRESQL.bat
BENCHMARK_5_UTILISATEURS.bat
```

Le benchmark synthétique reste un contrôle algorithmique, pas une mesure de ton PostgreSQL.

---

# NELYIO V60.3 — Benchmark performance

Build : **60.3-PROD-FINAL**  
Date : **24/09/2026**

## 1. Règle de lecture

Trois sources de mesure sont volontairement séparées :

1. **HAR réel avant correction** : mesures du navigateur sur le serveur Nelyio ;
2. **benchmark algorithmique isolé** : SQLite synthétique, mêmes données et mêmes fonctions pour comparer les algorithmes sans toucher aux bases métier ;
3. **PostgreSQL/Windows réel après déploiement** : **NON MESURÉ** dans l'environnement de construction.

Aucun temps PostgreSQL production n'est inventé.

## 2. Baseline HAR réelle

| Fonction | Avant réel observé |
|---|---:|
| Support | médiane ~8.04 s, max **31.52 s**, payload jusqu'à ~3.42 MB |
| Recherche d'appels | max **9.15 s** |
| Supervision | max ~5.78 s dans le dernier HAR ; ~32.06 s dans le HAR de gels |
| Diagnostic incidents | ~3.60 s |
| Qualité Agents | ~2.48 s dans le dernier HAR ; max ~53.06 s dans le HAR de gels |
| Distribution | ~1.01 s dans le dernier HAR |
| Priorités / Équipe & Files | max ~**36.03 s** dans le HAR de gels |
| Groupes | max ~**18.41 s** dans le HAR de gels |
| Dashboard | max ~26.60 s dans le HAR de gels |
| Login | jusqu'à ~83 s dans `http_slow.log` |

L'attente du premier octet serveur domine les requêtes lentes ; TLS/Caddy n'explique pas ces durées.

## 3. Comparaison V60.1 → V60.3 sur le même benchmark synthétique

Fixture : **60 000 appels, 50 agents, 30 jours**. Les valeurs V60.1 sont une exécution de référence conservée ; V60.3 est la médiane de **3 exécutions**, chaque vue étant elle-même répétée plusieurs fois.

| Fonction | V60.1 | V60.3 | Gain mesuré |
|---|---:|---:|---:|
| Qualité Agents | 0.0918 s | **0.0751 s** | x1.22 |
| Qualité de service | 0.5062 s | **0.4787 s** | x1.06 |
| Distribution | **0.2625 s** | 0.2670 s | x0.98 — quasi inchangé |
| Support | 1.0067 s | **0.0849 s** | **x11.86** |
| Recherche d'appels | 1.0940 s | **0.0855 s** | **x12.80** |
| Diagnostic | 0.4403 s | **0.0264 s** | **x16.68** |
| 5 vues mixtes simultanées | 3.3879 s | **0.5023 s** | **x6.74** |

Les résultats métier du benchmark restent cohérents avant/après. La Distribution n'est pas présentée comme améliorée : sa différence est dans le bruit de mesure.

## 4. V60.3 — Équipe & Files / Priorités / Groupes

Même fixture V60.3 avec 5 groupes, 10 files et 50 agents ACTIVE :

| Vue | V60.3 |
|---|---:|
| Priorités / Équipe & Files — froid | **0.0083 s** médian |
| Priorités / Équipe & Files — cache chaud | **0.0023 s** médian |
| Statut Groupes léger | **0.0014 s** médian |

La logique métier reste : **Groupe → Files → Agents avec affectation ACTIVE**. Les campagnes ne deviennent pas une source primaire d'appartenance.

## 5. V60.3 — concurrence synthétique

Trois runs indépendants :

- 5 vues Qualité Agents directes : 0.6989 s / 0.6226 s / 0.9128 s ; médiane **0.6989 s** ;
- 5 vues mixtes : 0.4988 s / 0.5261 s / 0.5023 s ; médiane **0.5023 s** ;
- exactitude : **OK** sur les 5 résultats de chaque run.

Le chemin de production Analytics possède en plus un **single-flight** : 5 requêtes identiques à froid déclenchent un seul calcul réel, vérifié par test de régression.

## 6. Objectifs vs validation actuelle

| Objectif | État |
|---|---|
| Navigation simple <500 ms | **NON MESURÉ sur serveur réel** |
| Filtre standard <500–800 ms | **NON MESURÉ sur serveur réel** |
| Recherche ANI <500 ms | **NON MESURÉ sur serveur réel** ; index trigram optionnel préparé |
| Dashboard <1 s | **NON MESURÉ sur serveur réel** |
| Rapport complexe <2 s | Algorithme synthétique conforme sur les vues testées ; **PostgreSQL réel NON MESURÉ** |
| 5 utilisateurs simultanés | Synthétique OK ; **HTTP/PostgreSQL production NON MESURÉ** |

## 7. Benchmark production à exécuter

Après démarrage et warm-up :

```bat
set NELYIO_BENCH_USER=votre_compte_test
set NELYIO_BENCH_PASSWORD=votre_mot_de_passe_test
BENCHMARK_5_UTILISATEURS.bat
```

Résultat : `BENCHMARK_API_RUNTIME.json`. Les identifiants ne sont pas enregistrés dans le rapport.

Pour analyser les traces Backend :

```bat
ANALYSER_PERFORMANCE_HTTP.bat
```

Pour une nouvelle capture navigateur :

```bat
python tools\analyze_har.py chemin\capture.har --output logs\har_after.json
```

Le fichier reproductible du benchmark intégré est `V60_3_SYNTHETIC_BENCHMARK.json`.
