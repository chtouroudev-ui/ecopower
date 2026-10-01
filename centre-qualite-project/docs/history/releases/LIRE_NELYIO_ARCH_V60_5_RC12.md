# Nelyio ARCH V60.5 RC12 - Size Hermes vérifié

RC12 corrige les faux rattachements de taille WAV observés dans Appels suspects.

## Règle

Un Size n'est conservé que si le WAV Hermes correspond à un appel SIMPLIFY2 unique avec :

- même Indice ;
- même journée de référence ;
- Conversation > 0 ;
- agent du fichier cohérent avec le premier/dernier agent de l'appel quand disponible.

Si la correspondance manque ou est ambiguë, le Size est rejeté.

## Migration

Au premier démarrage RC12, les anciens Size RC4-RC11 sont invalidés une fois. Relancer `SYNC_RECORDING_SIZES.bat` en mode `TOUT` pour reconstruire les tailles vérifiées.

La base conserve toujours uniquement `Indice` et `Size`; filename, date, agent, SDA/campagne et chemin ne sont pas persistés.

## Appels suspects

Un appel `Conversation = 0 s` est non analysable par Size : aucune taille WAV ni densité n'est affichée et aucun motif Size n'est produit. L'Indice est maintenant visible directement dans la ligne pour comparaison avec Hermes.

## Validation

106/106 tests Python passent sur le candidat RC12.
