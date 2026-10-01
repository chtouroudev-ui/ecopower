from unittest.mock import patch


def _scope():
    return {
        'basis':'configured_files',
        'groups':[
            {'id':'10','name':'G-A','line_ids':[101],'campaign_ids':['C1'],'member_agent_ids':['1001','1002'],'file_count':1,'member_count':2},
            {'id':'20','name':'G-B','line_ids':[202],'campaign_ids':['C2'],'member_agent_ids':['1002','1003'],'file_count':1,'member_count':2},
            {'id':'unassigned','name':'Sans groupe de file','line_ids':[],'campaign_ids':['C3'],'member_agent_ids':['1004'],'file_count':0,'member_count':1},
        ]
    }


def test_multi_group_agent_and_row_scope():
    import analysis_groups
    import unified_filters
    with patch.object(analysis_groups,'load_quality_file_scope',return_value=_scope()):
        assert analysis_groups.matches_agent_groups('S1002',['10'])
        assert analysis_groups.matches_agent_groups('1002',['20'])
        assert not analysis_groups.matches_agent_groups('1001',['20'])
        assert analysis_groups.selected_group_members(['10','20']) == {'1001','1002','1003'}
        rows=[{'agent':'1001','group_id':999},{'agent':'1002','group_id':999},{'agent':'1003','group_id':999}]
        out=unified_filters.apply_row_scope(rows,{'groups':['20']})
        assert [r['agent'] for r in out]==['1002','1003']


def test_quality_group_catalog_uses_files_not_campaign_anchors():
    import quality_scope
    import quality_summary
    campaigns=[{'campaign':'C1','campaign_name':'A'},{'campaign':'C2','campaign_name':'B'},{'campaign':'C3','campaign_name':'C'}]
    with patch.object(quality_scope,'load_quality_file_scope',return_value=_scope()):
        groups=quality_summary.group_catalog(campaigns)
    by={g['id']:g for g in groups}
    assert by['10']['campaign_ids']==['C1']
    assert by['20']['campaign_ids']==['C2']
    assert by['unassigned']['campaign_ids']==['C3']
    assert all(g['basis']=='configured_files' for g in groups)


def test_scope_membership_is_strictly_active_only():
    import sqlite3
    import quality_scope
    raw={
        'campaigns':[],
        'queues':[{'line_id':101,'line_name':'File A','campaign_ids':[]}],
        'observations':[],
        'agents':[
            {'agent_id':'1001','queues':[{'line_id':101,'activation_state':'active'}]},
            {'agent_id':'1002','queues':[{'line_id':101,'activation_state':'partial'}]},
            {'agent_id':'1003','queues':[{'line_id':101,'activation_state':'inactive'}]},
            {'agent_id':'S1004','queues':[{'line_id':101,'activation_state':'active'}]},
        ],
    }
    con=sqlite3.connect(':memory:')
    groups=[{'id':'10','name':'G-A','line_ids':[101],'agent_ids':[]}]
    try:
        with patch.object(quality_scope,'_read_raw',return_value=raw), \
             patch.object(quality_scope,'group_records',return_value=groups), \
             patch.object(quality_scope,'db_connect',return_value=con):
            data=quality_scope._build_scope()
        g=next(x for x in data['groups'] if x['id']=='10')
        assert g['member_agent_ids']==['1001','1004']
        assert data['membership_rule']=='group_files -> ACTIVE agent assignments only'
    finally:
        con.close()
