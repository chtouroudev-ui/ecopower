"""Loopback-only Analytics worker for Nelyio V59 production hardened.

The authenticated Web/API process validates access, then forwards only the
normalized query parameters here. Heavy analytics runs outside the Web Python
process, with a bounded in-memory response cache for repeated filters.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import signal
import threading
import time

import supervision  # schema/facade initialization for this worker
from analytics import analytics_view
from error_log import log_unexpected_error
import service_state
from service_control import clear_stop, stop_requested

HOST='127.0.0.1'
PORT=int(os.environ.get('NELYIO_ANALYTICS_PORT','9052'))
try:
    MAX_CONCURRENCY=max(1,min(16,int(os.environ.get('NELYIO_ANALYTICS_MAX_CONCURRENCY','5'))))
except ValueError:
    MAX_CONCURRENCY=5
MAX_REQUEST=256*1024
try:
    CACHE_MAX_BYTES=max(16, min(2048, int(os.environ.get('NELYIO_ANALYTICS_CACHE_MB','256'))))*1024*1024
except ValueError:
    CACHE_MAX_BYTES=256*1024*1024
CACHE_TTL=30.0
try:
    SLOW_SECONDS=max(0.25,float(os.environ.get('NELYIO_ANALYTICS_SLOW_SECONDS','2.0')))
except ValueError:
    SLOW_SECONDS=2.0
try:
    FRESH_SECONDS=max(5, min(60, int(os.environ.get('NELYIO_ANALYTICS_FRESH_SECONDS','15'))))
except ValueError:
    FRESH_SECONDS=15
_CACHE=OrderedDict()
_CACHE_BYTES=0
_CACHE_LOCK=threading.RLock()
_STOP=threading.Event()
_FLIGHTS=[threading.Lock() for _ in range(32)]


def _cache_get(key):
    global _CACHE_BYTES
    now=time.monotonic()
    with _CACHE_LOCK:
        for old,(until,data,size) in list(_CACHE.items()):
            if until<=now:
                _CACHE.pop(old,None);_CACHE_BYTES-=size
        item=_CACHE.get(key)
        if item is None:return None
        _CACHE.move_to_end(key)
        return item[1]


def _cache_put(key,data,ttl=CACHE_TTL):
    global _CACHE_BYTES
    size=len(data)+len(key)
    if size>CACHE_MAX_BYTES//2:return
    with _CACHE_LOCK:
        old=_CACHE.pop(key,None)
        if old:_CACHE_BYTES-=old[2]
        while _CACHE and (_CACHE_BYTES+size>CACHE_MAX_BYTES or len(_CACHE)>=64):
            _,item=_CACHE.popitem(last=False);_CACHE_BYTES-=item[2]
        _CACHE[key]=(time.monotonic()+float(ttl),data,size);_CACHE_BYTES+=size


def _log_slow(kind, elapsed, key):
    if float(elapsed) < SLOW_SECONDS:
        return
    try:
        root=os.path.dirname(os.path.abspath(__file__))
        folder=os.path.join(root,'logs');os.makedirs(folder,exist_ok=True)
        stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
        line=f"{stamp} kind={kind} elapsed={float(elapsed):.3f}s key={str(key)[:12]}\n"
        with open(os.path.join(folder,'analytics_slow.log'),'a',encoding='utf-8') as stream:
            stream.write(line)
    except OSError:
        pass


def _revision(kind=''):
    """Cheap data-driven cache revision.

    Never use a wall-clock bucket as a cache revision: a request slower than the
    bucket can never be cached. PostgreSQL revisions are based on monotonic
    source markers; SQLite uses file revisions. Configuration files are always
    included so policy/group changes invalidate immediately.
    """
    from pathlib import Path
    import db_compat
    import supervision_context as ctx
    from details_store import _sqlite_storage_revision
    root=Path(__file__).resolve().parent
    quality_kind=kind in {'quality_agents','quality_distributions','quality_overview','quality_pilotage','quality_action_compare','live_campaigns_history','live_campaign_drilldown_history'}
    values=[]
    if db_compat.postgres_enabled():
        try:
            from supervision_db import connect
            with connect() as c:
                if quality_kind:
                    a=c.execute('SELECT COALESCE(MAX(import_id),0) FROM coverage').fetchone()[0]
                    b=c.execute('SELECT COALESCE(MAX(import_id),0) FROM call_coverage').fetchone()[0]
                    values.extend([('coverage',a),('calls',b)])
                else:
                    probes=(
                        ('imports','SELECT COALESCE(MAX(id),0) FROM imports'),
                        ('coverage','SELECT COALESCE(MAX(import_id),0) FROM coverage'),
                        ('calls','SELECT COALESCE(MAX(import_id),0) FROM call_coverage'),
                        ('live','SELECT COALESCE(MAX(ingest_seq),0) FROM live_events'),
                        ('signals','SELECT COALESCE(MAX(ingest_seq),0) FROM technical_signals'),
                        ('notes','SELECT COALESCE(MAX(id),0) FROM notes'),
                    )
                    for label,sql in probes:
                        try: values.append((label,c.execute(sql).fetchone()[0]))
                        except Exception: values.append((label,0))
        except Exception:
            # Degraded startup only. This fallback is deliberately much wider
            # than the old 15 s bucket so long requests can still become warm.
            values.append(('fallback',int(time.time()//120)))
    else:
        for path in (ctx.db_path(),ctx.admin_db_path()):
            values.append(_sqlite_storage_revision(path))
    for path in sorted((root/'data').glob('*.json')):
        try:
            st=path.stat();values.append((path.name,st.st_mtime_ns,st.st_size))
        except OSError:pass
    for path in (root/'data'/'quality_scope.revision',):
        try:
            st=path.stat();values.append((path.name,st.st_mtime_ns,st.st_size))
        except OSError:pass
    return values


def _run_query(kind, query):
    """Execute one authenticated-Web delegated read in this worker process."""
    if kind == 'analytics':
        return analytics_view(query), 30.0
    if kind == 'quality_agents':
        from quality_agents import view
        return view(query), 300.0
    if kind == 'quality_distributions':
        from quality_distributions import view
        return view(query), 300.0
    if kind == 'quality_overview':
        from quality_metrics import overview
        return overview(query), 300.0
    if kind == 'quality_pilotage':
        from pilotage_quality import view
        return view(query), 120.0
    if kind == 'quality_action_compare':
        from pilotage_quality import compare_action
        return compare_action(query), 15.0
    if kind == 'live_campaigns_history':
        from live_campaigns import historical_view
        return historical_view(query), 60.0
    if kind == 'live_campaign_drilldown_history':
        from live_campaigns import historical_drilldown_view
        campaign_id=str((query or {}).get('_campaign_id',[''])[0] if isinstance((query or {}).get('_campaign_id'),list) else (query or {}).get('_campaign_id','')).strip()
        return historical_drilldown_view(query,campaign_id), 60.0
    if kind == 'support_view':
        from support_views import support_view
        return support_view(query), 120.0
    if kind == 'diagnostic_incidents':
        from support_views import diagnostic_incidents_view
        return diagnostic_incidents_view(query), 60.0
    if kind == 'supervision_view':
        from support_views import view
        return view(query), 60.0
    if kind == 'details_view':
        import details_store
        import supervision_context as ctx
        from supervision_db import config
        from support_filters import TECH_LABELS
        cfg=config()
        return details_store.details_view(query,ctx.db_path(),ctx.admin_db_path(),cfg['display_offset'],TECH_LABELS,cfg), 60.0
    if kind == 'calls_view':
        from calls import calls_view
        return calls_view(query), 120.0
    if kind == 'suspicious_calls':
        from suspicious_calls import view
        return view(query), 120.0
    raise ValueError('unknown analytics query kind')


def _revision_for(kind):
    fn=_revision
    code=getattr(fn,'__code__',None)
    if code is not None and int(getattr(code,'co_argcount',1) or 0)==0:
        return fn()
    return fn(kind)


def _analyze(kind, query=None):
    try:
        import perf_trace
        perf_token = perf_trace.begin('analytics', service='analytics', endpoint=str(kind))
    except Exception:
        perf_trace = None; perf_token = None
    finished=False
    try:
        # Backward-compatible internal call form used by regression tests and any
        # local tooling from V58: _analyze(query) means the Analytics view.
        if query is None:
            query=kind;kind='analytics'
        before=_revision_for(kind)
        raw=json.dumps([kind,query,before],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
        key=hashlib.sha256(raw).hexdigest()
        with _FLIGHTS[int(key[:8],16)%len(_FLIGHTS)]:
            hit=_cache_get(key)
            if hit is not None:
                if perf_trace is not None:
                    perf_trace.set_cache_hit(True);perf_trace.finish(extra={'query_kind':kind});finished=True
                return hit,True
            started=time.perf_counter()
            value,ttl=_run_query(kind,query)
            elapsed=time.perf_counter()-started
            if perf_trace is not None:
                perf_trace.add_compute(elapsed)
            _log_slow(kind,elapsed,key)
            json_started=time.perf_counter()
            payload=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            if perf_trace is not None:
                perf_trace.add_json(time.perf_counter()-json_started)
            if before==_revision_for(kind):_cache_put(key,payload,ttl)
            if perf_trace is not None:
                perf_trace.set_cache_hit(False);perf_trace.finish(extra={'query_kind':kind,'payload_bytes':len(payload)});finished=True
            return payload,False
    except Exception:
        if perf_trace is not None and not finished:
            try: perf_trace.finish(extra={'query_kind':str(kind),'error':True})
            except Exception: pass
        raise
    finally:
        if perf_trace is not None:
            perf_trace.reset(perf_token)


class AnalyticsHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=64
    def __init__(self,*args,**kwargs):
        self._slots=threading.BoundedSemaphore(MAX_CONCURRENCY)
        super().__init__(*args,**kwargs)
    def process_request(self,request,client_address):
        if not self._slots.acquire(blocking=False):
            try:
                request.settimeout(2)
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nRetry-After: 2\r\nContent-Length: 0\r\n\r\n')
            except OSError:pass
            finally:self.shutdown_request(request)
            return
        try:super().process_request(request,client_address)
        except BaseException:
            self._slots.release();raise
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self._slots.release()


class Handler(BaseHTTPRequestHandler):
    server_version='NelyioAnalytics/'+service_state.BUILD;sys_version=''
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.settimeout(30)
    def log_message(self,*_):pass
    def _send(self,status,data,ctype='application/json; charset=utf-8',extra=None):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store')
        if extra:
            for k,v in extra.items():self.send_header(k,v)
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path!='/healthz':return self._send(404,b'{}')
        data=json.dumps({'ok':True,'service':'nelyio-analytics','build':service_state.BUILD,'cache_bytes':_CACHE_BYTES,'max_concurrency':MAX_CONCURRENCY}).encode()
        self._send(200,data)
    def do_POST(self):
        if self.path not in ('/analyze','/query'):return self._send(404,b'{}')
        try:n=int(self.headers.get('Content-Length','0'))
        except ValueError:return self._send(400,b'{"error":"invalid length"}')
        if not 0<n<=MAX_REQUEST:return self._send(413,b'{"error":"request too large"}')
        try:
            body=json.loads(self.rfile.read(n))
            if self.path == '/analyze':
                kind='analytics';query=body
            else:
                if not isinstance(body,dict):raise ValueError('request object required')
                kind=str(body.get('kind') or '')
                query=body.get('query')
            if not isinstance(query,dict):raise ValueError('query object required')
            # Keep the internal API narrow: parse_qs-style list/scalar values only.
            for k,v in query.items():
                if not isinstance(k,str) or len(k)>100 or not isinstance(v,(str,list,tuple)):
                    raise ValueError('invalid query')
                if isinstance(v,(list,tuple)) and (len(v)>100 or any(not isinstance(x,str) or len(x)>500 for x in v)):
                    raise ValueError('invalid query')
            if kind not in {'analytics','quality_agents','quality_distributions','quality_overview',
                            'support_view','diagnostic_incidents','supervision_view','details_view','calls_view','suspicious_calls','quality_pilotage','quality_action_compare'}:
                raise ValueError('invalid query kind')
            data,hit=_analyze(kind,query)
            self._send(200,data,extra={'X-Nelyio-Cache':'HIT' if hit else 'MISS'})
        except (ValueError,TypeError,json.JSONDecodeError) as exc:
            self._send(400,json.dumps({'error':str(exc)},ensure_ascii=False).encode('utf-8'))
        except Exception:
            log_unexpected_error('analytics_service.request')
            self._send(500,b'{"error":"analytics worker error"}')


def _heartbeat(started):
    while not _STOP.wait(3):
        if stop_requested('analytics_service'):
            _STOP.set(); break
        with _CACHE_LOCK:
            detail={'port':PORT,'cache_entries':len(_CACHE),'cache_bytes':_CACHE_BYTES,'cache_limit_bytes':CACHE_MAX_BYTES,'max_concurrency':MAX_CONCURRENCY}
        try:service_state.beat('analytics',detail=detail,started_at=started)
        except Exception:pass


def run():
    started=time.time();service_state.beat('analytics',started_at=started,detail={'port':PORT,'cache_limit_bytes':CACHE_MAX_BYTES,'max_concurrency':MAX_CONCURRENCY})
    hb=threading.Thread(target=_heartbeat,args=(started,),name='nelyio-analytics-heartbeat',daemon=True);hb.start()
    server=AnalyticsHTTPServer((HOST,PORT),Handler);server.timeout=1
    try:
        while not _STOP.is_set() and not stop_requested('analytics_service'):server.handle_request()
    finally:
        server.server_close();_STOP.set();service_state.stop('analytics',{'port':PORT})


def main():
    clear_stop('analytics_service')
    def stop(*_):_STOP.set()
    for name in ('SIGINT','SIGTERM'):
        if hasattr(signal,name):signal.signal(getattr(signal,name),stop)
    run()

if __name__=='__main__':main()
