"""Cross-period technical diagnostics and comparison data for Nelyio."""
from collections import Counter
from datetime import datetime, timedelta
import html, re
import db_compat as sqlite3
from error_log import log_unexpected_error
import supervision_context as ctx
from supervision_db import connect, config
from agent_directory import (admin_name_for, admin_user_for, build_agent_roster, canonical_admin_key, load_admin_directory, support_agent_is_excluded)
from supervision_utils import display, selected_bounds, latest_agent_names
from live_capture import live_intervals
from support_filters import TECH_LABELS, _support_excluded_slots, _in_support_excluded_slot, _overlaps_support_excluded_slot
from disconnects import disconnect_statistics
from metrics_engine import aggregate_incident_metrics, compare_agent_trends, compare_snapshots, disconnect_metric_snapshot
from unified_filters import apply_row_scope, normalize_filters, public_filter_contract
from governance_engine import governed_visible_events
from policy_engine import load_policies
from declaration_engine import load_declarations
from analysis_groups import filter_catalog

_INACTIVE_STATE_RE=re.compile(r'(aucun\s+contexte|sans\s+contexte|no\s+context|inactive|inactif|context\s+inactive|contexte\s+inactif)')

def _analytics_days(first,last):
    try:a=datetime.strptime(first,'%Y-%m-%d');b=datetime.strptime(last,'%Y-%m-%d')
    except ValueError:raise ValueError('Dates d’analyse invalides.')
    length=(b-a).days+1
    if not 1<=length<=93:raise ValueError('La période doit contenir entre 1 et 93 jours.')
    return [(a+timedelta(days=i)).strftime('%Y-%m-%d') for i in range(length)]

def _analytics_delta(a,b):
    if b in (None,0):return None
    return round((a-b)*100.0/b,1)

def _analytics_is_inactive_state(state):
    s=html.unescape(str(state or '')).strip().lower()
    return bool(_INACTIVE_STATE_RE.search(s))

def _analytics_latest_devices():
    if not sqlite3.runtime_database_available(ctx.admin_db_path()):return {}
    out={}
    try:
        con=sqlite3.connect(str(ctx.admin_db_path()),timeout=5);con.row_factory=sqlite3.Row
        try:
            rows=con.execute("""WITH ranked AS (
                                  SELECT id,utilisateur,
                                         ROW_NUMBER() OVER (
                                           PARTITION BY utilisateur
                                           ORDER BY datetime(date_evenement) DESC,id DESC
                                         ) AS rn
                                  FROM diagnostic
                                  WHERE TRIM(COALESCE(utilisateur,''))<>''
                                    AND TRIM(COALESCE(ordinateur,''))<>''
                                )
                                SELECT d.utilisateur,d.ordinateur,d.adresse_ip,d.date_evenement
                                FROM ranked r
                                JOIN diagnostic d ON d.id=r.id
                                WHERE r.rn=1
                                ORDER BY datetime(d.date_evenement) DESC,d.id DESC""")
            for row in rows:
                key=canonical_admin_key(row['utilisateur'])
                if key and key not in out:
                    out[key]=dict(pc=row['ordinateur'] or '',ip=row['adresse_ip'] or '',last_seen=row['date_evenement'] or '')
        finally:con.close()
    except sqlite3.Error:
        log_unexpected_error('supervision._analytics_latest_devices.L2109')
        return {}
    return out

def _analytics_clusters(incidents,cfg,window=180,min_agents=3):
    """Detect non-overlapping multi-agent incident windows.

    Uses a sliding time window rather than fixed clock buckets so an incident
    at 10:02:59 and another at 10:03:01 can still belong to the same cluster.
    """
    by_day={}
    for r in incidents:
        r['collective']=False;r.pop('cluster_id',None)
        if r.get('agent'):by_day.setdefault(r['day'],[]).append(r)
    clusters=[];cluster_id=0
    for day,rows in by_day.items():
        rows.sort(key=lambda r:(float(r['start']),str(r.get('agent',''))))
        i=0
        while i<len(rows):
            j=i+1
            while j<len(rows) and float(rows[j]['start'])-float(rows[i]['start'])<=window:j+=1
            window_rows=rows[i:j];agents={r['agent'] for r in window_rows if r.get('agent')}
            if len(agents)<min_agents:
                i+=1;continue
            cluster_id+=1
            for r in window_rows:r['collective']=True;r['cluster_id']=cluster_id
            start=min(r['start'] for r in window_rows);end=max(r.get('end',r['start']) for r in window_rows)
            groups=sorted({r.get('group_name','') for r in window_rows if r.get('group_name')},key=str.casefold)
            pcs=sorted({r.get('pc','') for r in window_rows if r.get('pc')},key=str.casefold)
            categories=Counter(r['category'] for r in window_rows)
            clusters.append(dict(id=cluster_id,day=day,start=start,end=end,start_text=display(start,cfg['display_offset']),
                end_text=display(end,cfg['display_offset']),agent_count=len(agents),agents=sorted(agents,key=str),pc_count=len(pcs),pcs=pcs,groups=groups,
                incident_count=len(window_rows),lost_seconds=sum(int(r.get('governance_effective_seconds',r.get('duration') or 0)) for r in window_rows if r['category'] in ('offline','inactive')),
                categories=[dict(key=k,label=('Déconnexion' if k=='offline' else 'Contexte inactif' if k=='inactive' else TECH_LABELS.get(k,k)),value=v) for k,v in categories.most_common()]))
            i=j
    clusters.sort(key=lambda r:(-r['agent_count'],-r['incident_count'],r['start']))
    return clusters

def _analytics_collect_period(c,qs,cfg,days,names,admin_directory,devices,common_filters=None,hidden=None):
    get=lambda k,d='':qs.get(k,[d])[0]
    if common_filters is None or hidden is None:
        _,common_filters,_,hidden=normalize_filters(qs,cfg,default_date_from=days[0],default_date_to=days[-1],default_full_day='0')
    source_filter=str((hidden or {}).get('source') or '').strip()
    incident_type=str((hidden or {}).get('type') or '').strip()
    min_duration=float((common_filters or {}).get('min_disconnect') or 0)
    try:cluster_window=max(60,min(600,int(get('cluster_window','180') or 180)))
    except ValueError:raise ValueError('Fenêtre de simultanéité invalide.')
    try:cluster_min_agents=max(2,min(20,int(get('cluster_min_agents','3') or 3)))
    except ValueError:raise ValueError('Nombre minimum d’agents invalide.')
    admin_users=admin_directory['users'];excluded_slots=_support_excluded_slots(qs)
    agent_meta={}
    def meta(agent):
        if agent not in agent_meta:
            user=admin_user_for(agent,admin_users);key=canonical_admin_key(agent)
            agent_meta[agent]=(support_agent_is_excluded(agent,admin_directory),user,key,devices.get(key,{}))
        return agent_meta[agent]
    cov={r['day']:r['import_id'] for r in c.execute('SELECT * FROM coverage WHERE day BETWEEN ? AND ?',(days[0],days[-1]))}
    dqs=dict(qs);dqs['_include_incidents']=['1'];dqs['date_from']=[days[0]];dqs['date_to']=[days[-1]];dqs['min_disconnect']=[str(min_duration)]
    disconnects=disconnect_statistics(c,dqs,cfg,days,cov,names,admin_directory=admin_directory,policy_module="analytics")
    incidents=[]
    for raw in disconnects.get('incidents',[]):
        r=dict(raw);_,_,_,dev=meta(r.get('agent'))
        r.update(category='offline',label='Déconnexion',duration=int(r.get('seconds') or 0),detail='Déconnexion suivie d’une reconnexion',pc=dev.get('pc',''),ip=dev.get('ip',''))
        incidents.append(r)
    # Contextes inactifs : même règle de source automatique que Support.
    clock=datetime.now().timestamp()
    for day in days:
        a,b=selected_bounds(day,cfg,qs,'0');ref=cov.get(day);use_export=bool(ref) and source_filter!='capture';use_capture=(not use_export) and source_filter!='export'
        if use_export:
            rows=[dict(r) for r in c.execute('SELECT agent,name,start,end,state,kind FROM activities WHERE import_id=? AND start<? AND end>?',(ref,b,a))];src='export'
        elif use_capture:
            rows=live_intervals(c,a,b,cfg,clock);src='capture'
        else:
            rows=[];src='missing'
        for raw in rows:
            if not _analytics_is_inactive_state(raw.get('state')):continue
            agent=str(raw.get('agent') or '').strip()
            if not agent:continue
            is_excluded,u,_,dev=meta(agent)
            if is_excluded:continue
            start=max(a,float(raw.get('start') or 0));end=min(b,float(raw.get('end') or start));duration=max(0,int(round(end-start)))
            if duration<=0 or duration<min_duration:continue
            if _overlaps_support_excluded_slot(start,end,cfg,excluded_slots):continue
            u=u or {};name=u.get('display_name') or raw.get('name') or names.get(agent) or agent
            incidents.append(dict(agent=agent,name=name,group_id=u.get('group_id'),group_name=u.get('group_name',''),pc=dev.get('pc',''),ip=dev.get('ip',''),
                start=start,end=end,duration=duration,seconds=duration,day=day,start_text=display(start,cfg['display_offset']),end_text=display(end,cfg['display_offset']),
                category='inactive',label='Contexte inactif',detail=str(raw.get('state') or 'Contexte inactif'),source=src,collective=False))
    # Signaux techniques complémentaires : conservés pour le diagnostic, mais
    # Source/Type ne sont plus des filtres principaux de l'interface.
    if source_filter!='export':
        for day in days:
            a,b=selected_bounds(day,cfg,qs,'0')
            for raw in c.execute('SELECT * FROM technical_signals WHERE start>=? AND start<?',(a,b)):
                r=dict(raw);cat=str(r.get('category') or '')
                if cat in ('offline','disconnect_call'):continue
                if _in_support_excluded_slot(r.get('start'),cfg,excluded_slots):continue
                agent=str(r.get('agent') or '').strip()
                if agent:
                    is_excluded,u,_,dev=meta(agent)
                    if is_excluded:continue
                else:u={};dev={}
                u=u or {}
                incidents.append(dict(agent=agent,name=u.get('display_name') or names.get(agent) or agent or 'Collecte',group_id=u.get('group_id'),group_name=u.get('group_name',''),
                    pc=dev.get('pc',''),ip=dev.get('ip',''),start=float(r['start']),end=float(r['start']),duration=0,seconds=0,day=day,
                    start_text=display(r['start'],cfg['display_offset']),end_text=display(r['start'],cfg['display_offset']),category=cat,label=TECH_LABELS.get(cat,'Signal technique'),
                    detail=str(r.get('detail') or ''),source='capture',collector=str(r.get('source') or ''),collective=False))
    # Phase E: governance is now transversal for inactive contexts and
    # supplemental technical signals too, not only disconnect rows.
    generic_policies=load_policies()
    declarations=load_declarations(days[0] if days else None,days[-1] if days else None)
    incidents,governance_excluded=governed_visible_events(incidents,'analytics',generic_policies,declarations)
    incidents=apply_row_scope(incidents,common_filters)
    if incident_type:
        selected=[]
        for r in incidents:
            if incident_type=='technical' and r['category'] in ('offline','inactive'):continue
            if incident_type!='technical' and r['category']!=incident_type:continue
            selected.append(r)
        incidents=selected
    clusters=_analytics_clusters(incidents,cfg,cluster_window,cluster_min_agents)
    anomalies=[]
    for raw in disconnects.get('anomalies',[]):
        r=dict(raw);_,u,_,dev=meta(r.get('agent'));u=u or {};r['pc']=dev.get('pc','');r['ip']=dev.get('ip','')
        if not apply_row_scope([r],common_filters):continue
        if incident_type and incident_type!='offline':continue
        anomalies.append(r)
    aggregate=aggregate_incident_metrics(incidents,days)
    summary=dict(aggregate['summary']);summary.update(collective_events=len(clusters),anomalies=len(anomalies),governance_excluded=len(governance_excluded))
    categories=aggregate['categories']
    source_rows=disconnects.get('source_by_day') or []
    coverage_days=[dict(day=r.get('day'),source=r.get('source') or 'missing') for r in source_rows]
    coverage=dict(total_days=len(coverage_days),export_days=sum(r['source']=='export' for r in coverage_days),capture_days=sum(r['source']=='capture' for r in coverage_days),missing_days=sum(r['source']=='missing' for r in coverage_days),days=coverage_days)
    coverage['note']='Couverture complète.' if not coverage['missing_days'] else f"{coverage['missing_days']} jour(s) sans source exploitable : les tendances doivent être lues avec prudence."
    guidance=[]
    if clusters:guidance.append(dict(title='Vérifier les incidents collectifs',evidence=f"{len(clusters)} regroupement(s) simultané(s) détecté(s).",action='Contrôler en priorité réseau, VPN, Hermès ou infrastructure partagée.',target='analytics-clusters'))
    if aggregate['recurrence']:guidance.append(dict(title='Contrôler les récurrences locales',evidence=f"{len(aggregate['recurrence'])} combinaison(s) agent/signal répétée(s).",action='Comparer le poste, la connexion et le contexte des agents concernés.',target='analytics-recurrence'))
    if coverage['missing_days']:guidance.append(dict(title='Compléter la couverture',evidence=coverage['note'],action='Vérifier l’import SIMPLIFY2 ou la collecte avant de conclure sur ces journées.',target='analytics-coverage'))
    return dict(date_from=days[0],date_to=days[-1],summary=summary,core_metrics=disconnect_metric_snapshot(disconnects),
        incidents=sorted(incidents,key=lambda r:(r['start'],r.get('agent','')),reverse=True)[:1000],clusters=clusters[:100],recurrence=aggregate['recurrence'][:200],agents=aggregate['agents'][:300],
        daily=aggregate['daily'],hourly=aggregate['hourly'],anomalies=anomalies[:500],coverage=coverage,guidance=guidance,
        categories=[dict(key=k,label=('Déconnexion' if k=='offline' else 'Contexte inactif' if k=='inactive' else TECH_LABELS.get(k,k)),value=v) for k,v in categories.most_common()],
        cluster_window=cluster_window,cluster_min_agents=cluster_min_agents)

def analytics_view(qs):
    cfg=config();raw=dict(qs or {})
    with connect() as c:
        latest=c.execute('SELECT MAX(day) FROM coverage').fetchone()[0]
        from collection_store import latest_day as latest_live_day
        latest=latest_live_day(latest)
        if not latest:latest=display(datetime.now().timestamp(),cfg['display_offset'])[:10]
        latest_dt=datetime.strptime(latest,'%Y-%m-%d')
        if not raw.get('date_to'):raw['date_to']=[latest]
        if not raw.get('date_from'):raw['date_from']=[(latest_dt-timedelta(days=6)).strftime('%Y-%m-%d')]
        query,common_filters,days,hidden=normalize_filters(raw,cfg,default_full_day='0')
        names=latest_agent_names(c)
        from collection_views import enrich_names
        enrich_names(names)
        admin_directory=load_admin_directory();admin_users=admin_directory['users']
        for agent in list(names):names[agent]=admin_name_for(agent,admin_users,names[agent])
        devices=_analytics_latest_devices()
        current=_analytics_collect_period(c,query,cfg,days,names,admin_directory,devices,common_filters,hidden)
        first=datetime.strptime(days[0],'%Y-%m-%d');prev_to=first-timedelta(days=1);prev_from=prev_to-timedelta(days=len(days)-1)
        prev_days=_analytics_days(prev_from.strftime('%Y-%m-%d'),prev_to.strftime('%Y-%m-%d'))
        prev_query=dict(query);prev_query['date_from']=[prev_days[0]];prev_query['date_to']=[prev_days[-1]]
        prev_common=dict(common_filters);prev_common['date_from']=prev_days[0];prev_common['date_to']=prev_days[-1]
        previous=_analytics_collect_period(c,prev_query,cfg,prev_days,names,admin_directory,devices,prev_common,hidden)
        available=build_agent_roster(names,admin_directory,devices)
        cur=current['summary'];pre=previous['summary']
        comparison=compare_snapshots(cur,pre,['incidents','lost_seconds','impacted_agents','disconnects','inactive','collective_events','anomalies'])
        core_comparison=compare_snapshots(current['core_metrics'],previous['core_metrics'],['disconnects','during_call','lost_seconds','impacted_agents','collective_incidents','probable_closures','anomalies'])
        agent_trends=compare_agent_trends(current.get('agents'),previous.get('agents'))
        response_filters=public_filter_contract(common_filters)
        response_filters.update(cluster_window=str(current['cluster_window']),cluster_min_agents=str(current['cluster_min_agents']))
        return dict(current=current,previous=dict(date_from=previous['date_from'],date_to=previous['date_to'],summary=pre,daily=previous['daily'],coverage=previous['coverage'],core_metrics=previous['core_metrics']),
            comparison=comparison,core_comparison=core_comparison,agent_trends=agent_trends,
            comparison_note='Comparaison descriptive avec la période précédente de même durée et les mêmes filtres communs.',
            available_agents=available,admin_groups=filter_catalog(),admin_directory_available=admin_directory['available'],latest_day=latest,config=cfg,
            filters=response_filters,common_filters=response_filters,excluded_agents_count=len(admin_directory.get('exclusions',set())))

