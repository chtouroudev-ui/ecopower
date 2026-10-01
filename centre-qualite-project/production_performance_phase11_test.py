from datetime import datetime
from pathlib import Path

import performance_analysis as pa
import production_observability as obs


def _thresholds():
    return {
        'critical_seconds': 10.0,
        'warn_events_per_hour': 5,
        'critical_events_per_hour': 20,
        'http_log_seconds': 1.0,
        'analytics_log_seconds': 2.0,
    }


def _summary(rows=None, available=True):
    rows = rows or []
    return {
        'available': available,
        'last_hour': len(rows),
        'last_24h': len(rows),
        'top_24h': rows,
    }


def test_phase11_slow_summary_exposes_average_p95_and_total(tmp_path):
    path = tmp_path / 'http_slow.log'
    path.write_text(
        '2026-09-27 16:00:00 GET /api/quality/pilotage 1.000s\n'
        '2026-09-27 16:01:00 GET /api/quality/pilotage 2.000s\n'
        '2026-09-27 16:02:00 GET /api/quality/pilotage 4.000s\n',
        encoding='utf-8',
    )
    data = obs._slow_summary(path, obs._HTTP_SLOW, key_name='path', now=datetime(2026, 9, 27, 16, 5, 0))
    row = data['top_24h_detailed'][0]
    assert row['key'] == '/api/quality/pilotage'
    assert row['count'] == 3
    assert row['avg_seconds'] == 2.333
    assert row['p95_seconds'] == 4.0
    assert row['max_seconds'] == 4.0
    assert row['total_seconds'] == 7.0


def test_phase11_correlates_web_and_analytics_without_claiming_postgres_cause():
    perf = {
        'http': _summary([{'key':'/api/quality/pilotage','count':7,'avg_seconds':2.2,'p95_seconds':3.4,'max_seconds':4.2,'total_seconds':15.4}]),
        'analytics': _summary([{'key':'quality_pilotage','count':5,'avg_seconds':2.7,'p95_seconds':3.1,'max_seconds':3.8,'total_seconds':13.5}]),
    }
    out = pa.build(perf, {'ok':True,'latency_ms':3.1}, {'available':False}, _thresholds())
    finding = out['findings'][0]
    assert finding['code'] == 'WEB_ANALYTICS_CORRELATION'
    assert finding['scope'] == '/api/quality/pilotage'
    assert 'ne prouv' in finding['interpretation'].lower()
    assert 'postgresql' in finding['interpretation'].lower()
    assert out['automatic_tuning'] is False


def test_phase11_web_only_does_not_invent_worker_failure():
    perf = {
        'http': _summary([{'key':'/api/quality/overview','count':4,'max_seconds':2.2}]),
        'analytics': _summary([]),
    }
    out = pa.build(perf, {'ok':True,'latency_ms':2}, {'available':False}, _thresholds())
    finding = next(x for x in out['findings'] if x['scope'] == '/api/quality/overview')
    assert finding['code'] == 'WEB_WITHOUT_ANALYTICS_SLOW'
    assert 'ne prouve pas' in finding['interpretation'].lower()
    assert 'réseau/tls' in finding['next_step'].lower()


def test_phase11_soak_scenario_is_exposed_as_full_path_evidence():
    soak = {
        'available': True,
        'thresholds': {'warn_p95_seconds':2.0,'critical_max_seconds':10.0},
        'by_scenario': {'analytics': {'count':50,'median_s':1.2,'p95_s':3.5,'max_s':4.0}},
    }
    out = pa.build({'http':_summary([]),'analytics':_summary([])}, {'ok':True,'latency_ms':2}, soak, _thresholds())
    finding = next(x for x in out['findings'] if x['code'] == 'SOAK_P95_HIGH')
    assert finding['scope'] == '/api/quality/pilotage'
    assert 'parcours complet' in finding['interpretation'].lower()


def test_phase11_no_evidence_never_claims_system_is_fast():
    perf = {'http':_summary([], available=False),'analytics':_summary([], available=False)}
    out = pa.build(perf, {'ok':True,'latency_ms':1}, {'available':False}, _thresholds())
    assert out['status'] == 'DONNEES_INSUFFISANTES'
    assert not out['findings']
    assert any('absence' in x.lower() for x in out['limitations'])


def test_phase11_ui_and_reporter_are_read_only_and_replayable():
    root = Path(__file__).resolve().parent
    js = (root/'static'/'production-health.js').read_text(encoding='utf-8')
    bat = (root/'ANALYSER_PERFORMANCE_PRODUCTION.bat').read_text(encoding='utf-8')
    tool = (root/'tools'/'analyze_production_performance.py').read_text(encoding='utf-8')
    assert 'Analyse ciblée des performances' in js
    assert 'Aucune optimisation n’est appliquée automatiquement' in js
    assert 'performance_analysis.md' in js
    assert 'analyze_production_performance.py' in bat
    assert 'performance_analysis.json' in tool
    assert 'performance_analysis.md' in tool
