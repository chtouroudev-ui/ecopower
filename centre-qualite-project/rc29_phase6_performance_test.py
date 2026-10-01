import json
import os
import time
from unittest.mock import patch

os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'


def test_perf_trace_breakdown_and_size(tmp_path, monkeypatch):
    import perf_trace
    monkeypatch.setenv('NELYIO_PERF_TRACE','1')
    tok=perf_trace.begin('http',service='web',endpoint='/api/test')
    try:
        perf_trace.add_auth(0.001)
        perf_trace.add_worker(0.002)
        perf_trace.add_compute(0.003)
        perf_trace.add_json(0.004)
        perf_trace.add_response_bytes(1234)
        snap=perf_trace.snapshot()
        assert snap['auth_ms'] >= 1
        assert snap['worker_ms'] >= 2
        assert snap['compute_ms'] >= 3
        assert snap['json_ms'] >= 4
        assert snap['response_bytes'] == 1234
        assert snap['python_other_ms'] >= 0
    finally:
        perf_trace.reset(tok)


def test_analytics_compute_is_recorded(monkeypatch):
    import analytics_service, perf_trace
    analytics_service._CACHE.clear()
    monkeypatch.setattr(analytics_service,'_revision_for',lambda kind:'r1')
    monkeypatch.setattr(analytics_service,'_run_query',lambda kind,q: (time.sleep(0.01) or ({'ok':True},30.0)))
    captured=[]
    original_finish=perf_trace.finish
    monkeypatch.setattr(perf_trace,'finish',lambda **kw: captured.append(perf_trace.snapshot(kw.get('extra'))) or captured[-1])
    try:
        payload,hit=analytics_service._analyze('quality_overview',{'x':['1']})
    finally:
        monkeypatch.setattr(perf_trace,'finish',original_finish)
    assert not hit
    assert json.loads(payload)['ok'] is True
    assert captured and captured[-1]['compute_ms'] >= 8
    assert captured[-1]['response_bytes'] == 0  # worker payload size is carried as extra, HTTP layer owns response bytes


def test_session_touch_throttling_contract_source():
    import inspect, http_handler
    src=inspect.getsource(http_handler.Handler.session_user)
    assert 'NELYIO_SESSION_TOUCH_SECONDS' in src
    assert '(now - last_seen).total_seconds() >= refresh_seconds' in src
    assert 'UPDATE sessions SET last_seen_at' in src



def _session_probe(last_seen_text, monkeypatch):
    import http_handler
    from contextlib import contextmanager
    from datetime import datetime, timedelta

    now=datetime.now()
    row={
        'id':1,'username':'bench','role':'technician','active':1,
        'expires_at':(now+timedelta(hours=1)).isoformat(timespec='seconds'),
        'csrf_token':'csrf','last_seen_at':last_seen_text,
    }
    class Cursor:
        def __init__(self, value=None): self.value=value
        def fetchone(self): return self.value
    class Con:
        def __init__(self): self.updates=0; self.commits=0
        def execute(self, sql, params=()):
            if 'SELECT u.id' in sql: return Cursor(row)
            if 'UPDATE sessions SET last_seen_at' in sql: self.updates+=1
            return Cursor(None)
        def commit(self): self.commits+=1
    con=Con()
    @contextmanager
    def fake_db(): yield con
    h=http_handler.Handler.__new__(http_handler.Handler)
    h.headers={'Cookie':f'{http_handler.SESSION_COOKIE}=token'}
    monkeypatch.setattr(http_handler,'db_connect',fake_db)
    monkeypatch.setattr(http_handler,'access_profile',lambda con,user_id,role:{})
    return h,con


def test_session_touch_skips_fresh_polling_write(monkeypatch):
    from datetime import datetime
    h,con=_session_probe(datetime.now().isoformat(timespec='seconds'),monkeypatch)
    monkeypatch.setenv('NELYIO_SESSION_TOUCH_SECONDS','60')
    assert h.session_user()['username']=='bench'
    assert con.updates==0 and con.commits==0


def test_session_touch_persists_stale_activity(monkeypatch):
    from datetime import datetime, timedelta
    h,con=_session_probe((datetime.now()-timedelta(minutes=2)).isoformat(timespec='seconds'),monkeypatch)
    monkeypatch.setenv('NELYIO_SESSION_TOUCH_SECONDS','60')
    assert h.session_user()['username']=='bench'
    assert con.updates==1 and con.commits==1

def test_five_concurrent_http_clients_existing_contract(monkeypatch):
    # Reuse the existing production stability proof: 5 simultaneous clients on the threaded HTTP server.
    import production_stability_test as pst
    pst.test_http_five_concurrent_clients_without_disk_health_access(monkeypatch)
