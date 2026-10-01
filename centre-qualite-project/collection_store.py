"""Durable, minimal live-capture spool, separate from all production databases.

A response is committed before publication. Retrying a pending publication is
safe: both this outbox and the existing Support ingest use stable event keys.
No raw HTTP body, browser token, cookie or recording is persisted here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time
import threading
import uuid

import supervision_context as ctx
from nelyio_time import DISPLAY_TIMEZONE, local_day, display, day_bounds as local_day_bounds

TERMINAL = ('stopped', 'completed', 'interrupted')
AUTO_SUPPRESSED_DAY_KEY = 'auto_capture_suppressed_day'
_SCHEMA_LOCK = threading.RLock()
_SCHEMA_IDENTITIES = set()


def db_path():
    # V60: Live is a truly independent local SQLite database. It deliberately
    # bypasses the PostgreSQL compatibility layer so Live capture can never
    # lock, saturate or wait on the historical/Quality database.
    return Path(__file__).resolve().parent / 'Nelyio_Live.db'


def available():
    return db_path().is_file()


@contextmanager
def connect():
    con = sqlite3.connect(str(db_path()), timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init(force=True):
    path = db_path().resolve()
    def identity():
        try:
            st=path.stat(); return (str(path),st.st_mtime_ns,st.st_size)
        except OSError:
            return None
    if not force and identity() is not None and identity() in _SCHEMA_IDENTITIES: return
    with _SCHEMA_LOCK:
        if not force and identity() is not None and identity() in _SCHEMA_IDENTITIES: return
        _init_schema()
        _SCHEMA_IDENTITIES.add(identity())


def _init_schema():
    db_path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS collection_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS collection_sessions(
          id TEXT PRIMARY KEY,day TEXT NOT NULL,start_ts REAL NOT NULL,end_ts REAL NOT NULL,
          settings_json TEXT NOT NULL,actor TEXT NOT NULL,created_at REAL NOT NULL,
          status TEXT NOT NULL,connection_state TEXT NOT NULL DEFAULT 'waiting',
          stop_requested INTEGER NOT NULL DEFAULT 0,owner TEXT,lease_until REAL NOT NULL DEFAULT 0,
          first_response REAL,last_response REAL,last_published REAL,finished_at REAL,
          response_count INTEGER NOT NULL DEFAULT 0,event_count INTEGER NOT NULL DEFAULT 0,
          rejected_count INTEGER NOT NULL DEFAULT 0,error TEXT NOT NULL DEFAULT '');
        CREATE INDEX IF NOT EXISTS collection_session_date ON collection_sessions(created_at DESC);
        CREATE TABLE IF NOT EXISTS collection_responses(
          response_key TEXT PRIMARY KEY,session_id TEXT NOT NULL,source TEXT NOT NULL,
          stamp REAL NOT NULL,digest TEXT NOT NULL,recognized INTEGER NOT NULL,rejected INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS collection_events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT,event_key TEXT UNIQUE NOT NULL,
          session_id TEXT NOT NULL,source TEXT NOT NULL,stamp REAL NOT NULL,
          event_type TEXT NOT NULL,entity_id TEXT NOT NULL,payload_json TEXT NOT NULL,
          published INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS collection_outbox ON collection_events(published,seq);
        CREATE INDEX IF NOT EXISTS collection_event_date ON collection_events(event_type,stamp);
        CREATE INDEX IF NOT EXISTS collection_event_source ON collection_events(source,event_type,stamp);
        CREATE TABLE IF NOT EXISTS collection_catalog(
          entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,payload_json TEXT NOT NULL,
          stamp REAL NOT NULL,session_id TEXT NOT NULL,PRIMARY KEY(entity_type,entity_id));
        CREATE TABLE IF NOT EXISTS collection_audit(
          id INTEGER PRIMARY KEY,stamp REAL NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,detail TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS collection_state_latest
          ON collection_events(session_id,event_type,entity_id,stamp DESC,seq DESC);
        CREATE TABLE IF NOT EXISTS live_quality_rule_state(
          rule_id INTEGER NOT NULL,scope_type TEXT NOT NULL,scope_key TEXT NOT NULL,
          first_match REAL,last_match REAL,clear_since REAL,cooldown_until REAL NOT NULL DEFAULT 0,
          last_incident_id TEXT,updated_at REAL NOT NULL,
          PRIMARY KEY(rule_id,scope_type,scope_key));
        CREATE TABLE IF NOT EXISTS live_quality_incidents(
          id TEXT PRIMARY KEY,rule_id INTEGER NOT NULL,rule_name TEXT NOT NULL,
          scope_type TEXT NOT NULL,scope_key TEXT NOT NULL,scope_label TEXT NOT NULL,
          level_key TEXT NOT NULL,level_label TEXT NOT NULL,level_rank INTEGER NOT NULL,color TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'NOUVEAU',active INTEGER NOT NULL DEFAULT 1,
          first_seen REAL NOT NULL,last_seen REAL NOT NULL,triggered_at REAL NOT NULL,
          recovered_at REAL,closed_at REAL,cooldown_until REAL NOT NULL DEFAULT 0,
          reasons_json TEXT NOT NULL DEFAULT '[]',metrics_json TEXT NOT NULL DEFAULT '{}',updated_at REAL NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_live_quality_incident_active
          ON live_quality_incidents(rule_id,scope_type,scope_key) WHERE active=1;
        CREATE INDEX IF NOT EXISTS idx_live_quality_incident_recent
          ON live_quality_incidents(active,level_rank DESC,last_seen DESC);
        ''')
        import collection_calls
        collection_calls.ensure_schema(c)


def audit(c, actor, action, detail, clock=None):
    c.execute('INSERT INTO collection_audit(stamp,actor,action,detail) VALUES(?,?,?,?)',
              (clock if clock is not None else time.time(), str(actor)[:100], action, json.dumps(detail, ensure_ascii=False)))


def load_config():
    if not available(): return {}
    with connect() as c:
        row = c.execute("SELECT value FROM collection_settings WHERE key='config'").fetchone()
    return json.loads(row[0]) if row else {}


def save_config(value, actor):
    init(force=False)
    with connect() as c:
        c.execute("INSERT INTO collection_settings VALUES('config',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                  (json.dumps(value, ensure_ascii=False),))
        audit(c, actor, 'CONFIGURE', value)


def auto_suppressed_day():
    """Return the business day explicitly blocked by a manual collector stop."""
    if not available(): return ''
    with connect() as c:
        row = c.execute('SELECT value FROM collection_settings WHERE key=?', (AUTO_SUPPRESSED_DAY_KEY,)).fetchone()
    return str(row[0] or '') if row else ''


def clear_auto_suppression(actor, clock=None):
    """Explicitly allow auto-start again, including for the current day."""
    init(force=False)
    clock = time.time() if clock is None else float(clock)
    with connect() as c:
        row = c.execute('SELECT value FROM collection_settings WHERE key=?', (AUTO_SUPPRESSED_DAY_KEY,)).fetchone()
        c.execute('DELETE FROM collection_settings WHERE key=?', (AUTO_SUPPRESSED_DAY_KEY,))
        audit(c, actor, 'AUTO_CAPTURE_REACTIVATE', {'previous_day': str(row[0]) if row else ''}, clock)


def create_session(settings, actor, clock=None, owner=None):
    init(force=False); clock = time.time() if clock is None else float(clock)
    sid = uuid.uuid4().hex
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        # One durable session means one collector. In external-service mode an
        # armed session has no owner/lease until the worker claims it; checking
        # only lease_until allowed a second Start click to replace that session.
        busy = c.execute("SELECT id FROM collection_sessions WHERE status NOT IN ('stopped','completed','interrupted') LIMIT 1").fetchone()
        if busy:
            raise RuntimeError('Une collecte est deja en cours ou programmee. Arretez-la avant de changer la journee.')
        c.execute('''INSERT INTO collection_sessions(id,day,start_ts,end_ts,settings_json,actor,created_at,status,owner,lease_until)
                     VALUES(?,?,?,?,?,?,?,'armed',?,?)''',
                  (sid, settings['day'], settings['start_ts'], settings['end_ts'], json.dumps(settings, ensure_ascii=False), str(actor)[:100], clock, owner, clock + 30 if owner else 0))
        audit(c, actor, 'START_ONE_DAY', {'session': sid, 'day': settings['day'], 'start': settings['start_time'], 'end': settings['end_time']}, clock)
    return sid


def create_auto_session(settings, clock=None):
    """Atomically honor a manual-day hold and arm one automatic session.

    This transaction is the final arbiter for races between multiple Live
    workers and an administrator pressing Stop at the same instant.
    """
    init(force=False); clock = time.time() if clock is None else float(clock)
    sid = uuid.uuid4().hex
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        blocked = c.execute('SELECT value FROM collection_settings WHERE key=?', (AUTO_SUPPRESSED_DAY_KEY,)).fetchone()
        if blocked and str(blocked[0] or '') == str(settings['day']):
            return None, 'stopped_manually'
        busy = c.execute("SELECT id,day FROM collection_sessions WHERE status NOT IN ('stopped','completed','interrupted') LIMIT 1").fetchone()
        if busy:
            return None, 'already_armed' if str(busy['day'] or '') == str(settings['day']) else 'other_session_active'
        c.execute('''INSERT INTO collection_sessions(id,day,start_ts,end_ts,settings_json,actor,created_at,status,owner,lease_until)
                     VALUES(?,?,?,?,?,?,?,'armed',NULL,0)''',
                  (sid, settings['day'], settings['start_ts'], settings['end_ts'], json.dumps(settings, ensure_ascii=False), 'auto', clock))
        audit(c, 'auto', 'START_ONE_DAY', {'session': sid, 'day': settings['day'], 'start': settings['start_time'], 'end': settings['end_time']}, clock)
    return sid, 'armed'


def session(sid):
    with connect() as c:
        row = c.execute('SELECT * FROM collection_sessions WHERE id=?', (sid,)).fetchone()
    return dict(row) if row else None


def claim(sid, owner, clock=None):
    clock = time.time() if clock is None else float(clock)
    with connect() as c:
        cur = c.execute('''UPDATE collection_sessions SET owner=?,lease_until=? WHERE id=?
          AND status NOT IN ('stopped','completed','interrupted')
          AND (lease_until<? OR owner=? OR owner IS NULL)''', (owner, clock + 30, sid, clock, owner))
        return cur.rowcount == 1


def renew(sid, owner, clock=None):
    clock = time.time() if clock is None else float(clock)
    with connect() as c:
        return c.execute('UPDATE collection_sessions SET lease_until=? WHERE id=? AND owner=?', (clock + 30, sid, owner)).rowcount == 1


def update_connection(sid, state, error=''):
    with connect() as c:
        c.execute("UPDATE collection_sessions SET connection_state=?,error=?,status=CASE WHEN status='armed' THEN 'running' ELSE status END WHERE id=?",
                  (state, error[:300], sid))


def finish(sid, status, error='', clock=None, owner=None):
    if status not in (*TERMINAL, 'waiting_restart'): raise ValueError('Etat final invalide')
    clock = time.time() if clock is None else float(clock)
    with connect() as c:
        changed = c.execute('UPDATE collection_sessions SET status=?,connection_state=?,finished_at=?,lease_until=0,owner=NULL,error=? WHERE id=? AND (? IS NULL OR owner=?)',
                  (status, 'closed', clock, error[:300], sid, owner, owner))
        if changed.rowcount:
            import collection_calls
            if status=='waiting_restart':
                collection_calls.mark_restart_gap(c, sid)
            else:
                collection_calls.record_closure(c, sid, reason='capture_'+status if status in TERMINAL else 'capture_ended')


def request_stop(actor, clock=None, suppress_auto=True):
    """Stop active sessions immediately, even if the external Live worker is down.

    The worker still observes stop_requested, but the durable session itself must
    become terminal in the HTTP request. Otherwise an armed session can remain
    displayed as active forever when live_service is unavailable.
    """
    init(force=False)
    clock = time.time() if clock is None else float(clock)
    suppressed_day = local_day(clock) if suppress_auto else ''
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        rows = c.execute("SELECT id FROM collection_sessions WHERE status NOT IN ('stopped','completed','interrupted')").fetchall()
        if rows:
            c.execute("""UPDATE collection_sessions
                         SET stop_requested=1,status='stopped',connection_state='closed',
                             finished_at=?,lease_until=0,owner=NULL,error=''
                         WHERE status NOT IN ('stopped','completed','interrupted')""", (clock,))
            import collection_calls
            for row in rows:
                collection_calls.record_closure(c, row['id'], reason='capture_stopped')
        if suppress_auto:
            c.execute('INSERT INTO collection_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
                      (AUTO_SUPPRESSED_DAY_KEY, suppressed_day))
        audit(c, actor, 'STOP', {'sessions': len(rows), 'auto_suppressed_day': suppressed_day}, clock)
    return len(rows)


def unfinished():
    if not available(): return []
    with connect() as c:
        return [dict(r) for r in c.execute("SELECT * FROM collection_sessions WHERE status NOT IN ('stopped','completed','interrupted') ORDER BY created_at DESC")]


def record_response(sid, source, stamp, response_id, body_digest, decoded):
    """Only in-window receipts are committed. A replay cannot increase counts."""
    if not math.isfinite(stamp): raise ValueError('Horodatage invalide')
    key = hashlib.sha256(f'{sid}|{source}|{response_id}'.encode()).hexdigest()
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        row = c.execute('SELECT * FROM collection_sessions WHERE id=?', (sid,)).fetchone()
        if not row: raise ValueError('Session de collecte inconnue')
        if row['status'] in TERMINAL or row['stop_requested'] or not row['start_ts'] <= stamp < row['end_ts']:
            return {'accepted': False, 'reason': 'outside_session', 'events': 0}
        if c.execute('SELECT 1 FROM collection_responses WHERE response_key=?', (key,)).fetchone():
            return {'accepted': False, 'reason': 'duplicate', 'events': 0}
        recognized, rejected = int(decoded['recognized']), int(decoded['rejected'])
        c.execute('INSERT INTO collection_responses VALUES(?,?,?,?,?,?,?)', (key, sid, source, stamp, body_digest, recognized, rejected))
        c.execute('UPDATE collection_sessions SET response_count=response_count+1,rejected_count=rejected_count+? WHERE id=?', (rejected, sid))
        valid = bool(decoded.get('valid'))
        events = list(decoded['events']) if valid else []
        telemetry = decoded.get('telemetry')
        if telemetry:
            events.append(dict(type='protocol_telemetry', entity='', payload=telemetry))
        if valid:
            hb = c.execute("SELECT MAX(stamp) FROM collection_events WHERE source=? AND event_type='heartbeat'", (source,)).fetchone()[0]
            if hb is None or stamp - hb >= 5:
                events.append(dict(type='heartbeat', entity='', payload={}))
        for i, e in enumerate(events):
            ek = hashlib.sha256(f'{key}|{i}'.encode()).hexdigest()
            payload = json.dumps(e['payload'], ensure_ascii=False, sort_keys=True)
            c.execute('''INSERT INTO collection_events(event_key,session_id,source,stamp,event_type,entity_id,payload_json)
                         VALUES(?,?,?,?,?,?,?)''', (ek, sid, source, stamp, e['type'], e['entity'], payload))
            if e['type'] in ('queue', 'agent', 'campaign'):
                c.execute('''INSERT INTO collection_catalog VALUES(?,?,?,?,?)
                  ON CONFLICT(entity_type,entity_id) DO UPDATE SET payload_json=excluded.payload_json,stamp=excluded.stamp,session_id=excluded.session_id
                  WHERE excluded.stamp>=collection_catalog.stamp''', (e['type'], e['entity'], payload, stamp, sid))
        if not valid:
            # Une reponse inconnue reste diagnostiquable, sans prolonger une
            # observation d'appel ni actualiser last_response/first_response.
            c.execute("UPDATE collection_sessions SET event_count=event_count+?,connection_state='unrecognized',error='Reponse recue mais format non reconnu : aucun etat applique.' WHERE id=?", (len(events), sid))
            return {'accepted': True, 'reason': 'unrecognized', 'events': len(events)}
        import collection_calls
        collection_calls.refresh(c)
        c.execute('''UPDATE collection_sessions SET first_response=COALESCE(first_response,?),last_response=?,event_count=event_count+?,connection_state='receiving',error='',status='running' WHERE id=?''',
                  (stamp, stamp, len(events), sid))
    return {'accepted': True, 'events': len(events), 'reason': 'ok'}


def pending(limit=500):
    if not available(): return []
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM collection_events WHERE published=0 ORDER BY seq LIMIT ?', (limit,))]


def publish_pending(sync_details=True):
    # Keep receiving in the dedicated Live spool while a heavy import writes
    # Support. The thread lock preserves monolithic safety; the named lock is
    # the equivalent coordination primitive when Import and Live are processes.
    from import_workflow import _RUN_LOCK
    from process_lock import named_lock, LockBusy
    if not _RUN_LOCK.acquire(blocking=False): return 0
    try:
        try:
            with named_lock('support-write', timeout=0.0):
                return _publish_pending(sync_details)
        except LockBusy:
            return 0
    finally:
        _RUN_LOCK.release()


def _publish_pending(sync_details=True):
    """Existing Support normalization / keys remain the single incident path."""
    from live_capture import ingest
    events = pending()
    if not events: return 0
    batches = {}
    for e in events:
        p = json.loads(e['payload_json']); line = None
        if e['event_type'] == 'heartbeat': line = 'NELYIO_HEARTBEAT'
        elif e['event_type'] == 'state':
            tag = 'ETAT_INITIAL' if p.get('initial') else 'ETAT'
            state = p['state'] if p.get('initial') else p.get('old_state', '') + ' -> ' + p['state']
            line = f" | {tag} | Agent {p['agent']} | {state} | client={p.get('campaign','')} | evenement={e['event_key']}"
        if line is not None:
            ts = datetime.fromtimestamp(e['stamp'], timezone.utc).isoformat(timespec='microseconds')
            batches.setdefault(e['source'], []).append(dict(ts=ts, line=line))
    for source, rows in batches.items():
        ingest(dict(source=source, rows=rows), sync_details=False)
    with connect() as c:
        c.executemany('UPDATE collection_events SET published=1 WHERE seq=?', [(e['seq'],) for e in events])
        for sid in {e['session_id'] for e in events}:
            c.execute('UPDATE collection_sessions SET last_published=? WHERE id=?', (time.time(), sid))
    if sync_details:
        flush_details(force=False)
    return len(events)


def flush_details(force=False):
    """A final forced flush bypasses the normal five-second Details debounce."""
    import details_store
    return details_store.sync_from_sources(ctx.db_path(), ctx.admin_db_path(), ctx.tech_labels(), force=force)


def settle_pending_local(limit=10000):
    """V60: mark Live events as locally consumed without publishing to Support.

    Source events and call projections stay in Nelyio_Live.db for the current
    business day only.  No write is performed in the Support/Details database.
    """
    if not available(): return 0
    with connect() as c:
        rows=c.execute('SELECT seq,session_id FROM collection_events WHERE published=0 ORDER BY seq LIMIT ?', (int(limit),)).fetchall()
        if not rows:return 0
        c.executemany('UPDATE collection_events SET published=1 WHERE seq=?', [(r['seq'],) for r in rows])
        clock=time.time();session_ids=sorted({r['session_id'] for r in rows})
        if session_ids:
            c.executemany('UPDATE collection_sessions SET last_published=? WHERE id=?', [(clock,sid) for sid in session_ids])
        return len(rows)


def _history_candidates(c, limit=200):
    """Return finalized Live observations not yet copied to persistent history.

    A row is final when Hermes emitted an explicit end/segment transition, the
    collector explicitly closed it, or its owning session is terminal. A
    capture-gap row from an otherwise active session is intentionally not
    finalized because later receipts may still extend the same observation.
    """
    limit=max(1,min(5000,int(limit or 200)))
    terminal_status=('left_call','segment_changed','capture_ended','capture_stopped')
    marks=','.join('?' for _ in terminal_status)
    session_marks=','.join('?' for _ in TERMINAL)
    sql=f'''SELECT d.*,s.day AS business_day,s.status AS session_status
            FROM collection_call_details d
            JOIN collection_sessions s ON s.id=d.session_id
            LEFT JOIN collection_call_history_sync h ON h.history_key=d.event_key
            WHERE h.history_key IS NULL AND (
              d.status IN ({marks}) OR
              (s.status IN ({session_marks}) AND d.status<>'observing')
            )
            ORDER BY d.start,d.event_key LIMIT ?'''
    return c.execute(sql,(*terminal_status,*TERMINAL,limit)).fetchall()


def live_history_sync_status():
    """Small factual status for the administrator diagnostic."""
    init(force=False)
    with connect() as c:
        finalized=len(_history_candidates(c,limit=5000))
        total=int(c.execute('''SELECT COUNT(*) FROM collection_call_details d
          LEFT JOIN collection_call_history_sync h ON h.history_key=d.event_key
          WHERE h.history_key IS NULL''').fetchone()[0] or 0)
        synced=int(c.execute('SELECT COUNT(*) FROM collection_call_history_sync').fetchone()[0] or 0)
    return {'pending_finalized':finalized,'pending_total':total,'synced_local':synced}


def persist_finalized_history(limit=200):
    """Copy finalized Live evidence to the persistent supervision database.

    The copy is deliberately narrow: no ANI, no fabricated Call ID, no patient
    wait and no certified conversation duration are persisted. Retrying is
    safe because ``event_key`` is the stable primary key in both stores.
    """
    init(force=False)
    with connect() as local:
        rows=list(_history_candidates(local,limit=limit))
    if not rows:
        return {'persisted':0,'candidates':0,'pending_finalized':0}

    import supervision_db
    prepared=[]
    for row in rows:
        payload=_safe_payload(row['payload_json'])
        start=float(row['start'])
        finished=payload.get('finished_at')
        try:
            observed_end=float(finished) if finished not in (None,'') else float(row['observed_until'] or row['last_stamp'] or start)
        except (TypeError,ValueError):
            observed_end=float(row['last_stamp'] or start)
        observed_end=max(start,observed_end)
        span=payload.get('observed_span_seconds')
        try: span=float(span) if span is not None else round(observed_end-start,3)
        except (TypeError,ValueError): span=round(observed_end-start,3)
        prepared.append((
            str(row['event_key']),str(row['business_day'] or ''),start,observed_end,
            str(row['agent'] or ''),str(payload.get('line_id') or ''),str(payload.get('campaign') or ''),
            str(row['observation_ref'] or ''),str(payload.get('source_function') or ''),str(row['status'] or ''),
            1 if payload.get('partial_start') else 0,1 if payload.get('continuity_gap') else 0,span,
            str(row['session_id'] or ''),str(row['source'] or ''),datetime.now(timezone.utc).isoformat(timespec='seconds'),
        ))

    # Commit the durable copy before acknowledging anything in the Live spool.
    # If PostgreSQL is unavailable the local rows remain unsynced, so retention
    # can defer their deletion rather than lose evidence.
    with supervision_db.connect() as target:
        supervision_db.ensure_live_history_schema(target)
        for values in prepared:
            target.execute('''INSERT INTO live_call_observation_history(
              history_key,business_day,observed_start,observed_end,agent,line_id,campaign,
              observation_ref,source_function,final_status,partial_start,continuity_gap,
              observed_span,session_id,source,persisted_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(history_key) DO NOTHING''',values)

    synced_at=time.time()
    with connect() as local:
        local.executemany('INSERT OR IGNORE INTO collection_call_history_sync(history_key,synced_at) VALUES(?,?)',
                          [(r[0],synced_at) for r in prepared])
        pending=len(_history_candidates(local,limit=5000))
    return {'persisted':len(prepared),'candidates':len(prepared),'pending_finalized':pending}


def purge_before_day(keep_day=None):
    """Keep the Live spool compact without losing unsynchronized evidence.

    Finalized observations are copied to persistent history separately. A stale
    session containing any call observation that has not been acknowledged by
    that copy is deferred instead of deleted. SIMPLIFY2 remains authoritative
    for historical KPI calculations.
    """
    init(force=False)
    keep_day=str(keep_day or local_day(time.time()))
    from nelyio_time import day_bounds
    start,_=day_bounds(keep_day)
    deleted={'sessions':0,'events':0,'responses':0,'calls':0,'audit':0,'catalog':0}
    deferred=[]
    with connect() as c:
        stale=[r['id'] for r in c.execute('SELECT id FROM collection_sessions WHERE day<>?', (keep_day,)).fetchall()]
        if stale:
            marks_all=','.join('?'*len(stale))
            deferred=[r[0] for r in c.execute(f'''SELECT DISTINCT d.session_id
              FROM collection_call_details d
              LEFT JOIN collection_call_history_sync h ON h.history_key=d.event_key
              WHERE d.session_id IN ({marks_all}) AND h.history_key IS NULL''',stale).fetchall()]
            deferred_set=set(deferred)
            stale=[sid for sid in stale if sid not in deferred_set]
        if stale:
            marks=','.join('?'*len(stale))
            for table,key,label in (
                ('collection_call_details','session_id','calls'),
                ('collection_responses','session_id','responses'),
                ('collection_events','session_id','events'),
                ('collection_catalog','session_id','catalog'),
            ):
                before=c.execute(f'SELECT COUNT(*) FROM {table} WHERE {key} IN ({marks})', stale).fetchone()[0]
                c.execute(f'DELETE FROM {table} WHERE {key} IN ({marks})', stale);deleted[label]=int(before or 0)
            deleted['sessions']=len(stale)
            c.execute(f'DELETE FROM collection_sessions WHERE id IN ({marks})', stale)
        deleted['audit']=int(c.execute('SELECT COUNT(*) FROM collection_audit WHERE stamp<?',(start,)).fetchone()[0] or 0)
        c.execute('DELETE FROM collection_audit WHERE stamp<?',(start,))
        # Projection checkpoint follows the newest remaining event after purge.
        last=int(c.execute('SELECT COALESCE(MAX(seq),0) FROM collection_events').fetchone()[0] or 0)
        c.execute('INSERT INTO collection_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', ('call_projection_v563_seq',str(last)))
        c.execute('DELETE FROM collection_call_history_sync WHERE history_key NOT IN (SELECT event_key FROM collection_call_details)')
    # Keep the disposable daily spool physically compact as well as logically
    # purged. This runs only on a day change/startup and never touches Web/PG.
    if sum(deleted.values()):
        try:
            con=sqlite3.connect(str(db_path()),timeout=30,isolation_level=None)
            try:
                con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                con.execute('VACUUM')
            finally:
                con.close()
        except sqlite3.Error:
            pass
    return dict(day=keep_day,deleted=deleted,deferred_unsynced=len(deferred),deferred_sessions=deferred)


def catalog():
    if not available(): return {'queue': {}, 'agent': {}, 'campaign': {}}
    result = {'queue': {}, 'agent': {}, 'campaign': {}}
    with connect() as c:
        for row in c.execute('SELECT * FROM collection_catalog'):
            payload = json.loads(row['payload_json']); payload['seen_at'] = row['stamp']; payload['seen_day'] = local_day(row['stamp'])
            result[row['entity_type']][row['entity_id']] = payload
    return result


def latest_day(fallback=None):
    """Only actual accepted receipts can change the default day of a screen."""
    if not available(): return fallback
    with connect() as c:
        stamp = c.execute('SELECT MAX(last_response) FROM collection_sessions').fetchone()[0]
    return max(filter(None, (fallback, local_day(stamp) if stamp else None)), default=None)


def public_status(clock=None, include_config=False):
    # V60 Live is always a small local SQLite/WAL database.
    init(force=False)
    clock = time.time() if clock is None else float(clock)
    stored_config = {}
    with connect() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM collection_sessions ORDER BY created_at DESC LIMIT 10')]
        pending_count = c.execute('SELECT COUNT(*) FROM collection_events WHERE published=0').fetchone()[0]
        counts = {r[0]: r[1] for r in c.execute('SELECT entity_type,COUNT(*) FROM collection_catalog GROUP BY entity_type')}
        if include_config:
            config_row = c.execute("SELECT value FROM collection_settings WHERE key='config'").fetchone()
            stored_config = json.loads(config_row[0]) if config_row else {}
    output = []
    for row in rows:
        settings = json.loads(row.pop('settings_json'))
        for k in ('owner', 'lease_until'): row.pop(k, None)
        row['settings'] = settings
        row['fresh'] = bool(row['last_response'] and 0 <= clock-row['last_response'] <= 30 and row['status'] not in TERMINAL)
        for k in ('first_response', 'last_response', 'last_published', 'created_at', 'finished_at'):
            row[k + '_text'] = display(row[k]) if row[k] else ''
        output.append(row)
    result = dict(current=output[0] if output else None, history=output, pending=pending_count, catalog=counts,
                  timezone=DISPLAY_TIMEZONE, server_day=local_day(clock), server_clock=display(clock),
                  group_sync_supported=False, priority_sync_supported=False)
    if include_config:
        result['_stored_config'] = stored_config
    return result


def brief(clock=None):
    """Minimal shared banner without identities, URLs, or configuration."""
    clock = time.time() if clock is None else float(clock)
    if not available(): return dict(active=False, day=None, fresh=False)
    with connect() as c:
        row = c.execute('SELECT day,status,connection_state,last_response,last_published,first_response FROM collection_sessions ORDER BY created_at DESC LIMIT 1').fetchone()
        pending_count = c.execute('SELECT COUNT(*) FROM collection_events WHERE published=0').fetchone()[0]
    if not row: return dict(active=False, day=None, fresh=False, pending=0)
    out = dict(row)
    out['active'] = row['status'] not in TERMINAL
    out['fresh'] = bool(out['active'] and row['last_response'] and 0 <= clock-row['last_response'] <= 30)
    out['last_response_text'] = display(row['last_response']) if row['last_response'] else ''
    out['pending'] = int(pending_count or 0)
    out['publication_delayed'] = bool(out['pending'] and row['last_response'] and (not row['last_published'] or row['last_response'] > row['last_published']))
    return out


def live_admin_diagnostic(clock=None):
    """Small administrator-only health view for the isolated Live stack.

    Keep this deliberately factual: browser-client counts are not tracked by
    the current polling architecture, so they are exposed as unsupported
    instead of being guessed from HTTP traffic.
    """
    init(force=False)
    clock = time.time() if clock is None else float(clock)
    with connect() as c:
        session = c.execute('SELECT * FROM collection_sessions ORDER BY created_at DESC LIMIT 1').fetchone()
        health = _live_health(c, session, clock)
        pending = int(c.execute('SELECT COUNT(*) FROM collection_events WHERE published=0').fetchone()[0] or 0)

    database = {'ok': False, 'engine': 'unknown', 'error': ''}
    try:
        import db_compat
        import supervision_db
        database['engine'] = 'PostgreSQL' if db_compat.postgres_enabled() else 'SQLite compatibilité/laboratoire'
        with supervision_db.connect() as con:
            con.execute('SELECT 1').fetchone()
        database['ok'] = True
    except Exception as exc:
        # Diagnostic only: never make the isolated Live spool fail because the
        # historical database is unavailable.
        database['error'] = str(exc)[:240]

    try:
        history_sync=live_history_sync_status()
        history_sync['ok']=bool(database.get('ok'))
    except Exception as exc:
        history_sync={'ok':False,'pending_finalized':None,'pending_total':None,'synced_local':None,'error':str(exc)[:240]}

    worker_measured = health.get('worker_healthy') is not None
    return {
        'server_clock': display(clock),
        'collector': {
            'ok': bool(health.get('active') and health.get('state') not in {'worker_down', 'stopped'}),
            'state': health.get('state'),
            'label': health.get('label'),
            'status': health.get('collector_status'),
        },
        'hermes': {
            'ok': bool(health.get('fresh')),
            'connection_state': health.get('connection_state'),
            'last_response': health.get('last_response'),
            'last_response_text': health.get('last_response_text'),
            'age_seconds': health.get('last_response_age'),
        },
        'worker': {
            'measured': worker_measured,
            'ok': health.get('worker_healthy') if worker_measured else None,
            'state': health.get('worker_state'),
            'age_seconds': health.get('worker_age_seconds'),
            'build_match': health.get('worker_build_match'),
        },
        'database': database,
        'history_persistence': history_sync,
        'events': {
            'last_heartbeat': health.get('last_heartbeat'),
            'last_heartbeat_text': health.get('last_heartbeat_text'),
            'last_event': health.get('last_event'),
            'last_event_text': health.get('last_event_text'),
            'pending': pending,
        },
        'clients_live_connected': None,
        'capabilities': {'clients_live_connected': False,'finalized_live_evidence_history': True},
        'limitations': [
            'Le nombre de navigateurs Live connectés n’est pas mesuré par l’architecture polling actuelle.',
            'L’historique Live persiste uniquement des observations factuelles finalisées ; les KPI historiques certifiés restent issus des imports SIMPLIFY2.',
        ],
    }


def end_call_source(sid, source):
    import collection_calls
    with connect() as c:
        collection_calls.record_closure(c, sid, source, reason='capture_gap')


def _safe_payload(raw):
    try:
        value=json.loads(raw or '{}')
        return value if isinstance(value,dict) else {}
    except (TypeError,ValueError,json.JSONDecodeError):
        return {}


def _mask_phone(value):
    raw=str(value or '').strip()
    if not raw:
        return ''
    if len(raw)<=4:
        return '*'*len(raw)
    return raw[:2]+'*'*max(2,len(raw)-4)+raw[-2:]


def _latest_session_for_day(c, day):
    return c.execute('SELECT * FROM collection_sessions WHERE day=? ORDER BY created_at DESC LIMIT 1',(day,)).fetchone()


def _live_health(c, session, clock):
    if not session:
        return dict(state='inactive',label='Collecte non démarrée',fresh=False,active=False,
                    collector_status='',connection_state='',last_response=None,last_response_text='',
                    last_response_age=None,last_heartbeat=None,last_heartbeat_text='',last_event=None,last_event_text='')
    active=session['status'] not in TERMINAL
    last_response=float(session['last_response']) if session['last_response'] else None
    age=max(0.0,clock-last_response) if last_response is not None else None
    fresh=bool(active and last_response is not None and age<=30)
    if fresh:
        state,label='live','LIVE'
    elif active and last_response is None:
        state,label='waiting','En attente de données'
    elif active:
        state,label='delay','Retard de collecte'
    else:
        state,label='stopped','Collecte interrompue' if session['status']=='interrupted' else 'Collecte arrêtée'
    hb=c.execute("SELECT MAX(stamp) FROM collection_events WHERE session_id=? AND event_type='heartbeat'",(session['id'],)).fetchone()[0]
    ev=c.execute('SELECT MAX(stamp) FROM collection_events WHERE session_id=?',(session['id'],)).fetchone()[0]
    worker_healthy=None;worker_state='monolithic';worker_age=None;worker_build_match=None
    try:
        from service_mode import external_services_enabled
        if external_services_enabled():
            import service_state
            status=service_state.public_status()
            worker=next((x for x in status.get('services',[]) if x.get('service')=='live'),None)
            worker_healthy=bool(worker and worker.get('healthy'))
            worker_state=str((worker or {}).get('state') or 'not_started')
            worker_age=(worker or {}).get('age_seconds')
            worker_build_match=(worker or {}).get('build_match')
            if active and not worker_healthy:
                fresh=False;state='worker_down';label='Collecte interrompue'
    except Exception:
        # Service-health storage is deliberately independent; failure to read it
        # must not take the Live spool itself down.
        worker_healthy=False if active else None;worker_state='status_error'
        if active:
            fresh=False;state='worker_down';label='Collecte interrompue'
    return dict(state=state,label=label,fresh=fresh,active=active,
                collector_status=session['status'],connection_state=session['connection_state'],
                worker_healthy=worker_healthy,worker_state=worker_state,worker_age_seconds=worker_age,worker_build_match=worker_build_match,
                last_response=last_response,last_response_text=display(last_response) if last_response else '',
                last_response_age=round(age,1) if age is not None else None,
                last_heartbeat=float(hb) if hb is not None else None,last_heartbeat_text=display(hb) if hb else '',
                last_event=float(ev) if ev is not None else None,last_event_text=display(ev) if ev else '')


def _merge_interval_seconds(intervals):
    cleaned=sorted((float(a),float(b)) for a,b in intervals if b is not None and a is not None and float(b)>float(a))
    if not cleaned:return 0.0
    total=0.0;start,end=cleaned[0]
    for a,b in cleaned[1:]:
        if a<=end:
            end=max(end,b)
        else:
            total+=end-start;start,end=a,b
    return round(total+end-start,1)


def _live_agent_activity(c, sessions, day, clock):
    """Aggregate only directly observed Live facts for the requested local day."""
    from supervision_utils import kind
    session_rows=list(sessions or [])
    if not session_rows:return {}
    ids=[str(r['id']) for r in session_rows]
    marks=','.join('?' for _ in ids)
    d0,d1=local_day_bounds(day)
    session_end={}
    for r in session_rows:
        end=r['last_response'] or r['finished_at'] or r['end_ts'] or clock
        session_end[str(r['id'])]=min(float(end),float(clock),float(d1))
    intervals={};events={}
    sql=f"""SELECT session_id,seq,stamp,event_type,entity_id,payload_json
            FROM collection_events
            WHERE session_id IN ({marks}) AND event_type IN ('state','global_state')
            ORDER BY entity_id,session_id,stamp,seq"""
    for r in c.execute(sql,ids):
        aid=str(r['entity_id'] or '')
        if not aid:continue
        payload=_safe_payload(r['payload_json']);state=str(payload.get('state') or '').strip()
        if not state:continue
        events.setdefault((aid,str(r['session_id'])),[]).append((float(r['stamp']),int(r['seq']),kind(state)))
    for (aid,sid),rows in events.items():
        collapsed=[]
        for stamp,seq,k in rows:
            if collapsed and abs(collapsed[-1][0]-stamp)<0.0001:
                collapsed[-1]=(stamp,seq,k)
            elif collapsed and collapsed[-1][2]==k:
                continue
            else:
                collapsed.append((stamp,seq,k))
        end_ref=session_end.get(sid,float(clock))
        for idx,(stamp,_seq,k) in enumerate(collapsed):
            a=max(float(stamp),float(d0));b=min(float(collapsed[idx+1][0]) if idx+1<len(collapsed) else end_ref,float(d1))
            if b>a:intervals.setdefault(aid,{}).setdefault(k,[]).append((a,b))
    activity={}
    for aid,kinds in intervals.items():
        seconds={k:_merge_interval_seconds(v) for k,v in kinds.items()}
        observed=[]
        for vals in kinds.values():observed.extend(vals)
        seconds['observed']=_merge_interval_seconds(observed)
        seconds['non_available']=round(sum(seconds.get(k,0.0) for k in ('pause','offline','inactive_context','other')),1)
        activity[aid]={'state_seconds':seconds,'calls_today':0,'calls_15m':0,'calls_60m':0,
                       'call_observed_seconds':0.0,'campaigns':{},'last_call':None}
    import collection_calls
    collection_calls.ensure_schema(c)
    sql=f"""SELECT source,observation_ref,agent,start,last_stamp,status,payload_json,observed_until
            FROM collection_call_details WHERE session_id IN ({marks})
            ORDER BY last_stamp DESC"""
    for r in c.execute(sql,ids):
        aid=str(r['agent'] or '')
        if not aid:continue
        item=activity.setdefault(aid,{'state_seconds':{'observed':0.0,'non_available':0.0},'calls_today':0,'calls_15m':0,'calls_60m':0,
                                      'call_observed_seconds':0.0,'campaigns':{},'last_call':None})
        start=float(r['start']);end=max(start,float(r['observed_until'] or r['last_stamp'] or start))
        item['calls_today']+=1
        if start>=clock-900:item['calls_15m']+=1
        if start>=clock-3600:item['calls_60m']+=1
        item['call_observed_seconds']=round(float(item.get('call_observed_seconds') or 0.0)+max(0.0,end-start),1)
        cp=_safe_payload(r['payload_json']);campaign=str(cp.get('campaign') or '').strip()
        if campaign:
            cstats=item['campaigns'].setdefault(campaign,{'today':0,'last_15m':0,'last_60m':0})
            cstats['today']+=1
            if start>=clock-900:cstats['last_15m']+=1
            if start>=clock-3600:cstats['last_60m']+=1
        if item.get('last_call') is None:
            item['last_call']={'reference':str(r['observation_ref'] or ''),'start':start,'start_text':display(start),
                               'last_stamp':float(r['last_stamp'] or start),'last_text':display(float(r['last_stamp'] or start)),
                               'campaign':campaign,'line_id':str(cp.get('line_id') or ''),'line_name':str(cp.get('line_name') or ''),
                               'status':str(r['status'] or '')}
    return activity


def _explicit_hold_observation(payload, observed_until=None):
    """Return duration only when an explicit HOLD state label was observed."""
    from supervision_utils import kind
    p=payload if isinstance(payload,dict) else {}
    if int(p.get('timeline_trimmed') or 0)>0:
        return {'seconds':None,'segments':None,'quality':'unavailable','reason':'timeline_trimmed'}
    timeline=[x for x in (p.get('timeline') or []) if isinstance(x,dict) and x.get('stamp') is not None]
    timeline.sort(key=lambda x:float(x.get('stamp')))
    hits=[]
    for i,t in enumerate(timeline):
        if kind(str(t.get('state') or ''))!='hold':continue
        a=float(t['stamp']);b=float(timeline[i+1]['stamp']) if i+1<len(timeline) else float(observed_until or a)
        if b>a:hits.append((a,b))
    if not hits:
        return {'seconds':None,'segments':None,'quality':'unavailable','reason':'explicit_hold_state_not_observed'}
    return {'seconds':_merge_interval_seconds(hits),'segments':len(hits),'quality':'observed_explicit_state','reason':''}


def _first_explicit_hold_offset(payload, call_start):
    """Return first explicit HOLD offset from observed call start, or None.

    A partial call start cannot certify an "early hold" threshold, so it stays
    unavailable instead of being guessed from the first captured sample.
    """
    from supervision_utils import kind
    p=payload if isinstance(payload,dict) else {}
    if p.get('partial_start') or int(p.get('timeline_trimmed') or 0)>0:
        return None
    try: start=float(call_start)
    except (TypeError,ValueError): return None
    offsets=[]
    for item in p.get('timeline') or []:
        if not isinstance(item,dict) or item.get('stamp') is None: continue
        if kind(str(item.get('state') or ''))!='hold': continue
        try: offsets.append(max(0.0,float(item['stamp'])-start))
        except (TypeError,ValueError): pass
    return round(min(offsets),1) if offsets else None

def _identity_context():
    """Presentation-only identity context shared by Live views.

    Failure to load Administration/Quality catalogues must never stop the
    isolated Live spool; callers keep raw Hermes ids/labels as fallback.
    """
    admin_users={};configured_names={};scope=None;campaign_catalog=None
    try:
        from agent_directory import load_admin_directory
        admin_users=(load_admin_directory() or {}).get('users',{}) or {}
    except Exception:
        pass
    try:
        from quality_scope import load_quality_file_scope
        scope=load_quality_file_scope()
        configured_names={str(k):str(v) for k,v in (scope.get('agent_names') or {}).items() if str(k)}
        from identity_resolver import campaign_catalog as _campaign_catalog
        campaign_catalog=_campaign_catalog(scope)
    except Exception:
        pass
    return admin_users,configured_names,scope,campaign_catalog


def _resolve_live_agent_names(observed_names, agent_ids=(), *, context=None):
    from identity_resolver import resolve_agent_name
    admin_users,configured_names,_scope,_catalog=context or _identity_context()
    ids=set(str(x) for x in agent_ids if str(x))|set(str(x) for x in observed_names if str(x))
    return {aid:resolve_agent_name(aid,admin_users=admin_users,
                                   observed_name=observed_names.get(aid,''),
                                   configured_name=configured_names.get(aid,''))
            for aid in ids}


def _resolve_live_campaign(raw_id='', raw_label='', *, context=None):
    from identity_resolver import resolve_campaign_identity
    if context is None:
        _admin,_names,scope,catalog=_identity_context()
    else:
        scope,catalog=context
    try:
        return resolve_campaign_identity(raw_id,raw_label,scope=scope,catalog=catalog)
    except Exception:
        raw=str(raw_label or raw_id or '').strip()
        return {'campaign_id':str(raw_id or '').strip(),'campaign_label':raw,'identity_quality':'observed_only' if raw else 'unavailable'}


def _configured_live_reference(observed_rows=None):
    """Return the configured ACTIVE agent roster used as a supervision reference.

    The Live spool remains the source for *observed state*. Configuration only
    tells us which agents/groups should exist. Missing Live state therefore
    becomes ``unobserved`` rather than ``offline`` or a fabricated zero.
    """
    observed_rows=list(observed_rows or [])
    observed={str(a.get('agent') or ''):a for a in observed_rows if str(a.get('agent') or '')}
    try:
        from analysis_groups import catalog as analysis_group_catalog
        groups=[g for g in analysis_group_catalog(include_unassigned=False) if str(g.get('id') or '')!='unassigned']
    except Exception:
        groups=[]
    names={}
    try:
        from quality_scope import load_quality_file_scope
        names.update({str(k):str(v) for k,v in (load_quality_file_scope().get('agent_names') or {}).items() if str(k)})
    except Exception:
        pass
    try:
        from agent_directory import load_admin_directory, admin_name_for
        admin=load_admin_directory();users=admin.get('users',{})
        for aid in {str(x) for g in groups for x in (g.get('member_agent_ids') or []) if str(x)}:
            names[aid]=admin_name_for(aid,users,names.get(aid,aid))
    except Exception:
        pass
    groups_by_agent={}
    for g in groups:
        light=dict(id=str(g.get('id') or ''),name=str(g.get('name') or ''),service_name=str(g.get('service_name') or ''))
        for aid in g.get('member_agent_ids') or []:
            groups_by_agent.setdefault(str(aid),[]).append(light)
    roster=[]
    configured_ids=sorted(groups_by_agent,key=lambda x:(names.get(x,x).casefold(),x))
    for aid in configured_ids:
        assigned=groups_by_agent.get(aid,[])
        services=sorted({g.get('service_name') for g in assigned if g.get('service_name')},key=str.casefold)
        if aid in observed:
            row=dict(observed[aid]);row['observed']=bool(row.get('current_observed',True))
            row['last_known']=bool(row.get('last_known'))
            if not row.get('assigned_groups'):row['assigned_groups']=assigned
            if not row.get('groups'):row['groups']=assigned
            if not row.get('service_names'):row['service_names']=services
            if not str(row.get('name') or '').strip():row['name']=names.get(aid,aid)
            roster.append(row);continue
        roster.append(dict(agent=aid,name=names.get(aid,aid),state='Non observé',kind='unobserved',line_id='',campaign='',
                           groups=assigned,assigned_groups=assigned,current_groups=[],service_names=services,
                           started_at=None,started_at_text='',state_age_seconds=None,ticking=False,last_activity=None,
                           last_activity_text='',current_call=None,activity=None,fresh=False,observed=False))
    for aid,row in observed.items():
        if aid in groups_by_agent:continue
        item=dict(row);item['observed']=bool(item.get('current_observed',True));item['last_known']=bool(item.get('last_known'));roster.append(item)
    roster.sort(key=lambda r:(not bool(r.get('observed')),str(r.get('name') or r.get('agent') or '').casefold(),str(r.get('agent') or '')))
    return roster,groups

def _latest_native_hermes_metrics(c, session_id, day_session_ids=None, *, day_start=None, day_end=None, clock=None):
    """Return latest verified legacy-supervision metrics per agent/queue.

    UpQuH / UpAgtH are cumulative daily counters.  Read them across every
    event observed during the business day, not only from the currently active
    collector session: Hermes sends deltas and a reconnect must not erase the
    last daily values.  UpQuR is realtime, so an event from another session is
    accepted only when it is still very recent (30 s).
    """
    agents={}
    queues={}
    current_session=str(session_id)
    ids=[str(x) for x in (day_session_ids or [session_id]) if str(x)]
    if current_session not in ids: ids.append(current_session)
    params=[]
    where=[]
    if day_start is not None and day_end is not None:
        where.append('stamp>=? AND stamp<?')
        params.extend([float(day_start),float(day_end)])
    elif ids:
        placeholders=','.join('?' for _ in ids)
        where.append(f'session_id IN ({placeholders})')
        params.extend(ids)
    where.append("event_type IN ('agent_metrics','queue_metrics')")
    rows=c.execute(f"""SELECT session_id,stamp,event_type,entity_id,payload_json FROM collection_events
                      WHERE {' AND '.join(where)}
                      ORDER BY stamp DESC,seq DESC""",params)
    seen=set()
    for row in rows:
        payload=_safe_payload(row['payload_json'])
        fn=str(payload.get('source_function') or '')
        entity=str(row['entity_id'] or '')
        # UpQuR is realtime. Never reuse a stale queue snapshot merely because
        # an application restart resumed the same durable session. The daily
        # UpQuH counters remain day-wide and persistent; waiting/in-progress
        # must be re-observed within the freshness window.
        if fn=='UpQuR':
            if clock is not None and float(clock)-float(row['stamp'])>30.0:
                continue
            # Backward-compatible helper behavior when no wall clock is given:
            # realtime data may only come from the current collector session.
            if clock is None and str(row['session_id'])!=current_session:
                continue
        key=(row['event_type'],entity,fn)
        if not entity or key in seen:
            continue
        seen.add(key)
        mapped=dict(payload.get('mapped_metrics') or {})
        # Backward compatibility for sessions captured before the semantic
        # fields were added: derive only the mappings proven from the supplied HAR.
        counters=dict(payload.get('source_counters') or {})
        if not mapped and fn=='UpAgtH':
            mapped={
                'reception_today':counters.get('arg_6'),
                'pause_count_today':counters.get('arg_8'),
                'pause_seconds_today':counters.get('arg_9'),
            }
        elif not mapped and fn=='UpQuH':
            received=counters.get('arg_3');abandoned=counters.get('arg_5');handled=counters.get('arg_12')
            ex1=counters.get('arg_6');ex2=counters.get('arg_10');ex3=counters.get('arg_11')
            if all(v is not None for v in (received,abandoned,handled,ex1,ex2,ex3)):
                den=received-ex1-ex2-ex3
                mapped={'received_today':received,'abandoned_today':abandoned,'handled_today':handled,
                        'qos_exclusion_1':ex1,'qos_exclusion_2':ex2,'qos_exclusion_3':ex3,
                        'qos_denominator':den,'qos_today':(100.0*handled/den) if den>0 else None}
        elif not mapped and fn=='UpQuR':
            mapped={'calls_in_progress':counters.get('arg_2'),'calls_waiting':counters.get('arg_3'),
                    'agents_available_on_queue':counters.get('arg_8')}
        if not mapped:
            continue
        record={'source_function':fn,'stamp':float(row['stamp']),**mapped}
        if row['event_type']=='agent_metrics' and fn=='UpAgtH':
            agents[entity]=record
        elif row['event_type']=='queue_metrics' and fn in ('UpQuH','UpQuR'):
            queues.setdefault(entity,{})[fn]=record
    return agents,queues


def live_supervision_snapshot(day=None, clock=None, include_quality=True, show_phone=False):
    # Current operational agent state from the isolated Live spool. Only facts
    # demonstrated by Hermes callbacks are exposed here.
    from supervision_utils import kind
    init(force=False)
    clock=time.time() if clock is None else float(clock)
    day=str(day or local_day(clock))
    try:
        datetime.strptime(day,'%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('Jour Live invalide.') from exc
    with connect() as c:
        day_sessions=list(c.execute('SELECT * FROM collection_sessions WHERE day=? ORDER BY created_at',(day,)))
        session=day_sessions[-1] if day_sessions else None
        health=_live_health(c,session,clock)
        if not session:
            roster,_configured_groups=_configured_live_reference([])
            result=dict(day=day,server_clock=display(clock),health=health,kpi=dict(agents_known=0,connected=0,disconnected=None,in_call=0,available=0,unavailable=0,current_calls=None,calls_waiting=None),agents=[],
                        catalog_reference=True,agent_roster=roster,roster_counts=dict(configured=len(roster),observed=0,last_known=0,unobserved=len(roster)),
                        persistence=dict(database='Nelyio_Live.db',retention='current_day_spool',day_sessions=0,normalized_events=0,responses=0,call_observations=0,current_source='',current_agents=0,last_known_agents=0,daily_queue_stats=0,normalized_events_persisted=True,daily_metrics_persisted=True,raw_response_body_persisted=False,finalized_call_evidence_persisted=True),
                        capabilities=dict(calls_waiting=False,certified_call_duration=False,call_id=False,explicit_call_hold=True,agent_activity_today=True),limitations=['Aucune session Live disponible pour cette journée.'])
            if include_quality:
                try:
                    import live_quality
                    result['quality']=live_quality.quality_summary(result,clock=clock)
                except Exception:
                    result['quality']={'operational_status':{'level_key':'INDETERMINE','label':'INDÉTERMINÉ','rank':0,'color':'#667085','reason':'quality_engine_unavailable'},'data_quality':{'quality':'unavailable','label':'Qualité Live indisponible','color':'#667085'},'active_incident_count':0,'active_incidents':[]}
            return result
        sid=session['id']
        day_lo,day_hi=local_day_bounds(day,'00:00','23:59')
        # Include the final minute explicitly because day_bounds expects a
        # wall-clock interval, while Live daily counters span the full day.
        day_hi+=60.0
        day_session_ids=[str(x['id']) for x in day_sessions]
        native_agent_metrics,native_queue_metrics=_latest_native_hermes_metrics(
            c,sid,day_session_ids,day_start=day_lo,day_end=day_hi,clock=clock)
        # InitQueue is an observed Hermes catalogue. Keep only entries refreshed
        # by one of today's sessions so a stale label from another day cannot
        # silently repair a campaign/file mapping.
        live_queue_catalog={}
        marks=','.join('?' for _ in day_session_ids) if day_session_ids else ''
        if day_session_ids:
            for qrow in c.execute(f"SELECT entity_id,payload_json FROM collection_catalog WHERE entity_type='queue' AND session_id IN ({marks})",day_session_ids):
                qp=_safe_payload(qrow['payload_json'])
                qid=str(qrow['entity_id'] or '').strip();label=str(qp.get('name') or '').strip()
                if qid and label: live_queue_catalog[qid]=label
        # A reconnect/restart creates a new capture source even when the durable
        # day session is resumed. The newest normalized event identifies the
        # currently observed source segment; older same-day facts stay available
        # as last-known evidence instead of disappearing from the roster.
        source_row=c.execute("SELECT source FROM collection_events WHERE session_id=? AND event_type<>'protocol_telemetry' ORDER BY seq DESC LIMIT 1",(sid,)).fetchone()
        current_source=str(source_row['source'] or '') if source_row else ''
        activity_by_agent=_live_agent_activity(c,day_sessions,day,clock)
        observed_names={}
        if day_session_ids:
            for row in c.execute(f"SELECT entity_id,payload_json FROM collection_catalog WHERE entity_type='agent' AND session_id IN ({marks})",day_session_ids):
                p=_safe_payload(row['payload_json'])
                label=' '.join(x for x in (str(p.get('first_name') or '').strip(),str(p.get('last_name') or '').strip()) if x).strip()
                observed_names[str(row['entity_id'])]=label or str(p.get('name') or row['entity_id'])
        identity_context=_identity_context()
        names=_resolve_live_agent_names(observed_names,context=identity_context)
        campaign_context=(identity_context[2],identity_context[3])
        latest={}
        if day_session_ids:
            for row in c.execute(f"""SELECT session_id,source,seq,stamp,event_type,entity_id,payload_json FROM collection_events
                                    WHERE session_id IN ({marks}) AND event_type IN ('state','global_state')
                                    ORDER BY stamp DESC,seq DESC""",day_session_ids):
                agent=str(row['entity_id'] or '')
                if not agent or agent in latest:
                    continue
                latest[agent]=(row,_safe_payload(row['payload_json']))
        # Business hierarchy comes from configured groups/files, never from
        # campaign labels. Failure to load that optional catalogue must not take
        # the isolated Live spool down.
        group_catalog=[]
        try:
            from analysis_groups import catalog as analysis_group_catalog
            group_catalog=[g for g in analysis_group_catalog(include_unassigned=False) if str(g.get('id'))!='unassigned']
        except Exception:
            group_catalog=[]
        groups_by_agent={}
        groups_by_line={}
        for g in group_catalog:
            light=dict(id=str(g.get('id') or ''),name=str(g.get('name') or ''),service_name=str(g.get('service_name') or ''))
            for aid in g.get('member_agent_ids') or []:
                groups_by_agent.setdefault(str(aid),[]).append(light)
            for lid in g.get('line_ids') or []:
                groups_by_line.setdefault(str(lid),[]).append(light)
        import collection_calls
        collection_calls.ensure_schema(c)
        calls_by_agent={}
        for row in c.execute("""SELECT source,observation_ref,agent,start,last_stamp,status,payload_json,observed_until
                                FROM collection_call_details WHERE session_id=? AND status IN ('observing','capture_gap')
                                ORDER BY last_stamp DESC""",(sid,)):
            agent=str(row['agent'] or '')
            if agent and agent not in calls_by_agent:
                calls_by_agent[agent]=row
        agent_rows=[]
        counts=dict(agents_known=0,connected=0,disconnected=0,in_call=0,on_hold=0,available=0,unavailable=0,inactive_context=0,current_calls=0 if health['fresh'] else None,calls_waiting=None)
        for agent,(row,payload) in latest.items():
            state=str(payload.get('state') or '').strip()
            state_kind=kind(state)
            stamp=float(row['stamp'])
            row_session=str(row['session_id'] or '')
            row_source=str(row['source'] or '')
            # A persisted state is current only after THIS capture segment has
            # actually resumed receiving recognized Hermes data.  Immediately
            # after an application/browser restart, connection_state is
            # connecting/connected_waiting_data/waiting_browser: the old state
            # remains durable evidence but must be shown as last-known, not Live.
            current_observed=bool(session['connection_state']=='receiving' and current_source and row_session==sid and row_source==current_source)
            last_known=not current_observed
            reference=clock if health['fresh'] else (health.get('last_response') or stamp)
            age=max(0,reference-stamp)
            current_call=None
            call_row=calls_by_agent.get(agent)
            if call_row:
                cp=_safe_payload(call_row['payload_json'])
                live_status=str(call_row['status'])
                call_source=str(call_row['source'] or '')
                call_is_current=bool(live_status=='observing' and session['connection_state']=='receiving' and current_source and call_source==current_source)
                if live_status=='observing' and not call_is_current:
                    live_status='unconfirmed'
                if not health['fresh'] and live_status=='observing':
                    live_status='unconfirmed'
                hold=_explicit_hold_observation(cp,call_row['observed_until'])
                call_campaign_ident=_resolve_live_campaign('',str(cp.get('campaign') or ''),context=campaign_context)
                raw_phone=str(cp.get('phone') or '').strip()
                call_start=float(call_row['start'])
                if health['fresh'] and call_is_current:
                    call_reference=clock
                else:
                    call_reference=float(call_row['observed_until'] or call_row['last_stamp'] or call_start)
                call_age=max(0.0,call_reference-call_start)
                current_call=dict(reference=call_row['observation_ref'],status=live_status,
                                  source=call_row['source'],start=call_start,start_text=display(call_start),
                                  call_age_seconds=round(call_age,1),call_ticking=bool(health['fresh'] and call_is_current),
                                  last_stamp=float(call_row['last_stamp']),last_text=display(call_row['last_stamp']),
                                  line_id=str(cp.get('line_id') or ''),line_name=str(cp.get('line_name') or ''),
                                  campaign=str(cp.get('campaign') or ''),campaign_id=call_campaign_ident.get('campaign_id',''),campaign_name=call_campaign_ident.get('campaign_label',''),campaign_identity_quality=call_campaign_ident.get('identity_quality',''),state=str(cp.get('state') or ''),
                                  phone=(raw_phone if show_phone else _mask_phone(raw_phone)),phone_masked=bool(raw_phone and not show_phone),phone_status=str(cp.get('phone_status') or ''),
                                  partial_start=bool(cp.get('partial_start')),hold_observed_seconds=hold['seconds'],
                                  first_hold_offset_seconds=_first_explicit_hold_offset(cp,call_start),
                                  hold_observed_segments=hold['segments'],hold_quality=hold['quality'],hold_reason=hold['reason'])
            if current_observed:
                counts['agents_known']+=1
                if state_kind!='offline': counts['connected']+=1
                if state_kind=='offline': counts['disconnected']+=1
                if state_kind in ('call','hold'): counts['in_call']+=1
                if state_kind=='hold': counts['on_hold']+=1
                if state_kind=='ready': counts['available']+=1
                if state_kind=='inactive_context': counts['inactive_context']+=1
                if state_kind not in ('offline','ready','call','hold'): counts['unavailable']+=1
            line_id=str(payload.get('line_id') or (current_call or {}).get('line_id') or '')
            raw_campaign=str(payload.get('campaign') or '')
            agent_campaign_ident=_resolve_live_campaign('',raw_campaign,context=campaign_context)
            current_groups=groups_by_line.get(line_id,[]) if line_id else []
            assigned_groups=groups_by_agent.get(agent,[])
            effective_groups=current_groups or assigned_groups
            service_names=sorted({g['service_name'] for g in effective_groups if g.get('service_name')},key=str.casefold)
            if agent not in names:
                names.update(_resolve_live_agent_names({agent:observed_names.get(agent,'')},[agent],context=identity_context))
            agent_rows.append(dict(agent=agent,name=names.get(agent,agent),state=state,kind=state_kind,
                                   line_id=line_id,campaign=raw_campaign,campaign_id=agent_campaign_ident.get('campaign_id',''),campaign_name=agent_campaign_ident.get('campaign_label',''),campaign_identity_quality=agent_campaign_ident.get('identity_quality',''),
                                   groups=effective_groups,assigned_groups=assigned_groups,current_groups=current_groups,
                                   service_names=service_names,
                                   started_at=stamp,started_at_text=display(stamp),state_age_seconds=round(age,1),
                                   ticking=bool(health['fresh'] and current_observed),last_activity=stamp,last_activity_text=display(stamp),
                                   current_call=current_call,activity=activity_by_agent.get(agent) or {'state_seconds':{'observed':0.0,'non_available':0.0},'calls_today':0,'calls_15m':0,'calls_60m':0,'call_observed_seconds':0.0,'campaigns':{},'last_call':None},
                                   hermes_daily=native_agent_metrics.get(agent) or {},
                                   current_observed=current_observed,last_known=last_known,observation_session_id=row_session,observation_source=row_source,
                                   fresh=bool(health['fresh'] and current_observed)))
        if health['fresh']:
            counts['current_calls']=sum(1 for r in calls_by_agent.values() if r['status']=='observing' and session['connection_state']=='receiving' and current_source and str(r['source'] or '')==current_source)
        agent_rows.sort(key=lambda r:(not bool(r.get('current_observed')),r['kind']=='offline',r['kind'] not in ('call','hold'),str(r['name']).casefold(),r['agent']))
        agents=[r for r in agent_rows if r.get('current_observed')]
        roster,_configured_groups=_configured_live_reference(agent_rows)
        roster_counts=dict(configured=len(roster),
                           observed=sum(1 for r in roster if r.get('observed')),
                           last_known=sum(1 for r in roster if r.get('last_known') and not r.get('observed')),
                           unobserved=sum(1 for r in roster if not r.get('observed') and not r.get('last_known')))
        if day_session_ids:
            event_count=int(c.execute(f'SELECT COUNT(*) FROM collection_events WHERE session_id IN ({marks})',day_session_ids).fetchone()[0] or 0)
            response_count=int(c.execute(f'SELECT COUNT(*) FROM collection_responses WHERE session_id IN ({marks})',day_session_ids).fetchone()[0] or 0)
            call_count=int(c.execute(f'SELECT COUNT(*) FROM collection_call_details WHERE session_id IN ({marks})',day_session_ids).fetchone()[0] or 0)
        else:
            event_count=response_count=call_count=0
        persistence=dict(database='Nelyio_Live.db',retention='current_day_spool',day_sessions=len(day_sessions),
                         normalized_events=event_count,responses=response_count,call_observations=call_count,
                         current_source=current_source,current_agents=len(agents),last_known_agents=sum(1 for r in agent_rows if r.get('last_known')),
                         daily_queue_stats=sum(1 for v in native_queue_metrics.values() if (v or {}).get('UpQuH')),
                         normalized_events_persisted=True,daily_metrics_persisted=True,raw_response_body_persisted=False,
                         finalized_call_evidence_persisted=True)
    result=dict(day=day,server_clock=display(clock),health=health,kpi=counts,agents=agents,catalog_reference=True,agent_roster=roster,roster_counts=roster_counts,persistence=persistence,
                native_queue_metrics={
                    'by_line':native_queue_metrics if 'native_queue_metrics' in locals() else {},
                    'line_count':len(native_queue_metrics if 'native_queue_metrics' in locals() else {}),
                    'upqur_count':sum(1 for v in (native_queue_metrics if 'native_queue_metrics' in locals() else {}).values() if (v or {}).get('UpQuR')),
                    'upquh_count':sum(1 for v in (native_queue_metrics if 'native_queue_metrics' in locals() else {}).values() if (v or {}).get('UpQuH')),
                },
                live_queue_catalog=live_queue_catalog if 'live_queue_catalog' in locals() else {},
                capabilities=dict(calls_waiting=True,certified_call_duration=False,call_id=False,explicit_call_hold=True,agent_activity_today=True,hermes_daily_queue_stats=True,hermes_daily_agent_stats=True),
                limitations=[
                    'Les compteurs de file UpQuR exposent maintenant Attente et Appels en cours comme agrégats Live ; ils ne constituent toujours pas un Call ID individuel.',
                    'Une mise en attente pendant appel n’est affichée que lorsqu’un libellé explicite Mise en attente / HOLD est réellement observé dans la timeline Live ; son absence ne vaut pas zéro.',
                    'Le temps non disponible observé par agent = Pause + Déconnecté + autres états indisponibles ; Disponible et Post-appel ne sont pas comptés comme temps perdu.',
                    'La référence Live est une référence d’observation Nelyio, pas le Call ID historique SIMPLIFY2.',
                    'Les durées d’état sont mesurées depuis le changement d’état observé ; elles cessent d’être incrémentées si la collecte n’est plus fraîche.',
                    'Après une reprise, le dernier état connu du jour reste visible mais n’est pas compté comme état courant tant qu’Hermes ne l’a pas réobservé sur la nouvelle connexion.'
                ])
    if include_quality:
        try:
            import live_quality
            result['quality']=live_quality.quality_summary(result,clock=clock)
        except Exception:
            # Quality signalling is additive. A configuration/runtime failure must
            # never make the core Hermes supervision endpoint unavailable.
            result['quality']={
                'operational_status':{'level_key':'INDETERMINE','label':'INDÉTERMINÉ','rank':0,'color':'#667085','reason':'quality_engine_unavailable'},
                'data_quality':{'quality':'unavailable','label':'Qualité Live indisponible','color':'#667085'},
                'active_incident_count':0,'active_incidents':[],
            }
    return result


def live_call_search(qs=None, clock=None, show_phone=False):
    # Search the disposable current-day Live call projection without guessing
    # undocumented fields or turning an observation reference into a Call ID.
    qs=qs or {}
    get=lambda key,default='': str(qs.get(key,[default])[0]).strip()
    clock=time.time() if clock is None else float(clock)
    day=local_day(clock)
    window=get('window','30m') or '30m'
    allowed={'in_progress':None,'5m':300,'15m':900,'30m':1800,'1h':3600,'today':None}
    if window not in allowed:
        raise ValueError('Fenêtre Live invalide.')
    query=get('q').casefold();agent_filter=get('agent');ref_filter=get('reference')
    from sort_contract import request as sort_request
    sort_key,sort_direction=sort_request(qs,allowed={'last_stamp','start','agent','campaign','line','reference'},default_key='last_stamp',default_direction='desc')
    try:
        page=max(0,int(get('page','0') or 0));page_size=max(20,min(200,int(get('page_size','100') or 100)))
    except ValueError as exc:
        raise ValueError('Pagination Live invalide.') from exc
    init(force=False)
    with connect() as c:
        sessions=[r['id'] for r in c.execute('SELECT id FROM collection_sessions WHERE day=? ORDER BY created_at',(day,))]
        latest=_latest_session_for_day(c,day)
        health=_live_health(c,latest,clock)
        if not sessions:
            return dict(day=day,window=window,q=get('q'),count=0,page=page,page_size=page_size,rows=[],agents=[],health=health,
                        capabilities=dict(call_id=False,wait=False,conversation_duration=False,end_origin=False,explicit_call_hold=True),reference_label='Référence Live',limitations=['Aucune observation Live disponible aujourd’hui.'])
        marks=','.join('?' for _ in sessions)
        import collection_calls
        collection_calls.ensure_schema(c)
        observed_names={}
        for row in c.execute("SELECT entity_id,payload_json FROM collection_catalog WHERE entity_type='agent'"):
            p=_safe_payload(row['payload_json'])
            label=' '.join(x for x in (str(p.get('first_name') or '').strip(),str(p.get('last_name') or '').strip()) if x).strip()
            observed_names[str(row['entity_id'])]=label or str(p.get('name') or row['entity_id'])
        identity_context=_identity_context()
        names=_resolve_live_agent_names(observed_names,context=identity_context)
        campaign_context=(identity_context[2],identity_context[3])
        sql=f'''SELECT source,observation_ref,event_key,session_id,agent,start,last_stamp,status,payload_json,observed_until
                FROM collection_call_details WHERE session_id IN ({marks})'''
        params=list(sessions)
        if window=='in_progress':
            sql+=" AND status='observing'"
        elif allowed[window] is not None:
            sql+=' AND last_stamp>=?';params.append(clock-allowed[window])
        if agent_filter:
            sql+=' AND agent=?';params.append(agent_filter)
        if ref_filter:
            sql+=' AND observation_ref=?';params.append(ref_filter)
        sql+=' ORDER BY last_stamp DESC LIMIT 2000'
        candidates=[]
        for row in c.execute(sql,params):
            p=_safe_payload(row['payload_json']);phone=str(p.get('phone') or '').strip();phone_status=str(p.get('phone_status') or '')
            aid=str(row['agent'])
            if aid not in names:
                names.update(_resolve_live_agent_names({aid:observed_names.get(aid,'')},[aid],context=identity_context))
            display_name=names.get(aid,aid)
            campaign_ident=_resolve_live_campaign('',str(p.get('campaign') or ''),context=campaign_context)
            hay=' '.join((str(row['observation_ref']),aid,display_name,phone if show_phone else '',str(p.get('campaign') or ''),campaign_ident.get('campaign_label',''),str(p.get('line_id') or ''),str(p.get('line_name') or ''))).casefold()
            if query and query not in hay:
                continue
            live_status=str(row['status'])
            if latest and row['session_id']==latest['id'] and not health['fresh'] and live_status=='observing':
                live_status='unconfirmed'
            timeline=[]
            for t in p.get('timeline') or []:
                if not isinstance(t,dict):
                    continue
                stamp=t.get('stamp')
                timeline.append(dict(stamp=stamp,stamp_text=display(stamp) if stamp is not None else '',
                                     state=str(t.get('state') or ''),phase=str(t.get('phase') or '')))
            hold=_explicit_hold_observation(p,row['observed_until'])
            candidates.append(dict(reference=row['observation_ref'],reference_label='Référence Live',agent=aid,
                                   name=display_name,source=str(row['source']),
                                   start=float(row['start']),start_text=display(row['start']),last_stamp=float(row['last_stamp']),last_text=display(row['last_stamp']),
                                   observed_until=float(row['observed_until']),observed_until_text=display(row['observed_until']),
                                   observed_span_seconds=p.get('observed_span_seconds'),status=live_status,state=str(p.get('state') or ''),
                                   line_id=str(p.get('line_id') or ''),line_name=str(p.get('line_name') or ''),campaign=str(p.get('campaign') or ''),
                                   campaign_id=campaign_ident.get('campaign_id',''),campaign_name=campaign_ident.get('campaign_label',''),campaign_identity_quality=campaign_ident.get('identity_quality',''),
                                   phone=phone if show_phone else _mask_phone(phone),phone_masked=bool(phone and not show_phone),phone_status=phone_status,
                                   partial_start=bool(p.get('partial_start')),timeline=timeline,timeline_trimmed=int(p.get('timeline_trimmed') or 0),
                                   observation_count=int(p.get('observations') or 1),hold_observed_seconds=hold['seconds'],
                                   hold_observed_segments=hold['segments'],hold_quality=hold['quality'],hold_reason=hold['reason'],
                                   call_id=None,wait=None,conversation_duration=None,end_origin=None))
        from sort_contract import sorted_rows
        def sort_value(row,key):
            return {
                'last_stamp':row.get('last_stamp'),'start':row.get('start'),'agent':row.get('name') or row.get('agent'),
                'campaign':row.get('campaign_name') or row.get('campaign'),'line':row.get('line_name') or row.get('line_id'),
                'reference':row.get('reference'),
            }.get(key)
        candidates=sorted_rows(candidates,key=sort_key,direction=sort_direction,getter=sort_value,id_getter=lambda r:r.get('reference'))
        total=len(candidates);rows=candidates[page*page_size:(page+1)*page_size]
        agents=sorted(({r['agent']:r['name'] for r in candidates}).items(),key=lambda x:(x[1].casefold(),x[0]))
    return dict(day=day,window=window,q=get('q'),count=total,page=page,page_size=page_size,rows=rows,sort=sort_key,direction=sort_direction,
                agents=[dict(agent=a,name=n) for a,n in agents],health=health,
                capabilities=dict(call_id=False,wait=False,conversation_duration=False,end_origin=False,explicit_call_hold=True),reference_label='Référence Live',
                limitations=[
                    'La Référence Live identifie une observation locale et ne doit pas être présentée comme Call ID Hermes/SIMPLIFY2.',
                    'Attente patient, durée de conversation certifiée et origine de fin ne sont pas déduites des compteurs non documentés.',
                    'Le stockage Live est volontairement limité à la journée courante ; l’historique certifié vient des imports SIMPLIFY2.'
                ])


def live_campaign_call_preview(day=None, campaign_values=None, clock=None, show_phone=False, limit=100, window='30m'):
    """Return a bounded recent-call preview for one campaign drill-down.

    The projection stays in the isolated Live spool and matches only campaign
    labels/ids actually present in the call payload. It never invents CallID,
    waiting time, conversation duration or end origin.
    """
    clock=time.time() if clock is None else float(clock)
    day=str(day or local_day(clock))
    try:
        datetime.strptime(day,'%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('Jour Live invalide.') from exc
    windows={'15m':900,'30m':1800,'1h':3600,'2h':7200,'today':None}
    if window not in windows:
        raise ValueError('Fenêtre appels campagne invalide.')
    try:
        limit=max(20,min(200,int(limit or 100)))
    except (TypeError,ValueError) as exc:
        raise ValueError('Limite appels campagne invalide.') from exc
    wanted={str(x or '').strip().casefold() for x in (campaign_values or []) if str(x or '').strip()}
    init(force=False)
    with connect() as c:
        sessions=[r['id'] for r in c.execute('SELECT id FROM collection_sessions WHERE day=? ORDER BY created_at',(day,))]
        latest=_latest_session_for_day(c,day)
        health=_live_health(c,latest,clock)
        if not sessions or not wanted:
            return dict(day=day,window=window,count=0,rows=[],limit=limit,truncated=False,health=health,
                        source='Hermes Live',quality='reliable' if health.get('fresh') else 'unavailable')
        marks=','.join('?' for _ in sessions)
        observed_names={}
        for row in c.execute(f"SELECT entity_id,payload_json FROM collection_catalog WHERE entity_type='agent' AND session_id IN ({marks})",sessions):
            p=_safe_payload(row['payload_json'])
            label=' '.join(x for x in (str(p.get('first_name') or '').strip(),str(p.get('last_name') or '').strip()) if x).strip()
            observed_names[str(row['entity_id'])]=label or str(p.get('name') or row['entity_id'])
        identity_context=_identity_context()
        names=_resolve_live_agent_names(observed_names,context=identity_context)
        campaign_context=(identity_context[2],identity_context[3])
        sql=f"""SELECT source,observation_ref,event_key,session_id,agent,start,last_stamp,status,payload_json,observed_until
                FROM collection_call_details WHERE session_id IN ({marks})"""
        params=list(sessions)
        seconds=windows[window]
        if seconds is not None:
            sql+=' AND last_stamp>=?';params.append(clock-float(seconds))
        sql+=' ORDER BY last_stamp DESC LIMIT 5000'
        rows=[];matched=0;candidate_count=0
        for row in c.execute(sql,params):
            candidate_count+=1
            p=_safe_payload(row['payload_json'])
            campaign=str(p.get('campaign') or '').strip()
            if campaign.casefold() not in wanted:
                continue
            matched+=1
            if len(rows)>=limit:
                continue
            phone=str(p.get('phone') or '').strip();phone_status=str(p.get('phone_status') or '')
            live_status=str(row['status'])
            if latest and row['session_id']==latest['id'] and not health.get('fresh') and live_status=='observing':
                live_status='unconfirmed'
            timeline=[]
            for t in p.get('timeline') or []:
                if not isinstance(t,dict):continue
                stamp=t.get('stamp')
                timeline.append(dict(stamp=stamp,stamp_text=display(stamp) if stamp is not None else '',
                                     state=str(t.get('state') or ''),phase=str(t.get('phase') or '')))
            hold=_explicit_hold_observation(p,row['observed_until'])
            aid=str(row['agent'])
            if aid not in names:
                names.update(_resolve_live_agent_names({aid:observed_names.get(aid,'')},[aid],context=identity_context))
            campaign_ident=_resolve_live_campaign('',campaign,context=campaign_context)
            rows.append(dict(reference=row['observation_ref'],reference_label='Référence Live',agent=aid,
                             name=names.get(aid,aid),source=str(row['source']),
                             start=float(row['start']),start_text=display(row['start']),last_stamp=float(row['last_stamp']),last_text=display(row['last_stamp']),
                             observed_until=float(row['observed_until']),observed_until_text=display(row['observed_until']),
                             observed_span_seconds=p.get('observed_span_seconds'),status=live_status,state=str(p.get('state') or ''),
                             line_id=str(p.get('line_id') or ''),line_name=str(p.get('line_name') or ''),campaign=campaign,
                             campaign_id=campaign_ident.get('campaign_id',''),campaign_name=campaign_ident.get('campaign_label',''),campaign_identity_quality=campaign_ident.get('identity_quality',''),
                             phone=phone if show_phone else _mask_phone(phone),phone_masked=bool(phone and not show_phone),phone_status=phone_status,
                             partial_start=bool(p.get('partial_start')),timeline=timeline,timeline_trimmed=int(p.get('timeline_trimmed') or 0),
                             observation_count=int(p.get('observations') or 1),hold_observed_seconds=hold['seconds'],
                             hold_observed_segments=hold['segments'],hold_quality=hold['quality'],hold_reason=hold['reason'],
                             call_id=None,wait=None,conversation_duration=None,end_origin=None))
    return dict(day=day,window=window,count=matched,rows=rows,limit=limit,
                truncated=matched>len(rows) or candidate_count>=5000,candidate_limit_hit=candidate_count>=5000,
                health=health,source='Hermes Live',quality='reliable' if health.get('fresh') else 'unavailable',
                limitations=[
                    'La Référence Live est une référence d’observation Nelyio, pas un Call ID historique.',
                    'La timeline contient uniquement les événements réellement observés par le collecteur Live.',
                ])


def live_snapshot(day=None, page=0, page_size=100):
    """Small current-day Live view served directly from Nelyio_Live.db.

    This endpoint deliberately bypasses Support/Analytics/PostgreSQL.  It is
    operational evidence, not historical KPI data, and therefore stays useful
    even while an import or a historical calculation is running.
    """
    init(force=False)
    day = str(day or local_day(time.time()))
    try:
        datetime.strptime(day, '%Y-%m-%d')
    except ValueError as exc:
        raise ValueError('Jour Live invalide.') from exc
    page=max(0,int(page or 0));page_size=max(20,min(200,int(page_size or 100)))
    with connect() as c:
        sessions=[r[0] for r in c.execute('SELECT id FROM collection_sessions WHERE day=? ORDER BY created_at',(day,))]
        if not sessions:
            return dict(day=day,count=0,page=page,page_size=page_size,rows=[],events_by_type={},catalog={'agent':0,'queue':0,'campaign':0},agents=[],queues=[],campaigns=[],calls=0)
        marks=','.join('?' for _ in sessions)
        counts={r[0]:int(r[1]) for r in c.execute(
            f'SELECT event_type,COUNT(*) FROM collection_events WHERE session_id IN ({marks}) GROUP BY event_type',sessions)}
        total=int(c.execute(f'SELECT COUNT(*) FROM collection_events WHERE session_id IN ({marks})',sessions).fetchone()[0] or 0)
        rows=[]
        sql=f'''SELECT seq,event_key,session_id,source,stamp,event_type,entity_id,payload_json
                FROM collection_events WHERE session_id IN ({marks})
                ORDER BY stamp DESC,seq DESC LIMIT ? OFFSET ?'''
        params=list(sessions)+[page_size,page*page_size]
        labels={
            'call_observation':'Appel observe','agent_state_sample':'Etat agent','agent':'Agent',
            'context':'Contexte agent','queue':'File','campaign':'Campagne',
            'campaign_metrics':'Compteurs campagne','protocol_telemetry':'Telemetrie protocole',
            'heartbeat':'Heartbeat','signal':'Signal technique',
        }
        for r in c.execute(sql,params):
            try: payload=json.loads(r['payload_json'] or '{}')
            except (TypeError,ValueError,json.JSONDecodeError): payload={}
            rows.append(dict(
                seq=int(r['seq']),key=r['event_key'],source=r['source'],stamp=float(r['stamp']),
                stamp_text=display(r['stamp']),event_type=r['event_type'],
                event_label=labels.get(r['event_type'],r['event_type']),entity_id=r['entity_id'],
                agent=str(payload.get('agent') or ''),campaign=str(payload.get('campaign') or payload.get('campaign_id') or ''),
                line_id=str(payload.get('line_id') or ''),line_name=str(payload.get('line_name') or payload.get('name') or ''),
                phone=str(payload.get('phone') or ''),state=str(payload.get('state') or ''),
            ))
        catalog_counts={k:0 for k in ('agent','queue','campaign')}
        catalog_rows={k:[] for k in catalog_counts}
        for typ in catalog_counts:
            for r in c.execute(f'''SELECT entity_id,payload_json,stamp FROM collection_catalog
                                   WHERE entity_type=? AND session_id IN ({marks})
                                   ORDER BY stamp DESC,entity_id LIMIT 200''',[typ,*sessions]):
                try:p=json.loads(r['payload_json'] or '{}')
                except (TypeError,ValueError,json.JSONDecodeError):p={}
                item=dict(id=r['entity_id'],seen_at=display(r['stamp']))
                if typ=='agent':
                    item.update(name=(' '.join(filter(None,(str(p.get('first_name') or '').strip(),str(p.get('last_name') or '').strip()))).strip() or str(p.get('name') or '') or r['entity_id']),state=str(p.get('state') or ''))
                elif typ=='queue':item.update(name=str(p.get('name') or r['entity_id']))
                else:item.update(name=str(p.get('name') or r['entity_id']))
                catalog_rows[typ].append(item)
            catalog_counts[typ]=len(catalog_rows[typ])
    return dict(day=day,count=total,page=page,page_size=page_size,rows=rows,events_by_type=counts,
                catalog=catalog_counts,agents=catalog_rows['agent'],queues=catalog_rows['queue'],campaigns=catalog_rows['campaign'],
                calls=int(counts.get('call_observation',0)))
