"""Phone-call search, enrichment and note attachment."""
from collections import Counter
import re
from agent_directory import admin_group_for, admin_name_for, load_admin_directory
from supervision_db import connect, config
from supervision_utils import display, selected_bounds, date_range, latest_agent_names
from db_compat import postgres_enabled

def _mask_ani(value):
    raw=str(value or '').strip()
    if not raw:return ''
    if len(raw)<=4:return '*'*len(raw)
    return raw[:2]+'*'*max(2,len(raw)-4)+raw[-2:]

def _apply_ani_visibility(result, query):
    show=str(query.get('_show_ani',['0'])[0]).strip()=='1'
    for row in result.get('rows') or []:
        if not show:row['ani']=_mask_ani(row.get('ani'))
        row['ani_masked']=not show
    result['ani_full']=show
    return result


def call_rows(c,qs,cfg,days,admin_directory=None):
    get=lambda k,d='':qs.get(k,[d])[0]
    cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM call_coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
    rows={}
    for day in days:
        if day not in cov:continue
        a,b=selected_bounds(day,cfg,qs,'1')
        for r in c.execute('SELECT * FROM phone_calls WHERE import_id=? AND start>=? AND start<?',(cov[day],a,b)):
            d=dict(r)
            if d['call_id'] not in rows or rows[d['call_id']]['import_id']<d['import_id']:rows[d['call_id']]=d
    values=list(rows.values())
    if '_allowed_agents' in qs:
        allowed={str(x) for x in (qs.get('_allowed_agents') or []) if str(x)}
        values=[r for r in values if str(r.get('first_agent') or '') in allowed or str(r.get('last_agent') or '') in allowed] if allowed else []
    phone=re.sub(r'[^0-9]','',get('phone'))
    if get('phone') and not phone:raise ValueError('Le numéro doit contenir des chiffres.')
    phone_field=get('phone_field','any')
    if phone_field not in ['any','ani','dnis','outtel','outdialed']:raise ValueError('Champ téléphone invalide.')
    fields=['ani','dnis','outtel','outdialed'] if phone_field=='any' else [phone_field]
    if phone:values=[r for r in values if any(phone in re.sub(r'[^0-9]','',r[f]) for f in fields)]
    if get('indice'):values=[r for r in values if r['indice']==get('indice').strip()]
    if get('call_id'):values=[r for r in values if r['call_id']==get('call_id').strip()]
    names=latest_agent_names(c)
    if admin_directory is None:admin_directory=load_admin_directory()
    admin_users=admin_directory['users']
    for agent in list(names):names[agent]=admin_name_for(agent,admin_users,names[agent])
    if get('agent'):
        term=get('agent').strip().lower()
        values=[r for r in values if any(term in (ag+' '+names.get(ag,'')).lower() for ag in [r['first_agent'],r['last_agent']] if ag not in ('','0'))]
    if get('campaign'):values=[r for r in values if get('campaign').strip().lower() in r['campaign'].lower()]
    if get('reason'):values=[r for r in values if r['end_reason']==get('reason').strip()]
    if get('call_type'):values=[r for r in values if r['call_type']==get('call_type')]
    issue=get('call_issue')
    if issue=='end_code':values=[r for r in values if r['end_reason'] not in ('','0')]
    elif issue=='short':values=[r for r in values if 0<r['conversation']<=10]
    elif issue=='invalid':values=[r for r in values if any(r[k]<0 for k in ['duration','conversation','wait'])]
    elif issue=='abandon':values=[r for r in values if r['abandon']]
    elif issue=='no_agent':values=[r for r in values if r['no_agent']]
    elif issue not in ('','all'):raise ValueError('Filtre d’appels invalide.')
    agent_meta={}
    def meta(agent):
        if agent not in agent_meta:
            agent_meta[agent]=(admin_name_for(agent,admin_users,names.get(agent,'')),*admin_group_for(agent,admin_users))
        return agent_meta[agent]
    for r in values:
        r['key']='call:'+r['call_id'];r['start_text']=display(r['start'],cfg['display_offset'])
        r['first_name'],r['first_group_id'],r['first_group_name']=meta(r['first_agent'])
        r['last_name'],r['last_group_id'],r['last_group_name']=meta(r['last_agent'])
    return values,[dict(day=d,source='export' if d in cov else 'missing') for d in days]

def attach_notes(c,rows):
    latest={}
    # Only read notes for events present in this result. Batches stay below old
    # SQLite parameter limits and use note_key(event_key,id).
    keys=list(dict.fromkeys(r.get('key','') for r in rows if r.get('key')))
    for offset in range(0,len(keys),400):
        batch=keys[offset:offset+400]
        marks=','.join('?' for _ in batch)
        for n in c.execute(f'SELECT * FROM notes WHERE event_key IN ({marks}) ORDER BY event_key,id DESC',batch):
            latest.setdefault(n['event_key'],[]).append(dict(n))
    for r in rows:
        r['notes']=latest.get(r['key'],[])
        n=r['notes'][0] if r['notes'] else {}
        r['diagnosis']=n.get('diagnosis') or 'À qualifier';r['cause']=n.get('cause') or 'Indéterminée';r['status']=n.get('status') or 'À vérifier'

_CALL_SORT_SQL = {
    'date': 'start', 'agent': "COALESCE(NULLIF(last_agent,''),NULLIF(first_agent,''),'')",
    'ani': "COALESCE(ani,'')", 'duration': 'duration', 'conversation': 'conversation',
    'wait': 'wait', 'indice': "COALESCE(indice,'')"
}

def _call_sort(qs):
    get=lambda k,d='':str(qs.get(k,[d])[0]).strip()
    key=get('sort');direction=get('sort_dir').lower()
    if not key or direction in ('','default'):
        return '', 'default'
    if key not in _CALL_SORT_SQL or direction not in ('asc','desc'):
        raise ValueError('Tri d\'appels invalide.')
    return key,direction

def _call_sort_python(row,key):
    if key=='date':return float(row.get('start') or 0)
    if key=='agent':return str(row.get('last_agent') or row.get('first_agent') or '').casefold()
    if key=='ani':return str(row.get('ani') or '').casefold()
    if key in ('duration','conversation','wait'):return float(row.get(key) or 0)
    if key=='indice':return str(row.get('indice') or '').casefold()
    return float(row.get('start') or 0)

def calls_view(qs):
    cfg=config();query=dict(qs);get=lambda k,d='':query.get(k,[d])[0]
    # Same fix as the Support technique view: without this, the calls search
    # defaults to today's real calendar date and looks empty after a
    # successful automatic import of past days.
    if 'date_from' not in query and 'day' not in query:
        with connect() as c:
            latest_day=c.execute('SELECT MAX(day) FROM call_coverage').fetchone()[0]
        from collection_store import latest_day as latest_live_day
        latest_day=latest_live_day(latest_day)
        if latest_day:
            query['date_from']=[latest_day]
            query['date_to']=[latest_day]
    days=date_range(query,cfg)
    # Validate even on days with no export/live data; never silently ignore an invalid slot.
    selected_bounds(days[0],cfg,query,'1')
    time_from=get('time_from').strip();time_to=get('time_to').strip()
    mode='custom' if (time_from or time_to) else ('all' if get('full_day','1')=='1' else 'work')
    time_filter=dict(mode=mode,start=time_from or ('00:00' if mode=='all' else cfg['work_start']),
        end=time_to or ('24:00' if mode=='all' else cfg['work_end']),timezone='Europe/Paris',
        basis='call_start',end_exclusive=True)
    page=max(0,int(get('page','0')))
    sort_key,sort_dir=_call_sort(query)
    # Filters that live entirely on phone_calls are pushed into SQL so a search
    # never loads an entire month into Python just to return 100 rows. Agent-name
    # and note filters still use the compatibility path because they span other
    # catalogues/tables and must preserve their exact historical semantics.
    phone_requested=bool(get('phone'))
    sql_filterable=(not phone_requested or postgres_enabled())
    if _SQL_CALL_LIST_ENABLED and sql_filterable:
        return _apply_ani_visibility(_calls_page_sql(query,cfg,days,page,time_filter,apply_filters=True),query)
    with connect() as c:
        rows,coverage=call_rows(c,query,cfg,days);attach_notes(c,rows)
        if get('diagnosis'):rows=[r for r in rows if r['diagnosis']==get('diagnosis')]
        if get('status'):rows=[r for r in rows if r['status']==get('status')]
        if sort_key:
            rows.sort(key=lambda r:(_call_sort_python(r,sort_key),str(r.get('call_id') or '')),reverse=sort_dir=='desc')
        else:
            rows.sort(key=lambda r:(r['start'],r['call_id']),reverse=True)
        n=len(rows);conversation=[r['conversation'] for r in rows if r['conversation']>0]
        summary=dict(records=n,indices=len({r['indice'] for r in rows if r['indice']}),
            invalid_durations=sum(any(r[k]<0 for k in ['duration','conversation','wait']) for r in rows),end_codes=sum(r['end_reason'] not in ('','0') for r in rows),short=sum(0<r['conversation']<=10 for r in rows),
            abandons=sum(bool(r['abandon']) for r in rows),no_agent=sum(bool(r['no_agent']) for r in rows),
            conversation=sum(conversation),average_conversation=round(sum(conversation)/len(conversation),1) if conversation else None)
        daily=Counter(display(r['start'],cfg['display_offset'])[:10] for r in rows)
        reasons=Counter(r['end_reason'] or '0' for r in rows)
        return _apply_ani_visibility(dict(date_from=days[0],date_to=days[-1],coverage=coverage,summary=summary,count=n,page=page,
          calls_revision='V56.2-CALLS-TIME-1',time_filter=time_filter,sort=sort_key,sort_dir=sort_dir,
          rows=rows[page*100:(page+1)*100],daily=[dict(label=d,value=daily[d] if any(x['day']==d and x['source']=='export' for x in coverage) else None) for d in days],
          reasons=[dict(label=k,value=v) for k,v in sorted(reasons.items())],config=cfg),query)



_SQL_CALL_LIST_ENABLED = True

def _calls_page_sql(query,cfg,days,page,time_filter,apply_filters=False):
    """Fast server-side call search over authoritative daily snapshots.

    ``call_coverage`` selects one import per business day and the selected day
    windows are disjoint.  The aggregate query therefore materializes only the
    handful of columns needed by the counters instead of every call column.
    Pagination is resolved from the per-day counts and then reads only the day
    (or two) required to return the requested 100 rows.  Older builds
    materialized the complete monthly call payload again for every page.
    """
    sort_key,sort_dir=_call_sort(query)
    with connect() as c:
        c.execute('BEGIN')
        cov={r['day']:r['import_id'] for r in c.execute(
            'SELECT * FROM call_coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
        parts=[];params=[];page_parts=[];page_params_all=[]
        extra_sql=[];extra_params=[]
        if apply_filters:
            get=lambda k,d='':query.get(k,[d])[0]
            phone=re.sub(r'[^0-9]','',get('phone'))
            if get('phone') and not phone:raise ValueError('Le numéro doit contenir des chiffres.')
            phone_field=get('phone_field','any')
            if phone_field not in ('any','ani','dnis','outtel','outdialed'):raise ValueError('Champ téléphone invalide.')
            if phone:
                if not postgres_enabled():
                    raise ValueError('Recherche téléphone SQL réservée à PostgreSQL')
                if phone_field=='any':
                    # One expression allows a single optional pg_trgm index to
                    # accelerate the common search-across-all-number-fields case.
                    extra_sql.append("regexp_replace(COALESCE(p.ani,'')||'|'||COALESCE(p.dnis,'')||'|'||COALESCE(p.outtel,'')||'|'||COALESCE(p.outdialed,''),'[^0-9|]','','g') LIKE ?")
                    extra_params.append('%'+phone+'%')
                else:
                    extra_sql.append("regexp_replace(COALESCE(p.%s,''),'[^0-9]','','g') LIKE ?"%phone_field)
                    extra_params.append('%'+phone+'%')
            if get('indice'):
                extra_sql.append('p.indice=?');extra_params.append(get('indice').strip())
            if get('call_id'):
                extra_sql.append('p.call_id=?');extra_params.append(get('call_id').strip())
            if get('campaign'):
                extra_sql.append("LOWER(COALESCE(p.campaign,'')) LIKE ?");extra_params.append('%'+get('campaign').strip().lower()+'%')
            if get('reason'):
                extra_sql.append('p.end_reason=?');extra_params.append(get('reason').strip())
            if get('call_type'):
                extra_sql.append('p.call_type=?');extra_params.append(get('call_type'))
            if '_allowed_agents' in query:
                allowed=sorted({str(x) for x in (query.get('_allowed_agents') or []) if str(x)})
                if allowed:
                    marks=','.join('?' for _ in allowed)
                    extra_sql.append('(p.first_agent IN ('+marks+') OR p.last_agent IN ('+marks+'))')
                    extra_params.extend(allowed);extra_params.extend(allowed)
                else:
                    extra_sql.append('1=0')
            if get('agent'):
                term=get('agent').strip().lower()
                # Resolve a name/login search once, then let SQL filter the call
                # table by the matching physical agent IDs. This preserves the
                # former "id + display name" semantics without loading calls.
                names_all=latest_agent_names(c)
                users_all=load_admin_directory()['users']
                candidates=set(names_all) | {str(x) for x in users_all}
                matching=sorted(a for a in candidates if term in (a+' '+admin_name_for(a,users_all,names_all.get(a,''))).lower())
                if matching:
                    marks=','.join('?' for _ in matching)
                    extra_sql.append('(p.first_agent IN ('+marks+') OR p.last_agent IN ('+marks+'))')
                    extra_params.extend(matching);extra_params.extend(matching)
                else:
                    extra_sql.append('1=0')
            if get('diagnosis'):
                extra_sql.append("COALESCE((SELECT n.diagnosis FROM notes n WHERE n.event_key='call:'||p.call_id ORDER BY n.id DESC LIMIT 1),'À qualifier')=?")
                extra_params.append(get('diagnosis'))
            if get('status'):
                extra_sql.append("COALESCE((SELECT n.status FROM notes n WHERE n.event_key='call:'||p.call_id ORDER BY n.id DESC LIMIT 1),'À vérifier')=?")
                extra_params.append(get('status'))
            issue=get('call_issue')
            if issue=='end_code':extra_sql.append("COALESCE(p.end_reason,'') NOT IN ('','0')")
            elif issue=='short':extra_sql.append('p.conversation>0 AND p.conversation<=10')
            elif issue=='invalid':extra_sql.append('(p.duration<0 OR p.conversation<0 OR p.wait<0)')
            elif issue=='abandon':extra_sql.append('p.abandon<>0')
            elif issue=='no_agent':extra_sql.append('p.no_agent<>0')
            elif issue not in ('','all'):raise ValueError('Filtre d’appels invalide.')
        suffix=(' AND '+' AND '.join(extra_sql)) if extra_sql else ''
        for day in days:
            if day not in cov:continue
            a,b=selected_bounds(day,cfg,query,'1')
            parts.append('''SELECT ? AS business_day,p.indice,p.duration,p.conversation,p.wait,
                         p.end_reason,p.abandon,p.no_agent
                         FROM phone_calls p WHERE import_id=? AND start>=? AND start<?'''+suffix)
            params.extend((day,cov[day],a,b));params.extend(extra_params)
            page_parts.append("SELECT ? AS business_day,p.* FROM phone_calls p WHERE import_id=? AND start>=? AND start<?"+suffix)
            page_params_all.extend((day,cov[day],a,b));page_params_all.extend(extra_params)
        scope=' UNION ALL '.join(parts) if parts else "SELECT '' AS business_day,'' AS indice,0 AS duration,0 AS conversation,0 AS wait,'' AS end_reason,0 AS abandon,0 AS no_agent WHERE FALSE"
        selected='WITH selected AS MATERIALIZED ('+scope+') '
        meta_sql=selected+'''SELECT 'summary' AS kind,'' AS label,
              COUNT(*) AS n1,COUNT(DISTINCT NULLIF(indice,'')) AS n2,
              COALESCE(SUM(CASE WHEN duration<0 OR conversation<0 OR wait<0 THEN 1 ELSE 0 END),0) AS n3,
              COALESCE(SUM(CASE WHEN end_reason IS NULL OR end_reason NOT IN ('','0') THEN 1 ELSE 0 END),0) AS n4,
              COALESCE(SUM(CASE WHEN conversation>0 AND conversation<=10 THEN 1 ELSE 0 END),0) AS n5,
              COALESCE(SUM(CASE WHEN abandon<>0 THEN 1 ELSE 0 END),0) AS n6,
              COALESCE(SUM(CASE WHEN no_agent<>0 THEN 1 ELSE 0 END),0) AS n7,
              COALESCE(SUM(CASE WHEN conversation>0 THEN conversation ELSE 0 END),0) AS n8,
              COALESCE(SUM(CASE WHEN conversation>0 THEN 1 ELSE 0 END),0) AS n9
            FROM selected
            UNION ALL
            SELECT 'daily',business_day,COUNT(*),0,0,0,0,0,0,0,0 FROM selected GROUP BY business_day
            UNION ALL
            SELECT 'reason',COALESCE(NULLIF(end_reason,''),'0'),COUNT(*),0,0,0,0,0,0,0,0
              FROM selected GROUP BY COALESCE(NULLIF(end_reason,''),'0')'''
        meta=list(c.execute(meta_sql,params))
        summary_row=next((r for r in meta if r['kind']=='summary'),None)
        if summary_row is None:
            agg=dict(records=0,indices=0,invalid_durations=0,end_codes=0,short=0,abandons=0,no_agent=0,conversation=0,average_conversation=None)
        else:
            positive=int(summary_row['n9'] or 0);conversation=float(summary_row['n8'] or 0)
            agg=dict(records=int(summary_row['n1'] or 0),indices=int(summary_row['n2'] or 0),
                invalid_durations=int(summary_row['n3'] or 0),end_codes=int(summary_row['n4'] or 0),
                short=int(summary_row['n5'] or 0),abandons=int(summary_row['n6'] or 0),
                no_agent=int(summary_row['n7'] or 0),conversation=conversation,
                average_conversation=round(conversation/positive,1) if positive else None)
        daily={str(r['label']):int(r['n1'] or 0) for r in meta if r['kind']=='daily'}
        reasons=[dict(label=str(r['label']),value=int(r['n1'] or 0)) for r in meta if r['kind']=='reason']
        reasons.sort(key=lambda r:r['label'])
        # The global ordering is equivalent to business-day descending followed
        # by start/call_id descending because the selected day windows never
        # overlap.  Use the aggregate daily counts to skip complete days without
        # touching phone_calls, then hydrate only the rows needed for this page.
        rows=[]
        if sort_key:
            expr=_CALL_SORT_SQL[sort_key];direction='ASC' if sort_dir=='asc' else 'DESC'
            null_last=f"CASE WHEN {expr} IS NULL OR CAST({expr} AS TEXT)='' THEN 1 ELSE 0 END ASC"
            page_scope=' UNION ALL '.join(page_parts) if page_parts else "SELECT NULL AS business_day,p.* FROM phone_calls p WHERE FALSE"
            sql='SELECT * FROM ('+page_scope+') q ORDER BY '+null_last+', '+expr+' '+direction+', start DESC, call_id DESC LIMIT ? OFFSET ?'
            rows=[dict(r) for r in c.execute(sql,[*page_params_all,100,page*100])]
        else:
            remaining=100;skip=page*100
            for day in reversed(days):
                if remaining<=0:break
                day_count=int(daily.get(day,0) or 0)
                if day_count<=0:continue
                if skip>=day_count:
                    skip-=day_count;continue
                ref=cov.get(day)
                if ref is None:continue
                a,b=selected_bounds(day,cfg,query,'1')
                page_sql='SELECT p.* FROM phone_calls p WHERE import_id=? AND start>=? AND start<?'+suffix+' ORDER BY start DESC,call_id DESC LIMIT ? OFFSET ?'
                page_params=[ref,a,b]+list(extra_params)+[remaining,skip]
                batch=[dict(r) for r in c.execute(page_sql,page_params)]
                rows.extend(batch);remaining-=len(batch);skip=0
        agent_ids={r[k] for r in rows for k in ('first_agent','last_agent')}
        names=latest_agent_names(c,agent_ids) if agent_ids else {}
        users=load_admin_directory()['users']
        for row in rows:
            row.pop('business_day',None);row['key']='call:'+row['call_id'];row['start_text']=display(row['start'],cfg['display_offset'])
            for side in ('first','last'):
                agent=row[side+'_agent'];row[side+'_name']=admin_name_for(agent,users,names.get(agent,''))
                row[side+'_group_id'],row[side+'_group_name']=admin_group_for(agent,users)
        attach_notes(c,rows)
        coverage=[dict(day=day,source='export' if day in cov else 'missing') for day in days]
        return _apply_ani_visibility(dict(date_from=days[0],date_to=days[-1],coverage=coverage,summary=agg,count=agg['records'],page=page,
                    calls_revision='V56.2-CALLS-TIME-1',time_filter=time_filter,sort=sort_key,sort_dir=sort_dir,rows=rows,
                    daily=[dict(label=d,value=daily.get(d,0) if d in cov else None) for d in days],reasons=reasons,config=cfg),query)
