from pathlib import Path
from unittest.mock import patch

import pytest
import live_quality

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
CSS=(ROOT/'static'/'collection.css').read_text(encoding='utf-8')


def _scope():
    return {
        'groups':[{'id':'G1','name':'MED02','service_name':'MEDICAL','line_ids':['505','506'],'member_agent_ids':['1001','1002'],'member_count':2}],
        'queues':[{'line_id':'505','display_name':'Q505'},{'line_id':'506','display_name':'Q506'}],
        'campaigns':{
            'C1':{'campaign_id':'C1','campaign_name':'DOC1'},
            'C2':{'campaign_id':'C2','campaign_name':'DOC2'},
        },
        'campaign_to_files':{'C1':[{'line_id':'505'}],'C2':[{'line_id':'506'}]},
        'agents_by_line_state':{'active':{'505':['1001'],'506':['1002']}},
    }


def _snapshot(partial=False):
    queues={
        '505':{
            'UpQuR':{'calls_waiting':1,'calls_in_progress':2,'agents_available_on_queue':1},
            'UpQuH':{'received_today':100,'handled_today':80,'abandoned_today':15,
                     'qos_exclusion_1':1,'qos_exclusion_2':2,'qos_exclusion_3':2},
        },
        '506':{
            'UpQuR':{'calls_waiting':0,'calls_in_progress':0,'agents_available_on_queue':0},
            'UpQuH':{'received_today':50,'handled_today':40,'abandoned_today':8,
                     'qos_exclusion_1':1,'qos_exclusion_2':1,'qos_exclusion_3':0},
        },
    }
    if partial:
        queues['506'].pop('UpQuH')
    return {
        'catalog_reference':True,
        'health':{'fresh':True,'last_response_age':1},
        'scope':{'group_id':'G1'},
        'agents':[
            {'agent':'1001','kind':'ready','line_id':'505','campaign_id':'C1','campaign_name':'DOC1','campaign':'DOC1','current_call':None},
            {'agent':'1002','kind':'offline','line_id':'506','campaign_id':'C2','campaign_name':'DOC2','campaign':'DOC2','current_call':None},
        ],
        'agent_roster':[{'agent':'1001'},{'agent':'1002'}],
        'native_queue_metrics':{'by_line':queues},
        'kpi':{'connected':1,'disconnected':1,'available':1,'in_call':0,'agents_known':2,'current_calls':0},
    }


def _center(partial=False):
    with patch('quality_scope.load_quality_file_scope',return_value=_scope()):
        return live_quality.quality_center(_snapshot(partial=partial),levels=[],rules=[],incidents=[])


def test_native_queue_kpis_survive_quality_center_serialization_for_campaigns():
    center=_center()
    c1=next(x for x in center['scopes'] if x['scope_type']=='CAMPAIGN' and x['scope_key']=='C1')
    assert c1['line_ids']==['505']
    assert c1['native_calls']['received_today']==100
    assert c1['native_calls']['handled_today']==80
    assert c1['native_calls']['abandoned_today']==15
    assert c1['native_calls']['qos_today']==pytest.approx(80/95*100)
    assert c1['native_calls']['daily_coverage']==1


def test_group_and_global_daily_kpis_aggregate_unique_configured_lines():
    center=_center()
    group=next(x for x in center['scopes'] if x['scope_type']=='GROUP' and x['scope_key']=='G1')
    assert group['line_ids']==['505','506']
    assert group['native_calls']['received_today']==150
    assert group['native_calls']['handled_today']==120
    assert group['native_calls']['abandoned_today']==23
    assert group['native_calls']['qos_denominator']==143
    assert group['native_calls']['qos_today']==pytest.approx(120/143*100)
    assert center['global_native_calls']['received_today']==150
    assert center['global_native_calls']['daily_coverage']==2
    assert center['global_native_calls']['line_count']==2


def test_partial_upquh_is_marked_partial_and_never_invents_missing_zero():
    center=_center(partial=True)
    group=next(x for x in center['scopes'] if x['scope_type']=='GROUP' and x['scope_key']=='G1')
    native=group['native_calls']
    assert native['line_count']==2
    assert native['daily_coverage']==1
    assert native['daily_quality']=='partial'
    assert native['received_today']==100
    c2=next(x for x in center['scopes'] if x['scope_type']=='CAMPAIGN' and x['scope_key']=='C2')
    assert c2['native_calls']['daily_coverage']==0
    assert 'received_today' not in c2['native_calls']


def test_live_rail_has_requested_operational_kpis_and_no_details_drawer():
    assert '<span>Connectés</span>' in JS
    assert '<span>Disponibles</span>' in JS
    assert '<span>Déconnectés</span>' in JS
    assert '<span>En appel</span>' in JS
    assert '<span>Reçus</span>' in JS
    assert '<span>Traités</span>' in JS
    assert '<span>Abandonnés</span>' in JS
    assert '<span>QoS</span>' in JS
    rail=JS[JS.index('<aside class="live-supervision-rail"'):JS.index('<div id="live-ops-board"')]
    assert 'live-detail-drawer' not in rail
    assert 'Agents référencés' not in JS[JS.index("const disconnected="):JS.index("const liveMetricCards=")]
    assert 'États Live observés' not in JS[JS.index("const disconnected="):JS.index("const liveMetricCards=")]
    assert 'Appels observés' not in JS[JS.index("const disconnected="):JS.index("const liveMetricCards=")]


def test_disconnected_quick_filter_and_campaign_coverage_are_visible():
    assert "if(kind==='offline')return 'offline'" in JS
    assert "chip('offline','Déconnectés',c.offline)" in JS
    assert 'UpQuH ${Number(native.daily_coverage||0)}/${Number(native.line_count||0)}' in JS
    assert 'live-hermes-coverage' in CSS
    assert "rc29SortHeader(tableKey,'received','Reçus','number')" in JS
