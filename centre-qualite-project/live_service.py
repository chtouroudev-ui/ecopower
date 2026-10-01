"""Dedicated NELYIO V60 Live Service.

Live capture is intentionally isolated from Support/Quality history:
- its operational spool is Nelyio_Live.db (local SQLite/WAL);
- it never publishes incomplete rows to Support, Details or Quality;
- finalized factual observations are copied idempotently to a separate persistent
  evidence table before old spool rows may be purged.
Historical KPI reporting remains the responsibility of explicit SIMPLIFY2 imports.
"""
from __future__ import annotations

import signal
import threading
import time

import collection_store as store
from collection_service import manager, ensure_auto_config, ensure_auto_session
from error_log import log_unexpected_error
from nelyio_time import local_day
from service_mode import service_poll_seconds
import service_state
from service_control import clear_stop, stop_requested

_STOP = threading.Event()


def _handle_stop(*_):
    _STOP.set()


def _resume_and_auto_arm(live, clock=None):
    """Resume durable work, arm today when eligible, then verify progress."""
    live.resume()
    auto_capture = ensure_auto_session(clock=clock)
    # Always resume a second time.  This closes the gap where an already-armed
    # session survived a service restart but was not claimed on the first pass.
    live.resume()
    return auto_capture


def run():
    store.init(force=False)
    ensure_auto_config()
    poll = service_poll_seconds('live', 1.0)
    started = time.time()
    live = manager()
    retained_day = None
    last_purge = None
    quality_tick_seconds = 5.0
    last_quality_tick = 0.0
    auto_tick_seconds = 5.0
    last_auto_tick = 0.0
    hermes_scan_tick_seconds = 30.0
    last_hermes_scan_tick = 0.0
    hermes_scan_schedule = {'started': False, 'reason': 'not_checked'}
    auto_capture = {'created': False, 'reason': 'not_checked'}
    auto_recovery = {'recovered': False, 'reason': 'not_checked'}
    quality_status = {'enabled': True, 'last_tick': None, 'error': ''}
    service_state.beat('live', started_at=started, detail={
        'poll_seconds': poll,
        'database': 'Nelyio_Live.db',
        'retention': 'current_day_spool',
        'publishes_to_support': False,
        'persists_finalized_live_evidence': True,
        'quality_tick_seconds': quality_tick_seconds,
        'auto_tick_seconds': auto_tick_seconds,
        'hermes_scan_tick_seconds': hermes_scan_tick_seconds,
    })
    try:
        while not _STOP.is_set() and not stop_requested('live_service'):
            try:
                today = local_day(time.time())
                history_sync={'persisted':0,'pending_finalized':0}
                if retained_day != today:
                    # Persist what can be proven final before applying retention.
                    # A database failure is handled by the outer loop; purge itself
                    # then defers every unsynchronized call observation.
                    try:
                        history_sync=store.persist_finalized_history(limit=1000)
                    except Exception:
                        log_unexpected_error('live_service.history_before_purge')
                    purge = store.purge_before_day(today)
                    retained_day = today
                    last_purge = purge
                # First resume/close any durable session left by a restart or
                # an expired prior day. Then auto-arm today's session if the
                # persisted policy allows it, and immediately let claim/lease
                # select the single worker that owns the capture.
                now = time.time()
                if now - last_auto_tick >= auto_tick_seconds:
                    auto_capture = _resume_and_auto_arm(live, clock=now)
                    try:
                        auto_recovery = live.heal_due_waiting(clock=now, grace_seconds=12.0)
                    except Exception:
                        log_unexpected_error('live_service.auto_recovery')
                        auto_recovery = {'recovered': False, 'reason': 'recovery_failed'}
                    last_auto_tick = now
                else:
                    live.resume()
                # Events are already projected into the dedicated Live database
                # during receipt. Acknowledge them locally, then copy only
                # finalized factual call observations to persistent evidence.
                settled = store.settle_pending_local()
                try:
                    history_sync=store.persist_finalized_history(limit=500)
                except Exception:
                    log_unexpected_error('live_service.history_sync')
                    try: history_sync=store.live_history_sync_status()
                    except Exception: history_sync={'error':'history_sync_failed'}
                brief = store.brief()
                hermes_auto_open = {'started': False, 'reason': 'not_needed'}
                if brief.get('active') and brief.get('connection_state') in {'waiting_browser','connecting'}:
                    try:
                        from hermes_supervision_launcher import maybe_launch_for_auto
                        cfg = store.config()
                        hermes_auto_open = maybe_launch_for_auto(int(cfg.get('debug_port') or 9222), clock=time.time())
                    except Exception:
                        log_unexpected_error('live_service.hermes_auto_open')
                        hermes_auto_open = {'started': False, 'reason': 'auto_open_error'}
                now = time.time()
                if now - last_hermes_scan_tick >= hermes_scan_tick_seconds:
                    try:
                        import hermes_diagnostic
                        hermes_scan_schedule = hermes_diagnostic.scheduler_tick(clock=now)
                    except Exception:
                        log_unexpected_error('live_service.hermes_scan_schedule')
                        hermes_scan_schedule = {'started': False, 'reason': 'schedule_tick_failed'}
                    last_hermes_scan_tick = now
                if now - last_quality_tick >= quality_tick_seconds:
                    try:
                        import live_quality
                        result = live_quality.tick(clock=now)
                        quality_status = {
                            'enabled': True,
                            'last_tick': now,
                            'scope_count': len(result.get('scopes') or []),
                            'evaluation_count': len(result.get('evaluations') or []),
                            'error': '',
                        }
                    except Exception:
                        log_unexpected_error('live_service.quality_tick')
                        quality_status = {'enabled': True, 'last_tick': now, 'error': 'quality_tick_failed'}
                    last_quality_tick = now
                service_state.beat('live', detail={
                    'poll_seconds': poll,
                    'database': 'Nelyio_Live.db',
                    'retention': 'current_day_only',
                    'retained_day': retained_day,
                    'last_purge': last_purge,
                    'publishes_to_support': False,
                    'persists_finalized_live_evidence': True,
                    'settled_last_tick': int(settled or 0),
                    'history_sync': history_sync,
                    'active': bool(brief.get('active')),
                    'fresh': bool(brief.get('fresh')),
                    'pending': int(brief.get('pending') or 0),
                    'auto_capture': auto_capture,
                    'auto_recovery': auto_recovery,
                    'hermes_auto_open': hermes_auto_open,
                    'hermes_scan_schedule': hermes_scan_schedule,
                    'quality': quality_status,
                }, started_at=started)
            except Exception:
                log_unexpected_error('live_service.loop')
                service_state.beat('live', detail={
                    'poll_seconds': poll,
                    'database': 'Nelyio_Live.db',
                    'retention': 'current_day_spool',
                    'publishes_to_support': False,
                    'persists_finalized_live_evidence': True,
                    'error': 'loop_error',
                }, started_at=started)
            if _STOP.wait(poll):
                break
            if stop_requested('live_service'):
                _STOP.set()
                break
    finally:
        live.shutdown()
        try:
            store.settle_pending_local()
        except Exception:
            pass
        try:
            store.persist_finalized_history(limit=5000)
        except Exception:
            log_unexpected_error('live_service.history_shutdown')
        service_state.stop('live', {'database':'Nelyio_Live.db','retention':'current_day_spool',
                                    'persists_finalized_live_evidence':True})


def main():
    clear_stop('live_service')
    for name in ('SIGINT', 'SIGTERM'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _handle_stop)
    run()


if __name__ == '__main__':
    main()
