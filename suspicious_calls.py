"""Individual-call investigation for Nelyio Quality.

This module deliberately works at Call ID level and keeps uncertain facts
explicit.  It does not infer a caller hangup from EndByAgent=0 and it uses the
configured Group -> File hierarchy rather than campaigns as a substitute for
queues.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from agent_directory import load_admin_directory, admin_name_for
from analysis_groups import catalog as analysis_group_catalog
from supervision_db import connect, config
from supervision_utils import date_range, selected_bounds, display, latest_agent_names

PAGE_SIZE = 100

_SUSPECT_SORT_SQL={
    'date':'start','agent':"COALESCE(NULLIF(first_agent,''),NULLIF(last_agent,''),'')",
    'queue':"COALESCE(first_queue,'')",'campaign':"COALESCE(NULLIF(last_campaign,''),NULLIF(first_campaign,''),campaign,'')",
    'ani':"COALESCE(ani,'')",'duration':'COALESCE(call_duration,duration,0)',
    'hold':'COALESCE(hold_duration,0)','finish':'COALESCE(end_by_agent,0)'
}

def _sort_spec(qs):
    key=_get(qs,'sort');direction=_get(qs,'sort_dir').lower()
    if not key or direction in ('','default'):
        return '', 'default'
    if key not in _SUSPECT_SORT_SQL or direction not in ('asc','desc'):
        raise ValueError('Tri des appels suspects invalide.')
    return key,direction


def _get(qs, key, default=''):
    return str(qs.get(key, [default])[0]).strip()


def _mask_phone(value):
    raw=str(value or '').strip()
    if len(raw) <= 4:
        return '*' * len(raw)
    return raw[:2] + '*' * max(2, len(raw)-4) + raw[-2:]


def _service_catalog(groups):
    names={str(g.get('service_name') or '').strip() for g in groups}
    return sorted((x for x in names if x), key=str.casefold)


def _scope_lines(groups, service_name='', group_id=''):
    selected=[]
    service_cf=str(service_name or '').strip().casefold()
    gid=str(group_id or '').strip()
    for g in groups:
        if str(g.get('id')) == 'unassigned':
            continue
        if gid and str(g.get('id')) != gid:
            continue
        if service_cf and str(g.get('service_name') or '').strip().casefold() != service_cf:
            continue
        selected.append(g)
    if (gid or service_cf) and not selected:
        raise ValueError('Service ou groupe inconnu : actualisez les filtres.')
    lines=sorted({str(x) for g in selected for x in (g.get('line_ids') or [])})
    return selected, lines


def _technical_exists(alias='p', detail_alias='d'):
    # Correlate only by a real agent identifier and a bounded call window.
    return f'''EXISTS (SELECT 1 FROM technical_signals ts
      WHERE TRIM(COALESCE(ts.agent,''))<>''
        AND (ts.agent={alias}.first_agent OR ts.agent={alias}.last_agent)
        AND ts.start>={alias}.start-15
        AND ts.start<={alias}.start+CASE
              WHEN COALESCE({detail_alias}.call_duration,{alias}.duration,0)>0
              THEN COALESCE({detail_alias}.call_duration,{alias}.duration,0)+15 ELSE 30 END)'''


def _complex_flow_sql(alias='p', detail_alias='d'):
    # Exact ODR relations identify rerouting / transfers / consultations.
    # LastTransfer is retained as a compatibility fallback for older imports.
    return f'''(TRIM(COALESCE({detail_alias}.last_transfer,''))<>'' OR EXISTS (
      SELECT 1 FROM phone_call_relations cr
      WHERE cr.import_id={alias}.import_id
        AND (cr.call_id={alias}.call_id OR cr.ref_call_id={alias}.call_id)
        AND cr.reason_code IN ('1','2','3','5','6')))'''


def _media_sql(cfg):
    duration="COALESCE(d.call_duration,p.duration,0)"
    media_seconds="COALESCE(p.conversation,0)"
    size="COALESCE((SELECT cr.size_bytes FROM call_recording_sizes cr WHERE cr.indice=p.indice),0)"
    reference=max(1,int(cfg.get('recording_reference_bps',8000) or 8000))
    low=max(5,min(100,int(cfg.get('recording_low_percent',60) or 60)))
    minimum=max(5,int(cfg.get('recording_min_seconds',30) or 30))
    density=f"({size}/NULLIF({media_seconds},0))"
    return dict(duration=duration,seconds=media_seconds,size=size,reference=reference,low=low,minimum=minimum,density=density)


def _category_sql(category,cfg):
    media=_media_sql(cfg)
    duration=media['duration']
    hold="COALESCE(h.hold_duration,0)"
    technical=_technical_exists()
    complex_flow=_complex_flow_sql()
    hold30=f'({duration}>0 AND {hold}>0 AND {hold}>={duration}*0.30 AND NOT {complex_flow})'
    hold50=f'({duration}>0 AND {hold}>0 AND {hold}>={duration}*0.50 AND NOT {complex_flow})'
    low_content=(f"({media['seconds']}>={media['minimum']} AND {hold}=0 AND NOT {complex_flow} "
                 f"AND {media['size']}>0 "
                 f"AND {media['density']}<{media['reference']}*{media['low']}/100.0)")
    # Backward-compatible aliases: old bookmarks wait30/wait50 now mean the
    # corrected in-call hold rule, never ODCalls.WaitDuration.
    if category=='wait30':category='hold30'
    if category=='wait50':category='hold50'
    mapping={
        'short':f'({duration}>=0 AND {duration}<10 AND NOT {complex_flow})',
        'long_suspect':f'({duration}>=10 AND (({hold30}) OR ({low_content}) OR {technical}))',
        'hold30':hold30,
        'hold50':hold50,
        'low_content':low_content,
        'end_agent':'COALESCE(p.end_by_agent,0)<>0',
        'technical':technical,
    }
    if category in ('','all'):
        return f'(({duration}>=0 AND {duration}<10 AND NOT {complex_flow}) OR {hold30} OR ({low_content}) OR {technical})'
    if category == 'end_caller':
        return 'FALSE'
    if category not in mapping:
        raise ValueError('Catégorie d’appel suspect inconnue.')
    return mapping[category]


def _reasons(row, technical=False, cfg=None):
    reasons=[]
    duration=float(row.get('call_duration') if row.get('call_duration') is not None else row.get('duration') or 0)
    hold=float(row.get('hold_duration') or 0)
    complex_flow=bool(row.get('complex_flow'))
    cfg=cfg or {}
    media_seconds=float(row.get('media_seconds') or 0)
    media_density=float(row.get('media_density_bps') or 0)
    ref=max(1,float(cfg.get('recording_reference_bps',8000) or 8000))
    low=float(cfg.get('recording_low_percent',60) or 60)
    critical=float(cfg.get('recording_critical_percent',35) or 35)
    minimum=float(cfg.get('recording_min_seconds',30) or 30)
    if 0 <= duration < 10 and not complex_flow:
        reasons.append('Appel < 10 s')
    if duration>0 and hold>0 and not complex_flow:
        ratio=hold/duration
        if ratio>=0.50: reasons.append('Mise en attente ≥ 50 %')
        elif ratio>=0.30: reasons.append('Mise en attente ≥ 30 %')
    if media_seconds>=minimum and hold<=0 and not complex_flow and media_density>0:
        pct=100*media_density/ref
        if pct<critical: reasons.append('Contenu très faible / size')
        elif pct<low: reasons.append('Contenu faible / size')
    if technical:
        reasons.append('Indice technique détecté')
    if int(row.get('end_by_agent') or 0):
        reasons.append('Fin par agent')
    return reasons


def view(qs):
    cfg=config();days=date_range(qs,cfg)
    category=_get(qs,'category','all')
    if category=='wait30':category='hold30'
    if category=='wait50':category='hold50'
    service=_get(qs,'service');group=_get(qs,'group');agent=_get(qs,'agent');campaign=_get(qs,'campaign')
    queue=_get(qs,'queue');page=int(_get(qs,'page','0') or 0)
    sort_key,sort_dir=_sort_spec(qs)
    if page < 0 or page > 100000: raise ValueError('Page invalide.')
    show_ani=_get(qs,'_show_ani')=='1'
    groups=analysis_group_catalog(include_unassigned=False)
    selected_groups,scope_lines=_scope_lines(groups,service,group)
    try:
        from pilotage_quality import _governance_context
        governance=_governance_context(groups,days)
    except Exception:
        governance=None

    with connect() as c:
        from db_compat import begin_read_snapshot
        begin_read_snapshot(c)
        cov={str(r['day']):int(r['import_id']) for r in c.execute(
            'SELECT day,import_id FROM call_coverage WHERE day BETWEEN ? AND ?', (days[0],days[-1]))}
        parts=[];params=[]
        for day in days:
            iid=cov.get(day)
            if iid is None: continue
            lo,hi=selected_bounds(day,cfg,qs,'0')
            where=['p.import_id=?','p.start>=?','p.start<?',"COALESCE(p.call_type,'')='1'"]
            args=[iid,lo,hi]
            if scope_lines:
                where.append('COALESCE(d.first_queue,\'\') IN ('+','.join('?' for _ in scope_lines)+')');args.extend(scope_lines)
            elif service or group:
                where.append('FALSE')
            if queue:
                where.append("COALESCE(d.first_queue,'')=?");args.append(queue)
            if agent:
                where.append('(p.first_agent=? OR p.last_agent=?)');args.extend((agent,agent))
            if campaign:
                where.append("COALESCE(NULLIF(d.last_campaign,''),NULLIF(d.first_campaign,''),p.campaign,'')=?");args.append(campaign)
            where.append(_category_sql(category,cfg))
            parts.append('''SELECT ? AS business_day,p.import_id,p.call_id,p.indice,p.start,p.call_type,p.duration,p.conversation,p.wait,
                p.ani,p.dnis,p.first_agent,p.last_agent,p.campaign,p.end_reason,p.no_agent,p.abandon,p.closed,p.end_by_agent,
                d.call_duration,d.wait_initial,d.total_wait,d.first_queue,d.last_queue,d.first_campaign,d.last_campaign,d.last_transfer,
                COALESCE(h.hold_duration,0) AS hold_duration,COALESCE(h.hold_segments,0) AS hold_segments,
                COALESCE((SELECT cr.size_bytes FROM call_recording_sizes cr WHERE cr.indice=p.indice),0) AS recording_size_bytes
                FROM phone_calls p LEFT JOIN phone_call_details d ON d.import_id=p.import_id AND d.call_id=p.call_id
                LEFT JOIN quality_call_holds h ON h.import_id=p.import_id AND h.call_id=p.call_id
                WHERE '''+' AND '.join(where))
            params.append(day);params.extend(args)
        if not parts:
            return _empty(days,groups,service,group,category)
        source=' UNION ALL '.join(parts)
        count=int(c.execute('SELECT COUNT(*) FROM ('+source+') q',params).fetchone()[0] or 0)
        sort_expr=_SUSPECT_SORT_SQL.get(sort_key,'start')
        order=('ASC' if sort_dir=='asc' else 'DESC') if sort_key else 'DESC'
        null_last=f"CASE WHEN {sort_expr} IS NULL OR CAST({sort_expr} AS TEXT)='' THEN 1 ELSE 0 END ASC"
        rows=[dict(r) for r in c.execute('SELECT * FROM ('+source+') q ORDER BY '+null_last+', '+sort_expr+' '+order+', start DESC,call_id DESC LIMIT ? OFFSET ?',[*params,PAGE_SIZE,page*PAGE_SIZE])]
        agent_summary_raw=[dict(r) for r in c.execute('''SELECT CASE
                    WHEN TRIM(COALESCE(first_agent,'')) NOT IN ('','0','S0') THEN first_agent
                    WHEN TRIM(COALESCE(last_agent,'')) NOT IN ('','0','S0') THEN last_agent
                    ELSE '' END AS agent,COUNT(*) AS calls
                  FROM ('''+source+''') q GROUP BY 1 HAVING CASE
                    WHEN TRIM(COALESCE(first_agent,'')) NOT IN ('','0','S0') THEN first_agent
                    WHEN TRIM(COALESCE(last_agent,'')) NOT IN ('','0','S0') THEN last_agent
                    ELSE '' END<>'' ORDER BY calls DESC,agent LIMIT 20''',params)]

        # Candidate values come from the selected period/scope, not global history.
        queues=[];campaigns=[];agents=[]
        cat_rows=c.execute('''SELECT DISTINCT COALESCE(first_queue,'') AS queue,
                    COALESCE(NULLIF(last_campaign,''),NULLIF(first_campaign,''),campaign,'') AS campaign,
                    COALESCE(NULLIF(first_agent,''),NULLIF(last_agent,''),'') AS agent
                  FROM ('''+source+') q',params).fetchall()
        queues=sorted({str(r['queue']) for r in cat_rows if str(r['queue'] or '').strip()})
        campaigns=sorted({str(r['campaign']) for r in cat_rows if str(r['campaign'] or '').strip()},key=str.casefold)
        agent_ids=sorted({str(r['agent']) for r in cat_rows if str(r['agent'] or '').strip() not in ('','0','S0')})

        # One bounded technical query enriches the current page; no per-call N+1.
        technical_by_call=defaultdict(list)
        if rows:
            lo=min(float(r['start']) for r in rows)-15
            hi=max(float(r['start'])+max(float(r.get('call_duration') or r.get('duration') or 0),0)+15 for r in rows)
            ids={str(r.get('first_agent') or '') for r in rows}|{str(r.get('last_agent') or '') for r in rows}
            ids={x for x in ids if x not in ('','0','S0')}
            signals=[]
            if ids:
                marks=','.join('?' for _ in ids)
                signals=[dict(r) for r in c.execute('SELECT source,agent,start,category,detail FROM technical_signals WHERE agent IN ('+marks+') AND start>=? AND start<=? ORDER BY start',[*sorted(ids),lo,hi])]
            for row in rows:
                duration=max(float(row.get('call_duration') or row.get('duration') or 0),0)
                aids={str(row.get('first_agent') or ''),str(row.get('last_agent') or '')}
                for sig in signals:
                    if sig['agent'] in aids and float(row['start'])-15 <= float(sig['start']) <= float(row['start'])+duration+15:
                        technical_by_call[row['call_id']].append(sig)

        # Exact relation enrichment for the current page.  These relations are
        # also used to exclude normal transfer/consultation flows from heuristic
        # suspicion (short/hold/low-content).
        relation_by_call=defaultdict(list)
        if rows:
            by_import=defaultdict(set)
            for r in rows:by_import[int(r['import_id'])].add(str(r['call_id']))
            for iid,ids in by_import.items():
                marks=','.join('?' for _ in ids)
                rels=c.execute('''SELECT call_id,ref_call_id,reason_code,reason_label FROM phone_call_relations
                  WHERE import_id=? AND (call_id IN ('''+marks+''') OR ref_call_id IN ('''+marks+'''))''',[iid,*sorted(ids),*sorted(ids)]).fetchall()
                for rr in rels:
                    item=dict(rr)
                    if str(rr['call_id']) in ids:relation_by_call[str(rr['call_id'])].append(item)
                    if str(rr['ref_call_id']) in ids:relation_by_call[str(rr['ref_call_id'])].append(item)

        name_ids=set(agent_ids)|{str(r.get('first_agent') or '') for r in rows}|{str(r.get('last_agent') or '') for r in rows}
        name_ids.update(str(r.get('agent') or '') for r in agent_summary_raw)
        names=latest_agent_names(c,{x for x in name_ids if x not in ('','0','S0')})
        directory=load_admin_directory()['users']
        agent_summary=[dict(agent=str(r['agent']),name=admin_name_for(str(r['agent']),directory,names.get(str(r['agent']),'')) or str(r['agent']),calls=int(r['calls'] or 0)) for r in agent_summary_raw]
        group_by_line=defaultdict(list)
        for g in groups:
            for lid in g.get('line_ids',[]): group_by_line[str(lid)].append(g)
        for row in rows:
            aid=str(row.get('first_agent') or row.get('last_agent') or '')
            row['agent']=aid
            row['agent_name']=admin_name_for(aid,directory,names.get(aid,'')) if aid else ''
            line=str(row.get('first_queue') or '')
            linked=group_by_line.get(line,[])
            row['groups']=[dict(id=g['id'],name=g['name'],service_name=g.get('service_name') or '') for g in linked]
            row['service_names']=sorted({str(g.get('service_name') or '') for g in linked if str(g.get('service_name') or '')},key=str.casefold)
            governance_reason=None
            if governance:
                try:
                    from pilotage_quality import _governance_decision
                    governance_reason=_governance_decision(
                        governance,row['start'],row.get('call_duration') or row.get('duration') or 1,
                        aid,row.get('last_campaign') or row.get('first_campaign') or row.get('campaign'),line)
                except Exception:
                    governance_reason=None
            row['governance_excluded']=bool(governance_reason)
            row['governance_reason']=governance_reason or ''
            row['start_text']=display(row['start'])
            duration=float(row.get('call_duration') if row.get('call_duration') is not None else row.get('duration') or 0)
            relations=relation_by_call.get(str(row['call_id']),[])
            complex_codes={'1','2','3','5','6'}
            row['relations']=relations
            row['complex_flow']=bool(str(row.get('last_transfer') or '').strip()) or any(str(x.get('reason_code') or '') in complex_codes for x in relations)
            row['complex_flow_labels']=sorted({str(x.get('reason_label') or ('Relation '+str(x.get('reason_code') or ''))).strip() for x in relations if str(x.get('reason_code') or '') in complex_codes})
            hold=float(row.get('hold_duration') or 0)
            row['hold_ratio']=round(100*hold/duration,1) if duration>0 and hold>0 else None
            media_seconds=float(row.get('conversation') or 0)
            size_bytes=int(row.get('recording_size_bytes') or 0)
            # RC12: never surface a WAV Size for a call without an actual
            # conversation. Contract-v3 sync additionally verifies date/agent.
            if media_seconds<=0:
                size_bytes=0
            density=(size_bytes/media_seconds) if media_seconds>0 and size_bytes>0 else None
            reference=max(1,float(cfg.get('recording_reference_bps',8000) or 8000))
            row['recording_size_bytes']=size_bytes
            row['recording_verified']=bool(size_bytes>0 and media_seconds>0)
            row['media_seconds']=media_seconds
            row['media_density_bps']=round(density,2) if density is not None else None
            row['media_density_kbps']=round(density/1000,2) if density is not None else None
            row['media_reference_bps']=reference
            row['media_coverage_pct']=round(100*density/reference,1) if density is not None else None
            signals=technical_by_call.get(row['call_id'],[])
            row['technical_signals']=signals
            row['reasons']=_reasons(row,bool(signals),cfg)
            row['finish_origin']='agent' if int(row.get('end_by_agent') or 0) else 'indeterminate'
            if not show_ani:
                row['ani']=_mask_phone(row.get('ani'))
            row['ani_masked']=not show_ani

        agent_choices=[dict(agent=a,name=admin_name_for(a,directory,names.get(a,'')) or a) for a in agent_ids]
        coverage=[dict(day=d,available=d in cov) for d in days]
        return dict(
            source='ODCalls + phone_call_details',date_from=days[0],date_to=days[-1],
            category=category,service=service,group=group,agent=agent,campaign=campaign,queue=queue,
            services=_service_catalog(groups),groups=groups,selected_groups=[str(g['id']) for g in selected_groups],
            queues=queues,campaigns=campaigns,agents=agent_choices,coverage=coverage,
            count=count,page=page,page_size=PAGE_SIZE,sort=sort_key,sort_dir=sort_dir,rows=rows,agent_summary=agent_summary,
            capabilities=dict(end_by_agent=True,end_by_caller=False,in_call_hold=True,complex_flow_filter=True,
                              media_size=bool(c.execute('SELECT 1 FROM call_recording_sizes LIMIT 1').fetchone()),technical_correlation=True,ani_full=show_ani),
            media_rule=dict(reference_bps=int(cfg.get('recording_reference_bps',8000) or 8000),
                            low_percent=int(cfg.get('recording_low_percent',60) or 60),
                            critical_percent=int(cfg.get('recording_critical_percent',35) or 35),
                            min_seconds=int(cfg.get('recording_min_seconds',30) or 30)),
            limitations=[
                'EndByAgent=0 ne prouve pas une fin par appelant : origine indéterminée.',
                'La mise en attente est la sous-action Hermes/Stats.AGENT confirmée par ODActions état 1003 et rattachée au CallID par SessionID ; ODCalls.WaitDuration n’est pas utilisé comme hold.',
                'Reroutages, transferts et consultations certifiés par ODRelations (ou LastTransfer en compatibilité) sont exclus des heuristiques de durée/hold.',
                'Le critère contenu faible utilise uniquement un WAV Hermes vérifié : même Indice, même journée, Conversation > 0 et agent cohérent. Les tailles anciennes/orphelines sont invalidées.',
                'Le rattachement groupe/service d’un appel repose sur FirstQueue lorsqu’elle est disponible.',
                'Un indice technique est une corrélation temporelle, pas une preuve de panne réseau.',
                'Les Policies/Déclarations n’effacent pas la preuve brute : un appel exclu des KPI reste visible ici et est explicitement annoté.'
            ],
        )


def _empty(days,groups,service,group,category):
    return dict(source='ODCalls + phone_call_details',date_from=days[0],date_to=days[-1],category=category,
                service=service,group=group,count=0,page=0,page_size=PAGE_SIZE,rows=[],agent_summary=[],coverage=[dict(day=d,available=False) for d in days],
                services=_service_catalog(groups),groups=groups,queues=[],campaigns=[],agents=[],
                capabilities=dict(end_by_agent=True,end_by_caller=False,in_call_hold=True,complex_flow_filter=True,media_size=False,technical_correlation=True,ani_full=False),
                limitations=['Aucune donnée appel disponible pour cette période.'])
