from pathlib import Path
import pytest
from collection_parser import Decoder

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
CSS=(ROOT/'static'/'collection.css').read_text(encoding='utf-8')


def test_hermes_agent_daily_pause_mapping_from_verified_har_shape():
    result=Decoder().decode('UpAgtH(231,1048,7,0,73,2753,70,8634,1,732);')
    ev=result['events'][0]
    assert ev['type']=='agent_metrics'
    assert ev['entity']=='1048'
    assert ev['payload']['mapped_metrics']=={
        'reception_today':70,
        'pause_count_today':1,
        'pause_seconds_today':732,
    }


def test_hermes_queue_daily_mapping_and_qos_are_native_live_evidence():
    result=Decoder().decode('UpQuH(231,505,8,815,0,153,2,729,37,0,8,12,641,32,0,4946,86474,6784,0,0);')
    m=result['events'][0]['payload']['mapped_metrics']
    assert m['received_today']==815
    assert m['abandoned_today']==153
    assert m['handled_today']==641
    assert m['qos_denominator']==793
    assert m['qos_today']==pytest.approx(641/793*100)


def test_hermes_queue_realtime_mapping():
    result=Decoder().decode('UpQuR(231,505,5,4,0,0,0,0,1,0);')
    m=result['events'][0]['payload']['mapped_metrics']
    assert m=={'calls_in_progress':5,'calls_waiting':4,'agents_available_on_queue':1}


def test_live_ui_exposes_native_campaign_metrics_and_agent_pause_metrics():
    for label in ('Attente','En cours','Reçus','Traités','Abandonnés','QoS'):
        assert label in JS
    assert "'pauseDuration','Pauses'" in JS
    assert 'pause_seconds_today' in JS and 'pause_count_today' in JS
    assert 'hermes_daily?.pause_count_today' in JS
    assert 'hermes_daily?.pause_seconds_today' in JS
    assert 'activity?.state_seconds?.offline' in JS
    assert "offlineDuration','Déconnecté'" in JS
    assert 'live-scope-compact' in JS
    assert 'native.handled_today' in JS and 'native.qos_today' in JS


def test_centre_qualite_live_has_scoped_125_percent_desktop_scale():
    marker='Centre Qualite Live: +25% visual scale requested for desktop supervision only.'
    assert marker in CSS
    block=CSS[CSS.index(marker):]
    assert '.live-supervision-simple .live-agent-ops-table' in block
    assert '.live-supervision-simple .live-scope-table' in block
    assert 'font-size:13px!important' in block
    assert 'grid-template-columns:188px minmax(0,1fr)!important' in block
