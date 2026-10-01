from pathlib import Path

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static'/'collection.js').read_text(encoding='utf-8')
ROUTES=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
DIAG=(ROOT/'hermes_diagnostic.py').read_text(encoding='utf-8')
WORKER=(ROOT/'hermes_scan_worker.py').read_text(encoding='utf-8')
LAUNCH=(ROOT/'hermes_supervision_launcher.py').read_text(encoding='utf-8')
PS=(ROOT/'OPEN_HERMES_SUPERVISION.ps1').read_text(encoding='utf-8-sig')


def test_fix51_ui_uses_stable_admin_delegation_and_visible_states():
    assert 'collectionBindHermesAdminEvents' in JS
    assert "b.id==='collection-open-supervision'" in JS
    assert "b.id==='hermes-scan-start'" in JS
    assert "b.id==='hermes-scan-stop'" in JS
    assert "b.id==='hermes-scan-save'" in JS
    for label in ['PRÉPARATION','VÉRIFICATION EDGE','OUVERTURE EDGE','ATTENTE HERMES','ANALYSE EN COURS','ERREUR']:
        assert label in JS
    assert '/api/collection/hermes-supervision-status' in JS


def test_fix51_backend_exposes_browser_state_and_scan_stages():
    assert "action == 'hermes-supervision-status'" in ROUTES
    assert 'ACTIVE_STATUSES' in DIAG
    assert '_scanner_dependency_ready' in DIAG
    assert '_supervision_target_present' in DIAG
    assert 'status="opening_browser"' in WORKER
    assert 'status="waiting_browser"' in WORKER
    assert 'status="running"' in WORKER
    assert 'hermes_supervision_state.json' in LAUNCH


def test_fix51_edge_restart_is_limited_to_dedicated_profile():
    assert 'Get-NelyioEdgeProcesses' in PS
    assert "Name='msedge.exe'" in PS
    assert '$needleProfile' in PS
    assert 'Stop-StaleNelyioEdge' in PS
    assert 'Aucun processus tiers ne sera modifie' in PS
    assert 'remote-debugging-port=$Port' in PS
    assert 'Wait-Cdp' in PS and 'Wait-HermesTarget' in PS
