from pathlib import Path

ROOT=Path(__file__).resolve().parent
JS=(ROOT/'static/live-views.js').read_text(encoding='utf-8')
CSS=(ROOT/'static/collection.css').read_text(encoding='utf-8')


def test_quick_state_chips_have_required_counters():
    assert 'live-agent-state-chips' in JS
    assert "chip('call','En appel',c.call)" in JS
    assert "chip('ready','Disponible',c.ready)" in JS
    assert "chip('pause','Pause',c.pause)" in JS
    assert "chip('wrap','Post-appel',c.wrap)" in JS
    assert "chip('unobserved','Non observé',c.unobserved)" in JS
    assert "chip('hold','Mise en attente',c.hold)" in JS
    assert "state==='call'?['call','hold'].includes(bucket)" in JS
    assert "state==='call'?['call','hold'].includes(bucket):bucket===state" in JS


def test_alert_card_direct_navigation_targets_agent_or_campaign():
    assert 'data-live-alert-target="1"' in JS
    assert 'data-live-alert-scope-type' in JS
    assert 'data-live-alert-agent' in JS
    assert "scopeType==='CAMPAIGN'" in JS
    assert "scopeType==='AGENT'?scopeKey:agent" in JS
    assert "liveSupervisionState.layout='agents'" in JS
    assert "liveSupervisionState.layout='scopes'" in JS
    assert 'openAlertTarget' in JS


def test_layout_and_group_are_persisted():
    assert "localStorage.getItem('nelyio.live.layout')" in JS
    assert "localStorage.setItem('nelyio.live.layout'" in JS
    assert "localStorage.getItem('nelyio.live.group')" in JS
    assert "localStorage.setItem('nelyio.live.group'" in JS
    assert 'allowed_group_ids' in JS  # saved group is checked against access scope


def test_wall_mode_hides_application_chrome_and_uses_fullscreen_when_possible():
    assert 'id="live-wall-toggle"' in JS
    assert "document.body.classList.add('live-wall-active')" in JS
    assert 'requestFullscreen' in JS
    assert 'document.exitFullscreen' in JS
    assert 'body.live-wall-active .sidebar' in CSS
    assert 'body.live-wall-active .topbar' in CSS
    assert '.live-supervision-simple:fullscreen' in CSS


def test_agent_dom_reconciliation_contract_is_still_present():
    assert 'function livePatchAgentRoster(rows)' in JS
    assert 'data-live-agent-id' in JS
    assert "body.appendChild(tr)" in JS
    assert 'tr.dataset.liveSignature' in JS
