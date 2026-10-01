#!/usr/bin/env python3
"""Apply the bundled non-destructive PostgreSQL performance migration.

Manual tool: it never drops/truncates/resets data. It refuses to run without
--apply so an accidental double-click cannot change production.
"""
from __future__ import annotations
import argparse, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MIGRATION=ROOT/'migrations'/'performance_indexes.sql'


def load_env():
    p=ROOT/'data'/'postgres.env'
    if p.is_file():
        for raw in p.read_text(encoding='utf-8-sig').splitlines():
            line=raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k,v=line.split('=',1)
            os.environ.setdefault(k.strip(),v.strip())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--apply',action='store_true',help='Confirme la création idempotente des index.')
    args=ap.parse_args()
    if not args.apply:
        raise SystemExit('Aucune modification. Relancer avec --apply après sauvegarde PostgreSQL.')
    load_env(); dsn=os.environ.get('NELYIO_DATABASE_URL','').strip()
    if not dsn:
        raise SystemExit('NELYIO_DATABASE_URL absent de data/postgres.env')
    sql=MIGRATION.read_text(encoding='utf-8')
    upper=sql.upper()
    for forbidden in ('DROP TABLE','DROP DATABASE','TRUNCATE ','DELETE FROM'):
        if forbidden in upper:
            raise SystemExit('Migration refusée : instruction destructive détectée: '+forbidden.strip())
    try:
        import psycopg
    except Exception as exc:
        raise SystemExit('psycopg indisponible: '+str(exc))
    print('Base : connexion via data/postgres.env (DSN masqué)')
    print('Migration :',MIGRATION)
    print('Création/ANALYZE en cours...')
    with psycopg.connect(dsn,autocommit=True,connect_timeout=10) as con:
        with con.cursor() as cur:
            cur.execute("SET lock_timeout='5s'")
            # DDL is idempotent. No parameters => psycopg can execute the SQL
            # script as a simple command batch, including the guarded DO block.
            cur.execute(sql,prepare=False)
    print('OK - migration performance appliquée. Aucun DROP/TRUNCATE/reset exécuté.')

if __name__=='__main__':
    main()
