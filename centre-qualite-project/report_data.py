"""Weekly/report dataset preparation; PDF rendering remains in weekly_reports.py."""
from collections import Counter
from datetime import datetime, timedelta
import re, sqlite3, hashlib, json
from error_log import log_unexpected_error
from nelyio_time import today as france_today, display as france_display
import weekly_reports
from supervision_db import connect, config
from agent_directory import (normalize_admin_key, admin_name_for, admin_user_for, build_agent_roster, canonical_admin_key, load_admin_directory, support_agent_is_excluded)
from supervision_utils import date_range, display, selected_bounds, latest_agent_names
from calls import call_rows
from analysis_groups import matches_agent_groups, group_ids_for_agent, group_names_for_agent
from support_filters import TECH_LABELS, _support_excluded_slots, _overlaps_support_excluded_slot
from disconnects import disconnect_statistics, data_integrity
from live_capture import live_intervals
from analytics import _analytics_is_inactive_state, _analytics_latest_devices
from support_priority import load_priority_policies, evaluate_priority, public_policy_snapshot
from support_scoring import load_score_config, compute_agent_score, public_score_config
from metrics_engine import disconnect_metric_snapshot
from unified_filters import normalize_filters, public_filter_contract
from governance_engine import apply_event_governance, governed_visible_events
from policy_engine import load_policies
from declaration_engine import load_declarations

REPORT_MAX_DAYS = 30
REPORT_DETAIL_DEFAULT_PAGE_SIZE = 50
REPORT_DETAIL_MAX_PAGE_SIZE = 200

def _report_reference_day():
    with connect() as c:
        row=c.execute('SELECT MAX(day) FROM coverage').fetchone()
    return str(row[0]) if row and row[0] else france_today()

def _report_parse_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value or '')):
        raise ValueError('Dates invalides. Format attendu : AAAA-MM-JJ.')
    try:return datetime.strptime(value,'%Y-%m-%d')
    except ValueError as exc:raise ValueError('Date inexistante. Vérifier le jour, le mois et l’année.') from exc


def _report_get(qs,key,default=''):
    return str(qs.get(key,[default])[0] or default).strip()

def _report_values(qs,key):
    out=[]
    for raw in qs.get(key,[]):
        for value in str(raw or '').split(','):
            value=value.strip()
            if value and value not in out:out.append(value)
    return out

def _report_bool(qs,key,default=False):
    raw=_report_get(qs,key,'1' if default else '0').lower()
    return raw in ('1','true','yes','on')

def _report_week(qs):
    raw=_report_get(qs,'week')
    if not raw:
        latest=''
        try:
            with connect() as c:
                row=c.execute('SELECT MAX(day) FROM coverage').fetchone();latest=str(row[0] or '') if row else ''
        except sqlite3.Error:
            log_unexpected_error('supervision._report_week.L1594')
            latest=''
        reference=datetime.strptime(latest,'%Y-%m-%d').date() if latest else datetime.strptime(france_today(),'%Y-%m-%d').date()
        iso=reference.isocalendar();raw=f'{iso.year}-W{iso.week:02d}'
    m=re.fullmatch(r'(20\d{2})-W(\d{2})',raw)
    if not m:raise ValueError('Semaine invalide. Format attendu : AAAA-Wxx.')
    year=int(m.group(1));week=int(m.group(2))
    try:start=datetime.fromisocalendar(year,week,1)
    except ValueError as exc:raise ValueError('Semaine ISO invalide.') from exc
    end=start+timedelta(days=6)
    return raw,start.strftime('%Y-%m-%d'),end.strftime('%Y-%m-%d')

def _report_period(qs):
    mode=_report_get(qs,'period_mode','week').lower() or 'week'
    if mode not in ('week','custom','last30'):raise ValueError('Type de période invalide.')
    if mode=='week':
        week,date_from,date_to=_report_week(qs)
        iso_week=int(week.split('W',1)[1]);year=week[:4]
        return dict(mode='week',week=week,date_from=date_from,date_to=date_to,
            label=f'Semaine {iso_week} / {year}',token=week,days=7)
    if mode=='last30':
        b=_report_parse_date(_report_get(qs,'date_to') or _report_reference_day())
        a=b-timedelta(days=REPORT_MAX_DAYS-1)
        date_from=a.strftime('%Y-%m-%d');date_to=b.strftime('%Y-%m-%d')
    else:
        date_from=_report_get(qs,'date_from');date_to=_report_get(qs,'date_to')
        if not date_from or not date_to:raise ValueError('Choisir une date de début et une date de fin.')
        a=_report_parse_date(date_from);b=_report_parse_date(date_to)
    length=(b-a).days+1
    if length<1:raise ValueError('La date de fin doit être le même jour ou après la date de début.')
    if length>REPORT_MAX_DAYS:raise ValueError(f'Un rapport PDF est limité à {REPORT_MAX_DAYS} jours maximum, dates incluses ({length} jours sélectionnés).')
    return dict(mode=mode,week='',date_from=date_from,date_to=date_to,
        label='30 jours glissants' if mode=='last30' else f'Période personnalisée - {length} jour(s)',
        token=f'{date_from}_au_{date_to}',days=length)

def _report_call_governance(row,cfg,policies,declarations):
    """Return the strongest governance decision for either handling agent."""
    span=max(float(row.get('duration') or 0),float(row.get('conversation') or 0),float(row.get('wait') or 0),1.0)
    start=float(row.get('start') or 0);start_text=display(start,cfg['display_offset'])
    candidates=[
        (row.get('first_agent'),row.get('first_group_id'),row.get('first_group_name')),
        (row.get('last_agent'),row.get('last_group_id'),row.get('last_group_name')),
    ]
    decisions=[];seen=set()
    for agent,gid,gname in candidates:
        agent=str(agent or '').strip()
        key=(agent,str(gid or ''))
        if key in seen:continue
        seen.add(key)
        evt=dict(agent='' if agent=='0' else agent,group_id=gid,group_name=gname or '',start=start,start_text=start_text,day=start_text[:10],hour=start_text[11:16],seconds=max(1,int(round(span))),event_label='Appel ODCalls')
        decisions.append(apply_event_governance(evt,'reports',policies,declarations))
    if not decisions:
        evt=dict(agent='',group_id=None,group_name='',start=start,start_text=start_text,day=start_text[:10],hour=start_text[11:16],seconds=max(1,int(round(span))),event_label='Appel ODCalls')
        decisions=[apply_event_governance(evt,'reports',policies,declarations)]
    return dict(
        exclude_statistics=any(x.get('governance_exclude_statistics') for x in decisions),
        reason=' · '.join(dict.fromkeys(str(x.get('governance_reason') or '') for x in decisions if x.get('governance_reason'))),
    )


def _report_dataset(c,report_qs,cfg,days,names,source,groups,include_agents,exclude_agents,call_issue,priority_policies=None,score_config=None):
    """Build one report period using exactly the same filters for all sections."""
    cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
    generic_policies=load_policies()
    declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
    disconnects=disconnect_statistics(c,report_qs,cfg,days,cov,names,priority_policies=priority_policies,score_config=score_config,policy_module="reports",generic_policies=generic_policies,declarations=declarations)
    day_source={r['day']:r['source'] for r in disconnects['source_by_day']}
    integrity=data_integrity(c,cfg,days,day_source)

    # ODCalls exist only in exports. Keep their scope aligned with the technical
    # disconnect filters so the executive comparison is genuinely like-for-like.
    call_rows_data=[];call_coverage=[dict(day=d,source='missing') for d in days]
    excluded_calls_by_slot=0
    excluded_calls_by_governance=0
    if source!='capture':
        call_qs=dict(report_qs)
        if call_issue!='all':call_qs['call_issue']=[call_issue]
        call_rows_data,call_coverage=call_rows(c,call_qs,cfg,days)
        selected_groups={str(x) for x in groups}
        selected_include={canonical_admin_key(x) for x in include_agents if canonical_admin_key(x)}
        selected_exclude={canonical_admin_key(x) for x in exclude_agents if canonical_admin_key(x)}
        slots=_support_excluded_slots(report_qs)
        filtered_calls=[]
        for r in call_rows_data:
            agents={canonical_admin_key(r.get('first_agent')),canonical_admin_key(r.get('last_agent'))}
            agents={x for x in agents if x}
            if selected_groups and not any(matches_agent_groups(a,selected_groups) for a in agents):continue
            if selected_include and not (selected_include & agents):continue
            if selected_exclude and (selected_exclude & agents):continue
            span=max(float(r.get('duration') or 0),float(r.get('conversation') or 0),float(r.get('wait') or 0),1.0)
            call_end=float(r.get('start') or 0)+span
            if slots and _overlaps_support_excluded_slot(r.get('start'),call_end,cfg,slots):
                excluded_calls_by_slot+=1
                continue
            governance=_report_call_governance(r,cfg,generic_policies,declarations)
            if governance.get('exclude_statistics'):
                excluded_calls_by_governance+=1
                r['governance_reason']=governance.get('reason','')
                continue
            filtered_calls.append(r)
        call_rows_data=filtered_calls
    n=len(call_rows_data);conversation=[r['conversation'] for r in call_rows_data if r.get('conversation',0)>0]
    calls_summary=dict(records=n,indices=len({r['indice'] for r in call_rows_data if r.get('indice')}),
        invalid_durations=sum(any(r.get(k,0)<0 for k in ['duration','conversation','wait']) for r in call_rows_data),
        end_codes=sum(r.get('end_reason') not in ('','0') for r in call_rows_data),
        short=sum(0<r.get('conversation',0)<=10 for r in call_rows_data),
        abandons=sum(bool(r.get('abandon')) for r in call_rows_data),no_agent=sum(bool(r.get('no_agent')) for r in call_rows_data),
        conversation=sum(conversation),average_conversation=round(sum(conversation)/len(conversation),1) if conversation else None,
        excluded_by_time=excluded_calls_by_slot,excluded_by_governance=excluded_calls_by_governance,
        covered_days=sum(1 for r in call_coverage if r.get('source')=='export'))
    reasons=Counter(r.get('end_reason') or '0' for r in call_rows_data if (r.get('end_reason') or '0') not in ('','0'))
    top_end_reasons=[dict(label=k,value=v) for k,v in reasons.most_common(12)]
    return dict(disconnects=disconnects,core_metrics=disconnect_metric_snapshot(disconnects),integrity=integrity,calls_summary=calls_summary,
        top_end_reasons=top_end_reasons,call_coverage=call_coverage)

def _report_delta_status(current,previous,lower_is_better=True):
    if current is None or previous is None:return dict(delta_pct=None,status='unknown')
    current=float(current);previous=float(previous)
    if previous==0:
        if current==0:return dict(delta_pct=0.0,status='stable')
        return dict(delta_pct=None,status='degraded' if lower_is_better else 'improved')
    delta=(current-previous)*100.0/previous
    if abs(delta)<5:status='stable'
    elif (delta<0 and lower_is_better) or (delta>0 and not lower_is_better):status='improved'
    else:status='degraded'
    return dict(delta_pct=round(delta,1),status=status)

def _report_comparison(current,previous,days,previous_days,period,enabled=True):
    if not enabled:return dict(enabled=False,available=False)
    ds=current.get('disconnects',{}).get('summary',{});pds=previous.get('disconnects',{}).get('summary',{})
    cs=current.get('calls_summary',{});pcs=previous.get('calls_summary',{})
    sig=current.get('signals',{}).get('summary',{});psig=previous.get('signals',{}).get('summary',{})
    active=max(0,int(ds.get('active_days') or 0));prev_active=max(0,int(pds.get('active_days') or 0))
    available=prev_active>0
    prev_start=datetime.strptime(previous_days[0],'%Y-%m-%d');prev_end=datetime.strptime(previous_days[-1],'%Y-%m-%d')
    if period.get('mode')=='week':
        iso=prev_start.date().isocalendar();previous_label=f'Semaine {iso.week} / {iso.year}'
    else:
        previous_label=f"{prev_start.strftime('%d/%m/%Y')} au {prev_end.strftime('%d/%m/%Y')}"
    if not available:
        return dict(enabled=True,available=False,label=previous_label,date_from=previous_days[0],date_to=previous_days[-1],
            verdict=dict(code='unavailable',label='Comparaison indisponible',detail='Aucune journée exploitable sur la période précédente avec les mêmes filtres.'),metrics=[],daily=[])

    per_day=lambda value,count: round(float(value or 0)/count,2) if count else None
    metrics=[]
    def add_metric(key,label,current_value,previous_value,unit,lower_is_better=True,decimals=1):
        state=_report_delta_status(current_value,previous_value,lower_is_better)
        metrics.append(dict(key=key,label=label,current=round(float(current_value or 0),decimals),previous=round(float(previous_value or 0),decimals),
            unit=unit,lower_is_better=lower_is_better,delta_pct=state['delta_pct'],status=state['status']))

    add_metric('lost_minutes_per_day','Temps de coupure / jour',per_day(float(ds.get('total_lost') or 0)/60,active),per_day(float(pds.get('total_lost') or 0)/60,prev_active),' min / jour',True,1)
    add_metric('disconnects_per_day','Déconnexions / jour couvert',per_day(ds.get('total_deco'),active),per_day(pds.get('total_deco'),prev_active),' / jour',True,2)
    add_metric('during_call_per_day','Coupures en appel / jour',per_day(ds.get('total_deco_call'),active),per_day(pds.get('total_deco_call'),prev_active),' / jour',True,2)
    add_metric('anomalies_per_day','Anomalies > 1 h / jour',per_day(ds.get('anomalies_over_1h'),active),per_day(pds.get('anomalies_over_1h'),prev_active),' / jour',True,2)
    add_metric('inactive_minutes_per_day','Contexte inactif / jour',per_day(float(sig.get('inactive_seconds') or 0)/60,active),per_day(float(psig.get('inactive_seconds') or 0)/60,prev_active),' min / jour',True,1)
    add_metric('inactive_events_per_day','Contextes inactifs / jour',per_day(sig.get('inactive_count'),active),per_day(psig.get('inactive_count'),prev_active),' / jour',True,2)
    if int(cs.get('records') or 0)>0 and int(pcs.get('records') or 0)>0:
        add_metric('short_per_1000','Appels courts / 1 000 appels',1000*float(cs.get('short') or 0)/float(cs.get('records') or 1),1000*float(pcs.get('short') or 0)/float(pcs.get('records') or 1),' / 1 000',True,1)

    scored=[m for m in metrics if m['status'] in ('improved','degraded','stable')]
    counts=Counter(m['status'] for m in scored)
    if counts['improved']>counts['degraded']:
        code='improved';label='Amélioration'
    elif counts['degraded']>counts['improved']:
        code='degraded';label='Dégradation'
    else:
        code='stable';label='Stable / mixte'
    current_score=int(current.get('integrity',{}).get('score') or 0);previous_score=int(previous.get('integrity',{}).get('score') or 0)
    detail=f"{counts['improved']} indicateur(s) en amélioration, {counts['degraded']} en dégradation et {counts['stable']} stable(s), ramenés par jour couvert quand nécessaire."
    if current_score<85 or previous_score<85:
        detail+=' La couverture de données impose une lecture prudente.'

    weekdays=['Lun','Mar','Mer','Jeu','Ven','Sam','Dim']
    cur_daily=current.get('disconnects',{}).get('daily',[]);prev_daily=previous.get('disconnects',{}).get('daily',[])
    cur_sig={r.get('label'):r for r in current.get('signals',{}).get('daily',[])};prev_sig={r.get('label'):r for r in previous.get('signals',{}).get('daily',[])}
    daily=[]
    for i,day in enumerate(days):
        c_row=cur_daily[i] if i<len(cur_daily) else {};p_row=prev_daily[i] if i<len(prev_daily) else {};csig=cur_sig.get(day,{}) ; psigrow=prev_sig.get(previous_days[i],{})
        dt=datetime.strptime(day,'%Y-%m-%d')
        daily.append(dict(label=weekdays[dt.weekday()] if period.get('mode')=='week' else dt.strftime('%d/%m'),day=day,previous_day=previous_days[i],
            current=c_row.get('total'),previous=p_row.get('total'),current_source=c_row.get('source','missing'),previous_source=p_row.get('source','missing'),
            current_lost_seconds=c_row.get('lost_seconds'),previous_lost_seconds=p_row.get('lost_seconds'),
            current_inactive_seconds=csig.get('inactive_seconds',0),previous_inactive_seconds=psigrow.get('inactive_seconds',0),
            current_inactive_count=csig.get('inactive_count',0),previous_inactive_count=psigrow.get('inactive_count',0)))
    return dict(enabled=True,available=True,label=previous_label,date_from=previous_days[0],date_to=previous_days[-1],
        current_active_days=active,previous_active_days=prev_active,current_integrity=current_score,previous_integrity=previous_score,
        verdict=dict(code=code,label=label,detail=detail),metrics=metrics,daily=daily,
        previous_summary=pds,previous_calls_summary=pcs)

def _report_overview(dataset,comparison):
    ds=dataset.get('disconnects',{}).get('summary',{});agents=dataset.get('disconnects',{}).get('agents',[]);clusters=dataset.get('disconnects',{}).get('clusters',[])
    items=[]
    if comparison.get('available'):
        items.append(f"Tendance globale : {comparison.get('verdict',{}).get('label','Stable')} par rapport à {comparison.get('label','la période précédente')} avec les mêmes filtres.")
    else:
        items.append('Tendance globale : comparaison précédente indisponible ; la synthèse porte uniquement sur la période sélectionnée.')
    if agents:
        # Use the Support engine's policy order, not an independent ranking.
        top=agents[0]
        lost=max(0,int(round(float(top.get('lost_seconds') or 0))));h,rem=divmod(lost,3600);m=rem//60
        lost_text=(f"{h} h {m:02d} min" if h else f"{m} min")
        items.append(f"Concentration technique : {int(ds.get('impacted_agents') or 0)} agent(s)/poste(s) touché(s). Le premier poste selon les policies Support est {top.get('name') or top.get('agent')} avec {lost_text}, {int(top.get('deco') or 0)} déconnexion(s) dont {int(top.get('deco_call') or 0)} en appel.")
    else:
        items.append('Concentration technique : aucune déconnexion normale retenue avec les filtres sélectionnés.')
    items.append(f"Signaux majeurs : {int(ds.get('anomalies_over_1h') or 0)} anomalie(s) > 1 h et {len(clusters)} regroupement(s) simultané(s) détecté(s).")
    return items[:3]

def _report_scope_accept(agent,group_id,groups,include_agents,exclude_agents,admin_directory):
    key=canonical_admin_key(agent)
    if not key:return False
    if support_agent_is_excluded(agent,admin_directory):return False
    group_set={str(x) for x in groups}
    include_set={canonical_admin_key(x) for x in include_agents if canonical_admin_key(x)}
    exclude_set={canonical_admin_key(x) for x in exclude_agents if canonical_admin_key(x)}
    if group_set and not matches_agent_groups(agent,group_set):return False
    if include_set and key not in include_set:return False
    if exclude_set and key in exclude_set:return False
    return True

def _report_collect_signals(c,report_qs,cfg,days,names,admin_directory,groups,include_agents,exclude_agents,source,disconnects,include_details=False):
    """Collect context-inactive intervals and supplemental technical signals for reports.

    This intentionally mirrors the analytics source rules, but supports the report
    module's multi-group and multi-agent filters. Long disconnect anomalies are
    folded in here only for per-agent severity; they remain separate from normal
    disconnect KPIs.
    """
    admin_users=admin_directory.get('users',{})
    cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
    slots=_support_excluded_slots(report_qs)
    clock=datetime.now().timestamp()
    inactive=[];technical=[]
    for day in days:
        a,b=selected_bounds(day,cfg,report_qs,'1');ref=cov.get(day)
        use_export=bool(ref) and source!='capture';use_capture=(not use_export) and source!='export'
        if use_export:
            rows=[dict(r) for r in c.execute('SELECT agent,name,start,end,state,kind FROM activities WHERE import_id=? AND start<? AND end>?',(ref,b,a))]
            src='export'
        elif use_capture:
            rows=live_intervals(c,a,b,cfg,clock);src='capture'
        else:
            rows=[];src='missing'
        for raw in rows:
            if not _analytics_is_inactive_state(raw.get('state')):continue
            agent=str(raw.get('agent') or '').strip()
            if not agent:continue
            u=admin_user_for(agent,admin_users) or {};gid=u.get('group_id')
            if not _report_scope_accept(agent,gid,groups,include_agents,exclude_agents,admin_directory):continue
            start=max(a,float(raw.get('start') or 0));end=min(b,float(raw.get('end') or start));duration=max(0,int(round(end-start)))
            if duration<=0:continue
            if slots and _overlaps_support_excluded_slot(start,end,cfg,slots):continue
            inactive.append(dict(agent=agent,name=u.get('display_name') or raw.get('name') or names.get(agent) or agent,
                group_id=gid,group_name=u.get('group_name',''),start=start,end=end,seconds=duration,duration=duration,day=day,
                start_text=display(start,cfg['display_offset']),end_text=display(end,cfg['display_offset']),source=src,
                detail=str(raw.get('state') or 'Contexte inactif')))
        if source!='export':
            for raw in c.execute('SELECT * FROM technical_signals WHERE start>=? AND start<?',(a,b)):
                r=dict(raw);cat=str(r.get('category') or '')
                if cat in ('offline','disconnect_call'):continue
                agent=str(r.get('agent') or '').strip()
                if not agent:continue
                u=admin_user_for(agent,admin_users) or {};gid=u.get('group_id')
                if not _report_scope_accept(agent,gid,groups,include_agents,exclude_agents,admin_directory):continue
                start=float(r.get('start') or 0)
                if slots and _overlaps_support_excluded_slot(start,start+1,cfg,slots):continue
                technical.append(dict(agent=agent,name=u.get('display_name') or names.get(agent) or agent,group_id=gid,group_name=u.get('group_name',''),
                    start=start,end=start,seconds=0,duration=0,day=day,start_text=display(start,cfg['display_offset']),end_text=display(start,cfg['display_offset']),
                    source='capture',category=cat,label=TECH_LABELS.get(cat,'Signal technique'),detail=str(r.get('detail') or '')))

    generic_policies=load_policies()
    declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
    inactive,inactive_governance_excluded=governed_visible_events(inactive,'reports',generic_policies,declarations)
    technical,technical_governance_excluded=governed_visible_events(technical,'reports',generic_policies,declarations)
    by_agent={}
    def st_for(agent,name='',group_id=None,group_name=''):
        key=canonical_admin_key(agent)
        return by_agent.setdefault(key,dict(agent=agent,name=name or names.get(agent) or agent,group_id=group_id,group_name=group_name or '',
            inactive_count=0,inactive_seconds=0,technical_count=0,anomaly_count=0,anomaly_seconds=0))
    for r in inactive:
        st=st_for(r['agent'],r.get('name'),r.get('group_id'),r.get('group_name'));st['inactive_count']+=1;st['inactive_seconds']+=int(r.get('governance_effective_seconds',r.get('seconds') or 0))
    for r in technical:
        st=st_for(r['agent'],r.get('name'),r.get('group_id'),r.get('group_name'));st['technical_count']+=1
    all_anomalies=disconnects.get('all_anomalies') or disconnects.get('anomalies') or []
    for r in all_anomalies:
        agent=str(r.get('agent') or '').strip()
        if not agent:continue
        st=st_for(agent,r.get('name'),r.get('group_id'),r.get('group_name'));st['anomaly_count']+=1;st['anomaly_seconds']+=int(r.get('seconds') or 0)
    daily=[]
    for day in days:
        ir=[r for r in inactive if r['day']==day];tr=[r for r in technical if r['day']==day]
        daily.append(dict(label=day,inactive_count=len(ir),inactive_seconds=sum(int(r.get('governance_effective_seconds',r.get('seconds') or 0)) for r in ir),technical_count=len(tr)))
    summary=dict(inactive_count=len(inactive),inactive_seconds=sum(int(r.get('governance_effective_seconds',r.get('seconds') or 0)) for r in inactive),technical_count=len(technical),
        governance_excluded=len(inactive_governance_excluded)+len(technical_governance_excluded),
        anomalies=sum(int(v.get('anomaly_count') or 0) for v in by_agent.values()),anomaly_seconds=sum(int(v.get('anomaly_seconds') or 0) for v in by_agent.values()))
    return dict(summary=summary,agents=by_agent,daily=daily,
        inactive_incidents=inactive if include_details else sorted(inactive,key=lambda r:r['seconds'],reverse=True)[:40],
        technical_incidents=technical if include_details else technical[:40])

def _report_build_agent_profiles(available_agents,disconnects,signals,admin_directory,groups,include_agents,exclude_agents,selected_days=1):
    stats={canonical_admin_key(r.get('agent')):dict(r) for r in (disconnects.get('agents') or []) if canonical_admin_key(r.get('agent'))}
    sig=(signals or {}).get('agents') or {}
    rows=[];seen=set()
    for base in available_agents:
        agent=str(base.get('agent') or '');key=canonical_admin_key(agent)
        if not key or key in seen:continue
        if not _report_scope_accept(agent,base.get('group_id'),groups,include_agents,exclude_agents,admin_directory):continue
        seen.add(key)
        row=dict(agent=agent,name=base.get('name') or agent,group_id=base.get('group_id'),group_name=base.get('group_name') or '',
            deco=0,deco_call=0,critical_count=0,lost_seconds=0,max_seconds=0,days_affected=0,priority='AUCUNE',
            likely_cause='Aucun incident retenu',suggested_action='Aucune action technique requise sur la période selon les filtres du rapport.',
            inactive_count=0,inactive_seconds=0,technical_count=0,anomaly_count=0,anomaly_seconds=0)
        if key in stats:row.update(stats[key])
        if key in sig:row.update({k:v for k,v in sig[key].items() if k in ('inactive_count','inactive_seconds','technical_count','anomaly_count','anomaly_seconds')})
        rows.append(row)
    # Keep legacy/renamed impacted IDs even if missing from directory.
    for key in set(stats)|set(sig):
        if not key or key in seen:continue
        base=dict(stats.get(key) or sig.get(key) or {});agent=str(base.get('agent') or key)
        if not _report_scope_accept(agent,base.get('group_id'),groups,include_agents,exclude_agents,admin_directory):continue
        row=dict(agent=agent,name=base.get('name') or agent,group_id=base.get('group_id'),group_name=base.get('group_name') or '',
            deco=0,deco_call=0,critical_count=0,lost_seconds=0,max_seconds=0,days_affected=0,priority='AUCUNE',
            likely_cause='À qualifier',suggested_action='Vérifier le contexte technique.',inactive_count=0,inactive_seconds=0,technical_count=0,anomaly_count=0,anomaly_seconds=0)
        if key in stats:row.update(stats[key])
        if key in sig:row.update({k:v for k,v in sig[key].items() if k in ('inactive_count','inactive_seconds','technical_count','anomaly_count','anomaly_seconds')})
        rows.append(row);seen.add(key)
    policies=disconnects.get('priority_policy') or []
    cfg=disconnects.get('score_config') or {}
    observed={canonical_admin_key(k):v for k,v in (disconnects.get('worked_days_by_agent') or {}).items()}
    covered=max(1,int((disconnects.get('summary') or {}).get('active_days') or 0))
    for row in rows:
        key=canonical_admin_key(row.get('agent'))
        row['priority_evaluated']=key in stats or observed.get(key,0)>0
        if key not in stats and row['priority_evaluated']:
            row.update(compute_agent_score([],observed[key],cfg))
            row['priority'],metrics,row['priority_reasons']=evaluate_priority(row,selected_days,covered,policies)
            row.update(metrics)
        elif not row['priority_evaluated']:
            row['priority']='NON ÉVALUÉE'
            row['priority_reasons']=['Aucune activité observée sur la période avec les filtres retenus.']
            row['technical_score']=None
        if row['priority_evaluated'] and not row.get('priority_reasons'):
            row['priority_reasons']=['Niveau par défaut : aucune règle active de rang supérieur ne correspond.']
    return rows

def _report_score_agents(rows,reference_rows=None,policies=None):
    """Reuse Support scores and policy ranking. No cohort-relative index.

    Legacy instability_* keys remain API aliases for existing consumers.
    reference_rows is retained for compatibility, never used to rescale scores.
    """
    policy_map={p['priority']:p for p in (policies or [])}
    for r in rows:
        policy=policy_map.get(r.get('priority'),{})
        r['priority_rank']=int(policy.get('rank') or 0) if r.get('priority_evaluated',True) else -1
        r['priority_color']=policy.get('color') or '#667085'
        r['instability_score']=r.get('technical_score')
        r['instability_parts']={p['code']:p['points'] for p in (r.get('score_components') or []) if 'code' in p and 'points' in p}
    rows.sort(key=lambda r:(not r.get('priority_evaluated',True),-r['priority_rank'],
        -float(r.get('technical_score') or 0),-int(r.get('deco_call') or 0),-int(r.get('deco') or 0),str(r.get('name') or r.get('agent'))))
    return rows,{}

def _report_agent_comparison(current_rows,previous_rows):
    prev={canonical_admin_key(r.get('agent')):r for r in previous_rows}
    out=[]
    for r in current_rows:
        p=prev.get(canonical_admin_key(r.get('agent'))) or {}
        cur=float(r.get('technical_score') or 0);old=float(p.get('technical_score') or 0)
        comparable=bool(r.get('priority_evaluated') and p.get('priority_evaluated'))
        out.append(dict(agent=r.get('agent'),name=r.get('name'),group_name=r.get('group_name'),current_score=cur if r.get('priority_evaluated') else None,previous_score=old if p.get('priority_evaluated') else None,delta_score=round(cur-old,2) if comparable else None,
            comparable=comparable,current_priority=r.get('priority'),previous_priority=p.get('priority') or 'NON ÉVALUÉE',
            current_priority_color=r.get('priority_color'),previous_priority_color=p.get('priority_color'),
            current_lost=int(r.get('lost_seconds') or 0),previous_lost=int(p.get('lost_seconds') or 0),
            current_deco=int(r.get('deco') or 0),previous_deco=int(p.get('deco') or 0),current_call=int(r.get('deco_call') or 0),previous_call=int(p.get('deco_call') or 0),
            current_anomaly=int(r.get('anomaly_count') or 0),previous_anomaly=int(p.get('anomaly_count') or 0),
            current_inactive=int(r.get('inactive_seconds') or 0),previous_inactive=int(p.get('inactive_seconds') or 0)))
    out.sort(key=lambda r:(not r['comparable'],-float(r['delta_score'] or 0),-float(r['current_score'] or 0),str(r.get('name') or r.get('agent')).casefold()))
    return out

def _weekly_report_data(qs,user,include_details=False):
    cfg=config();period=_report_period(qs);date_from=period['date_from'];date_to=period['date_to']
    seeded=dict(qs or {});seeded['date_from']=[date_from];seeded['date_to']=[date_to]
    normalized_qs,common_filters,_,hidden_filters=normalize_filters(seeded,cfg,default_full_day='0',max_days=REPORT_MAX_DAYS)
    # One immutable configuration snapshot per report, shared by both periods.
    priority_policies=load_priority_policies();score_config=load_score_config()
    snapshot=dict(policies=public_policy_snapshot(priority_policies),score=public_score_config(score_config))
    fingerprint=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=True).encode('utf-8')).hexdigest()[:16]
    generated_at=france_display(datetime.now().timestamp())[0:19]
    mode=_report_get(qs,'mode','summary').lower()
    if mode not in ('summary','complete'):raise ValueError('Mode de rapport invalide.')
    report_type=_report_get(qs,'report_type','overview').lower() or 'overview'
    if report_type not in ('overview','comparison','detailed'):raise ValueError('Type de rapport invalide.')
    if report_type=='detailed':mode='complete'
    source=str(hidden_filters.get('source') or '')
    groups=_report_values(qs,'group')
    include_agents=_report_values(qs,'include_agent')
    exclude_agents=_report_values(qs,'exclude_agent')
    compare_previous=(report_type=='comparison') or _report_bool(qs,'compare_previous',False)

    # Backward compatibility with the first weekly-report UI.
    legacy_scope=_report_get(qs,'scope','global').lower()
    legacy_agent=_report_get(qs,'agent')
    if legacy_scope=='agent' and legacy_agent and legacy_agent not in include_agents:include_agents.append(legacy_agent)
    legacy_group=_report_get(qs,'group') if legacy_scope=='group' else ''
    if legacy_group and legacy_group not in groups:groups.append(legacy_group)

    call_scope=str(common_filters.get('call_scope') or 'all')
    call_issue=_report_get(qs,'call_issue','all').lower() or 'all'
    if call_issue not in ('all','end_code','short','invalid','abandon','no_agent'):raise ValueError('Filtre d’appels invalide.')
    min_disconnect=float(common_filters.get('min_disconnect') or 0)
    time_from=_report_get(qs,'time_from');time_to=_report_get(qs,'time_to')
    if (time_from and not time_to) or (time_to and not time_from):raise ValueError('Renseigner à la fois l’heure de début et l’heure de fin.')
    full_day='1' if _report_bool(qs,'full_day',False) else '0'
    report_qs={
        'date_from':[date_from],'date_to':[date_to],'source':[source],'full_day':[full_day],
        'min_disconnect':[str(min_disconnect)],'call_scope':[call_scope],
        'exclude_12_13':['1' if _report_bool(qs,'exclude_12_13') else '0'],
        'exclude_13_14':['1' if _report_bool(qs,'exclude_13_14') else '0'],
        'exclude_custom_from':[_report_get(qs,'exclude_custom_from','')],
        'exclude_custom_to':[_report_get(qs,'exclude_custom_to','')],
        '_legacy_exclusion_mode':[str(common_filters.get('legacy_exclusion_mode') or 'compat')],
    }
    if time_from:report_qs['time_from']=[time_from];report_qs['time_to']=[time_to]
    if groups:report_qs['group']=groups
    if include_agents:report_qs['include_agent']=include_agents
    if exclude_agents:report_qs['exclude_agent']=exclude_agents
    # Every generated PDF keeps the detailed technical evidence in annexes.
    # The first pages stay minimal; the raw incident lists are loaded only for
    # the PDF generation endpoint, never for the lightweight browser preview.
    if include_details:report_qs['_include_incidents']=['1']
    days=date_range(report_qs,cfg)
    if len(days)>REPORT_MAX_DAYS:raise ValueError(f'Un rapport PDF est limité à {REPORT_MAX_DAYS} jours maximum.')
    previous_days=[(datetime.strptime(d,'%Y-%m-%d')-timedelta(days=len(days))).strftime('%Y-%m-%d') for d in days]

    with connect() as c:
        names=latest_agent_names(c)
        admin_directory=load_admin_directory();admin_users=admin_directory['users']
        for ag in list(names):names[ag]=admin_name_for(ag,admin_users,names[ag])
        current=_report_dataset(c,report_qs,cfg,days,names,source,groups,include_agents,exclude_agents,call_issue,priority_policies,score_config)
        devices=_analytics_latest_devices()
        current['signals']=_report_collect_signals(c,report_qs,cfg,days,names,admin_directory,groups,include_agents,exclude_agents,source,current['disconnects'],include_details)
        previous={}
        if compare_previous:
            previous_qs=dict(report_qs);previous_qs['date_from']=[previous_days[0]];previous_qs['date_to']=[previous_days[-1]];previous_qs.pop('_include_incidents',None)
            previous=_report_dataset(c,previous_qs,cfg,previous_days,names,source,groups,include_agents,exclude_agents,call_issue,priority_policies,score_config)
            previous['signals']=_report_collect_signals(c,previous_qs,cfg,previous_days,names,admin_directory,groups,include_agents,exclude_agents,source,previous['disconnects'],False)

    comparison=_report_comparison(current,previous,days,previous_days,period,compare_previous) if compare_previous else dict(enabled=False,available=False)
    overview=_report_overview(current,comparison)

    group_names=[]
    for gid in groups:
        name=next((str(g.get('name') or '') for g in admin_directory.get('groups',[]) if str(g.get('id'))==str(gid)),str(gid))
        group_names.append(name or str(gid))
    def display_agent(agent):
        exact=admin_user_for(agent,admin_users)
        return (exact or {}).get('display_name') or names.get(agent) or str(agent)
    include_names=[display_agent(a) for a in include_agents]
    exclude_names=[display_agent(a) for a in exclude_agents]
    def compact_selection(label,values,limit=6):
        if not values:return ''
        shown=', '.join(values[:limit])
        if len(values)>limit:shown+=f' +{len(values)-limit} autre(s)'
        return f'{label} : {shown}'
    parts=[]
    if group_names:parts.append(compact_selection('Groupe(s)',group_names,5))
    if include_names:parts.append(compact_selection('Agents inclus',include_names,6))
    if exclude_names:parts.append(compact_selection('Agents exclus',exclude_names,6))
    scope_label='Global' if not parts else ' | '.join(parts)
    source_label={'':'Référence quotidienne automatique','export':'SIMPLIFY2 uniquement','capture':'Capture uniquement'}[source]
    if time_from:
        time_label=f'Plage personnalisée {time_from}-{time_to}'
    else:
        time_label='Journée complète 00:00-24:00' if full_day=='1' else f"Plage de travail {cfg['work_start']}-{cfg['work_end']}"
    excluded=[label for _,_,label in _support_excluded_slots(report_qs)]
    if excluded:time_label+=' | Logs exclus : '+', '.join(excluded)
    context_label={'all':'Toutes les déconnexions','during':'Pendant appel uniquement','outside':'Hors appel uniquement'}[call_scope]
    call_issue_label={'all':'Tous les appels','end_code':'EndReason non nul','short':'Conversations courtes','invalid':'Durées incohérentes','abandon':'Abandons','no_agent':'Sans agent'}[call_issue]
    available_agents=build_agent_roster(names,admin_directory,devices)

    # Build a complete roster and enrich every agent with the report's technical signals.
    report_agents=_report_build_agent_profiles(available_agents,current['disconnects'],current.get('signals'),admin_directory,groups,include_agents,exclude_agents,len(days))
    previous_agents=[];agent_comparison=[]
    if compare_previous and previous:
        previous_agents=_report_build_agent_profiles(available_agents,previous['disconnects'],previous.get('signals'),admin_directory,groups,include_agents,exclude_agents,len(previous_days))
        report_agents,instability_weights=_report_score_agents(report_agents,previous_agents,priority_policies)
        previous_agents,_=_report_score_agents(previous_agents,report_agents,priority_policies)
        agent_comparison=_report_agent_comparison(report_agents,previous_agents)
    else:
        report_agents,instability_weights=_report_score_agents(report_agents,policies=priority_policies)
    top_unstable=[r for r in report_agents if r.get('priority_evaluated') and any(float(r.get(k) or 0)>0 for k in ('deco','anomaly_count','collective_count','probable_closure_count','technical_score'))][:20]

    return dict(
        week=period['week'],week_label=period['label'],period_label=period['label'],period_mode=period['mode'],period_token=period['token'],
        date_from=date_from,date_to=date_to,period_days=len(days),max_report_days=REPORT_MAX_DAYS,reference_day=_report_reference_day(),
        priority_audit=dict(applied=True,fingerprint=fingerprint,captured_at=generated_at,
            policy_count=len([p for p in priority_policies if p.get('enabled')]),
            engine='support_scoring + support_priority',comparison_same_snapshot=True,
            method='Classement par rang de policy, puis score technique Support. Les niveaux, couleurs, seuils et conditions ET/OU proviennent de Priorités Support. Les anomalies > 1 h et les contextes inactifs restent des signaux séparés, sans ancien indice supplémentaire.'),
        generated_at=generated_at,generated_by=str((user or {}).get('username') or 'Nelyio'),
        mode=mode,report_type=report_type,scope='filtered' if parts else 'global',scope_label=scope_label,source=source,source_label=source_label,time_label=time_label,
        disconnect_context_label=context_label,call_issue_label=call_issue_label,
        disconnects=current['disconnects'],core_metrics=current.get('core_metrics') or disconnect_metric_snapshot(current['disconnects']),integrity=current['integrity'],calls_summary=current['calls_summary'],top_end_reasons=current['top_end_reasons'],
        call_coverage=current['call_coverage'],signals=current.get('signals',{}),comparison=comparison,overview=overview,reportlab_available=weekly_reports.reportlab_available(),
        top_unstable=top_unstable,instability_weights=instability_weights,agent_comparison=agent_comparison,previous_agents=previous_agents,
        common_filters=public_filter_contract(dict(common_filters,groups=groups,include_agents=include_agents,exclude_agents=exclude_agents)),
        filters=dict(groups=groups,include_agents=include_agents,exclude_agents=exclude_agents,full_day=full_day,time_from=time_from,time_to=time_to,
            min_disconnect=min_disconnect,call_scope=call_scope,call_issue=call_issue,compare_previous='1' if compare_previous else '0',
            exclude_12_13=report_qs['exclude_12_13'][0],exclude_13_14=report_qs['exclude_13_14'][0],
            exclude_custom_from=report_qs['exclude_custom_from'][0],exclude_custom_to=report_qs['exclude_custom_to'][0],excluded_slots=excluded),
        available_groups=admin_directory.get('groups',[]),available_agents=available_agents,report_agents=report_agents,scope_agent_count=len(report_agents),
        detail_counts=dict(
            disconnects=int((current.get('disconnects',{}).get('summary') or {}).get('raw_normal_disconnects') or 0),
            anomalies=int((current.get('disconnects',{}).get('summary') or {}).get('anomalies_over_1h') or 0),
            inactive=int((current.get('signals',{}).get('summary') or {}).get('inactive_count') or 0),
            technical=int((current.get('signals',{}).get('summary') or {}).get('technical_count') or 0),
            agents=len(report_agents),
        ),
        web_summary=dict(
            overview=overview,
            daily=current.get('disconnects',{}).get('daily',[]),
            duration_bands=current.get('disconnects',{}).get('duration_bands',[]),
            top_days=current.get('disconnects',{}).get('top_days',[]),
            coverage=current.get('disconnects',{}).get('source_by_day',[]),
            calls=current.get('calls_summary',{}),
            top_end_reasons=current.get('top_end_reasons',[]),
        ),
        work_start=cfg['work_start'],work_end=cfg['work_end'],
    )

def weekly_report_preview(qs,user):
    """Return a bounded browser preview.

    Detailed incident rows are deliberately loaded through weekly_report_details
    so a 30-day report stays fast and readable in the browser.
    """
    data=_weekly_report_data(qs,user,include_details=False)
    disconnects=data.get('disconnects') or {}
    data['disconnects']={k:v for k,v in disconnects.items() if k not in ('incidents','all_anomalies')}
    signals=dict(data.get('signals') or {})
    signals.pop('inactive_incidents',None);signals.pop('technical_incidents',None)
    data['signals']=signals
    return data

def _report_detail_kind(qs):
    kind=_report_get(qs,'detail_kind','disconnects').lower() or 'disconnects'
    if kind not in ('disconnects','anomalies','inactive','technical','agents'):
        raise ValueError('Type de détail du rapport invalide.')
    return kind

def _report_page(qs):
    try:page=max(1,int(_report_get(qs,'page','1') or 1))
    except ValueError as exc:raise ValueError('Page de détail invalide.') from exc
    try:page_size=int(_report_get(qs,'page_size',str(REPORT_DETAIL_DEFAULT_PAGE_SIZE)) or REPORT_DETAIL_DEFAULT_PAGE_SIZE)
    except ValueError as exc:raise ValueError('Taille de page invalide.') from exc
    page_size=max(10,min(REPORT_DETAIL_MAX_PAGE_SIZE,page_size))
    return page,page_size

def _report_detail_rows(data,kind):
    if kind=='disconnects':
        rows=list((data.get('disconnects') or {}).get('incidents') or [])
        rows.sort(key=lambda r:(-float(r.get('start') or 0),str(r.get('agent') or '')))
        return rows
    if kind=='anomalies':
        disconnects=data.get('disconnects') or {}
        rows=list(disconnects.get('all_anomalies') or disconnects.get('anomalies') or [])
        rows.sort(key=lambda r:(-float(r.get('start') or 0),str(r.get('agent') or '')))
        return rows
    if kind=='inactive':
        rows=list((data.get('signals') or {}).get('inactive_incidents') or [])
        rows.sort(key=lambda r:(-float(r.get('start') or 0),str(r.get('agent') or '')))
        return rows
    if kind=='technical':
        rows=list((data.get('signals') or {}).get('technical_incidents') or [])
        rows.sort(key=lambda r:(-float(r.get('start') or 0),str(r.get('agent') or '')))
        return rows
    rows=list(data.get('report_agents') or [])
    rows.sort(key=lambda r:(0 if r.get('priority_evaluated') else 1,-float(r.get('technical_score') or 0),str(r.get('name') or r.get('agent') or '').casefold()))
    return rows

def weekly_report_details(qs,user):
    """Paginated on-demand evidence using the exact report filters/calculations."""
    kind=_report_detail_kind(qs);page,page_size=_report_page(qs)
    data=_weekly_report_data(qs,user,include_details=True)
    rows=_report_detail_rows(data,kind);total=len(rows)
    pages=max(1,(total+page_size-1)//page_size)
    if page>pages:page=pages
    start=(page-1)*page_size;end=start+page_size
    return dict(
        kind=kind,page=page,page_size=page_size,pages=pages,total=total,rows=rows[start:end],
        date_from=data.get('date_from'),date_to=data.get('date_to'),scope_label=data.get('scope_label'),
        common_filters=data.get('common_filters') or {},detail_counts=data.get('detail_counts') or {},
    )

def weekly_report_pdf(qs,user):
    data=_weekly_report_data(qs,user,include_details=True)
    payload=weekly_reports.build_weekly_pdf(data)
    safe_scope=re.sub(r'[^A-Za-z0-9_-]+','_',data.get('scope_label','Global')).strip('_')[:40] or 'Global'
    token=re.sub(r'[^A-Za-z0-9_-]+','_',data.get('period_token') or 'periode').strip('_')[:40]
    kind={'overview':'Vue_Ensemble','comparison':'Comparaison','detailed':'Detail_Complet'}.get(data.get('report_type'),'Rapport')
    filename=f"Nelyio_{kind}_{token}_{safe_scope}.pdf"
    return payload,filename

