"""V60.4 regressions for real PostgreSQL hot paths.

These tests run on isolated SQLite fixtures. They verify semantics/query shape
without reading or modifying the production PostgreSQL database.
"""
import sqlite3
from audit_regression_test import lab


def test_latest_agent_names_uses_latest_active_import_for_catalog(lab):
    from supervision_db import connect
    from supervision_utils import latest_agent_names
    with connect() as c:
        c.execute("INSERT INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(1,'d1','x','now','t',0,120,'2026-09-17')")
        c.execute("INSERT INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(2,'d2','x','now','t',0,120,'2026-09-18')")
        c.execute("INSERT INTO coverage(day,import_id) VALUES('2026-09-17',1)")
        c.execute("INSERT INTO coverage(day,import_id) VALUES('2026-09-18',2)")
        # activities schema has many columns; enumerate the columns we need.
        c.execute("INSERT INTO activities(import_id,agent,name,start,end,kind,state,campaign) VALUES(1,'1001','Ancien nom',1,2,'ready','Ready','A')")
        c.execute("INSERT INTO activities(import_id,agent,name,start,end,kind,state,campaign) VALUES(2,'1001','Nom courant',3,4,'ready','Ready','A')")
        c.execute("INSERT INTO activities(import_id,agent,name,start,end,kind,state,campaign) VALUES(2,'1002','Deuxieme agent',3,4,'ready','Ready','B')")
        names=latest_agent_names(c)
        assert names=={'1001':'Nom courant','1002':'Deuxieme agent'}
        assert latest_agent_names(c,['1001'])['1001']=='Nom courant'


def test_details_range_terms_reads_active_days_once(lab):
    import details_store as d
    d.init()
    with d.connect_details() as c:
        # Three days and two authoritative sources per day.
        for i,day in enumerate(('2026-09-16','2026-09-17','2026-09-18'),1):
            c.execute("INSERT OR REPLACE INTO active_days(day,source_kind,source_import_id,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)",(day,'export',i))
            c.execute("INSERT OR REPLACE INTO active_days(day,source_kind,source_import_id,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP)",(day,'call',100+i))
        statements=[]
        # SQLite connection in the isolated test supports trace callbacks.
        c.set_trace_callback(statements.append)
        terms,params,upper=d._range_terms(
            c,
            ['2026-09-16','2026-09-17','2026-09-18'],
            {'work_start':'08:00','work_end':'19:00'},
            {'time_from':['08:00'],'time_to':['19:00']},
        )
        c.set_trace_callback(None)
    active=[s for s in statements if 'FROM active_days' in s]
    assert len(active)==1, active
    assert len(terms)>=3 and params and upper is not None


def test_probable_closure_batched_neighbor_index_matches_sql_fallback():
    from nelyio_time import day_bounds
    from support_scoring import build_activity_neighbor_index, probable_application_closure
    con=sqlite3.connect(':memory:')
    con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE activities(import_id INTEGER,agent TEXT,start REAL,end REAL,kind TEXT)')
    lo,_=day_bounds('2026-09-18')
    start=lo+12*3600
    end=start+59*60
    rows=[
        {'agent':'1001','start':start-8*60,'end':start-60,'kind':'ready'},
        {'agent':'1001','start':end+60,'end':end+8*60,'kind':'ready'},
    ]
    con.executemany('INSERT INTO activities VALUES(?,?,?,?,?)',[(1,r['agent'],r['start'],r['end'],r['kind']) for r in rows])
    event={'agent':'1001','start':start,'end':end,'seconds':59*60,'during_call':False}
    fallback=probable_application_closure(con,1,event)
    indexed=probable_application_closure(con,1,event,activity_index=build_activity_neighbor_index(rows))
    assert fallback==indexed
    assert indexed[0] is True
    con.close()


def test_v604_indexes_are_idempotent_and_non_destructive():
    from pathlib import Path
    sql=(Path(__file__).resolve().parent/'migrations'/'performance_indexes.sql').read_text(encoding='utf-8').upper()
    assert 'SUPERVISION_ACTIVITY_IMPORT_AGENT_LATEST' in sql
    assert 'DETAILS_DETAIL_EVENT_SOURCE_IMPORT_PAGE' in sql
    assert 'CREATE INDEX IF NOT EXISTS' in sql
    for forbidden in ('DROP TABLE','DROP DATABASE','TRUNCATE ','DELETE FROM'):
        assert forbidden not in sql


def test_v604_frontend_cache_busters():
    from pathlib import Path
    import re
    html=(Path(__file__).resolve().parent/'index.html').read_text(encoding='utf-8')
    # V60.4 introduced content-hash cache busters. Later releases must keep
    # the invariant without being pinned forever to the literal V60_4 label.
    match=re.search(r'app\.js\?v=(V\d+_\d+)-[0-9a-f]{16}',html)
    assert match is not None
    prefix=match.group(1)
    assert html.count('?v='+prefix+'-') >= 15
    assert 'app.js?v=RC2G-' not in html
