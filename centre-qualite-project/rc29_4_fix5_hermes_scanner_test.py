from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'


def _redirect(monkeypatch,tmp_path):
    import hermes_diagnostic as hd
    monkeypatch.setattr(hd,'DATA_DIR',tmp_path/'data')
    monkeypatch.setattr(hd,'RUN_DIR',tmp_path/'run')
    monkeypatch.setattr(hd,'REPORT_DIR',tmp_path/'data'/'reports')
    monkeypatch.setattr(hd,'SCHEDULE_FILE',tmp_path/'data'/'schedule.json')
    monkeypatch.setattr(hd,'STATE_FILE',tmp_path/'run'/'state.json')
    monkeypatch.setattr(hd,'LOCK_FILE',tmp_path/'run'/'scan.lock')
    monkeypatch.setattr(hd,'SCHEDULE_STATE_FILE',tmp_path/'run'/'schedule_state.json')
    return hd


def test_scanner_payload_keeps_only_schema_and_function_names():
    import hermes_scan_worker as w
    j=w.analyze_payload('{"agent":"1001","password":"TOPSECRET","nested":{"count":12,"token":"abc"}}')
    dumped=json.dumps(j)
    assert 'TOPSECRET' not in dumped and '"abc"' not in dumped and '12' not in dumped
    assert 'agent' in j['schema_keys'] and 'nested.count' in j['schema_keys']
    assert all('password' not in k and 'token' not in k for k in j['schema_keys'])
    f=w.analyze_payload('UpQuH(1,2,3); UpQuR(4,5); NewHermesCallback(1)')
    assert f['functions']['UpQuH']==1 and f['functions']['UpQuR']==1
    assert 'NewHermesCallback' not in f['functions']


def test_source_path_strips_query_and_only_supervision_host_is_accepted():
    import hermes_scan_worker as w
    assert w._source_key('https://fr06-supervision.vocalcom.com/hermes360/changes.ashx?secret=abc')=='/hermes360/changes.ashx'
    assert w._same_host('https://fr06-supervision.vocalcom.com/hermes360/changes.ashx') is True
    assert w._same_host('https://example.org/hermes360/changes.ashx') is False


def test_schedule_is_off_by_default_and_validated(tmp_path,monkeypatch):
    hd=_redirect(monkeypatch,tmp_path)
    assert hd.schedule()['enabled'] is False
    cfg=hd.save_schedule({'enabled':True,'time':'10:30','active_days':[1,3,5],'duration':60,'open_if_missing':True,'debug_port':9222},'admin')
    assert cfg['enabled'] is True and cfg['active_days']==[1,3,5] and cfg['open_if_missing'] is True
    with pytest.raises(ValueError):hd.save_schedule({'enabled':True,'time':'25:00','active_days':[1],'duration':60,'open_if_missing':False,'debug_port':9222},'admin')
    with pytest.raises(ValueError):hd.save_schedule({'enabled':True,'time':'10:30','active_days':[1],'duration':45,'open_if_missing':False,'debug_port':9222},'admin')


def test_scheduler_runs_once_in_window(tmp_path,monkeypatch):
    hd=_redirect(monkeypatch,tmp_path)
    hd.save_schedule({'enabled':True,'time':'10:30','active_days':[3],'duration':60,'open_if_missing':True,'debug_port':9222},'admin')
    calls=[]
    monkeypatch.setattr(hd,'start_scan',lambda **kw:calls.append(kw) or {'pid':1234})
    from nelyio_time import local_wall_timestamp
    now=local_wall_timestamp('2026-09-30',10,35)  # Wednesday
    first=hd.scheduler_tick(clock=now);second=hd.scheduler_tick(clock=now+60)
    assert first['started'] is True and second['reason']=='already_attempted_today'
    assert calls[0]['scheduled'] is True and calls[0]['open_if_missing'] is True


def test_coverage_lists_missing_upquh_without_inventing_zero(monkeypatch):
    import collection_store
    import hermes_scan_worker as w
    monkeypatch.setattr(collection_store,'live_supervision_snapshot',lambda include_quality=False:{
        'day':'2026-09-30','live_queue_catalog':{'1':'A','2':'B','3':'C'},
        'native_queue_metrics':{'upquh_count':2,'upqur_count':1,'by_line':{'1':{'UpQuH':{'handled_today':10},'UpQuR':{'calls_waiting':1}},'2':{'UpQuH':{'handled_today':4}}}},
        'persistence':{'normalized_events':99},
    })
    c=w._coverage()
    assert c['catalog_lines']==3 and c['upquh_lines']==2 and c['upqur_lines']==1
    assert [x['line_id'] for x in c['missing_upquh']]==['3']
    assert {x['line_id'] for x in c['missing_upqur']}=={'2','3'}


def test_scanner_is_admin_only_passive_and_wired_to_live_worker():
    routes=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'collection.js').read_text(encoding='utf-8')
    worker=(ROOT/'hermes_scan_worker.py').read_text(encoding='utf-8')
    service=(ROOT/'live_service.py').read_text(encoding='utf-8')
    assert "action in {'hermes-scan-status','hermes-scan-start','hermes-scan-stop','hermes-scan-schedule'}" in routes
    assert "user.get('role') != 'admin'" in routes
    assert 'Analyser la supervision Hermes' in js and 'Planification optionnelle' in js and 'Files sans UpQuH' in js
    assert 'Runtime.evaluate' not in worker
    assert 'Network.getResponseBody' in worker and 'raw_bodies_persisted' in worker
    assert 'hermes_diagnostic.scheduler_tick' in service
