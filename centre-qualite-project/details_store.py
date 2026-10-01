"""Dedicated detail-log archive for Nelyio.

The operational databases remain authoritative for Support/Analytics. This
module maintains a separate SQLite archive used only by the minimalist Details
interface. Synchronization is idempotent and incremental.
"""
from error_log import log_unexpected_error
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from collections import defaultdict
from array import array
from details_read_cache import ProjectionCache, fingerprint
import json
import math
import re
import db_compat as sqlite3
import threading
import time
from nelyio_time import day_bounds as france_day_bounds, display as france_display, today as france_today
from supervision_utils import selected_bounds
from support_filters import _support_excluded_slots
from agent_directory import build_agent_roster, canonical_admin_key, load_admin_directory
from unified_filters import normalize_filters, public_filter_contract
from policy_engine import load_policies
from declaration_engine import load_declarations
from governance_engine import apply_event_governance, DetailsGovernanceCalendar
from analysis_groups import filter_catalog

DETAILS_DB = Path(__file__).with_name('Nelyio_Details.db')
_SYNC_LOCK = threading.RLock()
_SCHEMA_LOCK = threading.RLock()
_SCHEMA_IDENTITIES = set()
_LAST_SYNC_AT = 0.0
_LAST_SYNC_RESULT = None
_READ_CACHE = ProjectionCache()
_MAX_PROJECTED_IDS = 1000000


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def normalize_key(value):
    value = str(value or '').strip()
    if not value:
        return ''
    if '\\' in value:
        value = value.rsplit('\\', 1)[-1]
    if '/' in value:
        value = value.rsplit('/', 1)[-1]
    if '@' in value:
        value = value.split('@', 1)[0]
    key = value.strip().upper()
    if re.fullmatch(r'S\d+', key):
        return key[1:]
    return key


def key_candidates(value):
    raw = str(value or '').strip()
    key = normalize_key(raw)
    out = []
    if key:
        out.append(key)
        if key.isdigit():
            out.append('S' + key)
    upper = raw.upper()
    if upper and upper not in out:
        out.append(upper)
    return out


@contextmanager
def connect_details():
    con = sqlite3.connect(str(DETAILS_DB), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=30000')
    con.execute('PRAGMA temp_store=MEMORY')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    path = Path(DETAILS_DB).resolve()
    def identity():
        return sqlite3.database_identity(path)
    if identity() is not None and identity() in _SCHEMA_IDENTITIES: return
    with _SCHEMA_LOCK:
        if identity() is not None and identity() in _SCHEMA_IDENTITIES: return
        _init_schema()
        _SCHEMA_IDENTITIES.add(identity())


def _init_schema():
    DETAILS_DB.parent.mkdir(parents=True, exist_ok=True)
    with connect_details() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA synchronous=NORMAL')
        con.execute('PRAGMA foreign_keys=ON')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS detail_meta(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS detail_imports(
          source_import_id INTEGER PRIMARY KEY,
          digest TEXT,
          name TEXT,
          imported_at TEXT,
          imported_by TEXT,
          rows_count INTEGER DEFAULT 0,
          offset_minutes INTEGER,
          activities_archived INTEGER DEFAULT 0,
          calls_archived INTEGER DEFAULT 0,
          synced_at TEXT
        );
        CREATE TABLE IF NOT EXISTS active_days(
          day TEXT NOT NULL,
          source_kind TEXT NOT NULL CHECK(source_kind IN ('export','call')),
          source_import_id INTEGER NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(day,source_kind)
        );
        CREATE TABLE IF NOT EXISTS detail_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          event_uid TEXT NOT NULL UNIQUE,
          event_source TEXT NOT NULL,
          source_label TEXT NOT NULL,
          source_import_id INTEGER,
          source_record_id TEXT,
          primary_agent_key TEXT,
          agent TEXT,
          name TEXT,
          group_id INTEGER,
          group_name TEXT,
          pc TEXT,
          ip TEXT,
          start REAL NOT NULL,
          end REAL NOT NULL,
          duration INTEGER NOT NULL DEFAULT 0,
          client TEXT,
          log_type TEXT,
          state TEXT,
          kind TEXT,
          session TEXT,
          collector TEXT,
          detail TEXT,
          raw_json TEXT NOT NULL,
          archived_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS detail_event_time ON detail_events(start,end);
        CREATE INDEX IF NOT EXISTS detail_event_page_order ON detail_events(start DESC,id DESC);
        CREATE INDEX IF NOT EXISTS detail_event_source_time ON detail_events(event_source,start);
        CREATE INDEX IF NOT EXISTS detail_event_import_time ON detail_events(source_import_id,start);
        CREATE INDEX IF NOT EXISTS detail_event_agent_time ON detail_events(primary_agent_key,start);
        CREATE INDEX IF NOT EXISTS detail_event_group_time ON detail_events(group_id,start);
        CREATE INDEX IF NOT EXISTS detail_event_client_time ON detail_events(client,start);
        CREATE TABLE IF NOT EXISTS detail_event_agents(
          event_uid TEXT NOT NULL,
          agent_key TEXT NOT NULL,
          agent TEXT,
          name TEXT,
          group_id INTEGER,
          group_name TEXT,
          pc TEXT,
          ip TEXT,
          relation TEXT,
          PRIMARY KEY(event_uid,agent_key),
          FOREIGN KEY(event_uid) REFERENCES detail_events(event_uid) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS detail_agent_key ON detail_event_agents(agent_key,event_uid);
        CREATE INDEX IF NOT EXISTS detail_agent_group ON detail_event_agents(group_id,event_uid);
        CREATE TABLE IF NOT EXISTS sync_state(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sync_runs(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          status TEXT NOT NULL,
          activities INTEGER DEFAULT 0,
          calls INTEGER DEFAULT 0,
          capture INTEGER DEFAULT 0,
          signals INTEGER DEFAULT 0,
          error TEXT
        );
        CREATE INDEX IF NOT EXISTS sync_runs_time ON sync_runs(id DESC);
        ''')
        # Invalidation transactionnelle : aucune colonne des preuves n'est changee.
        # L'epoch distingue deux bases neuves, meme si elles partagent un chemin.
        con.executescript("""
        CREATE TABLE IF NOT EXISTS detail_read_revision(
          id INTEGER PRIMARY KEY CHECK(id=1),
          epoch TEXT NOT NULL,
          version INTEGER NOT NULL CHECK(version>=0)
        );
        INSERT OR IGNORE INTO detail_read_revision(id,epoch,version)
          VALUES(1,lower(hex(randomblob(16))),0);
        """)
        for table, label in (('detail_events', 'events'), ('detail_event_agents', 'agents'),
                             ('active_days', 'days')):
            for operation in ('INSERT', 'UPDATE', 'DELETE'):
                condition = ''
                if table == 'active_days' and operation == 'UPDATE':
                    # updated_at est un suivi de sync, pas une condition de selection.
                    condition = (' WHEN OLD.day IS NOT NEW.day OR OLD.source_kind IS NOT NEW.source_kind'
                                 ' OR OLD.source_import_id IS NOT NEW.source_import_id')
                con.execute('CREATE TRIGGER IF NOT EXISTS detail_read_' + label + '_' + operation.lower()
                            + ' AFTER ' + operation + ' ON ' + table + condition
                            + ' BEGIN UPDATE detail_read_revision SET version=version+1 WHERE id=1; END')
        con.execute("INSERT OR REPLACE INTO detail_meta(key,value) VALUES('schema_version','1')")


def _load_admin(admin_db):
    result = {'groups': [], 'users': {}, 'devices': {}}
    if not sqlite3.runtime_database_available(Path(admin_db)):
        return result
    con = sqlite3.connect(str(admin_db), timeout=10)
    con.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'user_groups' in tables:
            result['groups'] = [dict(r) for r in con.execute('SELECT id,name,description FROM user_groups ORDER BY name COLLATE NOCASE')]
        directory = {}
        if 'user_directory' in tables:
            for r in con.execute('SELECT user_key,user_identifier,first_name,last_name FROM user_directory'):
                d = dict(r); directory[normalize_key(d.get('user_key') or d.get('user_identifier'))] = d
        memberships = {}
        if {'user_group_members','user_groups'}.issubset(tables):
            for r in con.execute('''SELECT m.user_key,m.user_identifier,m.group_id,g.name AS group_name
                                    FROM user_group_members m JOIN user_groups g ON g.id=m.group_id'''):
                d = dict(r); memberships[normalize_key(d.get('user_key') or d.get('user_identifier'))] = d
        for key in set(directory) | set(memberships):
            d = directory.get(key, {}); m = memberships.get(key, {})
            first = str(d.get('first_name') or '').strip(); last = str(d.get('last_name') or '').strip()
            identifier = str(d.get('user_identifier') or m.get('user_identifier') or key or '').strip()
            result['users'][key] = {
                'agent_key': key,
                'agent': identifier,
                'name': ' '.join(x for x in (first,last) if x).strip() or identifier,
                'group_id': m.get('group_id'),
                'group_name': str(m.get('group_name') or '')
            }
        if 'diagnostic' in tables:
            try:
                rows = con.execute('''WITH ranked AS (
                                  SELECT id,utilisateur,
                                         ROW_NUMBER() OVER (
                                           PARTITION BY utilisateur
                                           ORDER BY datetime(date_evenement) DESC,id DESC
                                         ) AS rn
                                  FROM diagnostic
                                  WHERE TRIM(COALESCE(utilisateur,''))<>''
                                    AND TRIM(COALESCE(ordinateur,''))<>''
                                )
                                SELECT d.utilisateur,d.ordinateur,d.adresse_ip,d.date_evenement
                                FROM ranked r
                                JOIN diagnostic d ON d.id=r.id
                                WHERE r.rn=1
                                ORDER BY datetime(d.date_evenement) DESC,d.id DESC''')
                for r in rows:
                    key = normalize_key(r['utilisateur'])
                    if key and key not in result['devices']:
                        result['devices'][key] = {'pc': r['ordinateur'] or '', 'ip': r['adresse_ip'] or '', 'last_seen': r['date_evenement'] or ''}
            except sqlite3.Error:
                log_unexpected_error('details_store._load_admin.L213')
                pass
    finally:
        con.close()
    return result


def _resolve_agent(agent, admin):
    raw = str(agent or '').strip()
    key = normalize_key(raw)
    user = None
    for cand in key_candidates(raw):
        cand_key = normalize_key(cand)
        if cand_key in admin['users']:
            user = admin['users'][cand_key]; key = cand_key; break
    user = user or {}
    dev = admin['devices'].get(key, {})
    return {
        'agent_key': key,
        'agent': raw,
        'name': user.get('name') or raw,
        'group_id': user.get('group_id'),
        'group_name': user.get('group_name') or '',
        'pc': dev.get('pc') or '',
        'ip': dev.get('ip') or ''
    }


def _insert_events(dst, items):
    events = []
    links = []
    for event, agents in items:
        events.append((
        event['event_uid'],event['event_source'],event['source_label'],event.get('source_import_id'),event.get('source_record_id'),
        event.get('primary_agent_key',''),event.get('agent',''),event.get('name',''),event.get('group_id'),event.get('group_name',''),event.get('pc',''),event.get('ip',''),
        float(event.get('start') or 0),float(event.get('end') or event.get('start') or 0),int(event.get('duration') or 0),event.get('client',''),event.get('log_type',''),
        event.get('state',''),event.get('kind',''),event.get('session',''),event.get('collector',''),event.get('detail',''),
        json.dumps(event.get('raw') or {},ensure_ascii=False,separators=(',',':'),default=str),utc_now()))
        for agent in agents:
            if agent.get('agent_key'):
                links.append((event['event_uid'], agent['agent_key'], agent.get('agent',''),
                              agent.get('name',''), agent.get('group_id'), agent.get('group_name',''),
                              agent.get('pc',''), agent.get('ip',''), agent.get('relation','linked')))
    if not events:
        return 0
    inserted = dst.executemany('''INSERT OR IGNORE INTO detail_events(
        event_uid,event_source,source_label,source_import_id,source_record_id,
        primary_agent_key,agent,name,group_id,group_name,pc,ip,start,end,duration,
        client,log_type,state,kind,session,collector,detail,raw_json,archived_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', events).rowcount
    if links:
        dst.executemany('''INSERT OR IGNORE INTO detail_event_agents(
            event_uid,agent_key,agent,name,group_id,group_name,pc,ip,relation)
            VALUES(?,?,?,?,?,?,?,?,?)''', links)
    return inserted


def _insert_event(dst, event, agents):
    return _insert_events(dst, [(event, agents)])


def _archive_rows(dst, rows, convert):
    count = 0
    batch = []
    for row in rows:
        batch.append(convert(row))
        if len(batch) >= 500:
            count += _insert_events(dst, batch)
            batch.clear()
    return count + _insert_events(dst, batch)


def _activity_event(row, admin):
    x = dict(row); a = _resolve_agent(x.get('agent'), admin)
    start = float(x.get('start') or 0); end = float(x.get('end') or start)
    event = dict(event_uid='export:'+str(x['id']),event_source='export',source_label='SIMPLIFY2',source_import_id=x.get('import_id'),source_record_id=str(x['id']),
        primary_agent_key=a['agent_key'],agent=x.get('agent') or '',name=a['name'] or x.get('name') or x.get('agent') or '',group_id=a['group_id'],group_name=a['group_name'],pc=a['pc'],ip=a['ip'],
        start=start,end=end,duration=max(0,int(round(end-start))),client=x.get('campaign') or '',log_type='Activité',state=x.get('state') or '',kind=x.get('kind') or '',session=x.get('session') or '',collector='',detail='',raw=x)
    aa=dict(a); aa['relation']='principal'; return event,[aa]


def _capture_event(row, admin):
    x = dict(row); a = _resolve_agent(x.get('agent'), admin); ts=float(x.get('start') or 0)
    event = dict(event_uid='capture:'+str(x['event_key']),event_source='capture',source_label='Capture',source_record_id=str(x['event_key']),primary_agent_key=a['agent_key'],agent=x.get('agent') or '',name=a['name'],group_id=a['group_id'],group_name=a['group_name'],pc=a['pc'],ip=a['ip'],start=ts,end=ts,duration=0,client=x.get('campaign') or '',log_type='État initial' if x.get('initial') else 'Changement état',state=x.get('state') or '',kind=x.get('kind') or '',session='',collector=x.get('source') or '',detail='Collecteur : '+str(x.get('source') or ''),raw=x)
    aa=dict(a); aa['relation']='principal'; return event,[aa]


def _signal_event(row, admin, tech_labels):
    x = dict(row); a = _resolve_agent(x.get('agent'), admin); ts=float(x.get('start') or 0); cat=str(x.get('category') or '')
    label = tech_labels.get(cat, cat or 'Signal technique')
    event = dict(event_uid='signal:'+str(x['signal_key']),event_source='signal',source_label='Signal technique',source_record_id=str(x['signal_key']),primary_agent_key=a['agent_key'],agent=x.get('agent') or '',name=a['name'],group_id=a['group_id'],group_name=a['group_name'],pc=a['pc'],ip=a['ip'],start=ts,end=ts,duration=0,client='',log_type=label,state=label,kind=cat,session='',collector=x.get('source') or '',detail=str(x.get('detail') or ''),raw=x)
    aa=dict(a); aa['relation']='principal'; return event,[aa]


def _call_event(row, admin):
    x = dict(row)
    first = str(x.get('first_agent') or '').strip(); last = str(x.get('last_agent') or '').strip()
    if first.lower() in ('0','-1','none','null'): first=''
    if last.lower() in ('0','-1','none','null'): last=''
    refs=[]
    for value,relation in ((first,'premier'),(last,'dernier')):
        if value and normalize_key(value) not in {z['agent_key'] for z in refs}:
            a=_resolve_agent(value,admin);a['relation']=relation;refs.append(a)
    primary_id=last or first;primary=_resolve_agent(primary_id,admin) if primary_id else {'agent_key':'','agent':'','name':'','group_id':None,'group_name':'','pc':'','ip':''}
    start=float(x.get('start') or 0);dur=max(0,int(float(x.get('duration') or 0)));end=start+dur
    event=dict(event_uid='call:'+str(x.get('import_id'))+':'+str(x.get('call_id')),event_source='call',source_label='Appel',source_import_id=x.get('import_id'),source_record_id=str(x.get('call_id') or ''),primary_agent_key=primary['agent_key'],agent=primary_id,name=primary['name'],group_id=primary['group_id'],group_name=primary['group_name'],pc=primary['pc'],ip=primary['ip'],start=start,end=end,duration=dur,client=x.get('campaign') or '',log_type='Appel '+str(x.get('call_type') or ''),state='Fin : '+str(x.get('end_reason') or '—'),kind=str(x.get('call_type') or ''),session=str(x.get('call_id') or ''),collector='',detail='ANI '+str(x.get('ani') or '—')+' · DNIS '+str(x.get('dnis') or '—')+' · indice '+str(x.get('indice') or '—'),raw=x)
    return event,refs


def _state_get(dst,key,default='0'):
    r=dst.execute('SELECT value FROM sync_state WHERE key=?',(key,)).fetchone()
    return r[0] if r else default


def _state_set(dst,key,value):
    dst.execute('''INSERT INTO sync_state(key,value,updated_at) VALUES(?,?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at''',(key,str(value),utc_now()))


def _refresh_directory_projection(dst, admin):
    """Current name/group are a projection; raw payloads and device evidence stay intact."""
    current={k:{f:v.get(f) for f in ('name','group_id','group_name')} for k,v in admin['users'].items()}
    previous=json.loads(_state_get(dst,'directory_projection','{}'))
    for key in set(previous)|set(current):
        if previous.get(key)==current.get(key):continue
        value=current.get(key,{})
        name=value.get('name');group=value.get('group_id');label=value.get('group_name') or ''
        dst.execute("""UPDATE detail_events SET name=COALESCE(?,NULLIF(json_extract(raw_json,'$.name'),''),agent),
                       group_id=?,group_name=? WHERE primary_agent_key=?""",(name,group,label,key))
        dst.execute("""UPDATE detail_event_agents SET name=COALESCE(?,agent),group_id=?,group_name=?
                       WHERE agent_key=?""",(name,group,label,key))
    _state_set(dst,'directory_projection',json.dumps(current,ensure_ascii=False,sort_keys=True))


def _sqlite_storage_revision(path):
    """Cheap revision for a SQLite database including uncheckpointed WAL writes."""
    base = Path(path)
    out = []
    for candidate in (base, Path(str(base) + '-wal')):
        try:
            st = candidate.stat()
            out.append((candidate.name, int(st.st_mtime_ns), int(st.st_size)))
        except FileNotFoundError:
            out.append((candidate.name, 0, 0))
    return tuple(out)


def sync_from_sources(supervision_db, admin_db, tech_labels=None, force=False, import_ids=None):
    if not force and not _SYNC_LOCK.acquire(blocking=False):
        return dict(ok=True, pending=True, path=str(DETAILS_DB))
    try:
        return _sync_from_sources(supervision_db, admin_db, tech_labels, force, import_ids)
    finally:
        if not force: _SYNC_LOCK.release()


def _sync_from_sources(supervision_db, admin_db, tech_labels=None, force=False, import_ids=None):
    global _LAST_SYNC_AT,_LAST_SYNC_RESULT
    tech_labels = tech_labels or {}
    with _SYNC_LOCK:
        admin_storage_revision=None if sqlite3.postgres_enabled() else _sqlite_storage_revision(admin_db)
        # Live publication can call this every two seconds. Avoid rebuilding the
        # complete administration projection during the five-second debounce
        # when neither the DB nor its WAL changed.
        if not force and admin_storage_revision is not None and _LAST_SYNC_RESULT is not None and _LAST_SYNC_RESULT.get('admin_storage_revision')==admin_storage_revision and _LAST_SYNC_RESULT.get('path')==str(DETAILS_DB) and time.time()-_LAST_SYNC_AT < 5:
            return _LAST_SYNC_RESULT
        admin=_load_admin(admin_db)
        directory_revision=fingerprint(admin['users'])
        if not force and _LAST_SYNC_RESULT is not None and _LAST_SYNC_RESULT.get('directory_revision')==directory_revision and _LAST_SYNC_RESULT.get('path')==str(DETAILS_DB) and time.time()-_LAST_SYNC_AT < 5:
            return _LAST_SYNC_RESULT
        init(); started=utc_now();counts={'activities':0,'calls':0,'capture':0,'signals':0}
        src=sqlite3.connect(str(supervision_db),timeout=30);src.row_factory=sqlite3.Row
        try:
            with connect_details() as dst:
                if getattr(dst, 'schema', None) == 'details':
                    locked = dst.execute('SELECT pg_try_advisory_xact_lock(781205831)').fetchone()[0]
                    if not locked:
                        return dict(ok=False, pending=True, path=str(DETAILS_DB))
                run=dst.execute("INSERT INTO sync_runs(started_at,status) VALUES(?,'RUNNING')",(started,)).lastrowid
                try:
                    _refresh_directory_projection(dst,admin)
                    # Keep the active daily reference in the archive. Old event rows remain preserved.
                    _sync_active_days(dst, src, utc_now())

                    # Imports are immutable except phone-call enrichment on a duplicate retry.
                    selected_ids=sorted({int(x) for x in (import_ids or []) if x is not None})
                    if selected_ids:
                        marks=','.join('?'*len(selected_ids))
                        imports=[dict(r) for r in src.execute('SELECT * FROM imports WHERE id IN ('+marks+') ORDER BY id',selected_ids)]
                        call_counts={int(r['import_id']):int(r['rows_count'] or 0) for r in src.execute('SELECT import_id,rows_count FROM call_imports WHERE import_id IN ('+marks+')',selected_ids)}
                    else:
                        imports=[dict(r) for r in src.execute('SELECT * FROM imports ORDER BY id')]
                        call_counts={int(r['import_id']):int(r['rows_count'] or 0) for r in src.execute('SELECT import_id,rows_count FROM call_imports')}
                    for imp in imports:
                        import_id=int(imp['id'])
                        # Immutable import manifest already records the exact inserted count.
                        act_count=int(imp['rows_count'] or 0)
                        call_count=int(call_counts.get(import_id,0))
                        old=dst.execute('SELECT * FROM detail_imports WHERE source_import_id=?',(import_id,)).fetchone()
                        old_act=int(old['activities_archived'] or 0) if old else 0;old_call=int(old['calls_archived'] or 0) if old else 0
                        if old and old_act==act_count and old_call==call_count and all(
                            old[k]==imp.get(k) for k in ('digest','name','imported_at','imported_by','offset_minutes')):
                            continue
                        if old_act < act_count:
                            rows = src.execute('SELECT id,import_id,agent,name,start,end,state,kind,campaign,session FROM activities WHERE import_id=? ORDER BY id',(import_id,))
                            counts['activities'] += _archive_rows(dst, rows, lambda row: _activity_event(row, admin))
                        if old_call < call_count:
                            rows = src.execute('''SELECT import_id,call_id,indice,start,call_type,duration,conversation,wait,ani,dnis,outtel,outdialed,first_agent,last_agent,campaign,end_reason,no_agent,abandon,closed,end_by_agent
                                                  FROM phone_calls WHERE import_id=? ORDER BY start,call_id''',(import_id,))
                            counts['calls'] += _archive_rows(dst, rows, lambda row: _call_event(row, admin))
                        dst.execute('''INSERT INTO detail_imports(source_import_id,digest,name,imported_at,imported_by,rows_count,offset_minutes,activities_archived,calls_archived,synced_at)
                                       VALUES(?,?,?,?,?,?,?,?,?,?)
                                       ON CONFLICT(source_import_id) DO UPDATE SET digest=excluded.digest,name=excluded.name,imported_at=excluded.imported_at,
                                       imported_by=excluded.imported_by,rows_count=excluded.rows_count,offset_minutes=excluded.offset_minutes,
                                       activities_archived=excluded.activities_archived,calls_archived=excluded.calls_archived,synced_at=excluded.synced_at''',
                                    (import_id,imp.get('digest'),imp.get('name'),imp.get('imported_at'),imp.get('imported_by'),imp.get('rows_count') or act_count,imp.get('offset_minutes'),act_count,call_count,utc_now()))

                    # SQLite used rowid as a durable insertion cursor. PostgreSQL
                    # has no rowid, so the production schema adds an identity ingest_seq
                    # to the two append-only source tables. This preserves incremental
                    # Details sync even when event timestamps arrive out of order.
                    if getattr(src, 'schema', None) == 'supervision':
                        last_live=int(_state_get(dst,'live_ingest_seq','0') or 0);max_live=last_live
                        for r in src.execute('SELECT ingest_seq AS _rowid,event_key,source,agent,start,state,kind,campaign,initial FROM live_events WHERE ingest_seq>? ORDER BY ingest_seq',(last_live,)):
                            e,aa=_capture_event(r,admin);counts['capture']+=_insert_event(dst,e,aa);max_live=max(max_live,int(r['_rowid']))
                        _state_set(dst,'live_ingest_seq',max_live)
                        last_sig=int(_state_get(dst,'signal_ingest_seq','0') or 0);max_sig=last_sig
                        for r in src.execute('SELECT ingest_seq AS _rowid,signal_key,source,agent,start,category,detail FROM technical_signals WHERE ingest_seq>? ORDER BY ingest_seq',(last_sig,)):
                            e,aa=_signal_event(r,admin,tech_labels);counts['signals']+=_insert_event(dst,e,aa);max_sig=max(max_sig,int(r['_rowid']))
                        _state_set(dst,'signal_ingest_seq',max_sig)
                    else:
                        last_live=int(_state_get(dst,'live_rowid','0') or 0);max_live=last_live
                        for r in src.execute('SELECT rowid AS _rowid,event_key,source,agent,start,state,kind,campaign,initial FROM live_events WHERE rowid>? ORDER BY rowid',(last_live,)):
                            e,aa=_capture_event(r,admin);counts['capture']+=_insert_event(dst,e,aa);max_live=max(max_live,int(r['_rowid']))
                        _state_set(dst,'live_rowid',max_live)
                        last_sig=int(_state_get(dst,'signal_rowid','0') or 0);max_sig=last_sig
                        for r in src.execute('SELECT rowid AS _rowid,signal_key,source,agent,start,category,detail FROM technical_signals WHERE rowid>? ORDER BY rowid',(last_sig,)):
                            e,aa=_signal_event(r,admin,tech_labels);counts['signals']+=_insert_event(dst,e,aa);max_sig=max(max_sig,int(r['_rowid']))
                        _state_set(dst,'signal_rowid',max_sig)
                    # V60: Live has its own daily SQLite database and is never
                    # merged into historical Details. Historical capture/signals
                    # above are only the durable supervision/import sources.
                    dst.execute('UPDATE sync_runs SET finished_at=?,status=?,activities=?,calls=?,capture=?,signals=? WHERE id=?',(utc_now(),'OK',counts['activities'],counts['calls'],counts['capture'],counts['signals'],run))
                except Exception as exc:
                    log_unexpected_error('details_store.sync_from_sources.L361')
                    dst.rollback()
                    try:
                        dst.execute('INSERT INTO sync_runs(started_at,finished_at,status,error) VALUES(?,?,?,?)',
                                    (started,utc_now(),'ERROR',str(exc)[:2000]))
                        dst.commit()
                    except Exception:
                        dst.rollback()
                        log_unexpected_error('details_store.sync_failure_record')
                    raise
        finally:
            src.close()
        _LAST_SYNC_AT=time.time();_LAST_SYNC_RESULT=dict(ok=True,path=str(DETAILS_DB),directory_revision=directory_revision,admin_storage_revision=admin_storage_revision,**counts)
        return _LAST_SYNC_RESULT


def _day_bounds(day, offset_minutes=None):
    return france_day_bounds(day)


def _display(ts,offset_minutes=None):
    return france_display(ts)


def _base_day_where(con,day,a,b):
    exp=con.execute("SELECT source_import_id FROM active_days WHERE day=? AND source_kind='export'",(day,)).fetchone()
    call=con.execute("SELECT source_import_id FROM active_days WHERE day=? AND source_kind='call'",(day,)).fetchone()
    terms=[];params=[]
    if exp:
        terms.append("(e.event_source='export' AND e.source_import_id=? AND e.start<? AND e.end>?)");params.extend([exp[0],b,a])
    if call:
        terms.append("(e.event_source='call' AND e.source_import_id=? AND e.start>=? AND e.start<?)");params.extend([call[0],a,b])
    terms.append("(e.event_source IN ('capture','signal') AND e.start>=? AND e.start<?)");params.extend([a,b])
    return '('+' OR '.join(terms)+')',params


def _query_filters(qs,cfg,latest):
    raw={str(k):[str(x) for x in v] for k,v in dict(qs or {}).items()}
    legacy_source=str((raw.get('source') or [''])[0] or '').strip().lower()
    if legacy_source not in ('','export','capture','signal','call'):
        raise ValueError('Source de logs invalide.')
    norm_input=dict(raw)
    if legacy_source in ('signal','call'):norm_input.pop('source',None)
    query,common,days,_=normalize_filters(norm_input,cfg,default_date_from=latest,default_date_to=latest,default_full_day='0')
    client=str((raw.get('client') or [''])[0] or '').strip();search=str((raw.get('q') or [''])[0] or '').strip().lower()
    try:page=max(0,int(str((raw.get('page') or ['0'])[0] or 0)))
    except ValueError:raise ValueError('Page invalide.')
    try:page_size=max(25,min(250,int(str((raw.get('page_size') or ['100'])[0] or 100))))
    except ValueError:raise ValueError('Taille de page invalide.')
    exact_agents=sorted({normalize_key(x) for x in raw.get('include_agent',[]) if normalize_key(x)})
    if len(raw.get('agent',[]))>1:
        exact_agents=sorted(set(exact_agents)|{normalize_key(x) for x in raw.get('agent',[]) if normalize_key(x)})
        common['agent']=''
    return query,common,days,legacy_source,client,search,page,page_size,exact_agents


def _range_terms(con, days, cfg, query):
    """Build range predicates without one active_days lookup per day/source.

    V60.3 executed two SELECTs against active_days for every selected day and
    did the same work again for Details metadata. Production traces showed
    39-49 SQL statements for a single Details request before the heavy query
    even started. Fetch the tiny pointer set once and build all windows in
    memory; event semantics stay unchanged.
    """
    windows = defaultdict(list)
    refs={}
    if days:
        for row in con.execute(
            'SELECT day,source_kind,source_import_id FROM active_days WHERE day>=? AND day<=?',
            (days[0],days[-1])):
            refs[(str(row['day']),str(row['source_kind']))]=row['source_import_id']
    for day in days:
        a, b = selected_bounds(day, cfg, query, '0')
        for source in ('export', 'call'):
            import_id=refs.get((day,source))
            if import_id is not None:
                windows[(source, import_id)].append((a, b))
        windows[('live', None)].append((a, b))
    terms = []; params = []; upper = None
    for (source, import_id), ranges in windows.items():
        merged = []
        for a, b in sorted(ranges):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        for a, b in merged:
            upper = b if upper is None else max(upper, b)
            if source == 'export':
                original = sorted(set((lo, hi) for lo, hi in ranges if lo >= a and hi <= b))
                if len(original) == 1:
                    terms.append("(e.event_source='export' AND e.source_import_id=? AND e.start<? AND e.end>?)")
                    params.extend((import_id, b, a))
                else:
                    exact = ' OR '.join('(e.start<? AND e.end>?)' for _ in original)
                    terms.append("(e.event_source='export' AND e.source_import_id=? AND e.start<? AND e.end>? AND (e.end>e.start OR (" + exact + ")))" )
                    params.extend((import_id, b, a))
                    for lo, hi in original:
                        params.extend((hi, lo))
            elif source == 'call':
                terms.append("(e.event_source='call' AND e.source_import_id=? AND e.start>=? AND e.start<?)")
                params.extend((import_id, a, b))
            else:
                terms.append("(e.event_source IN ('capture','signal') AND e.start>=? AND e.start<?)")
                params.extend((a, b))
    return terms, params, upper

def _base_range_where(con, days, cfg, query):
    terms, params, upper = _range_terms(con, days, cfg, query)
    if not terms:
        return '(0)', []
    # Borne SUPERIEURE seulement : un export peut commencer avant le premier jour.
    return '(e.start<? AND (' + ' OR '.join(terms) + '))', [upper] + params


def _details_exclusion_ranges(days,query):
    ranges=[]
    for start_min,end_min,_ in _support_excluded_slots(query):
        start_label=f"{start_min//60:02d}:{start_min%60:02d}"
        end_label='24:00' if end_min==24*60 else f"{end_min//60:02d}:{end_min%60:02d}"
        for day in days:
            a,b=france_day_bounds(day,start_label,end_label)
            ranges.append((a,b))
    return ranges


def _details_call_context_sql(scope):
    if scope=='all':return '',[]
    during="""EXISTS(
      SELECT 1 FROM detail_events ce
      WHERE ce.event_uid<>e.event_uid
        AND (
          (ce.event_source='call' AND ce.start<=e.start+2 AND ce.end>=e.start-2 AND
             EXISTS(SELECT 1 FROM detail_event_agents ca WHERE ca.event_uid=ce.event_uid AND ca.agent_key=e.primary_agent_key))
          OR
          (ce.event_source='export' AND LOWER(COALESCE(ce.kind,''))='call' AND ce.primary_agent_key=e.primary_agent_key
             AND ce.start<=e.start+2 AND ce.end>=e.start-2)
          OR
          (ce.event_source='signal' AND LOWER(COALESCE(ce.kind,''))='disconnect_call' AND ce.primary_agent_key=e.primary_agent_key
             AND ABS(ce.start-e.start)<=15)
        )
    )"""
    return (during if scope=='during' else 'NOT '+during),[]

def _governance_for_detail_row(r, display_offset, policies, declarations, calendar=None):
    time_text=_display(r.get('start') or 0,display_offset)
    evt={'agent':r.get('agent'),'name':r.get('name'),'group_id':r.get('group_id'),'group_name':r.get('group_name'),
         'day':time_text[:10],'hour':time_text[11:16],'start_text':time_text,
         'seconds':max(0,int(r.get('duration') or max(0,(r.get('end') or 0)-(r.get('start') or 0)))),
         'event_label':r.get('state') or r.get('kind') or r.get('log_type') or 'Événement technique'}
    if calendar is not None and not calendar.may_apply(evt):
        return calendar.empty_event(evt)
    return apply_event_governance(evt,'details',policies,declarations)


def _decorate_detail_row(r, linked, display_offset, policies, declarations, governance=None):
    r=dict(r);linked=linked or []
    r['log_id']=r['event_uid'];r['source']=r['event_source'];r['time_text']=_display(r['start'],display_offset);r['end_text']=_display(r['end'],display_offset) if r['duration'] else ''
    # Reutiliser la decision exacte de selection ; les autres appelants restent compatibles.
    pd=governance if governance is not None else _governance_for_detail_row(r,display_offset,policies,declarations)
    r['policy_decision']=pd.get('policy_decision');r['policy_reason']=pd.get('policy_reason');r['policy_applied']=pd.get('policy_applied',False)
    r['declaration_decision']=pd.get('declaration_decision');r['declaration_reason']=pd.get('declaration_reason');r['declaration_applied']=pd.get('declaration_applied',False)
    r['governance_reason']=pd.get('governance_reason','');r['governance_exclude_statistics']=pd.get('governance_exclude_statistics',False)
    r['governance_exclude_lost_time']=pd.get('governance_exclude_lost_time',False);r['governance_exclude_score']=pd.get('governance_exclude_score',False)
    for key,value in pd.items():
        if key.startswith('governance_'):
            r[key]=value
    refs=[x.get('agent') or '' for x in linked if x.get('agent')]
    fields={'ID log':r['event_uid'],'Source':r['source_label'],'Début':r['time_text'],'Fin':r['end_text'],'Durée (secondes)':r['duration'],
            'Agent principal':r.get('agent') or '','Agents liés':' / '.join(refs),'Nom':r.get('name') or '','Groupe':r.get('group_name') or 'Non affecté',
            'PC':r.get('pc') or '','IP':r.get('ip') or '','Client / campagne':r.get('client') or '','Type de log':r.get('log_type') or '',
            'État':r.get('state') or '','Type interne':r.get('kind') or '','Session / Call ID':r.get('session') or '','Collecteur':r.get('collector') or '',
            'Détail':r.get('detail') or '','Import source':r.get('source_import_id') if r.get('source_import_id') is not None else '',
            'ID source':r.get('source_record_id') or ''}
    if r.get('policy_applied') or r.get('declaration_applied'):
        fields['Durée exclue par gouvernance (secondes)']=pd['governance_excluded_seconds']
        fields['Durée retenue (secondes)']=pd['governance_effective_seconds']
        fields['Version du calcul']=pd['governance_contract_version']
    if r.get('policy_applied'):
        fields['Policies appliquées']=r.get('policy_reason') or '';fields['Décision Policy']=json.dumps(r.get('policy_decision') or {},ensure_ascii=False)
    if r.get('declaration_applied'):
        fields['Déclarations appliquées']=r.get('declaration_reason') or '';fields['Décision Déclaration']=json.dumps(r.get('declaration_decision') or {},ensure_ascii=False)
    try:raw=json.loads(r.get('raw_json') or '{}')
    except Exception:
        log_unexpected_error('details_store._decorate_detail_row');raw={'raw_json':r.get('raw_json') or ''}
    for k,v in raw.items():fields['Source · '+str(k)]=v
    r['fields']=fields
    for k in ('raw_json','event_source','source_record_id','primary_agent_key','archived_at'):r.pop(k,None)
    return r


def incident_evidence(qs,supervision_db,admin_db,display_offset,tech_labels=None):
    # Bridge one calculated disconnect to nearby raw detail archive rows.
    # The disconnect panel requests source=export (SIMPLIFY2). Keep a missing
    # source neutral for existing callers; filter in SQL BEFORE the 60-row cap.
    try:sync_from_sources(supervision_db,admin_db,tech_labels or {})
    except Exception:log_unexpected_error('details_store.incident_evidence.sync')
    init()
    get=lambda k,d='':str((qs.get(k) or [d])[0] or d)
    agent=get('agent').strip()
    try:start=float(get('start','0'));end=float(get('end',str(start)))
    except ValueError:raise ValueError('Incident invalide.')
    if not agent or start<=0:raise ValueError('Agent et heure de coupure requis.')
    if end<start:end=start
    key=normalize_key(agent);window_start=start-90;window_end=max(end,start+1)+90
    source=get('source').strip()
    if source not in ('','export','capture','signal','call'):
        raise ValueError('Source de logs invalide.')
    query='''SELECT e.* FROM detail_events e
        WHERE e.start<? AND (CASE WHEN e.end>e.start THEN e.end ELSE e.start+1 END)>?
          AND (e.primary_agent_key=? OR EXISTS(SELECT 1 FROM detail_event_agents a WHERE a.event_uid=e.event_uid AND a.agent_key=?))'''
    params=[window_end,window_start,key,key]
    if source:
        query+=' AND e.event_source=?'
        params.append(source)
    query+=' ORDER BY ABS(e.start-?) ASC,e.start ASC,e.id ASC LIMIT 60'
    params.append(start)
    with connect_details() as con:
        rows=[dict(r) for r in con.execute(query,params)]
        uids=[r['event_uid'] for r in rows];linked=defaultdict(list)
        if uids:
            marks=','.join('?' for _ in uids)
            for a in con.execute(f'SELECT * FROM detail_event_agents WHERE event_uid IN ({marks}) ORDER BY event_uid,relation,agent',uids):linked[a['event_uid']].append(dict(a))
        policies=load_policies();declarations=load_declarations(_display(start,display_offset)[:10],_display(end or start,display_offset)[:10])
        out=[_decorate_detail_row(r,linked.get(r['event_uid'],[]),display_offset,policies,declarations) for r in rows]
    return {'agent':agent,'start':start,'end':end,'count':len(out),'rows':out}


def _sync_active_days(dst, src, stamp):
    """Meme miroir actif et horodatage, sans supprimer/recreer les liens inchanges.

    Seuls les jours absents des couvertures sont retires du miroir ; les preuves
    restent intactes. Le journal de synchronisation continue d'etre ecrit.
    """
    desired = {}
    for source, table in (('export', 'coverage'), ('call', 'call_coverage')):
        for row in src.execute('SELECT day,import_id FROM ' + table):
            desired[(row['day'], source)] = row['import_id']
    for row in dst.execute('SELECT day,source_kind FROM active_days').fetchall():
        if (row['day'], row['source_kind']) not in desired:
            dst.execute('DELETE FROM active_days WHERE day=? AND source_kind=?',
                        (row['day'], row['source_kind']))
    for (day, source), import_id in desired.items():
        dst.execute("""INSERT INTO active_days(day,source_kind,source_import_id,updated_at)
                    VALUES(?,?,?,?) ON CONFLICT(day,source_kind) DO UPDATE SET
                    source_import_id=excluded.source_import_id,updated_at=excluded.updated_at""",
                    (day, source, import_id, stamp))


def _read_cache_key(con, namespace, inputs):
    """Cle liee a l'instantane, jamais a MAX(id) ni a un horodatage de fichier.

    Le droit Détails actuel est global par module, verifie par la route AVANT
    l'appel. Les filtres SQL exacts isolent groupes/agents/sources. Les selecteurs
    bruts restent intentionnellement globaux comme en V56.7. Toute future ACL
    par ligne doit etre exprimee dans ces predicats avant consultation du cache.
    Pas de cache si l'appelant n'a pas ouvert une transaction de lecture.
    """
    # This cache key intentionally depends on a SQLite file identity.
    # PostgreSQL has no equivalent local database file, so keep the exact
    # query path and simply bypass this optional cache in PostgreSQL mode.
    if getattr(con, 'schema', None) == 'details':
        revision = con.execute('SELECT epoch,version FROM detail_read_revision WHERE id=1').fetchone()
        return ('details/pg/v1', sqlite3.database_identity(DETAILS_DB), namespace,
                revision[0], revision[1], fingerprint(inputs)) if revision else None
    if not con.in_transaction:
        return None
    try:
        revision = con.execute('SELECT epoch,version FROM detail_read_revision WHERE id=1').fetchone()
        path = next(row[2] for row in con.execute('PRAGMA database_list') if row[1] == 'main')
        if not revision or not path:
            return None
        identity = Path(path).stat()
        digest = fingerprint(inputs)
        return ('details/module-global/v1', namespace, str(Path(path).resolve()),
                identity.st_dev, identity.st_ino, revision[0], revision[1], digest)
    except (sqlite3.Error, OSError, TypeError, ValueError, StopIteration):
        # La projection est facultative : le chemin exact continue sans cache.
        return None


def _cache_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _detail_rows_by_ids(con, ids):
    if not ids:
        return []
    marks = ','.join('?' for _ in ids)
    return [dict(row) for row in con.execute('SELECT e.* FROM detail_events e WHERE e.id IN ('
            + marks + ') ORDER BY e.start DESC,e.id DESC', list(ids))]


def _read_details_metadata(con, where_sql, params):
    """Trois requetes independantes de la page ; annuaire admin NON mis en cache."""
    key = _read_cache_key(con, 'metadata-v1', (where_sql, params))
    cached = _READ_CACHE.get(key)
    if cached is not None:
        return json.loads(cached[0])
    clients = [r[0] for r in con.execute('SELECT DISTINCT e.client FROM detail_events e WHERE '
        + where_sql + " AND TRIM(COALESCE(e.client,''))<>'' ORDER BY e.client COLLATE NOCASE", params)]
    agents = [dict(r) for r in con.execute("""SELECT ea.agent_key,MAX(ea.agent) AS agent,MAX(ea.name) AS name,
              MAX(ea.group_id) AS group_id,MAX(ea.group_name) AS group_name,MAX(ea.pc) AS pc,MAX(ea.ip) AS ip
              FROM detail_event_agents ea JOIN detail_events e ON e.event_uid=ea.event_uid
              WHERE """ + where_sql + ' GROUP BY ea.agent_key ORDER BY MAX(ea.name) COLLATE NOCASE,MAX(ea.agent) COLLATE NOCASE', params)]
    clients_by_agent = defaultdict(list)
    for row in con.execute("""SELECT ea.agent_key,e.client FROM detail_event_agents ea
              JOIN detail_events e ON e.event_uid=ea.event_uid WHERE """ + where_sql
              + " AND TRIM(COALESCE(e.client,''))<>'' GROUP BY ea.agent_key,e.client ORDER BY ea.agent_key,e.client COLLATE NOCASE", params):
        clients_by_agent[row['agent_key']].append(row['client'])
    result = (clients, agents, dict(clients_by_agent))
    if key is not None:
        _READ_CACHE.put(key, _cache_json(result))
    return result



def _configured_details_metadata(shared_admin, devices=None, page_rows=None, selected_client=''):
    """Fast filter catalogue from the configured ACTIVE file/campaign scope.

    The historical implementation rebuilt clients + agents + agent/client links
    by grouping the detail archive (1.84M rows in production) on every cold
    Details request.  That metadata is not a KPI and does not need to rescan raw
    evidence.  Reuse Nelyio's canonical configured File -> ACTIVE Agent scope.
    Raw detail rows remain authoritative for the actual journal query.
    """
    from quality_scope import load_quality_file_scope
    scope=load_quality_file_scope()
    campaigns=scope.get('campaigns') or {}
    def campaign_label(cid):
        item=campaigns.get(str(cid),{}) if isinstance(campaigns,dict) else {}
        return str(item.get('campaign_name') or item.get('display_name') or cid or '').strip()
    line_clients={}
    all_clients=set()
    for q in scope.get('queues') or []:
        labels={campaign_label(cid) for cid in (q.get('campaign_ids') or [])}
        labels={x for x in labels if x}
        try:lid=int(q.get('line_id') or 0)
        except (TypeError,ValueError):lid=0
        if lid:line_clients[lid]=labels
        all_clients.update(labels)
    clients_by_agent={}
    for agent,lines in (scope.get('agent_files') or {}).items():
        labels=set()
        for lid in lines or []:
            try:lid=int(lid)
            except (TypeError,ValueError):continue
            labels.update(line_clients.get(lid,set()))
        clients_by_agent[canonical_admin_key(agent)]=sorted(labels,key=str.casefold)
    # Keep currently visible/historical labels selectable even when they no
    # longer exist in the current configuration snapshot.
    for row in page_rows or ():
        client=str(row.get('client') or '').strip()
        if client:all_clients.add(client)
    if str(selected_client or '').strip():all_clients.add(str(selected_client).strip())
    roster=build_agent_roster({},shared_admin,devices or {},exclude_support=False)
    for row in roster:
        row['clients']=clients_by_agent.get(canonical_admin_key(row.get('agent')),[])
    return sorted(all_clients,key=str.casefold),roster,clients_by_agent

def _select_details_page(con, where_sql, params, offset, page_size, display_offset,
                         policies, declarations, include_excluded):
    """Total exact et projection ordonnee reutilisables entre pages.

    Premiere lecture : algorithme V56.7, plus les identifiants visibles (8 octets
    chacun, plafond explicite). Lectures suivantes du MEME instantane/regles :
    charger la page par ces identifiants, puis redecorer ses preuves. Aucun JSON
    brut ni decision d'agent n'est partage. Une ecriture invalide la projection.
    """
    active = not include_excluded and bool(policies or declarations)
    key = _read_cache_key(con, 'selection-v1',
                          (where_sql, params, display_offset, active, policies, declarations))
    cached = _READ_CACHE.get(key)
    if cached is not None:
        total, counts, clients = json.loads(cached[0])
        if active:
            ids = array('q')
            ids.frombytes(cached[1][offset*ids.itemsize:(offset+page_size)*ids.itemsize])
            rows = _detail_rows_by_ids(con, ids)
        else:
            rows = [dict(r) for r in con.execute('SELECT e.* FROM detail_events e INDEXED BY detail_event_page_order WHERE '
                    + where_sql + ' ORDER BY e.start DESC,e.id DESC LIMIT ? OFFSET ?', list(params)+[page_size,offset])]
        return total, rows, counts, set(clients), {}
    total=0;counts=defaultdict(int);clients=set();decisions={}
    projected = array('q') if key is not None and active else None
    if not active:
        for rec in con.execute('SELECT e.event_source,e.client,COUNT(*) AS n FROM detail_events e WHERE '+where_sql+' GROUP BY e.event_source,e.client',params):
            n=int(rec['n']);total+=n;counts[rec['event_source'] or '']+=n
            if str(rec['client'] or '').strip():clients.add(str(rec['client']))
        rows=[dict(r) for r in con.execute('SELECT e.* FROM detail_events e INDEXED BY detail_event_page_order WHERE '+where_sql+' ORDER BY e.start DESC,e.id DESC LIMIT ? OFFSET ?',list(params)+[page_size,offset])]
    else:
        calendar = DetailsGovernanceCalendar(policies, declarations)
        policies = calendar.policies; declarations = calendar.declarations
        columns='e.id,e.event_source,e.client,e.agent,e.name,e.group_id,e.group_name,e.start,e.end,e.duration,e.state,e.kind,e.log_type'
        ids=[]
        for rec in con.execute('SELECT '+columns+' FROM detail_events e WHERE '+where_sql+' ORDER BY e.start DESC,e.id DESC',params):
            pd=_governance_for_detail_row(dict(rec),display_offset,policies,declarations,calendar)
            if pd.get('governance_exclude_statistics'):
                continue
            counts[rec['event_source'] or '']+=1
            if str(rec['client'] or '').strip():clients.add(str(rec['client']))
            if projected is not None:
                if len(projected) >= _MAX_PROJECTED_IDS:
                    projected = None  # Pas de projection tronquee, calcul exact maintenu.
                else:
                    projected.append(rec['id'])
            if offset<=total<offset+page_size:
                ids.append(rec['id']);decisions[rec['id']]=calendar.detach(pd)
            total+=1
        rows = _detail_rows_by_ids(con, ids)
    if key is not None and (not active or projected is not None):
        _READ_CACHE.put(key, _cache_json((total, dict(counts), sorted(clients))),
                        projected.tobytes() if active else b'')
    return total,rows,counts,clients,decisions


def details_view(qs,supervision_db,admin_db,display_offset,tech_labels=None,cfg=None):
    # PERF1: reads must never perform a potentially heavy synchronization in
    # external-services mode. Imports and the Live worker maintain the archive.
    # This removes PostgreSQL write contention from the HTTP request path.
    sync_error='';sync_state={}
    try:
        from service_mode import external_services_enabled
        external = external_services_enabled()
    except Exception:
        external = False
    if external:
        sync_state={'delegated':True,'pending':False}
    else:
        try:sync_state=sync_from_sources(supervision_db,admin_db,tech_labels or {})
        except Exception as exc:
            log_unexpected_error('details_store.details_view.sync');sync_error=str(exc)
    init();admin=_load_admin(admin_db);cfg=cfg or {'display_offset':display_offset,'work_start':'08:00','work_end':'19:00'}
    with connect_details() as con:
        # Une reponse voit un seul instantane Details (WAL) : total, page,
        # donnees brutes, liens et filtres. Les ecritures live restent permises.
        # Les bases admin/live sont distinctes : pas de snapshot interbases garanti.
        sqlite3.begin_read_snapshot(con)
        latest=con.execute("SELECT MAX(day) FROM active_days WHERE source_kind='export'").fetchone()[0]
        from collection_store import latest_day as latest_live_day
        latest=latest_live_day(latest) or france_today()
        query,common,days,source,client,search,page,page_size,agents=_query_filters(qs,cfg,latest)
        base,base_params=_base_range_where(con,days,cfg,query);where=[base];params=list(base_params)
        if source:
            where.append('e.event_source=?');params.append(source)
        groups=[str(x) for x in common.get('groups',[]) if str(x)]
        if groups:
            from analysis_groups import selected_group_members
            members=sorted(selected_group_members(groups) or [])
            if members:
                marks=','.join('?' for _ in members)
                where.append(f'EXISTS(SELECT 1 FROM detail_event_agents ga WHERE ga.event_uid=e.event_uid AND ga.agent_key IN ({marks}))')
                params.extend(members)
            else:
                where.append('FALSE')
        if agents:
            marks=','.join('?' for _ in agents);where.append(f'EXISTS(SELECT 1 FROM detail_event_agents aa WHERE aa.event_uid=e.event_uid AND aa.agent_key IN ({marks}))');params.extend(agents)
        agent_term=str(common.get('agent') or '').strip().lower()
        if agent_term:
            term='%'+agent_term+'%'
            where.append('''(LOWER(COALESCE(e.agent,'')) LIKE ? OR LOWER(COALESCE(e.name,'')) LIKE ? OR LOWER(COALESCE(e.pc,'')) LIKE ?
                            OR EXISTS(SELECT 1 FROM detail_event_agents xa WHERE xa.event_uid=e.event_uid AND
                              (LOWER(COALESCE(xa.agent,'')) LIKE ? OR LOWER(COALESCE(xa.name,'')) LIKE ? OR LOWER(COALESCE(xa.pc,'')) LIKE ?)))''')
            params.extend([term]*6)
        if client:
            where.append("LOWER(COALESCE(e.client,''))=LOWER(?)");params.append(client)
        min_disconnect=float(common.get('min_disconnect') or 0)
        if min_disconnect>0:
            where.append("(LOWER(COALESCE(e.kind,''))<>'offline' OR COALESCE(e.duration,0)>=?)");params.append(min_disconnect)
        exclusion_ranges=_details_exclusion_ranges(days,query)
        if exclusion_ranges:
            overlap=[]
            for slot_start,slot_end in exclusion_ranges:
                overlap.append("(e.start<? AND (CASE WHEN e.end>e.start THEN e.end ELSE e.start+1 END)>?)")
                params.extend([slot_end,slot_start])
            where.append('NOT ('+' OR '.join(overlap)+')')
        call_scope=str(common.get('call_scope') or 'all')
        if call_scope!='all':
            # A context filter is meaningful only for disconnect rows in Détails.
            where.append("LOWER(COALESCE(e.kind,''))='offline'")
            context_sql,context_params=_details_call_context_sql(call_scope)
            where.append(context_sql);params.extend(context_params)
        if search:
            term='%'+search+'%'
            where.append('''(LOWER(COALESCE(e.agent,'')) LIKE ? OR LOWER(COALESCE(e.name,'')) LIKE ? OR LOWER(COALESCE(e.group_name,'')) LIKE ?
                            OR LOWER(COALESCE(e.pc,'')) LIKE ? OR LOWER(COALESCE(e.ip,'')) LIKE ? OR LOWER(COALESCE(e.client,'')) LIKE ?
                            OR LOWER(COALESCE(e.source_label,'')) LIKE ? OR LOWER(COALESCE(e.log_type,'')) LIKE ? OR LOWER(COALESCE(e.state,'')) LIKE ?
                            OR LOWER(COALESCE(e.kind,'')) LIKE ? OR LOWER(COALESCE(e.session,'')) LIKE ? OR LOWER(COALESCE(e.detail,'')) LIKE ?
                            OR LOWER(COALESCE(e.raw_json,'')) LIKE ? OR EXISTS(SELECT 1 FROM detail_event_agents sa WHERE sa.event_uid=e.event_uid AND
                              (LOWER(COALESCE(sa.agent,'')) LIKE ? OR LOWER(COALESCE(sa.name,'')) LIKE ? OR LOWER(COALESCE(sa.pc,'')) LIKE ? OR LOWER(COALESCE(sa.ip,'')) LIKE ?)))''')
            params.extend([term]*17)
        where_sql=' AND '.join(where)
        generic_policies=load_policies()
        declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
        include_excluded=str((qs.get('include_governance_excluded') or ['0'])[0] or '0')=='1'
        total,rows,counts,visible_clients,decisions=_select_details_page(
            con,where_sql,params,page*page_size,page_size,display_offset,
            generic_policies,declarations,include_excluded)
        uids=[r['event_uid'] for r in rows];agents_by_event=defaultdict(list)
        if uids:
            marks=','.join('?' for _ in uids)
            for a in con.execute(f'SELECT * FROM detail_event_agents WHERE event_uid IN ({marks}) ORDER BY event_uid,relation,agent',uids):agents_by_event[a['event_uid']].append(dict(a))
        rows=[_decorate_detail_row(r,agents_by_event.get(r['event_uid'],[]),display_offset,generic_policies,declarations,
                                   governance=decisions.get(r['id'])) for r in rows]

        # Filter catalogues must never dominate the raw journal query. In
        # production the old archive GROUP BY/JOIN metadata path could scan
        # ~1.84M detail rows and account for most of a 90+ s request. Build
        # selectors from the canonical configured File -> ACTIVE Agent scope;
        # raw rows remain the source of truth for the journal itself.
        shared_admin=load_admin_directory()
        clients,available_agents,clients_by_agent=_configured_details_metadata(
            shared_admin,admin.get('devices',{}),rows,client)
        counts=dict(counts)
        client_count=len(visible_clients)
        last_run=con.execute('SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone();db_size=DETAILS_DB.stat().st_size if DETAILS_DB.is_file() else 0
        public=public_filter_contract(common);public.update(client=client,q=str((qs.get('q') or [''])[0] or ''))
        return dict(day=days[0],date_from=days[0],date_to=days[-1],latest_day=latest,total=total,page=page,page_size=page_size,pages=max(1,math.ceil(total/page_size)) if total else 1,rows=rows,
            summary=dict(logs=total,clients=client_count,export=counts.get('export',0),capture=counts.get('capture',0),signals=counts.get('signal',0),calls=counts.get('call',0)),
            admin_groups=filter_catalog(),available_agents=available_agents,available_clients=clients,filters=public,common_filters=public,
            details_db=dict(path=str(DETAILS_DB),size_bytes=db_size,sync_pending=bool(sync_state.get('pending')),sync_error=sync_error,last_sync=dict(last_run) if last_run else None,
                read_consistency='instantane SQLite ; projections invalidees par revision et regles',
                cache_retention_seconds=_READ_CACHE.ttl_seconds))


def status():
    init()
    with connect_details() as con:
        return {
            'path': str(DETAILS_DB),
            'events': int(con.execute('SELECT COUNT(*) FROM detail_events').fetchone()[0]),
            'imports': int(con.execute('SELECT COUNT(*) FROM detail_imports').fetchone()[0]),
            'days': int(con.execute('SELECT COUNT(DISTINCT day) FROM active_days').fetchone()[0]),
            'size_bytes': DETAILS_DB.stat().st_size if DETAILS_DB.is_file() else 0,
            'last_sync': dict(con.execute('SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1').fetchone() or {})
        }


def sync_active_references(supervision_db):
    """Refresh only the tiny active-day pointer table after a staged import.

    V60.2 archives the new import while users still read the previous active
    reference. After the atomic coverage switch we only need to update these
    pointers; replaying every historical Details row would defeat the snapshot
    design and make the import unnecessarily slow.
    """
    init()
    src=sqlite3.connect(str(supervision_db),timeout=30);src.row_factory=sqlite3.Row
    try:
        with connect_details() as dst:
            if getattr(dst,'schema',None)=='details':
                locked=dst.execute('SELECT pg_try_advisory_xact_lock(781205831)').fetchone()[0]
                if not locked:
                    return dict(ok=False,pending=True,path=str(DETAILS_DB))
            _sync_active_days(dst,src,utc_now())
        return dict(ok=True,path=str(DETAILS_DB),active_references=True)
    finally:
        src.close()
