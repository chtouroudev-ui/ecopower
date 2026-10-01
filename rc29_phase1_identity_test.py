"""RC29 Phase 1 - identity contract tests.

These tests are deliberately pure: they prove label precedence and ambiguity
handling without touching KPI calculations or production databases.
"""
from identity_resolver import resolve_agent_identity, resolve_campaign_identity


def test_agent_admin_name_wins_but_technical_id_is_preserved():
    users={
        '1039':{
            'user_identifier':'1039','first_name':'Alice','last_name':'Martin',
            'display_name':'Alice Martin'
        }
    }
    result=resolve_agent_identity('1039',admin_users=users,observed_name='A. MARTIN',configured_name='Agent 1039')
    assert result['agent_id']=='1039'
    assert result['display_name']=='Alice Martin'
    assert result['name_source']=='administration'


def test_identifier_only_directory_does_not_hide_observed_name():
    users={'1039':{'user_identifier':'1039','first_name':'','last_name':'','display_name':'1039'}}
    result=resolve_agent_identity('1039',admin_users=users,observed_name='Alice Hermes')
    assert result['display_name']=='Alice Hermes'
    assert result['name_source']=='observed'


def test_campaign_id_is_canonical_and_label_preserved():
    scope={'campaigns':{'C1':{'campaign_id':'C1','campaign_name':'CABINET A'}}}
    result=resolve_campaign_identity('C1','Ancien libelle',scope=scope)
    assert result=={'campaign_id':'C1','campaign_label':'CABINET A','identity_quality':'configured_id'}


def test_unique_campaign_label_can_resolve_to_configured_id():
    scope={'campaigns':{'C1':{'campaign_name':'CABINET A'}}}
    result=resolve_campaign_identity('','CABINET A',scope=scope)
    assert result['campaign_id']=='C1'
    assert result['identity_quality']=='configured_label'


def test_ambiguous_campaign_label_is_never_silently_merged():
    scope={'campaigns':{
        'C1':{'campaign_name':'CABINET A'},
        'C2':{'campaign_name':'CABINET A'},
    }}
    result=resolve_campaign_identity('','CABINET A',scope=scope)
    assert result['campaign_id']=='RAW:cabinet a'
    assert result['campaign_label']=='CABINET A'
    assert result['identity_quality']=='observed_only'


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    for test in tests:test()
    print(f'OK - {len(tests)} tests RC29 Phase 1 identites')
