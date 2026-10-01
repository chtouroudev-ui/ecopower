from __future__ import annotations

from pathlib import Path

from live_scope_quality import _qos
from quality_rules import decorate
from sort_contract import request, sorted_rows

ROOT=Path(__file__).resolve().parent


def test_qos_contract():
    assert _qos(0,0,0,0) is None
    assert _qos(8,12,1,1)==80.0
    row=decorate({
        'treated_agent':8,'abandoned':2,'received':12,'closed':1,'hangup_before_queue':1,'rerouted_no_agent':1,
        'wait_sum':0,'wait_count':0,'completed':8,'transferred':0,'rerouted_agent':0,'overflow':0,'ignored':0,'double_classified':0,
    })
    assert row['qos_percent']==80.0
    assert row['qos_numerator']==8 and row['qos_denominator']==10
    assert row['reference_qos_numerator']==8 and row['reference_qos_denominator']==10
    empty=decorate({'treated_agent':0,'abandoned':0,'received':0,'wait_sum':0,'wait_count':0})
    assert empty['qos_percent'] is None


def test_backend_sort_allowlist_and_missing_last():
    qs={'sort':['duration'],'direction':['desc']}
    assert request(qs,allowed={'duration','id'},default_key='id')==('duration','desc')
    try:
        request({'sort':['duration;DROP TABLE users'],'direction':['asc']},allowed={'duration','id'},default_key='id')
    except ValueError:
        pass
    else:
        raise AssertionError('sort injection key accepted')
    rows=[{'id':'2','v':None},{'id':'1','v':5},{'id':'3','v':10}]
    getter=lambda r,k:r['v'] if k=='duration' else r['id']
    asc=sorted_rows(rows,key='duration',direction='asc',getter=getter,id_getter=lambda r:r['id'])
    desc=sorted_rows(rows,key='duration',direction='desc',getter=getter,id_getter=lambda r:r['id'])
    assert [r['id'] for r in asc]==['1','3','2']
    assert [r['id'] for r in desc]==['3','1','2']


def test_frontend_contract():
    src=(ROOT/'static/live-views.js').read_text(encoding='utf-8')
    assert "sessionStorage.setItem('nelyio.rc29.sort.'" in src
    assert "if(cur.direction==='asc')" in src and "direction:'desc'" in src and "direction:'default'" in src
    assert "data-live-agent-id" in src
    assert "livePatchAgentRoster" in src
    assert "app.innerHTML=shell(d)" in src
    assert "seq!==requestSeq" in src
    for expected in [
        "rc29SortHeader(key,'agent','Agent','string')",
        "rc29SortHeader(key,'state','État','state')",
        "rc29SortHeader(key,'callDuration','Appel total','duration')",
        "rc29SortHeader(key,'campaign','Campagne','string')",
        "rc29SortHeader(key,'handled','Traités','number')",
        "rc29SortHeader(key,'pauseDuration','Pauses','duration')",
        "rc29SortHeader(key,'offlineDuration','Déconnecté','duration')",
        "rc29SortHeader(key,'ani','ANI','string')",
    ]:
        assert expected in src
    assert 'Hermes Live · Réception' not in src
    assert 'durée observée · début réel antérieur possible' not in src
    assert 'liveAgentPageData' in src and 'live-compact-pager' in src
    assert 'Service / groupe</th>' not in src[src.index('function liveAgentHeaderHtml'):src.index('function liveCampaignMetric')]
    assert '/api/live/scope-quality' in src
    assert 'Traités / (Reçus - Clôturés - Raccrochés avant file d’attente)' in src
    assert "rc29SortHeader(key,'callDuration','Appel total','duration')" in src
    assert "liveStateLabel(r.kind)" in src and "data-live-duration-role=\"state\"" in src
    assert 'call.call_age_seconds' in src
    assert 'durée observée · début réel antérieur possible' not in src


def test_route_contract():
    routes=(ROOT/'routes_collection.py').read_text(encoding='utf-8')
    http=(ROOT/'http_handler.py').read_text(encoding='utf-8')
    assert 'def api_live_scope_quality' in routes
    assert 'scope_query(user,qs' in routes
    assert '"/api/live/scope-quality"' in http


if __name__=='__main__':
    tests=[test_qos_contract,test_backend_sort_allowlist_and_missing_last,test_frontend_contract,test_route_contract]
    for t in tests:t();print('OK',t.__name__)
