from __future__ import annotations

import pytest

import collection_cdp as cdp
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


def _target(target_id):
    return {
        'id': target_id,
        'url': 'https://example.invalid/Supervision/Login.aspx',
        'websocket': f'ws://127.0.0.1:9222/devtools/page/{target_id}',
    }


@pytest.fixture
def isolated_live(tmp_path, monkeypatch):
    live_db = tmp_path / 'Nelyio_Live.db'
    monkeypatch.setattr(store, 'db_path', lambda: live_db)
    monkeypatch.setattr(service, 'defaults', _defaults)
    store._SCHEMA_IDENTITIES.clear()
    store.init()
    yield live_db
    store._SCHEMA_IDENTITIES.clear()


def test_unique_matching_tab_is_selected_automatically():
    only = _target('new-tab')
    assert cdp._choose_target([only], '') is only


def test_recreated_tab_rebinds_when_old_target_id_disappeared():
    replacement = _target('replacement-tab')
    assert cdp._choose_target([replacement], 'old-tab') is replacement


def test_explicit_target_is_kept_when_it_still_exists_among_multiple_tabs():
    wanted = _target('wanted')
    other = _target('other')
    assert cdp._choose_target([other, wanted], 'wanted') is wanted


def test_zero_or_ambiguous_tabs_are_retryable_waiting_states():
    with pytest.raises(cdp.CaptureError, match="En attente de l'onglet"):
        cdp._choose_target([], '')
    with pytest.raises(cdp.CaptureError, match='Plusieurs onglets'):
        cdp._choose_target([_target('a'), _target('b')], '')


def test_probe_does_not_raise_when_edge_is_not_open(monkeypatch):
    monkeypatch.setattr(cdp, 'local_targets', lambda *_: (_ for _ in ()).throw(
        cdp.CaptureError("En attente d'Edge de collecte : port de diagnostic local inaccessible.")))
    result = cdp.probe(_defaults())
    assert result['ok'] is False
    assert result['state'] == 'waiting_browser'
    assert result['targets'] == []
    assert "En attente d'Edge" in result['message']


def test_probe_reports_unique_target_as_auto_selected(monkeypatch):
    monkeypatch.setattr(cdp, 'local_targets', lambda *_: [_target('only')])
    result = cdp.probe(_defaults())
    assert result['ok'] is True
    assert result['state'] == 'target_detected'
    assert result['auto_select'] is True
    assert result['targets'][0]['id'] == 'only'


def test_auto_session_never_persists_stale_target_id(isolated_live):
    now = local_wall_timestamp('2026-09-29', 10, 0)
    cfg = _defaults()
    cfg['target_id'] = 'yesterday-tab'
    store.save_config(cfg, 'legacy')

    created = service.ensure_auto_session(clock=now)
    assert created['created'] is True
    row = store.session(created['session_id'])
    settings = __import__('json').loads(row['settings_json'])
    assert settings['target_id'] == ''


def test_browser_retry_cadence_is_between_five_and_ten_seconds():
    assert service._browser_retry_seconds(1) == 5
    assert service._browser_retry_seconds(2) == 6
    assert service._browser_retry_seconds(6) == 10
    assert service._browser_retry_seconds(99) == 10


def test_manager_keeps_session_alive_while_browser_is_missing(isolated_live):
    import time as _time

    now = local_wall_timestamp('2026-09-29', 10, 0)

    class MissingReader:
        def __init__(self, settings):
            self.settings = settings
        def __enter__(self):
            raise cdp.CaptureError("En attente d'Edge de collecte : port de diagnostic local inaccessible.")
        def __exit__(self, *_):
            return False

    manager = service.Manager(reader_factory=MissingReader, clock=lambda: now)
    result = manager.start(_defaults(), 'test')
    sid = result['current']['id']
    deadline = _time.time() + 2
    row = store.session(sid)
    while _time.time() < deadline and row['connection_state'] != 'waiting_browser':
        _time.sleep(0.02)
        row = store.session(sid)

    assert row['connection_state'] == 'waiting_browser'
    assert row['status'] == 'running'
    assert 'En attente' in row['error']
    store.request_stop('test', clock=now, suppress_auto=False)
    manager.shutdown()


def test_manager_reconnects_same_session_after_browser_returns(isolated_live, monkeypatch):
    import time as _time

    now = local_wall_timestamp('2026-09-29', 10, 0)
    monkeypatch.setattr(service, '_browser_retry_seconds', lambda attempts: 0)

    class GoodReader:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def poll(self, timeout=0.5):
            _time.sleep(0.01)
            return None

    class SequenceFactory:
        def __init__(self):
            self.calls = 0
        def __call__(self, settings):
            self.calls += 1
            if self.calls == 1:
                class FirstFailure:
                    def __enter__(self_inner):
                        raise cdp.CaptureError("En attente de l'onglet de supervision : aucun onglet ne correspond au filtre.")
                    def __exit__(self_inner, *_):
                        return False
                return FirstFailure()
            return GoodReader()

    factory = SequenceFactory()
    manager = service.Manager(reader_factory=factory, clock=lambda: now)
    result = manager.start(_defaults(), 'test')
    sid = result['current']['id']
    deadline = _time.time() + 2
    row = store.session(sid)
    while _time.time() < deadline and row['connection_state'] != 'connected_waiting_data':
        _time.sleep(0.02)
        row = store.session(sid)

    assert factory.calls >= 2
    assert row['id'] == sid
    assert row['connection_state'] == 'connected_waiting_data'
    assert row['status'] == 'running'
    store.request_stop('test', clock=now, suppress_auto=False)
    manager.shutdown()
