"""Production transport adapter; business routes/calculations stay in their modules.

Deploy behind the bundled local Caddy reverse proxy, never directly on the WAN.
This adapter is intentionally separate from the frozen Phase 4 routing reference.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import socket
import time
import db_compat as sqlite3
import threading
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import app_config as cfg
import http_handler as legacy
from error_log import log_unexpected_error



def _runtime_build():
    try:
        meta=json.loads((cfg.BASE / 'VERSION.json').read_text(encoding='utf-8-sig'))
        version=str(meta.get('version') or 'unknown')
        revision=str(meta.get('runtime_revision') or '').strip()
        return f'{version}+{revision}' if revision else version
    except Exception:
        return 'unknown'

BUILD = _runtime_build()

def _env_float(name, default, low, high):
    try:
        return max(low, min(high, float(os.environ.get(name, str(default)))))
    except (TypeError, ValueError):
        return float(default)

HTTP_SLOW_SECONDS = _env_float('NELYIO_HTTP_SLOW_SECONDS', 1.0, 0.1, 60.0)
_ASSET_LOCK = threading.Lock()
_ASSETS: OrderedDict = OrderedDict()
_DETAILS_ROUTES = frozenset(('/api/supervision/diagnostic-incidents', '/api/supervision/incident-evidence'))


_HEALTH_LOCK = threading.Lock()
_HEALTH_STATE = {}
_HEALTH_THREAD = None


def start_health_monitor(port):
    """Publish heartbeats outside request threads; startup probes never wait on I/O."""
    global _HEALTH_THREAD
    def refresh():
        import service_state
        while True:
            try:
                service_state.beat('web', detail={'port': port, 'mode': 'external-services'})
                state = service_state.public_status()
                value = dict(services_ok=state['all_healthy'],
                             services={r['service']: r['healthy'] for r in state['services']},
                             checked_at=time.monotonic())
            except Exception:
                value = dict(services_ok=False, services={}, checked_at=time.monotonic())
            with _HEALTH_LOCK:
                _HEALTH_STATE.clear()
                _HEALTH_STATE.update(value)
            time.sleep(3)
    with _HEALTH_LOCK:
        if _HEALTH_THREAD is None:
            _HEALTH_THREAD = threading.Thread(target=refresh, name='web-health', daemon=True)
            _HEALTH_THREAD.start()


def cached_service_health():
    with _HEALTH_LOCK:
        result = dict(_HEALTH_STATE)
    checked = result.pop('checked_at', 0)
    if time.monotonic() - checked > 12:
        return dict(services_ok=False, services={})
    return result


def _file_payload(path: Path):
    """Bounded cache; file replacement is detected before reuse."""
    stat = path.stat()
    key = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    with _ASSET_LOCK:
        hit = _ASSETS.get(key)
        if hit is not None:
            _ASSETS.move_to_end(key)
            return hit
    data = path.read_bytes()
    value = (data, hashlib.sha256(data).hexdigest())
    if len(data) <= 2 * 1024 * 1024:
        with _ASSET_LOCK:
            _ASSETS[key] = value
            while len(_ASSETS) > 32:
                _ASSETS.popitem(last=False)
    return value


class Handler(legacy.Handler):
    """Defensive HTTP boundary, without changing business service payloads."""

    # Caddy and modern browsers can reuse upstream/client connections instead
    # of paying a new TCP connection for every API/static request.
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, fmt, *args):
        # The base logger writes the complete request, including patient ANI
        # and search text in query strings. Keep method/path/status only.
        if args and isinstance(args[0], str) and ' ' in args[0]:
            words = args[0].split(' ')
            if len(words) >= 2:
                words[1] = words[1].split('?', 1)[0]
                args = (' '.join(words), *args[1:])
        super().log_message(fmt, *args)

    def send_response(self, code, message=None):
        self._last_status = int(code)
        return super().send_response(code, message)

    def _guard(self, fn):
        started = time.perf_counter()
        safe_path = urlparse(self.path).path[:160]
        try:
            import perf_trace
            perf_token = perf_trace.begin('http', service='web', endpoint=safe_path)
        except Exception:
            perf_trace = None; perf_token = None
        try:
            return fn()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
            self.close_connection = True
        except Exception:
            # No SQL, local path, patient value or traceback in the HTTP response.
            log_unexpected_error('http.request.' + safe_path)
            try:
                return self.send_json({'error': 'Erreur interne. Consultez le journal des erreurs Nelyio.'}, 500)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
                self.close_connection = True
        finally:
            elapsed = time.perf_counter() - started
            if perf_trace is not None:
                try:
                    perf_trace.finish(extra={'method': self.command, 'status': int(getattr(self, '_last_status', 0) or 0)})
                    perf_trace.reset(perf_token)
                except Exception:
                    pass
            if elapsed >= HTTP_SLOW_SECONDS:
                try:
                    log_dir = cfg.BASE / 'logs'
                    log_dir.mkdir(parents=True, exist_ok=True)
                    with (log_dir / 'http_slow.log').open('a', encoding='utf-8') as fh:
                        fh.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S') +
                                 f' {self.command} {safe_path} {elapsed:.3f}s\n')
                except Exception:
                    pass

    def do_GET(self):
        return self._guard(self._get)

    def _get(self):
        parsed = urlparse(self.path)
        if parsed.path == '/healthz':
            payload={'ok': True, 'service': 'nelyio-backend',
                     'port': int(getattr(self.server, 'server_port', 0) or 0),
                     'build': BUILD}
            from service_mode import external_services_enabled
            payload['architecture']='services' if external_services_enabled() else 'monolith'
            try:
                import db_compat
                payload['database']='postgresql' if db_compat.postgres_enabled() else 'sqlite'
            except Exception:
                payload['database']='unknown'
            if external_services_enabled():
                payload.update(cached_service_health())
            return self.send_json(payload)
        if parsed.path in _DETAILS_ROUTES:
            # These two routes belong to Details, not to Support. The legacy
            # catch-all required both rights, despite the navigation allowing
            # a Details-only reader. The service still enforces Details too.
            user = self.require_user()
            if not user or not self.require_access(user, 'details'):
                return
            return legacy.supervision.get_route(self, parsed.path, parse_qs(parsed.query), user)
        return super().do_GET()

    def do_POST(self):
        return self._guard(super().do_POST)

    def read_json(self):
        """All JSON routes accept objects, never scalar/array payloads."""
        try:
            if self.headers.get('Transfer-Encoding'):
                self.close_connection = True
                return None
            lengths = self.headers.get_all('Content-Length', []) if hasattr(self.headers, 'get_all') else []
            if len(lengths) > 1:
                self.close_connection = True
                return None
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 <= n <= cfg.MAX_JSON_BYTES:
                self.close_connection = True
                return None
            raw = self.rfile.read(n) if n else b'{}'
            if n and len(raw) != n:
                return None
            value = json.loads(raw)
            return value if isinstance(value, dict) else None
        except (ValueError, UnicodeError, TypeError):
            return None

    def session_user(self):
        token = self.cookie_token()
        if not token:
            return None
        th = hashlib.sha256(token.encode('utf-8')).hexdigest()
        with legacy.db_connect() as con:
            row = con.execute('''
                SELECT u.id,u.username,u.role,u.active,s.expires_at,s.csrf_token,s.last_seen_at
                FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?
            ''', (th,)).fetchone()
            if not row or not row['active']:
                return None
            now = datetime.now()
            try:
                expires = datetime.fromisoformat(row['expires_at'])
                seen = datetime.fromisoformat(row['last_seen_at'] or row['expires_at'])
                expired = expires <= now or seen + timedelta(minutes=cfg.SESSION_IDLE_MINUTES) <= now
            except (ValueError, TypeError):
                expired = True
            if expired:
                con.execute('DELETE FROM sessions WHERE token_hash=?', (th,))
                return None
            # Renew at most once per minute rather than one write for EVERY
            # concurrent API read. Rights and active status are never cached.
            if (now - seen).total_seconds() >= 60:
                cutoff = (now - timedelta(seconds=60)).strftime('%Y-%m-%d %H:%M:%S')
                con.execute('''UPDATE sessions SET last_seen_at=?
                    WHERE token_hash=? AND (last_seen_at IS NULL OR last_seen_at<=?)''',
                            (legacy.now_text(), th, cutoff))
            out = dict(row)
            if out.get('role') == 'user':
                out['role'] = 'technician'
            out.update(legacy.access_profile(con, out['id'], out['role']))
            return out

    def serve_file(self, path, ctype=None):
        path = Path(path)
        if not path.is_file():
            return self.send_json({'error': 'not found'}, 404)
        data, digest = _file_payload(path)
        if ctype is None:
            explicit = {'.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
                        '.html': 'text/html; charset=utf-8', '.json': 'application/json; charset=utf-8',
                        '.svg': 'image/svg+xml'}
            ctype = explicit.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        if ctype.startswith('text/') and 'charset' not in ctype:
            ctype += '; charset=utf-8'
        static = path.suffix.lower() in {'.js', '.css'} and urlparse(self.path).path.startswith('/static/')
        version = parse_qs(urlparse(self.path).query).get('v', [''])[0]
        fingerprinted = static and version.endswith('-' + digest[:16])
        cache = 'public, max-age=31536000, immutable' if fingerprinted else ('no-cache' if static else 'no-store')
        etag = '"' + digest + '"'
        not_modified = static and self.headers.get('If-None-Match') == etag
        self.send_response(304 if not_modified else 200)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', cache)
        if static:
            self.send_header('ETag', etag)
        if not not_modified:
            self.send_header('Content-Length', str(len(data)))
        for key, value in self.security_headers().items():
            self.send_header(key, value)
        self.end_headers()
        if not not_modified:
            self.wfile.write(data)


class ProductionHTTPServer(_ThreadingHTTPServer):
    """Bound simultaneous workers; reject overload instead of exhausting RAM."""
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, *args, **kwargs):
        try:
            limit = max(4, min(128, int(os.environ.get('NELYIO_HTTP_WORKERS', '32'))))
        except ValueError:
            limit = 32
        self._workers = threading.BoundedSemaphore(limit)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            try:
                request.settimeout(2)
                request.sendall(b'HTTP/1.0 503 Service Unavailable\r\nRetry-After: 2\r\n'
                                b'Content-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()
