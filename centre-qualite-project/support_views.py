"""Support Nelyio overview and diagnostic view composition."""
from collections import Counter
from datetime import datetime
import re
from supervision_db import connect, config, now, audit
from agent_directory import (admin_name_for, admin_user_for, build_agent_roster, load_admin_directory,
    support_agent_is_excluded)
from supervision_utils import (display, day_bounds, selected_bounds, date_range, period_buckets, union_seconds, classify_anomaly, latest_agent_names)
from live_capture import live_intervals
from calls import call_rows, attach_notes
from support_filters import (TECH_LABELS, MAX_NORMAL_DISCONNECT_SECONDS, _support_excluded_slots,
    _in_support_excluded_slot, _overlaps_support_excluded_slot, valid_gap_key)
from disconnects import disconnect_statistics, data_integrity
from metrics_engine import disconnect_metric_snapshot
from governance_engine import governed_visible_events
from policy_engine import load_policies
from declaration_engine import load_declarations
from unified_filters import normalize_filters, public_filter_contract
from analysis_groups import matches_agent_groups, group_ids_for_agent, group_names_for_agent, filter_catalog

def chart_data(rows, cfg, a, b, mode):
    """Aggregate the full filtered result before pagination; no source mixing."""
    grouped={}
    for r in rows:
        grouped.setdefault(r['agent'],[]).append(r)
    durations=[]
    for k in ['call','ready','pause','wrap','offline','other']:
        seconds=sum(union_seconds([r for r in rs if r['kind']==k]) for rs in grouped.values())
        durations.append(dict(key=k,value=seconds))
    buckets=[]
    t=a
    while t<b:
        end=min(t+3600,b)
        buckets.append(dict(label=display(t,cfg['display_offset'])[11:16],end_label=display(end,cfg['display_offset'])[11:16],
            value=sum(1 for r in rows if r['anomaly'] and t<=r['start']<end)))
        t=end
    top=[]
    for agent,rs in grouped.items():
        flagged=[r for r in rs if r['anomaly']]
        if flagged:top.append(dict(agent=agent,label=rs[0]['name'] or agent,value=len(flagged)))
    top.sort(key=lambda r:(-r['value'],r['agent']))
    counts=Counter(r['kind'] for r in rows if r.get('fresh') is not False)
    agent_stats=[]
    for agent,rs in grouped.items():
        values={k:union_seconds([r for r in rs if r['kind']==k]) for k in ['call','ready','pause','wrap','offline']}
        agent_stats.append(dict(agent=agent,name=rs[0]['name'] or agent,activities=len(rs),
            anomalies=sum(bool(r['anomaly']) for r in rs),covered=union_seconds(rs),**values))
    agent_stats.sort(key=lambda r:(-r['anomalies'],r['name']))
    stats=dict(agents=len(grouped),activities=len(rows),anomalies=sum(bool(r['anomaly']) for r in rows),
        covered=sum(r['covered'] for r in agent_stats),
        flagged_agents=sum(r['anomalies']>0 for r in agent_stats))
    for k in ['call','ready','pause','wrap','offline']:
        episodes=[r for r in rows if r['kind']==k and r['duration']>0]
        stats[k+'_count']=len(episodes)
        stats[k+'_average']=round(sum(r['duration'] for r in episodes)/len(episodes)) if episodes else None
        stats[k+'_max']=max((r['duration'] for r in episodes),default=None)
    return dict(stats=stats,agent_stats=agent_stats,durations=durations,hourly=buckets,agents=top[:10],
                states=[dict(key=k,value=n) for k,n in sorted(counts.items())],
                stale=sum(r.get('fresh') is False for r in rows),total_rows=len(rows),mode=mode)

def view(qs):
    cfg=config();clock=datetime.now().timestamp()
    query=dict(qs)
    get=lambda k,d='':query.get(k,[d])[0]
    mode=get('mode','history')
    # Historical screens should open on the newest imported reference day.
    # Previously they defaulted to today's date, which made a successful older
    # import appear empty after a refresh or when using automatic import.
    if mode!='live' and 'date_from' not in query and 'day' not in query:
        with connect() as c:
            latest_day=c.execute('SELECT MAX(day) FROM coverage').fetchone()[0]
        from collection_store import latest_day as latest_live_day
        latest_day=latest_live_day(latest_day)
        if latest_day:
            query['date_from']=[latest_day]
            query['date_to']=[latest_day]
    days=date_range(query,cfg);day=days[0];a,b=day_bounds(day,cfg)
    full=get('full_day')=='1'
    source=get('source','reference');agent_filter=get('agent').strip().lower()
    filter_kind=get('kind');page=max(0,int(get('page','0')))
    with connect() as c:
        cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
        coverage=bool(cov)
        imports=[dict(r) for r in c.execute('SELECT * FROM imports ORDER BY id DESC LIMIT 30')]
        health=[dict(r) for r in c.execute('SELECT * FROM health')]
        names=latest_agent_names(c)
        from collection_views import enrich_names
        enrich_names(names)
        admin_directory=load_admin_directory();admin_users=admin_directory['users']
        for agent_id in list(names):names[agent_id]=admin_name_for(agent_id,admin_users,names[agent_id])
        if mode=='live':
            rows=[dict(r) for r in c.execute('''SELECT e.* FROM live_events e JOIN
              (SELECT source,agent,MAX(start) ts FROM live_events GROUP BY source,agent) x
              ON e.source=x.source AND e.agent=x.agent AND e.start=x.ts ORDER BY e.agent''')]
            hs={h['source']:h for h in health}
            out=[]
            for r in rows:
                h=hs.get(r['source'],{});hb=h.get('heartbeat') or 0
                fresh=0<=clock-hb<=cfg['stale_seconds']
                if fresh:
                    ps=[x[0] for x in c.execute('SELECT stamp FROM health_points WHERE source=? AND stamp>=? AND stamp<=? ORDER BY stamp',(r['source'],r['start']-5,hb))]
                    fresh=bool(ps) and ps[0]<=r['start']+5 and all(y-x<=cfg['stale_seconds'] for x,y in zip(ps,ps[1:]))
                out.append(dict(key='live:'+r['event_key'],agent=r['agent'],name=names.get(r['agent'],''),
                    start=r['start'],end=max(r['start'],min(clock,hb)) if fresh else r['start'],state=r['state'],kind=r['kind'],
                    campaign=r['campaign'],source='capture',quality='Provisoire' if fresh else 'État ancien — à vérifier',
                    fresh=fresh,initial=bool(r['initial']),collector=r['source']))
            rows=out;reference=False
        else:
            rows=[];provenance=[]
            for current_day in days:
                da,db=day_bounds(current_day,cfg,work=not full)
                ref=cov.get(current_day) if source!='capture' else None
                if ref:
                    rs=[dict(r) for r in c.execute('SELECT * FROM activities WHERE import_id=? AND start<? AND end>=?',(ref,db,da))]
                    for r in rs:
                        r.update(key='export:'+str(r['id']),source='export',quality='Référence SIMPLIFY2',start=max(da,r['start']),end=min(db,r['end']))
                else:rs=live_intervals(c,da,db,cfg,clock)
                provenance.append(dict(day=current_day,source='export' if ref else ('capture' if rs else 'missing'),rows=len(rs)))
                rows.extend(rs)
            reference=all(x['source']=='export' for x in provenance)
        for r in rows:
            r['name']=r.get('name') or names.get(r['agent'],'')
            r['duration']=max(0,int(r['end']-r['start']))
            r['anomaly']=classify_anomaly(r,cfg) if r.get('fresh') is not False else ''
            r['start_text']=display(r['start'],cfg['display_offset']);r['end_text']=display(r['end'],cfg['display_offset'])
        if agent_filter:rows=[r for r in rows if agent_filter in (r['agent']+' '+r['name']).lower()]
        if filter_kind:rows=[r for r in rows if r['kind']==filter_kind]
        # Sum per agent, merging overlaps; never sum live and export together.
        byagent={}
        for r in rows:byagent.setdefault(r['agent'],[]).append(r)
        totals={k:sum(union_seconds([r for r in rs if r['kind']==k]) for rs in byagent.values()) for k in ['call','pause','offline','ready','wrap']}
        summary=dict(agents=len(byagent),activities=len(rows),anomalies=sum(bool(r['anomaly']) for r in rows),durations=totals)
        if mode=='anomalies':rows=[r for r in rows if r['anomaly']]
        rows.sort(key=lambda r:r['start'],reverse=True)
        charts=chart_data(rows,cfg,a,b,mode)
        if mode!='live':
            charts['hourly']=period_buckets(rows,days,cfg,full)
            if len(days)>1:
                missing={r['day'] for r in provenance if r['source']=='missing'}
                for bucket in charts['hourly']:
                    if bucket['label'] in missing:bucket['value']=None
        else:provenance=[]
        count=len(rows);rows=rows[page*100:(page+1)*100]
        notes={}
        if rows:
            keys=[r['key'] for r in rows]
            for note in c.execute('SELECT * FROM notes WHERE event_key IN ('+','.join('?' for _ in keys)+') ORDER BY id DESC',keys):
                notes.setdefault(note['event_key'],[]).append(dict(note))
        for r in rows:r['notes']=notes.get(r['key'],[])
        for h in health:
            hb=h.get('heartbeat') or 0
            h['fresh']=0<=clock-hb<=cfg['stale_seconds'];h['heartbeat_text']=display(hb,cfg['display_offset']) if hb else None
            h['received_text']=display(h['received'],cfg['display_offset']) if h['received'] else None
        return dict(filters=dict(agent=agent_filter,kind=filter_kind,source=source),day=day,date_from=days[0],date_to=days[-1],provenance=provenance,rows=rows,count=count,page=page,summary=summary,reference=reference,
          coverage=bool(coverage),health=health,imports=imports,config=cfg,charts=charts,clock=display(clock,cfg['display_offset']),
          admin_groups=filter_catalog(),available_agents=build_agent_roster(names,admin_directory),admin_directory_available=admin_directory['available'])


def diagnostic_incidents_view(qs):
    """Minimal incident-by-incident feed used by the Diagnostic > Détails UI.

    This view intentionally reuses ``disconnect_statistics`` so Détails and the
    Diagnostic overview share the exact same filtering, classification,
    Policies/Declarations and call-context rules.  Raw archives remain
    available through the existing ``/api/supervision/details`` endpoint.
    """
    cfg=config();query=dict(qs or {})
    get=lambda k,d='':query.get(k,[d])[0]
    # Open on the newest imported reference day when no explicit period exists.
    if 'date_from' not in query and 'day' not in query:
        with connect() as c:
            latest=c.execute('SELECT MAX(day) FROM coverage').fetchone()[0]
        from collection_store import latest_day as latest_live_day
        latest=latest_live_day(latest)
        if latest:
            query['date_from']=[latest];query['date_to']=[latest]
    query['_include_incidents']=['1']
    query,common,days,hidden=normalize_filters(query,cfg,default_full_day='1')
    page=max(0,int(get('page','0') or 0))
    try:page_size=max(10,min(100,int(get('page_size','25') or 25)))
    except ValueError:page_size=25
    sort=str(get('sort','date') or 'date').strip().lower()
    if sort not in ('date','duration'):sort='date'
    with connect() as c:
        cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
        names=latest_agent_names(c)
        from collection_views import enrich_names
        enrich_names(names)
        admin_directory=load_admin_directory();admin_users=admin_directory['users']
        for agent in list(names):names[agent]=admin_name_for(agent,admin_users,names[agent])
        stats=disconnect_statistics(c,query,cfg,days,cov,names,admin_directory=admin_directory,policy_module='details')
    # Phase F3.2: Détails follows the exact same final governance filter as
    # every other technical screen. Raw evidence remains available through the
    # linked incident-evidence endpoint for audit/troubleshooting.
    incidents=[r for r in list(stats.get('incidents') or stats.get('recent') or []) if not r.get('governance_exclude_statistics')]
    anomalies=[r for r in list(stats.get('all_anomalies') or stats.get('anomalies') or []) if not r.get('governance_exclude_statistics')]
    for r in anomalies:
        r.setdefault('event_class','duration_anomaly');r.setdefault('event_label','Anomalie > 1 h')
        r.setdefault('classification_reason',r.get('reason') or 'Déconnexion supérieure à 1 heure, à vérifier.')
    rows=incidents+anomalies
    if sort=='duration':rows.sort(key=lambda r:(-int(r.get('seconds') or 0),-float(r.get('start') or 0),str(r.get('agent') or '')))
    else:rows.sort(key=lambda r:(-float(r.get('start') or 0),str(r.get('agent') or '')))
    def probable_cause(r):
        if r.get('declaration_applied'):
            return 'Déclaration — '+str(r.get('declaration_reason') or 'période déclarée')
        if r.get('policy_applied') and r.get('policy_authorized'):
            return 'Policy — '+str(r.get('policy_reason') or 'événement autorisé')
        kind=str(r.get('event_class') or '')
        if kind=='collective_incident':return 'Cause partagée probable — réseau / Hermès / infrastructure'
        if kind=='probable_closure':return 'Organisation / application — fermeture ou pause probable'
        if kind=='duration_anomaly':return 'Session / donnée — durée supérieure à 1 heure'
        if r.get('during_call'):return 'Déconnexion technique pendant appel — à qualifier'
        return 'Déconnexion technique hors appel — à qualifier'
    total=len(rows);paged=rows[page*page_size:(page+1)*page_size]
    public_rows=[]
    for r in paged:
        public_rows.append(dict(
            incident_id=f"{r.get('agent','')}:{int(float(r.get('start') or 0))}:{int(float(r.get('end') or 0))}",
            start=r.get('start'),end=r.get('end'),start_text=r.get('start_text',''),end_text=r.get('end_text',''),
            agent=r.get('agent',''),name=r.get('name') or r.get('agent',''),group_id=r.get('group_id'),group_name=r.get('group_name',''),
            seconds=int(r.get('seconds') or 0),during_call=bool(r.get('during_call')),source=r.get('source',''),
            event_class=r.get('event_class','technical_disconnect'),event_label=r.get('event_label','Déconnexion technique'),
            cause=probable_cause(r),classification_reason=r.get('classification_reason',''),
            call_id=r.get('call_id',''),indice=r.get('indice',''),ani=r.get('ani',''),dnis=r.get('dnis',''),campaign=r.get('campaign',''),
            policy_applied=bool(r.get('policy_applied')),policy_reason=r.get('policy_reason',''),
            declaration_applied=bool(r.get('declaration_applied')),declaration_reason=r.get('declaration_reason',''),
            governance_exclude_statistics=bool(r.get('governance_exclude_statistics')),
            governance_effective_seconds=int(r.get('governance_effective_seconds',r.get('seconds') or 0)),
            governance_excluded_seconds=int(r.get('governance_excluded_seconds',0)),
            governance_partially_excluded=bool(r.get('governance_partially_excluded')),
            governance_contract_version=r.get('governance_contract_version',''),
        ))
    public=public_filter_contract(common)
    return dict(date_from=days[0],date_to=days[-1],rows=public_rows,total=total,page=page,page_size=page_size,
        pages=max(1,(total+page_size-1)//page_size) if total else 1,sort=sort,summary=stats.get('summary',{}),
        common_filters=public,filters=public,admin_groups=filter_catalog(),
        available_agents=build_agent_roster(names,admin_directory,exclude_support=False),
        priority_policy=stats.get('priority_policy',[]))

def add_note(d,actor):
    key=str(d.get('key',''));status=d.get('status','À vérifier');comment=str(d.get('comment','')).strip()
    if status not in ['À vérifier','En cours','Résolu','Comportement normal']:raise ValueError('Statut invalide.')
    if not comment or len(comment)>4000:raise ValueError('Commentaire requis, 4000 caractères maximum.')
    with connect() as c:
        if key.startswith('export:'):found=c.execute('SELECT 1 FROM activities WHERE id=?',(key[7:],)).fetchone()
        elif key.startswith('tech:'):found=c.execute('SELECT 1 FROM technical_signals WHERE signal_key=?',(key[5:],)).fetchone()
        elif key.startswith('call:'):found=c.execute('SELECT 1 FROM phone_calls WHERE call_id=?',(key[5:],)).fetchone()
        elif key.startswith('gap:'):found=valid_gap_key(c,key)
        elif key.startswith('live:'):found=c.execute('SELECT 1 FROM live_events WHERE event_key=?',(key[5:],)).fetchone()
        else:found=None
        if not found:raise ValueError('Événement introuvable.')
        diagnosis=d.get('diagnosis','À qualifier');cause=d.get('cause','Indéterminée')
        if diagnosis not in ['À qualifier','Incident technique confirmé','Non technique']:raise ValueError('Qualification invalide.')
        if cause not in ['Indéterminée','Réseau / VPN','Audio / casque','Hermès / téléphonie','Poste / système','Capture / collecte','Organisation']:raise ValueError('Cause invalide.')
        c.execute('INSERT INTO notes(event_key,author,stamp,status,comment,diagnosis,cause) VALUES(?,?,?,?,?,?,?)',(key,actor,now(),status,comment,diagnosis,cause))
        audit(c,actor,'NOTE',key+' '+status)
    return {'ok':True}

def _support_anomalous_call_rows(c, query, cfg, days, admin_directory=None):
    """Load only call rows that can become Support signals.

    The Support UI only materializes ODCalls rows with an EndReason or an
    invalid duration.  Older builds called calls.call_rows(), which loaded
    every call in the selected period (200k+ rows in the real September HAR)
    before throwing almost all of them away.  Keep the exact visible semantics
    while making the cost proportional to anomalous calls.
    """
    get=lambda k,d='':query.get(k,[d])[0]
    cov={r['day']:r['import_id'] for r in c.execute(
        'SELECT * FROM call_coverage WHERE day BETWEEN ? AND ?', (days[0],days[-1]))}
    rows={}
    anomaly="(COALESCE(end_reason,'') NOT IN ('','0') OR duration<0 OR conversation<0 OR wait<0)"
    for day in days:
        ref=cov.get(day)
        if not ref:
            continue
        a,b=selected_bounds(day,cfg,query,'1')
        sql=f'SELECT * FROM phone_calls WHERE import_id=? AND start>=? AND start<? AND {anomaly}'
        for r in c.execute(sql,(ref,a,b)):
            d=dict(r)
            if d['call_id'] not in rows or rows[d['call_id']]['import_id']<d['import_id']:
                rows[d['call_id']]=d
    values=list(rows.values())
    phone=re.sub(r'[^0-9]','',get('phone'))
    if get('phone') and not phone:
        raise ValueError('Le numéro doit contenir des chiffres.')
    phone_field=get('phone_field','any')
    if phone_field not in ['any','ani','dnis','outtel','outdialed']:
        raise ValueError('Champ téléphone invalide.')
    fields=['ani','dnis','outtel','outdialed'] if phone_field=='any' else [phone_field]
    if phone:
        values=[r for r in values if any(phone in re.sub(r'[^0-9]','',str(r.get(f) or '')) for f in fields)]
    if get('indice'):
        values=[r for r in values if str(r.get('indice') or '')==get('indice').strip()]
    if get('call_id'):
        values=[r for r in values if str(r.get('call_id') or '')==get('call_id').strip()]
    if get('campaign'):
        term=get('campaign').strip().lower();values=[r for r in values if term in str(r.get('campaign') or '').lower()]
    if get('reason'):
        values=[r for r in values if str(r.get('end_reason') or '')==get('reason').strip()]
    if get('call_type'):
        values=[r for r in values if str(r.get('call_type') or '')==get('call_type')]
    issue=get('call_issue')
    if issue=='end_code':
        values=[r for r in values if str(r.get('end_reason') or '') not in ('','0')]
    elif issue=='invalid':
        values=[r for r in values if any((r.get(k) or 0)<0 for k in ['duration','conversation','wait'])]
    elif issue=='short':
        values=[r for r in values if 0<(r.get('conversation') or 0)<=10]
    elif issue=='abandon':
        values=[r for r in values if r.get('abandon')]
    elif issue=='no_agent':
        values=[r for r in values if r.get('no_agent')]
    elif issue not in ('','all'):
        raise ValueError('Filtre d’appels invalide.')
    names=latest_agent_names(c)
    if admin_directory is None:
        admin_directory=load_admin_directory()
    users=admin_directory['users']
    for agent in list(names):
        names[agent]=admin_name_for(agent,users,names[agent])
    if get('agent'):
        term=get('agent').strip().lower()
        values=[r for r in values if any(
            term in (str(ag)+' '+names.get(str(ag),'')).lower()
            for ag in [r.get('first_agent'),r.get('last_agent')] if str(ag or '') not in ('','0'))]
    for r in values:
        r['key']='call:'+str(r.get('call_id') or '')
        r['start_text']=display(r['start'],cfg['display_offset'])
    coverage=[dict(day=d,source='export' if d in cov else 'missing') for d in days]
    return values,coverage

def support_view(qs):
    cfg=config();query,common_filters,days,hidden=normalize_filters(qs,cfg,default_full_day='1')
    get=lambda k,d='':query.get(k,[d])[0]
    page=max(0,int(get('page','0')));signals=[];provenance=[]
    by_key={}
    def add(r):
        if r['key'] in by_key:
            prior=by_key[r['key']];prior['intervals'].append({'start':r['start'],'end':r['end']})
            prior['start']=min(prior['start'],r['start']);prior['end']=max(prior['end'],r['end']);return
        r['intervals']=[{'start':r['start'],'end':r['end']}]
        by_key[r['key']]=r;signals.append(r)
    with connect() as c:
        cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
        names=latest_agent_names(c)
        from collection_views import enrich_names
        enrich_names(names)
        admin_directory=load_admin_directory();admin_users=admin_directory['users']
        for agent in list(names):names[agent]=admin_name_for(agent,admin_users,names[agent])
        support_query={k:list(v) for k,v in query.items()}
        support_query['_compact']=['1']
        disconnects=disconnect_statistics(c,support_query,cfg,days,cov,names,admin_directory=admin_directory,policy_module="support")
        selected_source=hidden.get('source','')
        for day in days:
            a,b=selected_bounds(day,cfg,query,'1');ref=cov.get(day)
            use_export=bool(ref) and selected_source!='capture'
            use_capture=(not use_export) and selected_source!='export'
            used='missing'
            if use_export:
                used='export'
                offline=[dict(r) for r in c.execute("SELECT * FROM activities WHERE import_id=? AND kind='offline' AND start<? AND end>?",(ref,b,a))]
                for r in offline:
                    end=min(b,r['end']);begin=max(a,r['start'])
                    if end>begin:
                        add(dict(key='export:'+str(r['id']),agent=r['agent'],start=begin,end=end,category='offline',source='export',
                          detail='Déconnexion suivie d’une reconnexion dans ODActions. Elle peut être prévue ; cause à qualifier.'))
            elif use_capture:
                live=live_intervals(c,a,b,cfg,datetime.now().timestamp())
                if live:used='capture'
                for r in live:
                    if r['kind']=='offline' and r['end']>r['start']:
                        add(dict(key=r['key'],agent=r['agent'],start=r['start'],end=r['end'],category='offline',source='capture',detail='Durée provisoire, limitée aux signaux de capture continus.'))
            provenance.append(dict(day=day,source=used))
            if selected_source!='export':
                for r in c.execute('SELECT * FROM technical_signals WHERE start>=? AND start<?',(a,b)):
                    r=dict(r);add(dict(key='tech:'+r['signal_key'],agent=r['agent'],start=r['start'],end=r['start'],category=r['category'],source='capture',collector=r['source'],detail=r['detail']))
                points={}
                for r in c.execute('SELECT source,stamp FROM health_points WHERE stamp>=? AND stamp<? ORDER BY source,stamp',(a,b)):
                    points.setdefault(r['source'],[]).append(r['stamp'])
                for source,ps in points.items():
                    for start,end in zip(ps,ps[1:]):
                        if end-start>cfg['stale_seconds']:
                            add(dict(key=f'gap:{source}:{start}:{end}',agent='',start=start,end=end,category='capture_gap',source='capture',collector=source,
                              detail='Intervalle entre deux signaux Hermès. Peut correspondre à une capture arrêtée ; ce n’est pas une durée d’arrêt de production.'))
        calls,call_cov=_support_anomalous_call_rows(c,query,cfg,days,admin_directory=admin_directory)
        if selected_source!='capture':
            for r in calls:
                invalid=any(r[k]<0 for k in ['duration','conversation','wait'])
                if r['end_reason'] not in ('','0') or invalid:
                    add(dict(key=r['key'],agent=r['last_agent'] if r['last_agent']!='0' else '',start=r['start'],end=r['start'],category='end_code' if r['end_reason'] not in ('','0') else 'invalid_duration',source='export',
                      detail=('Durée négative exportée : exclue des moyennes de conversation. ' if invalid else '')+'Code EndReason '+r['end_reason']+' exporté. Signification et cause à vérifier.',call_id=r['call_id'],indice=r['indice'],ani=r['ani'],dnis=r['dnis']))
        excluded_cache={};admin_user_cache={}
        def is_excluded(agent):
            if agent not in excluded_cache:excluded_cache[agent]=support_agent_is_excluded(agent,admin_directory)
            return excluded_cache[agent]
        def user_for(agent):
            if agent not in admin_user_cache:admin_user_cache[agent]=admin_user_for(agent,admin_users)
            return admin_user_cache[agent]
        signals=[r for r in signals if not r.get('agent') or not is_excluded(r.get('agent'))]
        for r in signals:
            admin_user=user_for(r['agent']);r['name']=(admin_user or {}).get('display_name') or names.get(r['agent'],'')
            r['group_ids']=group_ids_for_agent(r.get('agent'));r['group_names']=group_names_for_agent(r.get('agent'));r['group_id']=(r['group_ids'][0] if len(r['group_ids'])==1 else None);r['group_name']=(r['group_names'][0] if len(r['group_names'])==1 else '');r['state']=TECH_LABELS[r['category']]
            r['duration']=union_seconds(r['intervals']);r['start_text']=display(r['start'],cfg['display_offset'])
            r['end_text']=display(r['end'],cfg['display_offset'])
        min_disconnect=float(common_filters.get('min_disconnect') or 0)
        excluded_slots=_support_excluded_slots(query)
        filtered_signals=[]
        for r in signals:
            if r['category']=='offline':
                if r['duration']<=0 or r['duration']>MAX_NORMAL_DISCONNECT_SECONDS or r['duration']<min_disconnect:continue
                if _overlaps_support_excluded_slot(r['start'],r['end'],cfg,excluded_slots):continue
            elif _in_support_excluded_slot(r['start'],cfg,excluded_slots):
                # Common exclusion windows apply to every visible diagnostic
                # event, not only to disconnect rows.
                continue
            filtered_signals.append(r)
        signals=filtered_signals
        # Phase E: every visible technical signal now passes through the same
        # Policy + Declaration decision used by disconnect KPIs. Legacy time
        # slots remain an optional compatibility pre-filter only.
        for r in signals:
            r['seconds']=int(r.get('duration') or 0)
            r['day']=str(r.get('start_text') or '')[:10]
            r['hour']=str(r.get('start_text') or '')[11:16]
            r['event_label']=TECH_LABELS.get(r.get('category'),'Signal technique')
        generic_policies=load_policies()
        declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
        signals,governance_excluded_signals=governed_visible_events(signals,'support',generic_policies,declarations)
        if get('agent'):
            term=get('agent').lower().strip();signals=[r for r in signals if term in (r['agent']+' '+r['name']).lower()]
        group_filters={str(x) for x in common_filters.get('groups',[]) if str(x)}
        if group_filters:signals=[r for r in signals if matches_agent_groups(r.get('agent'),group_filters)]
        if get('phone') or get('indice') or get('call_id') or get('campaign') or get('reason') or get('call_type') or get('call_issue'):
            signals=[r for r in signals if r.get('call_id')]
        legacy_category=get('category') or hidden.get('type','')
        if legacy_category:signals=[r for r in signals if r['category']==legacy_category]
        if selected_source:signals=[r for r in signals if r['source']==selected_source]
        attach_notes(c,signals)
        if get('diagnosis'):signals=[r for r in signals if r['diagnosis']==get('diagnosis')]
        if get('status'):signals=[r for r in signals if r['status']==get('status')]
        counts=Counter(r['category'] for r in signals);daily=Counter(display(r['start'],cfg['display_offset'])[:10] for r in signals)
        agents=Counter((r['agent'],r['name'] or r['agent']) for r in signals if r['agent'] not in ('','0'))
        summary=dict(signals=len(signals),agents=len(agents),confirmed=sum(r['diagnosis']=='Incident technique confirmé' for r in signals),
          unqualified=sum(r['diagnosis']=='À qualifier' for r in signals),normal=sum(r['diagnosis']=='Non technique' for r in signals),
          resolved=sum(r['status']=='Résolu' for r in signals),governance_excluded=len(governance_excluded_signals))
        signals.sort(key=lambda r:(r['start'],r['key']),reverse=True)
        health=[]
        for r in c.execute('SELECT * FROM health'):
            hb=r['heartbeat'] or 0
            health.append(dict(source=r['source'],fresh=0<=datetime.now().timestamp()-hb<=cfg['stale_seconds'],last=display(hb,cfg['display_offset']) if hb else 'Aucun signal'))
        day_source={r['day']:r['source'] for r in disconnects['source_by_day']}
        integrity=data_integrity(c,cfg,days,day_source)
        return dict(health=health,date_from=days[0],date_to=days[-1],count=len(signals),page=page,summary=summary,disconnects=disconnects,
          core_metrics=disconnect_metric_snapshot(disconnects),common_filters=public_filter_contract(common_filters),
          rows=signals[page*100:(page+1)*100],coverage=provenance,call_coverage=call_cov,integrity=integrity,
          categories=[dict(key=k,label=TECH_LABELS[k],value=n) for k,n in counts.most_common()],
          daily=[dict(label=d,value=daily[d]) for d in days],
          agents=[dict(key=k[0],label=k[1],value=v) for k,v in agents.most_common(10)],config=cfg,
          admin_groups=filter_catalog(),available_agents=build_agent_roster(names,admin_directory),admin_directory_available=admin_directory['available'],
          excluded_agents_count=len(admin_directory.get('exclusions',set())))

