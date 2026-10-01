from pathlib import Path

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static/live-views.js').read_text(encoding='utf-8')
CSS=(ROOT/'static/collection.css').read_text(encoding='utf-8')


def test_vital_status_is_always_in_primary_live_shell():
    assert 'live-quality-hero' in JS
    assert '<span>Qualité</span>' in JS
    assert '<span>Alertes</span>' in JS
    assert '<span>Hermes</span>' in JS
    assert 'hermesAge' in JS
    assert '#live-health-dynamic p{display:flex!important' in CSS


def test_desktop_rail_is_wider_and_collapsible_with_persistence():
    assert 'grid-template-columns:minmax(220px,240px) minmax(0,1fr)!important' in CSS
    assert 'id="live-rail-toggle"' in JS
    assert 'data-rail-collapsed' not in JS  # dataset is assigned dynamically, not hardcoded markup
    assert "main.dataset.railCollapsed=liveSupervisionState.railCollapsed?'1':'0'" in JS
    assert "localStorage.getItem('nelyio.live.railCollapsed')==='1'" in JS
    assert "localStorage.setItem('nelyio.live.railCollapsed'" in JS
    assert 'grid-template-columns:128px minmax(0,1fr)!important' in CSS


def test_operational_text_is_at_least_12px_in_final_phase4_overrides():
    phase=CSS[CSS.index('/* RC29.4 Phase 4') :]
    assert '.live-agent-ops-table th' in phase and 'font-size:12px!important' in phase
    assert '.live-agent-ops-table small' in phase and 'font-size:12px!important' in phase
    assert '.live-duration-label' in phase and 'font-size:12px!important' in phase
    assert '.live-detail-drawer>summary{font-size:12px!important' in phase
    assert '.live-quality-status-compact span{font-size:12px!important' in phase


def test_agent_states_have_color_plus_non_text_shape():
    phase=CSS[CSS.index('/* RC29.4 Phase 4') :]
    for state in ('call','hold','ready','pause','wrap','offline','unobserved','arrival','inactive_context','other'):
        assert f'.live-state.{state}:before' in phase
    assert '.live-state.unobserved{' in phase and 'border-style:dashed!important' in phase


def test_one_scroll_region_per_operational_column_and_sticky_headers():
    phase=CSS[CSS.index('/* RC29.4 Phase 4') :]
    assert '.live-agent-roster-panel>.live-monitor-scroll' in phase
    assert '.live-scope-panel>.live-monitor-scope' in phase
    assert 'overflow-y:auto!important' in phase
    assert '.live-scope-panel>.live-monitor-scope thead th' in phase
    assert 'position:sticky!important' in phase
    assert '.live-supervision-simple{height:calc(100vh - 108px)!important' in phase
