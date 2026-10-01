from unittest.mock import patch

import access_control as ac


def user(scope, interfaces=None):
    return {
        'id': 7, 'username': 'sup', 'role': 'viewer',
        'group_scope': scope,
        'interface_permissions': interfaces or {'live_supervision': 1},
    }


def test_locked_scope_forces_default_and_denies_escape():
    u=user({'mode':'SELECTED','allowed_group_ids':['10','11'],'default_group_id':'10','filter_locked':True})
    assert ac.effective_group_ids(u)=={'10'}
    assert ac.scope_query(u, {'group':['11']})['group']==['10']
    assert ac.scope_multi_query(u, {'group':['11','12']})['group']==['10']


def test_selected_scope_rejects_unauthorized_group():
    u=user({'mode':'SELECTED','allowed_group_ids':['10','11'],'default_group_id':'10','filter_locked':False})
    assert ac.scope_query(u,{})['group']==['10']
    try:
        ac.scope_query(u,{'group':['99']})
    except ac.ScopeDenied:
        pass
    else:
        raise AssertionError('unauthorized group must be rejected')


def test_live_snapshot_is_projected_to_selected_group_and_exposes_selector():
    u=user({'mode':'SELECTED','allowed_group_ids':['10','11'],'default_group_id':'10','filter_locked':False})
    snap={
        'health':{'fresh':True},
        'agents':[
            {'agent':'1001','name':'A','kind':'ready','groups':[{'id':'10','name':'G10'}]},
            {'agent':'1002','name':'B','kind':'call','groups':[{'id':'11','name':'G11'}],'current_call':{'reference':'x'}},
        ],
        'quality':{},
    }
    with patch('analysis_groups.catalog', return_value=[
        {'id':'10','name':'G10','service_name':'MEDICAL'},
        {'id':'11','name':'G11','service_name':'MEDICAL'},
        {'id':'12','name':'G12','service_name':'IMAGERIE'},
    ]), patch('live_quality.incident_snapshot', return_value=[]), patch('live_quality.quality_center', return_value={
        'engine':{'checked_at':1},'last_operational_status':{'label':'NORMAL'},'status':{'label':'NORMAL'},'data_quality':{},
    }):
        out=ac.filter_live_snapshot(u,snap,'11')
    assert [x['agent'] for x in out['agents']]==['1002']
    assert out['kpi']['agents_known']==1
    assert out['kpi']['in_call']==1
    assert out['access_scope']['selected_group_id']=='11'
    assert {x['id'] for x in out['access_scope']['groups']}=={'10','11'}


def test_shared_campaign_hides_cross_group_historical_kpis():
    u=user({'mode':'SELECTED','allowed_group_ids':['10'],'default_group_id':'10','filter_locked':True})
    payload={'groups':[{'id':'10','name':'G10'},{'id':'11','name':'G11'}],'services':[], 'campaigns':[{
        'campaign_id':'C1','groups':[{'id':'10','name':'G10'},{'id':'11','name':'G11'}],
        'today':{'quality':'reliable','calls':{'received':{'value':100}}},
        'last_15m':{'quality':'reliable','calls':{'received':{'value':5}}},
        'reference':{'quality':'reliable','calls':{'received':{'value':90}}},
        'trend':{'volume_change_vs_reference':11},'queues':{'configured':[],'observed_live':[],'top_files':[]},
    }]}
    with patch.object(ac,'_selected_scope_ids',return_value={'group_ids':['10'],'member_agent_ids':['1001'],'campaign_ids':['C1'],'line_ids':['1']}):
        out=ac.filter_live_campaign_payload(u,payload)
    row=out['campaigns'][0]
    assert row['groups']==[{'id':'10','name':'G10'}]
    assert row['today']['quality']=='unavailable'
    assert row['today']['reason']=='campaign_spans_unauthorized_groups'
    assert row['trend']['volume_change_vs_reference'] is None


def test_live_search_never_uses_shared_campaign_alone_as_authorization():
    u=user({'mode':'SELECTED','allowed_group_ids':['10'],'default_group_id':'10','filter_locked':True})
    payload={'rows':[{'reference':'a','agent':'1001','line_id':'1','campaign':'C1'}, {'reference':'b','agent':'2002','line_id':'2','campaign':'C1'}], 'count':2}
    with patch.object(ac,'_selected_scope_ids',return_value={'group_ids':['10'],'member_agent_ids':['1001'],'campaign_ids':['C1'],'line_ids':['1']}):
        out=ac.filter_live_search_payload(u,payload)
    assert [x['reference'] for x in out['rows']]==['a']


def test_interface_permission_is_independent_from_other_interfaces():
    u=user({'mode':'ALL','allowed_group_ids':[],'default_group_id':'','filter_locked':False},{'live_supervision':1,'live_campaigns':0,'live_incidents':2})
    assert ac.has_interface(u,'live_supervision')
    assert not ac.has_interface(u,'live_campaigns')
    assert ac.has_interface(u,'live_incidents',write=True)
    assert not ac.has_interface(u,'live_supervision',write=True)


def test_frontend_contains_group_filter_and_full_interface_access_editor():
    live=open('static/live-views.js',encoding='utf-8').read()
    app=open('static/app.js',encoding='utf-8').read()
    assert 'live-business-group' in live
    assert "accessScope.locked?'disabled':''" in live
    assert "localStorage.setItem('nelyio.live.group'" in live
    assert '/api/access-groups/interface-permissions' in app
    assert '/api/access-groups/scope' in app
    assert 'Périmètre des groupes métier' in app
    assert 'viewInterfaceMap' in app


def test_restricted_incidents_hide_cross_group_aggregates_and_shared_campaigns():
    u=user({'mode':'SELECTED','allowed_group_ids':['10'],'default_group_id':'10','filter_locked':True})
    incidents=[
        {'id':'g','scope_type':'GLOBAL','scope_key':'GLOBAL'},
        {'id':'s','scope_type':'SERVICE','scope_key':'MEDICAL'},
        {'id':'a','scope_type':'AGENT','scope_key':'1001'},
        {'id':'q','scope_type':'QUEUE','scope_key':'1'},
        {'id':'c','scope_type':'CAMPAIGN','scope_key':'C1'},
    ]
    with patch.object(ac,'_selected_scope_ids',return_value={'group_ids':['10'],'member_agent_ids':['1001'],'campaign_ids':['C1'],'line_ids':['1']}), \
         patch('analysis_groups.group_ids_for_campaign',return_value=['10','11']):
        out=ac.filter_live_incidents(u,incidents)
    assert {x['id'] for x in out}=={'a','q'}


def test_every_navigation_interface_has_a_fine_grained_mapping_except_personal_account():
    import re
    from pathlib import Path
    html=Path('index.html').read_text(encoding='utf-8')
    app=Path('static/app.js').read_text(encoding='utf-8')
    views=set(re.findall(r'data-view=["\']([^"\']+)',html)) - {'account'}
    block=re.search(r'const\s+viewInterfaceMap\s*=\s*\{(.*?)\n\};',app,re.S)
    assert block, 'viewInterfaceMap missing'
    mapped=set(re.findall(r'["\']?([A-Za-z0-9_-]+)["\']?\s*:',block.group(1)))
    assert views <= mapped


def test_group_status_route_uses_authenticated_business_scope():
    text=open('http_handler.py',encoding='utf-8').read()
    assert 'return self.api_group_status(user)' in text


def test_support_priority_has_dedicated_interface_api_and_write_gate():
    handler=open('http_handler.py',encoding='utf-8').read()
    ui=open('static/priority_admin.js',encoding='utf-8').read()
    assert 'if path == "/api/support-priority"' in handler
    assert 'require_interface(user, "support_priority")' in handler
    assert 'require_interface(user, "support_priority", write=True)' in handler
    assert "api('/api/support-priority')" in ui
    assert "canWriteInterface('support_priority')" in ui


def test_first_allowed_route_includes_every_protected_navigation_view():
    import re
    from pathlib import Path
    html=Path('index.html').read_text(encoding='utf-8')
    app=Path('static/app.js').read_text(encoding='utf-8')
    views=set(re.findall(r'data-view=["\']([^"\']+)',html)) - {'account'}
    order_match=re.search(r"const order=\[(.*?)\];",app,re.S)
    assert order_match
    ordered=set(re.findall(r"['\"]([^'\"]+)['\"]",order_match.group(1)))
    assert views <= ordered
