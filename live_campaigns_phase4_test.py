import unittest
from unittest.mock import patch

import live_campaigns
from routes_collection import CollectionRoutesMixin


SCOPE = {
    'campaigns': {
        'C1': {'campaign_id': 'C1', 'campaign_name': 'CABINET A'},
        'C2': {'campaign_id': 'C2', 'campaign_name': 'CABINET B'},
    },
    'queues': [
        {'line_id': 571, 'display_name': 'File 571'},
        {'line_id': 588, 'display_name': 'File 588'},
        {'line_id': 505, 'display_name': 'File 505'},
    ],
    'campaign_to_files': {
        'C1': [
            {'line_id': 571, 'line_name': 'File 571'},
            {'line_id': 588, 'line_name': 'File 588'},
            {'line_id': 505, 'line_name': 'File 505'},
        ],
        'C2': [{'line_id': 588, 'line_name': 'File 588'}],
    },
    'agent_files': {
        '1001': [571, 588, 505],
        '1002': [571],
        '1003': [588],
    },
    'configured_agents_by_line': {
        '571': ['1001', '1002'],
        '588': ['1001', '1003'],
        '505': ['1001'],
    },
    'groups': [
        {'id': 'G1', 'name': 'MED02', 'service_name': 'MEDICAL', 'line_ids': [571, 588, 505]},
        {'id': 'G2', 'name': 'IMG02', 'service_name': 'IMAGERIE', 'line_ids': [900]},
    ],
}


def metric_row(cid='C1', label='CABINET A', received=100, handled=90, abandoned=8, qos=92.0, p90=120.0):
    return {
        'campaign_id': cid, 'campaign_label': label, 'identity_quality': 'configured_id',
        'received': received, 'handled': handled, 'treated_agent': handled, 'abandoned': abandoned,
        'abandon_rate': (100 * abandoned / received if received else None), 'qos': qos,
        'wait_average_seconds': 45.0, 'wait_median_seconds': 30.0, 'wait_p90_seconds': p90,
        'wait_sample_size': 80, 'low_volume_flag': received < 20, 'agents_treating': 3,
    }


class Phase4CampaignTests(unittest.TestCase):
    def payload(self):
        history = {
            'day': '2026-09-25',
            'last_15m': {'source': 'Stats.INBOUND importé', 'quality': 'partial', 'reason': 'current_day_import_is_not_live', 'campaigns': [metric_row(received=25, handled=22, abandoned=2, qos=90.0, p90=140)]},
            'today': {'source': 'Stats.INBOUND importé', 'quality': 'partial', 'reason': 'current_day_import_is_not_live', 'campaigns': [metric_row(received=100, handled=90, abandoned=8, qos=92.0, p90=120)]},
            'reference': {'source': 'Stats.INBOUND importé', 'quality': 'reliable', 'reason': '', 'days': ['2026-09-18','2026-09-11'], 'label': 'médiane même tranche', 'campaigns': [metric_row(received=80, handled=74, abandoned=4, qos=95.0, p90=90)]},
            'queue_distribution': {
                'source': 'ODCalls.FirstQueue', 'quality': 'partial',
                'last_15m': {'C1': {'total': 25, 'files': [
                    {'file_id': '571', 'file_label': 'File 571', 'received': 18, 'treated': 16, 'abandoned': 1, 'agents_treating': 2, 'share_percent': 72.0},
                    {'file_id': '588', 'file_label': 'File 588', 'received': 5, 'treated': 4, 'abandoned': 1, 'agents_treating': 1, 'share_percent': 20.0},
                    {'file_id': '505', 'file_label': 'File 505', 'received': 2, 'treated': 2, 'abandoned': 0, 'agents_treating': 1, 'share_percent': 8.0},
                ]}},
                'today': {},
            },
            'query_plan': {'bounded': True, 'independent_of_campaign_count': True},
        }
        snapshot = {
            'health': {'fresh': True},
            'agents': [
                {'agent': '1001', 'kind': 'call', 'line_id': '571', 'campaign': 'CABINET A', 'current_call': {'campaign': 'CABINET A', 'line_id': '571'}},
                {'agent': '1002', 'kind': 'ready', 'line_id': '571', 'campaign': 'CABINET A', 'current_call': None},
                {'agent': '1003', 'kind': 'wrap', 'line_id': '588', 'campaign': 'CABINET B', 'current_call': None},
            ],
            'quality': {'center': {'data_quality': {'quality': 'reliable'}, 'scopes': [
                {'scope_type': 'CAMPAIGN', 'scope_key': 'CABINET A', 'scope_label': 'CABINET A', 'incident_count': 1,
                 'status': {'level_key': 'DEGRADE', 'label': 'DÉGRADÉ', 'rank': 300, 'color': '#B54708'}},
                {'scope_type': 'QUEUE', 'scope_key': '571', 'scope_label': '571', 'incident_count': 1,
                 'status': {'level_key': 'DEGRADE', 'label': 'DÉGRADÉ', 'rank': 300, 'color': '#B54708'}},
            ]}},
        }
        return snapshot, history

    @patch('live_campaigns.load_quality_file_scope', return_value=SCOPE)
    def test_campaign_group_service_and_unique_active_agents(self, _scope):
        snapshot, history = self.payload()
        out = live_campaigns.combine(snapshot, history, clock=1_800_000_000)
        c = next(x for x in out['campaigns'] if x['campaign_id'] == 'C1')
        self.assertEqual(c['services'], ['MEDICAL'])
        self.assertEqual([g['name'] for g in c['groups']], ['MED02'])
        self.assertEqual(c['live_now']['agents']['active_on_queues']['value'], 3)
        self.assertEqual(c['live_now']['agents']['configured']['value'], 3)

    @patch('live_campaigns.load_quality_file_scope', return_value=SCOPE)
    def test_72_percent_concentration_is_explicit(self, _scope):
        snapshot, history = self.payload()
        c = live_campaigns.combine(snapshot, history, clock=1_800_000_000)['campaigns'][0]
        self.assertEqual(c['queues']['top_share_percent'], 72.0)
        self.assertEqual(c['queues']['top_files'][0]['file_id'], '571')

    @patch('live_campaigns.load_quality_file_scope', return_value=SCOPE)
    def test_waiting_live_never_becomes_zero(self, _scope):
        snapshot, history = self.payload()
        c = live_campaigns.combine(snapshot, history, clock=1_800_000_000)['campaigns'][0]
        waiting = c['live_now']['calls']['waiting_now']
        self.assertIsNone(waiting['value'])
        self.assertEqual(waiting['quality'], 'unavailable')
        self.assertEqual(waiting['reason'], 'semantics_not_certified')

    @patch('live_campaigns.load_quality_file_scope', return_value=SCOPE)
    def test_windows_are_separate_and_trend_uses_reference(self, _scope):
        snapshot, history = self.payload()
        c = live_campaigns.combine(snapshot, history, clock=1_800_000_000)['campaigns'][0]
        self.assertEqual(c['last_15m']['calls']['received']['value'], 25)
        self.assertEqual(c['today']['calls']['received']['value'], 100)
        self.assertEqual(c['reference']['calls']['received']['value'], 80)
        self.assertAlmostEqual(c['trend']['volume_change_vs_reference'], 25.0)

    @patch('live_campaigns.load_quality_file_scope', return_value=SCOPE)
    def test_status_remains_explainable_live_rule_status(self, _scope):
        snapshot, history = self.payload()
        c = live_campaigns.combine(snapshot, history, clock=1_800_000_000)['campaigns'][0]
        self.assertEqual(c['status']['level_key'], 'DEGRADE')
        self.assertEqual(c['incident_count'], 1)
        self.assertEqual(c['queues']['count_under_tension'], 1)


    @patch('routes_collection.store.live_supervision_snapshot', return_value={'health': {'fresh': True}, 'agents': [], 'quality': {'center': {'data_quality': {'quality': 'reliable'}, 'scopes': []}}})
    @patch('analytics_rpc.delegated_view_remote', side_effect=RuntimeError('analytics down'))
    @patch('service_mode.external_services_enabled', return_value=True)
    def test_live_view_survives_analytics_failure(self, _external, _remote, _snapshot):
        class Fake(CollectionRoutesMixin):
            def send_json(self, payload, status=200):
                return status, payload
        status, payload = Fake().api_live_campaigns({}, include_history=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload['windows']['today']['quality'], 'unavailable')
        self.assertEqual(payload['windows']['today']['reason'], 'analytics_unavailable')

    def test_empty_history_does_not_invent_zero(self):
        h = live_campaigns.empty_history('2026-09-25')
        self.assertEqual(h['today']['quality'], 'unavailable')
        self.assertEqual(h['today']['campaigns'], [])
        self.assertTrue(h['query_plan']['bounded'])


if __name__ == '__main__':
    unittest.main()
