"""Database compatibility layer for Nelyio.

When data/postgres.env defines NELYIO_DATABASE_URL, the three historical/core
runtime databases are transparently redirected to PostgreSQL schemas:
  TECHIN_Stock_Manager.db -> admin
  NELYIO_Supervision.db   -> supervision
  Nelyio_Details.db       -> details

V60 deliberately excludes Nelyio_Live.db from this router: Live is an isolated
current-day SQLite/WAL database. Other SQLite files (legacy imports, capture
spool, migration sources) also continue using Python's stdlib sqlite3.
"""
from __future__ import annotations

import os
import re
import sqlite3 as _sqlite3
import threading
import time
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

Row = _sqlite3.Row
Connection = _sqlite3.Connection
Cursor = _sqlite3.Cursor
Error = _sqlite3.Error
OperationalError = _sqlite3.OperationalError
IntegrityError = _sqlite3.IntegrityError
DatabaseError = _sqlite3.DatabaseError
sqlite_version = _sqlite3.sqlite_version
DB_COMPAT_BUILD = 'V59-PG-POOL-READ-WORKER'

_PG_POOL_LOCK = threading.RLock()
_PG_IDLE = {}


def _pg_pool_limit():
    try:
        return max(0,min(16,int(os.environ.get('NELYIO_PG_POOL_IDLE','4'))))
    except (TypeError,ValueError):
        return 4


def _pg_prepare_new(psycopg, dsn, schema):
    con=psycopg.connect(dsn,autocommit=False,connect_timeout=5)
    try:
        with con.cursor() as cur:
            cur.execute(f'SET search_path TO "{schema}", public')
            cur.execute("SET TIME ZONE 'Europe/Paris'")
            cur.execute("SET lock_timeout = '5s'")
        con.commit()
        return con
    except Exception:
        con.close();raise


def _pg_acquire(psycopg, dsn, schema):
    started=time.perf_counter()
    key=(dsn,schema)
    while True:
        with _PG_POOL_LOCK:
            bucket=_PG_IDLE.get(key) or []
            con=bucket.pop() if bucket else None
            if bucket:_PG_IDLE[key]=bucket
            else:_PG_IDLE.pop(key,None)
        if con is None:
            con=_pg_prepare_new(psycopg,dsn,schema)
            try:
                import perf_trace; perf_trace.add_db_acquire(time.perf_counter()-started)
            except Exception: pass
            return con,key
        try:
            if con.closed:
                continue
            if con.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                con.rollback()
            try:
                import perf_trace; perf_trace.add_db_acquire(time.perf_counter()-started)
            except Exception: pass
            return con,key
        except Exception:
            try:con.close()
            except Exception:pass


def _pg_release(psycopg, key, con):
    if con is None:return
    limit=_pg_pool_limit()
    try:
        if con.closed:return
        if con.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            con.rollback()
        if limit<=0:
            con.close();return
    except Exception:
        try:con.close()
        except Exception:pass
        return
    with _PG_POOL_LOCK:
        bucket=_PG_IDLE.setdefault(key,[])
        if len(bucket)<limit:
            bucket.append(con);return
    try:con.close()
    except Exception:pass

_RUNTIME_SCHEMAS = {
    'techin_stock_manager.db': 'admin',
    'nelyio_supervision.db': 'supervision',
    'nelyio_details.db': 'details',
}


def _load_env_file():
    root = Path(__file__).resolve().parent
    env_file = root / 'data' / 'postgres.env'
    if not env_file.is_file():
        return
    try:
        for raw in env_file.read_text(encoding='utf-8-sig').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file()


def postgres_enabled() -> bool:
    if os.environ.get('NELYIO_FORCE_SQLITE','0').strip().lower() in {'1','true','yes','on'}:
        return False
    value = os.environ.get('NELYIO_DATABASE_URL', '').strip()
    return bool(value) and os.environ.get('NELYIO_DATABASE_ENGINE', 'postgresql').strip().lower() in {'postgres', 'postgresql'}


def schema_for_database(database) -> str | None:
    try:
        name = Path(str(database)).name.lower()
    except Exception:
        return None
    return _RUNTIME_SCHEMAS.get(name)


def runtime_database_available(database):
    """Routing/presence check only; a database query still checks connectivity."""
    return bool(postgres_enabled() and schema_for_database(database)) or Path(database).is_file()


def database_identity(database):
    path = Path(database).resolve()
    if postgres_enabled() and schema_for_database(path):
        import hashlib
        return ('postgresql', hashlib.sha256(os.environ['NELYIO_DATABASE_URL'].encode()).hexdigest(), schema_for_database(path))
    if not path.is_file():
        return None
    st = path.stat()
    return (str(path), st.st_dev, st.st_ino)


def begin_read_snapshot(con):
    """Start before the first business SELECT; one committed snapshot per view."""
    if getattr(con, 'schema', None):
        con.commit()  # connection setup PRAGMAs may have opened a transaction
        con.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    else:
        con.execute('BEGIN')


class PgRow:
    __slots__ = ('_keys', '_values', '_map')
    def __init__(self, keys, values):
        self._keys = tuple(keys)
        # PostgreSQL SUM(bigint) returns Decimal; SQLite returns int/float.
        self._values = tuple((int(v) if v.is_finite() and v==v.to_integral_value() else float(v))
                             if isinstance(v,Decimal) else v for v in values)
        self._map = {k: v for k, v in zip(self._keys, self._values)}
    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        return self._map[key]
    def __iter__(self):
        return iter(self._values)
    def __len__(self):
        return len(self._keys)
    def keys(self):
        return self._keys
    def __repr__(self):
        return repr(self._map)


def _quote_legacy_reserved_identifiers(sql: str) -> str:
    """Quote legacy SQLite column names that are PostgreSQL keywords.

    Nelyio historically uses a lowercase column named ``end`` in several
    SQLite tables. PostgreSQL reserves END for CASE / PL/pgSQL, so the same
    DDL and DML fails unless the identifier is quoted. The application SQL
    consistently writes the column as lowercase ``end`` while SQL control
    keywords are emitted as uppercase ``END``. Preserve that convention and
    only quote the lowercase identifier outside strings/quoted identifiers.
    """
    out=[]
    i=0
    quote=None
    n=len(sql)
    while i<n:
        ch=sql[i]
        if quote is not None:
            out.append(ch)
            if ch==quote:
                if i+1<n and sql[i+1]==quote:
                    out.append(sql[i+1]); i+=2; continue
                quote=None
            i+=1
            continue
        if ch in ("'", '"'):
            quote=ch; out.append(ch); i+=1; continue
        if ch.isalpha() or ch=='_':
            j=i+1
            while j<n and (sql[j].isalnum() or sql[j]=='_'):
                j+=1
            token=sql[i:j]
            out.append('"end"' if token=='end' else token)
            i=j
            continue
        out.append(ch); i+=1
    return ''.join(out)


def _replace_qmarks(sql: str) -> str:
    out=[]; quote=None; i=0
    while i < len(sql):
        ch=sql[i]
        if quote:
            out.append(ch)
            if ch==quote:
                if i+1 < len(sql) and sql[i+1]==quote:
                    out.append(sql[i+1]); i+=1
                else:
                    quote=None
        else:
            if ch in ("'", '"'):
                quote=ch; out.append(ch)
            elif ch=='?':
                out.append('%s')
            else:
                out.append(ch)
        i+=1
    return ''.join(out)


def _escape_psycopg_literal_percents(sql: str) -> str:
    """Escape literal percent signs for psycopg parameterized execution.

    psycopg uses the pyformat protocol whenever a parameter sequence is
    supplied. In that mode every literal ``%`` in the query text must be
    written as ``%%`` -- including percents inside SQL string literals and
    comments. Nelyio itself uses SQLite ``?`` placeholders, translated to
    psycopg ``%s`` outside quoted/commented SQL.

    Preserve real psycopg placeholders only in normal SQL context. Inside
    strings, quoted identifiers and comments every percent is literal. This
    also protects patterns such as ``LIKE '%stock%'`` whose first wildcard
    would otherwise look exactly like a ``%s`` placeholder.
    """
    out=[]
    i=0
    n=len(sql)
    quote=None
    line_comment=False
    block_comment=False
    while i<n:
        ch=sql[i]
        nxt=sql[i+1] if i+1<n else ''

        if line_comment:
            if ch=='%':
                if nxt=='%': out.append('%%'); i+=2; continue
                out.append('%%'); i+=1; continue
            out.append(ch)
            if ch in '\r\n': line_comment=False
            i+=1
            continue

        if block_comment:
            if ch=='%' :
                if nxt=='%': out.append('%%'); i+=2; continue
                out.append('%%'); i+=1; continue
            out.append(ch)
            if ch=='*' and nxt=='/':
                out.append('/'); i+=2; block_comment=False; continue
            i+=1
            continue

        if quote is not None:
            if ch=='%':
                if nxt=='%': out.append('%%'); i+=2; continue
                out.append('%%'); i+=1; continue
            out.append(ch)
            if ch==quote:
                if i+1<n and sql[i+1]==quote:
                    out.append(sql[i+1]); i+=2; continue
                quote=None
            i+=1
            continue

        if ch in ("'", '"'):
            quote=ch; out.append(ch); i+=1; continue
        if ch=='-' and nxt=='-':
            line_comment=True; out.extend(['-','-']); i+=2; continue
        if ch=='/' and nxt=='*':
            block_comment=True; out.extend(['/','*']); i+=2; continue
        if ch=='%':
            if nxt in {'s','b','t','%'}:
                out.append('%'+nxt); i+=2; continue
            out.append('%%'); i+=1; continue
        out.append(ch); i+=1
    return ''.join(out)


def _has_parameters(parameters) -> bool:
    if parameters is None:
        return False
    if isinstance(parameters, Mapping):
        return bool(parameters)
    try:
        return len(parameters) > 0
    except TypeError:
        return True


def _split_sql_script(script: str):
    """Split legacy SQLite executescript() input safely.

    Semicolons inside SQL strings *and comments* must not terminate a
    statement.  A production schema comment previously contained a semicolon
    ("...evidence; they are evaluated..."), which made the text after the
    semicolon reach PostgreSQL as executable SQL.
    """
    statements=[]; buf=[]; quote=None; i=0; line_comment=False; block_comment=False
    n=len(script)
    while i < n:
        ch=script[i]
        nxt=script[i+1] if i+1<n else ''
        if line_comment:
            if ch in '\r\n':
                line_comment=False
                buf.append('\n')
            i+=1
            continue
        if block_comment:
            if ch=='*' and nxt=='/':
                block_comment=False; i+=2
            else:
                i+=1
            continue
        if quote is not None:
            buf.append(ch)
            if ch==quote:
                if i+1<n and script[i+1]==quote:
                    buf.append(script[i+1]); i+=2; continue
                quote=None
            i+=1
            continue
        if ch in ("'", '"'):
            quote=ch; buf.append(ch); i+=1; continue
        if ch=='-' and nxt=='-':
            line_comment=True; i+=2; continue
        if ch=='/' and nxt=='*':
            block_comment=True; i+=2; continue
        if ch==';':
            text=''.join(buf).strip(); buf=[]
            if text: statements.append(text)
            i+=1; continue
        buf.append(ch); i+=1
    text=''.join(buf).strip()
    if text: statements.append(text)
    return statements


class PgCursor:
    def __init__(self, connection, cursor):
        self.connection=connection
        self._cursor=cursor
        self._rows=None
        self._idx=0
        self._lastrowid=connection._lastrowid
        self._column_keys=None
    @property
    def rowcount(self): return self._cursor.rowcount
    @property
    def lastrowid(self): return self._lastrowid
    @property
    def description(self): return self._cursor.description
    def _wrap(self, row):
        if row is None: return None
        if isinstance(row, PgRow): return row
        if self._column_keys is None:
            self._column_keys=[d.name if hasattr(d,'name') else d[0] for d in (self._cursor.description or [])]
        return PgRow(self._column_keys,row)
    def fetchone(self): return self._wrap(self._cursor.fetchone())
    def fetchall(self): return [self._wrap(r) for r in self._cursor.fetchall()]
    def __iter__(self):
        for r in self._cursor: yield self._wrap(r)


class PgConnection:
    def __init__(self, dsn: str, schema: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError('PostgreSQL active mais psycopg n est pas installe. Lancez CONFIGURER_POSTGRESQL_AUTO.bat.') from exc
        self._psycopg=psycopg
        self._con,self._pool_key=_pg_acquire(psycopg,dsn,schema)
        self._closed=False
        self.schema=schema
        self.row_factory=Row
        self._lastrowid=None
        self._pk_cache={}
        self._sequence_cache={}
        self._failed=False
    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type: self.rollback()
            else: self.commit()
        finally: self.close()
        return False
    def close(self):
        if self._closed:return
        self._closed=True
        con=self._con;self._con=None
        _pg_release(self._psycopg,self._pool_key,con)
    def commit(self):
        if self._failed:
            self.rollback()
            raise OperationalError('Transaction annulée après une erreur SQL; aucune écriture partielle validée.')
        self._con.commit()
    def rollback(self):
        self._con.rollback()
        self._failed=False
    def cursor(self): return PgCursor(self, self._con.cursor())
    @property
    def in_transaction(self):
        try:
            return self._con.info.transaction_status != self._psycopg.pq.TransactionStatus.IDLE
        except Exception:
            return False
    def create_function(self, *args, **kwargs): return None
    def backup(self, target):
        raise RuntimeError('backup() SQLite indisponible en mode PostgreSQL; utilisez SAUVEGARDER_POSTGRESQL.bat')
    def _pk_columns(self, table: str):
        if table in self._pk_cache: return self._pk_cache[table]
        with self._con.cursor() as cur:
            cur.execute("""
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey)
                WHERE i.indrelid=%s::regclass AND i.indisprimary
                ORDER BY array_position(i.indkey,a.attnum)
            """, (f'{self.schema}.{table}',))
            result=[r[0] for r in cur.fetchall()]
            self._pk_cache[table]=result
            return result
    def _serial_sequence(self, table):
        if table not in self._sequence_cache:
            pks=self._pk_columns(table)
            seq=None
            if len(pks)==1:
                with self._con.cursor() as cur:
                    cur.execute("SELECT pg_get_serial_sequence(%s,%s)",(f'{self.schema}.{table}',pks[0]))
                    row=cur.fetchone();seq=row[0] if row else None
            self._sequence_cache[table]=seq
        return self._sequence_cache[table]
    def _translate(self, sql: str) -> tuple[str, bool]:
        raw=sql.strip()
        upper=raw.upper()
        if upper.startswith('PRAGMA '):
            return raw, True
        if 'SQLITE_MASTER' in upper:
            # handled by execute special-case
            return raw, True
        s=raw
        # SQLite DDL compatibility. PostgreSQL has no AUTOINCREMENT keyword.
        # Normalize it unconditionally instead of only when the statement
        # begins exactly with CREATE TABLE. This also covers legacy scripts
        # prefixed by comments/whitespace or routed through executescript().
        s=re.sub(
            r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b',
            'BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY',
            s,
            flags=re.I,
        )
        if re.match(r'^CREATE\s+TABLE\b', s, re.I):
            s=re.sub(r'\bREAL\b','DOUBLE PRECISION',s,flags=re.I)
            s=re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\b','BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY',s,flags=re.I)
        # Last-resort cleanup for unusual legacy formatting. No PostgreSQL
        # statement is ever allowed to reach psycopg with AUTOINCREMENT left.
        s=re.sub(r'\bAUTOINCREMENT\b', '', s, flags=re.I)
        s=re.sub(r'\bCOLLATE\s+NOCASE\b','',s,flags=re.I)
        # SQLite query-planner hint; PostgreSQL chooses its own indexes.
        s=re.sub(r'\s+INDEXED\s+BY\s+[A-Za-z_][A-Za-z0-9_]*', '', s, flags=re.I)
        s=re.sub(r'\s+NOT\s+INDEXED\b', '', s, flags=re.I)
        s=re.sub(r"datetime\('now'\s*,\s*'localtime'\)", 'LOCALTIMESTAMP', s, flags=re.I)
        s=re.sub(r"date\('now'\s*,\s*'localtime'\)", 'CURRENT_DATE', s, flags=re.I)
        s=re.sub(r'\bdatetime\(([^(),]+)\)', r'CAST(\1 AS timestamp)', s, flags=re.I)
        s=re.sub(r'lower\(hex\(randomblob\(16\)\)\)', "md5(random()::text || clock_timestamp()::text)", s, flags=re.I)
        s=re.sub(r"json_extract\(([^,]+),\s*'\$\.([A-Za-z0-9_]+)'\)", r"(CAST(\1 AS jsonb) #>> '{\2}')", s, flags=re.I)
        s=re.sub(r'GROUP_CONCAT\(DISTINCT\s+([^)]+)\)', r"string_agg(DISTINCT \1, ',')", s, flags=re.I)
        s=_quote_legacy_reserved_identifiers(s)
        s=s.replace('MAX(0,CAST(julianday(CURRENT_DATE)-julianday(date(d.date_evenement)) AS INTEGER))',
                    'GREATEST(0, CAST(CURRENT_DATE - CAST(d.date_evenement AS date) AS INTEGER))')
        s=s.replace("julianday(CURRENT_DATE)-julianday(date(d.date_evenement))", "(CURRENT_DATE - CAST(d.date_evenement AS date))")
        s=re.sub(r'INSERT\s+OR\s+IGNORE\s+INTO\s+', 'INSERT INTO ', s, flags=re.I)
        ignore = bool(re.search(r'INSERT\s+OR\s+IGNORE\s+INTO\s+', raw, flags=re.I))
        replace = bool(re.search(r'INSERT\s+OR\s+REPLACE\s+INTO\s+', raw, flags=re.I))
        if replace:
            s=re.sub(r'INSERT\s+OR\s+REPLACE\s+INTO\s+', 'INSERT INTO ', s, flags=re.I)
        s=_replace_qmarks(s)
        if ignore and 'ON CONFLICT' not in s.upper():
            s=s.rstrip(';')+' ON CONFLICT DO NOTHING'
        if replace and 'ON CONFLICT' not in s.upper():
            m=re.search(r'INSERT\s+INTO\s+([\w\"]+)\s*\(([^)]+)\)\s*VALUES',s,re.I|re.S)
            if not m:
                m=re.search(r'INSERT\s+INTO\s+([\w\"]+)\s+VALUES',s,re.I|re.S)
            if m:
                table=m.group(1).strip('"')
                pks=self._pk_columns(table)
                if pks:
                    if m.lastindex and m.lastindex>=2 and m.group(2):
                        cols=[c.strip().strip('"') for c in m.group(2).split(',')]
                    else:
                        with self._con.cursor() as cur:
                            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",(self.schema,table))
                            cols=[r[0] for r in cur.fetchall()]
                    updates=[c for c in cols if c not in pks]
                    if updates:
                        s=s.rstrip(';')+' ON CONFLICT ('+','.join(f'"{c}"' for c in pks)+') DO UPDATE SET '+','.join(f'"{c}"=EXCLUDED."{c}"' for c in updates)
                    else:
                        s=s.rstrip(';')+' ON CONFLICT DO NOTHING'
        return s, False
    def _pragma(self, raw: str):
        cur=self._con.cursor()
        m=re.match(r'PRAGMA\s+table_info\s*\(\s*([\w\"]+)\s*\)',raw,re.I)
        if m:
            table=m.group(1).strip('"')
            cur.execute("""
                SELECT c.ordinal_position-1,c.column_name,c.data_type,
                       CASE WHEN c.is_nullable='NO' THEN 1 ELSE 0 END,c.column_default,
                       CASE WHEN tc.constraint_type='PRIMARY KEY' THEN 1 ELSE 0 END
                FROM information_schema.columns c
                LEFT JOIN information_schema.key_column_usage kcu
                  ON kcu.table_schema=c.table_schema AND kcu.table_name=c.table_name AND kcu.column_name=c.column_name
                LEFT JOIN information_schema.table_constraints tc
                  ON tc.constraint_schema=kcu.constraint_schema AND tc.constraint_name=kcu.constraint_name AND tc.constraint_type='PRIMARY KEY'
                WHERE c.table_schema=%s AND c.table_name=%s ORDER BY c.ordinal_position
            """,(self.schema,table))
            return PgCursor(self,cur)
        if re.match(r'PRAGMA\s+(foreign_keys|busy_timeout|temp_store|journal_mode|synchronous)\b',raw,re.I):
            cur.execute("SELECT 'ok'")
            return PgCursor(self,cur)
        if re.match(r'PRAGMA\s+(quick_check|integrity_check)\b',raw,re.I):
            cur.execute("SELECT 'ok'")
            return PgCursor(self,cur)
        if re.match(r'PRAGMA\s+foreign_key_check\b',raw,re.I):
            cur.execute("SELECT NULL WHERE FALSE")
            return PgCursor(self,cur)
        cur.execute("SELECT 'ok'")
        return PgCursor(self,cur)
    def execute(self, sql, parameters=()):
        if self._failed:
            raise OperationalError('Transaction en échec; rollback explicite requis.')
        raw=str(sql).strip()
        if re.match(r'^BEGIN(?:\s+IMMEDIATE)?$', raw, re.I):
            cur=self._con.cursor(); cur.execute('SELECT 1'); return PgCursor(self,cur)
        if re.match(r'^CREATE\s+TRIGGER\b', raw, re.I):
            cur=self._con.cursor(); cur.execute('SELECT 1'); return PgCursor(self,cur)
        if re.match(r'^SELECT\s+last_insert_rowid\(\)\s*$', raw, re.I):
            cur=self._con.cursor(); cur.execute('SELECT %s', (self._lastrowid,)); return PgCursor(self,cur)
        if raw.upper().startswith('PRAGMA '): return self._pragma(raw)
        if 'sqlite_master' in raw.lower():
            # Compatibility for existence checks and index/schema inspection.
            cur=self._con.cursor()
            table_name=None
            if parameters: table_name=parameters[-1]
            else:
                m=re.search(r"name\s*=\s*['\"]([^'\"]+)",raw,re.I)
                if m: table_name=m.group(1)
            if 'type=\'table\'' in raw.lower() or 'type="table"' in raw.lower() or "type='table'" in raw.lower():
                if table_name is None:
                    cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name",(self.schema,))
                else:
                    cur.execute("SELECT table_name AS name FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",(self.schema,table_name))
            elif 'type=\'index\'' in raw.lower() or "type='index'" in raw.lower():
                if table_name is None:
                    cur.execute("SELECT indexname AS name,indexdef AS sql FROM pg_indexes WHERE schemaname=%s ORDER BY indexname",(self.schema,))
                else:
                    cur.execute("SELECT indexname AS name,indexdef AS sql FROM pg_indexes WHERE schemaname=%s AND tablename=%s",(self.schema,table_name))
            else:
                cur.execute("SELECT NULL WHERE FALSE")
            return PgCursor(self,cur)
        translated,_=self._translate(raw)
        # Hard safety net: SQLite AUTOINCREMENT must never reach PostgreSQL.
        # Keep this guard here as well as in _translate() because startup DDL
        # comes from several legacy executescript() blocks.
        if 'AUTOINCREMENT' in translated.upper():
            translated=re.sub(
                r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b',
                'BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY',
                translated, flags=re.I,
            )
            translated=re.sub(r'\bAUTOINCREMENT\b', '', translated, flags=re.I)
        cur=self._con.cursor()
        _sql_started=time.perf_counter()
        try:
            # Important psycopg detail: passing even an empty parameter tuple
            # activates pyformat placeholder parsing. Legacy SQLite SQL often
            # contains literal percent signs (LIKE 'prefix_%', strftime formats).
            # Execute parameterless statements without a second argument. For
            # parameterized statements, escape literal percents while preserving
            # the %s/%b/%t placeholders produced by the compatibility translator.
            if _has_parameters(parameters):
                translated_exec=_escape_psycopg_literal_percents(translated)
                cur.execute(translated_exec, parameters)
            else:
                translated_exec=translated
                cur.execute(translated_exec)
            try:
                import perf_trace; perf_trace.add_sql(time.perf_counter()-_sql_started, translated_exec)
            except Exception: pass
        except self._psycopg.errors.UniqueViolation as exc:
            self._con.rollback(); self._failed=True; raise IntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            self._con.rollback(); self._failed=True; raise OperationalError(str(exc)) from exc
        # Emulate sqlite3 lastrowid for generated integer PKs only.
        # PostgreSQL marks the whole transaction as failed after any SQL error.
        # The old best-effort currval(pg_get_serial_sequence(...)) probe swallowed
        # errors but left the transaction aborted, so the next statement failed
        # with InFailedSqlTransaction. Put the ENTIRE metadata/currval probe in
        # a SAVEPOINT and roll back only that probe if it cannot produce a value.
        if translated.lstrip().upper().startswith('INSERT INTO') and getattr(cur,'rowcount',0)>0:
            m=re.search(r'INSERT\s+INTO\s+([\w\"]+)',translated,re.I)
            if m:
                table=m.group(1).strip('\"')
                seq=self._serial_sequence(table)
                self._lastrowid=None
                if seq:
                    with self._con.cursor() as idc:
                        idc.execute('SAVEPOINT nelyio_lastrowid_probe')
                        try:
                            idc.execute('SELECT currval(%s::regclass)',(seq,))
                            row=idc.fetchone(); self._lastrowid=row[0] if row else None
                            idc.execute('RELEASE SAVEPOINT nelyio_lastrowid_probe')
                        except self._psycopg.Error:
                            idc.execute('ROLLBACK TO SAVEPOINT nelyio_lastrowid_probe')
                            idc.execute('RELEASE SAVEPOINT nelyio_lastrowid_probe')
        return PgCursor(self,cur)
    def executemany(self, sql, seq):
        if self._failed: raise OperationalError('Transaction en échec; rollback explicite requis.')
        translated,_=self._translate(str(sql))
        translated_exec=_escape_psycopg_literal_percents(translated)
        cur=self._con.cursor()
        _sql_started=time.perf_counter()
        try:
            cur.executemany(translated_exec, seq)
            try:
                import perf_trace; perf_trace.add_sql(time.perf_counter()-_sql_started, translated_exec)
            except Exception: pass
        except self._psycopg.errors.UniqueViolation as exc:
            self._con.rollback(); self._failed=True; raise IntegrityError(str(exc)) from exc
        except self._psycopg.Error as exc:
            self._con.rollback(); self._failed=True; raise OperationalError(str(exc)) from exc
        return PgCursor(self,cur)
    def executescript(self, script):
        result=None
        for statement in _split_sql_script(script):
            if statement.upper().startswith('PRAGMA '):
                result=self._pragma(statement); continue
            # Runtime schemas are normally pre-created by the PostgreSQL
            # configurator. Still execute CREATE TABLE IF NOT EXISTS through the
            # compatibility translator so startup remains safe if a schema is
            # incomplete or a new runtime table is added later. Legacy indexes
            # are already recreated by postgres_migrate.py and can contain
            # SQLite-only expressions, so they remain skipped here.
            if re.match(r'^CREATE\s+TABLE\b',statement,re.I):
                result=self.execute(statement)
                continue
            if re.match(r'^CREATE\s+(?:UNIQUE\s+)?INDEX\b',statement,re.I):
                continue
            if re.match(r'^ALTER\s+TABLE\b',statement,re.I):
                result=self.execute(statement)
                continue
            result=self.execute(statement)
        return result


def connect(database, timeout=5, factory=None, uri=False, **kwargs):
    schema=schema_for_database(database)
    if postgres_enabled() and schema:
        return PgConnection(os.environ['NELYIO_DATABASE_URL'], schema)
    return _sqlite3.connect(database, timeout=timeout, factory=factory or _sqlite3.Connection, uri=uri, **kwargs)
