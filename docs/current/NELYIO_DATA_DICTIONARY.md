# Nelyio V60.5-ARCH-RC2 — Dictionnaire des données

Date de validation laboratoire : 25/09/2026.

Ce document décrit les sources réellement utilisées par Nelyio. Une donnée non prouvée par les sources reste indisponible ou indéterminée ; elle n'est pas fabriquée pour compléter l'interface.

## 1. Hiérarchie métier

Hiérarchie analytique :

`SERVICE -> GROUPE -> FILE -> AGENT -> APPEL`

- `SERVICE` : valeur configurable dans `user_groups.service_name`. Aucune affectation MEDICAL/IMAGERIE n'est déduite automatiquement.
- `GROUPE` : configuration Nelyio.
- `FILE` : `quality_group_lines` / affectations de files importées.
- `AGENT ACTIF` : affectation `StartAllContexts=true`. Une affectation partielle n'accorde pas automatiquement l'appartenance analytique au groupe.
- `CAMPAGNE` : dimension analytique. Elle ne remplace ni le service, ni le groupe, ni la file.

Un agent peut appartenir à plusieurs groupes. Les agrégations utilisent un prédicat de périmètre, pas une addition des résultats de chaque groupe, afin d'éviter les doubles comptages.

## 2. Qualité de service

Source principale : `Stats.INBOUND`, importée dans `quality_inbound_facts`.

Indicateurs source conservés séparément :

- reçus ;
- `IsCallAnswered` ;
- abandonnés ;
- clôturés ;
- overflow ;
- reroutés ;
- raccroché avant file ;
- transférés ;
- `IsCallLost` ;
- attente ;
- durées sources disponibles.

### Traité

Le KPI métier `treated_agent` suit la sémantique Nelyio validée : agent attribué (`AgentId > 0`, avec compatibilité des identifiants `Sxxxx`). Il ne doit pas être remplacé silencieusement par `IsCallAnswered`.

### QoS

Formule canonique actuelle :

`QoS = (traités par agent + reroutés sans agent) / (reçus - clôturés - raccrochés avant file) * 100`

Le numérateur et le dénominateur sont exposés séparément. La formule est centralisée dans `quality_rules.py` et réutilisée par les vues Qualité/Pilotage.

### ASA

`ASA = somme des attentes valides des appels attribués / nombre de ces attentes`.

Les durées négatives restent signalées comme problème de qualité de source au lieu d'être transformées silencieusement.

## 3. Qualité agents

Sources :

- `Stats.AGENT` -> `quality_agent_facts` / `activities` pour les activités, durées et **Appels traités par agent** ;
- `Stats.INBOUND` pour les indicateurs du record service (répondu, attente/ASA, durée d'appel) et comme fallback historique uniquement si la source Stats.AGENT est absente pour la journée ;
- affectations de files pour le périmètre analytique.

### Appels traités par agent

Règle canonique RC2 :

`1 SessionID unique en état Inbound call / Appel entrant = 1 interaction réellement traitée par cet agent`

Si `SessionID` est vide, la ligne source stable sert de clé de secours. Un appel transféré peut donc compter pour plusieurs agents lorsqu'ils ont chacun réellement eu une phase `Inbound call`. Ce compteur **ne remplace pas** le KPI global de Qualité de service et ne modifie pas la QoS, qui restent calculés depuis `Stats.INBOUND`.

La distribution par campagne dans Qualité agents utilise exactement le même compteur Stats.AGENT afin que le détail conserve le total affiché.

Les états FR/EN sont normalisés centralement. Les états anglais d'appel reconnus comprennent notamment `Inbound call`, `Outbound call`, `Manual call`, `Dialing` et `Consultation`. `Ringing` n'est pas assimilé à une conversation.

`Appels < 10 s` n'est plus un KPI Qualité agents : il est centralisé dans **Analytiques > Appels suspects**.

## 4. Appels historiques détaillés

Source : `ODCalls`.

Table historique compatible : `phone_calls`.

Identifiant canonique : `ODCalls.ID` lorsqu'il existe.

Extension non destructive : `phone_call_details`, liée par `(import_id, call_id)` :

- `call_duration` ;
- `wait_initial` (`WaitDuration`) ;
- `total_wait` ;
- `first_queue` ;
- `last_queue` ;
- `first_campaign` ;
- `last_campaign` ;
- `last_transfer`.

`LastQueue` n'est jamais supposé être systématiquement une file : les exports réels montrent qu'il peut porter d'autres identifiants après transfert.

Un re-import d'une archive déjà connue peut enrichir `phone_call_details` sans dupliquer `phone_calls`.

## 5. Appels suspects

Source : `ODCalls` + `phone_call_details`, avec corrélation des signaux techniques existants.

Catégories :

- `short` : durée d'appel connue >= 0 et < 10 s ;
- `long_suspect` : appel >= 10 s avec attente initiale >= 30 % ou signal technique ;
- `wait30` : attente initiale >= 30 % de la durée ;
- `wait50` : attente initiale >= 50 % de la durée ;
- `end_agent` : fin par agent uniquement quand `EndByAgent=1` le prouve ;
- `end_caller` : aucune conclusion n'est fabriquée à partir de `EndByAgent=0` ;
- `technical` : signal technique corrélé lorsque disponible.

`EndByAgent=0` ne signifie pas automatiquement « fin par appelant ». Sans preuve supplémentaire : **Origine de fin indéterminée**.

Les appels couverts par une Policy/Déclaration avec exclusion statistique restent visibles comme preuve brute mais sont annotés **Exclu des KPI**.

## 6. Relations d'appels

Source : `ODRelations` lorsque disponible.

Les relations parent/enfant doivent être utilisées pour les reroutages/consultations plutôt que de déduire une chaîne depuis `LastQueue` ou des horaires proches.

## 7. Temps et unités

- `ODCalls.DateUTC` : UTC.
- Affichage métier : `Europe/Paris`, géré centralement.
- Sur l'export réel du 21/09/2026, la correspondance observée avec `Stats.INBOUND.Date` était UTC + 2 h.
- `Stats.AGENT.ActionDuration` est traité en secondes.
- `ODActions.Duration` ne doit pas être mélangé directement aux durées Stats sans normalisation ; l'audit réel indique une échelle compatible avec des centièmes de seconde.

Fenêtre métier Nelyio : configurable, référence actuelle 08:00–19:00.

## 8. Pilotage Qualité

Sources : agrégats Qualité existants + configuration de groupes/services + Policies/Déclarations.

Baseline : occurrences précédentes du **même jour de semaine** et du même périmètre sélectionné. Le moteur préfère la médiane et exige un volume minimum configurable.

- pas assez de journées comparables -> `Données insuffisantes` ;
- aucun signal n'est généré uniquement sur un très petit volume ;
- MEDICAL et IMAGERIE ne sont pas comparés l'un contre l'autre ;
- lorsque l'écran global contient plusieurs services parents, les KPI globaux peuvent être affichés mais les signaux sont calculés **séparément par service**.

Une action et une évolution avant/après décrivent une association temporelle : Nelyio affiche **Évolution observée après l'action**, jamais une causalité prouvée.

## 9. Live opérationnel

Spool opérationnel : `Nelyio_Live.db` (SQLite/WAL local).

Le Live expose uniquement les faits observés :

- agents connus/connectés ;
- état courant ;
- appel observé ;
- file/campagne observées ;
- référence Live locale ;
- chronologie des états observés ;
- santé collecteur/Hermes/worker.

La Référence Live n'est pas présentée comme un Call ID Hermes/SIMPLIFY2.

Les compteurs non documentés Hermes ne sont pas renommés arbitrairement « attente patient » ou « conversation certifiée ».

## 10. Historique Live factuel

Table persistante : `supervision.live_call_observation_history` en production PostgreSQL (SQLite de compatibilité en laboratoire).

Cette table reçoit uniquement les **observations Live finalisées** :

- clé Live stable (`history_key`) ;
- jour métier ;
- début/fin observés ;
- agent ;
- file ;
- campagne ;
- référence Live ;
- fonction source ;
- statut final ;
- début partiel ;
- rupture de continuité ;
- durée observée ;
- session/source.

Elle ne contient volontairement **ni ANI, ni faux Call ID, ni attente patient, ni durée de conversation certifiée**.

Cette table est une preuve technique historique. Elle n'alimente pas automatiquement QoS, Pilotage ou Appels suspects. Les imports SIMPLIFY2 restent autoritatifs pour ces KPI.

La purge du spool Live refuse de supprimer une ancienne session contenant une observation non synchronisée.

## 11. ANI et confidentialité

Le droit `ani` est distinct du droit d'accès à Recherche d'appels.

- droit ANI : valeur complète ;
- sans droit ANI : valeur masquée ;
- sans droit ANI, une recherche générique ne peut pas tester silencieusement la présence d'un numéro complet.

Aucun ANI n'est persisté dans l'historique factuel Live.

## 12. Données insuffisantes / indisponibles

Nelyio n'invente pas :

- le nombre exact d'agents connectés historiques si la source ne le permet pas ;
- une occupation horaire si les états nécessaires ne sont pas disponibles ;
- l'origine « appelant » d'une fin d'appel sans preuve ;
- un nombre de navigateurs Live connectés dans l'architecture polling actuelle ;
- une attente patient certifiée depuis un compteur Hermes non documenté ;
- une baseline statistique depuis une seule journée.

## RC4 — Métadonnées d'enregistrements Hermes et densité média

Source : `changes.ashx?act=folder_info&basePath=RECORD&extension=*.wav` depuis la supervision Hermes authentifiée.

Format observé et validé dans le HAR utilisateur :

`AGENT#YYYYMMDD#HHMMSS#INDICE.wav`

Exemple : `1079#20260824#085611#781592555.wav`.

Contrat actif RC10 : `call_recording_sizes` ne conserve que :

- `indice` : clé unique de jointure vers `phone_calls.indice` ;
- `size_bytes` : taille WAV totale agrégée pour cet Indice.

Le nom du WAV, l'agent, la date, l'heure, la racine SDA/campagne et le chemin Hermes ne sont utilisés qu'en mémoire pendant le crawl puis sont jetés. Si plusieurs WAV partagent le même Indice, leurs tailles sont additionnées avant stockage. L'ancienne table `call_recordings` reste uniquement pour migration rétrocompatible des RC4-RC9 ; les nouvelles synchronisations n'y écrivent plus.

Aucun audio, cookie, mot de passe ou UID Hermes n'est persisté.

### Signal « Contenu faible / size anormal »

Dénominateur : `ConvDuration` si > 0, sinon `CallDuration`.

Densité : `size_bytes / secondes_media`, où `size_bytes` est déjà le total agrégé par Indice.

Référence initiale configurable : 8 000 octets/s, cohérente avec les mesures utilisateur d'environ 7,93 et 8,01 kB/s sur des appels standards.

Règle par défaut :

- durée média >= 30 s ;
- exactement 1 WAV pour l'Indice ;
- aucune mise en attente Hermes ;
- aucun transfert / consultation / reroutage ODRelations ou LastTransfer ;
- taille > 0 ;
- « contenu faible » si densité < 60 % de la référence ;
- « contenu très faible » si densité < 35 % de la référence.

Cette règle est un **indice à vérifier**, pas une preuve que l'appel ne contient aucun son. Elle mesure surtout une couverture d'enregistrement anormalement faible par rapport à la durée attendue.

## RC11 - Correctif Size sans conversation

Le signal `Contenu faible / size` exige desormais `ConvDuration > 0`. La densite est calculee uniquement comme `Size / ConvDuration`; `CallDuration` ne sert plus de fallback. Si `Conversation = 0 s`, l appel est considere non analysable par Size et aucun motif Size n est genere.


## RC12 - Validation stricte Indice / Size

RC12 invalide les anciennes tailles non vérifiées et reconstruit `Indice -> Size` uniquement à partir de WAV Hermes dont l'Indice correspond à un appel SIMPLIFY2 unique, sur la même journée de référence, avec `Conversation > 0` et un agent cohérent. Les métadonnées de validation (nom WAV, date, agent, chemin) restent transitoires et ne sont pas persistées. Appels suspects n'affiche le Size que si cette validation est acquise.
