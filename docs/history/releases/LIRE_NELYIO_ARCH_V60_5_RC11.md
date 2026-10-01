# Nelyio ARCH V60.5 RC11 - Correctif Size sans conversation

## Pourquoi
Trois appels du 18/09/2026 etaient classes `Contenu tres faible / size` alors que l'interface affichait `Conversation 0 s` et que les enregistrements n'etaient pas retrouvables dans la supervision.

## Correctif
Le signal Size exige maintenant obligatoirement une duree de conversation positive.

- densite = `Size / ConvDuration` ;
- aucun fallback vers `CallDuration` ;
- si `ConvDuration = 0`, l'appel est non analysable par Size ;
- aucun motif `Contenu faible / size` ou `Contenu tres faible / size` n'est genere dans ce cas ;
- les autres motifs (appel <10 s, mise en attente, technique, fin agent) restent independants.

## Validation
Un test de regression reproduit un appel long avec `Conversation = 0 s` et un petit Size. Le resultat attendu est l'absence de motif Size.
