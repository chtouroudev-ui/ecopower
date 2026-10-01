"""Canonical Stats.INBOUND quality metrics for Nelyio.

RC2H aligns the business KPIs with the Vocalcom/SIMPLIFY2 classification:
- received = physical inbound rows in the active date/time/filter perimeter;
- treated = AgentId assigned (> 0), not IsCallAnswered;
- Nelyio QoS = treated by agent / (received - closed - hangup before queue).
- This is the single QoS formula exposed by the application.
IsCallAnswered remains a technical metric named ``answered``.
"""
import hashlib
import io
import json
import math
import zipfile
import threading
import import_bundle
from datetime import date, timedelta
from quality_importer import csv_table, agent_key, MAX_BYTES, MAX_EXPANDED
from quality_rules import aggregate_sql, decorate, agent_assigned_sql, agent_unassigned_sql, principal_hits_sql
from supervision_db import connect, config
from quality_summary import handled_agents, hourly_abandons
from supervision_utils import stamp
from nelyio_time import display, day_bounds

VERSION = 2
SUPPORTED_VERSIONS = {1, 2}
_SCHEMA_LOCK=threading.Lock()
_SCHEMA_READY=set()
FLAGS = {
    'received':'IsCall',
    'closed':'IsCallClosed',
    'overflow':'IsCallOverflow',
    'rerouted':'IsCallRerouted',
    'before_queue':'IsCallHangupBeforeQueue',
    'abandoned':'IsCallAbandonned',
    'lost':'IsCallLost',
    'answered':'IsCallAnswered',
    'transferred':'IsCallTransferred',
}


def ensure_schema(c):
    schema=getattr(c,'schema',None)
    if schema:
        with _SCHEMA_LOCK:
            if schema in _SCHEMA_READY:return
    c.execute('''CREATE TABLE IF NOT EXISTS quality_inbound_imports(
      import_id INTEGER PRIMARY KEY, digest TEXT NOT NULL, version INTEGER NOT NULL,
      rows_count INTEGER NOT NULL, source TEXT NOT NULL, published_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quality_inbound_facts(
      import_id INTEGER NOT NULL, row_number INTEGER NOT NULL, day TEXT NOT NULL,
      start REAL NOT NULL, campaign TEXT NOT NULL, campaign_name TEXT NOT NULL, agent TEXT NOT NULL,
      received INTEGER NOT NULL, answered INTEGER NOT NULL, abandoned INTEGER NOT NULL,
      closed INTEGER NOT NULL, overflow INTEGER NOT NULL, rerouted INTEGER NOT NULL,
      before_queue INTEGER NOT NULL, transferred INTEGER NOT NULL, wait REAL NOT NULL,
      invalid_duration INTEGER NOT NULL, payload TEXT NOT NULL, lost INTEGER, call_duration REAL,
      PRIMARY KEY(import_id,row_number))''')
    cols={r[1] for r in c.execute('PRAGMA table_info(quality_inbound_facts)')}
    if 'lost' not in cols:
        # Non-destructive migration: legacy rows remain readable. NULL means the
        # IsCallLost source flag was not persisted by the older application.
        c.execute('ALTER TABLE quality_inbound_facts ADD COLUMN lost INTEGER')
    if 'call_duration' not in cols:
        c.execute('ALTER TABLE quality_inbound_facts ADD COLUMN call_duration REAL')
        # One-time non-destructive backfill for historical imports. PostgreSQL
        # runs this in the startup preflight, never in an interactive GET.
        c.execute('''UPDATE quality_inbound_facts
                     SET call_duration=CAST(NULLIF(json_extract(payload,'$.CallDuration'),'') AS REAL)
                     WHERE call_duration IS NULL AND invalid_duration=0
                       AND NULLIF(json_extract(payload,'$.CallDuration'),'') IS NOT NULL''')
        c.commit()
    c.execute('CREATE INDEX IF NOT EXISTS quality_inbound_day ON quality_inbound_facts(import_id,day,campaign,start)')
    c.execute('CREATE INDEX IF NOT EXISTS quality_inbound_agent ON quality_inbound_facts(import_id,day,agent,start)')
    c.execute('''CREATE TABLE IF NOT EXISTS quality_outbound_imports(
      import_id INTEGER PRIMARY KEY, digest TEXT NOT NULL, version INTEGER NOT NULL,
      rows_count INTEGER NOT NULL, source TEXT NOT NULL, present INTEGER NOT NULL DEFAULT 0,
      published_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quality_outbound_facts(
      import_id INTEGER NOT NULL, row_number INTEGER NOT NULL, day TEXT NOT NULL,
      start REAL NOT NULL, campaign TEXT NOT NULL, campaign_name TEXT NOT NULL, agent TEXT NOT NULL,
      answered INTEGER NOT NULL, lost INTEGER NOT NULL, payload TEXT NOT NULL,
      PRIMARY KEY(import_id,row_number))''')
    c.execute('CREATE INDEX IF NOT EXISTS quality_outbound_day ON quality_outbound_facts(import_id,day,campaign,start)')
    if schema:
        with _SCHEMA_LOCK:_SCHEMA_READY.add(schema)

def _read_tables(raw, filename):
    """Return (inbound, outbound) csv_table tuples from one SIMPLIFY2 ZIP."""
    if not filename.lower().endswith('.zip'):
        return None, None, None, None
    bundle=import_bundle.current(raw,filename)
    if bundle is not None:
        infos=bundle.infos()
        if len(infos)>2000: raise ValueError('Too many files in archive')
        inbound=[i for i in infos if i.filename.lower().endswith('.stats.inbound.csv')]
        outbound=[i for i in infos if i.filename.lower().endswith('.stats.outbound.csv')]
        if len(inbound)>1: raise ValueError('Multiple Stats.INBOUND files: ambiguous scope')
        if len(outbound)>1: raise ValueError('Multiple Stats.OUTBOUND files: ambiguous scope')
        if inbound and inbound[0].file_size>min(MAX_EXPANDED,80*1024*1024): raise ValueError('Stats.INBOUND too large')
        if outbound and outbound[0].file_size>min(MAX_EXPANDED,80*1024*1024): raise ValueError('Stats.OUTBOUND too large')
        in_table=(bundle.memo(('csv_table',inbound[0].filename),lambda:csv_table(bundle.read(inbound[0]))) if inbound else None)
        out_table=(bundle.memo(('csv_table',outbound[0].filename),lambda:csv_table(bundle.read(outbound[0]))) if outbound else None)
        return in_table,out_table,(inbound[0].filename if inbound else ''),(outbound[0].filename if outbound else '')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)>2000: raise ValueError('Too many files in archive')
        inbound=[i for i in infos if i.filename.lower().endswith('.stats.inbound.csv')]
        outbound=[i for i in infos if i.filename.lower().endswith('.stats.outbound.csv')]
        if len(inbound)>1: raise ValueError('Multiple Stats.INBOUND files: ambiguous scope')
        if len(outbound)>1: raise ValueError('Multiple Stats.OUTBOUND files: ambiguous scope')
        if inbound and inbound[0].file_size>min(MAX_EXPANDED,80*1024*1024): raise ValueError('Stats.INBOUND too large')
        if outbound and outbound[0].file_size>min(MAX_EXPANDED,80*1024*1024): raise ValueError('Stats.OUTBOUND too large')
        return (csv_table(z.read(inbound[0])) if inbound else None,
                csv_table(z.read(outbound[0])) if outbound else None,
                inbound[0].filename if inbound else '',
                outbound[0].filename if outbound else '')


def _safe_flag(row, column, line):
    try: value=int(row[column])
    except (TypeError,ValueError,KeyError) as exc: raise ValueError(f'Stats.INBOUND line {line}: invalid {column}') from exc
    if value not in (0,1): raise ValueError(f'Stats.INBOUND line {line}: {column} outside 0/1')
    return value


def ingest_inbound(raw, filename, import_id, offset):
    if not filename.lower().endswith('.zip'):
        return {'updated':False,'reason':'Stats.INBOUND not provided'}
    if len(raw)>MAX_BYTES: raise ValueError('Quality archive too large')
    digest=hashlib.sha256(raw+str(offset).encode()).hexdigest()
    with connect() as c:
        ensure_schema(c)
        if c.execute('SELECT 1 FROM quality_inbound_imports WHERE import_id=? AND digest=? AND version=?',
                     (import_id,digest,VERSION)).fetchone():
            return {'updated':False,'reason':'already_applied'}
    inbound,outbound,in_name,out_name=_read_tables(raw,filename)
    if inbound is None:return {'updated':False,'reason':'Stats.INBOUND not provided'}
    fields,rows=inbound
    required={'Date','CampaignID','CampaignName','AgentId','WaitDuration',*FLAGS.values()}
    if required-set(fields):raise ValueError('Stats.INBOUND missing columns: '+', '.join(sorted(required-set(fields))))
    facts=[]
    for n,r in enumerate(rows,2):
        try:
            source={key:_safe_flag(r,column,n) for key,column in FLAGS.items()}
            wait=float(r['WaitDuration'])
            if not math.isfinite(wait):raise ValueError('non-finite wait')
            start=stamp(r['Date'],offset)
            invalid=wait<0
            call_duration=None
            for key in ('CallDuration','WorkDuration','WrapupDuration','ReroutDuration','IvrDuration'):
                if r.get(key,'')!='':
                    value=float(r[key])
                    if not math.isfinite(value):raise ValueError('non-finite duration')
                    invalid=invalid or value<0
                    if key=='CallDuration':call_duration=value
            cid=r['CampaignID'].strip()
            if not cid:raise ValueError('empty CampaignID')
            aid=agent_key(r.get('AgentId',''))
            payload={k:r.get(k,'') for k in ('StatusGroup','StatusCode','StatusDetail','StatusCodeText',
                     'StatusDetailText','CallDuration','WorkDuration','WrapupDuration','IvrDuration','ReroutDuration')}
            facts.append((import_id,n,display(start)[:10],start,cid,r['CampaignName'],aid,
                          source['received'],source['answered'],source['abandoned'],source['closed'],
                          source['overflow'],source['rerouted'],source['before_queue'],source['transferred'],
                          wait,int(invalid),json.dumps(payload,ensure_ascii=False),source['lost'],call_duration))
        except (ValueError,TypeError,OverflowError) as exc:
            raise ValueError(f'Stats.INBOUND line {n}: {exc}') from exc
    outbound_facts=[]
    if outbound is not None:
        out_fields,out_rows=outbound
        out_required={'Date','CampaignID','CampaignName','AgentId','IsCallAnswered','IsCallLost'}
        if out_required-set(out_fields):raise ValueError('Stats.OUTBOUND missing columns: '+', '.join(sorted(out_required-set(out_fields))))
        for n,r in enumerate(out_rows,2):
            try:
                start=stamp(r['Date'],offset);cid=r['CampaignID'].strip()
                if not cid:raise ValueError('empty CampaignID')
                answered=int(r['IsCallAnswered']);lost=int(r['IsCallLost'])
                if answered not in (0,1) or lost not in (0,1):raise ValueError('outbound flag outside 0/1')
                payload={k:r.get(k,'') for k in ('StatusGroup','StatusCode','StatusDetail','StatusCodeText','StatusDetailText','WorkDuration','WrapupDuration')}
                outbound_facts.append((import_id,n,display(start)[:10],start,cid,r['CampaignName'],agent_key(r.get('AgentId','')),
                                       answered,lost,json.dumps(payload,ensure_ascii=False)))
            except (ValueError,TypeError,OverflowError) as exc:
                raise ValueError(f'Stats.OUTBOUND line {n}: {exc}') from exc
    with connect() as c:
        ensure_schema(c)
        c.execute('DELETE FROM quality_inbound_facts WHERE import_id=?',(import_id,))
        c.executemany('''INSERT INTO quality_inbound_facts(
          import_id,row_number,day,start,campaign,campaign_name,agent,received,answered,abandoned,
          closed,overflow,rerouted,before_queue,transferred,wait,invalid_duration,payload,lost,call_duration)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',facts)
        c.execute('INSERT OR REPLACE INTO quality_inbound_imports(import_id,digest,version,rows_count,source) VALUES(?,?,?,?,?)',
                  (import_id,digest,VERSION,len(facts),in_name))
        c.execute('DELETE FROM quality_outbound_facts WHERE import_id=?',(import_id,))
        if outbound_facts:
            c.executemany('''INSERT INTO quality_outbound_facts(
              import_id,row_number,day,start,campaign,campaign_name,agent,answered,lost,payload)
              VALUES(?,?,?,?,?,?,?,?,?,?)''',outbound_facts)
        c.execute('INSERT OR REPLACE INTO quality_outbound_imports(import_id,digest,version,rows_count,source,present) VALUES(?,?,?,?,?,?)',
                  (import_id,digest,VERSION,len(outbound_facts),out_name,int(outbound is not None)))
    return {'updated':True,'rows':len(facts),'outbound_rows':len(outbound_facts),'version':VERSION}


def _version_ready(version):
    try:return int(version) in SUPPORTED_VERSIONS
    except (TypeError,ValueError):return False


def _outbound_known(c, import_ids):
    ids=sorted({int(x) for x in import_ids})
    if not ids:return False
    rows=c.execute('SELECT import_id,present FROM quality_outbound_imports WHERE import_id IN ('+','.join('?'*len(ids))+')',ids).fetchall()
    present={int(r['import_id']):int(r['present']) for r in rows}
    return all(present.get(i)==1 for i in ids)


def _classification_examples(c, where, params, limit=20):
    assigned=agent_assigned_sql('f');hits=principal_hits_sql('f')
    sql=f'''SELECT row_number,start,agent,campaign,closed,overflow,rerouted,before_queue,abandoned,answered,lost,
      {hits} AS class_hits FROM quality_inbound_facts f WHERE ({where}) AND ({hits}<>1)
      ORDER BY start,row_number LIMIT ?'''
    out=[]
    for row in c.execute(sql,[*params,int(limit)]):
        r=dict(row);r['start_text']=display(r.pop('start'))
        labels=[]
        if r['closed']:labels.append('closed')
        if r['overflow']:labels.append('overflow')
        unassigned=str(r.get('agent') or '').strip().upper() in ('','0','S0')
        if unassigned and r['rerouted']:labels.append('rerouted_no_agent')
        if r['before_queue']:labels.append('hangup_before_queue')
        if r['abandoned']:labels.append('abandoned')
        if not unassigned:labels.append('treated_agent')
        r['classes']=labels;r['issue']='unclassified' if not labels else 'double_classified'
        out.append(r)
    return out


def overview(qs, *, connection=None, agents_only=False):
    get=lambda k,d='':str(qs.get(k,[d])[0]).strip()
    from contextlib import nullcontext
    with (nullcontext(connection) if connection is not None else connect()) as c:
        # In production PostgreSQL the runtime preflight owns DDL. Do not run
        # CREATE TABLE/INDEX from an interactive analytics GET: it can wait on
        # metadata locks while imports/live writers are active. SQLite keeps
        # the historical self-initializing behavior.
        if not getattr(c,'schema',None):
            ensure_schema(c)
        if connection is None:
            from db_compat import begin_read_snapshot
            begin_read_snapshot(c)
        latest=c.execute('SELECT MAX(day) FROM call_coverage').fetchone()[0]
        first=get('date_from',latest or date.today().isoformat())
        last=get('date_to',first)
        a,b=date.fromisoformat(first),date.fromisoformat(last)
        if b<a or (b-a).days>365:raise ValueError('Choose a period from 1 to 366 days')
        t1,t2=get('time_from'),get('time_to')
        if not t1 and not t2 and get('work_hours')=='1':
            settings=config();t1,t2=settings['work_start'],settings['work_end']
        if bool(t1)!=bool(t2):raise ValueError('Both start and end times are required')
        if t1 or t2:
            from datetime import datetime
            t1=datetime.strptime(t1,'%H:%M').strftime('%H:%M')
            t2=datetime.strptime(t2,'%H:%M').strftime('%H:%M')
            if t1>=t2:raise ValueError('End time must be after start time')
        threshold=int(get('threshold','60'))
        if not 1<=threshold<=3600:raise ValueError('Threshold must be between 1 and 3600 seconds')
        page=int(get('page','0'))
        if not 0<=page<=100000:raise ValueError('Invalid page')
        campaign=get('campaign');group=get('group');service=get('service');agent=agent_key(get('agent'))
        coverage=[];clauses=[];params=[];selected_import_ids=[];selected_days=[]
        refs={r['day']:r for r in c.execute("""SELECT cc.day,cc.import_id,q.version,q.published_at,q.source
            FROM call_coverage cc LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id
            WHERE cc.day BETWEEN ? AND ?""",(first,last))}
        for d in (a+timedelta(days=i) for i in range((b-a).days+1)):
            day=d.isoformat();ref=refs.get(day);ready=bool(ref and _version_ready(ref['version']))
            coverage.append({'day':day,'status':'available' if ready else 'missing',
                             'import_id':ref['import_id'] if ref else None,
                             'published_at':ref['published_at'] if ready else None,
                             'logic_version':int(ref['version']) if ready else None,
                             'needs_refresh':bool(ready and int(ref['version'])<VERSION)})
            if ready:
                lo,hi=day_bounds(day,t1,t2) if t1 else day_bounds(day)
                selected_days.append((ref['import_id'],day,lo,hi))
                selected_import_ids.append(ref['import_id'])
        # PostgreSQL: avoid a 30-366 branch OR predicate.  It caused the planner
        # to spend far too long on historical Quality requests.  Use the indexed
        # import/day/start range as the main predicate and only apply a local-time
        # work-hour test when a partial day is requested.  SQLite keeps the old
        # exact per-day predicate for regression compatibility.
        if selected_days and getattr(c,'schema',None):
            imports=sorted({int(x[0]) for x in selected_days})
            global_lo=min(float(x[2]) for x in selected_days);global_hi=max(float(x[3]) for x in selected_days)
            where='f.import_id IN ('+','.join('?'*len(imports))+') AND f.day BETWEEN ? AND ? AND f.start>=? AND f.start<?'
            params=[*imports,first,last,global_lo,global_hi]
            if t1:
                where+=" AND to_char(to_timestamp(f.start) AT TIME ZONE 'Europe/Paris','HH24:MI')>=? AND to_char(to_timestamp(f.start) AT TIME ZONE 'Europe/Paris','HH24:MI')<?"
                params.extend((t1,t2))
        else:
            for iid,day,lo,hi in selected_days:
                clauses.append('(f.import_id=? AND f.day=? AND f.start>=? AND f.start<?)')
                params.extend((iid,day,lo,hi))
            where='('+' OR '.join(clauses)+')' if clauses else 'FALSE'
        if agents_only:
            return dict(available_days=sum(x['status']=='available' for x in coverage),
                        agents=handled_agents(c,where,params))
        catalog={}
        for row in c.execute('SELECT DISTINCT campaign,campaign_name FROM quality_inbound_facts f WHERE '+where,params):
            item=catalog.setdefault(row['campaign'],dict(campaign=row['campaign'],campaign_name=row['campaign_name'],names=[]))
            item['names'].append(row['campaign_name'])
        # Groups are scoped from configured files (queues), never from campaign
        # links entered on the group itself. Queue -> campaign correspondence comes
        # from the Quality configuration snapshot.
        from quality_scope import load_quality_file_scope
        file_scope=load_quality_file_scope()
        period_ids=set(catalog)
        groups=[]
        for g in file_scope.get('groups',[]):
            item=dict(g)
            item['campaign_ids']=sorted(period_ids & set(g.get('campaign_ids',[])))
            item['campaign_count']=len(item['campaign_ids'])
            groups.append(item)
        services=sorted({str(g.get('service_name') or '').strip() for g in groups if str(g.get('service_name') or '').strip()},key=str.casefold)
        service_cf=service.casefold()
        if service and not any(x.casefold()==service_cf for x in services):raise ValueError('Service inconnu : actualisez les filtres')
        selected=next((g for g in groups if g['id']==group),None) if group else None
        if group and selected is None:raise ValueError('Groupe inconnu : actualisez les filtres')
        if selected is not None and service_cf and str(selected.get('service_name') or '').casefold()!=service_cf:
            raise ValueError('Ce sous-groupe n’appartient pas au service sélectionné')
        selected_groups=([selected] if selected is not None else ([g for g in groups if service_cf and str(g.get('service_name') or '').casefold()==service_cf] if service_cf else []))
        if selected_groups:
            # Group membership is defined by ACTIVE agent assignments on the
            # group's configured files. Campaign mapping is only a fallback for
            # rows that have no agent (abandoned/closed/before-queue, etc.).
            members=sorted({agent_key(x) for g in selected_groups for x in g.get('member_agent_ids',[]) if agent_key(x)})
            ids=sorted({str(x) for g in selected_groups for x in g.get('campaign_ids',[]) if str(x)})
            parts=[];gparams=[]
            if members:
                parts.append('f.agent IN ('+','.join('?'*len(members))+')');gparams.extend(members)
            if ids:
                parts.append('('+agent_unassigned_sql('f')+' AND f.campaign IN ('+','.join('?'*len(ids))+'))');gparams.extend(ids)
            if parts:
                where+=' AND ('+' OR '.join(parts)+')';params.extend(gparams)
            else:
                where+=' AND FALSE'
        if not selected_groups:
            choices=sorted(catalog.values(),key=lambda item:(item['campaign_name'].casefold(),item['campaign']))
        else:
            # Offer every campaign actually present after the group predicate,
            # including campaigns handled by active group agents even when the
            # file->campaign catalogue is incomplete.
            visible={}
            for row in c.execute('SELECT DISTINCT campaign,campaign_name FROM quality_inbound_facts f WHERE '+where,params):
                visible[row['campaign']]=dict(campaign=row['campaign'],campaign_name=row['campaign_name'],names=[row['campaign_name']])
            choices=sorted(visible.values(),key=lambda item:(item['campaign_name'].casefold(),item['campaign']))
        if campaign:
            if selected_groups and campaign not in {str(x.get('campaign')) for x in choices}:
                raise ValueError('Cette campagne ne contient aucun appel du périmètre sélectionné')
            where+=' AND f.campaign=?';params.append(campaign)
        # Agent choices are built after the date/group/campaign perimeter, before
        # an optional agent restriction. This keeps the dropdown stable.
        agent_choices=handled_agents(c,where,params)
        if agent:
            where+=' AND f.agent=?';params.append(agent)
        metric=aggregate_sql('f','?')
        outbound_known=_outbound_known(c,selected_import_ids)
        outbound_where=where.replace('f.','o.')
        outbound_total=(c.execute('SELECT COUNT(*) FROM quality_outbound_facts o WHERE '+outbound_where,params).fetchone()[0]
                        if outbound_known else None)
        total=decorate(c.execute('SELECT '+metric+' FROM quality_inbound_facts f WHERE '+where,[threshold,*params]).fetchone(),threshold,outbound_total)
        outbound_by_campaign={}
        if outbound_known and not campaign:
            for r in c.execute('SELECT o.campaign,COUNT(*) AS n FROM quality_outbound_facts o WHERE '+outbound_where+' GROUP BY o.campaign',params):
                outbound_by_campaign[r['campaign']]=r['n']
        campaigns=[]
        for r in c.execute('SELECT campaign,MAX(campaign_name) AS campaign_name,'+metric+
                           ' FROM quality_inbound_facts f WHERE '+where+' GROUP BY campaign ORDER BY received DESC,campaign',[threshold,*params]):
            campaigns.append(decorate(r,threshold,outbound_by_campaign.get(r['campaign']) if outbound_known else None))
        details=[]
        if get('detail')=='1':
            for r in c.execute('''SELECT row_number,start,agent,campaign,received,answered,abandoned,closed,overflow,rerouted,before_queue,transferred,lost,wait,invalid_duration
                                  FROM quality_inbound_facts f WHERE '''+where+' ORDER BY start,row_number LIMIT 50 OFFSET ?',[*params,page*50]):
                r=dict(r);r['start_text']=display(r.pop('start'));details.append(r)
        available=sum(x['status']=='available' for x in coverage)
        agents=(agent_choices if not agent else handled_agents(c,where,params))
        hourly=hourly_abandons(c,where,params,t1,t2,available)
        integrity={'ok':None,'checks':[],'coherence_delta':None,'examples':[]}
        if available:
            fields=('received','treated_agent','answered','abandoned','closed','overflow','rerouted_no_agent','hangup_before_queue','ignored')
            campaign_totals={k:sum(int(r.get(k) or 0) for r in campaigns) for k in fields}
            checks=[{'name':'source_durations_valid','ok':total['invalid_durations']==0,'actual':total['invalid_durations'],'expected':0,'severity':'warning'}]
            for key in fields:
                expected=int(total.get(key) or 0);actual=campaign_totals[key]
                checks.append({'name':'campaign_'+key,'ok':actual==expected,'expected':expected,'actual':actual})
            agent_handled=sum(int(r.get('handled') or 0) for r in agents)
            checks.append({'name':'agents_treated','ok':agent_handled==int(total.get('treated_agent') or 0),
                           'expected':int(total.get('treated_agent') or 0),'actual':agent_handled})
            hourly_abandoned=sum(int(r.get('abandoned') or 0) for r in hourly)
            checks.append({'name':'hourly_abandoned','ok':hourly_abandoned==int(total.get('abandoned') or 0),
                           'expected':int(total.get('abandoned') or 0),'actual':hourly_abandoned})
            expected_den=int(total.get('received') or 0)-int(total.get('closed') or 0)-int(total.get('hangup_before_queue') or 0)
            checks.append({'name':'qos_denominator','ok':expected_den==int(total.get('qos_denominator') or 0),
                           'expected':expected_den,'actual':int(total.get('qos_denominator') or 0)})
            checks.append({'name':'qos_numerator','ok':int(total.get('treated_agent') or 0)==int(total.get('qos_numerator') or 0),
                           'expected':int(total.get('treated_agent') or 0),'actual':int(total.get('qos_numerator') or 0)})
            checks.append({'name':'treated_subpartition','ok':bool(total.get('treated_subcategory_ok')),
                           'expected':int(total.get('treated_agent') or 0),'actual':int(total.get('treated_subtotal') or 0),
                           'delta':int(total.get('treated_subcategory_delta') or 0)})
            checks.append({'name':'business_partition','ok':bool(total.get('coherence_ok')),
                           'expected':int(total.get('received') or 0),'actual':int(total.get('classified_total') or 0),
                           'delta':int(total.get('coherence_delta') or 0),'double_classified':int(total.get('double_classified') or 0)})
            integrity={'ok':all(x['ok'] for x in checks if x.get('severity')!='warning'),'checks':checks,
                       'coherence_delta':int(total.get('coherence_delta') or 0),
                       'unclassified':int(total.get('ignored') or 0),
                       'double_classified':int(total.get('double_classified') or 0),
                       'examples':_classification_examples(c,where,params) if not total.get('coherence_ok') else []}
        if not available:
            total={k:None for k in total}
        return dict(version=VERSION,source='Stats.INBOUND',date_from=first,date_to=last,threshold=threshold,
                    coverage=coverage,available_days=available,total_days=len(coverage),total=total,
                    campaigns=campaigns,details=details,page=page,groups=groups,group=group,service=service,services=services,
                    group_name=selected['name'] if selected else '',campaign_choices=choices,agents=agents,
                    agent_choices=agent_choices,agent=agent,
                    hourly_abandons=hourly,integrity=integrity,time_from=t1,time_to=t2,
                    group_basis='Files du groupe → agents ACTIVE ; campagnes seulement pour les appels sans agent',
                    formula_status='QoS Nelyio = traités / (reçus - clôturés - raccrochés avant file)',
                    qs_hermes=None,timezone='Europe/Paris')
