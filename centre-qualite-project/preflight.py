"""Read-only release preflight. Does not import the application or start workers."""
from __future__ import annotations
import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import db_compat as sqlite3
import sqlite3 as native_sqlite3
import sys


def check(root: Path) -> dict:
    root=root.resolve();checks=[]
    def add(name,ok,detail,level='error'):
        checks.append(dict(check=name,ok=bool(ok),detail=str(detail),level=level))
    add('Python >= 3.10',sys.version_info>=(3,10),platform.python_version())
    for module in ('reportlab','websockets'):
        add('Dependance '+module,importlib.util.find_spec(module) is not None,module)
    add('Client HTTP externe',True,'Aucune dependance requests requise : urllib standard est utilise pour Edge DevTools et la recette HTTP.')
    manifest_path=root/'MANIFEST_PRODUCTION.json';manifest={}
    try:
        manifest=json.loads(manifest_path.read_text('utf-8'))
        invalid=[]
        for name,digest in manifest['files'].items():
            p=(root/name).resolve()
            if not p.is_relative_to(root) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:invalid.append(name)
        add('Integrite du code',not invalid,'OK' if not invalid else '; '.join(invalid))
    except (OSError,ValueError,KeyError) as exc:add('Integrite du code',False,type(exc).__name__)
    syntax=[]
    for p in root.glob('*.py'):
        try:ast.parse(p.read_text('utf-8-sig'),filename=p.name)
        except (SyntaxError,UnicodeError) as exc:syntax.append(p.name+': '+str(exc))
    add('Syntaxe Python',not syntax,'OK' if not syntax else '; '.join(syntax))
    for name in ('TECHIN_Stock_Manager.db','NELYIO_Supervision.db','Nelyio_Details.db'):
        p=root/name
        if not p.is_file():add('SQLite '+name,False,'Absente : restaurer une copie coherente avant bascule.');continue
        # Explicit read-only mode. Never checkpoint, vacuum, migrate or seed here.
        try:
            con=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,timeout=5)
            try:
                result=con.execute('PRAGMA quick_check').fetchall()
                add('SQLite '+name,result==[('ok',)],result)
            finally:con.close()
        except sqlite3.Error as exc:add('SQLite '+name,False,type(exc).__name__+': '+str(exc))
    live=root/'Nelyio_Live.db'
    if not live.is_file():
        add('Live SQLite V60',False,'Absente : elle sera creee au premier demarrage du service Live.','warning')
    else:
        try:
            con=native_sqlite3.connect(live.as_uri()+'?mode=ro',uri=True,timeout=5)
            try:
                result=con.execute('PRAGMA quick_check').fetchall()
                add('Live SQLite V60',result==[('ok',)],result)
            finally:con.close()
        except native_sqlite3.Error as exc:add('Live SQLite V60',False,type(exc).__name__+': '+str(exc))
    mutable=('Caddyfile',)
    for name in mutable:add('Configuration '+name,(root/name).is_file(),'Configuration locale preservee, non figee par empreinte.')
    add('Recette Windows/HTTPS/Hermes',False,'Executer RECETTE_PRODUCTION.bat sur le serveur cible, puis verifier HTTPS depuis un autre poste du LAN.','warning')
    return dict(version=manifest.get('version','inconnue'),ok=all(c['ok'] or c['level']=='warning' for c in checks),checks=checks)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--json',type=Path)
    args=p.parse_args();result=check(args.root)
    for c in result['checks']:print(('OK' if c['ok'] else 'ATTENTION' if c['level']=='warning' else 'ECHEC')+' - '+c['check']+' : '+c['detail'])
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True);args.json.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__=='__main__':sys.exit(main())
