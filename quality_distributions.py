"""Hourly inbound distribution + RC29 Phase 4 workforce perimeter metrics."""
from collections import defaultdict
from datetime import date, datetime, timedelta
import html

from quality_metrics import ensure_schema, VERSION, _version_ready
from quality_rules import agent_assigned_sql, agent_unassigned_sql
from quality_summary import group_catalog
from quality_importer import agent_key
from agent_directory import load_admin_directory
from identity_resolver import resolve_agent_name, resolve_campaign_identity, campaign_catalog as identity_campaign_catalog
from quality_scope import load_quality_file_scope
from quality_workforce import expected_agents, bucket_status, new_interval_map, merge_intervals
from supervision_db import connect, config
from nelyio_time import display, day_bounds, local_wall_timestamp, today


def _wall(day, minute):
    minute=int(minute)
    if minute>=1440:
        nxt=(datetime.strptime(str(day),'%Y-%m-%d')+timedelta(days=1)).strftime('%Y-%m-%d')
        return local_wall_timestamp(nxt,0,0)
    return local_wall_timestamp(day,minute//60,minute%60)


def _inbound_state(value):
    label=html.unescape(str(value or '')).strip().casefold()
    return label in ('appel entrant','inbound call') or ('appel entrant' in label and 'manuel' not in label)


def _fallback_work_state(state,kind):
    label=html.unescape(str(state or '')).strip().casefold()
    k=str(kind or '').strip().casefold()
    if _inbound_state(label):return True
    if label in ('appel manuel','manual call','outbound call'):return True
    if k in ('call','ready','wrap'):return True
    return label in ('prêt','pret','post-travail','supervision','numérotation','sonnerie','consultation')


def _workforce_evidence(c, first, last, start, end, population):
    """Return per-day positive-work/pause evidence and coverage.

    coverage is the Stats.AGENT daily reference. Enhanced imports use the
    normalized quality_agent_facts table; old imports use core activities.
    """
    refs={r['day']:dict(r) for r in c.execute('''SELECT cov.day,cov.import_id,q.hold_reference
        FROM coverage cov LEFT JOIN quality_agent_imports q ON q.import_id=cov.import_id
        WHERE cov.day BETWEEN ? AND ?''',(first,last))}
    a,b=date.fromisoformat(first),date.fromisoformat(last)
    days={}
    pop=sorted(set(population or ()))
    for i in range((b-a).days+1):
        day=(a+timedelta(days=i)).isoformat();ref=refs.get(day)
        lo,hi=day_bounds(day,start,end) if start else day_bounds(day)
        days[day]={'available':bool(ref),'import_id':int(ref['import_id']) if ref else None,
                   'enhanced':bool(ref and ref.get('hold_reference') is not None),
                   'lo':float(lo),'hi':float(hi),'work':new_interval_map(),'pause':new_interval_map()}
    if not pop:return days
    aliases=sorted({alias for aid in pop for alias in ((aid,'S'+aid) if str(aid).isdigit() else (aid,))})
    for day,d in days.items():
        if not d['available']:continue
        iid=d['import_id'];lo=d['lo'];hi=d['hi']
        if d['enhanced']:
            params=[iid,hi,lo]+pop
            sql='''SELECT agent,start,"end",kind,invalid FROM quality_agent_facts
                   WHERE import_id=? AND start<? AND "end">? AND agent IN ('''+','.join('?'*len(pop))+')'
            for r in c.execute(sql,params):
                if r['invalid']:continue
                aid=agent_key(r['agent']);kind=str(r['kind'] or '')
                begin,end_i=max(lo,float(r['start'])),min(hi,float(r['end']))
                if end_i<=begin:continue
                if kind=='pause':merge_intervals(d['pause'],aid,(begin,end_i))
                # Explicit positive work evidence only. Offline/pause/coaching/
                # unknown never turn an agent into worked.
                if kind in ('work','inbound','manual','hold'):
                    merge_intervals(d['work'],aid,(begin,end_i))
        else:
            params=[iid,hi,lo]+aliases
            sql='''SELECT agent,start,"end",state,kind FROM activities
                   WHERE import_id=? AND start<? AND "end">? AND agent IN ('''+','.join('?'*len(aliases))+')'
            for r in c.execute(sql,params):
                aid=agent_key(r['agent']);begin,end_i=max(lo,float(r['start'])),min(hi,float(r['end']))
                if end_i<=begin:continue
                state=html.unescape(str(r['state'] or '')).strip().casefold()
                if 'pause' in state:merge_intervals(d['pause'],aid,(begin,end_i))
                if _fallback_work_state(state,r['kind']):merge_intervals(d['work'],aid,(begin,end_i))
    return days


def view(qs):
    get=lambda key,default='':str(qs.get(key,[default])[0]).strip()
    settings=config()
    with connect() as c:
        from db_compat import begin_read_snapshot
        begin_read_snapshot(c)
        latest=c.execute('SELECT MAX(day) FROM call_coverage').fetchone()[0]
        first=get('date_from',latest or today());last=get('date_to',first)
        a,b=date.fromisoformat(first),date.fromisoformat(last)
        if b<a or (b-a).days>365:raise ValueError('Choisir une période de 1 à 366 jours.')
        start,end=get('time_from'),get('time_to')
        if not start and not end and get('work_hours','1')=='1':
            start,end=settings['work_start'],settings['work_end']
        if bool(start)!=bool(end):raise ValueError('Renseigner les deux heures.')
        if start:
            start=datetime.strptime(start,'%H:%M').strftime('%H:%M')
            end=datetime.strptime(end,'%H:%M').strftime('%H:%M')
            if start>=end:raise ValueError('Heure de fin après heure de début requise.')
        refs={r['day']:dict(r) for r in c.execute('''SELECT cc.day,cc.import_id,q.version FROM call_coverage cc
            LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id WHERE cc.day BETWEEN ? AND ?''',(first,last))}
        coverage=[];bounds=[];params=[]
        for i in range((b-a).days+1):
            day=(a+timedelta(days=i)).isoformat();ref=refs.get(day)
            ready=bool(ref and _version_ready(ref['version']))
            coverage.append(dict(day=day,available=ready))
            if ready:
                lo_ts,hi_ts=day_bounds(day,start,end) if start else day_bounds(day)
                bounds.append('(?,?,?,?)');params.extend((ref['import_id'],day,lo_ts,hi_ts))
        if bounds:
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(bounds)+') '
        else:
            empty_cols=('NULL::bigint,NULL::text,NULL::double precision,NULL::double precision'
                        if getattr(c,'schema',None) else 'NULL,NULL,NULL,NULL')
            prefix='WITH selected(import_id,day,lo,hi) AS (SELECT '+empty_cols+' WHERE FALSE) '
        source=' FROM selected s JOIN quality_inbound_facts f ON f.import_id=s.import_id AND f.day=s.day AND f.start>=s.lo AND f.start<s.hi'
        identity_scope=load_quality_file_scope()
        identity_campaigns=identity_campaign_catalog(identity_scope)
        catalog={}
        for row in c.execute(prefix+'SELECT DISTINCT f.campaign,f.campaign_name'+source,params):
            ident=resolve_campaign_identity(row['campaign'],row['campaign_name'],scope=identity_scope,catalog=identity_campaigns)
            item=catalog.setdefault(row['campaign'],dict(campaign=row['campaign'],campaign_name=ident['campaign_label'],names=[],identity_quality=ident['identity_quality']))
            item['names'].append(row['campaign_name'])
        groups=group_catalog(list(catalog.values()));group=get('group');service=get('service');campaign=get('campaign');agent=get('agent')
        services=sorted({str(g.get('service_name') or '').strip() for g in groups if str(g.get('service_name') or '').strip()},key=str.casefold)
        service_cf=service.casefold()
        if service and not any(x.casefold()==service_cf for x in services):raise ValueError('Service inconnu : actualisez les filtres.')
        selected=next((g for g in groups if g['id']==group),None) if group else None
        if group and selected is None:raise ValueError('Groupe inconnu : actualisez les filtres.')
        if selected is not None and service_cf and str(selected.get('service_name') or '').casefold()!=service_cf:
            raise ValueError('Ce sous-groupe n’appartient pas au service sélectionné.')
        selected_groups=([selected] if selected is not None else ([g for g in groups if service_cf and str(g.get('service_name') or '').casefold()==service_cf] if service_cf else []))
        where=' WHERE TRUE';filtered=list(params)
        if selected_groups:
            members=sorted({agent_key(x) for g in selected_groups for x in g.get('member_agent_ids',[]) if agent_key(x)})
            ids=sorted({str(x) for g in selected_groups for x in g.get('campaign_ids',[]) if str(x)})
            parts=[];gparams=[]
            if members:
                parts.append('f.agent IN ('+','.join('?' for _ in members)+')');gparams.extend(members)
            if ids:
                parts.append('('+agent_unassigned_sql('f')+' AND f.campaign IN ('+','.join('?' for _ in ids)+'))');gparams.extend(ids)
            if parts:
                where+=' AND ('+' OR '.join(parts)+')';filtered.extend(gparams)
            else:where+=' AND FALSE'
        if not selected_groups:
            choices=sorted(catalog.values(),key=lambda r:(r['campaign_name'].casefold(),r['campaign']))
        else:
            visible={}
            for row in c.execute(prefix+'SELECT DISTINCT f.campaign,f.campaign_name'+source+where,filtered):
                ident=resolve_campaign_identity(row['campaign'],row['campaign_name'],scope=identity_scope,catalog=identity_campaigns)
                visible[row['campaign']]=dict(campaign=row['campaign'],campaign_name=ident['campaign_label'],names=[row['campaign_name']],identity_quality=ident['identity_quality'])
            choices=sorted(visible.values(),key=lambda r:(r['campaign_name'].casefold(),r['campaign']))
        if campaign:
            if selected_groups and campaign not in {str(x.get('campaign')) for x in choices}:
                raise ValueError('Cette campagne ne contient aucun appel du périmètre sélectionné.')
            where+=' AND f.campaign=?';filtered.append(campaign)
        def key(raw):
            value=agent_key(raw);return '' if value in ('','0') else value
        c.create_function('distribution_agent',1,key,deterministic=True)
        directory=load_admin_directory()['users']
        agents=[dict(agent=r[0] or '__unassigned__',name=resolve_agent_name(r[0],admin_users=directory,configured_name=(identity_scope.get('agent_names') or {}).get(r[0],'')) if r[0] else 'Agent non renseigné') for r in c.execute(prefix+'SELECT DISTINCT distribution_agent(f.agent)'+source+where+' ORDER BY 1',filtered)]
        if agent:
            where+=' AND distribution_agent(f.agent)=?';filtered.append('' if agent=='__unassigned__' else key(agent))
        c.create_function('distribution_hour',1,lambda ts:int(display(ts)[11:13]),deterministic=True)
        assigned=agent_assigned_sql('f')
        counts={r['hour']:dict(r) for r in c.execute(prefix+f'''SELECT distribution_hour(f.start) AS hour,
            COUNT(*) AS received,
            SUM(CASE WHEN {assigned} THEN 1 ELSE 0 END) AS treated,
            SUM(f.answered) AS answered,
            SUM(f.abandoned) AS abandoned,
            SUM(f.closed) AS closed,
            SUM(f.before_queue) AS hangup_before_queue'''+source+where+' GROUP BY hour',filtered)}
        available=sum(r['available'] for r in coverage)
        minutes=lambda value:sum(int(v)*m for v,m in zip(value.split(':'),(60,1)))
        lo=minutes(start) if start else 0;hi=minutes(end) if end else 1440
        clock=lambda m:f'{m//60:02d}:{m%60:02d}' if m<1440 else '24:00'

        # RC29 Phase 4 workforce perimeter. ACTIVE population is configuration;
        # expected/worked/absent are asserted only when Stats.AGENT coverage exists.
        workforce_population=expected_agents(identity_scope,selected_groups,campaign,agent)
        population_reliable=bool(identity_scope.get('assignment_source_available')) and agent!='__unassigned__'
        workforce_days=_workforce_evidence(c,first,last,start,end,workforce_population) if population_reliable else {}
        workforce_available=sum(1 for x in workforce_days.values() if x.get('available')) if population_reliable else 0
        unit='agents' if len(coverage)==1 else 'agent-jours'
        workforce_hourly={}
        for h in range(lo//60,(hi+59)//60):
            bucket_lo=max(lo,h*60);bucket_hi=min(hi,(h+1)*60)
            agg={k:0 for k in ('active_agents','expected_agents','pause_agents','worked_agents','not_worked_agents')}
            agg['active_agents']=len(workforce_population)*len(coverage) if population_reliable else None
            if population_reliable:
                for day,d in workforce_days.items():
                    if not d['available']:continue
                    bs,be=_wall(day,bucket_lo),_wall(day,bucket_hi)
                    status=bucket_status(workforce_population,d['work'],d['pause'],bs,be)
                    agg['expected_agents']+=len(status['expected']);agg['pause_agents']+=len(status['pause'])
                    agg['worked_agents']+=len(status['worked']);agg['not_worked_agents']+=len(status['not_worked'])
            else:
                for k in ('active_agents','expected_agents','pause_agents','worked_agents','not_worked_agents'):agg[k]=None
            workforce_hourly[h]=agg

        metrics=('received','treated','answered','abandoned','closed','hangup_before_queue')
        hourly=[]
        for h in range(lo//60,(hi+59)//60):
            row=dict(hour=h,label=clock(max(lo,h*60))+'–'+clock(min(hi,(h+1)*60)),
                     **{k:counts.get(h,{}).get(k,0) if available else None for k in metrics},**workforce_hourly[h])
            den=(row['received'] or 0)-(row['closed'] or 0)-(row['hangup_before_queue'] or 0) if row['received'] is not None else 0
            row['qos']=100.0*(row['treated'] or 0)/den if den>0 else None
            hourly.append(row)
        total={k:sum(r[k] for r in hourly) if available else None for k in metrics}
        den=(total['received'] or 0)-(total['closed'] or 0)-(total['hangup_before_queue'] or 0) if total['received'] is not None else 0
        total['qos']=100.0*(total['treated'] or 0)/den if den>0 else None

        workforce_summary={k:None for k in ('active_agents','expected_agents','pause_agents','worked_agents','not_worked_agents')}
        if population_reliable:
            workforce_summary['active_agents']=len(workforce_population)
            workforce_summary['expected_agents']=len(workforce_population)*workforce_available
            paused_pairs=worked_pairs=0
            for day,d in workforce_days.items():
                if not d['available']:continue
                st=bucket_status(workforce_population,d['work'],d['pause'],d['lo'],d['hi'])
                paused_pairs+=len(st['pause']);worked_pairs+=len(st['worked'])
            workforce_summary['pause_agents']=paused_pairs
            workforce_summary['worked_agents']=worked_pairs
            workforce_summary['not_worked_agents']=workforce_summary['expected_agents']-worked_pairs

        detail_hour=get('detail_hour')
        workforce_detail=[]
        if detail_hour and population_reliable:
            try:h=int(detail_hour)
            except ValueError:h=-1
            if h>=0 and h<=23:
                bucket_lo=max(lo,h*60);bucket_hi=min(hi,(h+1)*60)
                names={aid:resolve_agent_name(aid,admin_users=directory,configured_name=(identity_scope.get('agent_names') or {}).get(aid,'')) for aid in workforce_population}
                for day,d in workforce_days.items():
                    if not d['available'] or bucket_hi<=bucket_lo:continue
                    st=bucket_status(workforce_population,d['work'],d['pause'],_wall(day,bucket_lo),_wall(day,bucket_hi))
                    workforce_detail.append({'day':day,'hour':h,'agents':[{'agent':aid,'name':names.get(aid) or aid,
                        'worked':aid in st['worked'],'pause':aid in st['pause'],'not_worked':aid in st['not_worked']} for aid in sorted(workforce_population)]})

        workforce_status=('reliable' if population_reliable and workforce_available==len(coverage)
                          else 'partial' if population_reliable and workforce_available>0 else 'not_calculable')
        return dict(source='Stats.INBOUND',timezone='Europe/Paris',date_from=first,date_to=last,time_from=start,time_to=end,
                    group=group,service=service,services=services,campaign=campaign,agent=agent,groups=groups,campaign_choices=choices,agent_choices=agents,
                    hourly=hourly,total=total,coverage=coverage,available_days=available,total_days=len(coverage),
                    workforce_summary=workforce_summary,workforce_status=workforce_status,workforce_available_days=workforce_available,
                    workforce_unit=unit,workforce_population_count=len(workforce_population) if population_reliable else None,
                    workforce_membership='Agents ACTIVE sur les files du périmètre sélectionné',
                    workforce_proof='Travail = preuve positive Stats.AGENT normalisée (work/inbound/manual/hold) ; offline/pause/coaching/unknown seuls ne prouvent pas le travail',
                    workforce_detail=workforce_detail)
