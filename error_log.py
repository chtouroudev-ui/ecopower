"""Bounded, privacy-preserving diagnostics independent of SQLite transactions.

No exception messages, source lines, locals, request bodies or full paths are
recorded. Only constant operation names, exception types and stack locations.
Each capture process has its own rotating file to avoid cross-process rotation.
"""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
import threading
import time
import traceback
from collections import OrderedDict

LOG_DIR = Path(__file__).resolve().parent / 'logs'
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 3
RATE_SECONDS = 60.0
_lock = threading.RLock()
_handlers = {}
_recent = OrderedDict()
_last_fallback = None


def _safe(value):
    return re.sub(r'[^A-Za-z0-9_.<>-]', '_', value)[:160]


def _component(operation):
    if operation.startswith('capture.Capture_NELYIO.'):
        return 'nelyio_capture_errors'
    if operation.startswith('capture.relay_nelyio.'):
        return 'nelyio_relay_errors'
    return 'nelyio_errors'


def log_unexpected_error(operation):
    """Call inside except. Return True if written; never interrupt the caller."""
    global _last_fallback
    try:
        exc_type, exc, tb = sys.exc_info()
        operation = _safe(operation)
        error_type = _safe(exc_type.__name__) if exc_type else 'UnknownError'
        now = time.monotonic()
        key = (operation, error_type)
        with _lock:
            old = _recent.get(key)
            if old and now - old[0] < RATE_SECONDS:
                _recent[key] = (old[0], old[1] + 1)
                _recent.move_to_end(key)
                return False
            component = _component(operation)
            handler = _handlers.get(component)
            if handler is None:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(
                    LOG_DIR / (component + '.log'), maxBytes=MAX_BYTES,
                    backupCount=BACKUP_COUNT, encoding='utf-8', delay=True)
                # Logging's default error handler can print record contents.
                # Raise into our controlled, constant-message fallback instead.
                def fail(record):
                    raise OSError('Diagnostic log unavailable')
                handler.handleError = fail
                handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
                _handlers[component] = handler
            frames = [{'file': _safe(Path(f.filename).name), 'line': f.lineno,
                       'function': _safe(f.name)} for f in traceback.extract_tb(tb)[-20:]]
            message = json.dumps({'operation': operation, 'exception': error_type,
                                  'stack': frames, 'suppressed': old[1] if old else 0},
                                 ensure_ascii=True)
            record = logging.LogRecord(component, logging.ERROR, '', 0, message, (), None)
            handler.handle(record)
            _recent[key] = (now, 0)
            _recent.move_to_end(key)
            while len(_recent) > 512:
                _recent.popitem(last=False)
            return True
    except Exception:
        # Keep the application's original fallback/rollback even if disk is full.
        try:
            with _lock:
                now = time.monotonic()
                if _last_fallback is None or now - _last_fallback >= RATE_SECONDS:
                    _last_fallback = now
                    sys.stderr.write('Nelyio: journal technique indisponible.\n')
        except Exception:
            pass
        return False


def close_error_logs():
    """Release file handles (tests and controlled shutdown)."""
    with _lock:
        for handler in _handlers.values():
            handler.close()
        _handlers.clear()
        _recent.clear()
