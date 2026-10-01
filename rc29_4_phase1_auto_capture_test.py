from __future__ import annotations

import threading

import pytest

import collection_service as service
import collection_store as store
from nelyio_time import local_wall_timestamp


def _defaults():
    return dict(
        day='2026-09-29', start_time='08:00', end_time='19:00',
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


def test_additive_auto_config_migration_preserves_existing_values(isolated_live):
    store.save_config({'page_match': 'Ma Supervision', 'include_phone': True}, 'legacy')
    migrated = service.ensure_auto_config()
    persisted = store.load_config()

    assert migrated['page_match'] == 'Ma Supervision'
    assert migrated['include_phone'] is True
    assert persisted['start_time'] == '08:00'
    assert persisted['end_time'] == '19:00'
    assert persisted['auto_capture'] is True
    assert persisted['active_days'] == [1, 2, 3, 4, 5, 6, 7]


def test_auto_session_is_created_once_inside_window(isolated_live):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    service.ensure_auto_config()

    first = service.ensure_auto_session(clock=now)
    second = service.ensure_auto_session(clock=now)

    assert first['created'] is True and first['reason'] == 'armed'
    assert second['created'] is False and second['reason'] == 'already_armed'
    row = store.session(first['session_id'])
    assert row['day'] == '2026-09-29'
    assert row['actor'] == 'auto'
    assert row['status'] == 'armed'
    assert row['owner'] is None
    assert len(store.unfinished()) == 1


def test_auto_session_respects_disabled_days_and_time_window(isolated_live):
    service.ensure_auto_config()
    cfg = store.load_config()
    cfg['active_days'] = [1]  # 2026-09-29 is Tuesday.
    store.save_config(cfg, 'test')
    tuesday = local_wall_timestamp('2026-09-29', 10, 0)
    assert service.ensure_auto_session(clock=tuesday)['reason'] == 'inactive_day'

    cfg['active_days'] = [1, 2, 3, 4, 5, 6, 7]
    store.save_config(cfg, 'test')
    early = local_wall_timestamp('2026-09-29', 7, 59)
    assert service.ensure_auto_session(clock=early)['reason'] == 'outside_window'

    cfg['auto_capture'] = False
    store.save_config(cfg, 'test')
    assert service.ensure_auto_session(clock=tuesday)['reason'] == 'disabled'
    assert store.unfinished() == []


def test_manual_stop_blocks_same_day_but_not_next_day(isolated_live):
    day1 = local_wall_timestamp('2026-09-29', 10, 0)
    day2 = local_wall_timestamp('2026-09-30', 10, 0)
    service.ensure_auto_config()

    first = service.ensure_auto_session(clock=day1)
    assert first['created'] is True
    assert store.request_stop('admin', clock=day1) == 1
    assert store.auto_suppressed_day() == '2026-09-29'
    assert service.ensure_auto_session(clock=day1)['reason'] == 'stopped_manually'

    next_day = service.ensure_auto_session(clock=day2)
    assert next_day['created'] is True
    assert store.session(next_day['session_id'])['day'] == '2026-09-30'


def test_explicit_reactivation_allows_same_day_restart(isolated_live, monkeypatch):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    service.ensure_auto_config()
    first = service.ensure_auto_session(clock=now)
    assert first['created'] is True
    store.request_stop('admin', clock=now)

    monkeypatch.setattr(service, '_live_service_status', lambda: {'healthy': True, 'state': 'running'})
    service.set_auto_capture(True, 'admin', clock=now)

    assert store.auto_suppressed_day() == ''
    restarted = service.ensure_auto_session(clock=now)
    assert restarted['created'] is True


def test_two_workers_cannot_create_two_auto_sessions(isolated_live):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    service.ensure_auto_config()
    barrier = threading.Barrier(3)
    results = []
    errors = []

    def worker():
        try:
            barrier.wait(timeout=5)
            results.append(service.ensure_auto_session(clock=now))
        except BaseException as exc:  # surfaced below for a useful test failure
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads: thread.start()
    barrier.wait(timeout=5)
    for thread in threads: thread.join(timeout=10)

    assert errors == []
    assert len(results) == 2
    assert sum(1 for result in results if result['created']) == 1
    assert len(store.unfinished()) == 1


def test_live_service_resumes_before_and_after_new_auto_arm(monkeypatch):
    import live_service

    class FakeLive:
        def __init__(self): self.resume_calls = 0
        def resume(self): self.resume_calls += 1

    live = FakeLive()
    monkeypatch.setattr(live_service, 'ensure_auto_session', lambda clock=None: {'created': True, 'session_id': 'x'})
    result = live_service._resume_and_auto_arm(live, clock=123)

    assert result['created'] is True
    assert live.resume_calls == 2


def test_expired_prior_day_is_closed_before_next_auto_day(isolated_live):
    from collection_service import Manager

    day1_clock = local_wall_timestamp('2026-09-29', 18, 0)
    day2_clock = local_wall_timestamp('2026-09-30', 10, 0)
    previous = dict(_defaults())
    previous.update(
        day='2026-09-29', start_time='08:00', end_time='19:00',
        start_ts=local_wall_timestamp('2026-09-29', 8, 0),
        end_ts=local_wall_timestamp('2026-09-29', 19, 0),
    )
    sid = store.create_session(previous, 'auto', clock=day1_clock, owner=None)

    manager = Manager(clock=lambda: day2_clock)
    manager.resume()
    assert store.session(sid)['status'] == 'completed'

    next_day = service.ensure_auto_session(clock=day2_clock)
    assert next_day['created'] is True
    assert store.session(next_day['session_id'])['day'] == '2026-09-30'


def test_auto_created_session_uses_existing_claim_lease(isolated_live):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    service.ensure_auto_config()
    created = service.ensure_auto_session(clock=now)
    sid = created['session_id']

    assert store.claim(sid, 'worker-a', clock=now) is True
    assert store.claim(sid, 'worker-b', clock=now) is False
    assert store.session(sid)['owner'] == 'worker-a'


def test_manual_stop_race_never_leaves_auto_session_active(isolated_live):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    service.ensure_auto_config()

    for _ in range(10):
        store.clear_auto_suppression('test-reset', clock=now)
        for item in store.unfinished():
            store.finish(item['id'], 'interrupted', clock=now)
        barrier = threading.Barrier(3)
        errors = []

        def auto_worker():
            try:
                barrier.wait(timeout=5)
                service.ensure_auto_session(clock=now)
            except BaseException as exc:
                errors.append(exc)

        def stop_worker():
            try:
                barrier.wait(timeout=5)
                store.request_stop('admin', clock=now)
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=auto_worker), threading.Thread(target=stop_worker)]
        for thread in threads: thread.start()
        barrier.wait(timeout=5)
        for thread in threads: thread.join(timeout=10)

        assert errors == []
        assert store.auto_suppressed_day() == '2026-09-29'
        assert store.unfinished() == []
