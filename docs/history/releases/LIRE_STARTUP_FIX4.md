# Nelyio RC2K - STARTUP FIX4

## Cause racine confirmee

`app.py` importe `supervision.py` avant d'entrer dans `main()`.
`supervision.py` execute `init()` a l'import et `supervision_db.init()` lancait une
synchronisation complete de Details avec `force=True`.

Sur une base de production volumineuse, cette synchronisation pouvait durer plus
de 120 secondes. Pendant ce temps :

- Python restait vivant ;
- le port 9051 restait ferme ;
- `backend_9051_stdout.log` et `stderr.log` pouvaient rester vides ;
- `startup_progress.log` n'etait pas encore cree par `main()` ;
- le lanceur finissait en code 14.

## Correction

- `START_NELYIO.ps1` definit `NELYIO_SKIP_STARTUP_DETAILS_SYNC=1` avant de lancer `app.py`.
- `app.py` ecrit maintenant une trace bootstrap AVANT l'import de `supervision`.
- La reconstruction Details est executee apres l'ouverture du serveur HTTP, dans
  le thread de maintenance post-demarrage.
- `/healthz` et le port 9051 ne dependent donc plus de la reconstruction Details.

## Diagnostic attendu

`logs/startup_progress.log` doit au minimum contenir :

```
Bootstrap Python : avant import supervision
Bootstrap Python : import supervision termine
Debut app.py
...
Serveur HTTP pret a ecouter sur 127.0.0.1:9051
```

La ligne `Synchronisation Details differee ...` peut continuer apres que le site
est deja disponible.
