"""RC29 Phase 3 — Signalisation Qualité Live regression tests.

All durable state is isolated in temporary SQLite databases.
"""
from __future__ import annotations
import os, sys, types, zipfile
from pathlib import Path
import pytest

os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

@pytest.fixture
def lab(tmp_path,monkeypatch):
    import app_config, supervision_context as ctx, collection_store
    with zipfile.ZipFile(ROOT/'audit_empty_schemas.zip') as z:z.extractall(tmp_path)
    admin=tmp_path/'TECHIN_Stock_Manager.db';live=tmp_path/'Nelyio_Live.db'
    monkeypatch.setattr(app_config,'APP_DB',admin);monkeypatch.setattr(ctx,'DEFAULT_ADMIN_DB',admin)
    facade=types.ModuleType('supervision');facade.ADMIN_DB=admin;facade.DB=tmp_path/'NELYIO_Supervision.db';monkeypatch.setitem(sys.modules,'supervision',facade)
    monkeypatch.setattr(collection_store,'db_path',lambda:live);collection_store._SCHEMA_IDENTITIES.clear();collection_store.init()
    return tmp_path

def levels():
    return [
        {'level_key':'DEGRADE','label':'DÉGRADÉ','rank':300,'color':'#B54708','enabled':1,'is_fallback':0},
        {'level_key':'SURVEILLANCE','label':'À SURVEILLER','rank':200,'color':'#A56A00','enabled':1,'is_fallback':0},
        {'level_key':'NORMAL','label':'NORMAL','rank':100,'color':'#24634A','enabled':1,'is_fallback':1},
    ]

def agent(aid,kind,state,age=600):
    return {'agent':str(aid),'name':f'Agent {aid}','kind':kind,'state':state,'state_age_seconds':age,'line_id':'571','campaign':'CABINET A','groups':[{'id':'2','name':'MED02','service_name':'MEDICAL'}],'assigned_groups':[{'id':'2','name':'MED02','service_name':'MEDICAL'}],'current_groups':[{'id':'2','name':'MED02','service_name':'MEDICAL'}],'service_names':['MEDICAL'],'current_call':None}

def snap(rows,fresh=True):
    connected=sum(1 for r in rows if r['kind']!='offline')
    return {'health':{'fresh':fresh,'active':True,'last_response_age':2 if fresh else 45},'kpi':{'agents_known':len(rows),'connected':connected,'in_call':0,'available':sum(r['kind']=='ready' for r in rows),'unavailable':sum(r['kind'] not in ('offline','ready','call','hold') for r in rows),'current_calls':0 if fresh else None,'calls_waiting':None},'agents':rows}

def test_inactive_context_requires_explicit_hermes_label():
    from supervision_utils import kind
    assert kind('Aucun contexte démarré')=='inactive_context'
    assert kind('Contexte inactif')=='inactive_context'
    assert kind('Inactive context')=='inactive_context'
    assert kind('Unknown state')=='other'
    assert kind('Sonnerie')=='other'

def test_inactive_context_metrics_are_distinct_from_other(lab):
    import live_quality
    scope=live_quality._scope_metrics([agent('1001','inactive_context','Aucun contexte démarré',420),agent('1002','other','Unknown state',999)],{'fresh':True,'last_response_age':1})
    assert scope['agents_inactive_context']['value']==1
    assert scope['inactive_context_percent']['value']==50.0
    assert scope['max_inactive_context_seconds']['value']==420.0
    assert scope['max_inactive_context_seconds']['value']!=999.0

def test_configured_but_absent_is_unavailable_not_zero(lab):
    import live_quality
    metrics=live_quality._scope_metrics([],{'fresh':True,'last_response_age':1},configured_count=1,reference_scope=True)
    assert metrics['agents_known']['value']==1
    assert metrics['agents_pause']['value'] is None
    assert metrics['agents_inactive_context']['value'] is None
    assert metrics['agents_offline']['value'] is None

def test_presets_and_modes_are_exposed_without_auto_creating_them(lab):
    import live_quality
    cfg=live_quality.config_snapshot();keys={p['key'] for p in cfg['presets']}
    assert {'pause_longue','post_appel_long','contexte_inactif_long','deconnexion_prolongee','aucun_disponible','trop_agents_pause','trop_agents_contexte_inactif'}<=keys
    assert cfg['modes']==['simple','advanced']
    # Presets are templates, not silently persisted rules.
    persisted={r['name'] for r in cfg['rules']}
    assert 'Contexte inactif long' not in persisted

def test_multi_targets_all_any_and_partial_contract(lab):
    import live_quality
    rule=live_quality.normalize_rule({'name':'Multi','scope_type':'GROUP','target_keys':['2','3','2'],'match_mode':'ANY','level_key':'SURVEILLANCE','min_sample_size':1,'allow_partial':True,'conditions':[{'metric':'agents_pause','operator':'>=','value':1}]},known_levels={'SURVEILLANCE'})
    assert rule['target_keys']==['2','3']
    scope={'scope_type':'GROUP','scope_key':'2','scope_label':'MED02','agent_count':1,'metrics':{'agents_pause':live_quality._metric(1,quality='partial')}}
    assert live_quality.evaluate_rule(rule,scope)['matched'] is True
    rule['allow_partial']=0
    result=live_quality.evaluate_rule(rule,scope)
    assert result['eligible'] is False and result['reason']=='metric_unavailable'

def test_aggregate_incident_exposes_observed_contributing_agents(lab):
    import live_quality
    rows=[agent('1001','pause','Pause',700),agent('1002','pause','Pause',300),agent('1003','ready','Prêt',20)]
    rule={'id':9301,'name':'Trop de pauses','enabled':1,'scope_type':'GROUP','target_key':'2','match_mode':'ALL','level_key':'SURVEILLANCE','min_duration_seconds':0,'recovery_seconds':30,'cooldown_seconds':60,'min_sample_size':3,'allow_partial':0,'conditions':[{'metric':'agents_pause','operator':'>=','value':2},{'metric':'pause_percent','operator':'>=','value':60}]}
    live_quality.process_snapshot(snap(rows),clock=1000,rules=[rule],levels=levels(),persist=True)
    inc=live_quality.incident_snapshot(active_only=True)
    assert len(inc)==1
    ids={x['agent'] for x in inc[0]['contributors']}
    assert ids=={'1001','1002'}
    assert all(x['kind']=='pause' for x in inc[0]['contributors'])

def test_simple_advanced_ui_and_contributor_rendering_are_present():
    admin=(ROOT/'static'/'live-quality-admin.js').read_text(encoding='utf-8')
    views=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
    assert "data-lq-mode=\"simple\"" in admin and "data-lq-mode=\"advanced\"" in admin
    assert 'data-lq-preset' in admin
    assert 'Agents contributeurs observés' in views
