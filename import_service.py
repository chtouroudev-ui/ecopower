"""Dedicated Import Worker process for Nelyio V59 production.

It drains durable manual-upload jobs, scans the Support import folder and runs
the diagnostic auto-import scheduler. Heavy parsing therefore no longer shares
Python CPU/thread state with HTTP request handling.
"""
from __future__ import annotations

import signal
import threading
import time

import supervision  # initializes the Support schema/facade once in this process
from app_db import ensure_schema, get_setting
from auto_import import scan_auto_import_folder
from diagnostic_import import import_diagnostic_source
from error_log import log_unexpected_error
from import_workflow import retry_pending_jobs, workflow_status
from service_mode import service_poll_seconds
import service_state
from service_control import clear_stop, stop_requested

_STOP = threading.Event()
_DETAIL_LOCK = threading.Lock()
_DETAIL = {'busy': False}


def _handle_stop(*_):
    _STOP.set()


def _set_detail(**values):
    with _DETAIL_LOCK:
        _DETAIL.update(values)


def _should_stop():
    return _STOP.is_set() or stop_requested('import_service')


def _heartbeat(started, poll):
    while not _STOP.wait(3):
        if stop_requested('import_service'):
            _STOP.set(); break
        with _DETAIL_LOCK:
            detail=dict(_DETAIL)
        detail['poll_seconds']=poll
        try: service_state.beat('import', detail=detail, started_at=started)
        except Exception: pass


def _diagnostic_due(state):
    if get_setting('auto_import_enabled', '0') != '1':
        return state
    source = get_setting('diagnostic_source_path', '').strip()
    if not source:
        return state
    try:
        minutes = max(1, min(1440, int(get_setting('auto_import_minutes', '5'))))
    except Exception:
        minutes = 5
    now_mono = time.monotonic()
    if state and now_mono - state < minutes * 60:
        return state
    _set_detail(busy=True, phase='diagnostic_import')
    try:
        import_diagnostic_source(source, 'AUTO_IMPORT_SERVICE')
    except Exception:
        log_unexpected_error('import_service.diagnostic')
    finally:
        _set_detail(busy=False, phase='idle')
    return now_mono


def _quality_assignment_recovery_due(last_attempt):
    # Group membership depends on configured ACTIVE agent->file assignments.
    # Retry recovery in this worker (never in a GET) so a missing snapshot can
    # self-heal after new SIMPLIFY2 archives arrive while the app is running.
    now=time.monotonic()
    if last_attempt and now-last_attempt < 30.0:
        return last_attempt
    try:
        from quality_service import _read_raw, has_quality_agent_queue_assignments, recover_quality_assignments_from_archive
        current=_read_raw()
        if not has_quality_agent_queue_assignments(current):
            _set_detail(busy=True,phase='quality_assignment_recovery')
            recover_quality_assignments_from_archive(current,cooldown_seconds=60.0)
    except Exception:
        log_unexpected_error('import_service.quality_assignment_recovery')
    finally:
        _set_detail(busy=False,phase='idle')
    return now


def run():
    ensure_schema()
    poll = service_poll_seconds('import', 1.0)
    diag_last = 0.0
    quality_recovery_last = 0.0
    started = time.time()
    service_state.beat('import', started_at=started, detail={'poll_seconds': poll, 'busy': False, 'phase':'startup'})
    hb=threading.Thread(target=_heartbeat,args=(started,poll),name='nelyio-import-heartbeat',daemon=True);hb.start()
    # First recovery attempt is outside Web/API and unthrottled at startup.
    try:
        from quality_service import _read_raw, has_quality_agent_queue_assignments, recover_quality_assignments_from_archive
        current=_read_raw()
        if not has_quality_agent_queue_assignments(current):
            _set_detail(busy=True,phase='quality_assignment_recovery')
            recover_quality_assignments_from_archive(current,cooldown_seconds=0.0)
        quality_recovery_last=time.monotonic()
    except Exception:
        log_unexpected_error('import_service.quality_assignment_recovery')
    finally:
        _set_detail(busy=False,phase='idle')
    while not _should_stop():
        work = 0
        try:
            _set_detail(busy=True,phase='support_scan')
            # Discover/queue every watched-folder source first. A slow older
            # export must never hide a newer SIMPLIFY2 file from the queue.
            results = scan_auto_import_folder()
            work += len(results)
            _set_detail(busy=True,phase='support_import')
            retry_pending_jobs(limit=1)
            _set_detail(busy=False,phase='idle')
            diag_last = _diagnostic_due(diag_last)
            quality_recovery_last = _quality_assignment_recovery_due(quality_recovery_last)
            status = workflow_status()
            _set_detail(
                queue=int(status.get('job_counts', {}).get('queued', 0)),
                running=int(status.get('job_counts', {}).get('running', 0)),
                partial=int(status.get('job_counts', {}).get('partial', 0)),
                last_scan_imports=work,
            )
        except Exception:
            log_unexpected_error('import_service.loop')
            _set_detail(busy=False, phase='loop_error', error='loop_error')
        if _STOP.wait(poll if not work else 0.2): break
        if stop_requested('import_service'): _STOP.set(); break
    service_state.stop('import')


def main():
    clear_stop('import_service')
    for name in ('SIGINT', 'SIGTERM'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), _handle_stop)
    run()


if __name__ == '__main__':
    main()
