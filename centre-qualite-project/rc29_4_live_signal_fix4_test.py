import json
import sqlite3
import time
from pathlib import Path

import collection_store
import live_quality


def metric_value(metrics,key):
    return (metrics.get(key) or {}).get('value')


def test_pause_subtypes_and_configurable_durations():
    agents=[
        {'agent':'1','kind':'pause','state':'Pause déjeuner','state_age_seconds':3700},
        {'agent':'2','kind':'pause','state':'Coaching','state_age_seconds':1900},
        {'agent':'3','kind':'pause','state':'General Break','state_age_seconds':700},
        {'agent':'4','kind':'pause','state':'Pause','state_age_seconds':120},
    ]
    m=live_quality._scope_metrics(agents,{'fresh':True,'last_response_age':1})
    assert metric_value(m,'agents_pause_lunch')==1
    assert metric_value(m,'agents_pause_coaching')==1
    assert metric_value(m,'agents_pause_general')==1
    assert metric_value(m,'agents_pause_normal')==1
    assert metric_value(m,'max_pause_lunch_seconds')==3700
    assert metric_value(m,'max_pause_coaching_seconds')==1900
    assert metric_value(m,'max_pause_general_seconds')==700
    assert metric_value(m,'max_pause_normal_seconds')==120


def test_early_hold_is_metric_and_partial_start_stays_unknown():
    agents=[{'agent':'1','kind':'call','state':'En appel','state_age_seconds':20,
             'current_call':{'first_hold_offset_seconds':7.5}}]
    m=live_quality._scope_metrics(agents,{'fresh':True,'last_response_age':1})
    assert metric_value(m,'earliest_hold_start_seconds')==7.5
    payload={'partial_start':False,'timeline':[{'stamp':100,'state':'En appel'},{'stamp':108,'state':'Mise en attente'}]}
    assert collection_store._first_explicit_hold_offset(payload,100)==8.0
    payload['partial_start']=True
    assert collection_store._first_explicit_hold_offset(payload,100) is None


def test_fix4_presets_are_available_and_editable():
    keys={x['key'] for x in live_quality.RULE_PRESETS}
    expected={'post_appel_surveillance_10s','post_appel_alerte_15s','post_appel_critique_25s',
              'pause_dejeuner_plus_1h','coaching_long','general_break_long','hold_long',
              'hold_precoce_10s','deconnexion_plus_10min','contexte_inactif_long_fix4'}
    assert expected <= keys
    early=next(x for x in live_quality.RULE_PRESETS if x['key']=='hold_precoce_10s')
    assert early['scope_type']=='AGENT'
    assert early['conditions']==[{'metric':'earliest_hold_start_seconds','operator':'<=','value':10}]


def test_agent_signal_uses_strongest_configured_level_only_for_agent():
    snapshot={'health':{'fresh':True,'last_response_age':1},'agents':[{'agent':'1001','name':'A','kind':'ready','state':'Disponible','state_age_seconds':2}],
              'agent_roster':[{'agent':'1001','name':'A','kind':'ready','state':'Disponible','state_age_seconds':2}]}
    incidents=[
        {'id':'a','rule_id':1,'rule_name':'Warn','scope_type':'AGENT','scope_key':'1001','scope_label':'A','level_key':'SURVEILLANCE','level_label':'À SURVEILLER','level_rank':200,'color':'#AA8800','status':'NOUVEAU','active':1,'triggered_at':1},
        {'id':'b','rule_id':2,'rule_name':'Critical','scope_type':'AGENT','scope_key':'1001','scope_label':'A','level_key':'CRITIQUE','level_label':'CRITIQUE','level_rank':400,'color':'#B42318','status':'NOUVEAU','active':1,'triggered_at':2},
        {'id':'c','rule_id':3,'rule_name':'Group','scope_type':'GROUP','scope_key':'G1','scope_label':'G1','level_key':'CRITIQUE','level_label':'CRITIQUE','level_rank':500,'color':'#000000','status':'NOUVEAU','active':1,'triggered_at':3},
    ]
    levels=[{'level_key':'NORMAL','label':'NORMAL','rank':100,'color':'#24634A','enabled':1,'is_fallback':1}]
    center=live_quality.quality_center(snapshot,levels=levels,rules=[],incidents=incidents)
    assert center['agent_signals']['1001']['incident_id']=='b'
    assert center['agent_signals']['1001']['color']=='#B42318'


def _incident_values(i, active, last_seen, recovered=None, closed=None):
    return (i,1,'R','AGENT','1001','A','SURVEILLANCE','À SURVEILLER',200,'#A56A00','NOUVEAU' if active else 'RETABLI',active,last_seen,last_seen,last_seen,recovered,closed,0,'[]','{}','[]',last_seen)


def test_history_retention_keeps_active_and_only_90_days(tmp_path, monkeypatch):
    db=tmp_path/'live.db'
    monkeypatch.setattr(collection_store,'db_path',lambda:db)
    collection_store.init(force=True)
    now=1_900_000_000.0
    old=now-91*86400
    recent=now-30*86400
    with collection_store.connect() as con:
        live_quality.ensure_runtime_schema(con)
        sql='''INSERT INTO live_quality_incidents(id,rule_id,rule_name,scope_type,scope_key,scope_label,level_key,level_label,level_rank,color,status,active,first_seen,last_seen,triggered_at,recovered_at,closed_at,cooldown_until,reasons_json,metrics_json,contributor_agents_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
        con.execute(sql,_incident_values('old',0,old,recovered=old))
        con.execute(sql,_incident_values('recent',0,recent,recovered=recent))
        con.execute(sql,_incident_values('active-old',1,old))
        for ident,stamp in [('old',old),('recent',recent),('active-old',old)]:
            con.execute("INSERT INTO live_quality_incident_events(incident_id,event_type,actor,created_at) VALUES(?,?,?,?)",(ident,'OUVERTURE','SYSTEM',stamp))
        deleted=live_quality.purge_incident_history(clock=now,con=con)
        assert deleted==1
        ids={r[0] for r in con.execute('SELECT id FROM live_quality_incidents')}
        assert ids=={'recent','active-old'}
        event_ids={r[0] for r in con.execute('SELECT incident_id FROM live_quality_incident_events')}
        assert event_ids=={'recent','active-old'}


def test_frontend_has_hold_filter_and_configured_row_signal():
    root=Path(__file__).resolve().parent
    js=(root/'static'/'live-views.js').read_text(encoding='utf-8')
    css=(root/'static'/'collection.css').read_text(encoding='utf-8')
    admin=(root/'static'/'live-quality-admin.js').read_text(encoding='utf-8')
    assert "chip('hold','Mise en attente',c.hold)" in js
    assert "state==='call'?['call','hold'].includes(bucket)" in js
    assert 'live-rule-signal' in js and 'agent_signals' in js
    assert '.live-agent-table tbody tr.live-rule-signal' in css
    assert 'Historique 90 jours' in js
    assert 'Historique 90 jours' in admin
