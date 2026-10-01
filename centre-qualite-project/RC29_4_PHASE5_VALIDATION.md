# RC29.4 — Phase 5 validation

## Scope
Centre Qualité Live: speed of use. No business KPI formula or signalisation rule changed.

## Implemented
- Quick state chips with counters: Tous, En appel, Disponible, Pause, Post-appel, Non observé.
- `Mise en attente` (`hold`) is intentionally grouped under `En appel`, not under Disponible.
- Alert cards are directly actionable: campaign alerts focus the Campaign scope; agent alerts (or an available contributing agent) focus the Agent roster.
- Layout persistence moved to localStorage (with sessionStorage compatibility).
- Group selection is persisted only after validating the saved group against the current access-scope policy.
- Optional `Mur d’écran` mode hides application navigation/topbar and uses the Fullscreen API when available; exiting fullscreen clears wall mode.
- Existing agent row reconciliation by `agent_id` and row signature remains unchanged.

## Verification
- `node --check static/live-views.js`: PASS.
- RC29.4 Phase 1–5 + RC29.3 Live usability/simple targeted suite: 47 PASS / 0 FAIL.

## Files changed in Phase 5
- `static/live-views.js`
- `static/collection.css`
- `rc29_4_phase5_live_workflow_test.py` (new test)

## Deferred to Phase 6
- Diagnose and fix Campaign `Traités`, `Abandonnés`, `QoS` values showing `—`.
- Reconcile the latest user-requested Centre Qualité Live UI details from the prior `Audit phase 0 RC29` work.
