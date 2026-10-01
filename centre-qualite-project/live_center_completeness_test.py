from pathlib import Path
import types,sys

ROOT=Path(__file__).resolve().parent


def _scope_fixture():
    return {
        'groups':[
            {'id':'G1','name':'MED1','service_name':'MEDICAL','line_ids':[571],'member_agent_ids':['1001','1002']},
            {'id':'G2','name':'IMG2','service_name':'IMAGERIE','line_ids':[881],'member_agent_ids':['2001']},
        ],
        'queues':[
            {'line_id':571,'line_name':'File 571','display_name':'File 571'},
            {'line_id':881,'line_name':'File 881','display_name':'File 881'},
        ],
        'campaigns':{
            'C1':{'campaign_name':'CABINET A'},
            'C2':{'campaign_name':'RADIO B'},
            'ORPHAN':{'campaign_name':'ANCIENNE CAMPAGNE SANS FILE'},
        },
        'campaign_to_files':{
            'C1':[{'line_id':571,'line_name':'File 571'}],
            'C2':[{'line_id':881,'line_name':'File 881'}],
        },
        'agents_by_line_state':{'active':{'571':['1001','1002'],'881':['2001']}},
    }


def test_configured_campaigns_remain_visible_without_live_state(monkeypatch):
    import quality_scope,live_quality
    monkeypatch.setattr(quality_scope,'load_quality_file_scope',lambda force=False:_scope_fixture())
    snap={'health':{'fresh':True,'last_response_age':1},'kpi':{'agents_known':0,'connected':0,'available':0,'in_call':0,'on_hold':0,'current_calls':0},'agents':[],'agent_roster':[],'catalog_reference':True}
    scopes=live_quality.build_scopes(snap)
    campaigns={x['scope_key']:x for x in scopes if x['scope_type']=='CAMPAIGN'}
    assert set(campaigns)=={'C1','C2'}
    assert 'ORPHAN' not in campaigns
    assert campaigns['C1']['configured_agent_count']==2
    assert campaigns['C1']['observed_agent_count']==0
    assert campaigns['C1']['metrics']['agents_connected']['value'] is None
    assert campaigns['C1']['metrics']['agents_connected']['reason']=='no_live_state_observed'


def test_selected_group_restricts_configured_campaigns_and_files(monkeypatch):
    import quality_scope,live_quality
    monkeypatch.setattr(quality_scope,'load_quality_file_scope',lambda force=False:_scope_fixture())
    snap={'health':{'fresh':True,'last_response_age':1},'kpi':{},'scope':{'group_id':'G1'},'agents':[],'agent_roster':[],'catalog_reference':True}
    scopes=live_quality.build_scopes(snap)
    assert {x['scope_key'] for x in scopes if x['scope_type']=='GROUP'}=={'G1'}
    assert {x['scope_key'] for x in scopes if x['scope_type']=='QUEUE'}=={'571'}
    assert {x['scope_key'] for x in scopes if x['scope_type']=='CAMPAIGN'}=={'C1'}


def test_configured_agent_roster_marks_missing_live_state_unobserved(monkeypatch):
    import analysis_groups,quality_scope,agent_directory,collection_store
    monkeypatch.setattr(analysis_groups,'catalog',lambda include_unassigned=False:[
        {'id':'G1','name':'MED1','service_name':'MEDICAL','member_agent_ids':['1001','1002']}
    ])
    monkeypatch.setattr(quality_scope,'load_quality_file_scope',lambda force=False:{'agent_names':{'1001':'Alice','1002':'Bob'}})
    monkeypatch.setattr(agent_directory,'load_admin_directory',lambda:{'users':{},'available':True,'groups':[],'exclusions':set()})
    monkeypatch.setattr(agent_directory,'admin_name_for',lambda aid,users,fallback='':fallback or aid)
    observed=[{'agent':'1001','name':'Alice','kind':'ready','groups':[{'id':'G1','name':'MED1','service_name':'MEDICAL'}],'service_names':['MEDICAL']}]
    roster,_=collection_store._configured_live_reference(observed)
    by={x['agent']:x for x in roster}
    assert set(by)=={'1001','1002'}
    assert by['1001']['observed'] is True
    assert by['1002']['observed'] is False
    assert by['1002']['kind']=='unobserved'
    assert by['1002']['state']=='Non observé'


def test_live_center_ui_uses_requested_agent_label_and_hides_uncertified_cards():
    js=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
    assert '<h2>Agents</h2>' in js
    assert 'Preuves agents / états Live' not in js
    assert "[gm.hold_percent,'Part en mise en attente']" not in js
    assert "liveMetricCard(gm.waiting_now,'Appels en attente')" not in js
    assert '<h3>Qualité certifiée</h3>' not in js
    assert 'Analyse qualité' in js
    assert "/api/live/campaigns?include_inactive=1" in js
