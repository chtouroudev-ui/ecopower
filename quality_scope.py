"""Lightweight Quality scopes based on configured queues (files).

This module deliberately avoids the heavy full priority projection used by the
Administration priority screens.  Quality KPIs only need queue/campaign links,
agent queue assignments and Administration group anchors.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import threading
import time

from app_db import db_connect
from group_workspace import group_records
from quality_importer import agent_key, activation
from quality_service import _read_raw, QUALITY_DATA_FILE, has_quality_agent_queue_assignments

_CACHE_LOCK = threading.RLock()
_CACHE = {"stamp": 0.0, "data": None, "fingerprint": None}
_CACHE_SECONDS = 300.0
_REVISION_FILE = Path(QUALITY_DATA_FILE).with_name("quality_scope.revision")


def _stat_fingerprint(path):
    try:
        st=Path(path).stat();return (st.st_mtime_ns,st.st_size)
    except OSError:
        return (0,0)


def _source_fingerprint():
    return (_stat_fingerprint(QUALITY_DATA_FILE),_stat_fingerprint(_REVISION_FILE))


def _state(row):
    value=str(row.get('activation_state') or '').strip().lower()
    if value:
        return value
    try:
        return str(activation(row).get('activation_state') or 'unknown').lower()
    except (TypeError, ValueError):
        return 'unknown'


def _build_scope():
    # Never scan import archives from an interactive HTTP request. Recovery is
    # owned by the Import Worker so group/quality reads stay bounded.
    raw=_read_raw()
    assignment_source_available=has_quality_agent_queue_assignments(raw)
    campaigns={str(c.get('campaign_id') or '').strip():dict(c) for c in raw.get('campaigns',[]) if str(c.get('campaign_id') or '').strip()}
    queue_map={}
    for src in raw.get('queues',[]):
        try: lid=int(src.get('line_id') or 0)
        except (TypeError,ValueError): continue
        if not lid: continue
        item=queue_map.setdefault(lid,dict(line_id=lid,line_name=str(src.get('line_name') or '').strip(),campaign_ids=set()))
        if not item['line_name'] and src.get('line_name'): item['line_name']=str(src.get('line_name')).strip()
        for cid in src.get('campaign_ids',[]) or []:
            cid=str(cid or '').strip()
            if cid:item['campaign_ids'].add(cid)
    # Older snapshots can carry queue/campaign correspondence only as observations.
    for obs in raw.get('observations',[]) or []:
        try: lid=int(obs.get('line_id') or 0)
        except (TypeError,ValueError): continue
        cid=str(obs.get('campaign_id') or '').strip()
        if lid and cid:
            queue_map.setdefault(lid,dict(line_id=lid,line_name='',campaign_ids=set()))['campaign_ids'].add(cid)

    def campaign_label(cid):
        c=campaigns.get(str(cid),{})
        return str(c.get('campaign_name') or cid)

    for q in queue_map.values():
        q['campaign_ids']=sorted(q['campaign_ids'])
        labels=[campaign_label(cid) for cid in q['campaign_ids']]
        q['display_name']=q['line_name'] or (' / '.join(labels[:3]) if labels else f'File {q["line_id"]}')

    with db_connect() as con:
        con.execute('BEGIN')
        records=group_records(con)

    all_period_campaigns=set(campaigns)
    assigned_campaigns=set()
    groups=[]
    line_to_groups=defaultdict(set)
    for g in records:
        line_ids=sorted({int(x) for x in g.get('line_ids',[])})
        ids=set()
        missing=[]
        for lid in line_ids:
            line_to_groups[lid].add(str(g['id']))
            q=queue_map.get(lid)
            if q: ids.update(q['campaign_ids'])
            else: missing.append(lid)
        assigned_campaigns.update(ids)
        groups.append(dict(
            id=str(g['id']),name=g['name'],service_name=str(g.get('service_name') or ''),line_ids=line_ids,file_count=len(line_ids),
            matched_file_count=len(line_ids)-len(missing),missing_line_ids=missing,
            campaign_ids=sorted(ids),campaign_count=len(ids),
            explicit_agent_ids=sorted({agent_key(x) for x in g.get('agent_ids',[]) if agent_key(x)}),
            basis='configured_files',
        ))

    # Canonical analysis rule: one pass over agent assignments builds reverse
    # file indexes. Only configured + ACTIVE assignments create membership.
    # partial/inactive/unknown remain visible as diagnostics but never widen KPIs.
    agent_files=defaultdict(set)
    agents_by_line=defaultdict(set)
    agent_names={}
    state_agents_by_line={state:defaultdict(set) for state in ('active','partial','inactive','unknown')}
    for a in raw.get('agents',[]) or []:
        aid=agent_key(a.get('agent_id') or a.get('login'))
        if not aid: continue
        first=str(a.get('agent_first_name') or a.get('first_name') or '').strip()
        last=str(a.get('agent_last_name') or a.get('last_name') or '').strip()
        display=' '.join(x for x in (first,last) if x).strip()
        if display: agent_names.setdefault(aid,display)
        for q in a.get('queues',[]) or []:
            if q.get('assignment_source') in ('observed_activity','demo'):
                continue
            try: lid=int(q.get('line_id') or 0)
            except (TypeError,ValueError): continue
            if not lid: continue
            state=_state(q)
            if state not in state_agents_by_line: state='unknown'
            state_agents_by_line[state][lid].add(aid)
            if state == 'active':
                agent_files[aid].add(lid);agents_by_line[lid].add(aid)

    for g in groups:
        lids=g['line_ids']
        file_members=set().union(*(agents_by_line.get(lid,set()) for lid in lids)) if lids else set()
        g['file_member_agent_ids']=sorted(file_members)
        # Analytical membership is strictly file-based. user_group_members is an
        # Administration/access relationship and must not silently widen KPI scopes.
        # An agent can naturally belong to several groups through several active files.
        g['member_agent_ids']=sorted(file_members)
        g['member_count']=len(file_members)
        g['assignment_counts']={state:len(set().union(*(by_line.get(lid,set()) for lid in lids)) if lids else set())
                                for state,by_line in state_agents_by_line.items()}

    # A synthetic scope remains useful to diagnose campaigns/agents not mapped
    # through any configured group file. It is not a saved Administration group.
    assigned_members={aid for g in groups for aid in g.get('member_agent_ids',[])}
    unassigned_members=sorted(set(agent_files)-assigned_members)
    groups.append(dict(id='unassigned',name='Sans groupe de file',service_name='',line_ids=[],file_count=0,
                       matched_file_count=0,missing_line_ids=[],
                       campaign_ids=sorted(all_period_campaigns-assigned_campaigns),
                       campaign_count=len(all_period_campaigns-assigned_campaigns),
                       explicit_agent_ids=[],file_member_agent_ids=unassigned_members,
                       member_agent_ids=unassigned_members,member_count=len(unassigned_members),
                       basis='configured_files'))

    campaign_to_files=defaultdict(list)
    for q in queue_map.values():
        for cid in q['campaign_ids']:
            campaign_to_files[cid].append(dict(line_id=q['line_id'],line_name=q['display_name']))
    for cid in campaign_to_files:
        campaign_to_files[cid].sort(key=lambda x:(x['line_name'].casefold(),x['line_id']))

    configured_agents_by_line={}
    agents_by_line_state={}
    for state,by_line in state_agents_by_line.items():
        public={str(lid):sorted(ids) for lid,ids in by_line.items()}
        agents_by_line_state[state]=public
        for lid,ids in by_line.items():
            configured_agents_by_line.setdefault(str(lid),set()).update(ids)
    configured_agents_by_line={lid:sorted(ids) for lid,ids in configured_agents_by_line.items()}

    return dict(groups=groups,queues=sorted(queue_map.values(),key=lambda q:q['line_id']),
                campaigns=campaigns,agent_files={k:sorted(v) for k,v in agent_files.items()},agent_names=agent_names,
                configured_agents_by_line=configured_agents_by_line,agents_by_line_state=agents_by_line_state,
                campaign_to_files=dict(campaign_to_files),basis='configured_files',
                membership_rule='group_files -> ACTIVE agent assignments only',
                assignment_source_available=assignment_source_available,
                assignment_source_file=str(raw.get('source_file') or ''),
                assignment_recovered=bool(raw.get('recovered_from_archive')),
                assignment_warning=('' if assignment_source_available else
                    'Aucune affectation Agents.csv configuree n est disponible. Importez un export SIMPLIFY2 contenant Agents.csv/Queues pour rendre les filtres de groupe analytiques.'))


def load_quality_file_scope(force=False):
    now=time.monotonic();fingerprint=_source_fingerprint()
    with _CACHE_LOCK:
        if (not force and _CACHE['data'] is not None and _CACHE.get('fingerprint')==fingerprint
                and now-_CACHE['stamp']<_CACHE_SECONDS):
            return _CACHE['data']
    # Build outside the cache lock. A cold scope reads JSON + small group tables;
    # concurrent requests must not queue behind disk/archive recovery.
    data=_build_scope()
    fingerprint=_source_fingerprint();now=time.monotonic()
    with _CACHE_LOCK:
        if (not force and _CACHE['data'] is not None and _CACHE.get('fingerprint')==fingerprint
                and now-_CACHE['stamp']<_CACHE_SECONDS):
            return _CACHE['data']
        _CACHE.update(stamp=now,data=data,fingerprint=fingerprint)
        return data


def invalidate_quality_scope_cache(*, touch_revision=True):
    if touch_revision:
        try:
            _REVISION_FILE.parent.mkdir(parents=True,exist_ok=True)
            _REVISION_FILE.touch()
        except OSError:
            pass
    with _CACHE_LOCK:
        _CACHE.update(stamp=0.0,data=None,fingerprint=None)
