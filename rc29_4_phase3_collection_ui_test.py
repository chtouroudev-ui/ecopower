from pathlib import Path

ROOT = Path(__file__).resolve().parent
JS = (ROOT / 'static' / 'collection.js').read_text(encoding='utf-8')
CSS = (ROOT / 'static' / 'collection.css').read_text(encoding='utf-8')


def test_auto_switch_and_operational_banner_exist():
    assert 'id="collection-auto-toggle"' in JS
    assert 'Détection automatique' in JS
    assert 'collection-auto-banner' in JS
    assert 'En attente d’Edge' in JS
    assert 'Onglet détecté' in JS
    assert 'Capture en cours' in JS
    assert 'Arrêtée manuellement — réactiver' in JS
    assert 'Réactiver aujourd’hui' in JS


def test_schedule_days_and_save_are_exposed():
    assert 'name="active_days"' in JS
    assert 'Jours actifs pour la détection automatique' in JS
    assert 'id="collection-save"' in JS
    assert "act('configure')" in JS
    assert 'start_time' in JS and 'end_time' in JS


def test_manual_fallbacks_remain_available():
    assert 'id="collection-probe"' in JS
    assert 'id="collection-start"' in JS
    assert 'id="collection-stop"' in JS
    assert 'Démarrer manuellement' in JS


def test_probe_does_not_auto_pin_single_target():
    assert "if(result.targets.length===1)select.value=result.targets[0].id" not in JS
    assert "else select.value=''" in JS
    assert 'Automatique si un seul onglet' in JS


def test_auto_api_is_called_explicitly():
    assert "api('/api/collection/auto'" in JS
    assert 'JSON.stringify({enabled:!!enabled})' in JS


def test_advanced_cdp_options_and_local_security_copy_remain():
    assert 'Options avancées · connexion CDP et confidentialité' in JS
    assert '127.0.0.1' in JS
    assert 'Aucun audio, cookie, mot de passe, JavaScript injecté ou corps HTTP brut' in JS


def test_phase3_css_has_switch_banner_and_day_chips():
    assert '.collection-auto-control' in CSS
    assert '.collection-switch' in CSS
    assert '.collection-auto-banner' in CSS
    assert '.collection-days' in CSS
