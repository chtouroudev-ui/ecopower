"""Read-only CDP transport for a LOCAL, explicitly selected supervision tab.

No page JavaScript is executed; no cookies, credentials or request bodies are
read. Only the configured response path on the selected page's origin is read.
"""
from __future__ import annotations

import base64
import inspect
import json
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, ProxyHandler, HTTPRedirectHandler, Request

from collection_parser import MAX_BODY_BYTES

# Keep the accepted payload bounded by MAX_BODY_BYTES, but give DevTools enough
# retention headroom to avoid evicting changes.ashx before getResponseBody.
# These values match the previously stabilized Nelyio collector.
NETWORK_MAX_RESOURCE_BUFFER = 100 * 1024 * 1024
NETWORK_MAX_TOTAL_BUFFER = 200 * 1024 * 1024
NETWORK_MAX_QUEUE = 512


class CaptureError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CaptureError('Redirection du port de diagnostic refusee.')


def local_targets(port, match):
    # No system proxy and no redirects, even if the environment has a proxy.
    opener = build_opener(ProxyHandler({}), NoRedirect())
    req = Request(f'http://127.0.0.1:{int(port)}/json/list', headers={'Accept': 'application/json'})
    try:
        with opener.open(req, timeout=3) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024: raise CaptureError('Liste des onglets trop volumineuse.')
        items = json.loads(raw)
    except CaptureError:
        raise
    except Exception as exc:
        raise CaptureError("En attente d'Edge de collecte : port de diagnostic local inaccessible. Ouvrez Edge avec le lanceur de collecte.") from exc
    if not isinstance(items, list): raise CaptureError('Le port indique ne repond pas comme un navigateur CDP.')
    result = []
    for item in items:
        if not isinstance(item, dict) or item.get('type') != 'page': continue
        page = urlsplit(str(item.get('url', '')))
        if page.scheme not in ('http', 'https') or not page.hostname or page.username or page.password: continue
        safe_url = urlunsplit((page.scheme, page.netloc, page.path, '', ''))
        if match.casefold() not in safe_url.casefold(): continue
        ws = urlsplit(str(item.get('webSocketDebuggerUrl', '')))
        if ws.scheme != 'ws' or ws.hostname not in ('127.0.0.1', 'localhost', '::1') or ws.port != int(port) or ws.username or ws.password: continue
        result.append(dict(id=str(item.get('id', ''))[:160], url=safe_url,
            # Normalize loopback and strip query data; CDP paths carry target IDs only.
            websocket=urlunsplit(('ws', f'127.0.0.1:{int(port)}', ws.path, '', ''))))
    return result


def probe(settings):
    try:
        targets = local_targets(settings['debug_port'], settings['page_match'])
    except CaptureError as exc:
        return {'ok': False, 'state': 'waiting_browser', 'auto_select': False, 'targets': [],
                'message': str(exc)}
    public = [{k: t[k] for k in ('id', 'url')} for t in targets]
    if len(targets) == 1:
        return {'ok': True, 'state': 'target_detected', 'auto_select': True, 'targets': public,
                'message': 'Onglet de supervision detecte automatiquement.'}
    if not targets:
        return {'ok': False, 'state': 'waiting_browser', 'auto_select': False, 'targets': public,
                'message': "En attente de l'onglet de supervision : aucun onglet ne correspond au filtre."}
    return {'ok': False, 'state': 'waiting_browser', 'auto_select': False, 'targets': public,
            'message': "Plusieurs onglets de supervision correspondent au filtre. Fermez les doublons ou utilisez une selection manuelle de secours."}


def _choose_target(targets, chosen=''):
    """Choose one safe target without pinning a recreated tab forever.

    An explicit target remains preferred while it exists. If that target was
    closed and exactly one matching page is now available, reconnect to that
    unique page automatically. Zero or ambiguous matches remain retryable
    waiting states handled by Manager._run().
    """
    chosen = str(chosen or '').strip()
    if chosen:
        exact = [t for t in targets if t.get('id') == chosen]
        if len(exact) == 1:
            return exact[0]
    if len(targets) == 1:
        return targets[0]
    if not targets:
        raise CaptureError("En attente de l'onglet de supervision : aucun onglet ne correspond au filtre.")
    raise CaptureError("Plusieurs onglets de supervision correspondent au filtre. Fermez les doublons ou utilisez une selection manuelle de secours.")


class Reader:
    """One CDP connection; reconnecting creates a new partial observation segment."""
    def __init__(self, settings):
        self.settings = settings
        self.socket = None
        self.next_id = 0
        self.requests = {}
        self.commands = {}
        self.origin = ''

    def __enter__(self):
        try:
            from websockets.sync.client import connect
            import websockets
            if int(websockets.__version__.split('.')[0]) < 14:
                raise ImportError('websockets >= 14 requis')
        except ImportError as exc:
            raise CaptureError('Module websockets absent. Executez INSTALL_CAPTURE_DEPENDENCIES.bat puis relancez Nelyio.') from exc
        targets = local_targets(self.settings['debug_port'], self.settings['page_match'])
        target = _choose_target(targets, self.settings.get('target_id', ''))
        page = urlsplit(target['url']); self.origin = (page.scheme.lower(), page.netloc.lower())
        options = dict(open_timeout=3, close_timeout=1, max_size=MAX_BODY_BYTES * 2,
                       compression=None, max_queue=NETWORK_MAX_QUEUE)
        if 'proxy' in inspect.signature(connect).parameters: options['proxy'] = None
        try:
            self.socket = connect(target['websocket'], **options)
            self._send('Network.enable', {'maxResourceBufferSize': NETWORK_MAX_RESOURCE_BUFFER,
                                          'maxTotalBufferSize': NETWORK_MAX_TOTAL_BUFFER}, 'enable')
        except Exception as exc:
            self.close()
            raise CaptureError('Connexion au navigateur refusee ou interrompue. Verifiez le profil Edge de collecte.') from exc
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        if self.socket:
            try: self.socket.close()
            except Exception: pass
            self.socket = None

    def _send(self, method, params, tag):
        self.next_id += 1
        self.commands[self.next_id] = (tag, time.time())
        self.socket.send(json.dumps(dict(id=self.next_id, method=method, params=params)))

    def matches_response(self, response):
        u = urlsplit(str(response.get('url', '')))
        return ((u.scheme.lower(), u.netloc.lower()) == self.origin and
                u.path.rsplit('/', 1)[-1].casefold() == self.settings['response_path'].casefold() and
                200 <= float(response.get('status', 0)) < 300)

    def poll(self, timeout=0.5):
        """Return (request_id, received_at, body), or None. Never blocks the stop."""
        try:
            raw = self.socket.recv(timeout=timeout)
        except TimeoutError:
            if any(time.time()-v[1] > 30 for v in self.commands.values()):
                raise CaptureError('Delai de lecture du navigateur depasse. Reconnexion en cours.')
            return None
        except Exception as exc:
            raise CaptureError('Connexion navigateur interrompue. Reconnexion en cours.') from exc
        try: message = json.loads(raw)
        except (ValueError, TypeError): raise CaptureError('Message CDP invalide.')
        now = time.time()
        self.requests = {k:v for k,v in self.requests.items() if now-v < 60}
        if len(self.requests) > 500 or len(self.commands) > 500:
            raise CaptureError('Tampon de collecte sature. Reconnexion sans inventer de continuite.')
        if 'id' in message:
            command = self.commands.pop(message['id'], None)
            if not command: return None
            tag, _ = command
            if 'error' in message:
                raise CaptureError('Le navigateur ne fournit plus les reponses attendues. Reconnexion du collecteur.')
            if tag == 'enable': return None
            result = message.get('result') or {}; body = result.get('body', '')
            if result.get('base64Encoded'):
                try: body = base64.b64decode(body, validate=True).decode('utf-8')
                except (ValueError, UnicodeError): raise CaptureError('Reponse live non lisible en UTF-8.')
            if not isinstance(body, str) or len(body.encode('utf-8')) > MAX_BODY_BYTES:
                raise CaptureError('Reponse live trop volumineuse (limite 4 Mo).')
            request_id, stamp = tag
            return request_id, stamp, body
        method, p = message.get('method'), message.get('params') or {}
        if method == 'Network.responseReceived' and self.matches_response(p.get('response') or {}):
            self.requests[str(p['requestId'])] = now
        elif method == 'Network.loadingFinished':
            rid = str(p.get('requestId', ''))
            if rid in self.requests:
                self.requests.pop(rid, None)
                self._send('Network.getResponseBody', {'requestId': rid}, (rid, now))
        elif method == 'Network.loadingFailed':
            if self.requests.pop(str(p.get('requestId', '')), None) is not None:
                raise CaptureError('Requete de supervision echouee. La coupure de collecte est conservee.')
        return None
