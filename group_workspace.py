"""Group editor backed by the existing Administration DB and Quality catalogue.

A daily call export is NOT a supervision-group configuration. We only propose
members from configured queues/campaigns; an administrator must validate them.
No catalogue refresh, GET request or priority import rewrites group membership.
F4.2 adds automatic analysis memberships: explicit group-file anchors
joined to the latest configured agent-file assignments. This projection never
changes primary/manual groups or login permissions and cannot feed itself.
"""
from __future__ import annotations

import copy
import hashlib
import json
import db_compat as sqlite3
import threading
import time
from pathlib import Path
from typing import Any

import app_config as cfg
from app_db import db_connect
from classification import normalize_user_key
from quality_importer import agent_key as canonical_agent_key

TABLES = ('user_groups', 'user_group_members', 'quality_group_campaigns',
          'quality_group_meta', 'quality_group_lines', 'quality_group_campaign_refs', 'supervision_group_imports')

# No customer-specific bootstrap in a clean distribution. The generic migration
# remains testable and available to explicitly configured callers.
SCREENSHOT_TEMPLATES = []
_WORKSPACE_CACHE_LOCK = threading.RLock()
_WORKSPACE_CACHE = {'stamp':0.0,'fingerprint':None,'data':None}
_WORKSPACE_CACHE_SECONDS = 30.0

class GroupConflict(ValueError):
    """Stale editor, duplicate ID, or attempted implicit transfer of an agent."""


def _path_revision(path):
    try:
        st=Path(path).stat();return (st.st_mtime_ns,st.st_size)
    except OSError:
        return (0,0)


def _workspace_fingerprint():
    quality=cfg.BASE/'data'/'quality_priorities.json'
    scope=cfg.BASE/'data'/'quality_scope.revision'
    return (_path_revision(cfg.APP_DB),_path_revision(str(cfg.APP_DB)+'-wal'),
            _path_revision(quality),_path_revision(scope))


def invalidate_group_workspace_cache():
    with _WORKSPACE_CACHE_LOCK:
        _WORKSPACE_CACHE.update(stamp=0.0,fingerprint=None,data=None)


def _refresh_token(rev: str) -> str:
    """Cheap cross-view revision token for Group/Quality refresh checks.

    It combines the actual group relationships (database revision) with the
    small file revisions that represent the current Quality assignment scope.
    No historical activity or call table is read here.
    """
    payload = json.dumps([rev, _workspace_fingerprint()[2:]], separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def status() -> dict:
    """Lightweight status used by dashboard/polling instead of full payloads."""
    from quality_service import load_quality_assignment_catalog
    from quality_scope import load_quality_file_scope
    data = load_quality_assignment_catalog()
    scope = load_quality_file_scope()
    with db_connect() as con:
        con.execute('BEGIN')
        records = group_records(con, data)
        rev = revision(con)
    scoped = set()
    for group in scope.get('groups', []) or []:
        scoped.update(canonical_agent_key(x) for x in group.get('member_agent_ids', []) or [] if canonical_agent_key(x))
    all_agents = {canonical_agent_key(a.get('agent_id')) for a in data.get('agents', []) if canonical_agent_key(a.get('agent_id'))}
    source_day = data.get('scope_sources', {}).get('agent_queues', {}).get('day') or data.get('source_day') or ''
    return {
        'ok': True,
        'revision': rev,
        'refresh_token': _refresh_token(rev),
        'stats': {'agents': len(all_agents)},
        'group_summary': {
            'saved': len(records),
            'scoped_agents': len(scoped & all_agents) if all_agents else len(scoped),
            'unclassified_agent_count': max(0, len(all_agents - scoped)),
            'source_day': source_day,
        },
        'assignment_source_available': bool(scope.get('assignment_source_available', False)),
    }


def campaign_key(c: dict) -> str:
    return str(c.get('campaign_id') or 'name:' + str(c.get('campaign_name', '')).casefold())


def _all(con, table: str) -> list[dict]:
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return []
    return [dict(r) for r in con.execute('SELECT * FROM ' + table)]


def revision(con) -> str:
    # Hash actual relationships, not timestamps (which can have 1-second granularity).
    state = {t: sorted(_all(con, t), key=lambda r: json.dumps(r, sort_keys=True)) for t in TABLES}
    return hashlib.sha256(json.dumps(state, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def group_records(con, quality: dict | None = None) -> list[dict]:
    meta = {r['group_id']: r for r in _all(con, 'quality_group_meta')}
    records = {r['id']: dict(r, supervision_id=meta.get(r['id'], {}).get('supervision_id') or '',
                             source_note=meta.get(r['id'], {}).get('source_note', 'manual'),
                             agent_ids=[], line_ids=[], campaigns=[]) for r in _all(con, 'user_groups')}
    for m in _all(con, 'user_group_members'):
        if m['group_id'] in records: records[m['group_id']]['agent_ids'].append(str(m['user_key']))
    for m in _all(con, 'quality_group_lines'):
        if m['group_id'] in records: records[m['group_id']]['line_ids'].append(m['line_id'])
    name_index: dict[str, list[dict]] = {}
    for c in (quality or {}).get('campaigns', []):
        name_index.setdefault(str(c.get('campaign_name', '')).casefold(), []).append(c)
    for m in _all(con, 'quality_group_campaign_refs'):
        if m['group_id'] in records:
            records[m['group_id']]['campaigns'].append(dict(key=m['campaign_key'], name=m['campaign_name']))
    # Read previous name-based assignments too, without inventing IDs or dropping them.
    for m in _all(con, 'quality_group_campaigns'):
        group = records.get(m['group_id'])
        if not group: continue
        name = m['campaign_name']
        if any(x['name'].casefold() == name.casefold() for x in group['campaigns']): continue
        matches = name_index.get(name.casefold(), [])
        key = campaign_key(matches[0]) if len(matches) == 1 else 'name:' + name.casefold()
        group['campaigns'].append(dict(key=key, name=name))
    for g in records.values():
        g['agent_ids'].sort(); g['line_ids'].sort(); g['campaigns'].sort(key=lambda c: (c['name'].casefold(), c['key']))
    return sorted(records.values(), key=lambda g: g['name'].casefold())


def enrich_quality(data: dict) -> dict:
    """Attach only explicit group links; target grouping is not agent grouping."""
    with db_connect() as con:
        con.execute('BEGIN')  # Consistent read snapshot for rows and revision.
        records = group_records(con, data)
        rev = revision(con)
    data['group_revision'] = rev
    data['refresh_token'] = _refresh_token(rev)
    def tag(g):
        return dict(group_id=g['id'], group_name=g['name'], supervision_id=g['supervision_id'])
    data['groups'] = [dict(id=g['id'], name=g['name'], service_name=str(g.get('service_name') or ''), description=g['description'],
                           supervision_id=g['supervision_id'],
                           agent_count=len(g['agent_ids']), line_count=len(g['line_ids']),
                           campaign_count=len(g['campaigns'])) for g in records]
    by_line: dict[int, list] = {}; by_campaign: dict[str, list] = {}
    for g in records:
        for lid in g['line_ids']: by_line.setdefault(lid, []).append(tag(g))
        for c in g['campaigns']: by_campaign.setdefault(c['key'], []).append(tag(g))
    for c in data.get('campaigns', []):
        tags = by_campaign.get(campaign_key(c), []) + by_campaign.get('name:' + c['campaign_name'].casefold(), [])
        c['groups'] = list({g['group_id']: g for g in tags}.values())
    for q in data.get('queues', []):
        # Do not transform observed queue/campaign correspondence into group membership.
        q['groups'] = by_line.get(q['line_id'], [])
    # Memberships are authoritative even when an imported identity is not yet
    # in user_directory, or the legacy directory key is S-prefixed.
    by_agent: dict[str, list] = {}
    for g in records:
        for aid in g['agent_ids']:
            by_agent.setdefault(canonical_agent_key(aid), []).append(tag(g))
    for a in data.get('agents', []):
        tags = {g['group_id']: g for g in by_agent.get(canonical_agent_key(a['agent_id']), [])}
        a['groups'] = list(tags.values())
        if len(tags) == 1:
            group = next(iter(tags.values()))
            a['group_id'], a['group_name'] = group['group_id'], group['group_name']
            a['supervision_group_id'] = group['supervision_id']
        elif not tags:
            a['group_id'], a['group_name'], a['supervision_group_id'] = None, '', ''
        else:
            # Do not silently choose between contradictory legacy aliases.
            a['group_id'], a['supervision_group_id'] = None, ''
            a['group_name'] = ' / '.join(g['group_name'] for g in tags.values())
            a['group_conflict'] = True
    data['group_summary'] = dict(
        saved=len(records), pending_templates=len(pending_templates(records)),
        assigned_lines=sum(bool(q.get('groups')) for q in data.get('queues', [])),
        assigned_agents=sum(bool(a.get('groups')) for a in data.get('agents', [])),
    )
    return attach_automatic_groups(attach_analysis_scopes(data, records), records)


def workspace() -> dict:
    now=time.monotonic();fingerprint=_workspace_fingerprint()
    with _WORKSPACE_CACHE_LOCK:
        cached=_WORKSPACE_CACHE.get('data')
        if (cached is not None and _WORKSPACE_CACHE.get('fingerprint')==fingerprint
                and now-float(_WORKSPACE_CACHE.get('stamp') or 0.0)<_WORKSPACE_CACHE_SECONDS):
            return copy.deepcopy(cached)
    # The Group editor only needs configured assignments. The full Quality
    # catalogue also scans Support activity and Live state, which made a simple
    # group GET block for tens of seconds on production data.
    from quality_service import load_quality_assignment_catalog
    data = load_quality_assignment_catalog()
    with db_connect() as con:
        con.execute('BEGIN')  # Consistent read snapshot for rows and revision.
        records = group_records(con, data)
        directory = _all(con, 'user_directory')
        members = _all(con, 'user_group_members')
        rev = revision(con)
    # Reuse an existing S-prefixed directory/member key for the same numeric
    # agent; do not offer a second unassigned identity for an already grouped agent.
    existing_keys = {}
    for row in directory:
        existing_keys.setdefault(canonical_agent_key(row['user_key']), str(row['user_key']))
    for row in members:
        existing_keys[canonical_agent_key(row['user_key'])] = str(row['user_key'])
    agents = {}
    for a in data.get('agents', []):
        canonical = canonical_agent_key(a['agent_id'])
        key = existing_keys.get(canonical, normalize_user_key(a['agent_id']))
        agents[key] = dict(key=key, agent_id=a['agent_id'], login=a.get('login', ''),
                           first_name=a.get('agent_first_name',''), last_name=a.get('agent_last_name',''),
                           name=a.get('directory_name') or ' '.join(x for x in
                                 (a.get('agent_last_name'), a.get('agent_first_name')) if x) or a['agent_id'],
                           line_ids=[q['line_id'] for q in a.get('queues', [])],
                           campaign_keys=[campaign_key(c) for c in a.get('campaign_assignments', [])
                                          if c.get('assignment_source') != 'observed_activity'],
                           imported=True)
    for d in directory:
        key = str(d['user_key'])
        agents.setdefault(key, dict(key=key, agent_id=key, login=d['user_identifier'],
                                    name=' '.join(x for x in (d.get('first_name'), d.get('last_name')) if x) or d['user_identifier'],
                                    line_ids=[], campaign_keys=[], imported=False))
    for m in members:
        key = str(m['user_key'])
        a = agents.setdefault(key, dict(key=key, agent_id=key, login=m['user_identifier'], name=m['user_identifier'],
                                       line_ids=[], campaign_keys=[], imported=False))
        a['group_id'] = m['group_id']
    group_names = {g['id']: g['name'] for g in records}
    for a in agents.values(): a['group_name'] = group_names.get(a.get('group_id'), '')
    lines = {q['line_id']: dict(id=q['line_id'], name=q['display_name'],
                              campaign_ids=q.get('configured_campaign_ids', []), imported=True)
             for q in data.get('queues', [])}
    campaigns = {campaign_key(c): dict(key=campaign_key(c), name=c['display_name'],
                                      campaign_id=c['campaign_id'], imported=True) for c in data.get('campaigns', [])}
    # Preserve members absent from a newer catalogue: absence is not a deletion command.
    for g in records:
        for lid in g['line_ids']: lines.setdefault(lid, dict(id=lid, name='File ' + str(lid) + ' (absente du catalogue)', imported=False))
        for c in g['campaigns']: campaigns.setdefault(c['key'], dict(key=c['key'], name=c['name'], campaign_id='', imported=False))
    for tpl in SCREENSHOT_TEMPLATES:
        for lid in tpl['line_ids']:
            # IDs are explicit evidence from the screenshot, but names come from the imported catalogue.
            lines.setdefault(lid, dict(id=lid, name='File ' + str(lid) + ' (capture fournie)', imported=False))
    records = analysis_scopes(records, data)
    auto = automatic_group_plan(records, data)
    # Use the same canonical file-based scope as every analytical filter.  This
    # prevents Administration from saying `7 files / 0 agents / 0 campaigns`
    # while Quality uses a different projection.  Campaigns are derived from
    # the configured files and agents only from ACTIVE file assignments.
    from quality_scope import load_quality_file_scope
    canonical_scope = load_quality_file_scope()
    canonical_groups = {str(x.get('id')): x for x in canonical_scope.get('groups', [])}
    campaign_catalog = canonical_scope.get('campaigns', {}) or {}
    for g in records:
        matching = auto['members_by_group'].get(g['id'], [])
        cg = canonical_groups.get(str(g['id']), {})
        canonical_members = {canonical_agent_key(x) for x in cg.get('member_agent_ids', []) if canonical_agent_key(x)}
        # In normal operation the detailed automatic plan and canonical scope
        # match.  Prefer the canonical set because it is exactly what KPI filters
        # use; synthesize lightweight rows only if the rich plan is unavailable.
        rich = {canonical_agent_key(x.get('agent_id')): x for x in matching if canonical_agent_key(x.get('agent_id'))}
        projected = []
        for aid in sorted(canonical_members):
            if aid in rich:
                projected.append(rich[aid])
            else:
                projected.append(dict(agent_id=aid, name=aid, via_line_ids=[], activation_by_line={}))
        manual = {canonical_agent_key(x) for x in g['agent_ids']}
        g['automatic_agents'] = projected
        g['automatic_agent_ids'] = sorted(canonical_members)
        g['effective_agent_ids'] = sorted(manual | canonical_members)
        g['automatic_only_count'] = len(canonical_members - manual)
        g['scope_agent_count'] = int(cg.get('member_count', len(canonical_members)) or 0)
        g['scope_line_count'] = int(cg.get('file_count', len(g.get('line_ids', []))) or 0)
        derived = []
        for cid in cg.get('campaign_ids', []) or []:
            c = campaign_catalog.get(str(cid), {}) if isinstance(campaign_catalog, dict) else {}
            name = str(c.get('campaign_name') or c.get('display_name') or cid)
            derived.append(dict(key=str(cid), campaign_id=str(cid), name=name, via_line_ids=[
                int(x.get('line_id')) for x in canonical_scope.get('campaign_to_files', {}).get(str(cid), [])
                if str(x.get('line_id', '')).isdigit() and int(x.get('line_id')) in set(g.get('line_ids', []))
            ]))
        g['derived_campaigns'] = derived
        g['scope_campaign_count'] = len(derived)
        g['assignment_counts'] = dict(cg.get('assignment_counts') or {})
        g['missing_line_ids'] = list(cg.get('missing_line_ids') or [])
    result=dict(automatic_rule=auto['summary'], revision=rev, refresh_token=_refresh_token(rev), groups=records, agents=sorted(agents.values(), key=lambda a:a['name'].casefold()),
                lines=sorted(lines.values(), key=lambda q:q['name'].casefold()),
                campaigns=sorted(campaigns.values(), key=lambda c:c['name'].casefold()),
                templates=SCREENSHOT_TEMPLATES, pending_templates=pending_templates(records), template_source='Capture fournie : liste partielle, affectations non completes.',
                source_day=data.get('scope_sources', {}).get('agent_queues', {}).get('day') or data.get('source_day'),
                source_file=data.get('source_file', ''),
                assignment_source_available=canonical_scope.get('assignment_source_available', False),
                assignment_recovered=canonical_scope.get('assignment_recovered', False),
                assignment_warning=canonical_scope.get('assignment_warning', ''),
                limitation='Regle analytique : files du groupe -> agents ACTIVE uniquement. Les campagnes et les durees suivent ce meme scope. Les droits/permissions restent separes.')
    with _WORKSPACE_CACHE_LOCK:
        _WORKSPACE_CACHE.update(stamp=time.monotonic(),fingerprint=_workspace_fingerprint(),data=copy.deepcopy(result))
    return result



def pending_templates(records: list[dict]) -> list[dict]:
    """Evidence still needing an explicit write. Never equate SPEC with
    SPECIALISTES or Dedie with DEDIEE: those may be different teams."""
    names = {g['name'].strip().casefold() for g in records}
    ids = {str(g.get('supervision_id') or '').strip() for g in records}
    return [dict(t, line_ids=list(t['line_ids'])) for t in SCREENSHOT_TEMPLATES
            if t['supervision_id'] not in ids and t['name'].casefold() not in names]


def add_capture_groups(payload: dict, actor: str, ip: str = '') -> dict:
    """Create selected, absent screenshot groups only, in one transaction.

    Existing groups, names, memberships and priority data remain unchanged.
    Five visible MED01 queue links are partial screenshot evidence, not a
    complete exported configuration. No agents or campaigns are assigned.
    """
    if not isinstance(payload, dict):
        raise ValueError('Donnees invalides')
    selected = _keys(payload.get('supervision_ids'), 'groupes')
    known = {t['supervision_id']: t for t in SCREENSHOT_TEMPLATES}
    if not selected or set(selected) - known.keys():
        raise ValueError('Choisir les groupes proposes dans la capture')
    expected = str(payload.get('revision') or '')
    if not expected:
        raise GroupConflict('Version de configuration manquante : actualiser')
    created, skipped = [], []
    try:
        with db_connect() as con:
            con.execute('BEGIN IMMEDIATE')
            if revision(con) != expected:
                raise GroupConflict('Les groupes ont change. Actualiser puis recommencer.')
            records = group_records(con)
            available = {t['supervision_id'] for t in pending_templates(records)}
            for sid in selected:
                if sid not in available:
                    skipped.append(sid)
                    continue
                tpl = known[sid]
                gid = con.execute(
                    'INSERT INTO user_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)',
                    (tpl['name'], 'Capture de supervision : configuration partielle a completer.', actor, actor)
                ).lastrowid
                con.execute('INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?)',
                            (gid, sid, 'capture_user_partial_validated'))
                for lid in tpl['line_ids']:
                    con.execute('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)',
                                (gid, lid, actor))
                created.append(dict(id=gid, supervision_id=sid, name=tpl['name'], line_ids=tpl['line_ids']))
            if created:
                con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                            (actor, 'GROUP_CAPTURE_ADDED', json.dumps(dict(created=created, skipped=skipped), ensure_ascii=False), ip))
            con.commit()
    except sqlite3.IntegrityError as exc:
        raise GroupConflict('Un nom ou ID existe deja. Aucun groupe ajoute : actualiser.') from exc
    invalidate_group_workspace_cache()
    return dict(ok=True, created=created, skipped=skipped)

def _keys(values: Any, label: str) -> list[str]:
    if not isinstance(values, list) or len(values) > 10000: raise ValueError('Liste ' + label + ' invalide')
    if any(not isinstance(v, (str, int)) or isinstance(v, bool) for v in values):
        raise ValueError('Identifiant ' + label + ' invalide')
    return sorted(set(str(v).strip() for v in values if str(v).strip()))


def save_group(payload: dict, actor: str, ip: str = '') -> dict:
    """Atomic replacement of ONE explicitly edited group, optimistic concurrency.

    Transferring a member from a different group is intentionally refused. The
    administrator removes that existing membership first, using the editor.
    """
    if not isinstance(payload, dict): raise ValueError('Donnees groupe invalides')
    name = str(payload.get('name') or '').strip()
    service_name = str(payload.get('service_name') or '').strip()
    description = str(payload.get('description') or '').strip()
    external = str(payload.get('supervision_id') or '').strip()
    if not name or len(name) > 60: raise ValueError('Nom requis, 60 caracteres maximum')
    if len(service_name) > 60: raise ValueError('Service parent : 60 caracteres maximum')
    if len(description) > 300: raise ValueError('Description : 300 caracteres maximum')
    if len(external) > 64: raise ValueError('ID supervision : 64 caracteres maximum')
    agent_ids = _keys(payload.get('agent_ids'), 'agents')
    lines = _keys(payload.get('line_ids'), 'files')
    if any(not x.isdigit() or int(x) <= 0 for x in lines): raise ValueError('ID file invalide')
    line_ids = sorted(set(int(x) for x in lines))
    campaign_keys = _keys(payload.get('campaign_keys'), 'campagnes')
    if payload.get('id') in (None, ''): gid = None
    else:
        try: gid = int(payload['id'])
        except (ValueError, TypeError): raise ValueError('Groupe invalide')
    choices = workspace()  # source catalogue is read only
    amap = {a['key']: a for a in choices['agents']}
    cmap = {c['key']: c for c in choices['campaigns']}
    lmap = {q['id']: q for q in choices['lines']}
    if set(agent_ids) - amap.keys(): raise ValueError('Un agent est absent du catalogue : actualiser')
    if set(line_ids) - lmap.keys(): raise ValueError('Une file est absente du catalogue : actualiser')
    if set(campaign_keys) - cmap.keys(): raise ValueError('Une campagne est absente du catalogue : actualiser')
    expected = str(payload.get('revision') or '')
    if not expected: raise GroupConflict('Version de configuration manquante : actualiser')
    try:
        with db_connect() as con:
            con.execute('BEGIN IMMEDIATE')
            if expected != revision(con): raise GroupConflict('Les groupes ont change pendant la saisie. Actualiser puis reappliquer les changements.')
            old = next((g for g in group_records(con) if g['id'] == gid), None)
            if gid is not None and old is None: raise ValueError('Groupe introuvable')
            member_rows = _all(con, 'user_group_members')
            for key in agent_ids:
                conflicts = [r for r in member_rows if canonical_agent_key(r['user_key']) == canonical_agent_key(key) and r['group_id'] != gid]
                if conflicts:
                    raise GroupConflict('Agent ' + key + ' deja affecte a un autre groupe. Retirer son ancienne affectation avant de le deplacer.')
            if gid is None:
                gid = con.execute('INSERT INTO user_groups(name,service_name,description,created_by,updated_by) VALUES(?,?,?,?,?)',
                                  (name, service_name, description, actor, actor)).lastrowid
            else:
                con.execute('UPDATE user_groups SET name=?,service_name=?,description=?,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE id=?',
                            (name, service_name, description, actor, gid))
            note = str(payload.get('source_note') or 'manual')[:200]
            con.execute('''INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?)
                           ON CONFLICT(group_id) DO UPDATE SET supervision_id=excluded.supervision_id,source_note=excluded.source_note''',
                        (gid, external or None, note))
            # Only this group's links are changed. Unedited groups stay intact.
            for table in ('user_group_members', 'quality_group_lines', 'quality_group_campaign_refs', 'quality_group_campaigns'):
                con.execute('DELETE FROM ' + table + ' WHERE group_id=?', (gid,))
            for key in agent_ids:
                a = amap[key]
                # Imported identities become available to the shared directory too.
                # Never overwrite names previously edited by an administrator.
                con.execute('''INSERT OR IGNORE INTO user_directory(user_key,user_identifier,first_name,last_name,created_by,updated_by)
                               VALUES(?,?,?,?,?,?)''', (key, a.get('agent_id', key), a.get('first_name',''), a.get('last_name',''), actor, actor))
                con.execute('INSERT INTO user_group_members(user_key,user_identifier,group_id,created_by) VALUES(?,?,?,?)',
                            (key, a.get('agent_id', key), gid, actor))
            for lid in line_ids:
                con.execute('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)', (gid, lid, actor))
            for key in campaign_keys:
                c = cmap[key]
                con.execute('INSERT INTO quality_group_campaign_refs(group_id,campaign_key,campaign_name,created_by) VALUES(?,?,?,?)',
                            (gid, key, c['name'], actor))
                con.execute('INSERT OR IGNORE INTO quality_group_campaigns(group_id,campaign_name,created_by) VALUES(?,?,?)',
                            (gid, c['name'], actor))
            audit = dict(before=old, after=dict(id=gid, name=name, supervision_id=external, agents=agent_ids, lines=line_ids, campaigns=campaign_keys))
            con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                        (actor, 'GROUP_WORKSPACE_SAVED', json.dumps(audit, ensure_ascii=False), ip))
            con.commit()
    except sqlite3.IntegrityError as exc:
        raise GroupConflict('Ce nom de groupe ou cet ID supervision est deja utilise.') from exc
    invalidate_group_workspace_cache()
    return dict(ok=True, id=gid, agents=len(agent_ids), lines=len(line_ids), campaigns=len(campaign_keys))


def export_group_links(con) -> list[dict]:
    """Versioned extension of the existing whole-application JSON backup."""
    return [dict(group_name=g['name'], supervision_id=g['supervision_id'], source_note=g['source_note'],
                 line_ids=g['line_ids'], campaigns=g['campaigns']) for g in group_records(con)]


def validate_group_links(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > 10000: raise ValueError('Configuration groupes invalide')
    out, external_ids, names = [], set(), set()
    for item in raw:
        if not isinstance(item, dict): raise ValueError('Configuration groupe invalide')
        name = str(item.get('group_name') or '').strip()
        ext = str(item.get('supervision_id') or '').strip()
        if not name or len(name) > 60 or name.casefold() in names: raise ValueError('Nom groupe invalide ou duplique')
        if len(ext) > 64 or (ext and ext in external_ids): raise ValueError('ID supervision invalide ou duplique')
        names.add(name.casefold())
        if ext: external_ids.add(ext)
        lines = _keys(item.get('line_ids', []), 'files')
        if any(not x.isdigit() or int(x) <= 0 for x in lines): raise ValueError('ID file invalide')
        campaigns = item.get('campaigns', [])
        if not isinstance(campaigns, list): raise ValueError('Campagnes invalides')
        normalized = []
        for c in campaigns:
            if not isinstance(c, dict) or not str(c.get('key') or '').strip(): raise ValueError('Reference campagne invalide')
            key, label = str(c['key']).strip(), str(c.get('name') or '').strip()
            if len(key) > 240 or len(label) > 300: raise ValueError('Reference campagne trop longue')
            normalized.append(dict(key=key, name=label))
        out.append(dict(group_name=name, supervision_id=ext, source_note=str(item.get('source_note') or 'config_import')[:200],
                        line_ids=sorted(set(map(int, lines))), campaigns=normalized))
    return out


def restore_group_links(con, links, group_ids, actor):
    """Called inside the existing config-import transaction, after group recreation."""
    for item in links:
        gid = group_ids.get(item['group_name'].casefold())
        if gid is None: continue  # Not present in this selected whole-config backup.
        con.execute('INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?)',
                    (gid, item['supervision_id'] or None, item['source_note']))
        for lid in item['line_ids']:
            con.execute('INSERT OR IGNORE INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)', (gid,lid,actor))
        for c in item['campaigns']:
            con.execute('INSERT OR IGNORE INTO quality_group_campaign_refs(group_id,campaign_key,campaign_name,created_by) VALUES(?,?,?,?)',
                        (gid,c['key'],c['name'],actor))
            if c['name']:
                con.execute('INSERT OR IGNORE INTO quality_group_campaigns(group_id,campaign_name,created_by) VALUES(?,?,?)',
                            (gid,c['name'],actor))


# F4.1: these links are analysis evidence, NOT official supervision membership.
def _configured(item):
    return item.get('assignment_source') not in ('observed_activity', 'demo')


def _agent_label(agent):
    return (agent.get('directory_name') or ' '.join(str(agent.get(k) or '') for k in
            ('agent_last_name', 'agent_first_name')).strip() or agent.get('login') or str(agent['agent_id']))


def analysis_scopes(records, data):
    """One-hop joins from explicit anchors. Never turn a proposal into an anchor.

    Registered agent -> its configured queues/campaigns.
    Registered queue/campaign -> configured agents on that target.
    Only ACTIVE file assignments are included; partial, inactive and unknown are excluded.
    ODCalls/observed_activity and similar names are never group evidence.
    """
    out = []
    for original in records:
        g = dict(original)
        explicit_agents = {canonical_agent_key(x) for x in g['agent_ids']}
        explicit_lines = set(g['line_ids'])
        campaign_keys = {c['key'] for c in g['campaigns']}
        def has_campaign(c):
            return (campaign_key(c) in campaign_keys or
                    'name:' + str(c.get('campaign_name') or '').casefold() in campaign_keys)
        linked_agents, linked_lines, linked_campaigns = {}, {}, {}
        for a in data.get('agents', []):
            aid = canonical_agent_key(a['agent_id'])
            own = aid in explicit_agents
            via_lines, via_campaigns = [], []
            for q in a.get('queues', []):
                if not _configured(q) or q.get('activation_state') != 'active':
                    continue
                lid = q['line_id']
                if lid in explicit_lines:
                    via_lines.append(lid)
                if own and lid not in explicit_lines:
                    item = linked_lines.setdefault(lid, dict(line_id=lid, via_agent_ids=[]))
                    item['via_agent_ids'].append(aid)
            for c in a.get('campaign_assignments', []):
                if not _configured(c):
                    continue
                key = campaign_key(c)
                if has_campaign(c):
                    via_campaigns.append(key)
                if own and not has_campaign(c):
                    item = linked_campaigns.setdefault(key, dict(key=key, name=c.get('campaign_name') or key, via_agent_ids=[]))
                    item['via_agent_ids'].append(aid)
            if not own and (via_lines or via_campaigns):
                linked_agents[aid] = dict(agent_id=aid, name=_agent_label(a),
                    via_line_ids=sorted(set(via_lines)), via_campaign_keys=sorted(set(via_campaigns)))
        g['linked_agents'] = sorted(linked_agents.values(), key=lambda a:a['agent_id'])
        g['linked_lines'] = sorted(linked_lines.values(), key=lambda q:q['line_id'])
        g['linked_campaigns'] = sorted(linked_campaigns.values(), key=lambda c:c['key'])
        g['scope_agent_count'] = len(explicit_agents | set(linked_agents))
        g['scope_line_count'] = len(explicit_lines | set(linked_lines))
        g['scope_campaign_count'] = len(campaign_keys | set(linked_campaigns))
        out.append(g)
    return out


def attach_analysis_scopes(data, records):
    """Add scope_groups beside (not in place of) authoritative groups."""
    scoped = analysis_scopes(records, data)
    def tag(g, origin, **evidence):
        return dict(group_id=g['id'], group_name=g['name'], supervision_id=g['supervision_id'],
                    origin=origin, linked=origin.startswith('linked_'), **evidence)
    agent_tags, line_tags, campaign_tags = {}, {}, {}
    def put(mapping, key, value):
        # A registered anchor takes precedence over any calculated relationship.
        mapping.setdefault(key, {}).setdefault(value['group_id'], value)
    for g in scoped:
        for aid in g['agent_ids']:
            put(agent_tags, canonical_agent_key(aid), tag(g, 'registered_agent'))
        for lid in g['line_ids']:
            put(line_tags, lid, tag(g, 'registered_file'))
        for c in g['campaigns']:
            put(campaign_tags, c['key'], tag(g, 'registered_campaign'))
        for a in g['linked_agents']:
            put(agent_tags, a['agent_id'], tag(g, 'linked_targets',
                via_line_ids=a['via_line_ids'], via_campaign_keys=a['via_campaign_keys']))
        for q in g['linked_lines']:
            put(line_tags, q['line_id'], tag(g, 'linked_agents', via_agent_ids=q['via_agent_ids']))
        for c in g['linked_campaigns']:
            put(campaign_tags, c['key'], tag(g, 'linked_agents', via_agent_ids=c['via_agent_ids']))
    def campaign_matches(c):
        return {**campaign_tags.get('name:' + str(c.get('campaign_name') or '').casefold(), {}),
                **campaign_tags.get(campaign_key(c), {})}
    for q in data.get('queues', []):
        q['scope_groups'] = list(line_tags.get(q['line_id'], {}).values())
    for c in data.get('campaigns', []):
        c['scope_groups'] = list(campaign_matches(c).values())
    for a in data.get('agents', []):
        tags = agent_tags.get(canonical_agent_key(a['agent_id']), {})
        a['scope_groups'] = list(tags.values())
        own = {gid:t for gid,t in tags.items() if t['origin']=='registered_agent'}
        # Row filtering is limited to the actual evidence. A linked agent does
        # NOT bring all their other queues into the selected group.
        for q in a.get('queues', []):
            on_file = {gid:dict(t, origin='linked_file', linked=True, via_line_ids=[q['line_id']])
                       for gid,t in line_tags.get(q['line_id'], {}).items()
                       if t['origin']=='registered_file'} if _configured(q) else {}
            q['scope_groups'] = list({**on_file, **own}.values())
        for c in a.get('campaign_assignments', []):
            on_campaign = {gid:dict(t, origin='linked_campaign', linked=True, via_campaign_keys=[campaign_key(c)])
                           for gid,t in campaign_matches(c).items() if t['origin']=='registered_campaign'} if _configured(c) else {}
            c['scope_groups'] = list({**on_campaign, **own}.values())
    by_id = {g['id']:g for g in scoped}
    for summary in data['groups']:
        g = by_id[summary['id']]
        for k in ('scope_agent_count','scope_line_count','scope_campaign_count'):
            summary[k] = g[k]
        summary['linked_agent_count'] = len(g['linked_agents'])
        summary['linked_line_count'] = len(g['linked_lines'])
    data['group_summary'].update(
        scoped_agents=sum(bool(a.get('scope_groups')) for a in data.get('agents', [])),
        scoped_lines=sum(bool(q.get('scope_groups')) for q in data.get('queues', [])),
        scope_note='Lie depuis les bases = relation configuree agent-file/campagne, pas appartenance officielle.',
        source_day=data.get('scope_sources', {}).get('agent_queues', {}).get('day') or data.get('source_day'))
    return data


def recover_known_groups_once(actor='SYSTEM_F41'):
    """Startup-only additive recovery authorized by this project update.

    Saves an online SQLite backup before any group write. The six group names
    and five MED01 queue links come from the user's screenshot, not from the
    daily ZIP. Existing memberships/permissions stay untouched. A still-empty exact MED01
    may recover its five known screenshot queue anchors once.
    A marker prevents deleted groups being recreated on each restart.
    """
    from datetime import datetime, timezone
    from pathlib import Path
    import uuid
    import app_config as cfg
    if not SCREENSHOT_TEMPLATES:
        return dict(created=[], preserved=[], filled_existing=[], skipped='no_templates_configured')
    marker = 'group_recovery_f41_v1'
    with db_connect() as con:
        row = con.execute('SELECT value FROM settings WHERE key=?', (marker,)).fetchone()
        if row:
            return dict(json.loads(row[0]), already_applied=True)
    directory = cfg.APP_DB.parent / 'backups' / 'groups'
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / ('before_f41_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ_') + uuid.uuid4().hex[:8] + '.db')
    # backup() is used outside a write transaction. A failure aborts recovery.
    with db_connect() as source:
        dest = sqlite3.connect(str(backup))
        try:
            source.backup(dest)
        finally:
            dest.close()
    try:
        with db_connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT value FROM settings WHERE key=?', (marker,)).fetchone()
            if row:
                return dict(json.loads(row[0]), already_applied=True)
            existing = group_records(con)
            ids = {g['supervision_id']:g for g in existing if g['supervision_id']}
            names = {g['name'].strip().casefold():g for g in existing}
            created, preserved, filled = [], [], []
            for tpl in SCREENSHOT_TEMPLATES:
                current = ids.get(tpl['supervision_id']) or names.get(tpl['name'].casefold())
                if current:
                    preserved.append(tpl['name'])
                    # An exact, still-empty MED01 can recover the five visible
                    # anchors once. Never expand a nonempty or conflicting group.
                    if (tpl['line_ids'] and not current['line_ids']
                            and current['name'].strip().casefold()==tpl['name'].casefold()
                            and current['supervision_id'] in ('', tpl['supervision_id'])):
                        for lid in tpl['line_ids']:
                            con.execute('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)',
                                        (current['id'],lid,actor))
                        if not current['supervision_id']:
                            con.execute('INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?) '
                                        'ON CONFLICT(group_id) DO UPDATE SET supervision_id=excluded.supervision_id',
                                        (current['id'],tpl['supervision_id'],'capture_user_partial_f41'))
                        filled.append(dict(id=current['id'],name=current['name'],line_ids=list(tpl['line_ids'])))
                    continue
                gid = con.execute('INSERT INTO user_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)',
                    (tpl['name'], 'Capture fournie : liste partielle. Liens calcules separes des membres enregistres.', actor, actor)).lastrowid
                con.execute('INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?)',
                    (gid, tpl['supervision_id'], 'capture_user_partial_f41'))
                for lid in tpl['line_ids']:
                    con.execute('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)', (gid,lid,actor))
                created.append(dict(id=gid, name=tpl['name'], supervision_id=tpl['supervision_id'], line_ids=list(tpl['line_ids'])))
            result = dict(version='F4.1', created=created, filled_existing=filled, preserved=preserved, backup=str(backup.relative_to(cfg.APP_DB.parent)),
                          sources=['user_groups', 'user_group_members', 'Capture utilisateur partielle'],
                          note='Aucun agent deplace. Liens calcules uniquement a la lecture.',
                          applied_at=datetime.now(timezone.utc).isoformat())
            con.execute('INSERT INTO settings(key,value,updated_by) VALUES(?,?,?)',
                        (marker,json.dumps(result,ensure_ascii=False),actor))
            con.execute('INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)',
                        (actor,'GROUP_RECOVERY_F41',json.dumps(result,ensure_ascii=False)))
            con.commit()
            return result
    except Exception:
        # Keep the pre-write backup for diagnosis; the transaction rolls back.
        raise


# F4.2 -- automatic memberships are a projection, not a second writable roster.
# That avoids stale removals, duplicate members and changes to access-control groups.
def automatic_group_plan(records, data):
    """Apply the user rule only to EXPLICIT group -> file assignments.

    Only explicitly active file assignments count, independently of the agent
    online state. A single agent may match multiple groups; priority does not
    break ties. Linked files from F4.1 and campaign/activity links are NOT anchors.
    """
    by_line = {}
    names = {}
    for g in records:
        names[g['id']] = g
        for lid in set(g.get('line_ids', [])):
            by_line.setdefault(int(lid), set()).add(g['id'])
    members = {}
    exported = set()
    for a in data.get('agents', []):
        aid = canonical_agent_key(a.get('agent_id') or a.get('login'))
        if not aid:
            continue
        exported.add(aid)
        if data.get('source_type') == 'demo':
            continue
        for q in a.get('queues', []):
            if not _configured(q) or q.get('activation_state') != 'active':
                continue
            try:
                lid = int(q['line_id'])
            except (KeyError, ValueError, TypeError):
                continue
            for gid in by_line.get(lid, ()):
                member = members.setdefault((gid, aid), dict(agent_id=aid,
                    name=_agent_label(a), via_line_ids=set(), activation_by_line={}))
                member['via_line_ids'].add(lid)
                member['activation_by_line'][str(lid)] = q.get('activation_state', 'unknown')
    scope_source = data.get('scope_sources', {}).get('agent_queues', {})
    source_day = scope_source.get('day') or data.get('source_day', '')
    source_file = scope_source.get('file') or data.get('source_file', '')
    grouped = {g['id']: [] for g in records}
    tags = {}
    for (gid, aid), member in sorted(members.items()):
        member['via_line_ids'] = sorted(member['via_line_ids'])
        grouped[gid].append(member)
        g = names[gid]
        tags.setdefault(aid, []).append(dict(group_id=gid, group_name=g['name'],
            supervision_id=g.get('supervision_id', ''), origin='automatic_file_assignment',
            automatic=True, linked=True, via_line_ids=member['via_line_ids'],
            source_day=source_day, source_file=source_file))
    # Includes labels and manual links: the UI can detect group edits as well as imports.
    sig = dict(rule='active_file_to_agent_v2', groups=[dict(id=g['id'],
        name=g['name'], supervision_id=g.get('supervision_id', ''),
        files=sorted(g.get('line_ids', [])), agents=sorted(g.get('agent_ids', [])),
        campaigns=g.get('campaigns', [])) for g in records],
        members=[dict(group_id=gid, **a) for gid, agents in sorted(grouped.items()) for a in agents],
        source_day=source_day, source_file=source_file)
    signature = hashlib.sha256(json.dumps(sig, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    summary = dict(enabled=True, rule='active_file_to_agent_v2', include_inactive=False,
        multi_group=True, source_day=source_day, source_file=source_file, signature=signature,
        groups_with_files=sum(bool(g.get('line_ids')) for g in records),
        groups_without_files=sum(not g.get('line_ids') for g in records),
        mapped_file_count=len(by_line), automatic_agent_count=len(tags),
        automatic_membership_count=len(members),
        multi_group_agent_count=sum(len(v)>1 for v in tags.values()),
        unclassified_agent_count=len(exported - tags.keys()))
    return dict(summary=summary, members_by_group=grouped, tags_by_agent=tags)


def attach_automatic_groups(data, records):
    """Expose effective analysis groups without changing legacy primary group fields."""
    plan = automatic_group_plan(records, data)
    for a in data.get('agents', []):
        auto = plan['tags_by_agent'].get(canonical_agent_key(a['agent_id']), [])
        a['automatic_groups'] = auto
        effective = {t['group_id']: dict(t) for t in auto}
        effective.update({t['group_id']: dict(t) for t in a.get('groups', [])})
        a['effective_groups'] = list(effective.values())
        gids = {t['group_id'] for t in auto}
        for t in a.get('scope_groups', []):
            if t['group_id'] in gids:
                t['automatic'] = True
        for q in a.get('queues', []):
            for t in q.get('scope_groups', []):
                # Automatic membership is known only from saved file anchors.
                evidence = next((v for v in auto if v['group_id']==t['group_id']), None)
                if evidence and q['line_id'] in evidence['via_line_ids']:
                    t['automatic'] = True
    for g in data.get('groups', []):
        matches = plan['members_by_group'].get(g['id'], [])
        g['automatic_agent_count'] = len(matches)
    data['automatic_rule'] = plan['summary']
    data['group_summary']['automatic_rule'] = plan['summary']
    return data


def automatic_import_delta(old, incoming):
    """Changes in calculated memberships only; never writes group/member tables."""
    with db_connect() as con:
        con.execute('BEGIN')
        records = group_records(con)
    before = automatic_group_plan(records, old)
    after = automatic_group_plan(records, incoming)
    pairs = lambda plan: {(gid, a['agent_id']) for gid, aa in plan['members_by_group'].items() for a in aa}
    bp, ap = pairs(before), pairs(after)
    return dict(**after['summary'], added=len(ap-bp), removed=len(bp-ap),
                unchanged=len(bp & ap), manual_groups_preserved=True)
