import json
from audit_regression_test import lab, SCOPE


def test_calls_sql_filter_preserves_counts(lab):
    from supervision_db import connect
    from nelyio_time import day_bounds
    from calls import calls_view
    lo,_=day_bounds('2026-09-18')
    with connect() as c:
        c.execute("INSERT INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(1,'d','x','now','t',0,120,'2026-09-18')")
        c.execute("INSERT INTO call_coverage(day,import_id) VALUES('2026-09-18',1)")
        c.execute("INSERT INTO call_imports(import_id,rows_count) VALUES(1,3)")
        rows=[
          (1,'c1','I1',lo+9*3600,'IN',30,8,2,'111','7111','','','1001','1001','A','0',0,0,0,1),
          (1,'c2','I2',lo+10*3600,'IN',60,30,3,'222','7111','','','1002','1002','B','42',0,0,0,1),
          (1,'c3','I3',lo+11*3600,'OUT',20,-1,1,'333','7111','','','1003','1003','A','0',0,0,0,1),
        ]
        c.executemany('INSERT INTO phone_calls VALUES('+','.join('?'*20)+')',rows)
    q=dict(SCOPE,indice=['I2'])
    out=calls_view(q)
    assert out['count']==1 and out['rows'][0]['call_id']=='c2'
    out=calls_view(dict(SCOPE,call_issue=['short']))
    assert out['count']==1 and out['rows'][0]['call_id']=='c1'
    out=calls_view(dict(SCOPE,campaign=['A']))
    assert out['count']==2


def test_calls_pagination_reads_authoritative_days_in_global_time_order(lab):
    from supervision_db import connect
    from nelyio_time import day_bounds
    from calls import calls_view
    days=['2026-09-17','2026-09-18']
    with connect() as c:
        for import_id,day in enumerate(days,1):
            lo,_=day_bounds(day,'09:00','19:00')
            c.execute("INSERT INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(?,?,?,?,?,?,?,?)",
                      (import_id,'d'+str(import_id),'x','now','t',0,120,day))
            c.execute('INSERT INTO call_coverage(day,import_id) VALUES(?,?)',(day,import_id))
            c.execute('INSERT INTO call_imports(import_id,rows_count) VALUES(?,?)',(import_id,75))
            rows=[]
            for j in range(75):
                rows.append((import_id,f'c{import_id}-{j}',f'I{import_id}-{j}',lo+j,'IN',30,20,2,'111','7111','','','1001','1001','A','0',0,0,0,1))
            c.executemany('INSERT INTO phone_calls VALUES('+','.join('?'*20)+')',rows)
    scope={'date_from':[days[0]],'date_to':[days[1]],'time_from':['00:00'],'time_to':['23:59']}
    first=calls_view(scope)
    second=calls_view(dict(scope,page=['1']))
    assert first['count']==150 and len(first['rows'])==100 and len(second['rows'])==50
    # Page 1 starts after all 75 rows of the newest day and the 25 newest rows
    # of the previous day.  No duplicate may cross the page boundary.
    ids1={r['call_id'] for r in first['rows']};ids2={r['call_id'] for r in second['rows']}
    assert ids1.isdisjoint(ids2)
    assert first['rows'][0]['start']>first['rows'][-1]['start']>second['rows'][-1]['start']


def test_group_status_is_lightweight_and_revisioned(lab):
    import app_config, group_workspace, quality_scope, quality_service
    from app_db import db_connect
    raw={
      'source_type':'imported','source_day':'2026-09-18',
      'campaigns':[],
      'queues':[{'line_id':7111,'line_name':'File A','campaign_ids':[]}],
      'agents':[{'agent_id':'1001','queues':[{'line_id':7111,'line_name':'File A','activation_state':'active'}]}],
      'observations':[],
      'scope_sources':{'agent_queues':{'day':'2026-09-18'}},
    }
    (lab/'data'/'quality_priorities.json').write_text(json.dumps(raw),encoding='utf8')
    with db_connect() as c:
        gid=c.execute("INSERT INTO user_groups(name,description,created_by,updated_by) VALUES('G1','','t','t')").lastrowid
        c.execute('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)',(gid,7111,'t'))
    quality_scope.invalidate_quality_scope_cache(touch_revision=False);quality_service.invalidate_quality_priorities_cache();group_workspace.invalidate_group_workspace_cache()
    a=group_workspace.status()
    assert a['stats']['agents']==1 and a['group_summary']['scoped_agents']==1
    assert a['refresh_token'] and a['group_summary']['source_day']=='2026-09-18'
    with db_connect() as c:c.execute("UPDATE user_groups SET description='changed' WHERE id=?",(gid,))
    b=group_workspace.status()
    assert b['refresh_token']!=a['refresh_token']


def test_performance_migration_is_non_destructive():
    from pathlib import Path
    sql=(Path(__file__).resolve().parent/'migrations'/'performance_indexes.sql').read_text().upper()
    for forbidden in ('DROP TABLE','DROP DATABASE','TRUNCATE ','DELETE FROM'):
        assert forbidden not in sql
    assert 'CREATE INDEX IF NOT EXISTS SUPERVISION_CALLS_IMPORT_TIME' in sql
    assert 'SUPERVISION_ACTIVITY_AGENT_LATEST' in sql


def test_frontend_group_polling_uses_status_endpoint():
    from pathlib import Path
    root=Path(__file__).resolve().parent/'static'
    assert "api('/api/groups/status')" in (root/'groups.js').read_text()
    assert "dashboardGroupNotice(await api('/api/groups/status'))" in (root/'app.js').read_text()


def test_frontend_support_and_calls_reuse_initial_payload():
    from pathlib import Path
    text=(Path(__file__).resolve().parent/'static'/'support.js').read_text(encoding='utf-8')
    support_block=text[text.index('async function supportView()'):text.index('function supportQuery()')]
    calls_block=text[text.index('async function callsView()'):text.index('// One daily time window')]
    assert "api('/api/supervision/support?'+initialQuery)" in support_block
    assert 'await supportRender(info,initialQuery)' in support_block
    assert 'await supportLoad();' not in support_block
    assert "api('/api/supervision/calls?'+initialQuery)" in calls_block
    assert 'callsRender(info,initialQuery)' in calls_block
    assert 'await callsLoad();' not in calls_block



def test_frontend_supervision_reuses_initial_live_payload():
    from pathlib import Path
    text=(Path(__file__).resolve().parent/'static'/'supervision.js').read_text(encoding='utf-8')
    block=text[text.index('async function supervisionView()'):text.index('function supRender(d)')]
    assert "api('/api/supervision/view?mode=live&page=0')" in block
    assert 'supRender(cfg)' in block
    assert 'await supLoad();' not in block


def test_ani_index_is_optional_and_non_destructive():
    from pathlib import Path
    sql=(Path(__file__).resolve().parent/'migrations'/'performance_indexes.sql').read_text(encoding='utf-8').upper()
    assert 'SUPERVISION_CALLS_ANI_DIGITS_TRGM' in sql
    assert "IF EXISTS (SELECT 1 FROM PG_EXTENSION WHERE EXTNAME='PG_TRGM')" in sql
    assert 'CREATE EXTENSION' not in sql


def test_analytics_single_flight_coalesces_identical_cold_requests(monkeypatch):
    import concurrent.futures
    import threading
    import time
    import analytics_service

    analytics_service._CACHE.clear()
    analytics_service._CACHE_BYTES=0
    calls={'count':0}
    lock=threading.Lock()

    def fake_revision(kind):
        return ('stable', kind)

    def fake_run(kind, query):
        with lock:
            calls['count']+=1
        time.sleep(0.05)
        return {'ok':True,'kind':kind,'query':query}, 60.0

    monkeypatch.setattr(analytics_service,'_revision_for',fake_revision)
    monkeypatch.setattr(analytics_service,'_run_query',fake_run)
    query={'date_from':['2026-09-01'],'date_to':['2026-09-23']}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(lambda _: analytics_service._analyze('quality_agents',query), range(5)))
    assert calls['count']==1
    assert all(payload==results[0][0] for payload,_ in results)
    assert sum(1 for _,hit in results if hit) == 4
