from __future__ import annotations

import json
from pathlib import Path

import pytest

import collection_calls
import collection_store as store
from nelyio_time import local_wall_timestamp

ROOT = Path(__file__).resolve().parent
JS = (ROOT / 'static' / 'live-views.js').read_text(encoding='utf-8')
CSS = (ROOT / 'static' / 'collection.css').read_text(encoding='utf-8')


def _settings(day='2026-09-30'):
    return {
        'day': day,
        'start_time': '08:00',
        'end_time': '19:00',
        'start_ts': local_wall_timestamp(day, 8, 0),
        'end_ts': local_wall_timestamp(day, 19, 0),
        'debug_port': 9222,
        'page_match': 'Supervision',
        'target_id': '',
        'response_path': 'changes.ashx',
        'include_phone': False,
        'timezone': 'Europe/Paris',
    }


@pytest.fixture
def isolated_live(tmp_path, monkeypatch):
    live_db = tmp_path / 'Nelyio_Live.db'
    monkeypatch.setattr(store, 'db_path', lambda: live_db)
    store._SCHEMA_IDENTITIES.clear()
    store.init()

    # Keep this test focused on the isolated Live spool, not Administration DBs.
    monkeypatch.setattr(store, '_identity_context', lambda: ({}, {}, None, None))
    monkeypatch.setattr(store, '_resolve_live_agent_names', lambda observed, agent_ids=(), context=None: {
        str(a): str(observed.get(str(a)) or a) for a in set(map(str, agent_ids)) | set(map(str, observed))
    })

    def _reference(rows):
        out=[]
        for row in rows:
            item=dict(row)
            item['observed']=bool(item.get('current_observed'))
            item['last_known']=bool(item.get('last_known'))
            out.append(item)
        return out, []
    monkeypatch.setattr(store, '_configured_live_reference', _reference)
    yield live_db
    store._SCHEMA_IDENTITIES.clear()


def _insert_event(sid, source, stamp, event_type, entity, payload):
    with store.connect() as c:
        c.execute(
            '''INSERT INTO collection_events(event_key,session_id,source,stamp,event_type,entity_id,payload_json)
               VALUES(?,?,?,?,?,?,?)''',
            (f"{sid}-{source}-{event_type}-{entity}-{stamp}-{payload.get('source_function','')}", sid, source, stamp, event_type, str(entity), json.dumps(payload)),
        )


def _set_receiving(sid, stamp):
    with store.connect() as c:
        c.execute("UPDATE collection_sessions SET status='running',connection_state='receiving',last_response=? WHERE id=?", (stamp, sid))


def test_daily_upquh_survives_new_same_day_session_and_old_state_is_last_known(isolated_live):
    day='2026-09-30'
    t1=local_wall_timestamp(day, 10, 0)
    t2=local_wall_timestamp(day, 10, 5)
    s1=store.create_session(_settings(day), 'test', clock=t1-5)
    _set_receiving(s1, t1)
    _insert_event(s1, 'src-old', t1, 'state', '1001', {'agent':'1001','state':'Disponible','line_id':'505','campaign':'DOC'})
    _insert_event(s1, 'src-old', t1, 'queue_metrics', '505', {
        'source_function':'UpQuH',
        'mapped_metrics':{'received_today':120,'handled_today':100,'abandoned_today':15,
                          'qos_exclusion_1':1,'qos_exclusion_2':2,'qos_exclusion_3':2,
                          'qos_denominator':115,'qos_today':100/115*100},
    })
    store.finish(s1, 'interrupted', clock=t1+10)

    s2=store.create_session(_settings(day), 'test', clock=t2-5)
    store.update_connection(s2, 'connected_waiting_data')

    snap=store.live_supervision_snapshot(day=day, clock=t2, include_quality=False)
    assert snap['native_queue_metrics']['by_line']['505']['UpQuH']['received_today']==120
    assert snap['persistence']['daily_queue_stats']==1
    assert snap['persistence']['day_sessions']==2
    assert snap['kpi']['connected']==0
    assert snap['kpi']['available']==0
    assert snap['agents']==[]
    old=next(x for x in snap['agent_roster'] if x['agent']=='1001')
    assert old['last_known'] is True
    assert old['observed'] is False
    assert snap['roster_counts']['last_known']==1


def test_current_segment_reobservation_revalidates_agent_after_restart(isolated_live):
    day='2026-09-30';t=local_wall_timestamp(day, 11, 0)
    sid=store.create_session(_settings(day), 'test', clock=t-20)
    _set_receiving(sid, t-10)
    _insert_event(sid, 'src-before-restart', t-10, 'state', '1001', {'agent':'1001','state':'Disponible'})

    # Simulate the service restart before any new Hermes receipt.
    store.finish(sid, 'waiting_restart', clock=t-5)
    store.update_connection(sid, 'connected_waiting_data')
    snap=store.live_supervision_snapshot(day=day, clock=t, include_quality=False)
    old=next(x for x in snap['agent_roster'] if x['agent']=='1001')
    assert old['last_known'] is True
    assert snap['kpi']['connected']==0

    # First recognized callback of the new source makes only the newly observed
    # state current again.
    _insert_event(sid, 'src-after-restart', t+1, 'state', '1001', {'agent':'1001','state':'Disponible'})
    _set_receiving(sid, t+1)
    snap=store.live_supervision_snapshot(day=day, clock=t+2, include_quality=False)
    assert snap['kpi']['connected']==1
    assert snap['kpi']['available']==1
    assert snap['agents'][0]['agent']=='1001'
    assert snap['agents'][0]['current_observed'] is True
    assert snap['roster_counts']['last_known']==0


def test_waiting_restart_preserves_observing_call_as_capture_gap(isolated_live):
    day='2026-09-30';t=local_wall_timestamp(day, 12, 0)
    sid=store.create_session(_settings(day), 'test', clock=t-30)
    _set_receiving(sid, t-5)
    with store.connect() as c:
        collection_calls.ensure_schema(c)
        payload={'agent':'1001','campaign':'DOC','line_id':'505','state':'En appel','observations':2,
                 'observed_span_seconds':5.0,'timeline':[{'stamp':t-5,'state':'En appel','phase':'observing'}]}
        c.execute('''INSERT INTO collection_call_details(source,observation_ref,event_key,session_id,agent,start,last_stamp,status,payload_json,observed_until)
                     VALUES(?,?,?,?,?,?,?,?,?,?)''',
                  ('src-a','obs-1','event-1',sid,'1001',t-5,t,'observing',json.dumps(payload),t))
    store.finish(sid, 'waiting_restart', clock=t+1)
    with store.connect() as c:
        row=c.execute("SELECT status,payload_json,observed_until FROM collection_call_details WHERE observation_ref='obs-1'").fetchone()
    assert row['status']=='capture_gap'
    data=json.loads(row['payload_json'])
    assert data['continuity_gap'] is True
    assert data['restart_gap'] is True
    assert float(row['observed_until'])==pytest.approx(t)


def test_realtime_upqur_expires_but_daily_upquh_remains(isolated_live):
    day='2026-09-30';t=local_wall_timestamp(day, 13, 0)
    sid=store.create_session(_settings(day), 'test', clock=t-120)
    _insert_event(sid, 'src-a', t-90, 'queue_metrics', '505', {
        'source_function':'UpQuR','mapped_metrics':{'calls_in_progress':4,'calls_waiting':2,'agents_available_on_queue':1}})
    _insert_event(sid, 'src-a', t-90, 'queue_metrics', '505', {
        'source_function':'UpQuH','mapped_metrics':{'received_today':50,'handled_today':45,'abandoned_today':4,
                                                   'qos_exclusion_1':0,'qos_exclusion_2':0,'qos_exclusion_3':0,
                                                   'qos_denominator':50,'qos_today':90.0}})
    with store.connect() as c:
        agents,queues=store._latest_native_hermes_metrics(
            c, sid, [sid], day_start=local_wall_timestamp(day,0,0),
            day_end=local_wall_timestamp(day,23,59)+60, clock=t)
    assert queues['505'].get('UpQuR') is None
    assert queues['505']['UpQuH']['received_today']==50


def test_ui_explains_connected_breakdown_and_same_day_persistence():
    assert 'Données du jour enregistrées' in JS
    assert 'Conservé en base · à revalider par Hermes' in JS
    assert 'current_observed' in JS and 'last_known' in JS
    assert 'dispo ·' in JS and ' appel · ' in JS and ' pause · ' in JS and ' post' in JS
    assert "liveAgentStateBucket(r.kind,r)" in JS
    assert 'live-persistence-note' in CSS
    assert 'live-state.live-last-known' in CSS
    assert 'live-last-known-note' in CSS
