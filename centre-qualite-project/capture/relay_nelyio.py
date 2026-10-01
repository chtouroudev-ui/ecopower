"""Send locally captured transitions to Nelyio. Python standard library only.
Reads SQLite in read-only mode. Cursor advances only after server acknowledgement.
No agent/customer telephone numbers are transmitted.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from error_log import log_unexpected_error
import sqlite3, json, time, uuid, urllib.request, urllib.parse, argparse, getpass
from pathlib import Path
from datetime import datetime

def run_once(cfg, state, state_path):
    path=Path(cfg['database']).resolve()
    if not path.is_file():raise FileNotFoundError('Base de capture introuvable : '+str(path))
    uri=path.as_uri()+'?mode=ro'
    con=sqlite3.connect(uri,uri=True,timeout=2)
    try:
        maximum=con.execute('SELECT COALESCE(MAX(id),0) FROM log_lines').fetchone()[0]
        cursor=state['cursor'] if maximum>=state['cursor'] else 0
        rows=con.execute('SELECT id,ts,line FROM log_lines WHERE id>? ORDER BY id LIMIT 2000',(cursor,)).fetchall()
    finally:con.close()
    payload=[]
    for ident,ts,line in rows:
        if any(tag in line for tag in [' | ETAT | Agent ', ' | ETAT_INITIAL | Agent ', 'NELYIO_HEARTBEAT', 'DECONNEXION_EN_APPEL', 'MICRO_ERREUR', 'ERREUR_CAPTURE', 'ERREUR_SCRIPT', 'AVERTISSEMENT_BUFFER_DEVTOOLS', 'WATCHDOG']):
            # Keep state and campaign only; drop all phone and raw body fields.
            line=line.split(' | numero=',1)[0]
            payload.append(dict(ts=ts,line=line))
    data=json.dumps(dict(source=state['source'],rows=payload)).encode()
    request=urllib.request.Request(cfg['url'].rstrip('/')+'/api/supervision/ingest',data=data,
        headers={'Content-Type':'application/json','X-Nelyio-Capture-Key':cfg['key']},method='POST')
    with urllib.request.urlopen(request,timeout=15) as response:
        result=json.load(response)
    if result.get('accepted')!=len(payload):raise ValueError('Accusé de réception incomplet')
    state['cursor']=rows[-1][0] if rows else cursor
    tmp=state_path.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(state_path)
    return len(rows),len(payload)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--configure',action='store_true');args=ap.parse_args()
    base=Path(__file__).resolve().parent;cp=base/'relay_config.json';sp=base/'relay_cursor.json'
    if args.configure or not cp.exists():
        url=input('URL Nelyio (ex. https://nelyio.exemple.fr) : ').strip().rstrip('/')
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme not in ('http','https') or not parsed.netloc:raise ValueError('URL invalide')
        if parsed.scheme=='http' and parsed.hostname not in ('localhost','127.0.0.1','::1'):
            raise ValueError('Utiliser HTTPS lorsque le serveur est sur un autre PC.')
        database=input('Base de capture [C:\\Logs\\hermes_supervision.db] : ').strip() or r'C:\Logs\hermes_supervision.db'
        key=getpass.getpass('Clé copiée depuis la configuration Nelyio : ').strip()
        if not key:raise ValueError('Clé vide')
        cp.write_text(json.dumps(dict(url=url,database=database,key=key),indent=2))
    cfg=json.loads(cp.read_text());state=json.loads(sp.read_text()) if sp.exists() else dict(source='capture-'+uuid.uuid4().hex,cursor=0)
    # Re-read once after upgrading to transmit past technical signals too.
    # Existing transitions and heartbeats remain idempotent at the server.
    if state.get('protocol',1)<2:
        state['cursor']=0;state['protocol']=2
        sp.write_text(json.dumps(state))
    # Persist stable identity before the first network attempt.
    if not sp.exists():sp.write_text(json.dumps(state))
    print('Relais Nelyio actif. Ctrl+C pour arrêter. Les erreurs sont réessayées sans avancer le curseur.')
    while True:
        try:
            count,sent=run_once(cfg,state,sp)
            if sent:print(datetime.now().strftime('%H:%M:%S'),sent,'observations transmises')
            time.sleep(0.1 if count==2000 else 5)
        except KeyboardInterrupt:break
        except Exception as exc:
            log_unexpected_error('capture.relay_nelyio.main.L63')
            print(datetime.now().strftime('%H:%M:%S'),'Relais en attente :',str(exc));time.sleep(5)
if __name__=='__main__':main()
