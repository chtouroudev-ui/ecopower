"""Phase 6 regression tests for Live incident lifecycle and actions."""
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


def levels():
    return [
        {'level_key': 'CRITIQUE', 'label': 'CRITIQUE', 'rank': 400, 'color': '#B42318', 'enabled': 1, 'is_fallback': 0},
        {'level_key': 'NORMAL', 'label': 'NORMAL', 'rank': 100, 'color': '#24634A', 'enabled': 1, 'is_fallback': 1},
    ]


def rule():
    return {
        'id': 9601, 'name': 'Aucun disponible Phase 6', 'enabled': 1,
        'scope_type': 'CAMPAIGN', 'target_key': 'CABINET A', 'match_mode': 'ALL', 'level_key': 'CRITIQUE',
        'min_duration_seconds': 0, 'recovery_seconds': 0, 'cooldown_seconds': 30,
        'min_sample_size': 1, 'allow_partial': 0,
        'conditions': [
            {'metric': 'agents_connected', 'operator': '>=', 'value': 1},
            {'metric': 'agents_available', 'operator': '<=', 'value': 0},
        ],
    }


def snapshot(kind='call', available=None):
    if available is None:
        available = 1 if kind == 'ready' else 0
    state = {'call': 'Inbound call', 'ready': 'Pret'}[kind]
    return {
        'health': {'fresh': True, 'active': True, 'last_response_age': 2},
        'kpi': {'agents_known': 1, 'connected': 1, 'in_call': 1 if kind == 'call' else 0,
                'available': available, 'current_calls': 1 if kind == 'call' else 0, 'calls_waiting': None},
        'agents': [{
            'agent': '1001', 'name': 'Agent 1001', 'state': state, 'kind': kind,
            'line_id': '571', 'campaign': 'CABINET A', 'groups': [], 'service_names': ['MEDICAL'],
            'state_age_seconds': 45, 'current_call': {'campaign': 'CABINET A', 'line_id': '571'} if kind == 'call' else None,
        }],
    }


def open_incident(live_quality, clock=100):
    live_quality.process_snapshot(snapshot('call'), clock=clock, rules=[rule()], levels=levels(), persist=True)
    rows = live_quality.incident_snapshot(active_only=True)
    assert len(rows) == 1
    return rows[0]['id']


def test_manual_lifecycle_requires_action_text_and_keeps_auto_recovery(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    detail = live_quality.incident_action(incident_id, action='transition', target_status='VU', actor='superviseur', comment='Pris en charge', clock=110)
    assert detail['incident']['status'] == 'VU'
    detail = live_quality.incident_action(incident_id, action='transition', target_status='EN_INVESTIGATION', actor='superviseur', comment='Analyse de la file', clock=120)
    assert detail['incident']['status'] == 'EN_INVESTIGATION'
    with pytest.raises(ValueError):
        live_quality.incident_action(incident_id, action='transition', target_status='ACTION_EN_COURS', actor='superviseur', clock=130)
    detail = live_quality.incident_action(incident_id, action='transition', target_status='ACTION_EN_COURS', actor='superviseur', action_text='Agent ajoute sur la file 571', comment='Renfort temporaire', clock=140)
    assert detail['incident']['status'] == 'ACTION_EN_COURS'
    assert any(e['event_type'] == 'ACTION_DEMARREE' for e in detail['events'])


def test_active_incident_cannot_be_closed_manually(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    with pytest.raises(ValueError):
        live_quality.incident_action(incident_id, action='transition', target_status='CLOTURE', actor='superviseur', clock=110)


def test_recovery_after_action_builds_non_causal_before_after(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    live_quality.incident_action(incident_id, action='transition', target_status='ACTION_EN_COURS', actor='superviseur', action_text='Agent ajoute sur la file 571', clock=120)
    live_quality.process_snapshot(snapshot('ready'), clock=180, rules=[rule()], levels=levels(), persist=True)
    detail = live_quality.incident_detail(incident_id)
    assert detail['incident']['status'] == 'RETABLI'
    assert detail['incident']['active'] == 0
    compare = detail['before_after']
    assert compare['recovered_after_action'] is True
    assert compare['action']['text'] == 'Agent ajoute sur la file 571'
    assert compare['observation'] == "Amélioration observée après l’action."
    assert 'ne prouve pas' in compare['causality_note']
    available = next(x for x in compare['changes'] if x['metric'] == 'agents_available')
    assert available['before'] == 0
    assert available['after'] == 1


def test_comment_is_audited_without_changing_status(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    detail = live_quality.incident_action(incident_id, action='comment', actor='superviseur', comment='Appel du responsable en cours', clock=115)
    assert detail['incident']['status'] == 'NOUVEAU'
    event = next(e for e in detail['events'] if e['event_type'] == 'COMMENTAIRE')
    assert event['actor'] == 'superviseur'
    assert event['comment'] == 'Appel du responsable en cours'


def test_recovered_incident_can_be_closed_and_history_is_preserved(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    live_quality.process_snapshot(snapshot('ready'), clock=150, rules=[rule()], levels=levels(), persist=True)
    detail = live_quality.incident_action(incident_id, action='transition', target_status='CLOTURE', actor='superviseur', comment='Controle termine', clock=170)
    assert detail['incident']['status'] == 'CLOTURE'
    assert detail['incident']['closed_at'] == 170
    assert [e['event_type'] for e in detail['events']] == ['OUVERTURE', 'RETOUR_NORMAL_AUTOMATIQUE', 'CLOTURE_MANUELLE']


def test_detail_exposes_sequential_lifecycle_and_allowed_transitions(lab):
    import live_quality
    incident_id = open_incident(live_quality)
    detail = live_quality.incident_detail(incident_id)
    assert detail['allowed_transitions'] == ['VU', 'EN_INVESTIGATION', 'ACTION_EN_COURS']
    labels = [x['label'] for x in detail['lifecycle']]
    assert labels == ['NOUVEAU', 'VU', 'EN INVESTIGATION', 'ACTION EN COURS', 'RÉTABLI', 'CLÔTURÉ']
