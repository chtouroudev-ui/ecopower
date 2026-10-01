from pathlib import Path
from quality_rules import decorate
from live_scope_quality import _qos

ROOT=Path(__file__).resolve().parent

def test_canonical_qos():
    row=decorate({'received':100,'treated_agent':80,'closed':5,'hangup_before_queue':10,'abandoned':7,'wait_sum':0,'wait_count':0})
    assert row['qos_numerator']==80
    assert row['qos_denominator']==85
    assert abs(row['qos_percent']-(80/85*100))<1e-10
    assert row['reference_qos_percent']==row['qos_percent']
    assert _qos(80,100,5,10)==round(80/85*100,4)
    assert _qos(1,10,5,5) is None

def test_no_legacy_qos_formula_in_active_ui_or_engines():
    files=['quality_rules.py','quality_metrics.py','quality_distributions.py','live_scope_quality.py','static/quality-overview.js','static/quality-distributions.js','static/live-views.js']
    legacy=('Traités / (Traités + Abandonnés)','treated / (treated + abandoned)','traités ÷ (traités + abandonnés)')
    for name in files:
        text=(ROOT/name).read_text(encoding='utf-8')
        for token in legacy:
            assert token not in text,(name,token)

def test_supervision_workstation_contract():
    js=(ROOT/'static/live-views.js').read_text(encoding='utf-8')
    css=(ROOT/'static/collection.css').read_text(encoding='utf-8')
    assert "liveSupervisionState.scopeType=liveSupervisionState.scopeType||'CAMPAIGN'" in js
    assert 'live-supervision-workstation' in js
    assert 'live-ops-board' in js
    assert "sessionStorage.getItem('nelyio.live.layout')||'agents'" in js
    assert '<option value="agents">Agents</option>' in js
    assert '<option value="scopes">Campagnes / périmètres</option>' in js
    assert '<option value="split">Double vue</option>' in js
    assert 'live-supervision-rail' in js
    assert 'live-detail-drawer' not in js
    assert 'live-kpis-wrap' in js
    assert '.live-supervision-workstation{max-width:none!important;height:calc(100dvh - 112px)' in css
    assert '.live-ops-board{display:grid' in css
    assert 'position:sticky;top:0' in css

if __name__=='__main__':
    tests=[test_canonical_qos,test_no_legacy_qos_formula_in_active_ui_or_engines,test_supervision_workstation_contract]
    for t in tests:t();print('OK',t.__name__)
