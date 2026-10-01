from datetime import datetime
from pathlib import Path

import production_observability as p

ROOT = Path(__file__).resolve().parent


def test_phase9_nav_route_and_read_only_api():
    index=(ROOT/'index.html').read_text(encoding='utf-8')
    app=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    handler=(ROOT/'http_handler.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'production-health.js').read_text(encoding='utf-8')
    assert '#production-health' in index
    assert 'Santé de production' in index
    assert "h==='#production-health'" in app
    assert '/api/production/observability' in handler
    assert 'require_access(user, "config")' in handler
    assert "api('/api/production/observability')" in js
    assert 'method:' not in js


def test_phase9_slow_log_summary_is_bounded_and_aggregated(tmp_path):
    log=tmp_path/'http_slow.log'
    log.write_text(
        '2026-09-27 16:00:00 GET /api/quality/pilotage 1.250s\n'
        '2026-09-27 16:01:00 GET /api/quality/pilotage 2.500s\n'
        '2026-09-27 16:02:00 GET /api/live/campaigns 1.100s\n',
        encoding='utf-8')
    out=p._slow_summary(log,p._HTTP_SLOW,key_name='path',now=datetime(2026,9,27,16,10,0))
    assert out['last_hour']==3
    assert out['last_24h']==3
    assert out['max_24h_seconds']==2.5
    assert out['top_24h'][0]=={'key':'/api/quality/pilotage','count':2,'max_seconds':2.5}
    assert all('?' not in row['key'] for row in out['recent'])


def test_phase9_overall_does_not_call_inactive_live_a_failure():
    services={'all_healthy':True}
    postgres={'ok':True}
    live={'active':False,'fresh':False}
    performance={'http':{'last_hour':0},'analytics':{'last_hour':0}}
    assert p._overall(services,postgres,live,performance)=={'status':'OK','reasons':[]}
    live={'active':True,'fresh':False}
    out=p._overall(services,postgres,live,performance)
    assert out['status']=='A_SURVEILLER' and 'live_stale' in out['reasons']


def test_phase9_privacy_contract_and_limitations(monkeypatch):
    p._CACHE['value']=None;p._CACHE['at']=0
    monkeypatch.setattr(p,'_service_status',lambda:{'all_healthy':True,'services':[],'required':['web','live','analytics']})
    monkeypatch.setattr(p,'_postgres_status',lambda:{'engine':'postgresql','ok':True,'latency_ms':1.2,'reason':''})
    monkeypatch.setattr(p,'_live_status',lambda:{'available':True,'active':False,'fresh':False,'pending':0})
    monkeypatch.setattr(p,'_session_status',lambda:{'available':True,'valid_sessions':2,'seen_last_10m':1})
    monkeypatch.setattr(p,'_import_status',lambda:{'available':True,'mode':'manual-v60','manual_importer':True,'pending_count':0,'active_count':0,'retry_due_count':0,'message':''})
    monkeypatch.setattr(p,'_acceptance_status',lambda:{'available':False,'status':'NON_EXECUTEE'})
    monkeypatch.setattr(p,'_slow_summary',lambda *a,**k:{'available':False,'last_hour':0,'last_24h':0,'max_24h_seconds':0.0,'top_24h':[],'recent':[]})
    out=p.snapshot()
    assert out['privacy']=={'business_identifiers':False,'query_strings':False,'credentials':False,'read_only':True}
    assert out['overall']['status']=='OK'
    assert any('LAN' in x for x in out['limitations'])


def test_phase9_snapshot_is_shared_for_concurrent_admin_tabs(monkeypatch):
    p._CACHE['value']=None;p._CACHE['at']=0
    calls={'services':0}
    def services():
        calls['services']+=1
        return {'all_healthy':True,'services':[],'required':['web','live','analytics']}
    monkeypatch.setattr(p,'_service_status',services)
    monkeypatch.setattr(p,'_postgres_status',lambda:{'engine':'postgresql','ok':True,'latency_ms':1,'reason':''})
    monkeypatch.setattr(p,'_live_status',lambda:{'available':True,'active':False,'fresh':False,'pending':0})
    monkeypatch.setattr(p,'_session_status',lambda:{'available':True,'valid_sessions':0,'seen_last_10m':0})
    monkeypatch.setattr(p,'_import_status',lambda:{'available':True,'mode':'manual-v60','manual_importer':True,'pending_count':0,'active_count':None,'retry_due_count':None,'message':''})
    monkeypatch.setattr(p,'_acceptance_status',lambda:{'available':False,'status':'NON_EXECUTEE'})
    monkeypatch.setattr(p,'_slow_summary',lambda *a,**k:{'available':False,'last_hour':0,'last_24h':0,'max_24h_seconds':0.0,'top_24h':[],'recent':[]})
    first=p.snapshot();second=p.snapshot()
    assert first is second
    assert calls['services']==1


def test_phase9_frontend_single_refresh_loop_and_french_labels():
    js=(ROOT/'static'/'production-health.js').read_text(encoding='utf-8')
    assert 'refreshTimer' in js and 'clearTimeout(refreshTimer)' in js
    assert 'Requêtes Web lentes' in js
    assert 'Calculs Analytics lents' in js
    assert 'Donnée fraîche' in js
    assert 'Post-appel' not in js  # unrelated Live business state is not duplicated here
