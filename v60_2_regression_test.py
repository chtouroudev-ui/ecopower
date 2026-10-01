import time
from unittest.mock import patch

from audit_regression_test import lab, archive


def _agent_row(duration='3600'):
    return dict(AgentId='1001',ActionDate='2026-09-18 09:00:00',ActionDuration=duration,
                ActionName='Pret',IsSubAction='0',IsSubPart='0')


def test_staged_import_keeps_previous_reference_on_critical_quality_failure(lab, monkeypatch):
    from export_import import import_export
    from supervision_db import connect, init
    import quality_agents
    first=archive('Stats.AGENT',[_agent_row('3600')])
    ok=import_export(first,'SIMPLIFY2.2026-09-18.export.zip',120,'audit')
    assert ok['status']=='completed'
    with connect() as c:
        previous=c.execute("SELECT import_id FROM coverage WHERE day='2026-09-18'").fetchone()[0]
    second=archive('Stats.AGENT',[_agent_row('5400')])
    monkeypatch.setattr(quality_agents,'ingest',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('quality busy')))
    result=import_export(second,'SIMPLIFY2.2026-09-18.v2.export.zip',120,'audit')
    assert result['status']=='partial'
    assert result['snapshot_commit']['activated'] is False
    with connect() as c:
        assert c.execute("SELECT import_id FROM coverage WHERE day='2026-09-18'").fetchone()[0]==previous
        staged=c.execute("SELECT state FROM import_reference_states WHERE import_id=?",(result['import_id'],)).fetchone()[0]
        assert staged=='staged'
    # A normal schema/init repair must not accidentally expose the staged import.
    init()
    with connect() as c:
        assert c.execute("SELECT import_id FROM coverage WHERE day='2026-09-18'").fetchone()[0]==previous


def test_details_failure_does_not_block_atomic_main_snapshot(lab, monkeypatch):
    from export_import import import_export
    from supervision_db import connect
    import details_store
    first=archive('Stats.AGENT',[_agent_row('3600')])
    ok=import_export(first,'SIMPLIFY2.2026-09-18.export.zip',120,'audit')
    assert ok['status']=='completed'
    with connect() as c:
        previous=c.execute("SELECT import_id FROM coverage WHERE day='2026-09-18'").fetchone()[0]
    second=archive('Stats.AGENT',[_agent_row('5400')])
    monkeypatch.setattr(details_store,'sync_from_sources',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('details busy')))
    result=import_export(second,'SIMPLIFY2.2026-09-18.v2.export.zip',120,'audit')
    assert result['status']=='partial'
    assert result['snapshot_commit']['activated'] is True
    assert result['details_sync']['ok'] is False
    with connect() as c:
        current=c.execute("SELECT import_id FROM coverage WHERE day='2026-09-18'").fetchone()[0]
        assert current!=previous and current==result['import_id']


def test_live_snapshot_reads_dedicated_database(lab, monkeypatch):
    import collection_store as store
    path=lab/'Nelyio_Live_v602.db'
    monkeypatch.setattr(store,'db_path',lambda:path)
    store._SCHEMA_IDENTITIES.clear();store.init()
    now=time.time();day=store.local_day(now)
    settings=dict(day=day,start_ts=now-60,end_ts=now+3600,start_time='00:00',end_time='23:59')
    sid=store.create_session(settings,'audit',clock=now)
    decoded=dict(valid=True,recognized=2,rejected=0,events=[
        dict(type='agent',entity='1001',payload={'agent':'1001','first_name':'Test','last_name':'Agent','state':'Pret'}),
        dict(type='queue',entity='7111',payload={'name':'File Test'}),
        dict(type='call_observation',entity='1001',payload={'agent':'1001','line_id':'7111','line_name':'File Test','phone':'0123456789','state':'call'}),
    ])
    store.record_response(sid,'capture',now,'r1','digest',decoded)
    snap=store.live_snapshot(day=day)
    assert snap['count']>=3
    assert snap['calls']==1
    assert snap['catalog']['agent']==1 and snap['catalog']['queue']==1
    assert any(r['phone']=='0123456789' for r in snap['rows'])


def test_quality_agents_keeps_short_calls_out_and_lazy_distribution(lab):
    from audit_regression_test import inbound_row, seed, SCOPE
    from supervision_db import connect
    from quality_agents import view
    rows=[inbound_row('09:00:00',agent='S1001',answered=1),
          inbound_row('09:05:00',agent='S1001',answered=1),
          inbound_row('09:10:00',agent='S1001',answered=1)]
    rows[0]['CallDuration']='9'
    rows[1]['CallDuration']='10'
    rows[2]['CallDuration']='4.5'
    seed(rows)
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO coverage(day,import_id) VALUES(?,?)',('2026-09-18',1))
    result=view(SCOPE)
    assert result['calls_compatible'] is True
    assert result['summary']['handled']==3
    assert 'short_calls' not in result['summary']
    row=next(r for r in result['rows'] if r['agent']=='1001')
    assert 'short_calls' not in row
    assert row['distribution_loaded'] is False
    detailed=view(dict(SCOPE,agent=['1001'],include_distribution=['1']))
    detail=next(r for r in detailed['rows'] if r['agent']=='1001')
    assert 'short_calls' not in detail
    assert detail['distribution_loaded'] is True
