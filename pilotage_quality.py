"""Operational quality cockpit built from Nelyio's canonical Stats.INBOUND facts.

The module keeps observations, baselines and hypotheses separate. It never
compares services to one another: a service/group is compared only with its own
same-weekday history and the same time slot.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import median
import json

from app_db import db_connect, ensure_schema, now_text
from quality_metrics import _version_ready
from quality_rules import aggregate_sql, decorate, agent_assigned_sql, agent_unassigned_sql
from quality_scope import load_quality_file_scope
from quality_importer import agent_key
from supervision_db import connect, config
from nelyio_time import day_bounds, display

ACTION_STATUSES=('À faire','En cours','Appliqué','À vérifier','Clos')


def _get(qs,key,default=''):
    return str(qs.get(key,[default])[0]).strip()


def _catalog():
    groups=[]
    for raw in load_quality_file_scope().get('groups',[]):
        if str(raw.get('id'))=='unassigned':
            continue
        g=dict(raw)
        g['id']=str(g.get('id'))
        g['service_name']=str(g.get('service_name') or '').strip()
        groups.append(g)
    services=sorted({g['service_name'] for g in groups if g['service_name']},key=str.casefold)
    return groups,services


def _resolve_scope(groups,service='',group=''):
    service_cf=service.casefold().strip();gid=str(group or '').strip()
    if not service_cf and not gid:
        return [],[],[]
    selected=[]
    for g in groups:
        if gid and str(g['id'])!=gid:continue
        if service_cf and str(g.get('service_name') or '').casefold()!=service_cf:continue
        selected.append(g)
    if (gid or service_cf) and not selected:
        raise ValueError('Service ou sous-groupe inconnu : actualisez les filtres.')
    members=sorted({agent_key(x) for g in selected for x in g.get('member_agent_ids',[]) if agent_key(x)})
    campaigns=sorted({str(x) for g in selected for x in g.get('campaign_ids',[]) if str(x)})
    return selected,members,campaigns


def _scope_sql(members,campaigns,filtered):
    if not members and not campaigns:
        return 'FALSE'
    parts=[]
    if members:
        parts.append('f.agent IN ('+','.join('?' for _ in members)+')');filtered.extend(members)
    if campaigns:
        parts.append('('+agent_unassigned_sql('f')+' AND f.campaign IN ('+','.join('?' for _ in campaigns)+'))');filtered.extend(campaigns)
    return '('+' OR '.join(parts)+')'


def _day_ref(c,day):
    row=c.execute('''SELECT cc.import_id,q.version FROM call_coverage cc
                     LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id WHERE cc.day=?''',(day,)).fetchone()
    return row if row and _version_ready(row['version']) else None


def _bounds(day,t1,t2):
    return day_bounds(day,t1,t2) if t1 else day_bounds(day)


def _percentile(values,p=0.90):
    values=sorted(float(x) for x in values if x is not None and float(x)>=0)
    if not values:return None
    if len(values)==1:return values[0]
    pos=(len(values)-1)*p;lo=int(pos);hi=min(lo+1,len(values)-1);fraction=pos-lo
    return values[lo]*(1-fraction)+values[hi]*fraction


def _metrics_for_day(c,day,t1,t2,members,campaigns,threshold=60,governance=None):
    ref=_day_ref(c,day)
    if not ref:return None
    if governance:
        aggregate,_visible=_aggregate_fact_rows(_fact_rows_for_day(c,day,t1,t2,members,campaigns),threshold,governance)
        received=int(aggregate.get('received') or 0);abandoned=int(aggregate.get('abandoned') or 0)
        return dict(day=day,received=received,treated=int(aggregate.get('treated_agent') or 0),abandoned=abandoned,
                    abandonment_rate=(100*abandoned/received if received else None),qos=aggregate.get('qos_percent'),
                    asa=aggregate.get('asa_seconds'),p90_wait=aggregate.get('p90_wait'),agents_treating=int(aggregate.get('agents_treating') or 0),
                    invalid_durations=int(aggregate.get('invalid_durations') or 0),coherence_ok=bool(aggregate.get('coherence_ok')),
                    qos_numerator=int(aggregate.get('qos_numerator') or 0),qos_denominator=int(aggregate.get('qos_denominator') or 0),
                    governance_excluded=int(aggregate.get('governance_excluded') or 0),governance_reasons=aggregate.get('governance_reasons') or [])
    lo,hi=_bounds(day,t1,t2)
    params=[ref['import_id'],day,lo,hi]
    where='f.import_id=? AND f.day=? AND f.start>=? AND f.start<?'
    if members or campaigns:
        scoped=[];where+=' AND '+_scope_sql(members,campaigns,scoped);params.extend(scoped)
    metric=aggregate_sql('f','?')
    row=c.execute('SELECT '+metric+' FROM quality_inbound_facts f WHERE '+where,[threshold,*params]).fetchone()
    out=decorate(row,threshold,None)
    assigned=agent_assigned_sql('f')
    agents=int(c.execute('SELECT COUNT(DISTINCT f.agent) FROM quality_inbound_facts f WHERE '+where+' AND '+assigned,params).fetchone()[0] or 0)
    waits=[r[0] for r in c.execute('SELECT f.wait FROM quality_inbound_facts f WHERE '+where+' AND '+assigned+' AND f.wait>=0',params)]
    received=int(out.get('received') or 0);abandoned=int(out.get('abandoned') or 0)
    return dict(day=day,received=received,treated=int(out.get('treated_agent') or 0),abandoned=abandoned,
                abandonment_rate=(100*abandoned/received if received else None),qos=out.get('qos_percent'),
                asa=out.get('asa_seconds'),p90_wait=_percentile(waits),agents_treating=agents,
                invalid_durations=int(out.get('invalid_durations') or 0),coherence_ok=bool(out.get('coherence_ok')),
                qos_numerator=int(out.get('qos_numerator') or 0),qos_denominator=int(out.get('qos_denominator') or 0),
                governance_excluded=0,governance_reasons=[])


def _previous_same_weekdays(c,target,limit=4):
    d=date.fromisoformat(target);weekday=d.weekday()
    rows=c.execute('''SELECT cc.day,q.version FROM call_coverage cc
                      LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id
                      WHERE cc.day<? ORDER BY cc.day DESC LIMIT 90''',(target,)).fetchall()
    return [str(r['day']) for r in rows if _version_ready(r['version']) and date.fromisoformat(str(r['day'])).weekday()==weekday][:limit]


def _median_baseline(items):
    keys=('received','treated','abandoned','abandonment_rate','qos','asa','p90_wait','agents_treating')
    return {k:(median([x[k] for x in items if x.get(k) is not None]) if any(x.get(k) is not None for x in items) else None) for k in keys}


def _queue_names():
    """Return configured queue labels without using campaigns as queue substitutes."""
    out={}
    for q in load_quality_file_scope().get('queues',[]) or []:
        key=str(q.get('line_id') or '').strip()
        if not key:
            continue
        out[key]=str(q.get('display_name') or q.get('line_name') or f'File {key}').strip()
    return out


def _governance_context(groups,days):
    """Load governance once per Pilotage request and prebuild exact scope maps."""
    days=sorted({str(x) for x in days if x})
    if not days:return None
    from policy_engine import load_policies
    from declaration_engine import load_declarations
    policies=load_policies()
    declarations=load_declarations(days[0],days[-1],include_cancelled=False)
    if not policies and not declarations:return None
    from governance_engine import DetailsGovernanceCalendar
    agent_groups={};campaign_groups={};line_groups={};group_names={}
    for g in groups:
        gid=str(g.get('id') or '').strip()
        if not gid:continue
        group_names[gid]=str(g.get('name') or gid)
        for aid in g.get('member_agent_ids',[]) or []:
            key=agent_key(aid)
            if key:agent_groups.setdefault(key,set()).add(gid)
        for campaign in g.get('campaign_ids',[]) or []:
            key=str(campaign or '').strip()
            if key:campaign_groups.setdefault(key,set()).add(gid)
        for line in g.get('line_ids',[]) or []:
            key=str(line or '').strip()
            if key:line_groups.setdefault(key,set()).add(gid)
    return dict(policies=policies,declarations=declarations,
                calendar=DetailsGovernanceCalendar(policies,declarations,max_days=max(64,len(days)+4)),
                agent_groups=agent_groups,campaign_groups=campaign_groups,line_groups=line_groups,group_names=group_names)


def _governance_decision(ctx,start,seconds,agent='',campaign='',line=''):
    if not ctx:return None
    event=dict(start=float(start),seconds=max(1,int(float(seconds or 1))),agent=agent_key(agent))
    if not ctx['calendar'].may_apply(event):return None
    line=str(line or '').strip();campaign=str(campaign or '').strip();aid=agent_key(agent)
    gids=set(ctx['line_groups'].get(line,set())) if line else set()
    if not gids and aid:gids.update(ctx['agent_groups'].get(aid,set()))
    if not gids and campaign:gids.update(ctx['campaign_groups'].get(campaign,set()))
    from governance_engine import apply_event_governance
    decisions=[]
    for gid in sorted(gids) or ['']:
        probe=dict(event)
        if gid:
            probe['group_id']=gid;probe['group_name']=ctx['group_names'].get(gid,gid)
        row=apply_event_governance(probe,'analytics',ctx['policies'],ctx['declarations'])
        if row.get('governance_exclude_statistics'):
            decisions.append(str(row.get('governance_reason') or 'Période exclue'))
    if not decisions:return None
    return ' · '.join(dict.fromkeys(x for x in decisions if x))


def _fact_rows_for_day(c,day,t1,t2,members,campaigns):
    ref=_day_ref(c,day)
    if not ref:return []
    lo,hi=_bounds(day,t1,t2);params=[ref['import_id'],day,lo,hi]
    where='f.import_id=? AND f.day=? AND f.start>=? AND f.start<?'
    if members or campaigns:
        scoped=[];where+=' AND '+_scope_sql(members,campaigns,scoped);params.extend(scoped)
    return [dict(r) for r in c.execute('''SELECT f.start,f.agent,f.campaign,f.received,f.answered,f.abandoned,f.closed,f.overflow,
             f.rerouted,f.before_queue,f.transferred,f.wait,f.invalid_duration,f.lost,f.call_duration,f.payload
             FROM quality_inbound_facts f WHERE '''+where,params)]


def _aggregate_fact_rows(rows,threshold=60,governance=None):
    acc=dict(received=0,is_call_count=0,treated_agent=0,answered=0,completed=0,transferred=0,rerouted_agent=0,
             rerouted_no_agent=0,abandoned=0,closed=0,overflow=0,hangup_before_queue=0,ignored=0,double_classified=0,
             lost_with_agent_known=0,lost_source_missing=0,invalid_durations=0,wait_sum=0.0,wait_count=0,within_threshold=0)
    waits=[];agents=set();excluded=0;reasons={}
    visible=[]
    for r in rows:
        reason=_governance_decision(governance,r['start'],r.get('call_duration') or 1,r.get('agent'),r.get('campaign')) if governance else None
        if reason:
            excluded+=1;reasons[reason]=reasons.get(reason,0)+1;continue
        visible.append(r)
        aid=agent_key(r.get('agent'));assigned=aid not in ('','0');unassigned=not assigned
        acc['received']+=1;acc['is_call_count']+=int(r.get('received') or 0);acc['treated_agent']+=int(assigned)
        acc['answered']+=int(r.get('answered') or 0);acc['abandoned']+=int(r.get('abandoned') or 0)
        acc['closed']+=int(r.get('closed') or 0);acc['overflow']+=int(r.get('overflow') or 0);acc['hangup_before_queue']+=int(r.get('before_queue') or 0)
        acc['transferred']+=int(assigned and int(r.get('transferred') or 0)==1)
        acc['completed']+=int(assigned and int(r.get('transferred') or 0)==0 and int(r.get('rerouted') or 0)==0)
        acc['rerouted_agent']+=int(assigned and int(r.get('rerouted') or 0)==1)
        acc['rerouted_no_agent']+=int(unassigned and int(r.get('rerouted') or 0)==1)
        hits=(int(r.get('closed') or 0)+int(r.get('overflow') or 0)+int(unassigned and int(r.get('rerouted') or 0)==1)+
              int(r.get('before_queue') or 0)+int(r.get('abandoned') or 0)+int(assigned))
        acc['ignored']+=int(hits==0);acc['double_classified']+=int(hits>1)
        if assigned:
            if r.get('lost') is None:acc['lost_source_missing']+=1
            else:acc['lost_with_agent_known']+=int(r.get('lost') or 0)
            agents.add(aid)
            try:wait=float(r.get('wait'))
            except (TypeError,ValueError):wait=-1
            if wait>=0:
                waits.append(wait);acc['wait_sum']+=wait;acc['wait_count']+=1;acc['within_threshold']+=int(wait<=threshold)
        acc['invalid_durations']+=int(r.get('invalid_duration') or 0)
    decorated=decorate(acc,threshold,None)
    decorated.update(p90_wait=_percentile(waits),agents_treating=len(agents),governance_excluded=excluded,
                     governance_reasons=[dict(reason=k,count=v) for k,v in sorted(reasons.items(),key=lambda x:(-x[1],x[0]))])
    return decorated,visible


def _call_day_ref(c,day):
    row=c.execute('SELECT import_id FROM call_coverage WHERE day=?',(day,)).fetchone()
    return int(row['import_id']) if row else None


def _file_metrics_for_day(c,day,t1,t2,scope_lines=None,governance=None):
    """Operational queue metrics sourced only from ODCalls.FirstQueue.

    Stats.INBOUND remains authoritative for the global Quality/QoS KPIs.  This
    helper intentionally uses the certified call -> FirstQueue relation only
    for drill-down and investigation by queue.
    """
    import_id=_call_day_ref(c,day)
    if import_id is None:
        return {}
    if scope_lines is not None and not scope_lines:
        return {}
    lo,hi=_bounds(day,t1,t2)
    params=[import_id,lo,hi]
    where="""p.import_id=? AND p.start>=? AND p.start<? AND COALESCE(p.call_type,'')='1'
             AND COALESCE(TRIM(d.first_queue),'') NOT IN ('','0','-1')"""
    if scope_lines is not None:
        lines=sorted({str(x).strip() for x in scope_lines if str(x).strip()})
        if not lines:
            return {}
        where+=' AND d.first_queue IN ('+','.join('?' for _ in lines)+')'
        params.extend(lines)
    if governance:
        acc={};waits={}
        for r in c.execute('''SELECT p.start,p.first_agent,p.abandon,p.duration,p.campaign,
                                      d.call_duration,d.wait_initial,d.first_queue
                               FROM phone_calls p
                               JOIN phone_call_details d ON d.import_id=p.import_id AND d.call_id=p.call_id
                               WHERE '''+where,params):
            fid=str(r['first_queue'] or '').strip();aid=agent_key(r['first_agent']);assigned=aid not in ('','0')
            if _governance_decision(governance,r['start'],r['call_duration'] or r['duration'] or 1,aid,r['campaign'],fid):
                continue
            x=acc.setdefault(fid,dict(file_id=fid,received=0,treated=0,abandoned=0,wait_sum=0.0,wait_count=0,agents=set()))
            x['received']+=1;x['treated']+=int(assigned);x['abandoned']+=int(bool(r['abandon']) and not assigned)
            if assigned:x['agents'].add(aid)
            try:wait=float(r['wait_initial'])
            except (TypeError,ValueError):wait=-1
            if wait>=0:
                x['wait_sum']+=wait;x['wait_count']+=1;waits.setdefault(fid,[]).append(wait)
        out={}
        for fid,x in acc.items():
            received=x['received'];abandoned=x['abandoned']
            out[fid]=dict(file_id=fid,received=received,treated=x['treated'],abandoned=abandoned,
                          abandonment_rate=(100*abandoned/received if received else None),
                          wait_average=(x['wait_sum']/x['wait_count'] if x['wait_count'] else None),
                          p90_wait=_percentile(waits.get(fid,[])),agents_treating=len(x['agents']))
        return out
    assigned="UPPER(TRIM(COALESCE(p.first_agent,''))) NOT IN ('','0','S0')"
    unassigned="UPPER(TRIM(COALESCE(p.first_agent,''))) IN ('','0','S0')"
    rows=c.execute(f'''SELECT d.first_queue AS file_id,
                              COUNT(*) AS received,
                              SUM(CASE WHEN {assigned} THEN 1 ELSE 0 END) AS treated,
                              SUM(CASE WHEN COALESCE(p.abandon,0)<>0 AND {unassigned} THEN 1 ELSE 0 END) AS abandoned,
                              AVG(CASE WHEN d.wait_initial>=0 THEN d.wait_initial END) AS wait_average,
                              COUNT(DISTINCT CASE WHEN {assigned} THEN TRIM(p.first_agent) END) AS agents_treating
                       FROM phone_calls p
                       JOIN phone_call_details d ON d.import_id=p.import_id AND d.call_id=p.call_id
                       WHERE {where}
                       GROUP BY d.first_queue''',params).fetchall()
    metrics={}
    for r in rows:
        fid=str(r['file_id'] or '').strip();received=int(r['received'] or 0);abandoned=int(r['abandoned'] or 0)
        metrics[fid]=dict(file_id=fid,received=received,treated=int(r['treated'] or 0),abandoned=abandoned,
                          abandonment_rate=(100*abandoned/received if received else None),
                          wait_average=(float(r['wait_average']) if r['wait_average'] is not None else None),
                          p90_wait=None,agents_treating=int(r['agents_treating'] or 0))
    waits={}
    for r in c.execute(f'''SELECT d.first_queue AS file_id,d.wait_initial AS wait_initial
                            FROM phone_calls p
                            JOIN phone_call_details d ON d.import_id=p.import_id AND d.call_id=p.call_id
                            WHERE {where} AND d.wait_initial>=0''',params):
        waits.setdefault(str(r['file_id'] or '').strip(),[]).append(float(r['wait_initial']))
    for fid,values in waits.items():
        if fid in metrics:
            metrics[fid]['p90_wait']=_percentile(values)
    return metrics


def _file_baseline(items):
    keys=('received','treated','abandoned','abandonment_rate','wait_average','p90_wait','agents_treating')
    return {k:(median([x[k] for x in items if x.get(k) is not None]) if any(x.get(k) is not None for x in items) else None) for k in keys}


def _files_to_investigate(current,historical,queue_names,min_volume):
    rows=[]
    impact_floor=max(5,int(round(min_volume*0.20)))
    for fid,cur in current.items():
        if int(cur.get('received') or 0)<min_volume:
            continue
        hist=[m[fid] for m in historical if fid in m]
        base=_file_baseline(hist) if len(hist)>=2 else None
        factors=[]
        if int(cur.get('agents_treating') or 0)==0:
            factors.append('Appels reçus sans agent ayant traité')
        if int(cur.get('abandoned') or 0)>=impact_floor:
            factors.append(f"{int(cur['abandoned'])} abandons sur {int(cur['received'])} appels")
        if base:
            ar=cur.get('abandonment_rate');bar=base.get('abandonment_rate')
            if ar is not None and bar is not None and ar-bar>=5:
                factors.append(f'Taux d’abandon +{ar-bar:.1f} point(s) vs historique comparable')
            p90=cur.get('p90_wait');bp90=base.get('p90_wait')
            if p90 is not None and bp90 is not None and p90-bp90>=30 and (bp90<=0 or p90>=bp90*1.25):
                factors.append(f'P90 attente +{p90-bp90:.0f} s vs historique comparable')
            agents=cur.get('agents_treating');bagents=base.get('agents_treating')
            if agents is not None and bagents is not None and bagents-agents>=2:
                factors.append(f'{agents} agent(s) ayant traité vs médiane {bagents:g}')
            received=cur.get('received');breceived=base.get('received')
            if breceived and received>=breceived*1.5 and received-breceived>=max(10,min_volume/2):
                factors.append(f'Volume +{received-breceived:.0f} appel(s) vs historique comparable')
        if not factors:
            continue
        row=dict(cur)
        row.update(file=queue_names.get(fid) or f'File {fid}',baseline=base,
                   baseline_status=('ready' if base else 'insufficient'),baseline_days=len(hist),factors=factors)
        # Transparent impact ordering: absence of handler first, then comparable
        # anomalies, then absolute abandoned volume and total volume.  This is
        # not a hidden performance score and is never exposed as one.
        row['_sort']=(1 if int(cur.get('agents_treating') or 0)==0 else 0,
                      1 if base and any('historique comparable' in x for x in factors) else 0,
                      int(cur.get('abandoned') or 0),int(cur.get('received') or 0),float(cur.get('p90_wait') or 0))
        rows.append(row)
    rows.sort(key=lambda r:r['_sort'],reverse=True)
    for r in rows:r.pop('_sort',None)
    return rows[:10]


def _signal(code,title,current,baseline,detail,hypotheses,severity='warning'):
    return dict(code=code,title=title,severity=severity,current=current,baseline=baseline,detail=detail,
                certainty='observation',hypotheses=list(hypotheses))


def _signals(current,base,min_volume):
    if not current or not base or int(current.get('received') or 0)<min_volume:return [],[]
    signals=[];improvements=[]
    def diff(a,b):return None if a is None or b is None else float(a)-float(b)
    ar=diff(current.get('abandonment_rate'),base.get('abandonment_rate'))
    if ar is not None:
        if ar>=5:signals.append(_signal('abandon_high','Abandon supérieur au niveau habituel',current['abandonment_rate'],base['abandonment_rate'],f'+{ar:.1f} point(s)',('planning','couverture','affectation','routage'),'danger' if ar>=10 else 'warning'))
        elif ar<=-5:improvements.append(dict(code='abandon_better',title='Abandon inférieur au niveau habituel',current=current['abandonment_rate'],baseline=base['abandonment_rate'],detail=f'{ar:.1f} point(s)'))
    qd=diff(current.get('qos'),base.get('qos'))
    if qd is not None:
        if qd<=-5:signals.append(_signal('qos_low','QoS inférieure au niveau habituel',current['qos'],base['qos'],f'{qd:.1f} point(s)',('couverture','routage','qualification'),'danger' if qd<=-10 else 'warning'))
        elif qd>=5:improvements.append(dict(code='qos_better',title='QoS supérieure au niveau habituel',current=current['qos'],baseline=base['qos'],detail=f'+{qd:.1f} point(s)'))
    for key,label,min_abs in [('p90_wait','P90 d’attente supérieur au niveau habituel',30),('asa','Attente moyenne supérieure au niveau habituel',15)]:
        cur=current.get(key);ref=base.get(key)
        if cur is not None and ref is not None and cur-ref>=min_abs and (ref<=0 or cur>=ref*1.25):
            signals.append(_signal(key+'_high',label,cur,ref,f'+{cur-ref:.0f} s',('charge','couverture','routage'),'warning'))
    cur_agents=current.get('agents_treating');ref_agents=base.get('agents_treating')
    if cur_agents is not None and ref_agents is not None and ref_agents-cur_agents>=2:
        signals.append(_signal('agents_treating_low','Moins d’agents ont traité des appels que d’habitude',cur_agents,ref_agents,f'{cur_agents} vs médiane {ref_agents:g}',('planning','affectation','couverture'),'warning'))
    rank={'danger':2,'warning':1}
    signals.sort(key=lambda x:(-rank.get(x['severity'],0),x['code']))
    return signals[:5],improvements[:3]


def _hourly(c,day,t1,t2,members,campaigns,granularity=60,governance=None):
    ref=_day_ref(c,day)
    if not ref:return []
    granularity=int(granularity)
    if granularity not in (30,60):raise ValueError('Granularité invalide.')
    lo,hi=_bounds(day,t1,t2);params=[ref['import_id'],day,lo,hi]
    where='f.import_id=? AND f.day=? AND f.start>=? AND f.start<?'
    if members or campaigns:
        scoped=[];where+=' AND '+_scope_sql(members,campaigns,scoped);params.extend(scoped)
    rows=[dict(r) for r in c.execute('SELECT f.start,f.agent,f.campaign,f.abandoned,f.wait,f.call_duration FROM quality_inbound_facts f WHERE '+where,params)]
    buckets={}
    for r in rows:
        if governance and _governance_decision(governance,r['start'],r.get('call_duration') or 1,r.get('agent'),r.get('campaign')):
            continue
        stamp=display(r['start']);hour=int(stamp[11:13]);minute=int(stamp[14:16]);slot_minute=0 if granularity==60 or minute<30 else 30
        key=(hour,slot_minute);b=buckets.setdefault(key,dict(hour=hour,minute=slot_minute,received=0,treated=0,abandoned=0,waits=[],agents=set()))
        b['received']+=1;b['abandoned']+=int(r.get('abandoned') or 0)
        aid=agent_key(r.get('agent'))
        if aid not in ('','0'):
            b['treated']+=1;b['agents'].add(aid)
            if r.get('wait') is not None and float(r['wait'])>=0:b['waits'].append(float(r['wait']))
    out=[]
    for key in sorted(buckets):
        b=buckets[key];received=b['received'];agents=len(b['agents']);start_minutes=b['hour']*60+b['minute'];end_minutes=start_minutes+granularity
        label=f'{start_minutes//60:02d}:{start_minutes%60:02d}–{end_minutes//60:02d}:{end_minutes%60:02d}'
        out.append(dict(hour=b['hour'],minute=b['minute'],label=label,received=received,treated=b['treated'],abandoned=b['abandoned'],
                        abandonment_rate=(100*b['abandoned']/received if received else None),
                        wait_average=(sum(b['waits'])/len(b['waits']) if b['waits'] else None),wait_median=_percentile(b['waits'],.5),p90_wait=_percentile(b['waits']),
                        agents_treating=agents,calls_per_agent=(received/agents if agents else None),
                        treated_per_agent=(b['treated']/agents if agents else None)))
    return out


def _actions_to_verify(limit=5):
    ensure_schema()
    with db_connect() as c:
        return [dict(r) for r in c.execute("SELECT id,title,service_name,group_id,file_id,application_date,status,comment FROM quality_actions WHERE status='À vérifier' ORDER BY COALESCE(application_date,created_at) DESC,id DESC LIMIT ?",(int(limit),))]


def _group_reliability(groups):
    configured=sum(int(g.get('file_count') or 0) for g in groups)
    matched=sum(int(g.get('matched_file_count') or 0) for g in groups)
    service_total=len(groups)
    service_assigned=sum(1 for g in groups if str(g.get('service_name') or '').strip())
    return dict(configured_files=configured,matched_files=matched,
                group_reconstruction_percent=(100*matched/configured if configured else None),
                service_groups_total=service_total,service_groups_assigned=service_assigned,
                service_assignment_percent=(100*service_assigned/service_total if service_total else None))


def _qualification_reliability(c,day,t1,t2,members,campaigns,governance=None):
    ref=_day_ref(c,day)
    if not ref:return dict(total=0,qualified=0,not_qualified=0,missing=0,qualification_percent=None,not_qualified_percent=None,missing_percent=None)
    if governance:
        rows=_fact_rows_for_day(c,day,t1,t2,members,campaigns)
        values=[]
        for r in rows:
            if _governance_decision(governance,r['start'],r.get('call_duration') or 1,r.get('agent'),r.get('campaign')):
                continue
            try:payload=json.loads(r.get('payload') or '{}')
            except Exception:payload={}
            values.append(str(payload.get('StatusCodeText') or '').strip().casefold())
        total=len(values);notq=sum(x=='not qualified' for x in values);qualified=sum(bool(x) and x!='not qualified' for x in values);missing=sum(not x for x in values)
        pct=lambda n:(100*n/total if total else None)
        return dict(total=total,qualified=qualified,not_qualified=notq,missing=missing,
                    qualification_percent=pct(qualified),not_qualified_percent=pct(notq),missing_percent=pct(missing))
    lo,hi=_bounds(day,t1,t2);params=[ref['import_id'],day,lo,hi]
    where='f.import_id=? AND f.day=? AND f.start>=? AND f.start<?'
    if members or campaigns:
        scoped=[];where+=' AND '+_scope_sql(members,campaigns,scoped);params.extend(scoped)
    status="LOWER(TRIM(COALESCE(json_extract(f.payload,'$.StatusCodeText'),'')))"
    r=c.execute(f'''SELECT COUNT(*) AS total,
                           SUM(CASE WHEN {status}='not qualified' THEN 1 ELSE 0 END) AS not_qualified,
                           SUM(CASE WHEN {status}<>'' AND {status}<>'not qualified' THEN 1 ELSE 0 END) AS qualified,
                           SUM(CASE WHEN {status}='' THEN 1 ELSE 0 END) AS missing
                    FROM quality_inbound_facts f WHERE {where}''',params).fetchone()
    total=int(r['total'] or 0);qualified=int(r['qualified'] or 0);notq=int(r['not_qualified'] or 0);missing=int(r['missing'] or 0)
    pct=lambda n:(100*n/total if total else None)
    return dict(total=total,qualified=qualified,not_qualified=notq,missing=missing,
                qualification_percent=pct(qualified),not_qualified_percent=pct(notq),missing_percent=pct(missing))


def view(qs):
    cfg=config();groups,services=_catalog();service=_get(qs,'service');group=_get(qs,'group')
    selected,members,campaigns=_resolve_scope(groups,service,group)
    min_volume=int(_get(qs,'min_volume','30') or 30);granularity=int(_get(qs,'granularity','60') or 60)
    if not 1<=min_volume<=10000:raise ValueError('Volume minimum invalide.')
    if granularity not in (30,60):raise ValueError('Granularité invalide.')
    with connect() as c:
        latest=c.execute('SELECT MAX(day) FROM call_coverage').fetchone()[0]
        target=_get(qs,'day',latest or date.today().isoformat());date.fromisoformat(target)
        t1=_get(qs,'time_from',cfg['work_start']);t2=_get(qs,'time_to',cfg['work_end'])
        if t1>=t2:raise ValueError('La fin de plage doit être après le début.')
        compare_days=_previous_same_weekdays(c,target,4)
        governance=_governance_context(groups,[target,*compare_days])
        current=_metrics_for_day(c,target,t1,t2,members,campaigns,governance=governance)
        comparable=[x for x in (_metrics_for_day(c,d,t1,t2,members,campaigns,governance=governance) for d in compare_days) if x]
        baseline=_median_baseline(comparable) if len(comparable)>=2 else None
        signals,improvements=_signals(current,baseline,min_volume)
        signal_scope_mode='selected_scope'
        # The global cockpit keeps global KPI cards, but alert generation must
        # not blend distinct parent services into one baseline.  When services
        # are configured, each service is compared only with its own history.
        if not service and not group and services:
            scoped_signals=[];scoped_improvements=[]
            for service_name in services:
                _sg,_members,_campaigns=_resolve_scope(groups,service_name,'')
                service_current=_metrics_for_day(c,target,t1,t2,_members,_campaigns,governance=governance)
                service_comparable=[x for x in (_metrics_for_day(c,d,t1,t2,_members,_campaigns,governance=governance) for d in compare_days) if x]
                service_baseline=_median_baseline(service_comparable) if len(service_comparable)>=2 else None
                ss,ii=_signals(service_current,service_baseline,min_volume)
                scoped_signals.extend(dict(x,service_name=service_name,scope_label=service_name) for x in ss)
                scoped_improvements.extend(dict(x,service_name=service_name,scope_label=service_name) for x in ii)
            rank={'danger':2,'warning':1}
            scoped_signals.sort(key=lambda x:(-rank.get(x.get('severity'),0),str(x.get('service_name') or '').casefold(),x.get('code','')))
            scoped_improvements.sort(key=lambda x:(str(x.get('service_name') or '').casefold(),x.get('code','')))
            signals=scoped_signals[:5];improvements=scoped_improvements[:3]
            signal_scope_mode='per_service'
        hourly=_hourly(c,target,t1,t2,members,campaigns,granularity,governance) if current else []
        filtered_scope=bool(service or group)
        scope_lines=(sorted({str(lid) for g in selected for lid in g.get('line_ids',[])}) if filtered_scope else None)
        current_files=_file_metrics_for_day(c,target,t1,t2,scope_lines,governance) if current else {}
        historical_files=[_file_metrics_for_day(c,d,t1,t2,scope_lines,governance) for d in compare_days]
        file_rows=_files_to_investigate(current_files,historical_files,_queue_names(),min_volume)
        qualification=_qualification_reliability(c,target,t1,t2,members,campaigns,governance) if current else _qualification_reliability(c,target,t1,t2,[],[],governance)
    group_quality=_group_reliability(groups)
    reliability=dict(status=('Données insuffisantes' if not current or not baseline else ('À surveiller' if current.get('invalid_durations') or not current.get('coherence_ok') else 'Fiable')),
                     invalid_durations=(current or {}).get('invalid_durations'),coherence_ok=(current or {}).get('coherence_ok'),
                     qualification=qualification,
                     governance=dict(active=bool(governance),policies=(len(governance['policies']) if governance else 0),
                                     declarations=(len(governance['declarations']) if governance else 0),
                                     excluded_calls=int((current or {}).get('governance_excluded') or 0),
                                     reasons=(current or {}).get('governance_reasons') or []),**group_quality)
    return dict(day=target,time_from=t1,time_to=t2,service=service,group=group,min_volume=min_volume,granularity=granularity,
                services=services,groups=groups,selected_groups=[g['id'] for g in selected],current=current,
                baseline=baseline,baseline_days=[x['day'] for x in comparable],baseline_status=('ready' if baseline else 'insufficient'),
                signals=signals,improvements=improvements,signal_scope_mode=signal_scope_mode,hourly=hourly,actions_to_verify=_actions_to_verify(),
                files_to_investigate=dict(status=('ready' if current_files else 'insufficient'),rows=file_rows,
                    source='ODCalls.FirstQueue',baseline_days=compare_days,
                    reason=('Aucune relation appel → FirstQueue exploitable sur ce périmètre.' if not current_files else ''),
                    note='Drill-down file basé uniquement sur ODCalls.FirstQueue. La QoS globale reste calculée depuis Stats.INBOUND.'),
                reliability=reliability,
                limitations=['Agents ayant traité ≠ agents connectés : Nelyio ne présente pas cette valeur comme une couverture temps réel.',
                             'Les files à investiguer utilisent ODCalls.FirstQueue pour le drill-down ; elles ne remplacent pas les KPI QoS officiels issus de Stats.INBOUND.',
                             'Les hypothèses affichées sont des vérifications proposées, jamais des causes confirmées.'])


def list_actions():
    ensure_schema()
    with db_connect() as c:
        rows=[dict(r) for r in c.execute('SELECT * FROM quality_actions ORDER BY COALESCE(application_date,created_at) DESC,id DESC')]
    for r in rows:
        try:r['context']=json.loads(r.pop('context_json') or '{}')
        except Exception:r['context']={}
    return {'statuses':list(ACTION_STATUSES),'rows':rows}


def save_action(payload,actor):
    ensure_schema()
    if not isinstance(payload,dict):raise ValueError('Action invalide.')
    title=str(payload.get('title') or '').strip();comment=str(payload.get('comment') or '').strip();status=str(payload.get('status') or 'À faire').strip()
    if not title or len(title)>160:raise ValueError('Titre requis (160 caractères maximum).')
    if len(comment)>4000:raise ValueError('Commentaire trop long.')
    if status not in ACTION_STATUSES:raise ValueError('Statut invalide.')
    app_date=str(payload.get('application_date') or '').strip()
    if app_date:date.fromisoformat(app_date)
    service=str(payload.get('service_name') or '').strip()[:60];group=str(payload.get('group_id') or '').strip();file_id=str(payload.get('file_id') or '').strip()
    anomaly_key=str(payload.get('anomaly_key') or '').strip()[:120];anomaly_label=str(payload.get('anomaly_label') or '').strip()[:240]
    context=payload.get('context') if isinstance(payload.get('context'),dict) else {}
    aid=int(payload.get('id') or 0)
    with db_connect() as c:
        if aid:
            if not c.execute('SELECT 1 FROM quality_actions WHERE id=?',(aid,)).fetchone():raise ValueError('Action introuvable.')
            c.execute('''UPDATE quality_actions SET title=?,service_name=?,group_id=?,file_id=?,anomaly_key=?,anomaly_label=?,comment=?,application_date=?,status=?,context_json=?,updated_at=?,updated_by=? WHERE id=?''',
                      (title,service,group,file_id,anomaly_key,anomaly_label,comment,app_date or None,status,json.dumps(context,ensure_ascii=False),now_text(),actor,aid))
        else:
            cur=c.execute('''INSERT INTO quality_actions(title,author,service_name,group_id,file_id,anomaly_key,anomaly_label,comment,application_date,status,context_json,updated_by)
                             VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(title,actor,service,group,file_id,anomaly_key,anomaly_label,comment,app_date or None,status,json.dumps(context,ensure_ascii=False),actor));aid=cur.lastrowid
    return {'ok':True,'id':aid}


def compare_action(qs):
    ensure_schema()
    aid=int(_get(qs,'id','0') or 0)
    with db_connect() as a:
        action=a.execute('SELECT * FROM quality_actions WHERE id=?',(aid,)).fetchone()
        if not action:raise ValueError('Action introuvable.')
        action=dict(action)
    applied=str(action.get('application_date') or '')
    if not applied:return {'action':action,'status':'insufficient','reason':'Date d’application non renseignée.'}
    groups,_=_catalog();selected,members,campaigns=_resolve_scope(groups,str(action.get('service_name') or ''),str(action.get('group_id') or ''))
    context=json.loads(action.get('context_json') or '{}');t1=str(context.get('time_from') or config()['work_start']);t2=str(context.get('time_to') or config()['work_end'])
    d=date.fromisoformat(applied);weekday=d.weekday()
    with connect() as c:
        days=[str(r['day']) for r in c.execute('SELECT day FROM call_coverage ORDER BY day')]
        before=[x for x in days if x<applied and date.fromisoformat(x).weekday()==weekday]
        after=[x for x in days if x>applied and date.fromisoformat(x).weekday()==weekday]
        before_day=before[-1] if before else '';after_day=after[0] if after else ''
        governance=_governance_context(groups,[x for x in (before_day,after_day) if x])
        file_id=str(action.get('file_id') or '').strip()
        if file_id:
            before_m=_file_metrics_for_day(c,before_day,t1,t2,[file_id],governance).get(file_id) if before_day else None
            after_m=_file_metrics_for_day(c,after_day,t1,t2,[file_id],governance).get(file_id) if after_day else None
        else:
            before_m=_metrics_for_day(c,before_day,t1,t2,members,campaigns,governance=governance) if before_day else None
            after_m=_metrics_for_day(c,after_day,t1,t2,members,campaigns,governance=governance) if after_day else None
    return {'action':action,'status':('ready' if before_m and after_m else 'insufficient'),'before':before_m,'after':after_m,
            'before_day':before_day,'after_day':after_day,'time_from':t1,'time_to':t2,
            'metric_scope':('file' if file_id else 'quality'),
            'message':'Évolution observée après l’action' if before_m and after_m else 'Données comparables insuffisantes',
            'causality':'Une évolution temporelle n’établit pas que l’action en est la cause.'}
