from pathlib import Path
import json

import production_observability as obs
from tools import soak_test

ROOT = Path(__file__).resolve().parent


def test_phase10_requests_removed_from_runtime_surface():
    requirements=(ROOT/'requirements.txt').read_text(encoding='utf-8')
    capture=(ROOT/'capture'/'Capture_NELYIO.py').read_text(encoding='utf-8')
    preflight=(ROOT/'preflight.py').read_text(encoding='utf-8')
    project=(ROOT/'OUTILS_PROJET.ps1').read_text(encoding='utf-8')
    assert 'requests==' not in requirements
    assert 'import requests' not in capture and 'from requests' not in capture
    assert 'urllib.request.urlopen' in capture
    assert "('reportlab','websockets')" in preflight
    assert 'Aucune dependance requests requise' in preflight
    assert 'import requests' not in project


def test_phase10_thresholds_are_configurable_and_bounded(monkeypatch):
    monkeypatch.setenv('NELYIO_HTTP_SLOW_SECONDS','0.01')
    monkeypatch.setenv('NELYIO_ANALYTICS_SLOW_SECONDS','999')
    monkeypatch.setenv('NELYIO_OBS_SLOW_EVENTS_PER_HOUR','0')
    monkeypatch.setenv('NELYIO_OBS_CRITICAL_SLOW_EVENTS_PER_HOUR','99999')
    monkeypatch.setenv('NELYIO_OBS_CRITICAL_SLOW_SECONDS','7.5')
    t=obs._performance_thresholds()
    assert t['http_log_seconds']==0.1
    assert t['analytics_log_seconds']==120.0
    assert t['warn_events_per_hour']==1
    assert t['critical_events_per_hour']==10000
    assert t['critical_seconds']==7.5


def test_phase10_observability_uses_warn_and_critical_thresholds():
    services={'all_healthy':True};postgres={'ok':True};live={'active':False,'fresh':False}
    thresholds={'warn_events_per_hour':5,'critical_events_per_hour':20,'critical_seconds':10.0}
    perf={'http':{'last_hour':5,'max_last_hour_seconds':2.0},'analytics':{'last_hour':0,'max_last_hour_seconds':0.0}}
    out=obs._overall(services,postgres,live,perf,thresholds)
    assert out['status']=='A_SURVEILLER' and out['reasons']==['http_slow']
    perf['http']={'last_hour':1,'max_last_hour_seconds':12.0}
    out=obs._overall(services,postgres,live,perf,thresholds)
    assert out['status']=='DEGRADE' and 'http_slow' in out['reasons']


def test_phase10_soak_summary_never_hides_errors():
    rows=[
        {'scenario':'live','status':200,'seconds':0.4,'error':''},
        {'scenario':'live','status':200,'seconds':0.8,'error':''},
        {'scenario':'quality','status':500,'seconds':0.2,'error':'boom'},
    ]
    out=soak_test.summarize(rows)
    assert out['requests']==3 and out['success']==2 and out['errors']==1
    assert out['median_s']==0.6 and out['p95_s']==0.8
    assert out['by_scenario']['live']['count']==2


def test_phase10_soak_status_is_bounded_technical_metadata(tmp_path, monkeypatch):
    logs=tmp_path/'logs';logs.mkdir()
    (logs/'soak_test_production.json').write_text(json.dumps({
        'status':'PASS','generated_at':'2026-09-27T17:00:00+00:00','virtual_users':5,
        'duration_seconds':300,'summary':{'requests':750,'errors':0,'median_s':0.2,'p95_s':0.6,'max_s':1.3},
        'records':[{'url':'should-not-be-exposed'}]
    }),encoding='utf-8')
    monkeypatch.setattr(obs,'LOGS',logs)
    out=obs._soak_status()
    assert out=={'available':True,'status':'PASS','generated_at':'2026-09-27T17:00:00+00:00','virtual_users':5,'duration_seconds':300.0,'requests':750,'errors':0,'median_s':0.2,'p95_s':0.6,'max_s':1.3}


def test_phase10_ui_exposes_thresholds_and_soak_without_business_ids():
    js=(ROOT/'static'/'production-health.js').read_text(encoding='utf-8')
    index=(ROOT/'index.html').read_text(encoding='utf-8')
    assert 'Seuils de surveillance' in js
    assert 'Charge prolongée' in js
    assert 'TEST_CHARGE_PROLONGEE.bat' in js
    assert '/static/production-health.js' in index
    assert 'ANI' not in js and 'DNIS' not in js
