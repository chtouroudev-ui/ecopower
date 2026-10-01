"""Read adapters: one spool, existing Nelyio interfaces, no parallel KPIs."""
from __future__ import annotations

import json
import re

import collection_store as store
from nelyio_time import local_day, display


def enrich_names(names):
    """Live identities are a fallback, never a replacement for Administration."""
    for aid, agent in store.catalog()['agent'].items():
        names.setdefault(aid, ' '.join(filter(None, (agent.get('first_name'), agent.get('last_name')))))
    return names


def enrich_quality_live(result):
    """InitQueue knows queue labels; it does not know priorities or group IDs."""
    catalog = store.catalog()
    source_day = result.get('source_day') or ''
    used = 0
    for queue in list(result.get('queues', [])) + [q for a in result.get('agents', []) for q in a.get('queues', [])]:
        live = catalog['queue'].get(str(queue.get('line_id', '')))
        if live and live.get('name') and live['seen_day'] >= source_day:
            queue['line_name'] = live['name']
            queue['display_name'] = live['name']
            queue['live_name_at'] = display(live['seen_at'])
            queue['line_name_source'] = 'InitQueue / capture live'
            used += 1
    result['live_catalog'] = dict(queue_names=len(catalog['queue']), agent_names=len(catalog['agent']),
        names_used=used, group_sync=False, priorities_from_live=False)
    return result


def sync_extra_details(dst, admin):
    """Called inside the existing Details transaction; retry-safe by event_uid."""
    if not store.available(): return 0
    import details_store as ds
    last = int(ds._state_get(dst, 'collection_seq', '0')); maximum = last; count = 0
    labels = {'queue': 'File observee', 'agent': 'Agent observe', 'campaign': 'Campagne observee',
              'context': 'Files du contexte', 'context_state': 'Etat du contexte',
              'global_state': 'Etat global', 'call_observation': 'Appel observe (partiel)',
              'call_update': 'Mise a jour appel live', 'state_counters': 'Compteurs etat Hermes',
              'agent_metrics': 'Compteurs source agent', 'queue_metrics': 'Compteurs source file',
              'campaign_metrics': 'Compteurs source campagne',
              'agent_state_sample': 'Etat agent source non interprete',
              'protocol_telemetry': 'Diagnostic protocole Hermes'}
    with store.connect() as c:
        for row in c.execute('SELECT * FROM collection_events WHERE seq>? ORDER BY seq', (last,)):
            maximum = max(maximum, row['seq'])
            if row['event_type'] not in labels: continue  # states/signals already archived via Support
            p = json.loads(row['payload_json']); aid = p.get('agent', '')
            agent = ds._resolve_agent(aid, admin)
            if not aid:
                agent.update(agent_key='', agent='', name='')
            detail = ''
            if row['event_type'] == 'queue': detail = 'File ' + p['line_id'] + ' - ' + p['name']
            elif row['event_type'] == 'campaign': detail = p['campaign_id'] + ' - ' + p['name']
            elif row['event_type'] in ('context', 'agent'): detail = 'Files observees : ' + ', '.join(p.get('queues', []))
            elif row['event_type'] == 'call_observation':
                detail = 'File ' + p.get('line_id', '') + ' - numero ' + (p.get('phone') or 'non collecte') + '. Observation live : details et compteurs source conserves.'
            elif row['event_type'] == 'campaign_metrics':
                detail = 'Libelle source : ' + p.get('source_label', '') + '. Compteurs sans signification metier confirmee.'
            elif row['event_type'] == 'agent_state_sample':
                detail = 'UpAgtMState : preuve source uniquement ; aucune coupure ni appel deduit.'
            elif row['event_type'] == 'protocol_telemetry':
                detail = 'Callbacks inconnus : ' + str(p.get('unknown_total', 0)) + ' ; formes rejetees : ' + str(p.get('rejected_total', 0)) + '.'
            event = dict(event_uid='collection:'+row['event_key'], event_source='capture',
                source_label='Capture live', source_record_id=row['event_key'],
                primary_agent_key=agent['agent_key'], agent=aid, name=agent['name'],
                group_id=agent.get('group_id'), group_name=agent.get('group_name',''),
                pc=agent.get('pc',''), ip=agent.get('ip',''), start=row['stamp'], end=row['stamp'],
                duration=0, client=p.get('campaign',''), log_type=labels[row['event_type']],
                state=p.get('state',''), kind=row['event_type'], session=row['session_id'],
                collector=row['source'], detail=detail, raw=p)
            count += ds._insert_event(dst, event, [dict(agent, relation='principal')] if aid else [])
    ds._state_set(dst, 'collection_seq', maximum)
    return count


def call_observations(qs, cfg, days, export_days):
    """Observations without fabricated call IDs/durations; not KPI input.

The default search suppresses live observations on exported days, rather than
pretending an observation with no call identifier is an additional real call.
Raw evidence remains available in Details after export reconciliation.
"""
    get = lambda k, d='': qs.get(k, [d])[0]
    page = max(0, int(get('live_page', '0') or 0))
    suppressed = [d for d in days if d in export_days]
    result = dict(rows=[], count=0, page=page, page_size=50, suppressed_days=suppressed,
                  label='Observations live, hors totaux des appels exportes', revision='V56.3-live-1')
    if not store.available(): return result
    # These fields are not present in the observed callbacks; never fake them.
    if any(get(k) for k in ('indice', 'call_id', 'reason', 'call_type', 'call_issue', 'diagnosis', 'status')):
        result['unavailable_filters'] = True
        return result
    from supervision_utils import selected_bounds
    from agent_directory import load_admin_directory, admin_name_for, admin_group_for
    from analysis_groups import matches_agent_groups, group_ids_for_agent, group_names_for_agent
    from governance_engine import governed_visible_events
    from support_filters import _support_excluded_slots, _in_support_excluded_slot
    directory = load_admin_directory(); users = directory['users']; live_agents = store.catalog()['agent']
    bounds = {d:selected_bounds(d, cfg, qs, '1') for d in days if d not in export_days}
    if not bounds: return result
    phone = re.sub(r'[^0-9]', '', get('phone'))
    if get('phone') and not phone: raise ValueError('Le numero doit contenir des chiffres.')
    if phone and get('phone_field', 'any') not in ('any', 'ani'):
        result['unavailable_filters'] = True
        return result
    term = get('agent').strip().casefold(); campaign = get('campaign').strip().casefold()
    groups = set(qs.get('group', [])); rows = []; slots = _support_excluded_slots(qs)
    import time
    import collection_calls
    with store.connect() as c:
        has_projection = c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='collection_call_details'").fetchone()
        if has_projection:
            sql = """SELECT e.*, d.payload_json AS detail_payload, d.last_stamp AS detail_stamp,
                     d.status AS detail_status, d.observed_until AS observed_until, s.last_response AS session_receipt,
                     s.status AS session_status, s.connection_state AS connection_state
                     FROM collection_events e
                     LEFT JOIN collection_call_details d ON d.event_key=e.event_key
                     LEFT JOIN collection_sessions s ON s.id=e.session_id
                     WHERE e.event_type='call_observation' AND e.stamp>=? AND e.stamp<?
                     ORDER BY e.stamp DESC,e.seq DESC"""
        else:
            sql = """SELECT *, NULL AS detail_payload FROM collection_events
                     WHERE event_type='call_observation' AND stamp>=? AND stamp<? ORDER BY stamp DESC,seq DESC"""
        for r in c.execute(sql, (min(x[0] for x in bounds.values()), max(x[1] for x in bounds.values()))):
            day = local_day(r['stamp']); b = bounds.get(day)
            if not b or not b[0] <= r['stamp'] < b[1]: continue
            if slots and _in_support_excluded_slot(r['stamp'], cfg, slots): continue
            p = json.loads(r['detail_payload'] or r['payload_json']); aid = p.get('agent','')
            if phone and phone not in re.sub(r'[^0-9]', '', p.get('phone','')): continue
            ag = live_agents.get(aid, {})
            fallback = ' '.join(filter(None, (ag.get('first_name'), ag.get('last_name')))) or aid
            name = admin_name_for(aid, users, fallback); gid, gn = admin_group_for(aid, users)
            if term and term not in (aid+' '+name).casefold(): continue
            if campaign and campaign not in p.get('campaign','').casefold(): continue
            if groups and not matches_agent_groups(aid, groups): continue
            has_detail = bool(r['detail_payload'])
            last_stamp = r['detail_stamp'] if has_detail else r['stamp']
            status = r['detail_status'] if has_detail else 'legacy'
            if status == 'observing':
                # Never advance using wall-clock time. Silent capture cannot
                # create ever-growing durations after browser/network failure.
                receipt = r['session_receipt'] or last_stamp
                if r['session_status'] in store.TERMINAL:
                    status = 'capture_ended'
                elif r['connection_state'] != 'receiving' or time.time() - receipt > 30:
                    status = 'unconfirmed'
            observed_until = r['observed_until'] if has_detail else r['stamp']
            span = max(0.0, observed_until - r['stamp']) if has_detail and not p.get('legacy') and observed_until > r['stamp'] else None
            if p.get('continuity_gap') or status == 'capture_gap':
                span = None
            # These are elapsed RECEIPTS for an observation. ODCalls fields
            # remain absent so nobody can mistake them for confirmed call KPIs.
            analysis_ids=group_ids_for_agent(aid);analysis_names=group_names_for_agent(aid)
            rows.append(dict(key='collection:'+r['event_key'], agent=aid, name=name,
                group_id=(analysis_ids[0] if len(analysis_ids)==1 else None),
                group_name=(analysis_names[0] if len(analysis_names)==1 else ''),
                group_ids=analysis_ids,group_names=analysis_names, start=r['stamp'], end=last_stamp, seconds=0,
                start_text=display(r['stamp']), last_observation_text=display(last_stamp), observed_until_text=display(observed_until),
                source='capture', kind='call', category='call_observation', line_id=p.get('line_id',''), line_name=p.get('line_name',''),
                campaign=p.get('campaign',''), phone=p.get('phone',''), phone_status=p.get('phone_status', 'available' if p.get('phone') else 'legacy'),
                state=p.get('state',''), next_state=p.get('next_state', ''), live_status=status,
                quality='Observation live - durees metier non certifiees', indice=None, duration=None,
                conversation=None, wait=None, observed_span_seconds=span,
                partial_start=p.get('partial_start',True),
                source_function=p.get('source_function', 'UpAgtTState'),
                source_counters=p.get('source_counters', {}), first_counters=p.get('first_counters', {}),
                end_counters=p.get('end_counters', {}), observation_count=p.get('observations',1),
                timeline=[dict(t, stamp_text=display(t['stamp'])) for t in p.get('timeline', [])],
                timeline_trimmed=p.get('timeline_trimmed',0), parser_version=p.get('parser_version','legacy'),
                # private fields removed before returning; used only for selected-page context
                _source=r['source'], _stamp=observed_until))
    rows, excluded = governed_visible_events(rows, module='calls')
    selected = rows[page*50:(page+1)*50]
    with store.connect() as c:
        for row in selected:
            row['context_counters'] = collection_calls.contextual_counters(
                c, row['_source'], row['agent'], row['line_id'], row['_stamp'])
            for stat in row['context_counters']:
                stat['stamp_text'] = display(stat['stamp'])
            row.pop('_source', None); row.pop('_stamp', None)
    result.update(count=len(rows), rows=selected, excluded_by_rules=len(excluded))
    return result
