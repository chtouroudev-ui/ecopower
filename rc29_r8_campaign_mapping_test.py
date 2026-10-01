from unittest.mock import patch
import live_quality

SCOPE={
    'groups':[{'id':'G1','name':'MED02','service_name':'MEDICAL','line_ids':['505'],'member_agent_ids':['1001'],'member_count':1}],
    'queues':[{'line_id':'505','display_name':'FILE 505'}],
    'campaigns':{'C1':{'campaign_id':'C1','campaign_name':'DOCVISION'}},
    'campaign_to_files':{},
    'agents_by_line_state':{'active':{'505':['1001']}},
}

def test_campaign_recovers_line_from_observed_live_campaign_pair():
    snap={
        'catalog_reference':True,
        'health':{'fresh':True},
        'scope':{'group_id':'G1'},
        'agents':[{
            'agent':'1001','kind':'call','line_id':'505','campaign':'DOCVISION','campaign_name':'DOCVISION','campaign_id':'C1',
            'current_call':{'line_id':'505','campaign':'DOCVISION','campaign_name':'DOCVISION','campaign_id':'C1'}
        }],
        'agent_roster':[{'agent':'1001','name':'Agent 1001'}],
        'native_queue_metrics':{'by_line':{'505':{
            'UpQuR':{'calls_waiting':4,'calls_in_progress':5},
            'UpQuH':{'received_today':815,'handled_today':641,'abandoned_today':153,'qos_exclusion_1':2,'qos_exclusion_2':8,'qos_exclusion_3':12},
        }}},
        'kpi':{},
    }
    with patch('quality_scope.load_quality_file_scope',return_value=SCOPE):
        rows=live_quality.build_scopes(snap)
    c=next(x for x in rows if x['scope_type']=='CAMPAIGN' and x['scope_key']=='C1')
    assert c['line_ids']==['505']
    assert c['native_calls']['calls_waiting']==4
    assert c['native_calls']['calls_in_progress']==5
    assert c['native_calls']['received_today']==815
    assert c['native_calls']['handled_today']==641
    assert c['native_calls']['abandoned_today']==153
    assert c['native_calls']['qos_today'] is not None
    assert 'live_observed_pair' in c['coverage_basis']


def test_view_selector_is_top_only():
    src=open('static/live-views.js',encoding='utf-8').read()
    assert 'live-layout-picker-inline' in src
    assert 'live-layout-bottom' not in src
    assert 'RC29.4 · Live Native R10' in src
