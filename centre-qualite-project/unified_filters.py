"""Common filter normalization for Nelyio technical modules.

Phase A deliberately keeps the historical query-string contract working while
exposing one canonical filter model to Support, Analyse, Details and Reports.
Technical provenance (source/type) may still be accepted for diagnostics and
backward compatibility, but it is intentionally excluded from the public model.
"""
from copy import deepcopy
from datetime import datetime, timedelta


def _first(qs, key, default=''):
    values=qs.get(key)
    if not values:
        return default
    value=values[0]
    return default if value is None else str(value)


def _values(qs, key):
    return [str(v).strip() for v in qs.get(key, []) if str(v).strip()]


def _bool(qs, key, default=False):
    raw=_first(qs,key,'1' if default else '').strip().lower()
    return raw in ('1','true','yes','on')


def _date(value, label):
    try:
        return datetime.strptime(str(value or ''),'%Y-%m-%d')
    except ValueError as exc:
        raise ValueError(f'{label} invalide. Utiliser AAAA-MM-JJ.') from exc


def _time(value, label):
    try:
        return datetime.strptime(str(value or ''),'%H:%M')
    except ValueError as exc:
        raise ValueError(f'{label} invalide. Utiliser HH:MM.') from exc


def normalize_filters(qs, cfg, *, default_date_from=None, default_date_to=None,
                      default_full_day='1', max_days=93, allow_legacy_technical=True):
    """Return ``(query, public, days, hidden)`` for a request.

    ``query`` is safe to pass to the existing calculation engines.  ``public``
    is the user-facing common model.  ``hidden`` contains legacy technical
    overrides that remain accepted but are no longer part of the normal UI.
    """
    query={str(k):[str(x) for x in v] for k,v in dict(qs or {}).items()}

    # Phase E: old hard-coded time exclusions remain parseable for backwards
    # compatibility, but a migrated installation can switch them off globally
    # to avoid applying the same exclusion twice next to an explicit Policy.
    try:
        from governance_migration import legacy_mode
        legacy_exclusion_mode=legacy_mode()
    except Exception:
        legacy_exclusion_mode='compat'
    query['_legacy_exclusion_mode']=[legacy_exclusion_mode]

    # Compatibility aliases used by older Analytics/Details screens.
    if not query.get('min_disconnect') and query.get('min_duration'):
        query['min_disconnect']=list(query['min_duration'])
    if not query.get('date_from') and query.get('day'):
        query['date_from']=[query['day'][0]]
    if not query.get('date_to') and query.get('date_from'):
        query['date_to']=[query['date_from'][0]]

    if not query.get('date_from') and default_date_from:
        query['date_from']=[str(default_date_from)]
    if not query.get('date_to'):
        if default_date_to:
            query['date_to']=[str(default_date_to)]
        elif query.get('date_from'):
            query['date_to']=[query['date_from'][0]]

    if not query.get('date_from'):
        today=datetime.now().strftime('%Y-%m-%d')
        query['date_from']=[today];query['date_to']=[today]

    start=_date(_first(query,'date_from'),'Date de début')
    end=_date(_first(query,'date_to',_first(query,'date_from')),'Date de fin')
    length=(end-start).days+1
    if not 1<=length<=max_days:
        raise ValueError(f'Choisir une période de 1 à {max_days} jours, avec la fin après le début.')
    days=[(start+timedelta(days=i)).strftime('%Y-%m-%d') for i in range(length)]
    query['date_from']=[days[0]];query['date_to']=[days[-1]]

    time_from=_first(query,'time_from').strip();time_to=_first(query,'time_to').strip()
    if (time_from and not time_to) or (time_to and not time_from):
        raise ValueError('Renseigner à la fois l’heure de début et l’heure de fin.')
    if time_from:
        tf=_time(time_from,'Heure de début');tt=_time(time_to,'Heure de fin')
        if (tf.hour,tf.minute)>=(tt.hour,tt.minute):
            raise ValueError('L’heure de fin doit être après l’heure de début.')
    else:
        # One common visible default. Existing engines still understand
        # full_day when a caller explicitly needs 00:00-24:00.
        full_day=_first(query,'full_day',default_full_day).strip() or default_full_day
        query['full_day']=[full_day]
        if full_day=='1':
            time_from='00:00';time_to='24:00'
        else:
            time_from=str(cfg.get('work_start','08:00'));time_to=str(cfg.get('work_end','19:00'))

    try:
        min_disconnect=max(0.0,min(3600.0,float(_first(query,'min_disconnect','0') or 0)))
    except ValueError as exc:
        raise ValueError('Durée minimum de déconnexion invalide.') from exc
    # Keep an integer-looking query value stable for old callers/tests.
    min_text=str(int(min_disconnect)) if min_disconnect.is_integer() else str(min_disconnect)
    query['min_disconnect']=[min_text]
    query.pop('min_duration',None)

    call_scope=_first(query,'call_scope','all').strip().lower() or 'all'
    if call_scope not in ('all','during','outside'):
        raise ValueError('Filtre de contexte de déconnexion invalide.')
    query['call_scope']=[call_scope]

    groups=[]
    for value in _values(query,'group'):
        if value not in groups:groups.append(value)
    if groups:query['group']=groups
    else:query.pop('group',None)

    agent=_first(query,'agent').strip()
    include_agents=[]
    for value in _values(query,'include_agent'):
        if value not in include_agents:include_agents.append(value)
    exclude_agents=[]
    for value in _values(query,'exclude_agent'):
        if value not in exclude_agents:exclude_agents.append(value)

    # Legacy technical selectors remain accepted for links/API diagnostics but
    # do not appear in the common visible filter model.
    source=_first(query,'source').strip().lower()
    if source not in ('','export','capture'):
        if allow_legacy_technical:raise ValueError('Source technique invalide.')
        source=''
    incident_type=_first(query,'type',_first(query,'category')).strip()
    hidden={'source':source,'type':incident_type}
    if source:query['source']=[source]
    else:query.pop('source',None)

    public={
        'date_from':days[0],
        'date_to':days[-1],
        'time_from':time_from,
        'time_to':time_to,
        'agent':agent,
        'groups':groups,
        'group':groups[0] if len(groups)==1 else '',
        'include_agents':include_agents,
        'exclude_agents':exclude_agents,
        'min_disconnect':min_disconnect,
        'call_scope':call_scope,
        'exclude_12_13':_bool(query,'exclude_12_13'),
        'exclude_13_14':_bool(query,'exclude_13_14'),
        'exclude_custom_from':_first(query,'exclude_custom_from').strip(),
        'exclude_custom_to':_first(query,'exclude_custom_to').strip(),
        'legacy_exclusion_mode':legacy_exclusion_mode,
        'legacy_exclusions_active':legacy_exclusion_mode=='compat',
    }
    return query,public,days,hidden


def public_filter_contract(filters):
    """Return a detached JSON-safe copy with stable common field names."""
    return deepcopy(filters or {})


def apply_row_scope(rows, filters, *, agent_fields=('agent','name','pc'), group_field='group_id'):
    """Apply the common text-agent/group scope to already normalized rows."""
    f=filters or {};term=str(f.get('agent') or '').strip().lower();groups={str(x) for x in (f.get('groups') or []) if str(x)}
    from analysis_groups import selected_group_members, _canon
    members = selected_group_members(groups) if groups else None
    out=[]
    for row in rows:
        if term:
            hay=' '.join(str(row.get(k) or '') for k in agent_fields).lower()
            if term not in hay:continue
        if groups:
            agent=row.get('agent') or row.get('first_agent') or row.get('last_agent')
            if _canon(agent) not in members:
                continue
        out.append(row)
    return out
