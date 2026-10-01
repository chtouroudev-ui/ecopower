from unittest.mock import patch


def test_explicit_hold_is_distinct_from_agent_waiting():
    from supervision_utils import kind
    assert kind('Mise en attente') == 'hold'
    assert kind('On Hold') == 'hold'
    assert kind('HOLD') == 'hold'
    assert kind('Waiting') == 'ready'
    assert kind('Disponible') == 'ready'


def test_call_hold_duration_requires_explicit_timeline_state():
    import collection_store
    p={'timeline':[{'stamp':100,'state':'Inbound call'},{'stamp':120,'state':'Mise en attente'},{'stamp':150,'state':'Inbound call'}]}
    h=collection_store._explicit_hold_observation(p,160)
    assert h['quality']=='observed_explicit_state'
    assert h['seconds']==30.0
    assert h['segments']==1
    missing=collection_store._explicit_hold_observation({'timeline':[{'stamp':100,'state':'Inbound call'}]},160)
    assert missing['seconds'] is None
    assert missing['quality']=='unavailable'


def test_hold_counts_as_in_call_but_is_also_visible_separately():
    import live_quality
    metrics=live_quality._scope_metrics([
        {'kind':'hold','state_age_seconds':42,'current_call':{'reference':'x'}},
        {'kind':'ready','state_age_seconds':10},
    ], {'fresh':True,'last_response_age':1})
    assert metrics['agents_in_call']['value']==1
    assert metrics['agents_on_hold']['value']==1
    assert metrics['max_hold_seconds']['value']==42.0
    assert metrics['hold_percent']['value']==50.0


def test_parser_keeps_explicit_hold_inside_call_segment():
    text=open('collection_parser.py',encoding='utf-8').read()
    assert "is_call = kind(state) in ('call', 'hold')" in text


def test_group_projection_counts_hold_as_active_call():
    import access_control as ac
    user={'id':7,'username':'sup','role':'viewer','group_scope':{'mode':'SELECTED','allowed_group_ids':['10'],'default_group_id':'10','filter_locked':True},'interface_permissions':{'live_supervision':1}}
    snap={'health':{'fresh':True},'agents':[{'agent':'1001','kind':'hold','groups':[{'id':'10','name':'G10'}],'current_call':{'reference':'x'}}],'quality':{}}
    with patch('analysis_groups.catalog',return_value=[{'id':'10','name':'G10','service_name':'MEDICAL'}]), patch('live_quality.incident_snapshot',return_value=[]), patch('live_quality.quality_center',return_value={'engine':{},'status':{},'data_quality':{}}):
        out=ac.filter_live_snapshot(user,snap,'10')
    assert out['kpi']['in_call']==1
    assert out['kpi']['on_hold']==1


def test_live_ui_exposes_operational_agent_and_campaign_detail():
    live=open('static/live-views.js',encoding='utf-8').read()
    assert 'Temps non disponible' in live
    assert 'Appels Live aujourd' in live
    assert "hold:'Mise en attente'" in live
    assert 'Mise en attente obs.' in live
    assert 'liveCallHold' in live
    assert 'liveAgentTimeBreakdown' in live
    assert 'observed_today' in live
