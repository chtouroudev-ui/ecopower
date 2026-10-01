# RC27 - Validation

## Fait
- correctif keyword-only `scope_query`/`scope_multi_query` ;
- Signalisation Qualité Live multi-cibles ;
- UI guidée et compacte ;
- exemples d'unités ;
- validation serveur du périmètre GROUP/AGENT/QUEUE.

## Vérifié
- 197/197 tests Python ;
- tests Phase 16 : PASS ;
- tous les JavaScript : syntaxe PASS ;
- audit frontend : PASS ;
- compileall : PASS.

## Risque maîtrisé
Aucune migration de base n'est requise. Les règles multi-cibles restent stockées dans le champ texte existant avec un encodage rétrocompatible.

## Upgrade RC26 -> RC27
- dry-run : PASS ;
- application sur copie RC26 : PASS ;
- `TECHIN_Stock_Manager.db` : SHA-256 identique ;
- `NELYIO_Supervision.db` : SHA-256 identique ;
- `Nelyio_Details.db` : SHA-256 identique ;
- `Nelyio_Live.db` : SHA-256 identique ;
- `Nelyio_Services.db` : SHA-256 identique ;
- `Caddyfile` : SHA-256 identique.
