"""Durable projection of LIVE OBSERVATIONS, never authoritative ODCalls.

Counters retain their callback/index provenance. Times describe collection
receipts, not an undocumented total-call or patient-wait metric. Source events
remain immutable. Rebuilding the projection is deterministic and idempotent.
"""
from __future__ import annotations
import json
import hashlib

VERSION = 'V56.3-live-1'
CHECKPOINT = 'call_projection_v563_seq'
CALL_TYPES = ('call_observation', 'call_update')
MAX_TIMELINE = 40


def ensure_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS collection_call_details(
      source TEXT NOT NULL, observation_ref TEXT NOT NULL,
      event_key TEXT UNIQUE NOT NULL, session_id TEXT NOT NULL,
      agent TEXT NOT NULL, start REAL NOT NULL, last_stamp REAL NOT NULL,
      status TEXT NOT NULL, payload_json TEXT NOT NULL, observed_until REAL NOT NULL,
      PRIMARY KEY(source,observation_ref));
    CREATE INDEX IF NOT EXISTS collection_calls_start ON collection_call_details(start DESC,event_key);
    CREATE INDEX IF NOT EXISTS collection_calls_session ON collection_call_details(session_id,status);
    CREATE INDEX IF NOT EXISTS collection_metric_lookup ON collection_events(source,event_type,entity_id,stamp DESC);
    CREATE TABLE IF NOT EXISTS collection_call_history_sync(
      history_key TEXT PRIMARY KEY, synced_at REAL NOT NULL);
    ''')
    refresh(c)


def refresh(c):
    last_row = c.execute('SELECT value FROM collection_settings WHERE key=?', (CHECKPOINT,)).fetchone()
    last = int(last_row[0]) if last_row else 0
    # Bounded batches; no parsed HTTP or secrets, no imports of application DBs.
    while True:
        rows = c.execute('SELECT * FROM collection_events WHERE seq>? ORDER BY seq LIMIT 500', (last,)).fetchall()
        if not rows:
            break
        for row in rows:
            if row['event_type'] in CALL_TYPES:
                project(c, row)
            elif row['event_type'] == 'heartbeat':
                advance_receipt(c, row['session_id'], row['source'], row['stamp'])
            elif row['event_type'] == 'call_capture_end':
                close_source(c, row['session_id'], row['source'], json.loads(row['payload_json'])['reason'])
            last = row['seq']
        c.execute('INSERT INTO collection_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                  (CHECKPOINT, str(last)))


def project(c, row):
    p = json.loads(row['payload_json'])
    ref = p.get('observation_ref') or 'legacy:' + row['event_key']
    source, stamp = row['source'], float(row['stamp'])
    old = c.execute('SELECT * FROM collection_call_details WHERE source=? AND observation_ref=?', (source, ref)).fetchone()
    if not old:
        if row['event_type'] != 'call_observation':
            return  # Never manufacture a beginning after a missing event.
        legacy = not p.get('parser_version')
        data = dict(p, legacy=legacy, first_counters=p.get('source_counters', {}),
                    observations=1, timeline=[snapshot(p, stamp)], timeline_trimmed=0,
                    observed_span_seconds=None, finished_at=None)
        c.execute('INSERT INTO collection_call_details VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (source, ref, row['event_key'], row['session_id'], p.get('agent', ''), stamp,
                   stamp, 'legacy' if legacy else 'observing', json.dumps(data, ensure_ascii=False), stamp))
        return
    if stamp < old['last_stamp']:
        return
    data = json.loads(old['payload_json'])
    ending = p.get('phase') in ('left_call', 'segment_changed')
    # Preserve first observation, reference, queue and number. Updating counters
    # in the same state is a measurement update, NOT a new call or incident.
    if not ending:
        for key in ('state', 'phone', 'phone_status', 'source_counters', 'source_function'):
            if key in p:
                data[key] = p[key]
    else:
        data.update(finished_at=stamp, next_state=p.get('next_state', ''),
                    end_counters=p.get('end_counters', {}))
    if old['status'] == 'capture_gap' or stamp - old['observed_until'] > 30:
        data['continuity_gap'] = True
    data['observations'] = data.get('observations', 1) + 1
    data['observed_span_seconds'] = round(max(0.0, stamp - old['start']), 3)
    data['timeline'].append(snapshot(p, stamp))
    if len(data['timeline']) > MAX_TIMELINE:
        # The first sample is kept; all raw normalized samples stay in events.
        del data['timeline'][1]
        data['timeline_trimmed'] = data.get('timeline_trimmed', 0) + 1
    status = p.get('phase', 'observing')
    if data.get('continuity_gap') and not ending:
        status = 'capture_gap'
    c.execute('UPDATE collection_call_details SET last_stamp=?,status=?,payload_json=?,observed_until=? WHERE source=? AND observation_ref=?',
              (stamp, status, json.dumps(data, ensure_ascii=False), stamp, source, ref))


def snapshot(p, stamp):
    return dict(stamp=stamp, state=p.get('next_state') or p.get('state', ''),
                phase=p.get('phase', 'legacy'),
                counters=p.get('end_counters') if p.get('phase') in ('left_call', 'segment_changed') else p.get('source_counters', {}))


def close_source(c, sid, source=None, reason='capture_ended'):
    where = "session_id=? AND status='observing'"
    args = [sid]
    if source is not None:
        where += ' AND source=?'
        args.append(source)
    c.execute('UPDATE collection_call_details SET status=? WHERE ' + where, [reason] + args)


def mark_restart_gap(c, sid):
    """Preserve the last observed call facts across a service/application restart.

    A restart is not evidence that the Hermes call ended.  Keep the durable
    observation as ``capture_gap`` with a frozen observed_until timestamp.
    When fresh callbacks arrive they create a new observation segment; no
    unobserved duration is ever filled across the gap.
    """
    rows=c.execute("SELECT source,observation_ref,payload_json FROM collection_call_details WHERE session_id=? AND status='observing'",(sid,)).fetchall()
    for row in rows:
        try:data=json.loads(row['payload_json'] or '{}')
        except Exception:data={}
        data['continuity_gap']=True
        data['restart_gap']=True
        c.execute("UPDATE collection_call_details SET status='capture_gap',payload_json=? WHERE source=? AND observation_ref=?",
                  (json.dumps(data,ensure_ascii=False),row['source'],row['observation_ref']))
    return len(rows)


def contextual_counters(c, source, agent, line, stamp):
    """Derniere preuve par callback, jamais un indicateur individuel d'appel.

    Les frequents UpQuR ne doivent pas masquer UpQuH dans une fenetre globale
    de 40 lignes. La limite s'applique maintenant PAR fonction source connue.
    Le timestamp et le seq donnent un ordre deterministe, sans regarder le futur.
    """
    found = []
    scopes = (('agent_metrics', agent, ('UpAgtH', 'UpAgtSH', 'UpAgtCtxH')),
              ('queue_metrics', line, ('UpQuH', 'UpQuR', 'UpQuCB', 'UpQuMR')))
    for typ, entity, functions in scopes:
        if not entity:
            continue
        for name in functions:
            row = c.execute('''SELECT stamp,payload_json FROM collection_events
              WHERE source=? AND event_type=? AND entity_id=? AND stamp<=?
                AND json_extract(payload_json,'$.source_function')=?
              ORDER BY stamp DESC,seq DESC LIMIT 1''',
              (source, typ, entity, stamp, name)).fetchone()
            if row:
                p = json.loads(row['payload_json'])
                found.append(dict(function=name, scope=p.get('scope'), stamp=row['stamp'],
                                  counters=p.get('source_counters', {})))
    return found


def advance_receipt(c, sid, source, stamp):
    """Continuous deltas can extend the observation to a received poll, never now.
    A silence over 30 seconds breaks continuity. No unobserved time is filled.
    """
    c.execute("UPDATE collection_call_details SET status='capture_gap' WHERE session_id=? AND source=? AND status='observing' AND ?-observed_until>30", (sid, source, stamp))
    c.execute("UPDATE collection_call_details SET observed_until=? WHERE session_id=? AND source=? AND status='observing' AND observed_until<=?", (stamp, sid, source, stamp))


def record_closure(c, sid, source=None, reason='capture_ended'):
    where = "session_id=? AND status='observing'"
    args = [sid]
    if source is not None:
        where += ' AND source=?'
        args.append(source)
    sources = c.execute('SELECT source,MAX(observed_until) AS last_seen FROM collection_call_details WHERE '+where+' GROUP BY source', args).fetchall()
    for row in sources:
        key=hashlib.sha256(('live-close|'+sid+'|'+row['source']).encode()).hexdigest()
        c.execute("""INSERT OR IGNORE INTO collection_events(event_key,session_id,source,stamp,event_type,entity_id,payload_json,published)
          VALUES(?,?,?,?,'call_capture_end','',?,1)""", (key,sid,row['source'],row['last_seen'],json.dumps({'reason':reason})))
    refresh(c)
