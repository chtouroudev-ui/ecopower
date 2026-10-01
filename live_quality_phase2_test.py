"""Phase 2 regression tests for configurable Live quality signalling.

Run: python -m pytest live_quality_phase2_test.py -q
All state is isolated in temporary SQLite databases.
"""
from __future__ import annotations

import os
import sys
import types
import zipfile
from pathlib import Path

import pytest

os.environ['NELYIO_FORCE_SQLITE'] = '1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC'] = '1'
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def lab(tmp_path, monkeypatch):
    import app_config
    import supervision_context as ctx
    import collection_store

    with zipfile.ZipFile(ROOT / 'audit_empty_schemas.zip') as z:
        z.extractall(tmp_path)
    admin = tmp_path / 'TECHIN_Stock_Manager.db'
    live = tmp_path / 'Nelyio_Live.db'
    monkeypatch.setattr(app_config, 'APP_DB', admin)
    monkeypatch.setattr(ctx, 'DEFAULT_ADMIN_DB', admin)
    facade = types.ModuleType('supervision')
    facade.ADMIN_DB = admin
    facade.DB = tmp_path / 'NELYIO_Supervision.db'
    monkeypatch.setitem(sys.modules, 'supervision', facade)
    monkeypatch.setattr(collection_store, 'db_path', lambda: live)
    collection_store._SCHEMA_IDENTITIES.clear()
    collection_store.init()
    return tmp_path


def snapshot(kind='call', campaign='CABINET A', fresh=True, age=30):
    state = {'call': 'Inbound call', 'ready': 'Prêt', 'wrap': 'Wrap-up', 'pause': 'Pause', 'offline': 'Déconnecté'}[kind]
    return {
        'health': {'fresh': fresh, 'active': True, 'last_response_age': 2 if fresh else 45},
        'kpi': {'agents_known': 1, 'connected': 0 if kind == 'offline' else 1,
                'in_call': 1 if kind == 'call' else 0, 'available': 1 if kind == 'ready' else 0,
                'unavailable': 0, 'current_calls': 1 if kind == 'call' and fresh else None,
                'calls_waiting': None},
        'agents': [{
            'agent': '1001', 'name': 'Agent 1001', 'state': state, 'kind': kind,
            'line_id': '571', 'campaign': campaign, 'groups': [{'id': '2', 'name': 'MED02', 'service_name': 'MEDICAL'}],
            'assigned_groups': [{'id': '2', 'name': 'MED02', 'service_name': 'MEDICAL'}],
            'current_groups': [{'id': '2', 'name': 'MED02', 'service_name': 'MEDICAL'}],
            'service_names': ['MEDICAL'], 'state_age_seconds': age,
            'current_call': {'campaign': campaign, 'line_id': '571'} if kind == 'call' else None,
        }],
    }


def levels():
    return [
        {'level_key': 'CRITIQUE', 'label': 'CRITIQUE', 'rank': 400, 'color': '#B42318', 'enabled': 1, 'is_fallback': 0},
        {'level_key': 'NORMAL', 'label': 'NORMAL', 'rank': 100, 'color': '#24634A', 'enabled': 1, 'is_fallback': 1},
    ]


def test_unavailable_waiting_never_becomes_zero(lab):
    import live_quality
    scopes = live_quality.build_scopes(snapshot())
    campaign = next(x for x in scopes if x['scope_type'] == 'CAMPAIGN')
    assert campaign['metrics']['waiting_now']['value'] is None
    assert campaign['metrics']['waiting_now']['quality'] == 'unavailable'
    rule = {
        'id': 1, 'name': 'Fausse attente zéro', 'scope_type': 'CAMPAIGN', 'target_key': '',
        'match_mode': 'ALL', 'level_key': 'CRITIQUE', 'min_sample_size': 0, 'allow_partial': 0,
        'conditions': [{'metric': 'waiting_now', 'operator': '<=', 'value': 0}],
    }
    result = live_quality.evaluate_rule(rule, campaign)
    assert result['eligible'] is False
    assert result['matched'] is False
    assert result['reason'] == 'metric_unavailable'


def test_levels_colors_and_rules_are_configurable(lab):
    import live_quality
    live_quality.ensure_admin_schema()
    saved = live_quality.save_level({
        'level_key': 'URGENT', 'label': 'URGENT', 'rank': 450, 'color': '#C01020',
        'enabled': True, 'is_fallback': False,
    }, 'audit')
    assert saved['color'] == '#C01020'
    rule = live_quality.save_rule({
        'name': 'Pause longue test', 'scope_type': 'AGENT', 'level_key': 'URGENT', 'match_mode': 'ALL',
        'min_duration_seconds': 30, 'recovery_seconds': 20, 'cooldown_seconds': 60,
        'conditions': [{'metric': 'max_pause_seconds', 'operator': '>=', 'value': 600}],
    }, 'audit')
    cfg = live_quality.config_snapshot()
    assert any(x['level_key'] == 'URGENT' and x['color'] == '#C01020' for x in cfg['levels'])
    assert any(x['id'] == rule['id'] and x['level_key'] == 'URGENT' for x in cfg['rules'])


def test_min_duration_hysteresis_cooldown_and_no_duplicate_incident(lab):
    import live_quality
    rule = {
        'id': 9001, 'name': 'Aucun disponible test', 'enabled': 1,
        'scope_type': 'CAMPAIGN', 'target_key': 'CABINET A', 'match_mode': 'ALL', 'level_key': 'CRITIQUE',
        'min_duration_seconds': 120, 'recovery_seconds': 60, 'cooldown_seconds': 300,
        'min_sample_size': 1, 'allow_partial': 0,
        'conditions': [
            {'metric': 'agents_connected', 'operator': '>=', 'value': 1},
            {'metric': 'agents_available', 'operator': '<=', 'value': 0},
        ],
    }
    s_bad = snapshot('call')
    live_quality.process_snapshot(s_bad, clock=1000, rules=[rule], levels=levels(), persist=True)
    assert live_quality.incident_snapshot(active_only=True) == []
    live_quality.process_snapshot(s_bad, clock=1119, rules=[rule], levels=levels(), persist=True)
    assert live_quality.incident_snapshot(active_only=True) == []
    live_quality.process_snapshot(s_bad, clock=1120, rules=[rule], levels=levels(), persist=True)
    active = live_quality.incident_snapshot(active_only=True)
    assert len(active) == 1 and active[0]['status'] == 'NOUVEAU'
    first_id = active[0]['id']
    live_quality.process_snapshot(s_bad, clock=1130, rules=[rule], levels=levels(), persist=True)
    active = live_quality.incident_snapshot(active_only=True)
    assert len(active) == 1 and active[0]['id'] == first_id

    s_good = snapshot('ready')
    live_quality.process_snapshot(s_good, clock=1140, rules=[rule], levels=levels(), persist=True)
    assert len(live_quality.incident_snapshot(active_only=True)) == 1
    live_quality.process_snapshot(s_good, clock=1199, rules=[rule], levels=levels(), persist=True)
    assert len(live_quality.incident_snapshot(active_only=True)) == 1
    live_quality.process_snapshot(s_good, clock=1200, rules=[rule], levels=levels(), persist=True)
    assert live_quality.incident_snapshot(active_only=True) == []
    history = live_quality.incident_snapshot(active_only=False)
    assert history[0]['status'] == 'RETABLI'
    assert history[0]['cooldown_until'] == pytest.approx(1500)

    # Condition returns during cooldown: no new incident even if the minimum
    # duration would otherwise be satisfied.
    live_quality.process_snapshot(s_bad, clock=1210, rules=[rule], levels=levels(), persist=True)
    live_quality.process_snapshot(s_bad, clock=1400, rules=[rule], levels=levels(), persist=True)
    assert live_quality.incident_snapshot(active_only=True) == []
    live_quality.process_snapshot(s_bad, clock=1500, rules=[rule], levels=levels(), persist=True)
    assert len(live_quality.incident_snapshot(active_only=True)) == 1


def test_data_quality_is_separate_from_operational_color(lab):
    import live_quality
    q = live_quality.quality_summary(snapshot('ready', fresh=True), clock=2000)
    assert q['data_quality']['quality'] == 'reliable'
    assert q['operational_status']['label'] == 'NORMAL'
    stale = live_quality.quality_summary(snapshot('ready', fresh=False), clock=2001)
    assert stale['data_quality']['quality'] == 'partial'
    assert stale['operational_status']['label'] == 'NORMAL'

def test_unavailable_data_does_not_auto_recover_incident(lab):
    import live_quality
    rule = {
        'id': 9002, 'name': 'Incident gelé si data stale', 'enabled': 1,
        'scope_type': 'CAMPAIGN', 'target_key': 'CABINET A', 'match_mode': 'ALL', 'level_key': 'CRITIQUE',
        'min_duration_seconds': 0, 'recovery_seconds': 10, 'cooldown_seconds': 60,
        'min_sample_size': 1, 'allow_partial': 0,
        'conditions': [{'metric': 'agents_available', 'operator': '<=', 'value': 0}],
    }
    live_quality.process_snapshot(snapshot('call', fresh=True), clock=100, rules=[rule], levels=levels(), persist=True)
    assert len(live_quality.incident_snapshot(active_only=True)) == 1
    # The stale snapshot makes Live metrics partial. Because allow_partial is
    # false, the rule is not evaluable and must not be interpreted as recovery.
    live_quality.process_snapshot(snapshot('ready', fresh=False), clock=1000, rules=[rule], levels=levels(), persist=True)
    assert len(live_quality.incident_snapshot(active_only=True)) == 1

def test_deleting_all_rules_does_not_reseed_defaults(lab):
    import live_quality
    live_quality.ensure_admin_schema()
    for row in list(live_quality.load_rules(include_disabled=True)):
        live_quality.delete_rule(row['id'])
    assert live_quality.load_rules(include_disabled=True) == []
    # Any later schema/config read must preserve the administrator's choice.
    live_quality.ensure_admin_schema()
    assert live_quality.config_snapshot()['rules'] == []
