from pathlib import Path
ROOT=Path(__file__).resolve().parent
js=(ROOT/'static/live-views.js').read_text(encoding='utf-8')
css=(ROOT/'static/collection.css').read_text(encoding='utf-8')

def test_default_agents_view():
    assert "||'agents'" in js
    assert '<option value="agents">Agents</option>' in js
    assert '<option value="scopes">Campagnes / périmètres</option>' in js
    assert '<option value="split">Double vue</option>' in js

def test_single_primary_workspace():
    assert 'live-supervision-main' in js
    assert 'live-supervision-rail' in js
    assert 'live-detail-drawer' not in js
    assert 'live-kpis-wrap' in js
    assert 'live-layout-select' in js
    assert 'grid-template-columns:150px minmax(0,1fr)' in css
    assert '.live-ops-board[data-layout="agents"]>.live-scope-panel{display:none!important}' in css
    assert '.live-ops-board[data-layout="scopes"]>.live-agent-panel{display:none!important}' in css

def test_secondary_content_not_permanent():
    assert 'Qualité certifiée' not in js
    assert 'Analyse qualité' in js
    assert 'Fiabilité / limites' not in js
    assert 'Règles / alertes' in js
    assert '<summary>Détails</summary>' not in js
    assert '<summary class="button ghost">Plus</summary>' in js

if __name__=='__main__':
    tests=[test_default_agents_view,test_single_primary_workspace,test_secondary_content_not_permanent]
    for t in tests:t();print('OK',t.__name__)
    print(f'{len(tests)}/{len(tests)} tests UI RC29.3 OK')
