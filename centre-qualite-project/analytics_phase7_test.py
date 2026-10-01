from pathlib import Path

ROOT=Path(__file__).resolve().parent

def test_phase7_nav_and_route():
    index=(ROOT/'index.html').read_text(encoding='utf-8')
    app=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    assert '#analytics-home' in index
    assert 'Synthèse Analytiques' in index
    assert '>Analyse détaillée<' in index
    assert "h==='#analytics-home'" in app
    assert 'analyticsHomeView()' in app

def test_phase7_decision_path_and_single_analytics_source():
    js=(ROOT/'static'/'analytics-home.js').read_text(encoding='utf-8')
    for label in ['Signal','Explication','Périmètre','Preuves','Drilldown','Action']:
        assert f'>{label}<' in js or f'>{label}</h2>' in js
    assert js.count("/api/quality/pilotage?")==1
    assert '/api/quality/overview' not in js
    assert '/api/quality/agent-activity' not in js
    assert '/api/quality/distributions' not in js
    assert '/api/quality/suspicious-calls' not in js

def test_phase7_preserves_noncausal_action_wording_and_quality_boundaries():
    js=(ROOT/'static'/'analytics-home.js').read_text(encoding='utf-8')
    assert 'Elle ne sera jamais présentée comme cause certaine' in js
    assert 'historique, pas connectés Live' in js
    assert 'Ce n’est pas un classement de performance' in js
    assert 'Les écrans détaillés restent disponibles' in js

def test_phase7_mobile_styles_exist():
    css=(ROOT/'static'/'quality.css').read_text(encoding='utf-8')
    assert 'Phase 7 - Analytics decision path' in css
    assert '@media(max-width:520px)' in css
    assert '.ah-drill-grid .button{width:100%}' in css
