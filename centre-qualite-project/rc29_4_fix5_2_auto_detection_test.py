from __future__ import annotations

from pathlib import Path

import pytest

import collection_service as service
import collection_store as store
from nelyio_time import local_wall_timestamp


def _defaults():
    return dict(
        day='2026-10-01', start_time='08:00', end_time='19:00',
        debug_port=9222, page_match='Supervision', target_id='',
        response_path='changes.ashx', include_phone=False,
        timezone='Europe/Paris', auto_capture=True,
        active_days=[1, 2, 3, 4, 5, 6, 7],
    )


@pytest.fixture
def isolated_live(tmp_path, monkeypatch):
    live_db = tmp_path / 'Nelyio_Live.db'
    monkeypatch.setattr(store, 'db_path', lambda: live_db)
    monkeypatch.setattr(service, 'defaults', _defaults)
    store._SCHEMA_IDENTITIES.clear()
    store.init()
    yield live_db
    store._SCHEMA_IDENTITIES.clear()


def test_auto_window_reports_active_window_at_0849(isolated_live):
    service.ensure_auto_config()
    now = local_wall_timestamp('2026-10-01', 8, 49)
    state = service.auto_window_state(clock=now)
    assert state['phase'] == 'active_window'
    assert state['eligible_now'] is True
    assert state['start_time'] == '08:00'
    assert state['end_time'] == '19:00'
    assert state['active_day'] is True


def test_status_exposes_auto_window_separately_from_connection_state(isolated_live):
    service.ensure_auto_config()
    now = local_wall_timestamp('2026-10-01', 8, 49)
    created = service.ensure_auto_session(clock=now)
    assert created['created'] is True
    out = service.status(clock=now)
    assert out['current']['connection_state'] == 'waiting'
    assert out['auto_window']['phase'] == 'active_window'
    assert out['auto_window']['eligible_now'] is True


def test_due_waiting_session_requests_safe_resume_after_grace(isolated_live, monkeypatch):
    service.ensure_auto_config()
    start = local_wall_timestamp('2026-10-01', 8, 0)
    now = local_wall_timestamp('2026-10-01', 8, 49)
    created = service.ensure_auto_session(clock=start + 1)
    assert created['created'] is True
    manager = service.Manager(clock=lambda: now)
    calls = []
    monkeypatch.setattr(manager, 'resume', lambda: calls.append('resume'))
    result = manager.heal_due_waiting(clock=now, grace_seconds=12)
    assert result['recovered'] is True
    assert result['reason'] == 'resume_requested'
    assert calls == ['resume']


def test_auto_arm_helper_retries_resume_even_when_session_already_exists(monkeypatch):
    import live_service

    class FakeLive:
        def __init__(self):
            self.resume_calls = 0
        def resume(self):
            self.resume_calls += 1

    live = FakeLive()
    monkeypatch.setattr(live_service, 'ensure_auto_session', lambda clock=None: {'created': False, 'reason': 'already_armed'})
    result = live_service._resume_and_auto_arm(live, clock=123)
    assert result['created'] is False
    assert live.resume_calls == 2


def test_collection_ui_does_not_mislabel_due_waiting_as_time_window():
    js = (Path(__file__).resolve().parent / 'static' / 'collection.js').read_text(encoding='utf-8')
    assert "w.phase==='active_window'" in js
    assert 'Plage active' in js
    assert 'Heure serveur' in js
    assert 'collectionConnectionText(s,d)' in js
