from pathlib import Path

ROOT=Path(__file__).resolve().parent
PS=(ROOT/'OPEN_HERMES_SUPERVISION.ps1').read_text(encoding='utf-8-sig')
JS=(ROOT/'static'/'collection.js').read_text(encoding='utf-8')
ROUTES=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
LAUNCH=(ROOT/'hermes_supervision_launcher.py').read_text(encoding='utf-8')
WORKER=(ROOT/'hermes_supervision_worker.py').read_text(encoding='utf-8')
CDP=(ROOT/'hermes_cdp_login.py').read_text(encoding='utf-8')


def test_safe_supervision_launcher_does_not_kill_browser_or_inject_page_js():
    lowered=PS.lower()
    assert 'runtime.evaluate' not in lowered
    assert 'stop-process' in lowered
    assert 'Get-NelyioEdgeProcesses' in PS
    assert "Name='msedge.exe'" in PS
    assert '$needleProfile' in PS
    assert 'Aucun processus tiers ne sera modifie' in PS
    assert '$password' not in lowered
    assert '$username' not in lowered
    assert 'remote-debugging-address=127.0.0.1' in PS
    assert "TECH-IN\\Nelyio\\CaptureBrowser" in PS
    assert 'Runtime.evaluate' not in CDP
    assert 'DOM.querySelector' in CDP and 'Input.insertText' in CDP


def test_open_supervision_and_secret_config_are_admin_only():
    assert "action == 'open-supervision'" in ROUTES
    assert "user.get('role') != 'admin'" in ROUTES
    assert 'HERMES_SUPERVISION_OPEN_REQUEST' in ROUTES
    assert 'HERMES_CREDENTIALS_SAVED' in ROUTES
    assert "self.client_ip() not in {'127.0.0.1','::1'}" in ROUTES
    assert "currentUser?.role==='admin'" in JS
    assert 'collection-open-supervision' in JS


def test_python_launcher_uses_short_lived_worker_not_shell():
    assert 'shell=False' in LAUNCH
    assert 'stdin=subprocess.DEVNULL' in LAUNCH
    assert 'hermes_supervision_worker.py' in LAUNCH
    assert 'OPEN_HERMES_SUPERVISION.ps1' in WORKER
    assert 'shell=False' in WORKER
