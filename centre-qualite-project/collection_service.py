"""One-day collection controller, armed manually or automatically and stopped at day's end.

The collector runs in a daemon thread separate from the HTTP request handlers.
It resumes only an unfinished durable session for its original date.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import threading
import time
import uuid

import collection_store as store
from collection_parser import Decoder
from collection_cdp import Reader, CaptureError, probe
from nelyio_time import DISPLAY_TIMEZONE, display, france_offset_for_local_datetime, local_day, local_datetime


AUTO_CONFIG_KEYS = ('auto_capture', 'active_days')


def _browser_retry_seconds(attempts):
    """Retry browser discovery every 5-10 seconds while the session stays armed."""
    return min(10, max(5, 4 + int(attempts or 0)))


def defaults():
    from supervision_db import config
    cfg = config()
    return dict(day=local_day(time.time()), start_time=cfg['work_start'], end_time=cfg['work_end'],
                debug_port=9222, page_match='Supervision', target_id='', response_path='changes.ashx',
                include_phone=False, timezone=DISPLAY_TIMEZONE,
                auto_capture=True, active_days=[1, 2, 3, 4, 5, 6, 7])


def with_persisted_auto_config(data):
    """Preserve auto-start preferences when legacy/manual callers omit them."""
    payload = dict(data or {})
    stored = store.load_config()
    for key in AUTO_CONFIG_KEYS:
        if key not in payload and key in stored:
            payload[key] = stored[key]
    return payload


def validate_settings(data, *, clock=None, starting=False):
    if not isinstance(data, dict): raise ValueError('Objet de configuration requis.')
    clock = time.time() if clock is None else float(clock)
    out = defaults()
    out.update({k:v for k,v in data.items() if k in out})
    if out['timezone'] != DISPLAY_TIMEZONE:
        raise ValueError('Utilisez le fuseau Europe/Paris, commun aux interfaces Nelyio.')
    try:
        day = datetime.strptime(str(out['day']), '%Y-%m-%d')
        start = datetime.strptime(str(out['start_time']), '%H:%M').time()
        end = datetime.strptime(str(out['end_time']), '%H:%M').time()
        if start >= end: raise ValueError()
        if not isinstance(out['include_phone'], bool): raise ValueError()
        if not isinstance(out['auto_capture'], bool): raise ValueError()
        if not isinstance(out['active_days'], (list, tuple)): raise ValueError()
        active_days = []
        for value in out['active_days']:
            if isinstance(value, bool): raise ValueError()
            day_value = int(value)
            if not 1 <= day_value <= 7: raise ValueError()
            if day_value not in active_days: active_days.append(day_value)
        if isinstance(out['debug_port'], bool): raise ValueError()
        port = int(out['debug_port'])
        if not 1024 <= port <= 65535: raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Date, plage horaire ou port invalide. La collecte reste sur une seule journee.')
    out['debug_port'] = port; out['day'] = day.strftime('%Y-%m-%d')
    out['active_days'] = sorted(active_days)
    out['start_time'] = start.strftime('%H:%M'); out['end_time'] = end.strftime('%H:%M')
    for key, t in (('start_ts', start), ('end_ts', end)):
        wall = datetime.combine(day.date(), t)
        # Do not accept missing/ambiguous DST-transition times for scheduling.
        if wall.hour == 2 and day.month in (3, 10) and day.weekday() == 6 and day.day >= 25:
            raise ValueError('Choisissez une heure hors du changement de fuseau (02h-03h).')
        out[key] = wall.replace(tzinfo=timezone(timedelta(minutes=france_offset_for_local_datetime(wall)))).timestamp()
    if starting:
        today = datetime.strptime(local_day(clock), '%Y-%m-%d')
        if day < today or day > today + timedelta(days=7) or out['end_ts'] <= clock:
            raise ValueError('Choisissez une journee non terminee, entre aujourd hui et les 7 prochains jours. Le live ne recupere pas le passe.')
    out['page_match'] = str(out['page_match']).strip()
    if not 3 <= len(out['page_match']) <= 160 or any(ch in out['page_match'] for ch in ('\n','\r','?','#','@')):
        raise ValueError('Filtre d onglet invalide : utilisez une partie du chemin, sans identifiant ni jeton.')
    out['target_id'] = str(out['target_id']).strip()
    if out['target_id'] and not re.fullmatch(r'[a-zA-Z0-9_.-]{1,160}', out['target_id']): raise ValueError('Onglet invalide.')
    out['response_path'] = str(out['response_path']).strip()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,100}', out['response_path']): raise ValueError('Nom de reponse invalide.')
    return out


def ensure_auto_config(actor='auto-migration'):
    """Add RC29.4 auto-start keys to the existing JSON config without resetting it."""
    stored = store.load_config()
    changed = False
    if 'start_time' not in stored or 'end_time' not in stored:
        base = defaults()
        if 'start_time' not in stored:
            stored['start_time'] = base['start_time']; changed = True
        if 'end_time' not in stored:
            stored['end_time'] = base['end_time']; changed = True
    if 'auto_capture' not in stored:
        stored['auto_capture'] = True; changed = True
    if 'active_days' not in stored:
        stored['active_days'] = [1, 2, 3, 4, 5, 6, 7]; changed = True
    if changed:
        # Additive JSON migration only: no business DB reset and no table rewrite.
        store.save_config(stored, actor)
    return stored


def set_auto_capture(enabled, actor, clock=None):
    """Persist the auto-start switch; enabling it explicitly clears today's manual hold."""
    if not isinstance(enabled, bool):
        raise ValueError('Le reglage Détection automatique doit etre vrai ou faux.')
    clock = time.time() if clock is None else float(clock)
    stored = ensure_auto_config(actor='auto-migration')
    stored['auto_capture'] = enabled
    validated = validate_settings({**defaults(), **stored}, clock=clock)
    store.save_config({k:v for k,v in validated.items() if not k.endswith('_ts')}, actor)
    if enabled:
        store.clear_auto_suppression(actor, clock=clock)
    return status(clock=clock)


def auto_window_state(clock=None):
    """Return the factual automatic-capture eligibility for the current business day.

    This is deliberately independent from the session connection_state.  A session can
    be armed but still waiting for a worker/browser; the UI must not mislabel that as
    "waiting for the time window" once the configured window is already active.
    """
    clock = time.time() if clock is None else float(clock)
    stored = ensure_auto_config()
    day = local_day(clock)
    settings = validate_settings({**defaults(), **stored, 'day': day}, clock=clock)
    weekday = local_datetime(clock).isoweekday()
    active_day = weekday in settings['active_days']
    if not settings['auto_capture']:
        phase, reason = 'disabled', 'disabled'
    elif not active_day:
        phase, reason = 'inactive_day', 'inactive_day'
    elif clock < settings['start_ts']:
        phase, reason = 'before_window', 'outside_window'
    elif clock >= settings['end_ts']:
        phase, reason = 'after_window', 'outside_window'
    else:
        phase, reason = 'active_window', 'eligible'
    return {
        'phase': phase, 'reason': reason, 'eligible_now': reason == 'eligible',
        'enabled': bool(settings['auto_capture']), 'active_day': bool(active_day),
        'weekday': int(weekday), 'day': day, 'server_clock': display(clock),
        'start_time': settings['start_time'], 'end_time': settings['end_time'],
        'start_ts': settings['start_ts'], 'end_ts': settings['end_ts'],
        'seconds_to_start': max(0, int(settings['start_ts'] - clock)),
        'seconds_to_end': max(0, int(settings['end_ts'] - clock)),
    }


def ensure_auto_session(clock=None):
    """Atomically arm today's session when automatic capture is eligible.

    The final duplicate protection remains store.create_auto_session(BEGIN IMMEDIATE),
    so two Live workers may race safely without creating two sessions.
    """
    clock = time.time() if clock is None else float(clock)
    stored = ensure_auto_config()
    day = local_day(clock)
    settings = validate_settings({**stored, 'day': day}, clock=clock)
    # Automatic sessions must never pin yesterday's CDP target identifier.
    # An Edge tab recreated during the day receives a new target id; leaving
    # target_id empty lets Reader select the single matching supervision tab.
    settings['target_id'] = ''
    if not settings['auto_capture']:
        return {'created': False, 'reason': 'disabled', 'day': day}
    weekday = local_datetime(clock).isoweekday()
    if weekday not in settings['active_days']:
        return {'created': False, 'reason': 'inactive_day', 'day': day}
    if not settings['start_ts'] <= clock < settings['end_ts']:
        return {'created': False, 'reason': 'outside_window', 'day': day}
    if store.auto_suppressed_day() == day:
        return {'created': False, 'reason': 'stopped_manually', 'day': day}
    unfinished = store.unfinished()
    if any(str(item.get('day') or '') == day for item in unfinished):
        return {'created': False, 'reason': 'already_armed', 'day': day}
    if unfinished:
        # Preserve the global one-collector invariant. Manager.resume() will
        # normally close an expired prior-day session before the next retry.
        return {'created': False, 'reason': 'other_session_active', 'day': day}
    sid, reason = store.create_auto_session(settings, clock=clock)
    if not sid:
        return {'created': False, 'reason': reason, 'day': day}
    return {'created': True, 'reason': 'armed', 'day': day, 'session_id': sid}


class Manager:
    def __init__(self, reader_factory=Reader, clock=time.time):
        self.reader_factory, self.clock = reader_factory, clock
        self.lock = threading.Lock()
        self.shutdown_event = threading.Event()
        self.thread = None
        self.sid = None
        self.owner = uuid.uuid4().hex
        self.resume_timer = None

    def start(self, data, actor):
        settings = validate_settings(with_persisted_auto_config(data), clock=self.clock(), starting=True)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise RuntimeError('Une collecte est deja en cours. Arretez-la avant de changer la journee.')
            sid = store.create_session(settings, actor, self.clock(), owner=self.owner)
            store.save_config({k:v for k,v in settings.items() if not k.endswith('_ts')}, actor)
            self._launch(sid)
        return store.public_status(self.clock())

    def _launch(self, sid):
        self.sid = sid; self.shutdown_event.clear()
        self.thread = threading.Thread(target=self._run, args=(sid,), name='nelyio-live-one-day', daemon=True)
        self.thread.start()

    def resume(self):
        store.init()
        # V60: Live is self-contained. Events are acknowledged only inside
        # Nelyio_Live.db and are never published into Support/Details.
        store.settle_pending_local()
        with self.lock:
            if self.thread and self.thread.is_alive(): return
            for item in store.unfinished():
                if item['end_ts'] <= self.clock():
                    store.finish(item['id'], 'completed', clock=self.clock()); continue
                if item['stop_requested']:
                    store.finish(item['id'], 'stopped', clock=self.clock()); continue
                if store.claim(item['id'], self.owner, self.clock()):
                    self._launch(item['id'])
                    return
                # A crash leaves a short lease. Retry without creating a new day.
                if not self.shutdown_event.is_set():
                    if self.resume_timer: self.resume_timer.cancel()
                    self.resume_timer = threading.Timer(5, self.resume)
                    self.resume_timer.daemon = True
                    self.resume_timer.start()
                    return

    def heal_due_waiting(self, clock=None, grace_seconds=12.0):
        """Recover a due session that is still stuck in the pre-window state.

        The recovery is intentionally narrow: only the current business day, only an
        unfinished session whose configured start has already passed, and only the
        neutral `waiting` connection state.  Browser errors (`waiting_browser`) are not
        restarted here because they already have their own retry loop.
        """
        now = self.clock() if clock is None else float(clock)
        today = local_day(now)
        due = None
        for item in store.unfinished():
            if str(item.get('day') or '') != today:
                continue
            if float(item.get('start_ts') or 0) <= now < float(item.get('end_ts') or 0):
                if str(item.get('connection_state') or '') == 'waiting' and not item.get('stop_requested'):
                    due = item
                    break
        if not due:
            return {'recovered': False, 'reason': 'no_due_waiting_session'}
        age = max(0.0, now - max(float(due.get('created_at') or 0), float(due.get('start_ts') or 0)))
        if age < float(grace_seconds):
            return {'recovered': False, 'reason': 'grace_period', 'age_seconds': round(age, 1), 'session_id': due['id']}

        thread = None
        with self.lock:
            if self.thread and self.thread.is_alive() and self.sid == due['id']:
                thread = self.thread
                self.shutdown_event.set()
        if thread is not None:
            thread.join(timeout=4)
            if thread.is_alive():
                return {'recovered': False, 'reason': 'collector_thread_busy', 'age_seconds': round(age, 1), 'session_id': due['id']}
            with self.lock:
                if self.thread is thread:
                    self.thread = None
                    self.sid = None
            self.shutdown_event.clear()

        # If there was no local thread, resume() safely claims only an unowned or
        # expired lease.  It never steals a valid lease from another live worker.
        self.resume()
        return {'recovered': True, 'reason': 'resume_requested', 'age_seconds': round(age, 1), 'session_id': due['id']}

    def shutdown(self):
        self.shutdown_event.set()
        if self.resume_timer: self.resume_timer.cancel()
        if self.thread and self.thread.is_alive(): self.thread.join(timeout=6)

    def _tick(self, sid):
        item = store.session(sid)
        if not item or item['owner'] != self.owner: return 'interrupted'
        if self.shutdown_event.is_set(): return 'waiting_restart'
        if item['stop_requested']: return 'stopped'
        if self.clock() >= item['end_ts']: return 'completed'
        if item['lease_until'] - self.clock() < 15:
            if not store.renew(sid, self.owner, self.clock()): return 'interrupted'
        return None

    def _run(self, sid):
        settings = json.loads(store.session(sid)['settings_json'])
        final, final_error = 'interrupted', ''
        try:
            while self.clock() < settings['start_ts']:
                final = self._tick(sid)
                if final: return
                self.shutdown_event.wait(0.5)
            attempts = 0
            while True:
                final = self._tick(sid)
                if final: break
                source = 'live-' + sid + '-' + uuid.uuid4().hex[:10]
                decoder = Decoder(include_phone=settings['include_phone'])
                store.update_connection(sid, 'connecting')
                try:
                    with self.reader_factory(settings) as reader:
                        last_receipt, last_publish, last_stamp = self.clock(), 0.0, 0.0
                        store.update_connection(sid, 'connected_waiting_data')
                        while True:
                            final = self._tick(sid)
                            if final: break
                            result = reader.poll(timeout=0.5)
                            if result:
                                rid, stamp, body = result
                                if stamp < last_stamp:
                                    raise CaptureError('Reponses recues dans le desordre. Nouvelle sequence de capture.')
                                last_stamp = stamp
                                decoded = decoder.decode(body)
                                store.record_response(sid, source, stamp, rid,
                                    hashlib.sha256(body.encode('utf-8')).hexdigest(), decoded)
                                # Unrecognized responses cannot keep a healthy capture alive.
                                if decoded['valid']: last_receipt = self.clock(); attempts = 0
                            if self.clock() - last_publish >= 2:
                                store.settle_pending_local(); last_publish = self.clock()
                            if self.clock() - last_receipt > 60:
                                raise CaptureError('Aucune reponse de supervision reconnue depuis 60 secondes. Verifiez la session et le filtre; reconnexion en cours.')
                        if final: break
                except (CaptureError, OSError, ValueError) as exc:
                    # Only our curated messages are shown; no WebSocket headers/tokens.
                    message = str(exc) if isinstance(exc, (CaptureError, ValueError)) else 'Erreur locale de collecte. Reconnexion en cours.'
                    store.end_call_source(sid, source)
                    store.update_connection(sid, 'waiting_browser', message)
                    attempts += 1
                    # Browser absence/ambiguity is a waiting state, not a
                    # terminal failure. Retry quickly without busy-looping.
                    until = self.clock() + _browser_retry_seconds(attempts)
                    while self.clock() < until:
                        final = self._tick(sid)
                        if final: break
                        self.shutdown_event.wait(0.5)
                    if final: break
        except Exception:
            final, final_error = 'interrupted', 'Collecte interrompue par une erreur locale. Les donnees deja recues sont conservees.'
        finally:
            try:
                store.settle_pending_local()
            except Exception:
                final_error = 'La finalisation locale Live a echoue; les donnees deja recues restent dans Nelyio_Live.db.'
            try: store.finish(sid, final or 'interrupted', final_error, self.clock(), owner=self.owner)
            except Exception: pass


_MANAGER = None

def manager():
    global _MANAGER
    if _MANAGER is None: _MANAGER = Manager()
    return _MANAGER


def _live_service_status():
    try:
        import service_state
        state = service_state.public_status()
        return next((r for r in state['services'] if r['service'] == 'live'), None) or {'healthy': False, 'state': 'not_started'}
    except Exception:
        return {'healthy': False, 'state': 'status_error'}


def arm(data, actor):
    """Create a durable session only when the external Live worker is healthy."""
    from service_mode import external_services_enabled
    if external_services_enabled():
        live = _live_service_status()
        if not live.get('healthy'):
            raise RuntimeError('Service Live indisponible. Relancez Nelyio/les services avant de demarrer la capture.')
    settings = validate_settings(with_persisted_auto_config(data), clock=time.time(), starting=True)
    sid = store.create_session(settings, actor, time.time(), owner=None)
    store.save_config({k:v for k,v in settings.items() if not k.endswith('_ts')}, actor)
    result = store.public_status()
    result['armed_session_id'] = sid
    return result


def status(clock=None):
    # Read status + persisted configuration through one DB transaction instead
    # of opening a second PostgreSQL connection for every polling request.
    clock = time.time() if clock is None else float(clock)
    result = store.public_status(clock=clock, include_config=True)
    stored = result.pop('_stored_config', {})
    result['config'] = validate_settings({**defaults(), **stored})
    result['auto_capture_suppressed_day'] = store.auto_suppressed_day()
    result['auto_capture_blocked_today'] = result['auto_capture_suppressed_day'] == local_day(clock)
    result['auto_window'] = auto_window_state(clock=clock)
    try:
        from service_mode import external_services_enabled
        if external_services_enabled():
            result['live_service'] = _live_service_status()
    except Exception:
        result['live_service']={'healthy':False,'state':'status_error'}
    try:
        import websockets
        from websockets.sync.client import connect  # noqa: F401
        result['dependency_ready'] = int(websockets.__version__.split('.')[0]) >= 14
        result['dependency_version'] = websockets.__version__
    except ImportError:
        result['dependency_ready'] = False
    return result
