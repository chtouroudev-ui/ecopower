from pathlib import Path
import importlib
import json

ROOT=Path(__file__).resolve().parent


def test_dpapi_vault_never_persists_plaintext(monkeypatch,tmp_path):
    import hermes_credentials as hc
    monkeypatch.setattr(hc,'CREDENTIAL_FILE',tmp_path/'hermes_credentials.dpapi')
    monkeypatch.setattr(hc,'GUARD_FILE',tmp_path/'hermes_login_guard.json')
    monkeypatch.setattr(hc,'_protect_windows',lambda b:b'ENC:'+b[::-1])
    monkeypatch.setattr(hc,'_unprotect_windows',lambda b:b[4:][::-1])
    result=hc.save_credentials('TEST.USER','SuperSecret!42',auto_login=True)
    raw=(tmp_path/'hermes_credentials.dpapi').read_text(encoding='utf-8')
    assert 'TEST.USER' not in raw
    assert 'SuperSecret!42' not in raw
    loaded=hc.load_credentials()
    assert loaded['username']=='TEST.USER'
    assert loaded['password']=='SuperSecret!42'
    assert loaded['auto_login'] is True
    assert result['configured'] is True
    assert 'password' not in result and 'username' not in result


def test_login_guard_enforces_cooldown(monkeypatch,tmp_path):
    import hermes_credentials as hc
    monkeypatch.setattr(hc,'GUARD_FILE',tmp_path/'guard.json')
    hc.record_login_failure('bad login',clock=1000)
    state=hc.login_guard_status(clock=1001)
    assert state['blocked'] is True
    assert state['blocked_until']==1000+hc.COOLDOWN_SECONDS
    hc.clear_login_guard()
    assert hc.login_guard_status(clock=1001)['blocked'] is False


def test_cdp_login_uses_dom_input_not_runtime_evaluate():
    text=(ROOT/'hermes_cdp_login.py').read_text(encoding='utf-8')
    assert 'Runtime.evaluate' not in text
    assert 'DOM.querySelector' in text
    assert 'Input.insertText' in text
    assert 'Page.navigate' in text
    assert 'Network.getCookies' not in text
    assert 'Storage.getCookies' not in text


def test_auto_login_reuses_credentials_only_in_memory(monkeypatch):
    import hermes_cdp_login as h
    state={'logged':False,'cleared':False,'failed':False}
    monkeypatch.setattr(h,'login_guard_status',lambda:{'blocked':False})
    monkeypatch.setattr(h,'load_credentials',lambda:{'username':'U','password':'P','auto_login':True})
    def find(port,host):
        if host==h.SUPERVISION_HOST:
            return {'host':host,'url':'https://'+host+'/x','websocket':'ws://127.0.0.1:9222/devtools/page/1'} if state['logged'] else None
        if host==h.LOGIN_HOST:
            return {'host':host,'url':'https://'+host+'/Hermes360/Admin/Launcher/login','websocket':'ws://127.0.0.1:9222/devtools/page/2'}
        return None
    monkeypatch.setattr(h,'_find_target',find)
    monkeypatch.setattr(h,'_login_form',lambda target,u,p: state.update(logged=(u=='U' and p=='P')))
    monkeypatch.setattr(h,'clear_login_guard',lambda:state.update(cleared=True))
    monkeypatch.setattr(h,'record_login_failure',lambda reason:state.update(failed=True))
    result=h.auto_login(9222,wait_seconds=1)
    assert result['ok'] is True
    assert state['cleared'] is True
    assert state['failed'] is False


def test_auto_launcher_is_rate_limited(monkeypatch,tmp_path):
    import hermes_supervision_launcher as l
    monkeypatch.setattr(l,'AUTO_GUARD',tmp_path/'guard.json')
    monkeypatch.setattr(l,'credential_status',lambda check_decrypt=False:{'configured':True,'auto_login':True,'cooldown_active':False})
    calls=[]
    monkeypatch.setattr(l,'launch_supervision',lambda port:(calls.append(port) or {'started':True,'pid':123,'port':port,'auto_login':True}))
    first=l.maybe_launch_for_auto(9222,clock=1000)
    second=l.maybe_launch_for_auto(9222,clock=1001)
    assert first['started'] is True
    assert second['started'] is False and second['reason']=='launch_rate_limited'
    assert calls==[9222]


def test_routes_and_ui_keep_secret_admin_only_and_local():
    routes=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'collection.js').read_text(encoding='utf-8')
    assert "action in {'hermes-credentials-status','hermes-credentials','hermes-credentials-delete','hermes-auto-login'}" in routes
    assert "user.get('role') != 'admin'" in routes
    assert "self.client_ip() not in {'127.0.0.1','::1'}" in routes
    assert 'secret=never_logged' in routes
    assert 'hermes-password' in js and 'type="password"' in js
    assert 'Windows DPAPI' in js
    assert "currentUser?.role==='admin'" in js


def test_live_worker_only_auto_opens_for_active_waiting_browser():
    text=(ROOT/'live_service.py').read_text(encoding='utf-8')
    assert "brief.get('active') and brief.get('connection_state') in {'waiting_browser','connecting'}" in text
    assert 'maybe_launch_for_auto' in text
