"""Isolated regression tests; never uses production PostgreSQL."""
import os
os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'
import json, subprocess, sys, time
from unittest.mock import patch, Mock
import pytest
from audit_regression_test import lab, seed, inbound_row, SCOPE

def test_process_probe_preserves_running_child():
    import process_lock as p
    child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
    try:
        for _ in range(10): assert p._alive(child.pid)
        assert child.poll() is None
    finally: child.terminate();child.wait(timeout=5)
    assert not p._alive(child.pid)

def test_windows_branch_never_sends_signal():
    import process_lock as p
    with patch.object(p.os,'name','nt'), patch.object(p,'_windows_alive',return_value=True) as probe, patch.object(p.os,'kill',side_effect=AssertionError('signal forbidden')):
        assert p._alive(234)
        probe.assert_called_once_with(234)

def test_permission_denied_preserves_lock_owner():
    import process_lock as p
    with patch.object(p.os,'name','posix'), patch.object(p.os,'kill',side_effect=PermissionError): assert p._alive(234)

def test_lock_contention_and_release(tmp_path,monkeypatch):
    import process_lock as p
    monkeypatch.setattr(p,'RUN',tmp_path)
    with p.named_lock('test'):
        with pytest.raises(p.LockBusy):
            with p.named_lock('test'): pass
    with p.named_lock('test'): pass
    assert not list(tmp_path.glob('*.lock'))

def test_scope_index_rebuilds_after_scope_replacement():
    import analysis_groups as a
    scope={'groups':[{'id':'1','member_agent_ids':['S1001']}]}
    with patch.object(a,'load_quality_file_scope',return_value=scope):
        first=a.membership_map()
        assert a.membership_map() is first
        assert a.matches_agent_groups('1001',['1'])
    with patch.object(a,'load_quality_file_scope',return_value={'groups':[{'id':'2','member_agent_ids':['1001']}]}):
        assert a.matches_agent_groups('S1001',['2'])
        assert not a.matches_agent_groups('1001',['1'])

def test_row_filter_resolves_once_and_never_falls_back_to_admin():
    import analysis_groups as a
    import unified_filters as f
    rows=[{'agent':'1001','group_id':99},{'agent':'1002','group_id':99}]*500
    with patch.object(a,'selected_group_members',return_value={'1001'}) as resolve:
        assert len(f.apply_row_scope(rows,{'groups':['99']}))==500
        resolve.assert_called_once()
    with patch.object(a,'selected_group_members',side_effect=RuntimeError('scope unavailable')):
        with pytest.raises(RuntimeError): f.apply_row_scope(rows,{'groups':['99']})

def test_details_batch_idempotent_and_links(lab):
    import details_store as d
    d.init()
    event={'event_uid':'test:1','event_source':'export','source_label':'SIMPLIFY2','start':1,'end':3,'raw':{'name':'Example'}}
    links=[{'agent_key':'1001','agent':'S1001'},{'agent_key':'1002','agent':'1002'}]
    with d.connect_details() as c:
        assert d._insert_events(c,[(event,links)])==1
        assert d._insert_events(c,[(event,links)])==0
        assert c.execute('SELECT COUNT(*) FROM detail_events').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM detail_event_agents').fetchone()[0]==2
        assert json.loads(c.execute('SELECT raw_json FROM detail_events').fetchone()[0])==event['raw']

def test_details_failure_preserves_root_error_and_rolls_back(lab):
    import details_store as d
    import sqlite3
    def fail(dst,admin):
        dst.execute("INSERT INTO sync_state(key,value,updated_at) VALUES('partial','no','now')")
        raise sqlite3.OperationalError('original SQL cause')
    with patch.object(d,'_refresh_directory_projection',side_effect=fail):
        with pytest.raises(sqlite3.OperationalError,match='original SQL cause'):
            d.sync_from_sources(lab/'NELYIO_Supervision.db',lab/'TECHIN_Stock_Manager.db',force=True)
    with d.connect_details() as c:
        assert c.execute("SELECT COUNT(*) FROM sync_state WHERE key='partial'").fetchone()[0]==0
        row=c.execute('SELECT status,error FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone()
        assert tuple(row)==('ERROR','original SQL cause')

def test_health_is_available_when_heartbeat_store_fails(monkeypatch):
    import production_http as p
    import service_state
    h=p.Handler.__new__(p.Handler);h.path='/healthz';h.server=Mock(server_port=9051);h.send_json=lambda value:value
    monkeypatch.setenv('NELYIO_EXTERNAL_SERVICES','1')
    with patch.object(service_state,'beat',side_effect=AssertionError('disk access')), patch.object(service_state,'public_status',side_effect=AssertionError('disk access')): data=h._get()
    assert data['ok'] and data['architecture']=='services'

def test_stale_service_health_is_not_green():
    import production_http as p
    with patch.dict(p._HEALTH_STATE, {'services_ok':True,'services':{'web':True},'checked_at':time.monotonic()-20},clear=True): assert not p.cached_service_health()['services_ok']

def test_group_agent_campaign_hour_consistency_between_views(lab):
    import quality_metrics as m
    import quality_distributions as d
    import quality_scope
    seed([inbound_row('09:00:00','1001','A'),inbound_row('10:00:00','1002','B'),inbound_row('11:00:00','0','A',abandoned=1),inbound_row('12:00:00','1003','A')])
    scope={'groups':[{'id':'1','name':'G1','line_ids':[1],'file_count':1,'campaign_ids':['A'],'member_agent_ids':['1001','1002'],'member_count':2}], 'campaign_to_files':{}}
    with patch.object(quality_scope,'load_quality_file_scope',return_value=scope):
        for filters,received,treated in [({'group':['1']},3,2),({'group':['1'],'agent':['S1002']},1,1),({'group':['1'],'campaign':['A']},2,1),({'group':['1'],'time_from':['10:00'],'time_to':['11:00']},1,1)]:
            query=dict(SCOPE,**filters)
            overview=m.overview(query);distribution=d.view(query)
            assert overview['total']['received']==distribution['total']['received']==received
            assert overview['total']['treated_agent']==distribution['total']['treated']==treated
            assert sum(r['received'] for r in distribution['hourly'])==received

def test_http_five_concurrent_clients_without_disk_health_access(monkeypatch):
    import threading, urllib.request
    from concurrent.futures import ThreadPoolExecutor
    import production_http as p
    import service_state
    monkeypatch.setenv('NELYIO_EXTERNAL_SERVICES','1')
    server=p.ProductionHTTPServer(('127.0.0.1',0),p.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        def get(_):
            with urllib.request.urlopen(f'http://127.0.0.1:{server.server_port}/healthz',timeout=3) as r:
                return r.status,json.load(r)
        with patch.object(service_state,'beat',side_effect=AssertionError('disk access')),patch.object(service_state,'public_status',side_effect=AssertionError('disk access')):
            with ThreadPoolExecutor(max_workers=5) as pool: results=list(pool.map(get,range(25)))
        assert all(status==200 and data['ok'] for status,data in results)
    finally: server.shutdown();server.server_close();thread.join(timeout=3)
