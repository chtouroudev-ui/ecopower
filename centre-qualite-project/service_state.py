"""Small isolated heartbeat database for the local Nelyio services.

No business data is stored here. Web, Live and Analytics therefore report
health without contending on PostgreSQL or the main Support database.
The optional local Importer only publishes a heartbeat while it is running.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

BASE = Path(__file__).resolve().parent
DB = BASE / 'Nelyio_Services.db'
try:
    _version_meta=json.loads((BASE / 'VERSION.json').read_text(encoding='utf-8-sig'))
    _version=str(_version_meta.get('version') or 'unknown')
    _revision=str(_version_meta.get('runtime_revision') or '').strip()
    BUILD=f'{_version}+{_revision}' if _revision else _version
except Exception:
    BUILD = 'unknown'
_SCHEMA_LOCK = threading.Lock()
_READY = False


@contextmanager
def connect():
    con = sqlite3.connect(str(DB), timeout=3)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=3000')
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    global _READY
    if _READY and DB.exists():
        return
    with _SCHEMA_LOCK:
        if _READY and DB.exists():
            return
        DB.parent.mkdir(parents=True, exist_ok=True)
        with connect() as con:
            con.execute('PRAGMA journal_mode=WAL')
            con.executescript('''
            CREATE TABLE IF NOT EXISTS service_heartbeats(
              service TEXT PRIMARY KEY,
              pid INTEGER NOT NULL,
              build TEXT NOT NULL,
              started_at REAL NOT NULL,
              last_seen REAL NOT NULL,
              state TEXT NOT NULL,
              detail_json TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS service_seen ON service_heartbeats(last_seen DESC);
            ''')
        _READY = True


def beat(service: str, state: str = 'running', detail=None, *, started_at=None):
    init()
    now = time.time()
    detail_json = json.dumps(detail or {}, ensure_ascii=False, separators=(',', ':'))
    with connect() as con:
        row = con.execute('SELECT started_at,pid FROM service_heartbeats WHERE service=?', (service,)).fetchone()
        first = float(row['started_at']) if row and int(row['pid']) == os.getpid() else float(started_at or now)
        con.execute('''INSERT INTO service_heartbeats(service,pid,build,started_at,last_seen,state,detail_json)
                       VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(service) DO UPDATE SET pid=excluded.pid,build=excluded.build,
                       started_at=excluded.started_at,last_seen=excluded.last_seen,state=excluded.state,detail_json=excluded.detail_json''',
                    (service, os.getpid(), BUILD, first, now, str(state)[:40], detail_json[:4000]))


def stop(service: str, detail=None):
    try:
        beat(service, 'stopped', detail)
    except Exception:
        pass


def public_status(stale_after=12.0):
    init()
    now = time.time()
    rows = []
    with connect() as con:
        source = con.execute('SELECT * FROM service_heartbeats ORDER BY service').fetchall()
    by_name = {}
    for row in source:
        item = dict(row)
        try:
            item['detail'] = json.loads(item.pop('detail_json') or '{}')
        except Exception:
            item['detail'] = {}
        item['age_seconds'] = round(max(0.0, now - float(item['last_seen'])), 1)
        # A heartbeat from an older release must never make a freshly updated
        # stack look healthy.  This matters after an interrupted deployment:
        # stale/orphan workers can otherwise survive and serve incompatible
        # cached/schema assumptions until the next manual reboot.
        item['build_match'] = str(item.get('build') or '') == BUILD
        item['healthy'] = (
            item['state'] == 'running'
            and item['age_seconds'] <= float(stale_after)
            and item['build_match']
        )
        by_name[item['service']] = item
        rows.append(item)
    required = ('web', 'live', 'analytics')
    optional = ('import',)
    return {
        'build': BUILD,
        'expected': list(required),
        'required': list(required),
        'optional': list(optional),
        'all_healthy': all(by_name.get(name, {}).get('healthy', False) for name in required),
        'services': rows,
    }
