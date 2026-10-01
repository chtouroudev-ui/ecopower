"""Phase 3 regression tests for the Live Quality cockpit.

Run: python -m pytest live_quality_phase3_test.py -q
"""
from __future__ import annotations

from live_quality_phase2_test import lab, snapshot, levels


def _rule(scope_type='CAMPAIGN', target_key='', rid=10):
    return {
        'id': rid, 'name': 'Couverture insuffisante', 'enabled': 1,
        'scope_type': scope_type, 'target_key': target_key,
        'match_mode': 'ALL', 'level_key': 'CRITIQUE',
        'min_duration_seconds': 0, 'recovery_seconds': 30,
        'cooldown_seconds': 300, 'min_sample_size': 1, 'allow_partial': 0,
        'conditions': [
            {'metric': 'agents_connected', 'operator': '>=', 'value': 1},
            {'metric': 'agents_available', 'operator': '<=', 'value': 0},
        ],
    }


def test_cockpit_never_reports_normal_when_live_is_stale(lab):
    import live_quality
    data = snapshot(kind='call', fresh=False)
    center = live_quality.quality_center(data, clock=1000, levels=levels(), rules=[_rule()], incidents=[])
    assert center['data_quality']['quality'] == 'partial'
    assert center['status']['level_key'] == 'COLLECTE_INTERROMPUE'
    assert center['status']['label'] == 'COLLECTE INTERROMPUE'


def test_cockpit_is_indeterminate_when_no_rule_is_active(lab):
    import live_quality
    data = snapshot(kind='ready', fresh=True)
    center = live_quality.quality_center(data, clock=1000, levels=levels(), rules=[], incidents=[])
    assert center['status']['level_key'] == 'INDETERMINE'
    assert center['active_rule_count'] == 0


def test_campaign_and_group_remain_distinct_scopes(lab):
    import live_quality
    center = live_quality.quality_center(snapshot(kind='call', campaign='CABINET A'), clock=1000,
                                         levels=levels(), rules=[_rule()], incidents=[])
    campaigns = [x for x in center['scopes'] if x['scope_type'] == 'CAMPAIGN']
    groups = [x for x in center['scopes'] if x['scope_type'] == 'GROUP']
    assert [x['scope_label'] for x in campaigns] == ['CABINET A']
    assert [x['scope_label'] for x in groups] == ['MED02']
    assert campaigns[0]['monitored'] is True
    assert groups[0]['monitored'] is False


def test_scope_status_uses_configured_incident_color_and_reasons(lab):
    import live_quality
    incident = {
        'id': 'inc-1', 'rule_id': 10, 'rule_name': 'Couverture insuffisante',
        'scope_type': 'CAMPAIGN', 'scope_key': 'CABINET A', 'scope_label': 'CABINET A',
        'level_key': 'CRITIQUE', 'level_label': 'CRITIQUE', 'level_rank': 400, 'color': '#B42318',
        'status': 'NOUVEAU', 'active': 1, 'first_seen': 900.0, 'last_seen': 1000.0,
        'reasons': [{'metric': 'agents_available', 'label': 'Agents disponibles', 'operator': '<=',
                     'threshold': 0, 'value': 0, 'unit': '', 'quality': 'reliable', 'source': 'Hermes Live',
                     'usable': True, 'passed': True}],
        'metrics': {},
    }
    center = live_quality.quality_center(snapshot(kind='call', campaign='CABINET A'), clock=1000,
                                         levels=levels(), rules=[_rule()], incidents=[incident])
    campaign = next(x for x in center['scopes'] if x['scope_type'] == 'CAMPAIGN')
    assert campaign['status']['level_key'] == 'CRITIQUE'
    assert campaign['status']['color'] == '#B42318'
    assert center['attention'][0]['duration_seconds'] == 100.0
    assert center['attention'][0]['matched_reasons'][0]['metric'] == 'agents_available'


def test_uncertified_service_quality_metrics_remain_explicitly_unavailable(lab):
    import live_quality
    center = live_quality.quality_center(snapshot(kind='call'), clock=1000,
                                         levels=levels(), rules=[_rule()], incidents=[])
    for key in ('waiting_now', 'oldest_waiting_seconds', 'median_wait_seconds', 'p90_wait_seconds', 'abandon_rate', 'qos'):
        metric = center['global_metrics'][key]
        assert metric['value'] is None
        assert metric['quality'] == 'unavailable'
        assert metric['reason'] == 'semantics_not_certified'
