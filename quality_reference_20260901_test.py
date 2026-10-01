"""Validation rejouable de la logique Qualité Nelyio sur l'export SIMPLIFY2 du 01/09/2026.

Usage:
  python quality_reference_20260901_test.py --zip "C:\\...\\SIMPLIFY2.2026-09-01.export.zip"

Le test travaille exclusivement dans des bases SQLite temporaires extraites de
``audit_empty_schemas.zip``. Il ne lit ni ne modifie les bases de production.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ['NELYIO_FORCE_SQLITE'] = '1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC'] = '1'
sys.path.insert(0, str(ROOT))

EXPECTED = {
    'received': 12115,
    'closed': 599,
    'overflow': 20,
    'rerouted_no_agent': 2,
    'hangup_before_queue': 337,
    'abandoned': 2070,
    'treated_agent': 9087,
    'answered': 8650,
    'lost_with_agent': 163,
    'rerouted_agent': 274,
    'transferred': 65,
    'completed': 8748,
    'qos_numerator': 9087,
    'qos_denominator': 11179,
    'reference_qos_numerator': 9087,
    'reference_qos_denominator': 11179,
    'treated_under_60_count': 5071,
    'outbound_count': 79,
}


def _install_isolated_runtime(tmp: Path) -> None:
    fixture = ROOT / 'audit_empty_schemas.zip'
    if not fixture.is_file():
        raise RuntimeError('audit_empty_schemas.zip absent')
    with zipfile.ZipFile(fixture) as z:
        z.extractall(tmp)
    (tmp / 'data').mkdir(exist_ok=True)

    import app_config
    import supervision_context as ctx
    import details_store
    import quality_service

    app_config.APP_DB = tmp / 'TECHIN_Stock_Manager.db'
    ctx.DEFAULT_DB = tmp / 'NELYIO_Supervision.db'
    ctx.DEFAULT_ADMIN_DB = tmp / 'TECHIN_Stock_Manager.db'
    facade = types.ModuleType('supervision')
    facade.DB = ctx.DEFAULT_DB
    facade.ADMIN_DB = ctx.DEFAULT_ADMIN_DB
    sys.modules['supervision'] = facade
    details_store.DETAILS_DB = tmp / 'Nelyio_Details.db'
    quality_service.QUALITY_DATA_FILE = tmp / 'data/quality_priorities.json'
    quality_service.QUALITY_SEED_FILE = tmp / 'absent.json'
    quality_service.QUALITY_REFERENCE_FILE = tmp / 'absent2.json'


def _eq(name: str, actual, expected) -> dict:
    return {'name': name, 'ok': actual == expected, 'actual': actual, 'expected': expected}


def run(reference_zip: Path) -> dict:
    if not reference_zip.is_file():
        raise FileNotFoundError(reference_zip)
    raw = reference_zip.read_bytes()
    with tempfile.TemporaryDirectory(prefix='nelyio-quality-reference-') as td:
        tmp = Path(td)
        _install_isolated_runtime(tmp)
        from quality_metrics import ingest_inbound, overview
        from supervision_db import connect

        ingested = ingest_inbound(raw, reference_zip.name, 1, 120)
        with connect() as con:
            con.execute('INSERT OR REPLACE INTO call_coverage(day,import_id) VALUES(?,?)', ('2026-09-01', 1))

        result = overview({
            'date_from': ['2026-09-01'],
            'date_to': ['2026-09-01'],
            'work_hours': ['0'],
            'threshold': ['60'],
        })
        total = result['total']
        checks = [_eq(k, total.get(k), v) for k, v in EXPECTED.items()]
        checks.extend([
            {
                'name': 'qos_percent_81_29',
                'ok': math.isclose(float(total.get('qos_percent')), 81.28634045979068, rel_tol=0, abs_tol=1e-9),
                'actual': total.get('qos_percent'),
                'expected': 81.28634045979068,
            },
            {
                'name': 'reference_qos_alias_81_29',
                'ok': math.isclose(float(total.get('reference_qos_percent')), 81.28634045979068, rel_tol=0, abs_tol=1e-9),
                'actual': total.get('reference_qos_percent'),
                'expected': 81.28634045979068,
            },
            {
                'name': 'asa_seconds_115_93',
                'ok': math.isclose(float(total.get('asa_seconds')), 115.9336414658303, rel_tol=0, abs_tol=1e-9),
                'actual': total.get('asa_seconds'),
                'expected': 115.9336414658303,
            },
            {
                'name': 'treated_under_60_percent_55_80',
                'ok': math.isclose(float(total.get('treated_under_60_percent')), 55.80499614834379, rel_tol=0, abs_tol=1e-9),
                'actual': total.get('treated_under_60_percent'),
                'expected': 55.80499614834379,
            },
            _eq('treated_subpartition',
                int(total.get('completed') or 0) + int(total.get('transferred') or 0) + int(total.get('rerouted_agent') or 0),
                int(total.get('treated_agent') or 0)),
            _eq('business_partition', int(total.get('classified_total') or 0), int(total.get('received') or 0)),
            _eq('coherence_delta', int(total.get('coherence_delta') or 0), 0),
            _eq('coherence_ok', total.get('coherence_ok'), True),
            _eq('integrity_ok', result.get('integrity', {}).get('ok'), True),
        ])
        return {
            'ok': all(c['ok'] for c in checks),
            'reference_zip': str(reference_zip),
            'ingest': ingested,
            'period': {'date_from': result['date_from'], 'date_to': result['date_to'], 'timezone': result['timezone']},
            'summary': {
                'received': total.get('received'),
                'treated_agent': total.get('treated_agent'),
                'answered': total.get('answered'),
                'abandoned': total.get('abandoned'),
                'qos_percent': total.get('qos_percent'),
                'asa_seconds': total.get('asa_seconds'),
                'treated_under_60_count': total.get('treated_under_60_count'),
                'treated_under_60_percent': total.get('treated_under_60_percent'),
                'outbound_count': total.get('outbound_count'),
                'coherence_delta': total.get('coherence_delta'),
            },
            'checks': checks,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--zip', dest='reference_zip', type=Path, required=True)
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    try:
        result = run(args.reference_zip)
    except Exception as exc:
        result = {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if result.get('error'):
        print('ECHEC -', result['error'])
        return 1
    s = result['summary']
    print('OK' if result['ok'] else 'ECHEC', '- référence Qualité 01/09/2026')
    print(f"Reçus={s['received']} | Traités={s['treated_agent']} | Répondus={s['answered']} | Abandonnés={s['abandoned']}")
    print(f"QoS={s['qos_percent']:.2f}% | ASA={s['asa_seconds']:.2f}s | <=60s={s['treated_under_60_percent']:.2f}% | OUTBOUND={s['outbound_count']}")
    print(f"Cohérence delta={s['coherence_delta']}")
    for check in result['checks']:
        if not check['ok']:
            print('ECHEC -', check['name'], ':', check.get('actual'), 'attendu', check.get('expected'))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
