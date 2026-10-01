# RC29.4 — Phase 4 validation

## Scope
Centre Qualité Live: readability and vital information only. No KPI formula, perimeter, signalisation rule, or campaign data source changed.

## Implemented
- Desktop Live rail expanded to 220–240 px (>=200 px), with a 128 px collapsed state.
- Rail collapse is persisted in browser localStorage (`nelyio.live.railCollapsed`).
- Global Quality status, active alert count and Hermes freshness are always in the primary rail (no Details click required).
- Hermes freshness text is also visible in the top cockpit toolbar; the previous desktop CSS hiding it is overridden.
- Operational table text and secondary operational text are forced to >=12 px in the final Phase 4 overrides.
- Agent states keep their text and color and now add a distinct symbol/shape for call, hold, ready, pause, wrap, offline, unobserved, arrival, inactive_context and other.
- Desktop workstation uses one vertical scrolling region for Agents and one for Scopes/Campaigns; page/panel overflow is constrained.
- Agent and scope table headers are sticky inside their own operational scroll regions.

## Invariants preserved
- QoS and every other business KPI unchanged.
- Unknown remains distinct from zero.
- Agent rows still reconcile by `agent_id`; no full DOM rebuild was introduced.
- Existing 3-state sorting logic unchanged.
- Permissions and group access scope unchanged.

## Verification
- `node --check static/live-views.js`: PASS.
- RC29.4 Phase 1–4 + RC29.3 Live usability/simple targeted suite: 42 PASS / 0 FAIL.
- A supplementary Chromium file-harness run was attempted for computed layout metrics but the headless Chromium process did not complete in the container time limit; no visual metric from that attempt is claimed.

## Files changed in Phase 4
- `static/live-views.js`
- `static/collection.css`
- `rc29_4_phase4_live_readability_test.py` (new test)
