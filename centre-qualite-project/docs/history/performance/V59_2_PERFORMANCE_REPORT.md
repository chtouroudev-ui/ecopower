# NELYIO V59.2 — Performance hardening

Build: **59.2-PROD-PERF**

## Correctifs principaux

1. **Cache Analytics PostgreSQL piloté par les données**
   - suppression du bucket temporel de 15 s comme clé de révision ;
   - les résultats longs peuvent maintenant réellement entrer dans le cache ;
   - Quality est invalidé par les imports/configurations, pas par l'horloge ;
   - Support/Diagnostic/Analytics sont invalidés par les marqueurs réels imports/live/signaux/notes.

2. **Quality Service PostgreSQL**
   - suppression du grand prédicat `OR` jour par jour pour PostgreSQL ;
   - sélection compacte par `import_id`, `day`, intervalle global et plage horaire Europe/Paris ;
   - conservation du comportement SQLite historique pour les tests de régression.

3. **Durée du cache Quality**
   - réponses Quality : jusqu'à 300 s tant que la révision métier ne change pas ;
   - le cache reste partagé dans le worker Analytics pour les utilisateurs simultanés.

## Validation isolée

- `audit_regression_test.py` : OK
- `production_stability_test.py` : OK
- Benchmark SQLite isolé, 60 000 appels / 50 agents / 30 jours :
  - Quality Agents médiane ~0,0675 s
  - Quality Service médiane ~0,4394 s
  - Distribution médiane ~0,2577 s
  - 5 vues Quality Agents concurrentes : ~0,854 s, résultats corrects

## Validation production à faire

Après démarrage sur PostgreSQL réel :

1. Ouvrir une vue lente une première fois (MISS).
2. Recharger exactement le même filtre : la seconde réponse doit être nettement plus rapide (HIT).
3. Contrôler `logs/http_slow.log` pour les endpoints restant >1 s.
4. Si un fetch reste >5 s, conserver le HAR et `http_slow.log` : le point restant sera alors une requête PostgreSQL précise, pas Caddy/HTTPS.
