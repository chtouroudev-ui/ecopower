# RC29.4 — Validation Phase 6 — Centre Qualité Live R10

## Objet
Corriger les valeurs Campagnes du Centre Qualité Live et aligner l'interface sur les derniers ajustements demandés, sans modifier les KPI métier ni la formule QoS canonique.

## Correctifs vérifiés

- `Ready` et `Available` Hermes sont maintenant normalisés en `ready` / Disponible, au même titre que `Waiting`, `Disponible` et `Prêt`. `Mise en attente` / `HOLD` reste strictement distinct et classé `hold`.
- Le rendu Campagnes ne référence plus `latestPayload` hors de sa portée lexicale. Les diagnostics UpQuR/UpQuH sont passés explicitement à `liveScopeRowsHtml()`.
- La jointure campagne → file conserve les sources existantes (configuration + couple campagne/LineId réellement observé) et ajoute un fallback conservateur : correspondance **exacte** entre le nom de campagne configuré et le nom de file observé via `InitQueue` du jour. Aucun fuzzy matching n'est utilisé.
- Un agent effectivement observé sur un LineId ou une campagne est conservé dans le périmètre Live même si l'affectation ACTIVE importée est incomplète. Cela ne modifie aucune donnée historique ni aucun groupe enregistré.
- Pour une campagne à une seule file seulement, `agents_available_on_queue` UpQuR peut servir de fallback lorsque l'état individuel Disponible est indisponible. Les compteurs de plusieurs files ne sont jamais additionnés afin d'éviter les doubles comptes.
- Traités, Abandonnés et QoS restent alimentés par UpQuH lorsque ces compteurs sont réellement reçus. Si UpQuH est absent, Nelyio conserve `—` au lieu d'inventer zéro.
- Formule QoS Live native : `handled / (received - exclusion1 - exclusion2 - exclusion3) * 100`. Si le dénominateur est <= 0, QoS = `—`.
- Le tableau Campagnes n'a plus de pagination de 10 lignes : toutes les campagnes sont disponibles dans le scroll vertical interne avec en-tête collant.
- La vue Campagnes reste sans colonne Statut.
- Agents : `Durée appel` devient `Appel total`; sous l'état, la durée est explicitement libellée `HOLD` pendant une mise en attente ou `État` sinon. Les deux durées restent donc visibles simultanément pendant HOLD.
- Les colonnes Agents Traités, Pauses, Déconnecté et ANI sont conservées.
- Sous 900 px, le sélecteur Agents / Campagnes / Double vue masque réellement le panneau non sélectionné.
- Marqueur runtime : `RC29.4 · Live Native R10`.

## Sécurité / invariants

- Aucune modification des règles de signalisation.
- Aucun changement du périmètre d'accès groupe.
- Aucun reset ni migration destructive.
- Aucun compteur inconnu transformé en zéro.
- ANI inchangé et toujours soumis à l'autorisation existante.
- Réconciliation des lignes Agents par `agent_id` inchangée.
- Protection contre réponses obsolètes inchangée.

## Validation

- `python -m py_compile supervision_utils.py collection_store.py live_quality.py` : OK.
- `node --check static/live-views.js` : OK.
- Suite ciblée Phase 1 → Phase 6 + régressions Live/Campagnes/états : **75 tests passés**.
- Revalidation UI Phase 4–6 après passage R10 : **16 tests passés**.
- Un ancien test `rc29_r8_campaign_mapping_test.py::test_view_selector_is_top_only` attend encore littéralement le marqueur `RC29.3 · Live Native R9`. Cette assertion de version est obsolète pour RC29.4/R10 et sera remise en cohérence pendant la Phase 7; le test métier de mapping campagne du même fichier reste valide.

## Conclusion
Phase 6 validée. Les valeurs Campagnes sont maintenant reliées aux compteurs Hermes lorsqu'une preuve de file existe; toute absence réelle de compteur reste visible comme `—`.
