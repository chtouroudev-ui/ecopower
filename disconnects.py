"""Disconnection incident calculation, clustering and data-integrity checks."""
from collections import Counter, defaultdict
from datetime import datetime, date
import math
from nelyio_time import france_offset_for_day
from agent_directory import (admin_user_for, canonical_admin_key, load_admin_directory,
    support_agent_is_excluded)
from analysis_groups import matches_agent_groups, group_ids_for_agent, group_names_for_agent
from supervision_utils import display, selected_bounds, day_bounds
from live_capture import live_intervals
from support_filters import (MAX_NORMAL_DISCONNECT_SECONDS, _support_excluded_slots,
    _overlaps_support_excluded_slot)
from support_priority import load_priority_policies, evaluate_priority, public_policy_snapshot
from policy_engine import load_policies, policy_snapshot
from declaration_engine import load_declarations, declaration_snapshot
from governance_engine import apply_governance
from support_scoring import (
    build_activity_neighbor_index, compute_agent_score, load_score_config, probable_application_closure, probable_application_closure_candidate, public_score_config,
)

def _merge_disconnect_intervals(rows, tolerance=2.0):
    """Merge overlapping duplicate offline intervals for the same agent.
    Stats.AGENT and ODActions can describe the same disconnection; this keeps
    one technical incident instead of double-counting it.
    """
    grouped={}
    for row in rows:
        agent=str(row.get('agent','')).strip()
        start=float(row.get('start',0));end=float(row.get('end',start))
        if not agent or end<=start:continue
        grouped.setdefault(agent,[]).append((start,end))
    merged=[]
    for agent,items in grouped.items():
        current=None
        for start,end in sorted(items):
            if current is None or start>current[1]+tolerance:
                if current is not None:merged.append(dict(agent=agent,start=current[0],end=current[1]))
                current=[start,end]
            else:current[1]=max(current[1],end)
        if current is not None:merged.append(dict(agent=agent,start=current[0],end=current[1]))
    return merged

def detect_clusters(incidents,cfg,window=120,min_agents=3):
    """Group disconnects that happen close together across several agents.
    A cluster is a strong signal of a shared cause (network, Hermès, site
    power) rather than N separate individual problems. Purely time-bucket
    based: simple and explainable, no guessing beyond 'close in time'.
    """
    buckets={}
    for r in incidents:
        b=int(r['start']//window)
        buckets.setdefault((r['day'],b),[]).append(r)
    clusters=[]
    for (day,b),rows in buckets.items():
        agents={r['agent'] for r in rows if r['agent']}
        if len(agents)>=min_agents:
            start=min(r['start'] for r in rows);end=max(r['end'] for r in rows)
            clusters.append(dict(day=day,bucket=b,start=start,end=end,
                start_text=display(start,cfg['display_offset']),
                agents=sorted(agents,key=str),agent_count=len(agents),
                incident_count=len(rows),lost_seconds=sum(int(r.get('governance_effective_seconds',r['seconds'])) for r in rows)))
    clusters.sort(key=lambda x:(-x['agent_count'],-x['incident_count'],x['start']))
    keys={(x['day'],x['bucket']) for x in clusters}
    for r in incidents:
        r['collective']=(r['day'],int(r['start']//window)) in keys
    return clusters[:15]

def data_integrity(c,cfg,days,day_source):
    """A trust indicator for the period, separate from the incident KPIs.
    Sundays are intentionally excluded from the integrity denominator because
    they are non-working days for the Nelyio support analysis. They remain in
    the selected calendar range, but they cannot lower the coverage score.
    """
    excluded_days=[]
    effective_days=[]
    for day in days:
        try:is_sunday=date.fromisoformat(day).weekday()==6
        except ValueError:is_sunday=False
        if is_sunday:excluded_days.append(day)
        else:effective_days.append(day)
    effective_set=set(effective_days)
    total=len(effective_days)
    export_days=sum(1 for d in effective_days if day_source.get(d)=='export')
    capture_days=sum(1 for d in effective_days if day_source.get(d)=='capture')
    missing_days=sum(1 for d in effective_days if day_source.get(d,'missing')=='missing')
    issues=[];score=100
    if missing_days:
        issues.append(dict(code='missing_days',severity='critical',
            label=f'{missing_days} jour(s) sans aucune source de données',
            detail='Ni export SIMPLIFY2 ni capture exploitable : les incidents de ces jours sont invisibles, pas seulement incertains. Les dimanches sont exclus de ce contrôle.'))
        score-=min(40,missing_days*8)
    if capture_days:
        issues.append(dict(code='capture_only',severity='warning',
            label=f'{capture_days} jour(s) basé(s) uniquement sur la capture provisoire',
            detail='Ces journées n’ont pas encore été confirmées par un export SIMPLIFY2 : les chiffres peuvent encore bouger.'))
        score-=min(20,capture_days*3)
    wrong_offsets=[]
    if effective_days:
        for r in c.execute('SELECT cv.day,i.offset_minutes FROM imports i JOIN coverage cv ON cv.import_id=i.id WHERE cv.day BETWEEN ? AND ? ORDER BY cv.day',(effective_days[0],effective_days[-1])):
            if r['day'] not in effective_set:continue
            expected=france_offset_for_day(r['day'])
            if r['offset_minutes'] is not None and int(r['offset_minutes'])!=expected:
                wrong_offsets.append((r['day'],int(r['offset_minutes']),expected))
    if wrong_offsets:
        preview=', '.join(f'{d}: UTC{actual/60:+g} au lieu de UTC{expected/60:+g}' for d,actual,expected in wrong_offsets[:5])
        issues.append(dict(code='wrong_import_offset',severity='critical',
            label=f'{len(wrong_offsets)} jour(s) importe(s) avec un fuseau source inattendu',
            detail=preview+'. Le fuseau d affichage reste Europe/Paris automatique ; verifier uniquement le fuseau ActionDate choisi a l import.'))
        score-=25
    # Capture gaps are counted only for their overlap with non-Sunday days.
    gap_count=0;gap_seconds=0
    if effective_days:
        active_bounds=[day_bounds(day,cfg,work=False) for day in effective_days]
        a=min(x[0] for x in active_bounds);b=max(x[1] for x in active_bounds)
        points={}
        for r in c.execute('SELECT source,stamp FROM health_points WHERE stamp>=? AND stamp<? ORDER BY source,stamp',(a,b)):
            points.setdefault(r['source'],[]).append(r['stamp'])
        for source,ps in points.items():
            for x,y in zip(ps,ps[1:]):
                if y-x<=cfg['stale_seconds']:continue
                overlap=sum(max(0,min(y,db)-max(x,da)) for da,db in active_bounds)
                if overlap>0:gap_count+=1;gap_seconds+=overlap
    if gap_count:
        mins=round(gap_seconds/60,1)
        issues.append(dict(code='capture_gaps',severity='warning',
            label=f'{gap_count} coupure(s) de capture détectée(s) (~{mins} min cumulées)',
            detail='Le service de capture a cessé d’envoyer des signaux pendant ces intervalles. Seules les portions situées hors dimanche sont comptabilisées.'))
        score-=min(15,gap_count*2)
    invalid=0
    if effective_days:
        placeholders=','.join('?' for _ in effective_days)
        query=('SELECT COUNT(*) FROM phone_calls WHERE import_id IN '
               f'(SELECT import_id FROM coverage WHERE day IN ({placeholders})) '
               'AND (duration<0 OR conversation<0 OR wait<0)')
        invalid=c.execute(query,tuple(effective_days)).fetchone()[0]
    if invalid:
        issues.append(dict(code='invalid_durations',severity='warning',
            label=f'{invalid} ligne(s) d’appel avec une durée négative dans l’export',
            detail='Déjà exclues des moyennes de conversation, mais leur présence dans le fichier source mérite un signalement si ça se répète.'))
        score-=min(15,invalid)
    now_ts=datetime.now().timestamp()
    stale_active=[dict(h) for h in c.execute('SELECT * FROM health') if not (0<=now_ts-(h['heartbeat'] or 0)<=cfg['stale_seconds'])]
    if capture_days and stale_active and effective_days and effective_days[-1]>=display(now_ts,cfg['display_offset'])[:10]:
        issues.append(dict(code='stale_capture',severity='critical' if missing_days else 'warning',
            label=f'{len(stale_active)} source(s) de capture actuellement silencieuse(s)',
            detail='La période sélectionnée inclut aujourd’hui et ces collecteurs ne remontent plus de signal en ce moment.'))
        score-=10
    score=max(0,min(100,round(score)))
    applicable=bool(total)
    label=('Non applicable' if not applicable else ('Fiable' if score>=85 else ('À vérifier' if score>=60 else 'Peu fiable')))
    return dict(score=score,label=label,total_days=total,selected_days=len(days),export_days=export_days,capture_days=capture_days,
        missing_days=missing_days,excluded_sundays=len(excluded_days),excluded_days=excluded_days,applicable=applicable,issues=issues)

def _compact_public_event(row):
    """Return only fields used by the interactive Support UI.

    Governance engines attach large nested decision contracts to every event.
    Those contracts are useful for detailed reports/audits but made the normal
    Support response several megabytes. Keep interactive payloads lean.
    """
    keep = (
        'agent','name','group_id','group_name','group_ids','group_names',
        'start','end','seconds','during_call','source','day','critical',
        'start_text','end_text','hour','call_id','indice','ani','dnis','campaign',
        'event_class','event_label','classification_reason','collective',
        'anomaly_type','reason','detail','policy_applied','policy_reason',
        'declaration_applied','declaration_reason','governance_exclude_statistics',
    )
    return {k: row.get(k) for k in keep if k in row}


def _nearest_phone_context(c, import_id, agent, stamp):
    """Find call metadata only for disconnects that need it.

    V60.1 loaded every ODCalls row for every selected day just to enrich a
    handful of disconnects. Cost is now proportional to disconnect count.
    """
    candidates = {}
    params=(int(import_id), str(agent), float(stamp)+5.0)
    for column in ('first_agent','last_agent'):
        sql=("SELECT call_id,indice,ani,dnis,campaign,start,duration,conversation,wait "
             "FROM phone_calls WHERE import_id=? AND "+column+"=? AND start<=? "
             "ORDER BY start DESC LIMIT 24")
        for r in c.execute(sql, params):
            d=dict(r)
            span=max(float(d.get('duration') or 0),float(d.get('conversation') or 0),float(d.get('wait') or 0),1.0)
            d['end']=float(d['start'])+span
            if float(d['start'])-5.0 <= stamp <= d['end']+5.0:
                candidates[str(d.get('call_id') or '')]=d
    if not candidates:
        return None
    return min(candidates.values(), key=lambda x: abs(float(x['start'])-stamp))


def disconnect_statistics(c,qs,cfg,days,cov,names,admin_directory=None,*,priority_policies=None,score_config=None,policy_module="support",generic_policies=None,declarations=None):
    """Technical disconnect KPIs inspired by Hermes Stats Supervision V2.
    One day uses one source: authoritative export when available, otherwise
    continuous live capture. The returned dataset is deliberately detailed so
    the helpdesk can move from a KPI to the exact incident, agent and call.
    """
    get=lambda k,d='':qs.get(k,[d])[0]
    source_filter=get('source').strip();term=get('agent').strip().lower()
    group_filters={str(x).strip() for x in qs.get('group',[]) if str(x).strip()}
    include_agents={canonical_admin_key(x) for x in qs.get('include_agent',[]) if canonical_admin_key(x)}
    exclude_agents={canonical_admin_key(x) for x in qs.get('exclude_agent',[]) if canonical_admin_key(x)}
    call_scope=get('call_scope','all').strip().lower() or 'all'
    if call_scope not in ('all','during','outside'):raise ValueError('Filtre de contexte de déconnexion invalide.')
    try:min_disconnect=max(0.0,min(3600.0,float(get('min_disconnect','0') or 0)))
    except ValueError:raise ValueError('Durée minimum de déconnexion invalide.')
    excluded_slots=_support_excluded_slots(qs)
    excluded_log_counts=Counter()
    if admin_directory is None:admin_directory=load_admin_directory()
    admin_users=admin_directory['users']
    agent_meta={}
    def meta(agent):
        if agent not in agent_meta:
            user=admin_user_for(agent,admin_users)
            agent_meta[agent]=(support_agent_is_excluded(agent,admin_directory),user,canonical_admin_key(agent))
        return agent_meta[agent]
    incidents=[];anomalies=[];day_source={};worked_days_by_agent=defaultdict(set);clock=datetime.now().timestamp()
    if score_config is None:score_config=load_score_config()
    for day in days:
        a,b=selected_bounds(day,cfg,qs,'1');ref=cov.get(day)
        use_export=bool(ref) and source_filter!='capture'
        use_capture=(not use_export) and source_filter!='export'
        rows=[];call_ranges={};call_marks=[];source='missing'
        activity_index=None
        if use_export:
            source='export'
            for wr in c.execute("SELECT DISTINCT agent FROM activities WHERE import_id=? AND start<? AND end>? AND agent<>''",(ref,b,a)):
                worked_days_by_agent[str(wr['agent'])].add(day)
            raw=[dict(r) for r in c.execute("SELECT agent,start,end FROM activities WHERE import_id=? AND kind='offline' AND start<? AND end>?",(ref,b,a))]
            rows=_merge_disconnect_intervals([dict(agent=r['agent'],start=max(a,r['start']),end=min(b,r['end'])) for r in raw])
            for r in c.execute("SELECT agent,start,end FROM activities WHERE import_id=? AND kind='call' AND start<? AND end>?",(ref,b,a)):
                call_ranges.setdefault(r['agent'],[]).append((r['start'],r['end']))
            # V60.4: replace two SQL statements per lunch-like disconnect with
            # at most one bounded neighbor query for the whole day.
            candidate_rows=[]
            for inc in rows:
                seconds=max(1,int(round(max(0.0,float(inc['end']-inc['start'])))))
                probe=dict(agent=inc['agent'],start=inc['start'],end=inc['end'],seconds=seconds,during_call=False)
                if probable_application_closure_candidate(probe,score_config,validated_config=True):
                    candidate_rows.append(probe)
            if candidate_rows:
                tolerance=float(score_config.get('probable_closure_activity_tolerance_minutes') or 0)*60.0
                cand_agents=sorted({r['agent'] for r in candidate_rows if r.get('agent')})
                if cand_agents:
                    marks=','.join('?' for _ in cand_agents)
                    lo=min(float(r['start']) for r in candidate_rows)-tolerance
                    hi=max(float(r['end']) for r in candidate_rows)+tolerance
                    neighbor_rows=[dict(r) for r in c.execute(
                        "SELECT agent,start,end,kind FROM activities WHERE import_id=? AND kind<>'offline' AND agent IN ("+marks+") AND start<=? AND end>=?",
                        [ref]+cand_agents+[hi,lo])]
                    activity_index=build_activity_neighbor_index(neighbor_rows)
        elif use_capture:
            live=live_intervals(c,a,b,cfg,clock)
            for wr in live:
                if str(wr.get('agent') or '').strip():worked_days_by_agent[str(wr['agent'])].add(day)
            rows=_merge_disconnect_intervals([dict(agent=r['agent'],start=r['start'],end=r['end']) for r in live if r['kind']=='offline' and r['end']>r['start']])
            call_marks=[dict(r) for r in c.execute("SELECT agent,start FROM technical_signals WHERE category='disconnect_call' AND start>=? AND start<?",(a-15,b+15))]
            if rows or any(a<=r['start']<b for r in call_marks):source='capture'
        day_source[day]=source
        for inc in rows:
            excluded,admin_user,agent_key=meta(inc['agent'])
            if excluded:continue
            admin_name=(admin_user or {}).get('display_name') or names.get(inc['agent'],'')
            if term and term not in (inc['agent']+' '+admin_name).lower():continue
            if include_agents and agent_key not in include_agents:continue
            if exclude_agents and agent_key in exclude_agents:continue
            if group_filters and not matches_agent_groups(inc['agent'],group_filters):continue
            if source=='export':
                # A disconnect beginning while an exported call activity is still
                # active is considered "during call". A 2 s tolerance absorbs
                # timestamp rounding between export files.
                during=any(cs-2<=inc['start']<=ce+2 for cs,ce in call_ranges.get(inc['agent'],[]))
            else:
                during=any(m['agent']==inc['agent'] and abs(m['start']-inc['start'])<=15 for m in call_marks)
            if call_scope=='during' and not during:continue
            if call_scope=='outside' and during:continue
            seconds_raw=max(0.0,float(inc['end']-inc['start']))
            if seconds_raw<=0:continue
            seconds=max(1,int(round(seconds_raw)))
            start_text=display(inc['start'],cfg['display_offset']);end_text=display(inc['end'],cfg['display_offset'])
            analysis_ids=group_ids_for_agent(inc['agent']);analysis_names=group_names_for_agent(inc['agent'])
            row=dict(agent=inc['agent'],name=admin_name or inc['agent'],group_id=(analysis_ids[0] if len(analysis_ids)==1 else None),group_name=(analysis_names[0] if len(analysis_names)==1 else ''),group_ids=analysis_ids,group_names=analysis_names,start=inc['start'],end=inc['end'],seconds=seconds,
                during_call=bool(during),source=source,day=day,critical=seconds>cfg['offline_seconds'],start_text=start_text,end_text=end_text,
                hour=start_text[11:13]+'h',call_id='',indice='',ani='',dnis='',campaign='')
            if during and source=='export' and ref:
                call=_nearest_phone_context(c,ref,inc['agent'],inc['start'])
                if call:
                    for key in ['call_id','indice','ani','dnis','campaign']:
                        row[key]=call.get(key,'') or ''
            # Apply selected log-exclusion windows before classifying the row.
            # A row is removed if ANY part of the disconnect overlaps the selected
            # window. This applies to normal disconnects and >1 h anomalies alike.
            if _overlaps_support_excluded_slot(inc['start'],inc['end'],cfg,excluded_slots):
                excluded_log_counts['disconnects']+=1
                excluded_log_counts['during_call']+=int(bool(during))
                if seconds_raw>MAX_NORMAL_DISCONNECT_SECONDS:excluded_log_counts['anomalies']+=1
                else:excluded_log_counts['normal_disconnects']+=1
                continue
            # A gap above one hour is not treated as a normal technical
            # disconnect: it often represents a session left open, a long
            # break, a workstation shutdown or another data-quality issue.
            # Keep it visible in a dedicated anomaly list only when it is not
            # inside one of the selected excluded break windows.
            if seconds_raw>MAX_NORMAL_DISCONNECT_SECONDS:
                anomaly=dict(row)
                anomaly.update(anomaly_type='disconnect_over_1h',reason='Déconnexion supérieure à 1 heure',
                    detail='Exclue automatiquement des statistiques normales. À vérifier : session, pause longue, arrêt poste ou donnée exportée incohérente.')
                anomalies.append(anomaly)
                continue
            if seconds_raw<min_disconnect:continue
            row['event_class']='technical_disconnect'
            row['event_label']='Déconnexion technique'
            row['classification_reason']='Déconnexion normale à qualifier techniquement.'
            if source=='export' and ref:
                probable,reason=probable_application_closure(c,ref,row,score_config,validated_config=True,activity_index=activity_index)
                if probable:
                    row['event_class']='probable_closure'
                    row['event_label']='Fermeture application / pause probable'
                    row['classification_reason']=reason
            row['collective']=False
            incidents.append(row)
    # Phase D: governance is evaluated before collective detection. Generic
    # Policies run first, then punctual Declarations. Raw events are retained
    # with both decisions attached; only the final governance flags affect KPIs.
    if generic_policies is None: generic_policies=load_policies()
    if declarations is None:
        declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
    incidents=apply_governance(incidents,policy_module,generic_policies,declarations)
    anomalies=apply_governance(anomalies,policy_module,generic_policies,declarations)
    # Les fermetures/pause probables restent visibles mais ne servent pas à
    # fabriquer artificiellement une panne collective.
    technical_for_clusters=[r for r in incidents if r.get('event_class')=='technical_disconnect' and not r.get('governance_exclude_statistics')]
    clusters=detect_clusters(
        technical_for_clusters,cfg,
        window=score_config["collective_window_seconds"],
        min_agents=score_config["collective_min_agents"],
    )
    for r in technical_for_clusters:
        if r.get('collective'):
            r['event_class']='collective_incident'
            r['event_label']='Incident collectif'
            r['classification_reason']=(f"Incident collectif : au moins {score_config['collective_min_agents']} agents distincts dans une fenêtre de {score_config['collective_window_seconds']} s.")
    selected_days=max(1,len(days))
    covered_days=max(1,sum(day_source.get(day)!='missing' for day in days))
    if priority_policies is None:priority_policies=load_priority_policies()
    by_agent={}
    def ensure_agent(row):
        agent=str(row.get('agent') or '')
        st=by_agent.get(agent)
        if st is None:
            st=dict(agent=agent,name=row.get('name') or agent,group_id=row.get('group_id'),group_name=row.get('group_name',''),
                raw_events=[],anomaly_count=0,first_start=None,last_start=None,last_text='')
            by_agent[agent]=st
        return st
    for r in incidents:
        st=ensure_agent(r);st['raw_events'].append(r)
        if st['first_start'] is None or r['start']<st['first_start']:st['first_start']=r['start']
        if st['last_start'] is None or r['start']>st['last_start']:st['last_start']=r['start'];st['last_text']=r['start_text']
    for r in anomalies:
        st=ensure_agent(r);st['anomaly_count']+=1
        if st['first_start'] is None or r['start']<st['first_start']:st['first_start']=r['start']
        if st['last_start'] is None or r['start']>st['last_start']:st['last_start']=r['start'];st['last_text']=r['start_text']

    agent_stats=[]
    for st in by_agent.values():
        raw_events=st['raw_events']
        technical=[r for r in raw_events if r.get('event_class')=='technical_disconnect' and not r.get('governance_exclude_statistics')]
        collective=[r for r in raw_events if r.get('event_class')=='collective_incident' and not r.get('governance_exclude_statistics')]
        probable=[r for r in raw_events if r.get('event_class')=='probable_closure']
        policy_excluded=[r for r in raw_events if r.get('policy_exclude_statistics')]
        declaration_excluded=[r for r in raw_events if r.get('declaration_exclude_statistics')]
        governance_excluded=[r for r in raw_events if r.get('governance_exclude_statistics')]
        score_technical=[r for r in technical if not r.get('governance_exclude_score')]
        durations=sorted(r['seconds'] for r in technical)
        days_affected={r['day'] for r in technical}
        sources=Counter(r['source'] for r in technical)
        hours=Counter(r['hour'] for r in technical)
        st['raw_deco']=len(raw_events)
        st['raw_lost_seconds']=sum(r['seconds'] for r in raw_events)
        st['deco']=len(technical)
        st['deco_call']=sum(int(bool(r['during_call'])) for r in technical)
        st['critical_count']=sum(int(bool(r['critical'])) for r in technical)
        st['lost_seconds']=sum(int(r.get('governance_effective_seconds',r['seconds'])) for r in technical)
        st['policy_excluded_count']=len(policy_excluded)
        st['policy_authorized_count']=sum(int(bool(r.get('policy_authorized'))) for r in raw_events)
        st['declaration_excluded_count']=len(declaration_excluded)
        st['declaration_applied_count']=sum(int(bool(r.get('declaration_applied'))) for r in raw_events)
        st['declaration_authorized_count']=sum(int(bool(r.get('declaration_authorized'))) for r in raw_events)
        st['governance_excluded_count']=len(governance_excluded)
        st['max_seconds']=max(durations,default=0)
        st['avg_seconds']=round(sum(durations)/len(durations)) if durations else 0
        st['median_seconds']=round((durations[(len(durations)-1)//2]+durations[len(durations)//2])/2) if durations else 0
        st['call_percent']=round(st['deco_call']*100/st['deco'],1) if st['deco'] else 0
        st['critical_percent']=round(st['critical_count']*100/st['deco'],1) if st['deco'] else 0
        st['days_affected']=len(days_affected)
        st['export_count']=sources.get('export',0);st['capture_count']=sources.get('capture',0)
        st['collective_count']=len(collective)
        st['probable_closure_count']=len(probable)
        st['worked_days']=len(worked_days_by_agent.get(st['agent'],set()))

        score_data=compute_agent_score(
            score_technical,st['worked_days'],score_config,
            probable_closure_count=len(probable),collective_count=len(collective))
        st.update(score_data)
        # Backward-compatible field name used by exports/UI before v41.
        st['risk_score']=st['technical_score']
        # A Policy may keep an event visible in statistics while removing its
        # impact from Support prioritization. Build a dedicated policy-neutral
        # view for the priority engine instead of mutating the displayed KPIs.
        priority_view=dict(st)
        priority_view['deco']=len(score_technical)
        priority_view['deco_call']=sum(int(bool(r.get('during_call'))) for r in score_technical)
        priority_view['lost_seconds']=sum(int(r.get('governance_score_effective_seconds',r.get('governance_effective_seconds',r.get('seconds') or 0))) for r in score_technical)
        priority_view['days_affected']=len({r.get('day') for r in score_technical if r.get('day')})
        priority_view['call_percent']=round(priority_view['deco_call']*100/priority_view['deco'],1) if priority_view['deco'] else 0
        st['priority'],priority_metrics,priority_reasons=evaluate_priority(
            priority_view,selected_days,covered_days,priority_policies)
        st.update(priority_metrics)
        st['priority_reasons']=priority_reasons

        special=[]
        if st['anomaly_count']:
            special.append(dict(code='anomaly',label='ANOMALIE',count=st['anomaly_count']))
        if st['collective_count']:
            special.append(dict(code='collective',label='INCIDENT COLLECTIF',count=st['collective_count']))
        if st['probable_closure_count']:
            special.append(dict(code='probable_closure',label='FERMETURE / PAUSE PROBABLE',count=st['probable_closure_count']))
        if selected_days>=3 and st['worked_days']<2 and (st['deco'] or st['anomaly_count']):
            special.append(dict(code='insufficient',label='DONNÉES INSUFFISANTES',count=st['worked_days']))
        st['special_statuses']=special

        top_hour,top_hour_n=(hours.most_common(1) or [('',0)])[0]
        collective_share=st['collective_count']/max(1,st['raw_deco'])
        if st['collective_count'] and (collective_share>=0.5 or not technical):
            st['likely_cause']='Incident collectif probable (réseau/Hermès/infrastructure)'
            st['suggested_action']=f"{st['collective_count']} coupure(s) coïncident avec d’autres agents. Elles restent visibles mais ne pénalisent pas le score individuel par défaut."
            st['diagnosis_code']='collectif'
        elif st['probable_closure_count'] and not technical:
            st['likely_cause']='Fermeture application / pause probable'
            st['suggested_action']='Événement conservé pour traçabilité mais exclu du score technique par défaut. Vérifier manuellement si le contexte ne correspond pas à une pause.'
            st['diagnosis_code']='fermeture'
        elif st.get('bursts_30m',0)>=1:
            st['likely_cause']='Déconnexions techniques répétitives'
            st['suggested_action']=f"{st['bursts_30m']} série(s) rapprochée(s) détectée(s). Contrôler réseau/VPN, navigateur WebRTC et poste avant de conclure à un incident isolé."
            st['diagnosis_code']='repetition'
        elif top_hour_n>=3 and st['deco'] and top_hour_n/st['deco']>=0.6:
            st['likely_cause']=f'Récurrence horaire autour de {top_hour}'
            st['suggested_action']=f"{top_hour_n} coupure(s) techniques sur {st['deco']} se produisent vers {top_hour}. Vérifier tâche planifiée, réseau ou organisation du poste."
            st['diagnosis_code']='horaire'
        elif st['deco_call']>=1 or st['max_seconds']>=cfg['offline_seconds']*10:
            st['likely_cause']='Problème individuel probable (poste, casque ou connexion)'
            st['suggested_action']='Vérifier le poste, le casque, le navigateur/WebRTC et la connexion de l’agent. Les incidents collectifs et fermetures probables sont déjà séparés.'
            st['diagnosis_code']='individuel'
        elif st['anomaly_count'] and not technical:
            st['likely_cause']='Anomalie de durée / session à qualifier'
            st['suggested_action']='La durée > 1 h reste hors score et doit être vérifiée manuellement (session, arrêt poste, fermeture application ou donnée incohérente).'
            st['diagnosis_code']='anomalie'
        else:
            st['likely_cause']='Signal insuffisant pour trancher automatiquement'
            st['suggested_action']='Peu de signaux techniques individuels : conserver en surveillance ou qualifier manuellement selon le contexte.'
            st['diagnosis_code']='indetermine'
        del st['raw_events'];agent_stats.append(st)

    priority_rank={str(p.get('priority')):int(p.get('rank') or 0) for p in priority_policies}
    agent_stats.sort(key=lambda r:(-priority_rank.get(r.get('priority'),0),-r['technical_score'],-r['deco_call'],-r['deco'],r['name']))

    probable_closures=[r for r in incidents if r.get('event_class')=='probable_closure']
    # Raw-vs-corrected reference: the raw KPI population keeps the same technical
    # classification rules but ignores Policies/Declarations. This makes the
    # governance impact explicit without bringing probable application closures
    # back into the technical KPI population.
    raw_technical_kpi_incidents=[r for r in incidents if r.get('event_class')!='probable_closure']
    technical_kpi_incidents=[r for r in raw_technical_kpi_incidents if not r.get('governance_exclude_statistics')]
    individual_technical=[r for r in incidents if r.get('event_class')=='technical_disconnect']
    collective_incidents=[r for r in incidents if r.get('event_class')=='collective_incident']
    total=len(technical_kpi_incidents);call=sum(r['during_call'] for r in technical_kpi_incidents);lost=sum(int(r.get('governance_effective_seconds',r['seconds'])) for r in technical_kpi_incidents);durations=sorted(r['seconds'] for r in technical_kpi_incidents)
    median=round((durations[(len(durations)-1)//2]+durations[len(durations)//2])/2) if durations else 0
    p95=durations[min(len(durations)-1,max(0,math.ceil(len(durations)*.95)-1))] if durations else 0
    active_days=sum(day_source.get(day)!='missing' for day in days)
    raw_total=len(raw_technical_kpi_incidents)
    raw_call=sum(int(bool(r.get('during_call'))) for r in raw_technical_kpi_incidents)
    raw_lost=sum(int(r.get('seconds') or 0) for r in raw_technical_kpi_incidents)
    summary=dict(total_deco=total,total_deco_call=call,total_call_percent=round(call*100/total,1) if total else 0,
        total_lost=lost,raw_total_deco=raw_total,raw_total_deco_call=raw_call,raw_total_lost=raw_lost,
        governance_removed_deco=max(0,raw_total-total),governance_removed_lost=max(0,raw_lost-lost),
        impacted_agents=len(by_agent),technical_impacted_agents=len({r['agent'] for r in technical_kpi_incidents}),
        avg_seconds=round(lost/total) if total else 0,median_seconds=median,p95_seconds=p95,
        max_seconds=max(durations,default=0),critical=sum(r['critical'] for r in technical_kpi_incidents),active_days=active_days,
        incidents_per_active_day=round(total/active_days,2) if active_days else 0,min_disconnect=min_disconnect,
        raw_normal_disconnects=len(incidents),individual_technical_disconnects=len(individual_technical),
        collective_disconnects=len(collective_incidents),probable_closures=len(probable_closures),
        individual_technical_lost=sum(r['seconds'] for r in individual_technical),
        anomalies_over_1h=len(anomalies),excluded_slots=[label for _,_,label in excluded_slots],
        policy_excluded_events=sum(int(bool(r.get('policy_exclude_statistics'))) for r in incidents),
        policy_authorized_events=sum(int(bool(r.get('policy_authorized'))) for r in incidents),
        declaration_applied_events=sum(int(bool(r.get('declaration_applied'))) for r in incidents),
        declaration_excluded_events=sum(int(bool(r.get('declaration_exclude_statistics'))) for r in incidents),
        declaration_authorized_events=sum(int(bool(r.get('declaration_authorized'))) for r in incidents),
        governance_excluded_events=sum(int(bool(r.get('governance_exclude_statistics'))) for r in incidents),
        excluded_logs=dict(disconnects=excluded_log_counts['disconnects'],normal_disconnects=excluded_log_counts['normal_disconnects'],
            anomalies=excluded_log_counts['anomalies'],during_call=excluded_log_counts['during_call']),
        max_normal_disconnect_seconds=MAX_NORMAL_DISCONNECT_SECONDS)
    daily_acc={day:dict(total=0,call=0,lost_seconds=0,critical=0,agents=set()) for day in days}
    hourly_acc=[dict(total=0,call=0,critical=0,lost_seconds=0) for _ in range(24)]
    bands=[0,0,0,0,0]
    for r in technical_kpi_incidents:
        acc=daily_acc[r['day']];acc['total']+=1;acc['call']+=int(bool(r['during_call']));acc['lost_seconds']+=int(r.get('governance_effective_seconds',r['seconds']));acc['critical']+=int(bool(r['critical']));acc['agents'].add(r['agent'])
        try:hour=int(str(r['hour'])[:2])
        except (ValueError,TypeError):hour=-1
        if 0<=hour<24:
            h=hourly_acc[hour];h['total']+=1;h['call']+=int(bool(r['during_call']));h['critical']+=int(bool(r['critical']));h['lost_seconds']+=int(r.get('governance_effective_seconds',r['seconds']))
        seconds=r['seconds']
        if seconds<=10:bands[0]+=1
        elif seconds<=30:bands[1]+=1
        elif seconds<=60:bands[2]+=1
        elif seconds<=300:bands[3]+=1
        else:bands[4]+=1
    daily=[]
    for day in days:
        src=day_source.get(day,'missing');acc=daily_acc[day]
        daily.append(dict(label=day,source=src,total=acc['total'] if src!='missing' else None,call=acc['call'] if src!='missing' else None,
            lost_seconds=acc['lost_seconds'] if src!='missing' else None,critical=acc['critical'] if src!='missing' else None,
            avg_seconds=(round(acc['lost_seconds']/acc['total']) if acc['total'] else (0 if src!='missing' else None)),
            agents=len(acc['agents']) if src!='missing' else None))
    hourly=[dict(label=f'{hour:02d}h',**hourly_acc[hour]) for hour in range(24)]
    duration_bands=[
        dict(label='≤ 10 s',value=bands[0]),
        dict(label='11–30 s',value=bands[1]),
        dict(label='31–60 s',value=bands[2]),
        dict(label='1–5 min',value=bands[3]),
        dict(label='> 5 min',value=bands[4]),
    ]
    longest=sorted(technical_kpi_incidents,key=lambda r:(-r['seconds'],r['start']))[:50]
    recent=sorted(incidents,key=lambda r:(-r['start'],r['agent']))[:500]
    top_days=sorted((r for r in daily if r['total'] is not None),key=lambda r:(-r['total'],-r['lost_seconds'],r['label']))[:10]
    anomalies.sort(key=lambda r:(-r['start'],r['agent']))
    observed_days={}
    for agent,worked in worked_days_by_agent.items():
        excluded,user,key=meta(agent)
        if excluded:continue
        if group_filters and not matches_agent_groups(agent,group_filters):continue
        if include_agents and key not in include_agents:continue
        if key in exclude_agents:continue
        if term and term not in (agent+' '+names.get(agent,agent)).lower():continue
        observed_days[agent]=len(worked)
    compact=str(get('_compact','')).strip()=='1'
    probable_sorted=sorted(probable_closures,key=lambda r:(-r['start'],r['agent']))
    if compact:
        longest=[_compact_public_event(r) for r in longest[:20]]
        recent=[_compact_public_event(r) for r in recent[:200]]
        anomalies_out=[_compact_public_event(r) for r in anomalies[:200]]
        probable_out=[_compact_public_event(r) for r in probable_sorted[:100]]
    else:
        anomalies_out=anomalies[:500]
        probable_out=probable_sorted[:500]
    result=dict(worked_days_by_agent=observed_days,summary=summary,agents=agent_stats,daily=daily,hourly=hourly,duration_bands=duration_bands,longest=longest,recent=recent,top_days=top_days,
        clusters=clusters,anomalies=anomalies_out,probable_closures=probable_out,
        source_by_day=[dict(day=d,source=day_source.get(d,'missing')) for d in days],
        priority_policy=public_policy_snapshot(priority_policies),score_config=public_score_config(score_config),
        generic_policies=policy_snapshot(include_disabled=False),declarations=declaration_snapshot(days[0] if days else None,days[-1] if days else None,include_cancelled=False),policy_module=policy_module)
    if str(get('_include_incidents','')).strip()=='1':
        result['incidents']=incidents
        result['all_anomalies']=anomalies
    return result

