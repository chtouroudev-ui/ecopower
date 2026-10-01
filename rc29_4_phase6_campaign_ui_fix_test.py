from pathlib import Path
from unittest.mock import patch

import pytest

from supervision_utils import kind
import live_quality

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
CSS=(ROOT/'static'/'collection.css').read_text(encoding='utf-8')
STORE=(ROOT/'collection_store.py').read_text(encoding='utf-8')


def _scope(active=None, campaign_to_files=None):
    return {
        'groups':[{'id':'G1','name':'MED02','service_name':'MEDICAL','line_ids':['505'],'member_agent_ids':list(active or []),'member_count':len(active or [])}],
        'queues':[{'line_id':'505','display_name':'FILE 505'}],
        'campaigns':{'C1':{'campaign_id':'C1','campaign_name':'DOCVISION'}},
        'campaign_to_files':campaign_to_files or {},
        'agents_by_line_state':{'active':{'505':list(active or [])}},
    }


def _snapshot(*, received=815, handled=641, abandoned=153, exclusions=(2,8,12), kind_name='ready'):
    return {
        'catalog_reference':True,
        'health':{'fresh':True,'last_response_age':1},
        'scope':{'group_id':'G1'},
        'live_queue_catalog':{'505':'DOCVISION'},
        'agents':[{
            'agent':'1001','kind':kind_name,'line_id':'505','campaign':'DOCVISION','campaign_name':'DOCVISION','campaign_id':'C1',
            'current_call':None,
        }],
        'agent_roster':[{'agent':'1001','name':'Agent 1001'}],
        'native_queue_metrics':{'by_line':{'505':{
            'UpQuR':{'calls_waiting':4,'calls_in_progress':5,'agents_available_on_queue':1},
            'UpQuH':{'received_today':received,'handled_today':handled,'abandoned_today':abandoned,
                     'qos_exclusion_1':exclusions[0],'qos_exclusion_2':exclusions[1],'qos_exclusion_3':exclusions[2]},
        }}},
        'kpi':{},
    }


def test_ready_and_available_english_states_are_available_not_other():
    assert kind('Ready')=='ready'
    assert kind('Available')=='ready'
    assert kind('Waiting')=='ready'
    assert kind('Mise en attente')=='hold'


def test_exact_initqueue_label_repairs_campaign_mapping_and_keeps_native_kpis():
    snap=_snapshot()
    snap['agents'][0].update(campaign='',campaign_name='',campaign_id='')
    with patch('quality_scope.load_quality_file_scope',return_value=_scope(active=[])):
        rows=live_quality.build_scopes(snap)
    c=next(x for x in rows if x['scope_type']=='CAMPAIGN' and x['scope_key']=='C1')
    assert c['line_ids']==['505']
    assert c['catalog_line_ids']==['505']
    assert 'live_queue_catalog_exact' in c['coverage_basis']
    # Observed Live evidence must keep the agent in the campaign even if an imported ACTIVE assignment is missing.
    assert c['observed_agent_count']==1
    assert c['metrics']['agents_available']['value']==1
    assert c['native_calls']['received_today']==815
    assert c['native_calls']['handled_today']==641
    assert c['native_calls']['abandoned_today']==153
    assert c['native_calls']['qos_denominator']==793
    assert c['native_calls']['qos_today']==pytest.approx(641/793*100)
    assert c['native_calls']['agents_available_on_queue']==1


def test_qos_is_unavailable_when_canonical_denominator_is_not_positive():
    with patch('quality_scope.load_quality_file_scope',return_value=_scope(active=['1001'],campaign_to_files={'C1':[{'line_id':'505'}]})):
        rows=live_quality.build_scopes(_snapshot(received=10,handled=4,abandoned=2,exclusions=(5,5,1)))
    c=next(x for x in rows if x['scope_type']=='CAMPAIGN' and x['scope_key']=='C1')
    assert c['native_calls']['qos_denominator']==-1
    assert c['native_calls']['qos_today'] is None


def test_campaign_render_receives_queue_diagnostics_without_out_of_scope_latestpayload():
    assert "function liveScopeRowsHtml(center,type,query='',queueDiagnostics=null)" in JS
    assert 'const qdiag=queueDiagnostics||{};' in JS
    scope_fn=JS[JS.index('function liveScopeRowsHtml'):JS.index('function liveCertifiedQualityBody')]
    assert 'latestPayload?.native_queue_metrics' not in scope_fn
    assert 'latestPayload.native_queue_metrics||{}' in JS


def test_campaigns_scroll_all_rows_and_agent_duration_labels_are_unambiguous():
    assert 'campagne(s) · défilement vertical' in JS
    assert "const stateDurationLabel=String(r.kind||'')==='hold'?'HOLD':'État';" in JS
    assert "'callDuration','Appel total','duration'" in JS
    assert 'live-duration-label' in JS
    assert '[data-layout="agents"]>.live-scope-panel' in CSS
    assert '[data-layout="scopes"]>.live-agent-panel' in CSS


def test_snapshot_exposes_only_today_refreshed_initqueue_catalog_contract():
    assert 'live_queue_catalog={}' in STORE
    assert "entity_type='queue'" in STORE
    assert "session_id IN ({marks})" in STORE
    assert 'live_queue_catalog=live_queue_catalog' in STORE
