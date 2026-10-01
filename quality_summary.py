"""Q2 read-only projections: explicit campaign groups, handled agents and hours."""
from collections import defaultdict
from app_db import db_connect
from group_workspace import group_records
from quality_importer import agent_key
from agent_directory import load_admin_directory, admin_name_for, admin_user_for, admin_key_candidates
from nelyio_time import display
from supervision_utils import latest_agent_names
from quality_rules import agent_assigned_sql


def group_catalog(campaigns):
    """Canonical analysis groups resolved from configured files, never campaign anchors.

    ``campaigns`` is only the currently visible call catalog; it limits which
    campaign IDs can be offered in the active period. Group membership itself
    comes from quality_group_lines + ACTIVE queue assignments only.
    """
    from quality_scope import load_quality_file_scope
    scope=load_quality_file_scope()
    available={str(c.get('campaign') or c.get('campaign_id') or '').strip() for c in campaigns}
    groups=[]
    assigned=set()
    for g in scope.get('groups',[]):
        gid=str(g.get('id'))
        if gid!='unassigned' and int(g.get('file_count') or 0)<=0:
            continue
        ids=[str(x) for x in g.get('campaign_ids',[]) if str(x) in available]
        if gid!='unassigned': assigned.update(ids)
        groups.append({'id':gid,'name':g.get('name') or '',
                       'service_name':str(g.get('service_name') or ''),
                       'campaign_ids':sorted(set(ids)),
                       'campaign_count':len(set(ids)),
                       'line_ids':list(g.get('line_ids') or []),
                       'member_agent_ids':list(g.get('member_agent_ids') or []),
                       'file_count':int(g.get('file_count') or 0),
                       'member_count':int(g.get('member_count') or 0),
                       'assignment_counts':dict(g.get('assignment_counts') or {}),
                       'basis':'configured_files','ambiguous_links':0})
    # If the cached synthetic group predates the current call catalog, make sure
    # every visible campaign still has an explicit diagnostic home.
    unassigned=next((g for g in groups if g['id']=='unassigned'),None)
    missing=sorted(available-assigned-set((unassigned or {}).get('campaign_ids',[])))
    if missing:
        if unassigned is None:
            unassigned={'id':'unassigned','name':'Sans groupe de file','campaign_ids':[],
                        'campaign_count':0,'line_ids':[],'member_agent_ids':[],
                        'file_count':0,'member_count':0,
                        'basis':'configured_files','ambiguous_links':0}
            groups.append(unassigned)
        unassigned['campaign_ids']=sorted(set(unassigned['campaign_ids'])|set(missing))
        unassigned['campaign_count']=len(unassigned['campaign_ids'])
    return groups


def handled_agents(c, where, params):
    # Business KPI: a call is treated when an AgentId is assigned (> 0).
    # IsCallAnswered remains a separate technical source flag.
    grouped={}
    assigned=agent_assigned_sql('f')
    for row in c.execute('SELECT agent,COUNT(*) AS handled FROM quality_inbound_facts f WHERE ('+where+') AND '+assigned+
                         ' GROUP BY agent',params):
        aid=agent_key(row['agent'])
        if aid in ('','0'):aid=''
        grouped[aid]=grouped.get(aid,0)+row['handled']
    directory=load_admin_directory()['users']
    fallback={}
    # Current directory is authoritative; source names fill missing identities only.
    missing=[aid for aid in grouped if aid and not any((admin_user_for(aid,directory) or {}).get(k) for k in ('first_name','last_name'))]
    aliases=sorted({alias for aid in missing for alias in admin_key_candidates(aid)})
    if aliases:
        for agent,name in latest_agent_names(c,aliases).items():
            row={'agent':agent,'name':name}
            fallback[agent_key(row['agent'])]=row['name']
    def name(aid):
        if not aid:return 'Agent non renseigné'
        user=admin_user_for(aid,directory) or {}
        if user.get('first_name') or user.get('last_name'):return admin_name_for(aid,directory)
        return fallback.get(aid) or admin_name_for(aid,directory)
    rows=[{'agent':aid,'name':name(aid),'handled':count} for aid,count in grouped.items()]
    return sorted(rows,key=lambda r:(-r['handled'],r['name'].casefold(),r['agent']))


def hourly_abandons(c,where,params,start_time,end_time,available_days):
    c.create_function('quality_local_hour',1,lambda ts:int(display(ts)[11:13]),deterministic=True)
    counts={r['hour']:r['abandoned'] for r in c.execute(
        'SELECT quality_local_hour(start) AS hour,SUM(abandoned) AS abandoned FROM quality_inbound_facts f WHERE '+where+
        ' AND abandoned=1 GROUP BY hour',params)}
    minutes=lambda value:sum(int(x)*m for x,m in zip(value.split(':'),(60,1)))
    lo=minutes(start_time) if start_time else 0
    hi=minutes(end_time) if end_time else 1440
    clock=lambda minute:f'{minute//60:02d}:{minute%60:02d}'
    total=sum(counts.values())
    return [{'hour':hour,'label':clock(max(lo,hour*60))+'–'+clock(min(hi,(hour+1)*60)),
             'abandoned':counts.get(hour,0) if available_days else None,
             'share':100*counts.get(hour,0)/total if available_days and total else None}
            for hour in range(lo//60,(hi+59)//60)]
