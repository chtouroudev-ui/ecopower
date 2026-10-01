from pathlib import Path
from supervision_utils import kind

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
STORE=(ROOT/'collection_store.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
HTTP=(ROOT/'http_handler.py').read_text(encoding='utf-8')


def test_waiting_agent_is_available_but_call_hold_is_distinct():
    assert kind('En attente') == 'ready'
    assert kind('Attente') == 'ready'
    assert kind('Waiting') == 'ready'
    assert kind('Mise en attente') == 'hold'
    assert kind('On hold') == 'hold'


def test_campaign_scope_removes_status_only_for_campaign_rows():
    assert "isCampaign=String(type)==='CAMPAIGN'" in JS
    assert "rc29SortHeader(tableKey,'scope','Campagne','string')" in JS
    assert "rc29SortHeader(tableKey,'status','Statut','state')" in JS
    campaign_block=JS[JS.index('if(isCampaign){'):JS.index('const hist=liveSupervisionState.scopeQuality?.data')]
    assert "'Statut'" not in campaign_block
    assert 'native.handled_today' in JS and 'native.qos_today' in JS and 'native.calls_waiting' in JS
    assert 'native.calls_in_progress' in JS and 'native.received_today' in JS and 'native.abandoned_today' in JS


def test_agent_roster_columns_are_operational():
    assert "'handled','Traités','number'" in JS
    assert "'pauseDuration','Pauses','duration'" in JS
    assert 'pause_count_today' in JS and 'pause_seconds_today' in JS
    assert "'ani','ANI'" in JS
    header=JS[JS.index('function liveAgentHeaderHtml'):JS.index('function liveCampaignMetric')]
    assert "'line','File'" not in header
    assert "'freshness','Fraîcheur'" not in header
    assert 'liveAgentHistoryMap' in JS


def test_live_supervision_ani_respects_permission():
    assert 'show_phone=False' in STORE
    assert 'phone=(raw_phone if show_phone else _mask_phone(raw_phone))' in STORE
    assert 'phone_masked=bool(raw_phone and not show_phone)' in STORE
    assert 'show_phone=user_has_access(user, "ani")' in HTTP
    assert 'show_phone=show_phone' in ROUTES


def test_agent_roster_exposes_daily_disconnect_duration():
    assert "offlineDuration','Déconnecté','duration'" in JS
    assert 'activity?.state_seconds?.offline' in JS


def test_daily_native_queue_metrics_survive_same_day_reconnect_but_realtime_does_not():
    import json
    from collection_store import _latest_native_hermes_metrics
    class FakeCon:
        def execute(self, sql, params):
            return [
                {'session_id':'old','stamp':20,'event_type':'queue_metrics','entity_id':'505','payload_json':json.dumps({'source_function':'UpQuH','mapped_metrics':{'received_today':815,'handled_today':641,'abandoned_today':153}})},
                {'session_id':'old','stamp':19,'event_type':'queue_metrics','entity_id':'505','payload_json':json.dumps({'source_function':'UpQuR','mapped_metrics':{'calls_waiting':9,'calls_in_progress':7}})},
                {'session_id':'new','stamp':30,'event_type':'queue_metrics','entity_id':'505','payload_json':json.dumps({'source_function':'UpQuR','mapped_metrics':{'calls_waiting':4,'calls_in_progress':5}})},
            ]
    agents,queues=_latest_native_hermes_metrics(FakeCon(),'new',['old','new'])
    assert queues['505']['UpQuH']['received_today']==815
    assert queues['505']['UpQuR']['calls_waiting']==4
    assert queues['505']['UpQuR']['calls_in_progress']==5


def test_campaign_live_filters_orphans_and_keeps_file_fallback_contract():
    import live_quality
    src=Path(live_quality.__file__).read_text(encoding='utf-8')
    assert 'if not line_ids:' in src and 'continue' in src
    assert "'FILE:'+qid" in src
    assert 'diagnostic_file_fallback' in src
