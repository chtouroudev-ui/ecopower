# Nelyio RC2K - PERF FIX1

## Cause racine traitee

Le backend HTTP pouvait etre disponible mais rester tres lent car des travaux lourds partageaient encore le chemin Web/PostgreSQL :

1. `app.py` lancait une synchronisation complete Details dans un thread du processus Web apres le demarrage.
2. `details_store.details_view()` pouvait relancer une synchronisation au moment meme d'une lecture HTTP.
3. `live_service.py` synchronisait Details a chaque publication Live, potentiellement tres frequemment.
4. Le Dashboard recalculait deux fois la projection couteuse du dernier etat des PC.

## Corrections

- En architecture services, le processus Web ne lance plus la maintenance lourde de demarrage.
- L'interface Details ne synchronise plus la projection dans le thread de la requete HTTP quand les services externes sont actifs.
- Le Live publie toujours rapidement les evenements, mais la projection Details est rafraichie au maximum toutes les 10 secondes pendant l'activite, puis forcee a la fermeture de session.
- Le Dashboard reutilise son premier calcul au lieu d'executer `current_sql()` deux fois.
- `logs/http_slow.log` journalise automatiquement toute requete HTTP >= 1 seconde, sans query string ni donnee patient.

## Validation

- `pytest -q` : 37/37 PASS
- Verification syntaxe JavaScript : PASS
- `py_compile` des fichiers modifies : PASS

## Fichiers modifies

- `app.py`
- `details_store.py`
- `live_service.py`
- `routes_inventory.py`
- `production_http.py`

## Apres installation

Redemarrer completement Nelyio et ses services. Si une page reste lente, consulter :

```powershell
Get-Content .\logs\http_slow.log -Tail 100
```

Chaque ligne indique uniquement methode, chemin API et duree, par exemple :

`2026-09-23 17:00:00 GET /api/supervision/details 2.431s`
