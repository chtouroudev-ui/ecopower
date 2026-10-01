"""Shared, presentation-neutral metrics for Nelyio.

Phase A introduced the common disconnect snapshot. Phase B adds reusable
period/agent comparison helpers so Analytics and Reports do not each invent a
different trend calculation.
"""
from collections import Counter


def disconnect_metric_snapshot(disconnects):
    """Normalize the core Support disconnect metrics for every consumer."""
    d=disconnects or {};s=d.get('summary') or {}
    return {
        'disconnects':int(s.get('total_deco') or 0),
        'during_call':int(s.get('total_deco_call') or 0),
        'during_call_percent':float(s.get('total_call_percent') or 0),
        'lost_seconds':int(s.get('total_lost') or 0),
        'impacted_agents':int(s.get('impacted_agents') or 0),
        'technical_impacted_agents':int(s.get('technical_impacted_agents') or 0),
        'collective_incidents':int(s.get('collective_disconnects') or 0),
        'probable_closures':int(s.get('probable_closures') or 0),
        'anomalies':int(s.get('anomalies_over_1h') or 0),
        'active_days':int(s.get('active_days') or 0),
        'average_seconds':int(s.get('avg_seconds') or 0),
        'median_seconds':int(s.get('median_seconds') or 0),
        'p95_seconds':int(s.get('p95_seconds') or 0),
        'max_seconds':int(s.get('max_seconds') or 0),
    }


def metric_delta(current, previous):
    current=float(current or 0);previous=float(previous or 0)
    if previous==0:return None if current else 0.0
    return round((current-previous)*100.0/previous,1)


def compare_snapshots(current, previous, keys=None):
    keys=keys or sorted(set(current or {})|set(previous or {}))
    out={}
    for key in keys:
        cur=(current or {}).get(key,0);prev=(previous or {}).get(key,0)
        try:delta=cur-prev
        except TypeError:delta=None
        out[key]={'current':cur,'previous':prev,'delta':delta,'percent':metric_delta(cur,prev)}
    return out



def compare_agent_trends(current_agents, previous_agents):
    """Compare technical incident aggregates agent by agent.

    The result is descriptive only: it reports changes in incident volume and
    identified technical time. It is intentionally independent from Support
    priority/scoring so the Analytics view remains a diagnostic trend tool.
    """
    def key(row):
        return str((row or {}).get('agent') or '').strip().casefold()
    current={key(r):dict(r) for r in (current_agents or []) if key(r)}
    previous={key(r):dict(r) for r in (previous_agents or []) if key(r)}
    rows=[]
    for agent_key in sorted(set(current)|set(previous)):
        cur=current.get(agent_key,{}) ; prev=previous.get(agent_key,{})
        identity=cur or prev
        ci=int(cur.get('incidents') or 0);pi=int(prev.get('incidents') or 0)
        cl=int(cur.get('lost_seconds') or 0);pl=int(prev.get('lost_seconds') or 0)
        cd=int(cur.get('days_affected') or 0);pd=int(prev.get('days_affected') or 0)
        if pi==0 and ci>0:status='appeared'
        elif ci==0 and pi>0:status='cleared'
        elif ci>pi:status='increased'
        elif ci<pi:status='decreased'
        else:status='stable'
        rows.append(dict(
            agent=identity.get('agent') or agent_key,name=identity.get('name') or identity.get('agent') or agent_key,
            group_id=identity.get('group_id'),group_name=identity.get('group_name') or '',pc=identity.get('pc') or '',ip=identity.get('ip') or '',
            current_incidents=ci,previous_incidents=pi,delta_incidents=ci-pi,incident_percent=metric_delta(ci,pi),
            current_lost_seconds=cl,previous_lost_seconds=pl,delta_lost_seconds=cl-pl,lost_percent=metric_delta(cl,pl),
            current_days_affected=cd,previous_days_affected=pd,status=status,
        ))
    rows.sort(key=lambda r:(-abs(r['delta_incidents']),-abs(r['delta_lost_seconds']),str(r.get('name') or '').casefold()))
    return rows

def aggregate_incident_metrics(incidents, days):
    """Aggregate Analytics-only incident context without redefining disconnect KPIs."""
    by_agent={};by_recurrence={}
    daily_acc={day:{'incidents':0,'agents':set(),'lost_seconds':0,'collective':0} for day in days}
    hourly_acc=[{'incidents':0,'agents':set(),'lost_seconds':0,'collective':0} for _ in range(24)]
    categories=Counter()
    for r in incidents or []:
        category=str(r.get('category') or '')
        categories[category]+=1
        agent=str(r.get('agent') or '').strip();lost=int(r.get('governance_effective_seconds',r.get('duration') or 0)) if category in ('offline','inactive') else 0
        collective=int(bool(r.get('collective')));day=str(r.get('day') or '')
        if day in daily_acc:
            d=daily_acc[day];d['incidents']+=1;d['lost_seconds']+=lost;d['collective']+=collective
            if agent:d['agents'].add(agent)
        try:hour=int(str(r.get('start_text') or '')[11:13])
        except (ValueError,TypeError):hour=-1
        if 0<=hour<24:
            h=hourly_acc[hour];h['incidents']+=1;h['lost_seconds']+=lost;h['collective']+=collective
            if agent:h['agents'].add(agent)
        if not agent:continue
        st=by_agent.setdefault(agent,dict(agent=agent,name=r.get('name') or agent,group_id=r.get('group_id'),group_name=r.get('group_name',''),pc=r.get('pc',''),ip=r.get('ip',''),incidents=0,lost_seconds=0,offline=0,inactive=0,technical=0,collective=0,days=set(),max_seconds=0,last_start=0,last_text=''))
        st['incidents']+=1;st['lost_seconds']+=lost;st['offline']+=int(category=='offline');st['inactive']+=int(category=='inactive');st['technical']+=int(category not in ('offline','inactive'));st['collective']+=collective;st['days'].add(day);st['max_seconds']=max(st['max_seconds'],int(r.get('duration') or 0))
        if float(r.get('start') or 0)>=st['last_start']:st['last_start']=float(r.get('start') or 0);st['last_text']=r.get('start_text') or ''
        key=(agent,category);rec=by_recurrence.setdefault(key,dict(agent=agent,name=st['name'],group_name=st['group_name'],pc=st['pc'],category=category,label=r.get('label') or category,count=0,lost_seconds=0,days=set(),max_seconds=0,collective=0,last_text=''))
        rec['count']+=1;rec['lost_seconds']+=int(r.get('governance_effective_seconds',r.get('duration') or 0));rec['days'].add(day);rec['max_seconds']=max(rec['max_seconds'],int(r.get('duration') or 0));rec['collective']+=collective
        text=r.get('start_text') or ''
        if not rec['last_text'] or text>rec['last_text']:rec['last_text']=text
    agents=[]
    for st in by_agent.values():
        st['days_affected']=len(st.pop('days'));agents.append(st)
    agents.sort(key=lambda r:(-r['incidents'],-r['lost_seconds'],str(r.get('name') or '')))
    recurrence=[]
    for rec in by_recurrence.values():
        rec['days_affected']=len(rec.pop('days'))
        if rec['count']>=2:recurrence.append(rec)
    recurrence.sort(key=lambda r:(-r['days_affected'],-r['count'],-r['lost_seconds'],str(r.get('name') or '')))
    daily=[dict(label=day,incidents=daily_acc[day]['incidents'],agents=len(daily_acc[day]['agents']),lost_seconds=daily_acc[day]['lost_seconds'],collective=daily_acc[day]['collective']) for day in days]
    hourly=[dict(label=f'{hour:02d}h',incidents=hourly_acc[hour]['incidents'],agents=len(hourly_acc[hour]['agents']),lost_seconds=hourly_acc[hour]['lost_seconds'],collective=hourly_acc[hour]['collective']) for hour in range(24)]
    return dict(agents=agents,recurrence=recurrence,daily=daily,hourly=hourly,categories=categories,
        summary=dict(incidents=len(incidents or []),impacted_agents=len(by_agent),lost_seconds=sum(int(r.get('governance_effective_seconds',r.get('duration') or 0)) for r in incidents or [] if r.get('category') in ('offline','inactive')),
                     disconnects=categories.get('offline',0),inactive=categories.get('inactive',0),technical=sum(v for k,v in categories.items() if k not in ('offline','inactive')),
                     collective_incidents=sum(bool(r.get('collective')) for r in incidents or []),recurring_agents=len({r['agent'] for r in recurrence})))
