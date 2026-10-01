"""Safe code-only upgrade. Dry run by default; never overwrite databases/config.

Run from the NEW release, with all Nelyio/Caddy/capture/import workers stopped:
  python deploy_release.py --target "C:\\Nelyio"
  python deploy_release.py --target "C:\\Nelyio" --apply --confirm-stopped
Keep the sibling backup to roll back the ENTIRE installation after stopping it.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import socket
import sys

ROOT=Path(__file__).resolve().parent
PROTECTED={'INITIAL_ADMIN.txt','Caddyfile','Caddyfile.json','quality_priorities.json','agent_catalog.json'}


def allowed(name: str) -> bool:
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name:return False
    if p.name in PROTECTED or p.suffix.lower() in {'.db','.sqlite','.sqlite3','.key','.pem','.crt','.pfx','.log'}:return False
    if len(p.parts)==1:
        return (
            p.suffix.lower() in {'.py','.ps1','.bat','.cmd','.vbs','.html','.md','.txt'}
            or p.name in {'VERSION.json','MANIFEST_FRONTEND_REPAIR_F2.json','audit_empty_schemas.zip'}
        )
    if p.parts[0]=='docs':return p.suffix.lower()=='.md'
    if p.parts[0]=='static':return p.suffix.lower() in {'.css','.js','.svg','.png','.ico'}
    if p.parts[0]=='capture':return p.suffix.lower()=='.py'
    if p.parts[0]=='security':return p.suffix.lower() in {'.ps1','.bat','.cmd'}
    if p.parts[0]=='import':return p.name=='LISEZMOI_IMPORT_AUTO.txt'
    if p.parts[0]=='tools':return p.suffix.lower()=='.py'
    if p.parts[0]=='migrations':return p.suffix.lower()=='.sql'
    return False


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=.3):return True
    except OSError:return False


def deploy(source:Path,target:Path,apply=False,confirm_stopped=False,check_ports=True) -> dict:
    source=source.resolve();target=target.resolve()
    if source==target or source.is_relative_to(target) or target.is_relative_to(source):raise ValueError('Source et cible doivent etre deux dossiers distincts non imbriques.')
    if not (target/'app.py').is_file() or not (target/'TECHIN_Stock_Manager.db').is_file():raise ValueError('La cible ne ressemble pas a une installation Nelyio existante.')
    manifest=json.loads((source/'MANIFEST_PRODUCTION.json').read_text('utf-8'));files=manifest['files']
    for name,digest in files.items():
        src=source/name;dst=target/name
        if not allowed(name):raise ValueError('Chemin deploiement interdit : '+name)
        if src.is_symlink() or not src.resolve().is_relative_to(source) or not dst.resolve().is_relative_to(target):raise ValueError('Lien ou chemin sortant interdit : '+name)
        if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest()!=digest:raise ValueError('Source incomplete ou modifiee : '+name)
    accepted=manifest.get('upgrade_from',[])
    if accepted:
        versions=[dict(item['files']) for item in accepted]
        # Idempotent reapplication of this release is also accepted.
        versions.append({name:digest for name,digest in files.items() if name in accepted[0]['files']})
        def matches(version):
            return all((target/name).is_file() and hashlib.sha256((target/name).read_bytes()).hexdigest()==digest for name,digest in version.items())
        if not any(matches(v) for v in versions):
            raise ValueError('Version cible inconnue ou code local modifie. Aucun ecrasement automatique; comparer avec les versions de reference indiquees dans MANIFEST_PRODUCTION.json.')
    plan=dict(mode='simulation',version=manifest['version'],files=len(files),target=str(target),protected='Bases, data/, comptes, configuration Caddy, certificats, journaux et imports non remplaces.')
    if not apply:return plan
    if not confirm_stopped:raise ValueError('Arretez les processus puis ajoutez --confirm-stopped.')
    if check_ports and any(port_open(p) for p in (9050,9051,9052,5000,5050)):raise ValueError('Un port Nelyio habituel repond encore. Arretez les instances avant la copie.')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=target.parent/'NELYIO_BACKUPS'/(target.name+'_'+stamp)
    backup.parent.mkdir(parents=True,exist_ok=True)
    # Stopped coherent full snapshot. The virtual environment is not modified
    # by this upgrade; excluding it avoids copying gigabytes of reinstallable code.
    shutil.copytree(target,backup,ignore=shutil.ignore_patterns('.venv','venv','__pycache__','.pytest_cache','.git'))
    changed=[]
    try:
        for name in files:
            dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True)
            changed.append((name,dst.exists()));shutil.copy2(source/name,dst)
        shutil.copy2(source/'MANIFEST_PRODUCTION.json',target/'MANIFEST_PRODUCTION.json')
        for name,digest in files.items():
            if hashlib.sha256((target/name).read_bytes()).hexdigest()!=digest:raise OSError('Verification de copie echouee : '+name)
    except BaseException:
        for name,existed in reversed(changed):
            if existed:shutil.copy2(backup/name,target/name)
            else:(target/name).unlink(missing_ok=True)
        if (backup/'MANIFEST_PRODUCTION.json').exists():shutil.copy2(backup/'MANIFEST_PRODUCTION.json',target/'MANIFEST_PRODUCTION.json')
        else:(target/'MANIFEST_PRODUCTION.json').unlink(missing_ok=True)
        raise
    plan.update(mode='applique',backup=str(backup),next='Executer VALIDATION_PRODUCTION.bat, demarrer Nelyio, lancer RECETTE_PRODUCTION.bat, puis TEST_CHARGE_PROLONGEE.bat et ANALYSER_PERFORMANCE_PRODUCTION.bat. Aucun service demarre automatiquement par l upgrade.')
    log=target/'logs'/'deployment_rc2.json';log.parent.mkdir(exist_ok=True);log.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',type=Path,required=True);p.add_argument('--apply',action='store_true');p.add_argument('--confirm-stopped',action='store_true');args=p.parse_args()
    try:
        result=deploy(ROOT,args.target,args.apply,args.confirm_stopped);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError) as exc:print('ECHEC : '+str(exc),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
