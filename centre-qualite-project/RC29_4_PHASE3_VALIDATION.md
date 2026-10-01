# RC29.4 — Phase 3 validation

## Scope
Phase 3 — Collecteur : interface. No KPI, QoS, signalisation, Live business calculation or CDP backend behavior changed in this phase.

## Implemented
- Visible `Détection automatique` switch at the top of Collecteur Live.
- Operational banner states: automatic disabled, automatic ready/scheduled, waiting for Edge, tab detected, capture running with last-data age, manually stopped with explicit same-day reactivation.
- Persistent schedule editing: start/end time and active days.
- Advanced CDP/privacy options moved under a dedicated disclosure.
- Manual fallbacks kept: Tester le navigateur, Démarrer manuellement, Arrêter.
- `Tester le navigateur` no longer automatically pins the single returned target id; automatic target selection stays selected unless the administrator explicitly chooses another target.
- Manual Stop remains a same-day automatic hold; `Réactiver aujourd’hui` calls the existing Phase 1 `/api/collection/auto` action.

## Security / invariants preserved
- Local diagnostic wording explicitly keeps 127.0.0.1.
- No JavaScript injection into the supervised page.
- No audio, cookie, password or raw HTTP body recording added.
- Phone collection remains governed by the existing checkbox.
- No business database reset or schema rewrite.

## Verification
- `node --check static/collection.js`: PASS.
- Python compilation for collector backend touched in earlier phases: PASS.
- RC29.4 Phase 1–3 targeted suite: 27 PASS / 0 FAIL.
- Existing collection-specific tests present in the tree rerun separately; see command output from the build session.

## Files changed in Phase 3
- `static/collection.js`
- `static/collection.css`
- `rc29_4_phase3_collection_ui_test.py` (new test)

## Not done yet
- Phase 4/5 Centre Qualité Live UX changes.
- Additional user-requested campaign KPI/UI reconciliation is reserved for Phase 6.
- Full final regression gate and production manifest update are reserved for Phase 7.
