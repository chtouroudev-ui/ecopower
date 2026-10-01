"""Canonical, cached analysis-group resolver for Nelyio.

Analysis groups are defined ONLY by configured files (quality_group_lines) and
ACTIVE agent-to-file assignments from the latest SIMPLIFY2 configuration.
Administrative user_group_members remain available for permissions/directory but
must not drive analytical filters. One agent can belong to several analysis groups.

RC2M: all reverse indexes are built once per quality-scope snapshot. This avoids
rebuilding/copying the full group catalogue once per row in Support/Diagnostic.
"""
from __future__ import annotations

import threading

from quality_importer import agent_key
from quality_scope import load_quality_file_scope

_INDEX_LOCK = threading.RLock()
_INDEX_SCOPE = None
_INDEX_CATALOG = ()
_INDEX_BY_ID = {}
_INDEX_MEMBERS = {}
_INDEX_GROUP_MEMBERS = {}
_INDEX_NAMES = {}
_INDEX_CAMPAIGNS = {}


def _canon(value):
    return agent_key(value)


def _public_group(g):
    """Return a detached JSON-safe group mapping; callers cannot corrupt indexes."""
    return dict(
        id=g['id'], name=g['name'], service_name=str(g.get('service_name') or ''),
        line_ids=list(g['line_ids']), campaign_ids=list(g['campaign_ids']),
        member_agent_ids=list(g['member_agent_ids']),
        file_count=g['file_count'], member_count=g['member_count'],
        matched_file_count=g.get('matched_file_count', g['file_count']),
        missing_line_ids=list(g.get('missing_line_ids', ())),
        campaign_count=g.get('campaign_count', len(g['campaign_ids'])),
        assignment_counts=dict(g.get('assignment_counts') or {}),
        basis='configured_files',
    )


def _ensure_index():
    global _INDEX_SCOPE, _INDEX_CATALOG, _INDEX_BY_ID, _INDEX_MEMBERS
    global _INDEX_GROUP_MEMBERS, _INDEX_NAMES, _INDEX_CAMPAIGNS
    scope = load_quality_file_scope()
    with _INDEX_LOCK:
        if scope is _INDEX_SCOPE:
            return
        catalog=[]; by_id={}; members_by_agent={}; group_members={}; names={}; campaigns={}
        for raw in scope.get('groups', []):
            gid=str(raw.get('id'))
            member_ids=frozenset(_canon(a) for a in raw.get('member_agent_ids', []) if _canon(a))
            campaign_ids=frozenset(str(c) for c in raw.get('campaign_ids', []) if str(c))
            g=dict(
                id=gid,
                name=str(raw.get('name') or ''),
                service_name=str(raw.get('service_name') or ''),
                line_ids=tuple(int(x) for x in raw.get('line_ids', []) if str(x).isdigit()),
                campaign_ids=tuple(sorted(campaign_ids)),
                member_agent_ids=tuple(sorted(member_ids)),
                file_count=int(raw.get('file_count') or 0),
                member_count=int(raw.get('member_count') or len(member_ids)),
                matched_file_count=int(raw.get('matched_file_count') or 0),
                missing_line_ids=tuple(raw.get('missing_line_ids') or ()),
                campaign_count=int(raw.get('campaign_count') or len(campaign_ids)),
                assignment_counts=dict(raw.get('assignment_counts') or {}),
                basis='configured_files',
            )
            catalog.append(g);by_id[gid]=g;group_members[gid]=member_ids;names[gid]=g['name']
            for aid in member_ids:
                members_by_agent.setdefault(aid,set()).add(gid)
            for cid in campaign_ids:
                campaigns.setdefault(cid,set()).add(gid)
        _INDEX_CATALOG=tuple(catalog)
        _INDEX_BY_ID=by_id
        _INDEX_MEMBERS={k:frozenset(v) for k,v in members_by_agent.items()}
        _INDEX_GROUP_MEMBERS=group_members
        _INDEX_NAMES=names
        _INDEX_CAMPAIGNS={k:frozenset(v) for k,v in campaigns.items()}
        _INDEX_SCOPE=scope


def catalog(include_unassigned=True):
    _ensure_index()
    with _INDEX_LOCK:
        return [_public_group(g) for g in _INDEX_CATALOG if include_unassigned or g['id']!='unassigned']


def filter_catalog():
    """Groups meaningful for analytical filters: saved groups with >=1 file."""
    return [g for g in catalog(include_unassigned=False) if int(g.get('file_count') or 0)>0]


def group_scope(group_id):
    """Return one canonical analytical group scope."""
    gid=str(group_id or '').strip()
    if not gid:
        return None
    _ensure_index()
    with _INDEX_LOCK:
        g=_INDEX_BY_ID.get(gid)
        return _public_group(g) if g else None


def selected_group_scope(selected_groups):
    selected={str(x).strip() for x in (selected_groups or []) if str(x).strip()}
    if not selected:
        return dict(group_ids=[],member_agent_ids=[],campaign_ids=[],line_ids=[])
    _ensure_index()
    with _INDEX_LOCK:
        found=[];members=set();campaigns=set();lines=set()
        for gid in selected:
            g=_INDEX_BY_ID.get(gid)
            if not g:continue
            found.append(gid);members.update(_INDEX_GROUP_MEMBERS.get(gid,()))
            campaigns.update(g['campaign_ids']);lines.update(g['line_ids'])
        return dict(group_ids=sorted(found),member_agent_ids=sorted(members),campaign_ids=sorted(campaigns),line_ids=sorted(lines))


def membership_map():
    _ensure_index()
    with _INDEX_LOCK:
        return _INDEX_MEMBERS


def group_ids_for_agent(agent):
    return sorted(membership_map().get(_canon(agent),()))


def group_names_for_agent(agent):
    ids=group_ids_for_agent(agent)
    _ensure_index()
    with _INDEX_LOCK:
        return [_INDEX_NAMES[i] for i in ids if i in _INDEX_NAMES]


def matches_agent_groups(agent, selected_groups):
    selected={str(x).strip() for x in (selected_groups or []) if str(x).strip()}
    if not selected:
        return True
    return bool(selected & set(membership_map().get(_canon(agent),())))


def selected_group_members(selected_groups):
    selected={str(x).strip() for x in (selected_groups or []) if str(x).strip()}
    if not selected:
        return None
    _ensure_index()
    with _INDEX_LOCK:
        members=set()
        for gid in selected:
            members.update(_INDEX_GROUP_MEMBERS.get(gid,()))
        return members


def group_ids_for_campaign(campaign_id):
    cid=str(campaign_id or '').strip()
    if not cid:
        return []
    _ensure_index()
    with _INDEX_LOCK:
        return sorted(_INDEX_CAMPAIGNS.get(cid,()))


def matches_campaign_groups(campaign_id, selected_groups):
    selected={str(x).strip() for x in (selected_groups or []) if str(x).strip()}
    if not selected:
        return True
    return bool(selected & set(group_ids_for_campaign(campaign_id)))
