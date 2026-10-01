from pathlib import Path
import live_quality as lq

ROOT=Path(__file__).parent

def _scope(key,label=None):
    return {'scope_type':'GROUP','scope_key':key,'scope_label':label or key,'agent_count':1,'metrics':{'agents_connected':{'value':1,'quality':'reliable','source':'test'}}}

def test_scope_query_calls_are_keyword_only():
    assert "scope_query(user, query or {}, 'group')" not in (ROOT/'routes_quality.py').read_text(encoding='utf-8')
    assert "(user,qs or {},'group')" not in (ROOT/'supervision_routes.py').read_text(encoding='utf-8')
    assert "param='group'" in (ROOT/'routes_quality.py').read_text(encoding='utf-8')
    assert "param='group'" in (ROOT/'supervision_routes.py').read_text(encoding='utf-8')

def test_multi_target_rule_matches_any_selected_target():
    rule=lq.normalize_rule({'name':'multi','scope_type':'GROUP','target_keys':['MED1','MED2'],'match_mode':'ALL','level_key':'DEGRADE','conditions':[{'metric':'agents_connected','operator':'>=','value':1}]},known_levels={'DEGRADE'})
    assert lq.evaluate_rule(rule,_scope('MED1'))['matched'] is True
    assert lq.evaluate_rule(rule,_scope('MED2'))['matched'] is True
    assert lq.evaluate_rule(rule,_scope('IMG1'))['eligible'] is False

def test_multi_target_storage_roundtrip_is_backward_compatible():
    rule=lq.normalize_rule({'name':'multi','scope_type':'AGENT','target_keys':['1001','1002'],'match_mode':'ANY','level_key':'DEGRADE','conditions':[{'metric':'agents_connected','operator':'>=','value':1}]},known_levels={'DEGRADE'})
    assert rule['target_key'].startswith('@MULTI:')
    assert lq.rule_target_keys(rule)==['1001','1002']
    legacy={'target_key':'1001'}
    assert lq.rule_target_keys(legacy)==['1001']

def test_signal_ui_has_guided_multi_target_and_units():
    js=(ROOT/'static/live-quality-admin.js').read_text(encoding='utf-8')
    for token in ['target_keys','sélection multiple','Anti-bruit / temporisation','120 s = 2 min','lq-target-search']:
        assert token.lower() in js.lower()
