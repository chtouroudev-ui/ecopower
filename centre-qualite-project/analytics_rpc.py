"""Client for the loopback-only Analytics worker."""
from __future__ import annotations
import json
import os
import socket
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

PORT=int(os.environ.get('NELYIO_ANALYTICS_PORT','9052'))
BASE_URL=f'http://127.0.0.1:{PORT}'
try:
    DEFAULT_TIMEOUT=max(10.0,min(180.0,float(os.environ.get('NELYIO_ANALYTICS_TIMEOUT','90'))))
except ValueError:
    DEFAULT_TIMEOUT=90.0

def _body_error(exc):
    try:
        raw=exc.read(4096)
        if not raw:return ''
        obj=json.loads(raw.decode('utf-8','replace'))
        if isinstance(obj,dict) and obj.get('error'):
            return str(obj['error'])[:300]
    except Exception:
        pass
    return ''

def _post(path, value, timeout=None):
    timeout=DEFAULT_TIMEOUT if timeout is None else float(timeout)
    payload=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    request=Request(BASE_URL+path,data=payload,headers={'Content-Type':'application/json','Content-Length':str(len(payload))},method='POST')
    last_busy=None
    for attempt in range(3):
        attempt_started=time.perf_counter()
        try:
            with urlopen(request,timeout=timeout) as response:
                if response.status!=200:
                    raise RuntimeError(f'Analytics HTTP {response.status}.')
                result=json.loads(response.read())
                if not isinstance(result,dict):raise RuntimeError('Réponse Analytics invalide.')
                try:
                    import perf_trace; perf_trace.add_worker(time.perf_counter()-attempt_started)
                except Exception:
                    pass
                return result
        except HTTPError as exc:
            detail=_body_error(exc)
            if exc.code==503:
                last_busy=exc
                if attempt<2:
                    time.sleep(0.6*(attempt+1))
                    continue
                raise RuntimeError('Analytics occupé : trop de calculs simultanés. Réessayez dans quelques secondes.') from exc
            if exc.code==400:
                raise RuntimeError('Requête Analytics refusée'+(f' : {detail}' if detail else '.')) from exc
            if exc.code==500:
                raise RuntimeError('Erreur interne Analytics'+(f' : {detail}' if detail else '. Consultez logs\\nelyio_errors.log.')) from exc
            raise RuntimeError(f'Analytics HTTP {exc.code}'+(f' : {detail}' if detail else '.')) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f'Analytics timeout après {int(timeout)} s. La requête PostgreSQL est trop lente.') from exc
        except (URLError,OSError) as exc:
            raise RuntimeError('Analytics réellement indisponible sur 127.0.0.1:9052.') from exc
        except (ValueError,json.JSONDecodeError) as exc:
            raise RuntimeError('Réponse Analytics invalide.') from exc
    raise RuntimeError('Analytics occupé.') from last_busy

def analytics_view_remote(qs, timeout=None):
    return _post('/analyze',dict(qs or {}),timeout)

def delegated_view_remote(kind, qs, timeout=None):
    if kind not in {'quality_agents','quality_distributions','quality_overview',
                    'support_view','diagnostic_incidents','supervision_view','details_view','calls_view','suspicious_calls','quality_pilotage','quality_action_compare','live_campaigns_history','live_campaign_drilldown_history'}:
        raise ValueError('Type de requête déléguée invalide.')
    return _post('/query',{'kind':kind,'query':dict(qs or {})},timeout)
