"""Qualite F3.8: configured priorities and call observations remain separate."""
from __future__ import annotations
import copy
import json
import os
import re
import db_compat as sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import app_config as cfg
from quality_importer import (text as _text, agent_key as _canonical_admin_key, integer, activation, extract_snapshot)

QUALITY_DATA_FILE = cfg.BASE / "data" / "quality_priorities.json"
QUALITY_SEED_FILE = cfg.BASE / "data" / "quality_seed_20260911.json"
QUALITY_REFERENCE_FILE = cfg.BASE / "data" / "quality_reference_campaigns.json"
_IMPORT_LOCK = threading.RLock()
_RECOVERY_LOCK = threading.RLock()
_RECOVERY_STATE = {"last_attempt": 0.0, "result": "not_attempted"}
_PRIORITY_CACHE_LOCK = threading.RLock()
_PRIORITY_CACHE = {"stamp": 0.0, "fingerprint": None, "data": None}
try:
    _PRIORITY_CACHE_SECONDS = max(2.0, min(300.0, float(os.environ.get("NELYIO_QUALITY_CATALOG_CACHE_SECONDS", "60"))))
except (TypeError, ValueError):
    _PRIORITY_CACHE_SECONDS = 60.0


def _file_fingerprint(path):
    try:
        st = Path(path).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (0, 0)


def _priority_fingerprint():
    base = Path(QUALITY_DATA_FILE)
    return (
        _file_fingerprint(base),
        _file_fingerprint(QUALITY_REFERENCE_FILE),
        _file_fingerprint(base.with_name("quality_last_import.json")),
        _file_fingerprint(base.with_name("quality_scope.revision")),
    )


def invalidate_quality_priorities_cache():
    with _PRIORITY_CACHE_LOCK:
        _PRIORITY_CACHE.update(stamp=0.0, fingerprint=None, data=None)


def has_quality_agent_queue_assignments(raw) -> bool:
    """True only when the snapshot contains configured agent->queue assignments.

    Observed/demo activity is deliberately not accepted as an analytical group
    source: group KPIs are defined by real configured ACTIVE file assignments.
    """
    for agent in (raw or {}).get('agents', []) or []:
        for queue in agent.get('queues', []) or []:
            if queue.get('assignment_source') not in ('observed_activity', 'demo'):
                try:
                    if int(queue.get('line_id') or 0) > 0:
                        return True
                except (TypeError, ValueError):
                    continue
    return False


def recover_quality_assignments_from_archive(current=None, *, cooldown_seconds=60.0, max_candidates=12):
    """Restore a missing Agents.csv assignment snapshot from durable imports.

    The recovery is conservative: only completed/partial import jobs are used,
    sources whose workflow explicitly skipped Quality as an inactive reference
    are ignored, paths must remain inside import_archive, and the same 100 MB
    source limit as normal imports is enforced. If no authoritative source is
    available the current snapshot is returned unchanged.
    """
    import time
    current = _read_raw() if current is None else current
    if has_quality_agent_queue_assignments(current):
        return current
    now_mono = time.monotonic()
    with _RECOVERY_LOCK:
        if has_quality_agent_queue_assignments(current):
            return current
        if now_mono - float(_RECOVERY_STATE.get('last_attempt') or 0.0) < float(cooldown_seconds):
            return current
        _RECOVERY_STATE['last_attempt'] = now_mono
        try:
            import supervision_context as context
            from supervision_db import connect as supervision_connect
            archive = (context.db_path().parent / 'import_archive').resolve()
            if not archive.is_dir():
                _RECOVERY_STATE['result'] = 'archive_missing'
                return current
            candidates=[]
            with supervision_connect() as con:
                rows=con.execute("""
                    SELECT filename,source_file,status,result_json,updated_at
                    FROM import_jobs
                    WHERE status IN ('completed','partial')
                    ORDER BY updated_at DESC
                    LIMIT ?
                """,(max(1,int(max_candidates)),)).fetchall()
            for row in rows:
                try:
                    result_json=row['result_json'] if hasattr(row,'keys') else row[3]
                    result=json.loads(result_json or '{}')
                    qstep=result.get('quality_import') or {}
                    if qstep.get('reason') == 'inactive_reference':
                        continue
                    filename=str(row['filename'] if hasattr(row,'keys') else row[0])
                    source_file=str(row['source_file'] if hasattr(row,'keys') else row[1])
                    source=(archive/source_file).resolve()
                    if source.parent != archive or not source.is_file():
                        continue
                    size=source.stat().st_size
                    if size <= 0 or size > 100*1024*1024:
                        continue
                    candidates.append((source,filename))
                except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError):
                    continue
            for source,filename in candidates:
                try:
                    incoming=extract_quality_snapshot(source.read_bytes(),filename)
                except (OSError,ValueError,TypeError):
                    continue
                if not incoming or 'agent_queues' not in set(incoming.get('scopes',[])) or not has_quality_agent_queue_assignments(incoming):
                    continue
                merged,accepted,_ignored=merge_quality_snapshot(current,incoming)
                if 'agent_queues' not in accepted or not has_quality_agent_queue_assignments(merged):
                    continue
                merged['recovered_from_archive']=True
                merged['recovery_source_archive']=source.name
                merged['recovery_updated_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
                if Path(QUALITY_DATA_FILE).is_file():
                    try:
                        previous=json.loads(Path(QUALITY_DATA_FILE).read_text(encoding='utf-8-sig'))
                        save_quality_snapshot(previous,Path(QUALITY_DATA_FILE).with_name('quality_priorities.before_recovery.json'))
                    except (OSError,ValueError):
                        pass
                save_quality_snapshot(merged)
                invalidate_quality_priorities_cache()
                _RECOVERY_STATE['result']='recovered:'+source.name
                try:
                    from quality_scope import invalidate_quality_scope_cache
                    invalidate_quality_scope_cache()
                except Exception:
                    pass
                return merged
            _RECOVERY_STATE['result']='no_authoritative_agents_snapshot'
        except Exception as exc:
            _RECOVERY_STATE['result']='recovery_error:'+type(exc).__name__
        return current

def _admin_campaign_groups() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    groups: list[dict[str, Any]] = []
    mapping: dict[str, list[dict[str, Any]]] = {}
    if not sqlite3.runtime_database_available(cfg.APP_DB):
        return groups, mapping
    try:
        con = sqlite3.connect(str(cfg.APP_DB), timeout=5)
        con.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "user_groups" in tables:
                groups = [dict(r) for r in con.execute("SELECT id,name,description FROM user_groups ORDER BY name COLLATE NOCASE")]
            if "quality_group_campaigns" in tables:
                for r in con.execute("""
                    SELECT q.campaign_name,g.id group_id,g.name group_name
                    FROM quality_group_campaigns q JOIN user_groups g ON g.id=q.group_id
                    ORDER BY q.campaign_name COLLATE NOCASE,g.name COLLATE NOCASE
                """):
                    mapping.setdefault(str(r["campaign_name"]).casefold(), []).append({"group_id": r["group_id"], "group_name": r["group_name"]})
        finally:
            con.close()
    except sqlite3.Error:
        pass
    return groups, mapping




def _admin_agent_directory() -> dict[str, dict[str, Any]]:
    """Return numeric agent identities from Administration without imports.

    This deliberately avoids importing ``agent_directory`` because that module
    depends on the supervision stack and can create a circular import when the
    Quality service is loaded standalone (tests, maintenance scripts, startup).
    """
    users: dict[str, dict[str, Any]] = {}
    if not sqlite3.runtime_database_available(cfg.APP_DB):
        return users
    try:
        con = sqlite3.connect(str(cfg.APP_DB), timeout=5)
        con.row_factory = sqlite3.Row
        try:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "user_directory" not in tables:
                return users
            has_members = "user_group_members" in tables and "user_groups" in tables
            if has_members:
                rows = con.execute("""
                    SELECT d.user_key,d.user_identifier,d.first_name,d.last_name,
                           m.group_id,g.name AS group_name
                    FROM user_directory d
                    LEFT JOIN user_group_members m ON m.user_key=d.user_key
                    LEFT JOIN user_groups g ON g.id=m.group_id
                """)
            else:
                rows = con.execute("SELECT user_key,user_identifier,first_name,last_name,NULL group_id,'' group_name FROM user_directory")
            for row in rows:
                ident = _text(row["user_identifier"] or row["user_key"])
                key = _canonical_admin_key(ident)
                if not key or not re.fullmatch(r"\d+", key):
                    continue
                users[key] = {
                    "user_key": key,
                    "user_identifier": ident,
                    "first_name": _text(row["first_name"]),
                    "last_name": _text(row["last_name"]),
                    "display_name": " ".join(x for x in (_text(row["first_name"]), _text(row["last_name"])) if x).strip() or ident,
                    "group_id": row["group_id"],
                    "group_name": _text(row["group_name"]),
                }
        finally:
            con.close()
    except sqlite3.Error:
        return users
    return users

def _split_support_name(value: Any) -> tuple[str, str]:
    clean = " ".join(_text(value).split())
    if not clean:
        return "", ""
    parts = clean.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _project_roster_and_campaigns(active_campaigns: set[str], include_observed: bool = False) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]], dict[str, Any]]:
    """Read the real Nelyio roster and observed campaign assignments.

    Quality priority exports are configuration snapshots and may legitimately
    contain only a subset of agents.  The UI must nevertheless show the whole
    operational roster.  We therefore merge the Administration directory with
    Support activity observations.  Observed campaigns are *not* treated as
    priority configuration: they are only associations and keep both priority
    fields empty until a compatible priority export supplies them.
    """
    roster: dict[str, dict[str, Any]] = {}
    observed: dict[str, set[str]] = {}
    meta: dict[str, Any] = {"latest_import": "", "latest_imported_at": "", "reference_day": ""}

    # Administration directory is the authoritative roster/name source.
    admin_users = _admin_agent_directory()
    for key, user in admin_users.items():
        ident = _text(user.get("user_identifier") or key)
        roster[key] = {
            "agent_id": key,
            "agent_last_name": _text(user.get("last_name")),
            "agent_first_name": _text(user.get("first_name")),
            "login": "S" + key if key.isdecimal() else ident,
            "queues": [],
            "campaign_assignments": [],
            "default_campaign_name": None,
        }
    canonical_admin_key = _canonical_admin_key

    # Support activity provides real agents seen in production plus campaign
    # associations.  Only campaigns in the active Quality catalogue are used,
    # which avoids re-introducing old/renamed campaigns from historical logs.
    try:
        import supervision_context as state
        db_path = state.db_path()
        if sqlite3.runtime_database_available(db_path):
            con = sqlite3.connect(str(db_path), timeout=10)
            con.row_factory = sqlite3.Row
            try:
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "imports" in tables:
                    row = con.execute("SELECT name,imported_at,reference_day FROM imports ORDER BY id DESC LIMIT 1").fetchone()
                    if row:
                        meta.update(latest_import=_text(row["name"]), latest_imported_at=_text(row["imported_at"]), reference_day=_text(row["reference_day"]))
                if "activities" in tables and (not roster or include_observed):
                    # Administration + configured agent snapshots normally provide
                    # the complete roster. Historical activity is a fallback only;
                    # scanning it on every Priorities/Teams read made latency grow
                    # with retention even though campaigns are not the group source.
                    # Only active coverage can contribute to the fallback roster.
                    # Older builds grouped the complete historical activity table
                    # merely to obtain one name per agent, making Priorities/Teams
                    # grow with history instead of current configuration.
                    if sqlite3.postgres_enabled():
                        latest_names = con.execute("""
                            SELECT DISTINCT ON (a.agent) a.agent,a.name
                            FROM activities a
                            JOIN (SELECT DISTINCT import_id FROM coverage) cov ON cov.import_id=a.import_id
                            WHERE TRIM(COALESCE(a.agent,''))<>'' AND a.agent<>'0'
                            ORDER BY a.agent,a.import_id DESC,a.id DESC
                        """).fetchall()
                    else:
                        latest_names = con.execute("""
                            SELECT a.agent,a.name
                            FROM activities a
                            JOIN (
                              SELECT a2.agent,MAX(a2.id) last_id
                              FROM activities a2
                              JOIN (SELECT DISTINCT import_id FROM coverage) cov2 ON cov2.import_id=a2.import_id
                              WHERE TRIM(COALESCE(a2.agent,''))<>'' AND a2.agent<>'0'
                              GROUP BY a2.agent
                            ) x ON x.last_id=a.id
                        """).fetchall()
                    for row in latest_names:
                        raw_agent = _text(row["agent"])
                        key = canonical_admin_key(raw_agent)
                        if not key or not re.fullmatch(r"\d+", key):
                            continue
                        if key not in roster:
                            first, last = _split_support_name(row["name"])
                            roster[key] = {
                                "agent_id": key,
                                "agent_last_name": last,
                                "agent_first_name": first,
                                "login": "S" + key if key.isdecimal() else raw_agent,
                                "queues": [],
                                "campaign_assignments": [],
                                "default_campaign_name": None,
                            }
                    # Campaign observations are diagnostic only and are not part
                    # of the Group -> File -> ACTIVE Agent business rule. Avoid a
                    # DISTINCT scan on every priorities read unless explicitly requested.
                    if include_observed:
                        for row in con.execute("""
                            SELECT DISTINCT a.agent,a.campaign
                            FROM activities a
                            JOIN (SELECT DISTINCT import_id FROM coverage) cov ON cov.import_id=a.import_id
                            WHERE TRIM(COALESCE(a.agent,''))<>'' AND a.agent<>'0'
                              AND TRIM(COALESCE(a.campaign,''))<>''
                        """):
                            key = canonical_admin_key(row["agent"])
                            campaign = _text(row["campaign"])
                            if not key or not re.fullmatch(r"\d+", key) or campaign.casefold() not in active_campaigns:
                                continue
                            observed.setdefault(key, set()).add(campaign)
            finally:
                con.close()
    except (sqlite3.Error, OSError):
        pass

    return roster, observed, meta



def _read_raw(path=None):
    source = Path(path or QUALITY_DATA_FILE)
    raw = json.loads(source.read_text(encoding='utf-8-sig')) if source.is_file() else {}
    # The supplied historical export is a read-only bootstrap, never a patch
    # overwriting an already imported configuration. Its date stays visible.
    if path is None and raw.get('source_type', 'empty') in ('demo', 'empty') and QUALITY_SEED_FILE.is_file():
        raw = json.loads(QUALITY_SEED_FILE.read_text(encoding='utf-8-sig'))
        raw['bootstrap_source'] = True
    return raw


def _num(v, agent=False):
    # Do not fabricate a value by clamping. Invalid legacy values are unknown.
    try: return integer(v, 'Priorite', 99 if agent else None)
    except ValueError: return None


def _queue(raw):
    q = dict(raw)
    q['line_id'] = int(raw.get('line_id') or 0)
    q['line_name'] = _text(raw.get('line_name'))
    q['agent_priority_level'] = _num(raw.get('agent_priority_level', raw.get('priority_level')), True)
    q['priority_level'] = q['agent_priority_level']  # no fallback to base or zero
    q['base_priority_level'] = _num(raw.get('base_priority_level'))
    if 'activation_state' not in q:
        try: q.update(activation(q))
        except ValueError: q.update(activation({}))
    return q


def _campaign_key(c):
    cid = _text(c.get('campaign_id'))
    if cid.startswith('REF-'): cid = ''  # F3.5 reference IDs were not telephony IDs
    return cid or 'name:' + _text(c.get('campaign_name')).casefold()


def _load_quality_priorities_uncached(path: Path | None = None) -> dict[str, Any]:
    raw = _read_raw(path)
    # Interactive reads must never scan durable import archives. If the
    # configured agent->file snapshot is missing, the Import Worker performs
    # conservative recovery in the background and invalidates the caches.
    catalog = {}
    for c in raw.get('campaigns', []):
        c = {'campaign_name': c} if isinstance(c, str) else dict(c)
        c['campaign_id'] = '' if _text(c.get('campaign_id')).startswith('REF-') else _text(c.get('campaign_id'))
        c['campaign_name'] = _text(c.get('campaign_name'))
        c['base_priority_level'] = _num(c.get('base_priority_level'))
        catalog[_campaign_key(c)] = c
    # Keep the original reference names, but never its demo agent/IDs.
    reference = Path(QUALITY_DATA_FILE)
    if path is None and (reference.is_file() or QUALITY_REFERENCE_FILE.is_file()):
        ref = json.loads(reference.read_text(encoding='utf-8-sig')) if reference.is_file() else {}
        if QUALITY_REFERENCE_FILE.is_file():
            ref = dict(campaigns=ref.get('campaigns', []) + json.loads(QUALITY_REFERENCE_FILE.read_text(encoding='utf-8-sig')))
        names = {c['campaign_name'].casefold() for c in catalog.values() if c['campaign_name']}
        for c in ref.get('campaigns', []):
            if isinstance(c, dict) and c.get('campaign_name', '').casefold() not in names:
                name = c.get('campaign_name', '')
                catalog['name:' + name.casefold()] = dict(campaign_id='', campaign_name=name, base_priority_level=None)
                names.add(name.casefold())
    # Drop name-only reference duplicates once a real ID has been resolved.
    named_ids = {c['campaign_name'].casefold() for c in catalog.values() if c['campaign_id'] and c['campaign_name']}
    catalog = {k:c for k,c in catalog.items() if c['campaign_id'] or c['campaign_name'].casefold() not in named_ids}
    groups, campaign_groups = _admin_campaign_groups()
    for c in catalog.values():
        c['groups'] = campaign_groups.get(c['campaign_name'].casefold(), [])
        c['display_name'] = c['campaign_name'] or ('Campagne ' + c['campaign_id'] + ' (nom non fourni)')
    roster, _observed, project_meta = _project_roster_and_campaigns({c['campaign_name'].casefold() for c in catalog.values()})
    admin = _admin_agent_directory()
    raw_agents = raw.get('agents', [])
    if raw.get('source_type') == 'demo' and roster: raw_agents = []
    agents = {}
    queue_map = {int(q['line_id']):dict(q) for q in raw.get('queues', []) if q.get('line_id')}
    for a in raw_agents:
        aid = _canonical_admin_key(a.get('agent_id') or a.get('login'))
        if not aid: continue
        a = dict(a)
        a['agent_id'] = aid
        a['queues'] = [_queue(q) for q in a.get('queues', [])]
        for q in a['queues']:
            qc = queue_map.setdefault(q['line_id'], dict(line_id=q['line_id'], line_name=q['line_name'], base_priority_level=q['base_priority_level'], campaign_ids=[]))
            if not qc.get('line_name') and q['line_name']: qc['line_name'] = q['line_name']
        agents[aid] = a
    for aid, a in roster.items():
        if aid not in agents: agents[aid] = dict(a)
    observation_map = {}
    for o in raw.get('observations', []):
        observation_map.setdefault(int(o['line_id']), []).append(dict(o))
    for lid, q in queue_map.items():
        q['base_priority_level'] = _num(q.get('base_priority_level'))
        q['campaigns'] = [catalog[cid] for cid in q.get('campaign_ids', []) if cid in catalog]
        labels = list(dict.fromkeys(c['display_name'] for c in q['campaigns']))
        q['display_name'] = _text(q.get('line_name')) or (' / '.join(labels) if labels else 'Nom de file non fourni')
        q['name_source'] = 'configuration' if q.get('line_name') else ('campaign_correspondence' if labels else 'missing')
        q['observations'] = []
        for o in observation_map.get(lid, []):
            c = catalog.get(o['campaign_id'], {})
            o['campaign_name'] = c.get('campaign_name', '')
            o['display_name'] = c.get('display_name', o['campaign_id'])
            q['observations'].append(o)
        q['groups'] = list({str(g['group_id']):g for c in q['campaigns'] for g in c.get('groups', [])}.values())
    for aid, a in agents.items():
        user = admin.get(aid, {})
        for field in ('agent_last_name', 'agent_first_name', 'login'):
            if not a.get(field): a[field] = a.get({'agent_last_name':'last_name', 'agent_first_name':'first_name'}.get(field, field)) or roster.get(aid, {}).get(field, '')
        a['directory_name'] = _text(user.get('display_name'))
        a['group_id'] = user.get('group_id')
        a['group_name'] = _text(user.get('group_name'))
        a['agent_last_name'] = _text(a.get('agent_last_name', a.get('last_name')))
        a['agent_first_name'] = _text(a.get('agent_first_name', a.get('first_name')))
        a['login'] = a.get('login') or ('S' + aid if aid.isdigit() else aid)
        a['queues'] = sorted([_queue(q) for q in a.get('queues', [])], key=lambda q:q['line_id'])
        for q in a['queues']:
            cat = queue_map.get(q['line_id'], {})
            if cat.get('base_priority_level') is not None: q['base_priority_level'] = cat['base_priority_level']
            if not q['line_name']: q['line_name'] = cat.get('line_name', '')
        ass = []
        for c in a.get('campaign_assignments', a.get('campaign_names', a.get('campaigns', []))) or []:
            if isinstance(c, str): c = dict(campaign_id='', campaign_name=c)
            c = dict(c)
            if c.get('assignment_source') == 'observed_activity': continue
            cat = catalog.get(_campaign_key(c), {})
            c['campaign_name'] = c.get('campaign_name') or cat.get('campaign_name', '')
            c['campaign_id'] = _text(c.get('campaign_id'))
            c['display_name'] = c['campaign_name'] or cat.get('display_name') or 'Campagne ' + c['campaign_id']
            c['agent_priority_level'] = _num(c.get('agent_priority_level', c.get('priority_level')), True)
            c['base_priority_level'] = _num(cat.get('base_priority_level', c.get('base_priority_level')))
            c['groups'] = campaign_groups.get(c['campaign_name'].casefold(), [])
            if 'activation_state' not in c: c.update(activation({}))
            ass.append(c)
        a['observed_campaign_names'] = sorted(_observed.get(aid, set()))
        a['campaign_assignments'] = ass
        a['campaign_names'] = [c['campaign_name'] for c in ass if c['campaign_name']]
        a['campaign_count'] = len(ass)
        a['queue_count'] = len(a['queues'])
        a['max_priority'] = max((q['agent_priority_level'] for q in a['queues'] if q['agent_priority_level'] is not None), default=None)
        a['default_campaign_name'] = catalog.get(a.get('default_campaign_id'), {}).get('campaign_name') or a.get('default_campaign_name') or a.get('default_campaign')
    agents = sorted(agents.values(), key=lambda a: (a['agent_last_name'].casefold(), a['agent_first_name'].casefold(), a['agent_id']))
    priority_agents = sum(any(q['agent_priority_level'] is not None for q in a['queues']) or any(c['agent_priority_level'] is not None for c in a['campaign_assignments']) for a in agents)
    configured_base = sum(q['base_priority_level'] is not None for q in queue_map.values()) + sum(c['base_priority_level'] is not None for c in catalog.values())
    last_attempt = {}
    if path is None:
        p = Path(QUALITY_DATA_FILE).with_name('quality_last_import.json')
        if p.exists():
            try: last_attempt = json.loads(p.read_text(encoding='utf-8'))
            except (OSError, ValueError): pass
    result = dict(version=3, source_type=('project' if raw.get('source_type') == 'demo' and roster else raw.get('source_type', 'empty')), source_label=raw.get('source_label', 'Aucun export de configuration'),
                source_file=raw.get('source_file', ''), source_day=raw.get('source_day', ''), updated_at=raw.get('updated_at'),
                scope_sources=raw.get('scope_sources', {}), bootstrap_source=raw.get('bootstrap_source', False),
                priority_source_available=bool(priority_agents or configured_base), priority_agent_count=priority_agents,
                configured_base_count=configured_base, observation_count=len(raw.get('observations', [])),
                observation_divisor=raw.get('observation_divisor', 100), observation_scale_note=raw.get('observation_scale_note', ''),
                queues=sorted(queue_map.values(), key=lambda q:q['line_id']), campaigns=sorted(catalog.values(), key=lambda c:c['display_name'].casefold()),
                groups=groups, agents=agents, matched_files=raw.get('matched_files', []), warnings=raw.get('warnings', []),
                campaign_assignment_count=sum(a['campaign_count'] for a in agents), observed_campaign_assignment_count=0,
                stats=dict(agents=len(agents), queues=sum(a['queue_count'] for a in agents), campaigns=len(catalog)),
                roster_source_file=project_meta.get('latest_import', ''), last_import_attempt=last_attempt)
    # V60: historical Quality no longer reads the daily Live database.
    # Queue labels/configuration are supplied by explicit SIMPLIFY2 imports.
    if sqlite3.runtime_database_available(cfg.APP_DB):
        from group_workspace import enrich_quality
        result = enrich_quality(result)
    return result


def load_quality_priorities(path: Path | None = None) -> dict[str, Any]:
    """Full Administration quality catalogue with a small bounded read cache."""
    if path is not None:
        return _load_quality_priorities_uncached(path)
    now = time.monotonic(); fingerprint = _priority_fingerprint()
    with _PRIORITY_CACHE_LOCK:
        cached = _PRIORITY_CACHE.get("data")
        if (cached is not None and _PRIORITY_CACHE.get("fingerprint") == fingerprint
                and now - float(_PRIORITY_CACHE.get("stamp") or 0.0) < _PRIORITY_CACHE_SECONDS):
            return copy.deepcopy(cached)
    data = _load_quality_priorities_uncached(None)
    fingerprint = _priority_fingerprint(); now = time.monotonic()
    with _PRIORITY_CACHE_LOCK:
        _PRIORITY_CACHE.update(stamp=now, fingerprint=fingerprint, data=copy.deepcopy(data))
    return data


def load_quality_assignment_catalog() -> dict[str, Any]:
    """Lightweight configured assignment catalogue for the Group workspace.

    Unlike ``load_quality_priorities`` this never scans Support activity, Live
    state or import archives.  Group auto-membership is configuration evidence:
    group -> file -> ACTIVE configured agent assignment.
    """
    raw = _read_raw()
    campaigns = {}
    for src in raw.get("campaigns", []) or []:
        c = {"campaign_name": src} if isinstance(src, str) else dict(src)
        c["campaign_id"] = "" if _text(c.get("campaign_id")).startswith("REF-") else _text(c.get("campaign_id"))
        c["campaign_name"] = _text(c.get("campaign_name"))
        c["display_name"] = c["campaign_name"] or ("Campagne " + c["campaign_id"] if c["campaign_id"] else "Campagne sans nom")
        campaigns[_campaign_key(c)] = c

    queue_map = {}
    for src in raw.get("queues", []) or []:
        try: lid = int(src.get("line_id") or 0)
        except (TypeError, ValueError): continue
        if not lid: continue
        queue_map[lid] = dict(src)
        queue_map[lid]["line_id"] = lid
        queue_map[lid]["campaign_ids"] = [str(x) for x in (src.get("campaign_ids") or []) if str(x)]

    agents = []
    for src in raw.get("agents", []) or []:
        aid = _canonical_admin_key(src.get("agent_id") or src.get("login"))
        if not aid: continue
        a = dict(src); a["agent_id"] = aid
        a["agent_last_name"] = _text(a.get("agent_last_name", a.get("last_name")))
        a["agent_first_name"] = _text(a.get("agent_first_name", a.get("first_name")))
        a["login"] = _text(a.get("login")) or ("S" + aid if aid.isdigit() else aid)
        a["directory_name"] = ""
        a["queues"] = [_queue(q) for q in (a.get("queues") or [])]
        for q in a["queues"]:
            item = queue_map.setdefault(q["line_id"], dict(line_id=q["line_id"], line_name=q.get("line_name", ""), campaign_ids=[]))
            if not item.get("line_name") and q.get("line_name"): item["line_name"] = q["line_name"]
        assigned=[]
        for csrc in (a.get("campaign_assignments", a.get("campaign_names", a.get("campaigns", []))) or []):
            c = {"campaign_id":"", "campaign_name":csrc} if isinstance(csrc, str) else dict(csrc)
            if c.get("assignment_source") == "observed_activity": continue
            c["campaign_id"] = _text(c.get("campaign_id"))
            c["campaign_name"] = _text(c.get("campaign_name"))
            if "activation_state" not in c:
                try: c.update(activation(c))
                except ValueError: c.update(activation({}))
            assigned.append(c)
        a["campaign_assignments"] = assigned
        agents.append(a)

    queues=[]
    for lid,qsrc in queue_map.items():
        q=dict(qsrc); q["line_id"]=lid
        q["configured_campaign_ids"] = sorted({str(x) for x in (q.get("campaign_ids") or []) if str(x)})
        labels=[]
        for cid in q["configured_campaign_ids"]:
            c=campaigns.get(cid)
            if c: labels.append(c["display_name"])
        q["display_name"] = _text(q.get("line_name")) or (" / ".join(labels[:3]) if labels else "File " + str(lid))
        queues.append(q)

    return dict(
        version=3, source_type=raw.get("source_type", "empty"), source_label=raw.get("source_label", ""),
        source_file=raw.get("source_file", ""), source_day=raw.get("source_day", ""), updated_at=raw.get("updated_at"),
        scope_sources=raw.get("scope_sources", {}), agents=agents, queues=sorted(queues,key=lambda q:q["line_id"]),
        campaigns=sorted(campaigns.values(), key=lambda c:c["display_name"].casefold()),
        assignment_source_available=has_quality_agent_queue_assignments(raw),
    )


def extract_quality_snapshot(raw: bytes, filename: str):
    return extract_snapshot(raw, filename)


def save_quality_snapshot(snapshot, path=None):
    target = Path(path or QUALITY_DATA_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='quality_', suffix='.json', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)
    return target


def merge_quality_snapshot(old, incoming):
    """Replace only the explicitly supplied scope, with per-scope source dates.

    Thus Lines.csv cannot erase agent memberships, and an old daily export
    cannot silently roll the latest configuration backwards. Replacing a full
    Agents.csv clears assignments removed from that snapshot, including [].
    """
    old = json.loads(json.dumps(old))
    if old.get('source_type') == 'demo': old = {'campaigns':old.get('campaigns', [])}
    scopes = set(incoming.get('scopes', []))
    accepted, ignored = set(), []
    scope_sources = old.setdefault('scope_sources', {})
    for previous_scope in old.get('scopes', []):
        scope_sources.setdefault(previous_scope, dict(day=old.get('source_day', ''), file=old.get('source_file', ''), updated_at=old.get('updated_at')))
    for scope in scopes:
        previous_day = scope_sources.get(scope, {}).get('day', old.get('source_day', ''))
        day = incoming.get('source_day', '')
        if day and previous_day and day < previous_day: ignored.append(scope)
        else: accepted.add(scope)
    if not accepted: return old, [], ignored
    agents = {_canonical_admin_key(a.get('agent_id')):a for a in old.get('agents', [])}
    for scope, field in [('agent_queues', 'queues'), ('agent_campaigns', 'campaign_assignments')]:
        if scope not in accepted: continue
        for a in agents.values(): a[field] = []
        for a in incoming.get('agents', []):
            aid = _canonical_admin_key(a['agent_id'])
            dest = agents.setdefault(aid, dict(agent_id=aid, queues=[], campaign_assignments=[]))
            for f in ('agent_first_name', 'agent_last_name', 'login', 'default_campaign_id'):
                if f in a: dest[f] = a[f]
            dest[field] = a.get(field, [])
    # A matched configuration scope controls numeric base values, while
    # statistics can enrich names/links but cannot overwrite configuration.
    queues = {int(q['line_id']):q for q in old.get('queues', [])}
    old_observed_links = {}
    for o in old.get('observations', []): old_observed_links.setdefault(int(o['line_id']), set()).add(o['campaign_id'])
    for lid, q in queues.items():
        q.setdefault('configured_campaign_ids', sorted(set(q.get('campaign_ids', [])) - old_observed_links.get(lid, set())))
    for q in incoming.get('queues', []):
        dest = queues.setdefault(int(q['line_id']), dict(line_id=int(q['line_id']), line_name='', base_priority_level=None, campaign_ids=[]))
        if q.get('line_name') and accepted.intersection({'queue_catalog','agent_queues'}): dest['line_name'] = q['line_name']
        if q.get('base_priority_level') is not None and accepted.intersection({'queue_catalog','agent_queues'}): dest['base_priority_level'] = q['base_priority_level']
        if 'observations' in accepted or 'queue_catalog' in accepted:
            if q.get('campaign_ids'): dest['campaign_ids'] = q['campaign_ids']
            if 'queue_catalog' in accepted: dest['configured_campaign_ids'] = q.get('configured_campaign_ids', [])
    campaigns = {_campaign_key(c):c for c in old.get('campaigns', []) if isinstance(c, dict)}
    for c in incoming.get('campaigns', []):
        k = _campaign_key(c)
        dest = campaigns.setdefault(k, dict(campaign_id=c.get('campaign_id',''), campaign_name='', base_priority_level=None))
        if c.get('campaign_name'): dest['campaign_name'] = c['campaign_name']
        if c.get('base_priority_level') is not None and accepted.intersection({'campaign_catalog','agent_campaigns'}): dest['base_priority_level'] = c['base_priority_level']
    if 'observations' in accepted:
        old['observations'] = incoming.get('observations', [])
        # Never preserve obsolete observed links for a refreshed ODCalls day.
        obs_links = {}
        for o in old['observations']: obs_links.setdefault(o['line_id'], set()).add(o['campaign_id'])
        for lid, q in queues.items(): q['campaign_ids'] = sorted(obs_links.get(lid, set()) | set(q.get('configured_campaign_ids', [])))
    for scope in accepted:
        scope_sources[scope] = dict(day=incoming.get('source_day',''), file=incoming.get('source_file',''), updated_at=incoming.get('updated_at'))
    for f in ('version','source_type','source_label','source_file','source_day','updated_at','digest','matched_files','warnings','observation_divisor','observation_scale_note'):
        if f in incoming: old[f] = incoming[f]
    old.pop('bootstrap_source', None)
    old['agents'] = list(agents.values()); old['queues'] = list(queues.values()); old['campaigns'] = list(campaigns.values())
    old['scope_sources'] = scope_sources
    old['scopes'] = sorted(scope_sources)
    return old, sorted(accepted), ignored


def update_quality_from_export(raw, filename):
    with _IMPORT_LOCK:
        try:
            incoming = extract_quality_snapshot(raw, filename)
            if incoming is None:
                result = dict(updated=False, reason='no_priority_source', source_file=Path(filename).name,
                              message='Aucun Agents.csv avec Queues ni configuration de priorites reconnu. Les donnees precedentes sont conservees.')
            else:
                old = _read_raw()
                # V60 safety: a partial/malformed export that advertises the
                # agent_queues scope but contains no configured assignment must
                # never erase a previously valid Group -> File -> Agent map.
                # An intentional reset remains an Administration operation, not
                # an accidental side effect of a daily statistics import.
                if ('agent_queues' in set(incoming.get('scopes', []))
                        and has_quality_agent_queue_assignments(old)
                        and not has_quality_agent_queue_assignments(incoming)):
                    incoming = copy.deepcopy(incoming)
                    incoming['scopes'] = [x for x in incoming.get('scopes', []) if x != 'agent_queues']
                    incoming.setdefault('warnings', []).append(
                        'Affectations agents/files absentes de cet export : la derniere configuration ACTIVE valide est conservee.')
                merged, accepted, ignored = merge_quality_snapshot(old, incoming)
                if accepted:
                    if Path(QUALITY_DATA_FILE).exists():
                        save_quality_snapshot(json.loads(Path(QUALITY_DATA_FILE).read_text(encoding='utf-8-sig')), Path(QUALITY_DATA_FILE).with_name('quality_priorities.previous.json'))
                    save_quality_snapshot(merged)
                group_update = None
                try:
                    from group_workspace import automatic_import_delta
                    if sqlite3.runtime_database_available(cfg.APP_DB):
                        group_update = automatic_import_delta(old, merged)
                except sqlite3.Error:
                    # The valid priority import must not be lost if Administration is locked.
                    group_update = dict(available=False, message='Groupes relus au prochain acces.')
                result = dict(automatic_groups=group_update, updated=bool(accepted), reason='imported' if accepted else 'older_snapshot', accepted_scopes=accepted,
                              ignored_older_scopes=ignored, source_file=incoming['source_file'], source_day=incoming['source_day'], matched_files=incoming['matched_files'],
                              agents=len(incoming['agents']), queues=sum(len(a['queues']) for a in incoming['agents']), queue_assignments=sum(len(a['queues']) for a in incoming['agents']), distinct_queues=len(incoming['queues']),
                              campaigns=len(incoming['campaigns']), warnings=incoming.get('warnings', []))
            result['attempted_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
            save_quality_snapshot(result, Path(QUALITY_DATA_FILE).with_name('quality_last_import.json'))
            if result.get('updated'):
                invalidate_quality_priorities_cache()
                from quality_scope import invalidate_quality_scope_cache
                invalidate_quality_scope_cache()
            return result
        except Exception as exc:
            save_quality_snapshot(dict(updated=False, reason='invalid_export', source_file=Path(filename).name,
                                       message=str(exc), attempted_at=datetime.now(timezone.utc).isoformat(timespec='seconds')),
                                  Path(QUALITY_DATA_FILE).with_name('quality_last_import.json'))
            raise
