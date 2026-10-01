"""F2 : verification, restauration des fichiers web et diagnostic HTTP, sans base."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit

MANIFEST = 'MANIFEST_FRONTEND_REPAIR_F2.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_path(root: Path, relative: str) -> Path:
    # Les chemins viennent du manifeste, mais sont controles avant toute ecriture.
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or '..' in parts or ':' in relative or '\\' in relative:
        raise ValueError('Chemin relatif refuse : ' + relative)
    path = root / relative
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
        raise ValueError('Lien symbolique refuse : ' + relative)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Chemin hors dossier : ' + relative)
    return path


def manifest(package: Path) -> tuple[dict, Path]:
    data = json.loads((package / MANIFEST).read_text(encoding='utf-8'))
    if data.get('lot') != 'V56.8-F2-REPARATION':
        raise ValueError('Manifeste incompatible')
    payload = (package / data.get('payload_directory', 'MISE_A_JOUR')).resolve()
    if not payload.is_relative_to(package.resolve()):
        raise ValueError('Source de copie hors paquet')
    for name, digest in data['frontend'].items():
        if name != 'index.html' and not (name.startswith('static/') and Path(name).suffix in {'.js', '.css'}):
            raise ValueError('Le paquet ne doit remplacer que le frontend')
        p = safe_path(payload, name)
        if not p.is_file() or sha(p) != digest:
            raise ValueError('Paquet incomplet ou modifie : ' + name)
    return data, payload


def inspect(target: Path, package: Path) -> dict:
    if not target.is_dir():
        raise ValueError('Dossier Nelyio introuvable')
    data, _ = manifest(package)
    incompatible = []
    for name, digest in data['backend_reference'].items():
        p = safe_path(target, name)
        if not p.is_file() or sha(p) != digest:
            incompatible.append(name)
    changes = []
    for name, expected in data['frontend'].items():
        p = safe_path(target, name)
        if p.exists() and not p.is_file():
            raise ValueError('Un fichier est attendu : ' + name)
        current = sha(p) if p.exists() else None
        if current != expected:
            changes.append({'file': name, 'before': current, 'after': expected,
                            'state': 'absent' if current is None else 'different'})
    return {'compatible': not incompatible, 'backend_different': incompatible,
            'changes': changes, 'already_correct': not changes, 'database_access': False}


def atomic_copy(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.nelyio-f2-', suffix='.tmp', dir=dest.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temp)
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply(target: Path, package: Path, stopped: bool = False) -> dict:
    if not stopped:
        raise ValueError('Confirmez l arret de Nelyio, de la collecte et des imports')
    result = inspect(target, package)
    if not result['compatible']:
        raise ValueError('Version backend differente : ' + ', '.join(result['backend_different']))
    if not result['changes']:
        return {'already_correct': True, 'backup': None}
    data, payload = manifest(package)
    if target.resolve() == payload or target.resolve().is_relative_to(payload):
        raise ValueError('Le dossier cible doit etre separe des fichiers source du paquet')
    backup = Path(tempfile.mkdtemp(prefix='NELYIO_SAUVEGARDE_F2_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '_', dir=target.parent))
    saved = {'target': str(target.resolve()), 'files': result['changes'], 'lot': data['lot']}
    for entry in saved['files']:
        if entry['before'] is not None:
            p = safe_path(backup, entry['file']);p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(safe_path(target, entry['file']), p)
            if sha(p) != entry['before']:
                raise ValueError('Sauvegarde non conforme : ' + entry['file'])
    write_json(backup/'RESTAURATION.json', saved)
    written = []
    try:
        # Refuse une modification locale survenue depuis la verification.
        for entry in saved['files']:
            p = safe_path(target, entry['file'])
            if (sha(p) if p.exists() else None) != entry['before']:
                raise ValueError('Le fichier a change pendant la preparation : ' + entry['file'])
        for entry in saved['files']:
            p = safe_path(target, entry['file']);atomic_copy(safe_path(payload, entry['file']), p)
            written.append(entry)
            if sha(p) != entry['after']:
                raise ValueError('Copie non conforme : ' + entry['file'])
    except Exception:
        for entry in reversed(written):
            p = safe_path(target, entry['file'])
            if entry['before'] is None:
                p.unlink(missing_ok=True)
            else:
                atomic_copy(safe_path(backup, entry['file']), p)
        raise
    write_json(backup/'INSTALLATION.json', {'verified': True, 'database_access': False})
    return {'backup': str(backup), 'files_written': len(written), 'verified': inspect(target, package)['already_correct']}


def rollback(target: Path, backup: Path, stopped: bool = False) -> dict:
    if not stopped:
        raise ValueError('Confirmez l arret des processus avant restauration')
    state = json.loads((backup/'RESTAURATION.json').read_text(encoding='utf-8'))
    if state.get('lot') != 'V56.8-F2-REPARATION' or Path(state['target']).resolve() != target.resolve():
        raise ValueError('Sauvegarde destinee a une autre installation')
    for entry in state['files']:
        name = entry['file']
        if name != 'index.html' and not (name.startswith('static/') and Path(name).suffix in {'.js','.css'}):
            raise ValueError('Fichier non autorise dans la restauration')
        p = safe_path(target, name)
        if not p.is_file() or sha(p) != entry['after']:
            raise ValueError('Fichier modifie depuis la reparation : ' + name)
        if entry['before'] is not None:
            p = safe_path(backup, name)
            if not p.is_file() or sha(p) != entry['before']:
                raise ValueError('Sauvegarde incomplete : ' + name)
    for entry in state['files']:
        p = safe_path(target, entry['file'])
        if entry['before'] is None:
            p.unlink()
        else:
            atomic_copy(safe_path(backup, entry['file']), p)
    return {'restored': len(state['files']), 'database_access': False}


def diagnose_url(base: str, package: Path) -> dict:
    """GET des seuls fichiers web publics : aucun identifiant ni contenu metier."""
    u = urlsplit(base)
    if u.scheme not in {'http','https'} or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:
        raise ValueError('Indiquez une origine http(s) sans mot de passe ni chemin')
    data, _ = manifest(package)
    rows = []
    for name, expected in data['frontend'].items():
        path = '/' if name == 'index.html' else '/' + name + '?v=F2-' + expected[:16]
        row = {'file': name}
        try:
            # Validation TLS normale, aucun mode insecure ni bypass de certificat.
            req = Request(base.rstrip('/')+path, headers={'Cache-Control':'no-cache', 'Accept-Encoding':'identity'})
            with urlopen(req, timeout=8) as r:
                if urlsplit(r.url).netloc != u.netloc:
                    raise ValueError('Redirection vers une autre origine')
                content = r.read(5_000_001)
                if len(content) > 5_000_000:
                    raise ValueError('Reponse anormalement volumineuse')
                mime = r.headers.get_content_type()
                allowed = {'text/html'} if name == 'index.html' else ({'text/css'} if name.endswith('.css') else {'application/javascript','text/javascript'})
                digest = hashlib.sha256(content).hexdigest()
                row.update(status=r.status, content_type=mime, sha256=digest, identical=digest==expected,
                           ok=r.status==200 and mime in allowed and digest==expected)
        except (HTTPError, URLError, OSError, ValueError) as exc:
            row.update(ok=False, error=str(exc))
        rows.append(row)
        if name == 'index.html' and 'error' in row:
            break
    return {'url':base, 'ok':len(rows)==len(data['frontend']) and all(r['ok'] for r in rows), 'files':rows,
            'scope':'Transport HTTP, type MIME et empreinte ; pas une execution JavaScript du navigateur.'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--interactive',action='store_true')
    parser.add_argument('--confirm-stopped',action='store_true')
    parser.add_argument('--rollback',type=Path)
    parser.add_argument('--url')
    parser.add_argument('--report',type=Path,default=Path('DIAGNOSTIC_FRONTEND_F2.json'))
    a=parser.parse_args()
    try:
        if a.url:
            result=diagnose_url(a.url,a.package)
            write_json(a.report,result);print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['ok'] else 2
        interactive=a.interactive or a.target is None
        if a.target is None:
            entered=input('Dossier Nelyio contenant app.py (Annuler : entree vide) : ').strip().strip('"')
            if not entered:
                print('Annule. Aucun fichier modifie.');return 2
            a.target=Path(entered)
        a.target=a.target.resolve();result=inspect(a.target,a.package)
        write_json(a.report,result)
        print('Backend compatible :',result['compatible'],'; fichiers web a remplacer :',len(result['changes']))
        for row in result['changes']:print(' -',row['file'],':',row['state'])
        if not result['compatible']:
            print('Arret. Fichiers differents :',', '.join(result['backend_different']));return 2
        if interactive and result['changes']:
            print('Une sauvegarde des seuls fichiers web sera creee a cote du dossier Nelyio.')
            print('Les personnalisations de ces fichiers seront remplacees. Aucune base ne sera ouverte.')
            a.apply=input('Nelyio, collecte et imports arretes ? Appliquer la reparation : taper OUI : ').strip()=='OUI'
            a.confirm_stopped=a.apply
        if a.rollback:
            result=rollback(a.target,a.rollback,a.confirm_stopped)
        elif a.apply:
            result=apply(a.target,a.package,a.confirm_stopped)
        else:
            return 0
        write_json(a.report,result);print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except Exception as exc:
        print('ERREUR :',exc,file=sys.stderr)
        write_json(a.report,{'error':str(exc),'database_access':False});return 1


if __name__ == '__main__':
    raise SystemExit(main())
