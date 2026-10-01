"""Generic Nelyio policy engine (Phase C).

Policies never delete raw events. They attach a decision explaining how an
otherwise-valid technical event must be treated by Support/Analytics/Reports.
"""
import json

from app_db import db_connect
from governance_intervals import (event_datetime, policy_ranges, summarize_actions,
    attach_decision, subtract_ranges, merge_ranges, time_minutes)

SCOPE_RANK={'GLOBAL':1,'GROUP':2,'AGENT':3}
ALLOWED_MODULES={'support','analytics','reports','details'}
ALLOWED_TYPES={'PAUSE','REUNION','FORMATION','INTERVENTION','AUTORISATION','HORAIRE_PARTICULIER','EXCLUSION_TECHNIQUE','AUTRE'}
ACTION_KEYS={'exclude_statistics','exclude_lost_time','exclude_score','mark_authorized','reclassify'}
AUTO_FILTER_TYPES={'PAUSE','REUNION','FORMATION','INTERVENTION','AUTORISATION','HORAIRE_PARTICULIER','EXCLUSION_TECHNIQUE'}


def _auto_filter_period(policy):
    """Return True when a configured organizational Policy defines a period.

    Phase F3.2: configured organizational durations are global exclusions across
    every technical surface (Support, Diagnostic/Détails, Analyse, Rapports).
    The module list still controls non-filter annotations/reclassification.
    """
    typ=str(policy.get('policy_type') or '').upper()
    weekdays=policy.get('_weekdays_set') if '_weekdays_set' in policy else set(policy.get('weekdays') or [])
    temporal=bool(policy.get('time_from') or policy.get('time_to') or policy.get('date_from') or policy.get('date_to') or weekdays)
    if not temporal:
        return False
    # Saved organizational Policies and legacy explicit exclusion Policies both
    # become application-wide when they define an actual period.
    return typ in AUTO_FILTER_TYPES or bool((policy.get('actions') or {}).get('exclude_statistics'))


def _json(raw, default):
    try:
        value=json.loads(raw or '')
        return value if isinstance(value,type(default)) else default
    except Exception:
        return default


def _norm_key(value):
    return str(value or '').strip().casefold()


def _policy_row(row, targets=()):
    d=dict(row)
    d['enabled']=bool(d.get('enabled'))
    d['weekdays']=_json(d.pop('weekdays_json','[]'),[])
    d['actions']=_json(d.pop('action_json','{}'),{})
    d['modules']=_json(d.pop('modules_json','[]'),[])
    d['targets']=[dict(x) for x in targets]
    d['_weekdays_set']=frozenset(int(x) for x in d['weekdays'] if str(x).lstrip('-').isdigit())
    d['_time_from_min']=_time_minutes(d.get('time_from'))
    d['_time_to_min']=_time_minutes(d.get('time_to'))
    d['_agent_targets']=frozenset(_norm_key(x.get('target_key')) for x in d['targets'] if str(x.get('target_type') or '').upper()=='AGENT')
    d['_group_targets']=frozenset(_norm_key(x.get('target_key')) for x in d['targets'] if str(x.get('target_type') or '').upper()=='GROUP')
    d['_has_global_target']=any(str(x.get('target_type') or '').upper()=='GLOBAL' for x in d['targets'])
    return d


def load_policies(include_disabled=False, include_deleted=False):
    with db_connect() as con:
        where=[];params=[]
        if not include_disabled: where.append('p.enabled=1')
        if not include_deleted: where.append('p.deleted_at IS NULL')
        sql='SELECT p.* FROM nelyio_policies p'+((' WHERE '+' AND '.join(where)) if where else '')+' ORDER BY p.priority DESC,p.id ASC'
        rows=con.execute(sql,params).fetchall()
        by={int(r['id']):[] for r in rows}
        if by:
            marks=','.join('?' for _ in by)
            for t in con.execute(f'SELECT policy_id,target_type,target_key FROM nelyio_policy_targets WHERE policy_id IN ({marks}) ORDER BY id',tuple(by)):
                by[int(t['policy_id'])].append(t)
        return [_policy_row(r,by.get(int(r['id']),[])) for r in rows]


def public_policy(policy):
    p={k:v for k,v in dict(policy or {}).items() if not str(k).startswith('_')}
    p['actions']={k:v for k,v in dict(p.get('actions') or {}).items() if k in ACTION_KEYS}
    p['modules']=[m for m in p.get('modules',[]) if m in ALLOWED_MODULES]
    return p


def policy_snapshot(include_disabled=True):
    return [public_policy(p) for p in load_policies(include_disabled=include_disabled)]


def _event_dt(event):
    return event_datetime(event)


def _time_minutes(text):
    return time_minutes(text)


def _window_matches(policy, event):
    return bool(policy_ranges(policy, event))


def _target_specificity(policy,event):
    targets=policy.get('targets') or []
    if not targets:return SCOPE_RANK['GLOBAL'] if policy.get('target_scope')=='GLOBAL' else 0
    agent_keys={_norm_key(event.get('agent')),_norm_key(event.get('name'))}
    group_keys={_norm_key(event.get('group_id')),_norm_key(event.get('group_name'))}
    agent_targets=policy.get('_agent_targets')
    group_targets=policy.get('_group_targets')
    if agent_targets is not None:
        if agent_keys & set(agent_targets):return SCOPE_RANK['AGENT']
        if group_keys & set(group_targets or ()):return SCOPE_RANK['GROUP']
        if policy.get('_has_global_target'):return SCOPE_RANK['GLOBAL']
        return 0
    matched=[]
    for t in targets:
        typ=str(t.get('target_type') or '').upper();key=_norm_key(t.get('target_key'))
        if typ=='GLOBAL':matched.append(SCOPE_RANK['GLOBAL'])
        elif typ=='AGENT' and key in agent_keys:matched.append(SCOPE_RANK['AGENT'])
        elif typ=='GROUP' and key in group_keys:matched.append(SCOPE_RANK['GROUP'])
    return max(matched or [0])


def matching_policies(event,module='support',policies=None):
    module=str(module or 'support').lower()
    rows=policies if policies is not None else load_policies()
    out=[]
    for p in rows:
        if not p.get('enabled') or p.get('deleted_at'):continue
        mods=set(p.get('modules') or [])
        # A configured organizational duration is a global application filter.
        # Do not let a legacy module selection make the same period visible in
        # another Nelyio screen. Non-filter policies still respect modules.
        if mods and module not in mods and not _auto_filter_period(p):continue
        specificity=_target_specificity(p,event)
        if not specificity:continue
        ranges=policy_ranges(p,event)
        if not ranges:continue
        q=dict(p);q['_specificity']=specificity;q['_event_ranges']=ranges;out.append(q)
    # Specificity is local to each time segment. An agent rule must not erase
    # a group/global rule outside the period it actually covers.
    effective=[]
    higher=[]
    for rank in sorted({int(p['_specificity']) for p in out}, reverse=True):
        same_rank=[p for p in out if int(p['_specificity'])==rank]
        for p in same_rank:
            p['_event_ranges']=subtract_ranges(p['_event_ranges'],higher)
            if p['_event_ranges']:effective.append(p)
        higher=merge_ranges(higher+[r for p in same_rank for r in p['_event_ranges']])
    effective.sort(key=lambda p:(-int(p['_specificity']),-int(p.get('priority') or 0),int(p.get('id') or 0)))
    return effective


def evaluate_event(event,module='support',policies=None):
    matches=matching_policies(event,module,policies)
    decision={'applied':False,'policy_ids':[],'policy_names':[],'exclude_statistics':False,'exclude_lost_time':False,'exclude_score':False,'mark_authorized':False,'reclassify':'','reason':''}
    intervals={}
    if not matches:
        decision.update(summarize_actions(event,intervals))
        return decision
    decision['applied']=True
    # Most-specific/highest-priority rule wins for reclassification; boolean
    # exclusions are additive so a broader rule cannot accidentally undo one.
    for p in matches:
        a=p.get('actions') or {}
        decision['policy_ids'].append(int(p.get('id') or 0));decision['policy_names'].append(str(p.get('name') or 'Policy'))
        auto_filter=_auto_filter_period(p)
        actions={key:bool(a.get(key)) for key in ('exclude_statistics','exclude_lost_time','exclude_score','mark_authorized')}
        if auto_filter:
            actions.update(exclude_statistics=True,exclude_lost_time=True,exclude_score=True)
            if str(p.get('policy_type') or '').upper()!='EXCLUSION_TECHNIQUE':
                actions['mark_authorized']=True
        for key,value in actions.items():
            if value:intervals.setdefault(key,[]).extend(p['_event_ranges'])
        if not decision['reclassify'] and str(a.get('reclassify') or '').strip():decision['reclassify']=str(a.get('reclassify')).strip()[:80]
    decision['reason']='; '.join(decision['policy_names'])
    decision.update(summarize_actions(event,intervals))
    return decision


def apply_event_policy(event,module='support',policies=None):
    out=dict(event);d=evaluate_event(out,module,policies)
    out['policy_decision']=d
    out['policy_applied']=bool(d['applied'])
    out['policy_reason']=d['reason']
    attach_decision(out,'policy',d)
    if d['reclassify']:
        out['policy_original_label']=out.get('event_label') or ''
        out['event_label']=d['reclassify']
    return out


def apply_policies(events,module='support',policies=None):
    rows=policies if policies is not None else load_policies()
    return [apply_event_policy(e,module,rows) for e in (events or [])]
