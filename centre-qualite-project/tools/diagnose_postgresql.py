#!/usr/bin/env python3
"""Read-only PostgreSQL diagnostic for Nelyio.

No DDL/DML is executed. The DSN/password is never printed. pg_stat_statements
is inspected only when already installed; this tool never enables extensions.
"""
from __future__ import annotations
import argparse, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_env():
    p=ROOT/'data'/'postgres.env'
    if p.is_file():
        for raw in p.read_text(encoding='utf-8-sig').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(),v.strip())

def fetchall(cur,sql,params=()):
    cur.execute(sql,params)
    cols=[d.name for d in cur.description]
    return [dict(zip(cols,row)) for row in cur.fetchall()]

def scalar(cur,sql,params=()):
    cur.execute(sql,params);row=cur.fetchone();return row[0] if row else None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',default=str(ROOT/'logs'/'postgresql_diagnostic.json'))
    ap.add_argument('--top',type=int,default=25)
    args=ap.parse_args()
    load_env();dsn=os.environ.get('NELYIO_DATABASE_URL','').strip()
    if not dsn:
        raise SystemExit('NELYIO_DATABASE_URL absent de data/postgres.env')
    try: import psycopg
    except Exception as exc: raise SystemExit('psycopg indisponible: '+str(exc))
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'read_only':True,'dsn_redacted':True}
    with psycopg.connect(dsn,autocommit=True,connect_timeout=5) as con:
      with con.cursor() as cur:
        report['server']={
          'version':scalar(cur,'SHOW server_version'),
          'database':scalar(cur,'SELECT current_database()'),
          'max_connections':scalar(cur,'SHOW max_connections'),
          'shared_buffers':scalar(cur,'SHOW shared_buffers'),
          'work_mem':scalar(cur,'SHOW work_mem'),
          'effective_cache_size':scalar(cur,'SHOW effective_cache_size'),
          'timezone':scalar(cur,'SHOW TimeZone'),
        }
        report['connections']=fetchall(cur,"""
          SELECT state,COUNT(*) AS count
          FROM pg_stat_activity WHERE datname=current_database() GROUP BY state ORDER BY state NULLS FIRST
        """)
        report['long_transactions']=fetchall(cur,"""
          SELECT pid,usename,state,wait_event_type,wait_event,
                 round(extract(epoch from (clock_timestamp()-xact_start))::numeric,3) AS xact_seconds,
                 left(query,300) AS query
          FROM pg_stat_activity
          WHERE datname=current_database() AND pid<>pg_backend_pid() AND xact_start IS NOT NULL
            AND clock_timestamp()-xact_start > interval '5 seconds'
          ORDER BY xact_start LIMIT 50
        """)
        report['blocked']=fetchall(cur,"""
          SELECT pid,usename,state,wait_event_type,wait_event,pg_blocking_pids(pid) AS blocking_pids,
                 left(query,300) AS query
          FROM pg_stat_activity
          WHERE datname=current_database() AND cardinality(pg_blocking_pids(pid))>0
          ORDER BY pid
        """)
        report['tables']=fetchall(cur,"""
          SELECT schemaname,relname,n_live_tup,n_dead_tup,seq_scan,seq_tup_read,idx_scan,
                 last_analyze,last_autoanalyze,last_vacuum,last_autovacuum
          FROM pg_stat_user_tables
          WHERE schemaname IN ('admin','supervision','details')
          ORDER BY n_live_tup DESC,schemaname,relname
        """)
        report['indexes']=fetchall(cur,"""
          SELECT s.schemaname,s.relname,s.indexrelname,s.idx_scan,
                 pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
          FROM pg_stat_user_indexes s
          WHERE s.schemaname IN ('admin','supervision','details')
          ORDER BY s.schemaname,s.relname,s.indexrelname
        """)
        wanted=['supervision_calls_import_time','supervision_calls_indice','supervision_activity_agent_latest','supervision_activity_import_agent_latest','details_detail_event_source_import_page','supervision_calls_ani_digits_trgm','supervision_calls_phone_any_trgm']
        report['recommended_index_presence']=fetchall(cur,"""
          SELECT c.relname AS index_name, n.nspname AS schema_name
          FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relkind='i' AND c.relname=ANY(%s)
          ORDER BY c.relname
        """,(wanted,))
        report['pg_trgm_installed']=bool(scalar(cur,"SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_trgm')"))
        has_pgs=bool(scalar(cur,"SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements')"))
        report['pg_stat_statements_available']=has_pgs
        if has_pgs:
            lim=max(1,min(100,args.top))
            report['pg_stat_statements_total']=fetchall(cur,"""
              SELECT calls,round(total_exec_time::numeric,3) AS total_exec_ms,
                     round(mean_exec_time::numeric,3) AS mean_exec_ms,rows,
                     shared_blks_hit,shared_blks_read,temp_blks_written,left(query,500) AS query
              FROM pg_stat_statements
              WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database())
                AND query NOT ILIKE '%%pg_stat_statements%%'
              ORDER BY total_exec_time DESC LIMIT %s
            """,(lim,))
            report['pg_stat_statements_mean']=fetchall(cur,"""
              SELECT calls,round(total_exec_time::numeric,3) AS total_exec_ms,
                     round(mean_exec_time::numeric,3) AS mean_exec_ms,rows,
                     shared_blks_hit,shared_blks_read,temp_blks_written,left(query,500) AS query
              FROM pg_stat_statements
              WHERE dbid=(SELECT oid FROM pg_database WHERE datname=current_database()) AND calls>0
                AND query NOT ILIKE '%%pg_stat_statements%%'
              ORDER BY mean_exec_time DESC LIMIT %s
            """,(lim,))
        else:
            report['pg_stat_statements_note']='Extension non installée : aucune activation automatique effectuée.'
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('Diagnostic PostgreSQL écrit :',out)
    print('pg_stat_statements :','disponible' if report['pg_stat_statements_available'] else 'non disponible')
    print('transactions >5s :',len(report['long_transactions']),'bloquées :',len(report['blocked']))

if __name__=='__main__': main()
