"""Canonical display identity helpers for RC29.

This module is deliberately presentation-only: it resolves labels without
changing analytical membership, call attribution, KPI sources or raw technical
identifiers. Technical ids always remain available to callers.
"""
from __future__ import annotations

from collections import defaultdict


def _clean(value):
    return str(value or '').strip()


def _cf(value):
    return _clean(value).casefold()


def resolve_agent_identity(agent, *, admin_users=None, observed_name='', configured_name='', fallback=''):
    """Resolve one agent display name while preserving the technical id.

    Priority is explicit and shared across RC29 views:
      1. Administration directory when it has a real first/last/display name;
      2. observed Hermes/SIMPLIFY2 name;
      3. configured Quality name;
      4. caller fallback;
      5. technical id.
    """
    technical_id=_clean(agent)
    admin_users=admin_users or {}
    admin_name=''
    admin_identifier=''
    try:
        from agent_directory import admin_user_for
        user=admin_user_for(technical_id,admin_users) or {}
        # Do not let an identifier-only directory row hide a better observed name.
        if _clean(user.get('first_name')) or _clean(user.get('last_name')):
            admin_name=_clean(user.get('display_name'))
        admin_identifier=_clean(user.get('user_identifier'))
    except Exception:
        user={}
    choices=(
        ('administration',admin_name),
        ('observed',_clean(observed_name)),
        ('configured',_clean(configured_name)),
        ('fallback',_clean(fallback)),
        ('technical_id',technical_id),
    )
    source='technical_id';display_name=technical_id
    for candidate_source,candidate in choices:
        if candidate:
            source=candidate_source;display_name=candidate;break
    return {
        'agent_id':technical_id,
        'display_name':display_name,
        'name_source':source,
        'admin_identifier':admin_identifier,
    }


def resolve_agent_name(agent, *, admin_users=None, observed_name='', configured_name='', fallback=''):
    return resolve_agent_identity(
        agent,admin_users=admin_users,observed_name=observed_name,
        configured_name=configured_name,fallback=fallback,
    )['display_name']


def campaign_catalog(scope=None):
    """Return the configured campaign catalogue with id and label indexes."""
    if scope is None:
        from quality_scope import load_quality_file_scope
        scope=load_quality_file_scope()
    rows=[];by_id={};by_label=defaultdict(list)
    for cid,raw in (scope.get('campaigns') or {}).items():
        cid=_clean(cid)
        if not cid:continue
        label=_clean((raw or {}).get('campaign_name')) or cid
        item={'campaign_id':cid,'campaign_label':label}
        rows.append(item)
        by_id[_cf(cid)]=item
        by_label[_cf(label)].append(item)
    return rows,by_id,by_label


def resolve_campaign_identity(raw_id='', raw_label='', *, scope=None, catalog=None):
    """Resolve campaign id/label without merging ambiguous observed labels.

    Configured id wins. A configured label is accepted only when unique.
    Unmatched observations keep an explicit RAW: identity so incidents and
    filters never silently merge two campaigns that merely share a label.
    """
    rows,by_id,by_label=catalog or campaign_catalog(scope)
    rid=_clean(raw_id);label=_clean(raw_label) or rid
    if _cf(rid) in by_id:
        item=by_id[_cf(rid)]
        return {'campaign_id':item['campaign_id'],'campaign_label':item['campaign_label'],'identity_quality':'configured_id'}
    if _cf(label) in by_id:
        item=by_id[_cf(label)]
        return {'campaign_id':item['campaign_id'],'campaign_label':item['campaign_label'],'identity_quality':'configured_id'}
    matches=by_label.get(_cf(label),[])
    if len(matches)==1:
        item=matches[0]
        return {'campaign_id':item['campaign_id'],'campaign_label':item['campaign_label'],'identity_quality':'configured_label'}
    raw=rid or label
    if not raw:
        return {'campaign_id':'','campaign_label':'','identity_quality':'unavailable'}
    return {'campaign_id':'RAW:'+_cf(raw),'campaign_label':label or raw,'identity_quality':'observed_only'}


def resolve_campaign_name(raw_id='', raw_label='', *, scope=None, catalog=None):
    return resolve_campaign_identity(raw_id,raw_label,scope=scope,catalog=catalog)['campaign_label']
