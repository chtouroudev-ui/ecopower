"""Hermes recording metadata sync for Nelyio.

Only folder metadata is read from the already authenticated, LOCAL Edge
supervision tab.  Audio files, browser cookies, credentials and session tokens
are never persisted.  The Hermes session parameters are kept only in memory.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from collection_cdp import CaptureError, local_targets
from supervision_db import connect

FOLDER_PATH = '/hermes360/Supervision/changes.ashx'
FILE_RE = re.compile(r'^([^#]+)#(\d{8})#(\d{6})#([^#.]+)\.wav$', re.I)
MAX_DAYS = 31
SYNC_STATE_PATH = Path(__file__).resolve().parent / 'data' / 'recording_size_sync_state.json'
MAX_REQUESTS = 10000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_FOLDER_DEPTH = 8
RECORDING_SIZE_CONTRACT_VERSION = '3'
SYNC_STATE_VERSION = 2


def ensure_schema(c):
    # RC12 keeps only Indice + Size in the persistent business table, but
    # invalidates RC4-RC11 values once because those generations did not prove
    # that the WAV date/agent matched the SIMPLIFY2 call.
    c.execute("CREATE TABLE IF NOT EXISTS call_recording_sizes(indice TEXT PRIMARY KEY,size_bytes INTEGER NOT NULL)")
    try:
        row=c.execute("SELECT value FROM settings WHERE key='recording_size_contract_version'").fetchone()
        current=str((row[0] if row and not hasattr(row,'keys') else (row['value'] if row else '')) or '')
        if current != RECORDING_SIZE_CONTRACT_VERSION:
            c.execute('DELETE FROM call_recording_sizes')
            c.execute("""INSERT INTO settings(key,value) VALUES('recording_size_contract_version',?)
              ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(RECORDING_SIZE_CONTRACT_VERSION,))
            try:
                SYNC_STATE_PATH.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        # Fresh/unit schemas may initialize settings later. Crucially, no old
        # unverified recording rows are migrated into the active table.
        pass


def parse_file(item):
    if not isinstance(item, dict):
        return None
    name=str(item.get('Name') or '').strip()
    m=FILE_RE.match(name)
    if not m:
        return None
    try:size=int(item.get('Size'))
    except (TypeError,ValueError):return None
    if size < 0:return None
    agent,ymd,hms,indice=m.groups()
    if not indice or indice=='0':
        return None
    # These fields are transient validation evidence only. RC12 still persists
    # exactly Indice + Size after the call match has been proven.
    recorded_day=f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}'
    return dict(filename=name,indice=indice,size_bytes=size,agent=agent,recorded_day=recorded_day,recorded_time=hms)


def parse_folder_payload(text):
    if not isinstance(text,str) or len(text.encode('utf-8'))>MAX_RESPONSE_BYTES:
        raise ValueError('Réponse folder_info trop volumineuse.')
    data=json.loads(text)
    if not isinstance(data,dict):raise ValueError('Réponse folder_info invalide.')
    folders=[str(x) for x in (data.get('FolderList') or []) if str(x).strip()]
    files=[]
    for item in data.get('FileList') or []:
        row=parse_file(item)
        if row:files.append(row)
    return folders,files


def _aggregate_sizes(rows):
    # Deduplicate identical WAV metadata in memory, then aggregate every piece
    # belonging to the same Indice. Only Indice + total Size survives.
    totals=defaultdict(int)
    seen=set();wav_count=0
    for r in rows or []:
        key=str(r.get('filename') or '').strip()
        if key and key in seen:
            continue
        if key:seen.add(key)
        indice=str(r.get('indice') or '').strip()
        if not indice:
            continue
        totals[indice]+=max(0,int(r.get('size_bytes') or 0));wav_count+=1
    return totals,wav_count


def _agent_token(value):
    text=str(value or '').strip()
    m=re.fullmatch(r'[sS]?(\d{3,10})',text)
    return m.group(1) if m else text.casefold()


def _verified_totals(rows, c):
    # Validate transient WAV metadata against imported SIMPLIFY2 calls.
    # Accepted only when Indice resolves to exactly one positive-conversation
    # call on the same reference day and the recording agent is coherent.
    grouped=defaultdict(list)
    seen=set();wav_count=0
    for r in rows or []:
        key=str(r.get('filename') or '').strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        indice=str(r.get('indice') or '').strip()
        if not indice:
            continue
        grouped[indice].append(r);wav_count+=1
    if not grouped:
        return {},wav_count,0

    call_map=defaultdict(list)
    indices=list(grouped)
    for pos in range(0,len(indices),400):
        chunk=indices[pos:pos+400]
        marks=','.join('?' for _ in chunk)
        sql=("SELECT p.indice,p.call_id,p.conversation,p.first_agent,p.last_agent,"
             "COALESCE(i.reference_day,'') AS reference_day "
             "FROM phone_calls p LEFT JOIN imports i ON i.id=p.import_id "
             f"WHERE p.indice IN ({marks})")
        for row in c.execute(sql,chunk).fetchall():
            if hasattr(row,'keys'):
                vals=dict(indice=str(row['indice'] or ''),call_id=str(row['call_id'] or ''),
                          conversation=float(row['conversation'] or 0),first_agent=str(row['first_agent'] or ''),
                          last_agent=str(row['last_agent'] or ''),reference_day=str(row['reference_day'] or ''))
            else:
                vals=dict(indice=str(row[0] or ''),call_id=str(row[1] or ''),conversation=float(row[2] or 0),
                          first_agent=str(row[3] or ''),last_agent=str(row[4] or ''),reference_day=str(row[5] or ''))
            call_map[vals['indice']].append(vals)

    totals={};rejected=0
    for indice,pieces in grouped.items():
        days={str(x.get('recorded_day') or '') for x in pieces if x.get('recorded_day')}
        agents={_agent_token(x.get('agent')) for x in pieces if x.get('agent')}
        candidates=[]
        for call in call_map.get(indice,[]):
            if call['conversation']<=0:
                continue
            if days and call['reference_day'] not in days:
                continue
            call_agents={_agent_token(call['first_agent']),_agent_token(call['last_agent'])}-{'',None}
            if agents and call_agents and not (agents & call_agents):
                continue
            candidates.append(call)
        unique={x['call_id']:x for x in candidates}
        if len(unique)!=1:
            rejected+=1
            continue
        totals[indice]=sum(max(0,int(x.get('size_bytes') or 0)) for x in pieces)
    return totals,wav_count,rejected


def store(rows, *, source='hermes_record_folder', now=None):
    with connect() as c:
        ensure_schema(c)
        totals,_wav_count,_rejected=_verified_totals(rows,c)
        if not totals:
            return 0
        for indice,size in totals.items():
            c.execute("""INSERT INTO call_recording_sizes(indice,size_bytes) VALUES(?,?)
              ON CONFLICT(indice) DO UPDATE SET size_bytes=excluded.size_bytes""",(indice,int(size)))
        c.commit()
    return len(totals)

def known_recording_agents():
    """Return numeric agent ids already known by Nelyio.

    Hermes can occasionally return an incomplete FolderList for a day even
    though additional agent recording folders exist. Nelyio already has an
    agent catalogue from SIMPLIFY2 imports, so probe missing numeric agent
    folders directly without opening them in the UI.

    This is best-effort: an empty/new database must not prevent the normal
    FolderList traversal from working.
    """
    try:
        from supervision_utils import latest_agent_names
        with connect() as c:
            ids=latest_agent_names(c).keys()
    except Exception:
        return []
    out=set()
    for raw in ids:
        text=str(raw or '').strip()
        m=re.fullmatch(r'[sS]?(\d{3,10})',text)
        if m:
            out.add(m.group(1))
    return sorted(out,key=lambda x:(len(x),x))


def _child_path(parent, child):
    parent=str(parent or '').replace('/','\\').strip('\\')
    child=str(child or '').replace('/','\\').strip('\\')
    if not child:
        return parent
    pcf=parent.casefold();ccf=child.casefold()
    if ccf==pcf or ccf.startswith(pcf+'\\'):
        return child
    return parent+'\\'+child if parent else child


def _root_id(value, *, require_label=False):
    """Extract a top-level RECORD folder id from a Hermes label/path.

    The UI displays roots such as ``76431213 - CIMVES-HABERGES`` while
    folder_info paths use only the numeric id.  Agent ids are 4 digits in this
    installation, so requiring at least 6 digits prevents confusing agents
    with RECORD roots.  DOM text must contain the visible ``id - label`` form
    to avoid matching call Indice values shown in the recordings grid.
    """
    text=str(value or '').strip().replace('\u00a0',' ')
    if require_label:
        m=re.match(r'^(\d{6,12})\s*-\s*\S',text)
    else:
        m=re.match(r'^(\d{6,12})(?:\s*-\s*\S|$)',text)
    return m.group(1) if m else ''


def _root_from_path(path):
    parts=[x for x in str(path or '').replace('/','\\').strip('\\').split('\\') if x]
    return parts[0] if parts and re.fullmatch(r'\d{6,12}',parts[0]) else ''


def _dedupe_recordings(rows):
    # A recording can be reached once through FolderList and once through the
    # agent-catalogue fallback. Filename is already the storage primary key;
    # dedupe here as well so scan metrics remain accurate.
    return list({r['filename']:r for r in rows}.values())


def collect_folder_tree(browser, seed, start_path, *, stats=None, visited=None,
                        depth=0, max_depth=MAX_FOLDER_DEPTH, pause=.05):
    """Recursively collect WAV metadata below one Hermes folder."""
    if depth>max_depth:
        raise ValueError('Arborescence Enregistrements trop profonde; synchronisation interrompue par sécurité.')
    stats=stats if stats is not None else {}
    visited=visited if visited is not None else set()
    path=str(start_path or '').replace('/','\\').strip('\\')
    key=path.casefold()
    if not path or key in visited:
        return []
    visited.add(key)
    stats['requests']=int(stats.get('requests',0))+1
    if stats['requests']>MAX_REQUESTS:
        raise ValueError('Trop de dossiers pour une seule synchronisation.')
    folders,files=parse_folder_payload(browser.post_json(seed,path))
    stats['folders_returned']=int(stats.get('folders_returned',0))+len(folders)
    if files:
        stats['folders_with_wav']=int(stats.get('folders_with_wav',0))+1
    rows=list(files)
    for folder in folders:
        rows.extend(collect_folder_tree(
            browser,seed,_child_path(path,folder),stats=stats,visited=visited,
            depth=depth+1,max_depth=max_depth,pause=pause))
        if pause:time.sleep(pause)
    return rows


def collect_day(browser, seed, day_path, *, agent_ids=None, pause=.05, initial_payload=None,
                probe_known_agents=True):
    """Collect one RECORD root/day then descend through every returned folder.

    ``initial_payload`` may contain the exact response generated when the user
    clicks the requested day in Hermes.  The day FolderList is authoritative
    for that RECORD root.  ``probe_known_agents`` is kept only as a legacy
    safety net for single-root layouts; multi-root RC8 scans trust each root's
    own FolderList so an empty root does not trigger ~100 pointless probes.
    """
    stats={'requests':0,'folders_returned':0,'folders_with_wav':0,
           'agents_probed':0,'agents_with_wav':0,'probe_errors':0,
           'anchor_folders':0,'anchor_files':0,'day_folders':0}
    visited=set()
    path=str(day_path or '').replace('/','\\').strip('\\')
    visited.add(path.casefold())
    if initial_payload is not None:
        folders,files=parse_folder_payload(initial_payload)
        stats['requests']=1  # exact Hermes UI request captured through CDP
        stats['anchor_folders']=len(folders)
        stats['anchor_files']=len(files)
    else:
        stats['requests']=1
        folders,files=parse_folder_payload(browser.post_json(seed,path))
    stats['day_folders']=len(folders)
    stats['folders_returned']=len(folders)
    stats['folders_with_wav']=1 if files else 0
    rows=list(files)
    for folder in folders:
        rows.extend(collect_folder_tree(
            browser,seed,_child_path(path,folder),stats=stats,visited=visited,
            depth=1,pause=pause))
        if pause:time.sleep(pause)

    if probe_known_agents:
        for agent in sorted({str(x).strip() for x in (agent_ids or []) if str(x).strip()}):
            apath=_child_path(path,agent)
            if apath.casefold() in visited:
                continue
            stats['agents_probed']+=1
            before=len(rows)
            try:
                extra=collect_folder_tree(browser,seed,apath,stats=stats,visited=visited,pause=pause)
            except CaptureError:
                stats['probe_errors']+=1
                continue
            rows.extend(extra)
            if len(rows)>before:
                stats['agents_with_wav']+=1
            if pause:time.sleep(pause)
    return _dedupe_recordings(rows),stats


def extract_seed(urls):
    """Return an in-memory folder_info template without persisting its uid.

    RC9 accepts the RECORD root-list request itself (``subPath=``) as a valid
    session seed.  Earlier versions required a path that already contained a
    year, which forced the operator to drill manually into one SDA/campaign.
    The session parameters are identical at the root level, so opening the
    Enregistrements window is sufficient.
    """
    for raw in reversed(list(urls)):
        try:u=urlsplit(str(raw))
        except Exception:continue
        if u.scheme not in ('http','https') or u.path.casefold()!=FOLDER_PATH.casefold():continue
        q=parse_qs(u.query,keep_blank_values=True)
        if (q.get('act') or [''])[0] != 'folder_info':continue
        if (q.get('basePath') or [''])[0].upper() != 'RECORD':continue
        uid=(q.get('uid') or [''])[0]
        company=(q.get('idCompany') or [''])[0]
        if not uid or not company:continue
        sub=(q.get('subPath') or [''])[0].replace('/','\\').strip('\\')
        parts=[x for x in sub.split('\\') if x]
        year_idx=next((i for i,x in enumerate(parts) if re.fullmatch(r'20\d{2}',x)),None)
        root='\\'.join(parts[:year_idx]) if year_idx is not None and year_idx>=1 else ''
        origin=urlunsplit((u.scheme,u.netloc,'','',''))
        params={k:(v[0] if v else '') for k,v in q.items()}
        return dict(origin=origin,uid=uid,idCompany=company,root=root,params=params,referrer='')
    return None


class BrowserSession:
    def __init__(self, port=9222, match='Supervision', target_id=''):
        self.port=int(port);self.match=match;self.target_id=target_id;self.ws=None;self._ws_cm=None;self.seq=0
    def __enter__(self):
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise CaptureError('Module websockets absent. Lancez INSTALL_CAPTURE_DEPENDENCIES.bat.') from exc
        targets=local_targets(self.port,self.match)
        if self.target_id:targets=[t for t in targets if t['id']==self.target_id]
        if len(targets)!=1:
            raise CaptureError('Sélectionnez exactement un onglet Supervision dans la fenêtre Edge de collecte.')
        self.target=targets[0]
        options=dict(open_timeout=3,close_timeout=1,max_size=MAX_RESPONSE_BYTES*2,compression=None)
        # Keep the websocket inside its supported context-manager lifecycle.
        # This removes the websockets deprecation warning while remaining
        # compatible with the synchronous API used by the existing collector.
        self._ws_cm=connect(self.target['websocket'],**options)
        if hasattr(self._ws_cm,'__enter__'):
            self.ws=self._ws_cm.__enter__()
        else:
            self.ws=self._ws_cm
        self.call('Runtime.enable',{})
        self.call('Network.enable',{})
        return self
    def __exit__(self,exc_type,exc,tb):
        if self._ws_cm and hasattr(self._ws_cm,'__exit__'):
            try:self._ws_cm.__exit__(exc_type,exc,tb)
            except Exception:pass
        elif self.ws:
            try:self.ws.close()
            except Exception:pass
        self.ws=None;self._ws_cm=None
    def call(self,method,params,timeout=15):
        self.seq+=1;ident=self.seq
        self.ws.send(json.dumps({'id':ident,'method':method,'params':params}))
        end=time.time()+timeout
        while time.time()<end:
            try:raw=self.ws.recv(timeout=max(.1,end-time.time()))
            except TimeoutError:break
            msg=json.loads(raw)
            if msg.get('id')!=ident:continue
            if msg.get('error'):raise CaptureError('Commande navigateur refusée : '+str(msg['error'].get('message') or 'erreur CDP'))
            return msg.get('result') or {}
        raise CaptureError('Délai navigateur dépassé pendant la synchronisation des tailles.')
    def resource_urls(self):
        # Hermes Supervision uses same-origin frames.  Recording requests can be
        # issued by a child frame, so scanning only the top page misses them.
        expr=r"""(()=>{const out=[];const seen=new Set();function walk(w){try{if(seen.has(w))return;seen.add(w);try{out.push(String(w.location.href||''));}catch(e){}try{for(const x of (w.performance?.getEntriesByType('resource')||[])){const n=String(x.name||'');if(n.includes('act=folder_info')&&n.includes('basePath=RECORD'))out.push(n);}}catch(e){}try{for(let i=0;i<w.frames.length;i++)walk(w.frames[i]);}catch(e){}}catch(e){}}walk(window);return JSON.stringify([...new Set(out)].slice(-500));})()"""
        r=self.call('Runtime.evaluate',{'expression':expr,'returnByValue':True})
        value=((r.get('result') or {}).get('value')) or '[]'
        try:return json.loads(value)
        except Exception:return []
    @staticmethod
    def _folder_request_info(url):
        try:u=urlsplit(str(url or ''))
        except Exception:return None
        if u.scheme not in ('http','https') or u.path.casefold()!=FOLDER_PATH.casefold():return None
        q=parse_qs(u.query,keep_blank_values=True)
        if (q.get('act') or [''])[0] != 'folder_info':return None
        if (q.get('basePath') or [''])[0].upper() != 'RECORD':return None
        sub=(q.get('subPath') or [''])[0].replace('/','\\').strip('\\')
        if not sub:return None
        return u,q,sub

    def recording_root_ids_from_dom(self):
        """Read all visible/loaded top-level RECORD roots from Hermes UI frames.

        The file manager renders labels such as ``76430929 - CH GISORS``.  We
        inspect text nodes (plus common label attributes) across same-origin
        frames.  Indice values in the recordings table are ignored because DOM
        candidates must contain the visible ``numeric-id - label`` form.
        """
        expr=r"""(()=>{const out=new Set(),seen=new Set(),rx=/^(\d{6,12})\s*-\s*\S/;
function take(v){const s=String(v||'').replace(/\u00a0/g,' ').trim().replace(/\s+/g,' ');const m=s.match(rx);if(m)out.add(m[1]);}
function walk(w){try{if(seen.has(w))return;seen.add(w);let d;try{d=w.document;}catch(e){return;}if(!d)return;
try{const root=d.body||d.documentElement;if(root){const tw=d.createTreeWalker(root,NodeFilter.SHOW_TEXT);let n;while((n=tw.nextNode()))take(n.nodeValue);}}
catch(e){}
try{for(const el of d.querySelectorAll('[title],[aria-label],[data-text],[data-name]')){take(el.getAttribute('title'));take(el.getAttribute('aria-label'));take(el.getAttribute('data-text'));take(el.getAttribute('data-name'));}}catch(e){}
try{for(let i=0;i<w.frames.length;i++)walk(w.frames[i]);}catch(e){}
}catch(e){}}
walk(window);return JSON.stringify([...out]);})()"""
        r=self.call('Runtime.evaluate',{'expression':expr,'returnByValue':True})
        value=((r.get('result') or {}).get('value')) or '[]'
        try:raw=json.loads(value)
        except Exception:raw=[]
        return sorted({x for x in (_root_id(v) for v in raw) if x})

    def discover_recording_roots(self, seed, anchor_path=''):
        """Discover every top-level RECORD root without opening WAV files."""
        roots=set()
        anchor=_root_from_path(anchor_path) or str(seed.get('root') or '').split('\\')[0]
        if anchor:roots.add(anchor)
        # Existing folder_info resource URLs can reveal roots already touched in
        # this browser session.
        for raw in self.resource_urls():
            info=self._folder_request_info(raw)
            if info:
                rid=_root_from_path(info[2])
                if rid:roots.add(rid)
        # Prefer server root enumeration when Hermes accepts subPath="".
        try:
            folders,_=parse_folder_payload(self.post_json(seed,''))
            for label in folders:
                rid=_root_id(label)
                if rid:roots.add(rid)
        except Exception:
            pass
        # The current Hermes UI exposes all clinic RECORD roots in its tree.
        try:roots.update(self.recording_root_ids_from_dom())
        except Exception:pass
        return sorted(roots,key=lambda x:(len(x),x))

    def wait_day_anchor(self, day, seconds=90):
        """Capture the exact Hermes request/response produced by one day click.

        This avoids relying on stale Resource Timing entries and preserves the
        request's referrer/query context. Only one click on the requested day is
        needed; agent folders and WAV files are still crawled automatically.
        """
        suffix=day.strftime('%Y\\%m\\%d').casefold()
        print('INFO - Session Hermes détectée.')
        print('INFO - Dans Enregistrements, cliquez maintenant UNE seule fois sur le dossier du jour '+day.strftime('%d/%m/%Y')+'.')
        print('INFO - Ne cliquez sur aucun agent ni aucun WAV. Nelyio fera le reste automatiquement.')
        deadline=time.time()+seconds
        matched=None
        while time.time()<deadline:
            try:raw=self.ws.recv(timeout=min(.5,max(.1,deadline-time.time())))
            except TimeoutError:continue
            try:msg=json.loads(raw)
            except Exception:continue
            if msg.get('method')!='Network.requestWillBeSent':continue
            params=msg.get('params') or {}; req=params.get('request') or {}
            info=self._folder_request_info(req.get('url',''))
            if not info:continue
            _,_,sub=info
            if not sub.casefold().endswith(suffix):continue
            seed=extract_seed([req.get('url','')])
            if not seed:continue
            headers=req.get('headers') or {}
            seed['referrer']=str(headers.get('Referer') or headers.get('referer') or params.get('documentURL') or '')
            matched=(str(params.get('requestId') or ''),seed,sub)
            break
        if not matched:
            raise CaptureError('Aucune requête du dossier '+day.strftime('%d/%m/%Y')+' détectée. Laissez ce programme ouvert puis cliquez une fois sur CE JOUR dans Enregistrements.')
        request_id,seed,sub=matched
        # Wait for the exact UI request to finish, then read its body through CDP.
        finished=False
        deadline=time.time()+20
        while time.time()<deadline:
            try:raw=self.ws.recv(timeout=min(.5,max(.1,deadline-time.time())))
            except TimeoutError:continue
            try:msg=json.loads(raw)
            except Exception:continue
            if msg.get('method')=='Network.loadingFinished' and str((msg.get('params') or {}).get('requestId') or '')==request_id:
                finished=True;break
            if msg.get('method')=='Network.loadingFailed' and str((msg.get('params') or {}).get('requestId') or '')==request_id:
                raise CaptureError('La requête Hermes du jour sélectionné a échoué.')
        body=''
        if finished:
            try:
                result=self.call('Network.getResponseBody',{'requestId':request_id},timeout=10)
                body=str(result.get('body') or '')
                if result.get('base64Encoded'):
                    body=base64.b64decode(body).decode('utf-8','replace')
            except Exception:
                body=''
        if not body:
            # Last-resort replay uses the exact captured URL/referrer template.
            body=self.post_json(seed,sub)
        folders,files=parse_folder_payload(body)
        print('INFO - Réponse réelle du jour capturée :',len(folders),'dossiers,',len(files),'WAV au niveau jour.')
        return seed,sub,body

    def wait_seed(self,seconds=75):
        # First reuse any recording request still visible in the main page or a
        # same-origin frame.  If none exists, keep CDP listening while the user
        # opens Enregistrements once; relaunching after the click is not needed.
        seed=extract_seed(self.resource_urls())
        if seed:return seed
        print('INFO - Session Hermes trouvée, mais la zone Enregistrements n’a pas encore fourni de contexte RECORD exploitable.')
        print('INFO - Pendant que ce programme reste ouvert, ouvrez maintenant Enregistrements UNE seule fois dans la Supervision.')
        print('INFO - Restez au niveau des SDA/campagnes. Ne naviguez ni dans une année, ni dans un mois, ni dans un jour.')
        print(f'INFO - Attente maximale : {int(seconds)} secondes. Nelyio parcourra toute la hiérarchie automatiquement.')
        deadline=time.time()+seconds
        while time.time()<deadline:
            try:raw=self.ws.recv(timeout=min(.5,max(.1,deadline-time.time())))
            except TimeoutError:continue
            try:msg=json.loads(raw)
            except Exception:continue
            if msg.get('method')!='Network.requestWillBeSent':continue
            req=(msg.get('params') or {}).get('request') or {}
            seed=extract_seed([req.get('url','')])
            if seed:return seed
        # Final frame scan covers cases where the request completed while CDP
        # was processing another command but remains in Resource Timing.
        seed=extract_seed(self.resource_urls())
        if seed:return seed
        raise CaptureError('Aucune session RECORD détectée. Laissez ce programme ouvert puis ouvrez Enregistrements dans l’onglet Supervision sélectionné, sans entrer dans les dossiers. Vérifiez aussi qu’un seul onglet Supervision correspond au port 9222.')
    def post_json(self, seed, subpath):
        q=dict(seed.get('params') or {})
        q.update({'act':'folder_info','uid':seed['uid'],'idCompany':seed['idCompany'],
                  'extension':q.get('extension') or '*.wav','basePath':'RECORD','subPath':subpath})
        if 'filters' not in q:q['filters']=''
        url=seed['origin']+FOLDER_PATH+'?'+urlencode(q)
        # Replay the same-origin request with the exact captured query template
        # and, when available, the original GetChanges referrer.
        opts={'method':'POST','credentials':'include','headers':{'content-type':'text/xml; charset=utf-8','content-encoding':'utf-8'}}
        if seed.get('referrer'):opts['referrer']=seed['referrer']
        js="""(async()=>{const r=await fetch(%s,%s);const t=await r.text();return JSON.stringify({status:r.status,text:t});})()""" % (json.dumps(url),json.dumps(opts))
        r=self.call('Runtime.evaluate',{'expression':js,'awaitPromise':True,'returnByValue':True},timeout=20)
        if r.get('exceptionDetails'):raise CaptureError('La supervision a refusé la lecture des métadonnées d’enregistrement.')
        value=((r.get('result') or {}).get('value'))
        try:obj=json.loads(value)
        except Exception as exc:raise CaptureError('Réponse folder_info non lisible.') from exc
        if int(obj.get('status') or 0)!=200:raise CaptureError('Hermes a répondu HTTP '+str(obj.get('status'))+' pendant la lecture des tailles.')
        return str(obj.get('text') or '')



def _load_sync_state():
    try:
        data=json.loads(SYNC_STATE_PATH.read_text(encoding='utf-8'))
        days={str(x) for x in (data.get('completed_days') or []) if re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(x))}
        roots={str(x) for x in (data.get('roots') or []) if str(x).strip()}
        return {'completed_days':days,'roots':roots,'version':int(data.get('version') or 0)}
    except Exception:
        return {'completed_days':set(),'roots':set(),'version':0}


def _save_sync_state(state):
    SYNC_STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    payload={'version':SYNC_STATE_VERSION,'completed_days':sorted(state.get('completed_days') or []),'roots':sorted(state.get('roots') or []),'updated_at':time.time()}
    tmp=SYNC_STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    tmp.replace(SYNC_STATE_PATH)


def _numeric_children(folders, pattern):
    rx=re.compile(pattern);out=[]
    for raw in folders or []:
        text=str(raw or '').strip().replace('/','\\').strip('\\')
        leaf=text.split('\\')[-1]
        if rx.fullmatch(leaf):out.append(leaf)
    return sorted(set(out))


def discover_history_days(browser, seed, roots, *, pause=.02):
    """Return {YYYY-MM-DD: [root,...]} from Hermes folder metadata only."""
    by_day=defaultdict(set);requests=0
    for root in roots:
        try:
            years,_=parse_folder_payload(browser.post_json(seed,root));requests+=1
        except Exception:
            continue
        for year in _numeric_children(years,r'20\d{2}'):
            ypath=_child_path(root,year)
            try:
                months,_=parse_folder_payload(browser.post_json(seed,ypath));requests+=1
            except Exception:
                continue
            for month in _numeric_children(months,r'(?:0?[1-9]|1[0-2])'):
                m=int(month);mpath=_child_path(ypath,f'{m:02d}')
                try:
                    ds,_=parse_folder_payload(browser.post_json(seed,mpath));requests+=1
                except Exception:
                    continue
                for day in _numeric_children(ds,r'(?:0?[1-9]|[12]\d|3[01])'):
                    try:d=date(int(year),m,int(day))
                    except ValueError:continue
                    by_day[d.isoformat()].add(root)
                if pause:time.sleep(pause)
    return {k:sorted(v) for k,v in by_day.items()},requests


def sync_all(*,port=9222,match='Supervision',target_id='',pause=.05,resume=True):
    """Synchronize every historical day exposed by Hermes without audio."""
    state=_load_sync_state() if resume else {'completed_days':set(),'roots':set(),'version':SYNC_STATE_VERSION}
    if int(state.get('version') or 0)!=SYNC_STATE_VERSION:
        state={'completed_days':set(),'roots':set(),'version':SYNC_STATE_VERSION}
    completed=set(state.get('completed_days') or [])
    total_indices=0;total_wav=0;total_requests=0;processed=0;skipped=0
    roots=[];roots_with_wav=set();agent_folders=0
    with BrowserSession(port,match,target_id) as browser:
        seed=browser.wait_seed()
        roots=browser.discover_recording_roots(seed,'')
        roots=sorted(set(roots),key=lambda x:(len(x),x))
        if not roots:raise CaptureError('Aucune SDA/campagne RECORD détectée dans la fenêtre Enregistrements.')
        previous_roots=set(state.get('roots') or [])
        if resume and previous_roots and previous_roots!=set(roots):
            print('INFO - La liste SDA/campagnes a changé : reprise historique réinitialisée pour garantir la complétude.')
            completed.clear()
        state['roots']=set(roots)
        print('INFO - SDA/campagnes RECORD détectées :',len(roots))
        history,discovery_requests=discover_history_days(browser,seed,roots,pause=min(pause,.02))
        total_requests+=discovery_requests
        days=sorted(history)
        if not days:raise CaptureError('Aucune journée d’enregistrement détectée dans les SDA/campagnes RECORD.')
        print('INFO - Journées historiques détectées :',len(days),'de',days[0],'à',days[-1])
        recent_cutoff=(date.today()-timedelta(days=2)).isoformat()
        for pos,day_text in enumerate(days,1):
            if resume and day_text in completed and day_text < recent_cutoff:
                skipped+=1;continue
            d=datetime.strptime(day_text,'%Y-%m-%d').date()
            day_rows=[];day_requests=0;day_agent_folders=0
            for root in history[day_text]:
                day_path=root+'\\'+d.strftime('%Y\\%m\\%d')
                rows,stats=collect_day(browser,seed,day_path,agent_ids=[],pause=pause,probe_known_agents=False)
                day_rows.extend(rows);day_requests+=int(stats.get('requests',0));day_agent_folders+=int(stats.get('day_folders',0))
                if rows:roots_with_wav.add(root)
            day_rows=_dedupe_recordings(day_rows)
            _,wav_count=_aggregate_sizes(day_rows);stored=store(day_rows)
            total_indices+=stored;total_wav+=wav_count;total_requests+=day_requests;agent_folders+=day_agent_folders;processed+=1
            completed.add(day_text);state['completed_days']=completed;_save_sync_state(state)
            print(f'INFO - [{pos}/{len(days)}] {day_text}: racines {len(history[day_text])}, agents {day_agent_folders}, WAV {wav_count}, Indices {stored}')
    return dict(days_detected=len(days),days_processed=processed,days_skipped=skipped,
                requests=total_requests,roots_detected=len(roots),roots_with_wav=len(roots_with_wav),
                agent_folders_scanned=agent_folders,wav_files=total_wav,stored=total_indices)

def date_span(start,end):
    a=datetime.strptime(start,'%Y-%m-%d').date();b=datetime.strptime(end,'%Y-%m-%d').date()
    if b<a:raise ValueError('La date de fin précède la date de début.')
    if (b-a).days+1>MAX_DAYS:raise ValueError(f'Plage limitée à {MAX_DAYS} jours par synchronisation.')
    cur=a
    while cur<=b:
        yield cur;cur+=timedelta(days=1)


def sync(start,end,*,port=9222,match='Supervision',target_id='',pause=.05):
    rows=[];days=0
    totals={'requests':0,'folders_returned':0,'folders_with_wav':0,
            'agents_probed':0,'agents_with_wav':0,'probe_errors':0,
            'anchor_folders':0,'anchor_files':0,'day_folders':0}
    agent_ids=known_recording_agents()
    span=list(date_span(start,end))
    roots=[];roots_with_wav=set();agent_folders_scanned=0
    with BrowserSession(port,match,target_id) as browser:
        # RC9 follows the real Hermes hierarchy exactly:
        # SDA/campagne -> year -> month -> day -> agent/login -> WAV.
        # Opening Enregistrements is enough to obtain a RECORD session seed; no
        # manual navigation to a day folder is required anymore.
        seed=browser.wait_seed()
        roots=browser.discover_recording_roots(seed,'')
        roots=sorted(set(roots),key=lambda x:(len(x),x))
        if not roots:
            raise CaptureError('Aucune SDA/campagne RECORD détectée dans la fenêtre Enregistrements.')
        print('INFO - SDA/campagnes RECORD détectées :',len(roots))
        for d in span:
            for root in roots:
                day_path=root+'\\'+d.strftime('%Y\\%m\\%d')
                try:
                    day_rows,day_stats=collect_day(
                        browser,seed,day_path,agent_ids=agent_ids,pause=pause,
                        initial_payload=None,probe_known_agents=False)
                except (CaptureError, ValueError):
                    # Une SDA/campagne peut légitimement ne rien avoir pour la
                    # journée demandée. Les autres racines continuent.
                    continue
                if day_rows:roots_with_wav.add(root)
                rows.extend(day_rows)
                agent_folders_scanned+=int(day_stats.get('day_folders',0))
                for key in totals:
                    totals[key]+=int(day_stats.get(key,0))
            days+=1
    rows=_dedupe_recordings(rows)
    _,wav_count=_aggregate_sizes(rows)
    stored=store(rows)
    return dict(days=days,requests=totals['requests'],files=wav_count,indices=stored,stored=stored,rows=rows,
                known_agents=len(agent_ids),folders_returned=totals['folders_returned'],
                folders_with_wav=totals['folders_with_wav'],agents_probed=totals['agents_probed'],
                agents_with_wav=totals['agents_with_wav'],probe_errors=totals['probe_errors'],
                anchor_folders=0,anchor_files=0,
                roots_detected=len(roots),roots_with_wav=len(roots_with_wav),
                agent_folders_scanned=agent_folders_scanned)



def import_har(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    rows=[]
    for entry in ((data.get('log') or {}).get('entries') or []):
        url=str(((entry.get('request') or {}).get('url')) or '')
        if 'act=folder_info' not in url or 'basePath=RECORD' not in url:
            continue
        text=str((((entry.get('response') or {}).get('content') or {}).get('text')) or '')
        if not text:
            continue
        try:
            _,files=parse_folder_payload(text)
        except Exception:
            continue
        rows.extend(files)
    rows=_dedupe_recordings(rows)
    _,wav_count=_aggregate_sizes(rows)
    stored=store(rows,source='har_folder_info')
    return dict(files=wav_count,indices=stored,stored=stored,rows=rows)

def main(argv=None):
    ap=argparse.ArgumentParser(description='Synchronise uniquement les tailles WAV Hermes, sans télécharger les audios.')
    today=date.today().isoformat()
    ap.add_argument('--from',dest='date_from',default=today)
    ap.add_argument('--to',dest='date_to',default=today)
    ap.add_argument('--port',type=int,default=9222)
    ap.add_argument('--match',default='Supervision')
    ap.add_argument('--har',default='',help='Importe les FileList folder_info d un HAR au lieu du navigateur')
    ap.add_argument('--all',action='store_true',help='Synchronise tout l historique Hermes disponible')
    ap.add_argument('--no-resume',action='store_true',help='En mode --all, rescane aussi les journées déjà terminées')
    args=ap.parse_args(argv)
    try:
        if args.har:
            result=import_har(args.har)
            print('OK - fichiers WAV HAR:',result['files'],'stockés:',result['stored'])
            return 0
        if args.all:
            result=sync_all(port=args.port,match=args.match,resume=not args.no_resume)
            print('OK - historique: journées détectées:',result['days_detected'],'traitées:',result['days_processed'],
                  'déjà faites:',result['days_skipped'],'requêtes:',result['requests'],
                  'SDA/campagnes RECORD:',result['roots_detected'],'racines avec WAV:',result['roots_with_wav'],
                  'dossiers agents parcourus:',result['agent_folders_scanned'],'WAV lus:',result['wav_files'],
                  'Indices stockés:',result['stored'])
            return 0
        result=sync(args.date_from,args.date_to,port=args.port,match=args.match)
    except Exception as exc:
        print('ECHEC -',str(exc));return 2
    print('OK - jours:',result['days'],'requêtes:',result['requests'],
          'SDA/campagnes RECORD:',result.get('roots_detected',0),
          'racines avec WAV:',result.get('roots_with_wav',0),
          'dossiers agents parcourus:',result.get('agent_folders_scanned',0),
          'WAV lus:',result['files'],'Indices stockés:',result['stored'])
    return 0

if __name__=='__main__':
    raise SystemExit(main())
