"""Phase E migration helpers for legacy hard-coded exclusion windows.

The old Support/Analytics/Reports UI exposed query-string flags such as
``exclude_12_13``.  Phase E keeps these flags readable for compatibility, but
allows administrators to convert them into explicit, audited Policies and then
switch the application to ``policy_only`` mode to prevent double exclusion.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app_db import db_connect, get_setting, set_setting
from policy_admin import save_policy
from support_filters import _support_excluded_slots

MODE_COMPAT = 'compat'
MODE_POLICY_ONLY = 'policy_only'
ALLOWED_MODES = {MODE_COMPAT, MODE_POLICY_ONLY}
DEFAULT_WEEKDAYS = [0, 1, 2, 3, 4]


def legacy_mode():
    mode = str(get_setting('governance_legacy_exclusion_mode', MODE_COMPAT) or MODE_COMPAT).strip().lower()
    return mode if mode in ALLOWED_MODES else MODE_COMPAT


def _time_text(minutes):
    minutes = max(0, min(24 * 60, int(minutes)))
    if minutes == 24 * 60:
        return '23:59'
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _payload_to_qs(data):
    data = data or {}
    qs = {}
    for key in ('exclude_12_13', 'exclude_13_14', 'exclude_custom_from', 'exclude_custom_to'):
        value = data.get(key)
        if value not in (None, '', False, 0):
            qs[key] = ['1' if value is True else str(value)]
    return qs


def legacy_slots_from_payload(data):
    return _support_excluded_slots(_payload_to_qs(data), respect_mode=False)


def _migration_key(start_min, end_min, weekdays, target='GLOBAL', target_key='*', modules=()):
    raw = json.dumps({'start': int(start_min), 'end': int(end_min), 'weekdays': list(weekdays), 'target': target, 'target_key': target_key, 'modules': sorted(modules)}, sort_keys=True)
    return 'legacy-time-' + hashlib.sha256(raw.encode('utf-8')).hexdigest()[:20]


def migration_status():
    mode = legacy_mode()
    with db_connect() as con:
        rows = [dict(r) for r in con.execute('''
            SELECT m.*,p.name AS policy_name,p.enabled AS policy_enabled,p.deleted_at AS policy_deleted_at
            FROM nelyio_governance_migrations m
            LEFT JOIN nelyio_policies p ON p.id=m.policy_id
            ORDER BY m.created_at DESC,m.id DESC
        ''').fetchall()]
    return {
        'mode': mode,
        'legacy_filters_applied': mode == MODE_COMPAT,
        'migrated_at': get_setting('governance_legacy_exclusion_migrated_at', ''),
        'migrated_by': get_setting('governance_legacy_exclusion_migrated_by', ''),
        'migrations': rows,
    }


def set_legacy_mode(mode, actor):
    mode = str(mode or '').strip().lower()
    if mode not in ALLOWED_MODES:
        raise ValueError('Mode de compatibilité legacy invalide')
    with db_connect() as con:
        old = legacy_mode()
        set_setting(con, 'governance_legacy_exclusion_mode', mode, actor)
        con.execute('INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)',
                    (actor, 'NELYIO_LEGACY_EXCLUSION_MODE', f'{old} -> {mode}'))
        con.commit()
    return migration_status()


def migrate_legacy_exclusions(data, actor):
    data = data or {}
    slots = legacy_slots_from_payload(data)
    if not slots:
        raise ValueError('Choisir au moins une ancienne plage à migrer')
    weekdays = []
    for value in data.get('weekdays', DEFAULT_WEEKDAYS) if isinstance(data.get('weekdays', DEFAULT_WEEKDAYS), list) else DEFAULT_WEEKDAYS:
        try:
            n = int(value)
        except Exception:
            continue
        if 0 <= n <= 6 and n not in weekdays:
            weekdays.append(n)
    if not weekdays:
        weekdays = list(DEFAULT_WEEKDAYS)
    target = str(data.get('target_type') or 'GLOBAL').upper()
    target_key = str(data.get('target_key') or '*').strip()
    if target not in ('GLOBAL', 'GROUP', 'AGENT'):
        raise ValueError('Cible de migration invalide')
    if target == 'GLOBAL':
        target_key = '*'
    if target != 'GLOBAL' and not target_key:
        raise ValueError('Choisir une cible pour la migration')
    modules = [m for m in data.get('modules', ['support', 'analytics', 'reports', 'details']) if m in ('support', 'analytics', 'reports', 'details')]
    if not modules:
        modules = ['support', 'analytics', 'reports', 'details']

    created = []
    existing = []
    for start_min, end_min, label in slots:
        key = _migration_key(start_min, end_min, weekdays, target, target_key, modules)
        with db_connect() as con:
            row = con.execute('SELECT * FROM nelyio_governance_migrations WHERE migration_key=? AND status=\'MIGRATED\'', (key,)).fetchone()
            if row:
                existing.append(dict(row))
                continue
        time_from = _time_text(start_min)
        # Policy engine treats end as exclusive. 23:59 is the closest legal UI
        # value for a theoretical 24:00 legacy bound.
        time_to = _time_text(end_min)
        payload = {
            'name': f'Migration ancienne exclusion {label}',
            'description': f'Policy créée automatiquement en Phase E depuis l’ancienne plage codée en dur {label}. Les logs bruts restent conservés.',
            'enabled': True,
            'policy_type': 'PAUSE',
            'targets': [{'target_type': target, 'target_key': target_key}],
            'weekdays': weekdays,
            'time_from': time_from,
            'time_to': time_to,
            'actions': {
                'exclude_statistics': True,
                'exclude_lost_time': True,
                'exclude_score': True,
                'mark_authorized': True,
                'reclassify': 'Période autorisée (migration legacy)',
            },
            'modules': modules,
            'priority': int(data.get('priority') or 50),
        }
        policy = save_policy(payload, actor)
        source = {
            'label': label, 'start_minute': start_min, 'end_minute': end_min,
            'weekdays': weekdays, 'target_type': target, 'target_key': target_key,
            'modules': modules,
        }
        with db_connect() as con:
            con.execute('''INSERT INTO nelyio_governance_migrations(
                migration_key,source_json,policy_id,status,created_by
            ) VALUES(?,?,?,?,?)''', (key, json.dumps(source, ensure_ascii=False, separators=(',', ':')), int(policy['id']), 'MIGRATED', actor))
            con.execute('INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)',
                        (actor, 'NELYIO_LEGACY_EXCLUSION_MIGRATED', f'{label} -> Policy #{policy["id"]}'))
            con.commit()
        created.append(policy)

    if data.get('switch_to_policy_only', True):
        with db_connect() as con:
            set_setting(con, 'governance_legacy_exclusion_mode', MODE_POLICY_ONLY, actor)
            set_setting(con, 'governance_legacy_exclusion_migrated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), actor)
            set_setting(con, 'governance_legacy_exclusion_migrated_by', actor, actor)
            con.commit()
    return {'created': created, 'existing': existing, 'status': migration_status()}
