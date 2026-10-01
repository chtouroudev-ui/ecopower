"""SQLite schema, configuration and reference-day maintenance for Nelyio supervision."""
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import Counter
import json, secrets, re, os
import db_compat as sqlite3
from error_log import log_unexpected_error
from nelyio_time import DISPLAY_TIMEZONE, france_offset_for_utc_timestamp
import supervision_context as state

DEFAULTS = dict(export_offset=120, display_offset=120, capture_offset=60,
                pause_seconds=900, offline_seconds=15, ready_seconds=900,
                wrap_seconds=180, stale_seconds=30, work_start='08:00', work_end='19:00')

@contextmanager
def connect():
    con = sqlite3.connect(state.db_path(), timeout=15)
    con.row_factory = sqlite3.Row
    # Keep concurrent readers responsive while a short writer transaction is active.
    con.execute('PRAGMA busy_timeout=15000')
    con.execute('PRAGMA temp_store=MEMORY')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def _reference_day_from_name(filename):
    """Return the business day encoded in a SIMPLIFY2 daily export name."""
    name=Path(str(filename or '')).name
    m=re.search(r'(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)',name)
    if not m:return ''
    try:datetime.strptime(m.group(1),'%Y-%m-%d')
    except ValueError:return ''
    return m.group(1)

def _local_day_from_stamp(ts,offset):
    return datetime.fromtimestamp(float(ts),timezone(timedelta(minutes=int(offset)))).strftime('%Y-%m-%d')

def _dominant_import_day(c,import_id,display_offset):
    """Fallback for old/custom filenames: choose the day containing most activities."""
    counts=Counter(_local_day_from_stamp(r[0],display_offset) for r in c.execute('SELECT start FROM activities WHERE import_id=?',(import_id,)))
    return counts.most_common(1)[0][0] if counts else ''

def _reference_day_for_import(c,import_id,name,import_offset,stored_day=''):
    if stored_day:return stored_day
    return _reference_day_from_name(name) or _dominant_import_day(c,import_id,import_offset)

def migrate_reference_days(c):
    """Freeze the business day of every historical import before timezone changes."""
    cols={r[1] for r in c.execute('PRAGMA table_info(imports)')}
    if 'reference_day' not in cols:
        c.execute('ALTER TABLE imports ADD COLUMN reference_day TEXT')
    coverage_by_import={}
    for r in c.execute('SELECT day,import_id FROM coverage ORDER BY day'):
        coverage_by_import.setdefault(int(r['import_id']),str(r['day']))
    for r in c.execute('SELECT day,import_id FROM call_coverage ORDER BY day'):
        coverage_by_import.setdefault(int(r['import_id']),str(r['day']))
    for r in c.execute('SELECT id,name,offset_minutes,reference_day FROM imports ORDER BY id'):
        day=str(r['reference_day'] or '').strip()
        if day:
            continue
        day=coverage_by_import.get(int(r['id'])) or _reference_day_from_name(r['name'])
        if not day:
            import_offset=int(r['offset_minutes'] if r['offset_minutes'] is not None else DEFAULTS['export_offset'])
            day=_dominant_import_day(c,r['id'],import_offset)
        if day:
            c.execute('UPDATE imports SET reference_day=? WHERE id=?',(day,r['id']))

def repair_reference_coverage(c):
    """Rebuild day mappings only from the frozen import reference day."""
    migrate_reference_days(c)
    from import_workflow import ensure_schema, reference_status
    ensure_schema(c)
    desired={};call_desired={}
    call_ids={r[0] for r in c.execute('SELECT import_id FROM call_imports')}
    for r in c.execute('SELECT id,name,offset_minutes,reference_day FROM imports ORDER BY id'):
        import_offset=int(r['offset_minutes'] if r['offset_minutes'] is not None else DEFAULTS['export_offset'])
        day=_reference_day_for_import(c,r['id'],r['name'],import_offset,r['reference_day'])
        if not day:continue
        ref=reference_status(c,r['id'])
        if ref['state']!='accepted':continue
        if ref.get('has_activities',True):desired[day]=r['id']
        if r['id'] in call_ids:call_desired[day]=r['id']
    valid_ids={r[0]:r[1] for r in c.execute('SELECT id,reference_day FROM imports')}
    for choice in c.execute('SELECT * FROM import_reference_choices'):
        if valid_ids.get(choice['activity_import_id'])==choice['day']:desired[choice['day']]=choice['activity_import_id']
        if valid_ids.get(choice['call_import_id'])==choice['day']:call_desired[choice['day']]=choice['call_import_id']
    current={r['day']:r['import_id'] for r in c.execute('SELECT day,import_id FROM coverage')}
    current_calls={r['day']:r['import_id'] for r in c.execute('SELECT day,import_id FROM call_coverage')}
    changed=current!=desired or current_calls!=call_desired
    if current!=desired:
        c.execute('DELETE FROM coverage')
        c.executemany('INSERT INTO coverage(day,import_id) VALUES(?,?)',sorted(desired.items()))
    if current_calls!=call_desired:
        c.execute('DELETE FROM call_coverage')
        c.executemany('INSERT INTO call_coverage(day,import_id) VALUES(?,?)',sorted(call_desired.items()))
    return dict(changed=changed,coverage_days=len(desired),call_days=len(call_desired))

def repair_english_call_kinds(c):
    """Repair already imported Hermes English call states.

    Older V60.4 imports classified these states as ``other`` because kind()
    only recognized French call labels. Keep Ringing excluded: ringing is not
    proof that a conversation has started. The update is idempotent and safe
    to run at startup for both SQLite and PostgreSQL through db_compat.
    """
    states=('inbound call','outbound call','manual call','dialing','consultation','call')
    marks=','.join('?' for _ in states)
    cur=c.execute(
        f"UPDATE activities SET kind='call' "
        f"WHERE kind<>'call' AND LOWER(TRIM(COALESCE(state,''))) IN ({marks})",
        states,
    )
    try:return int(cur.rowcount or 0)
    except Exception:return 0


def init():
    with connect() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS imports(id INTEGER PRIMARY KEY, digest TEXT UNIQUE NOT NULL,
          name TEXT, imported_at TEXT, imported_by TEXT, rows_count INTEGER, offset_minutes INTEGER, reference_day TEXT);
        CREATE TABLE IF NOT EXISTS coverage(day TEXT PRIMARY KEY, import_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY, import_id INTEGER NOT NULL,
          agent TEXT NOT NULL, name TEXT, start REAL NOT NULL, end REAL NOT NULL,
          state TEXT NOT NULL, kind TEXT NOT NULL, campaign TEXT, session TEXT);
        CREATE INDEX IF NOT EXISTS activity_time ON activities(start,end);
        CREATE INDEX IF NOT EXISTS activity_import ON activities(import_id,start,end);
        CREATE INDEX IF NOT EXISTS activity_kind_time ON activities(import_id,kind,start,end);
        CREATE INDEX IF NOT EXISTS activity_agent ON activities(agent,start);
        CREATE INDEX IF NOT EXISTS activity_agent_latest ON activities(agent,import_id DESC,name);
        CREATE INDEX IF NOT EXISTS activity_agent_latest_v2 ON activities(agent,import_id DESC,id DESC);
        CREATE INDEX IF NOT EXISTS activity_import_agent_time ON activities(import_id,agent,start,end);
        CREATE INDEX IF NOT EXISTS activity_import_agent_campaign ON activities(import_id,agent,campaign);
        CREATE TABLE IF NOT EXISTS live_events(event_key TEXT PRIMARY KEY,source TEXT NOT NULL,
          agent TEXT NOT NULL, start REAL NOT NULL, state TEXT NOT NULL,kind TEXT NOT NULL,
          campaign TEXT, initial INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS live_agent_time ON live_events(agent,start);
        CREATE INDEX IF NOT EXISTS live_source_agent_time ON live_events(source,agent,start DESC);
        CREATE INDEX IF NOT EXISTS live_time ON live_events(start);
        CREATE TABLE IF NOT EXISTS health(source TEXT PRIMARY KEY, heartbeat REAL, received REAL,
          last_event REAL, error TEXT);
        CREATE TABLE IF NOT EXISTS health_points(source TEXT, stamp REAL,
          PRIMARY KEY(source,stamp));
        CREATE INDEX IF NOT EXISTS health_time ON health_points(stamp);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, event_key TEXT NOT NULL,
          author TEXT, stamp TEXT, status TEXT, comment TEXT);
        CREATE INDEX IF NOT EXISTS note_key ON notes(event_key,id);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,stamp TEXT,actor TEXT,action TEXT,detail TEXT);
        ''')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS phone_calls(
          import_id INTEGER NOT NULL,call_id TEXT NOT NULL,indice TEXT NOT NULL,start REAL NOT NULL,
          call_type TEXT,duration REAL,conversation REAL,wait REAL,ani TEXT,dnis TEXT,outtel TEXT,outdialed TEXT,
          first_agent TEXT,last_agent TEXT,campaign TEXT,end_reason TEXT,no_agent INTEGER,abandon INTEGER,
          closed INTEGER,end_by_agent INTEGER,PRIMARY KEY(import_id,call_id));
        CREATE INDEX IF NOT EXISTS calls_time ON phone_calls(import_id,start);
        CREATE INDEX IF NOT EXISTS calls_import_agent_time ON phone_calls(import_id,first_agent,start);
        CREATE INDEX IF NOT EXISTS calls_import_last_agent_time ON phone_calls(import_id,last_agent,start);
        CREATE INDEX IF NOT EXISTS calls_import_campaign_time ON phone_calls(import_id,campaign,start);
        CREATE INDEX IF NOT EXISTS calls_indice ON phone_calls(indice);
        CREATE TABLE IF NOT EXISTS call_coverage(day TEXT PRIMARY KEY,import_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS call_imports(import_id INTEGER PRIMARY KEY,rows_count INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS technical_signals(
          signal_key TEXT PRIMARY KEY,source TEXT,agent TEXT,start REAL,category TEXT,detail TEXT);
        CREATE INDEX IF NOT EXISTS technical_time ON technical_signals(start);
        CREATE INDEX IF NOT EXISTS technical_category_time ON technical_signals(category,start);
        CREATE TABLE IF NOT EXISTS auto_import_log(
          id INTEGER PRIMARY KEY, filename TEXT NOT NULL, processed_at TEXT NOT NULL,
          status TEXT NOT NULL, offset_minutes INTEGER, activities INTEGER DEFAULT 0,
          calls INTEGER DEFAULT 0, detail TEXT);
        CREATE INDEX IF NOT EXISTS auto_import_log_time ON auto_import_log(processed_at DESC);
        CREATE TABLE IF NOT EXISTS retention_import_tombstones(
          digest TEXT PRIMARY KEY,name TEXT,reference_day TEXT,original_import_id INTEGER,
          archive_path TEXT,purged_at TEXT NOT NULL,policy_version TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS retention_tombstone_day ON retention_import_tombstones(reference_day);
        CREATE TABLE IF NOT EXISTS retention_monthly_aggregates(
          month TEXT PRIMARY KEY,calls INTEGER NOT NULL DEFAULT 0,activities INTEGER NOT NULL DEFAULT 0,
          offline_events INTEGER NOT NULL DEFAULT 0,live_events INTEGER NOT NULL DEFAULT 0,
          technical_signals INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL);
        ''')
        cols={r[1] for r in c.execute('PRAGMA table_info(notes)')}
        for name in ['diagnosis','cause']:
            if name not in cols:c.execute('ALTER TABLE notes ADD COLUMN '+name+' TEXT')
        for k,v in DEFAULTS.items():
            c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',(k,str(v)))
        c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('bridge_key',secrets.token_urlsafe(32)))
        # V60.4 call-state repair: fix existing imported rows before Diagnostic
        # Nelyio builds call ranges. This also repairs already-imported weeks;
        # users do not need to delete or reimport historical exports.
        repaired_calls=repair_english_call_kinds(c)
        if repaired_calls:
            try:audit(c,'system','REPAIR_CALL_KINDS',f'{repaired_calls} activités reclassées en appel')
            except Exception:pass
        # Freeze historical business-day mappings before changing display-time rules.
        migrate_reference_days(c)
        repair_reference_coverage(c)
        # Legacy clients may still read display_offset. Keep it informational only.
        current_display_offset=france_offset_for_utc_timestamp(datetime.now(timezone.utc).timestamp())
        c.execute("UPDATE settings SET value=? WHERE key='display_offset'",(str(current_display_offset),))
        c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',('display_timezone',DISPLAY_TIMEZONE))
    with connect() as c:
        from quality_metrics import ensure_schema as ensure_inbound
        from quality_agents import ensure_schema as ensure_agents
        ensure_inbound(c);ensure_agents(c)
    # Only the Web/API process performs the startup backfill. Dedicated worker
    # processes reuse the schema but must not launch simultaneous full scans.
    if os.environ.get('NELYIO_SKIP_STARTUP_DETAILS_SYNC','0').strip().lower() not in {'1','true','yes','on'}:
        try:
            import details_store
            details_store.sync_from_sources(state.db_path(),state.admin_db_path(),state.tech_labels(),force=True)
        except Exception as exc:
            log_unexpected_error('supervision.init.L348')
            print('Synchronisation base Détails ignorée :',exc)

def config(private=False):
    with connect() as c:
        d = dict(c.execute('SELECT key,value FROM settings'))
    # PostgreSQL production hardening: a partially migrated/older settings
    # table must never crash the whole application with KeyError. Defaults are
    # authoritative for missing legacy keys and init() persists them on repair.
    for k,v in DEFAULTS.items():
        raw=d.get(k, v)
        if isinstance(v,int):
            try:d[k]=int(raw)
            except (TypeError,ValueError):d[k]=int(v)
        else:
            d[k]=str(raw if raw not in (None,'') else v)
    d['display_timezone']=DISPLAY_TIMEZONE
    d['display_timezone_mode']='automatic'
    d['display_offset']=france_offset_for_utc_timestamp(datetime.now(timezone.utc).timestamp())
    if not private:d.pop('bridge_key',None)
    return d

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')

def audit(c,actor,action,detail):
    c.execute('INSERT INTO audit(stamp,actor,action,detail) VALUES(?,?,?,?)',(now(),actor,action,detail))

def save_config(data,actor):
    out={}
    for k,default in DEFAULTS.items():
        if k not in data:continue
        if k=='display_offset':
            # Display time is automatic Europe/Paris. Ignore cached legacy forms.
            continue
        v=data[k]
        if isinstance(default,int):
            v=int(v)
            low,high=(-720,840) if k.endswith('offset') else (5,86400)
            if not low<=v<=high:raise ValueError('Valeur hors limites : '+k)
        else:
            datetime.strptime(v,'%H:%M')
        out[k]=v
    current=config();current.update(out)
    if current['work_start']>=current['work_end']:raise ValueError('La fin doit etre apres le debut, sur la meme journee.')
    with connect() as c:
        for k,v in out.items():c.execute('UPDATE settings SET value=? WHERE key=?',(str(v),k))
        audit(c,actor,'CONFIG',json.dumps(out))
    return config()

