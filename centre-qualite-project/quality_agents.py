"""Q3 activity metrics: main intervals plus independently identified call holds."""
import hashlib,html,io,json,math,zipfile,threading
import import_bundle
from datetime import date,timedelta,datetime
from collections import defaultdict
from quality_importer import csv_table,agent_key
from supervision_db import connect,config
from supervision_utils import stamp
from nelyio_time import display,day_bounds

_SCHEMA_LOCK=threading.Lock()
_SCHEMA_READY=set()


def ensure_schema(c):
    schema=getattr(c,'schema',None)
    if schema:
        with _SCHEMA_LOCK:
            if schema in _SCHEMA_READY:return
    c.execute('CREATE TABLE IF NOT EXISTS quality_agent_imports(import_id INTEGER PRIMARY KEY,digest TEXT,rows_count INTEGER,hold_reference INTEGER,duplicates INTEGER)')
    c.execute('''CREATE TABLE IF NOT EXISTS quality_agent_facts(import_id INTEGER,row_key TEXT,agent TEXT,name TEXT,
      start REAL,end REAL,kind TEXT,campaign TEXT,session TEXT,invalid INTEGER,
      PRIMARY KEY(import_id,row_key))''')
    c.execute('CREATE INDEX IF NOT EXISTS quality_agent_time ON quality_agent_facts(import_id,start,end,agent)')
    c.execute('CREATE INDEX IF NOT EXISTS quality_agent_member_time ON quality_agent_facts(import_id,agent,start,end)')
    c.execute('''CREATE TABLE IF NOT EXISTS quality_call_holds(
      import_id INTEGER NOT NULL,call_id TEXT NOT NULL,hold_duration REAL NOT NULL DEFAULT 0,hold_segments INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(import_id,call_id))''')
    c.execute('CREATE INDEX IF NOT EXISTS quality_call_holds_session ON quality_call_holds(import_id,call_id)')
    # One-time compatibility backfill for imports created before the dedicated
    # CallID-level hold aggregate existed. SessionID is kept exact; rows only
    # become call evidence when suspicious_calls joins the same ODCalls.ID.
    try:
        have_hold=c.execute("SELECT 1 FROM quality_call_holds LIMIT 1").fetchone()
        old_hold=c.execute("SELECT 1 FROM quality_agent_facts WHERE kind='hold' AND TRIM(COALESCE(session,''))<>'' LIMIT 1").fetchone()
        if not have_hold and old_hold:
            c.execute('''INSERT INTO quality_call_holds(import_id,call_id,hold_duration,hold_segments)
              SELECT import_id,session,SUM(CASE WHEN "end">start THEN "end"-start ELSE 0 END),COUNT(*)
              FROM quality_agent_facts WHERE kind='hold' AND TRIM(COALESCE(session,''))<>''
              GROUP BY import_id,session
              ON CONFLICT(import_id,call_id) DO UPDATE SET
                hold_duration=excluded.hold_duration,hold_segments=excluded.hold_segments''')
    except Exception:
        # Old/partially migrated databases are repaired by normal import replay.
        pass
    if schema:
        with _SCHEMA_LOCK:_SCHEMA_READY.add(schema)


def ingest(raw,filename,ident,offset):
    if len(raw)>100*1024*1024:raise ValueError('Archive trop volumineuse')
    digest=hashlib.sha256(raw+str(offset).encode()).hexdigest()
    with connect() as c:
        ensure_schema(c)
        if c.execute('SELECT 1 FROM quality_agent_imports WHERE import_id=? AND digest=?',(ident,digest)).fetchone():return dict(updated=False,reason='already_applied')
    if filename.lower().endswith('.zip'):
        bundle=import_bundle.current(raw,filename)
        if bundle is not None:
            def read(suffix):
                matches=bundle.matching(suffix)
                if len(matches)>1:raise ValueError('Plusieurs tables '+suffix)
                if not matches:return None
                if matches[0].file_size>80*1024*1024:raise ValueError('Table trop volumineuse')
                return bundle.memo(('csv_table',matches[0].filename),lambda:csv_table(bundle.read(matches[0])))
            table=read('.stats.agent.csv');actions=read('.odactions.csv');states=read('.agentstates.csv')
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                def read(suffix):
                    matches=[i for i in z.infolist() if i.filename.lower().endswith(suffix)]
                    if len(matches)>1:raise ValueError('Plusieurs tables '+suffix)
                    if not matches:return None
                    if matches[0].file_size>80*1024*1024:raise ValueError('Table trop volumineuse')
                    return csv_table(z.read(matches[0]))
                table=read('.stats.agent.csv');actions=read('.odactions.csv');states=read('.agentstates.csv')
    else:table=csv_table(raw);actions=states=None
    if table is None:return dict(updated=False,reason='Stats.AGENT non fourni')
    fields,rows=table
    required={'AgentId','ActionDate','ActionDuration','ActionName','IsSubAction','IsSubPart'}
    if required-set(fields):raise ValueError('Stats.AGENT : colonnes obligatoires absentes')
    # The source dictionary identifies ODActions state 1003. No guess from Stats code 100101 alone.
    hold_reference=bool(actions and states and any(r.get('Context')=='1' and r.get('State')=='1003' and 'hold' in r.get('Description','').lower() for r in states[1]))
    holds=set()
    if hold_reference:
        for r in actions[1]:
            if r.get('Context')=='1' and r.get('State')=='1003':
                holds.add((agent_key(r['AgentId']),r.get('SessionId',''),int(stamp(r['DateUTC'],0))))
    facts={};duplicates=0;unmatched=0;hold_intervals=defaultdict(list)
    for n,r in enumerate(rows,2):
        try:
            aid=agent_key(r['AgentId']);start=stamp(r['ActionDate'],offset);duration=float(r['ActionDuration'])
            if not math.isfinite(duration):raise ValueError('durée non finie')
            sub=int(r['IsSubAction']);part=int(r['IsSubPart'])
            if sub not in (0,1) or part not in (0,1):raise ValueError('indicateur invalide')
            label=html.unescape(r['ActionName']).strip().casefold();session=r.get('SessionID','')
            if part:continue
            if sub:
                key=(aid,session,int(start))
                kind='hold' if session and key in holds else 'unresolved_subaction'
            elif 'coaching' in label:kind='coaching'
            elif 'pause' in label:kind='pause'
            elif label in ('appel entrant','inbound call'):kind='inbound'
            elif label in ('appel manuel','manual call','outbound call'):kind='manual'
            elif label in ('arrivée','départ','logout','login'):continue
            elif label in ('aucun contexte démarré','unknown state',''):kind='unknown'
            elif label in ('prêt','pret','post-travail','supervision','numérotation','sonnerie','consultation'):kind='work'
            else:kind='unknown'
            if not aid:raise ValueError('AgentId vide')
            key=hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if key in facts:duplicates+=1;continue
            unmatched+=kind=='unresolved_subaction'
            name=' '.join(v for v in (r.get('AgentFirstName',''),r.get('AgentLastName','')) if v).strip()
            end=start+max(0,duration)
            facts[key]=(ident,key,aid,name,start,end,kind,r.get('CampaignID',''),session,int(duration<0))
            if kind=='hold' and session and end>start:
                hold_intervals[session].append((start,end))
        except (ValueError,TypeError,OverflowError) as exc:raise ValueError(f'Stats.AGENT ligne {n} : {exc}') from exc
    with connect() as c:
        ensure_schema(c);c.execute('DELETE FROM quality_agent_facts WHERE import_id=?',(ident,))
        c.executemany('INSERT INTO quality_agent_facts VALUES('+','.join('?'*10)+')',facts.values())
        c.execute('DELETE FROM quality_call_holds WHERE import_id=?',(ident,))
        hold_rows=[(ident,session,union(intervals),len(intervals)) for session,intervals in hold_intervals.items()]
        if hold_rows:
            c.executemany('INSERT INTO quality_call_holds(import_id,call_id,hold_duration,hold_segments) VALUES(?,?,?,?)',hold_rows)
        c.execute('INSERT OR REPLACE INTO quality_agent_imports VALUES(?,?,?,?,?)',(ident,digest,len(facts),int(hold_reference),duplicates))
    return dict(updated=True,rows=len(facts),duplicates=duplicates,hold_reference=hold_reference,unmatched_subactions=unmatched,call_holds=len(hold_intervals))


def union(intervals):
    end=-float('inf');total=0.0
    for a,b in sorted(intervals):
        total+=max(0,b-max(a,end));end=max(end,b)
    return total


def _merged(intervals):
    out=[]
    for a,b in sorted((float(a),float(b)) for a,b in intervals if b>a):
        if out and a<=out[-1][1]:
            out[-1]=(out[-1][0],max(out[-1][1],b))
        else:
            out.append((a,b))
    return out


def productive_presence_seconds(presence, excluded):
    """Observed productive time = presence minus pause/coaching overlaps.

    Stats.AGENT labels vary between Hermes exports.  Presence is the stable
    source envelope; explicit work labels remain useful diagnostics but must
    not make an active agent appear as 0 seconds worked.
    """
    base=_merged(presence);cuts=_merged(excluded)
    total=sum(b-a for a,b in base)
    overlap=0.0
    j=0
    for a,b in base:
        while j<len(cuts) and cuts[j][1]<=a:j+=1
        k=j
        while k<len(cuts) and cuts[k][0]<b:
            overlap+=max(0.0,min(b,cuts[k][1])-max(a,cuts[k][0]));k+=1
    return max(0.0,total-overlap)


def _call_distribution(agent, campaign_counts, scope):
    """Allocate handled calls to a file only when the mapping is unambiguous."""
    active_files=set(scope.get('agent_files',{}).get(agent,[]))
    campaign_to_files=scope.get('campaign_to_files',{})
    exact={};other=[]
    for item in campaign_counts:
        cid=str(item.get('campaign') or '')
        count=int(item.get('handled') or 0)
        if count<=0:continue
        candidates=list(campaign_to_files.get(cid,[]))
        own=[q for q in candidates if int(q['line_id']) in active_files]
        pool=own or candidates
        if len(pool)==1:
            q=pool[0];key=int(q['line_id'])
            row=exact.setdefault(key,dict(file_id=key,file_name=q.get('line_name') or f'File {key}',handled=0,campaigns=[],mapping='exact'))
            row['handled']+=count
            row['campaigns'].append(dict(campaign=cid,campaign_name=item.get('campaign_name') or cid,handled=count))
        elif pool:
            other.append(dict(file_id=None,file_name='File ambiguë',handled=count,mapping='ambiguous',
                              campaign=cid,campaign_name=item.get('campaign_name') or cid,
                              candidate_files=[dict(x) for x in pool]))
        else:
            other.append(dict(file_id=None,file_name='File non identifiée',handled=count,mapping='unmapped',
                              campaign=cid,campaign_name=item.get('campaign_name') or cid,candidate_files=[]))
    rows=list(exact.values())+other
    rows.sort(key=lambda r:(0 if r['mapping']=='exact' else 1,-int(r['handled']),str(r['file_name']).casefold()))
    return rows


def view(qs):
    from agent_directory import load_admin_directory,admin_name_for,admin_user_for
    from quality_metrics import ensure_schema as ensure_quality_schema, _version_ready
    from quality_scope import load_quality_file_scope
    from db_compat import begin_read_snapshot
    get=lambda k,d='':str(qs.get(k,[d])[0]).strip()
    cfg=config();scope=load_quality_file_scope()
    with connect() as c:
        # PostgreSQL production schema is validated before the Web/Analytics
        # processes start. Replaying CREATE TABLE/INDEX from a GET can take
        # metadata locks and was visible as multi-second TTFB in the HAR.
        # SQLite/manual mode still self-initializes for compatibility.
        if not getattr(c,'schema',None):
            ensure_schema(c);ensure_quality_schema(c)
        begin_read_snapshot(c)
        latest=c.execute('SELECT MAX(day) FROM coverage').fetchone()[0]
        first=get('date_from',latest or date.today().isoformat());last=get('date_to',first)
        a,b=date.fromisoformat(first),date.fromisoformat(last)
        if b<a or (b-a).days>365:raise ValueError('Choisir une période de 1 à 366 jours')
        t1=get('time_from',cfg['work_start']);t2=get('time_to',cfg['work_end'])
        t1=datetime.strptime(t1,'%H:%M').strftime('%H:%M');t2=datetime.strptime(t2,'%H:%M').strftime('%H:%M')
        if t1>=t2:raise ValueError('Plage horaire invalide')

        groups=[dict(id=str(g['id']),name=g['name'],service_name=str(g.get('service_name') or ''),file_count=int(g.get('file_count') or 0),
                     member_count=int(g.get('member_count') or 0)) for g in scope.get('groups',[])]
        group=get('group');service=get('service');service_cf=service.casefold()
        services=sorted({g['service_name'] for g in groups if g['service_name']},key=str.casefold)
        if service and not any(x.casefold()==service_cf for x in services):raise ValueError('Service inconnu')
        selected=next((g for g in scope.get('groups',[]) if str(g['id'])==group),None) if group else None
        if group and selected is None:raise ValueError('Groupe inconnu')
        if selected is not None and service_cf and str(selected.get('service_name') or '').casefold()!=service_cf:
            raise ValueError('Ce sous-groupe n’appartient pas au service sélectionné')
        selected_groups=([selected] if selected is not None else ([g for g in scope.get('groups',[]) if service_cf and str(g.get('service_name') or '').casefold()==service_cf] if service_cf else []))
        members=(set().union(*(set(g.get('member_agent_ids',[])) for g in selected_groups)) if selected_groups else None)
        requested_agent=agent_key(get('agent')) if get('agent') else ''
        include_distribution=get('include_distribution','0')=='1' or bool(requested_agent)
        if requested_agent:
            if members is not None and requested_agent not in members:
                members=set()
            else:
                members={requested_agent}

        agents=defaultdict(lambda:dict(name='',offline=[],open_departures=0,work=[],presence=[],days=set(),
            pause=[],coach=[],call=[],hold=[],pause_n=0,coach_n=0,call_n=0,hold_n=0,
            call_values=[],hold_values=[],inbound_duration_sum=0.0,inbound_duration_count=0,inbound_fact_duration_sum=0.0,inbound_fact_duration_count=0,unresolved=0,invalid=0,
            call_campaigns=defaultdict(lambda:dict(handled=0,campaign_name='')),
            handled=0,answered=0,wait_sum=0.0,wait_count=0))

        # Activity coverage: quality_agent_facts is preferred, but historical
        # imports can still be read from the core activities table without a reimport.
        refs={r['day']:dict(r) for r in c.execute("""SELECT cov.day,cov.import_id,q.hold_reference
            FROM coverage cov LEFT JOIN quality_agent_imports q ON q.import_id=cov.import_id
            WHERE cov.day BETWEEN ? AND ?""",(first,last))}
        coverage=[];bounds={};enhanced_ids=set();fallback_ids=set();hold_known=True
        for i in range((b-a).days+1):
            day=(a+timedelta(days=i)).isoformat();lo,hi=day_bounds(day,t1,t2);ref=refs.get(day)
            ready=ref is not None
            coverage.append(dict(day=day,available=ready,enhanced=bool(ready and ref.get('hold_reference') is not None)))
            if not ready:
                hold_known=False;continue
            iid=int(ref['import_id']);bounds[iid]=(day,lo,hi)
            if ref.get('hold_reference') is None:
                fallback_ids.add(iid);hold_known=False
            else:
                enhanced_ids.add(iid);hold_known=hold_known and bool(ref['hold_reference'])

        def allowed(aid):return members is None or aid in members
        def positive_day(x,day,begin,end):
            if end>begin:x['days'].add(day)
        def add_interval(x,key,interval):
            if interval[1]>interval[0]:x[key].append(interval)
        def inbound_state(value):
            label=html.unescape(str(value or '')).strip().casefold()
            return label in ('appel entrant','inbound call') or ('appel entrant' in label and 'manuel' not in label)

        # Compact selected-day join: keep PostgreSQL on import/time indexes
        # instead of scanning the global min..max window for every import.
        if enhanced_ids and (members is None or members):
            selected_rows=[];activity_params=[]
            for iid in sorted(enhanced_ids):
                day,lo,hi=bounds[iid];selected_rows.append('(?,?,?,?)');activity_params.extend((iid,day,lo,hi))
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(selected_rows)+') '
            sql=prefix+'SELECT f.*,s.day AS selected_day,s.lo AS selected_lo,s.hi AS selected_hi FROM selected s JOIN quality_agent_facts f ON f.import_id=s.import_id AND f.start<s.hi AND f.end>=s.lo WHERE TRUE'
            if members is not None:
                sql+=' AND f.agent IN ('+','.join('?'*len(members))+')';activity_params.extend(sorted(members))
            for r in c.execute(sql,activity_params):
                day,lo,hi=str(r['selected_day']),float(r['selected_lo']),float(r['selected_hi']);aid=agent_key(r['agent'])
                if not allowed(aid):continue
                x=agents[aid];x['name']=r['name'] or x['name'];kind=r['kind']
                if r['invalid']:x['invalid']+=1;continue
                if kind=='unresolved_subaction':x['unresolved']+=1;continue
                begin,end=max(lo,r['start']),min(hi,r['end'])
                if end<=begin and not (lo<=r['start']<hi):continue
                positive_day(x,day,begin,end);interval=(begin,end)
                if kind!='hold':add_interval(x,'presence',interval)
                if kind in ('work','inbound','manual'):add_interval(x,'work',interval)
                key={'pause':'pause','coaching':'coach','inbound':'call','hold':'hold'}.get(kind)
                if key:
                    add_interval(x,key,interval);x[key+'_n']+=int(lo<=r['start']<hi)
                    if key in ('call','hold') and lo<=r['start']<hi and r['end']>r['start']:
                        x[key+'_values'].append(r['end']-r['start'])

        # Core activities serve two purposes: disconnections for every import,
        # and a compatible fallback for old imports not yet enriched by Q3 facts.
        if bounds and (members is None or members):
            selected_rows=[];activity_params=[]
            for iid in sorted(bounds):
                day,lo,hi=bounds[iid];selected_rows.append('(?,?,?,?)');activity_params.extend((iid,day,lo,hi))
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(selected_rows)+') '
            sql=prefix+"SELECT a.import_id,a.agent,a.name,a.start,a.end,a.state,a.kind,s.day AS selected_day,s.lo AS selected_lo,s.hi AS selected_hi FROM selected s JOIN activities a ON a.import_id=s.import_id AND a.start<s.hi AND a.end>=s.lo WHERE TRUE"
            if members is not None:
                aliases=sorted({alias for aid in members for alias in ((aid,'S'+aid) if str(aid).isdigit() else (aid,))})
                sql+=' AND a.agent IN ('+','.join('?'*len(aliases))+')';activity_params.extend(aliases)
            for r in c.execute(sql,activity_params):
                iid=int(r['import_id']);day,lo,hi=str(r['selected_day']),float(r['selected_lo']),float(r['selected_hi']);aid=agent_key(r['agent'])
                if not allowed(aid):continue
                x=agents[aid];x['name']=x['name'] or r['name'];begin,end=max(lo,r['start']),min(hi,r['end'])
                state=html.unescape(str(r['state'] or '')).strip().casefold();kind=str(r['kind'] or '')
                if kind in ('offline','departure'):
                    if end>begin:
                        x['offline'].append((begin,end));positive_day(x,day,begin,end)
                    elif lo<=r['start']<hi:x['open_departures']+=1
                # Moy. appel entrant is always rebuilt from the core activity
                # rows imported from Stats.AGENT. This works for old imports
                # created before quality_agent_facts existed and avoids a blank
                # value when the enrichment table is incomplete.
                if inbound_state(state) and lo<=r['start']<hi and r['end']>r['start']:
                    x['inbound_duration_sum']+=float(r['end']-r['start'])
                    x['inbound_duration_count']+=1
                if iid not in fallback_ids:continue
                if end<=begin:continue
                positive_day(x,day,begin,end);interval=(begin,end)
                if 'coaching' in state:
                    add_interval(x,'presence',interval);add_interval(x,'coach',interval);x['coach_n']+=int(lo<=r['start']<hi)
                elif 'pause' in state:
                    add_interval(x,'presence',interval);add_interval(x,'pause',interval);x['pause_n']+=int(lo<=r['start']<hi)
                elif state in ('appel entrant','inbound call'):
                    add_interval(x,'presence',interval);add_interval(x,'work',interval);add_interval(x,'call',interval);x['call_n']+=int(lo<=r['start']<hi)
                    if lo<=r['start']<hi:x['call_values'].append(r['end']-r['start'])
                elif state in ('appel manuel','manual call','outbound call') or kind in ('call','ready','wrap') or state in ('prêt','pret','post-travail','supervision','numérotation','sonnerie','consultation'):
                    add_interval(x,'presence',interval);add_interval(x,'work',interval)
                else:
                    add_interval(x,'presence',interval)

        # Agent handled-call ownership prefers Stats.AGENT.  The enriched
        # quality_agent_facts table is used when available; older imports use
        # the core activities table.  Only a day for which no Stats.AGENT
        # source exists may fall back to Stats.INBOUND, preserving historical
        # compatibility without losing transferred-agent interactions on days
        # where Stats.AGENT is present.
        enhanced_source_ids=set()
        if enhanced_ids:
            qmarks=','.join('?'*len(enhanced_ids))
            enhanced_source_ids={int(r[0]) for r in c.execute(
                "SELECT DISTINCT import_id FROM quality_agent_facts WHERE kind='inbound' AND import_id IN ("+qmarks+")",sorted(enhanced_ids))}
        core_source_ids=set()
        if fallback_ids:
            qmarks=','.join('?'*len(fallback_ids))
            core_source_ids={int(r[0]) for r in c.execute(
                "SELECT DISTINCT import_id FROM activities WHERE LOWER(TRIM(state)) IN ('appel entrant','inbound call') AND import_id IN ("+qmarks+")",sorted(fallback_ids))}
        agent_source_ids=enhanced_source_ids|core_source_ids
        agent_source_days={day for day,ref in refs.items() if int(ref['import_id']) in agent_source_ids}

        campaign_names={}
        try:
            for cr in c.execute('SELECT campaign,MAX(campaign_name) AS campaign_name FROM quality_inbound_facts GROUP BY campaign'):
                campaign_names[str(cr['campaign'] or '')]=cr['campaign_name'] or ''
        except Exception:
            campaign_names={}

        def add_handled(agent,day,campaign,count):
            aid=agent_key(agent)
            if not allowed(aid):return
            x=agents[aid];n=int(count or 0);x['handled']+=n
            if n:x['days'].add(str(day))
            if include_distribution:
                cid=str(campaign or '')
                cc=x['call_campaigns'][cid];cc['handled']+=n
                cc['campaign_name']=campaign_names.get(cid) or cc['campaign_name'] or cid

        # New/enriched Stats.AGENT imports: quality_agent_facts already stores
        # normalized agent ids, campaign and SessionID.
        if enhanced_source_ids and (members is None or members):
            rows=[];params=[]
            for iid in sorted(enhanced_source_ids):
                day,lo,hi=bounds[iid];rows.append('(?,?,?,?)');params.extend((iid,day,lo,hi))
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(rows)+') '
            where="f.kind='inbound'"
            if members is not None:
                if members:
                    where+=' AND f.agent IN ('+','.join('?'*len(members))+')';params.extend(sorted(members))
                else:
                    where+=' AND FALSE'
            sql=prefix+'''SELECT f.agent,s.day,f.campaign,
                    COUNT(DISTINCT CASE
                        WHEN TRIM(COALESCE(f.session,''))<>'' THEN f.session
                        ELSE 'row:' || f.row_key
                    END) AS handled
                FROM selected s
                JOIN quality_agent_facts f ON f.import_id=s.import_id AND f.start>=s.lo AND f.start<s.hi
                WHERE '''+where+'''
                GROUP BY f.agent,s.day,f.campaign'''
            for r in c.execute(sql,params):
                add_handled(r['agent'],r['day'],r['campaign'],r['handled'])

        # Historical Stats.AGENT imports: core activities remains available and
        # supports the same SessionID rule without requiring a re-import.
        if core_source_ids and (members is None or members):
            rows=[];params=[]
            for iid in sorted(core_source_ids):
                day,lo,hi=bounds[iid];rows.append('(?,?,?,?)');params.extend((iid,day,lo,hi))
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(rows)+') '
            where="TRIM(COALESCE(a.agent,'')) NOT IN ('','0','S0') AND LOWER(TRIM(a.state)) IN ('appel entrant','inbound call')"
            if members is not None:
                aliases=sorted({alias for aid in members for alias in ((aid,'S'+aid) if str(aid).isdigit() else (aid,))})
                if aliases:
                    where+=' AND a.agent IN ('+','.join('?'*len(aliases))+')';params.extend(aliases)
                else:
                    where+=' AND FALSE'
            sql=prefix+'''SELECT a.agent,s.day,a.campaign,
                    COUNT(DISTINCT CASE
                        WHEN TRIM(COALESCE(a.session,''))<>'' THEN a.session
                        ELSE 'row:' || CAST(a.id AS TEXT)
                    END) AS handled
                FROM selected s
                JOIN activities a ON a.import_id=s.import_id AND a.start>=s.lo AND a.start<s.hi
                WHERE '''+where+'''
                GROUP BY a.agent,s.day,a.campaign'''
            for r in c.execute(sql,params):
                add_handled(r['agent'],r['day'],r['campaign'],r['handled'])

        # Remaining call KPIs (answered flag, wait/ASA and imported call
        # duration) continue to use Stats.INBOUND.  They describe the service
        # call record and must not redefine agent ownership when Stats.AGENT is
        # available.
        # Call KPIs use the authoritative Stats.INBOUND coverage and are independent
        # from activity-import identity.
        call_refs={r['day']:dict(r) for r in c.execute("""SELECT cc.day,cc.import_id,q.version
            FROM call_coverage cc LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id
            WHERE cc.day BETWEEN ? AND ?""",(first,last))}
        call_rows=[];call_params=[];calls_available=0
        for i in range((b-a).days+1):
            day=(a+timedelta(days=i)).isoformat();ref=call_refs.get(day)
            if not (ref and _version_ready(ref.get('version'))):continue
            lo,hi=day_bounds(day,t1,t2);calls_available+=1
            call_rows.append('(?,?,?,?)');call_params.extend((ref['import_id'],day,lo,hi))
        calls_compatible=calls_available==len(coverage) and bool(coverage)
        call_source_days={day for day,ref in call_refs.items() if ref and _version_ready(ref.get('version'))}
        handled_compatible=bool(coverage) and all(str(x['day']) in agent_source_days or str(x['day']) in call_source_days for x in coverage)
        if agent_source_days and all(str(x['day']) in agent_source_days for x in coverage):
            handled_source='Stats.AGENT / Inbound call / SessionID unique'
        elif agent_source_days:
            handled_source='Stats.AGENT prioritaire / Stats.INBOUND fallback si Stats.AGENT absent'
        else:
            handled_source='Stats.INBOUND fallback (Stats.AGENT indisponible)'
        if call_rows:
            prefix='WITH selected(import_id,day,lo,hi) AS (VALUES '+','.join(call_rows)+') '
            where="TRIM(COALESCE(f.agent,'')) NOT IN ('','0','S0')"
            if members is not None:
                if members:
                    where+=' AND f.agent IN ('+','.join('?'*len(members))+')';call_params.extend(sorted(members))
                else:where+=' AND FALSE'
            campaign_cols=(",f.campaign,MAX(f.campaign_name) AS campaign_name" if include_distribution else "")
            group_cols=(",f.campaign" if include_distribution else "")
            sql=prefix+'''SELECT s.import_id AS selected_import,f.agent,f.day'''+campaign_cols+''',COUNT(*) AS handled,
                    COALESCE(SUM(f.answered),0) AS answered,
                    COALESCE(SUM(CASE WHEN f.wait>=0 THEN f.wait ELSE 0 END),0) AS wait_sum,
                    COALESCE(SUM(CASE WHEN f.wait>=0 THEN 1 ELSE 0 END),0) AS wait_count,
                    COALESCE(SUM(CASE WHEN f.invalid_duration=0 AND f.call_duration IS NOT NULL
                                      THEN f.call_duration ELSE 0 END),0) AS call_duration_sum,
                    COALESCE(SUM(CASE WHEN f.invalid_duration=0 AND f.call_duration IS NOT NULL
                                      THEN 1 ELSE 0 END),0) AS call_duration_count
                   FROM selected s JOIN quality_inbound_facts f ON f.import_id=s.import_id AND f.day=s.day AND f.start>=s.lo AND f.start<s.hi
                   WHERE '''+where+''' GROUP BY s.import_id,f.agent,f.day'''+group_cols
            for r in c.execute(sql,call_params):
                aid=agent_key(r['agent']);x=agents[aid];n=int(r['handled'] or 0)
                x['answered']+=int(r['answered'] or 0);x['wait_sum']+=float(r['wait_sum'] or 0);x['wait_count']+=int(r['wait_count'] or 0)
                x['inbound_fact_duration_sum']+=float(r['call_duration_sum'] or 0);x['inbound_fact_duration_count']+=int(r['call_duration_count'] or 0)
                if n:x['days'].add(str(r['day']))
                if str(r['day']) not in agent_source_days:
                    x['handled']+=n
                    if include_distribution:
                        cid=str(r['campaign'] or '')
                        cc=x['call_campaigns'][cid];cc['handled']+=n;cc['campaign_name']=r['campaign_name'] or cc['campaign_name'] or cid

        users=load_admin_directory()['users'];out=[];term=get('search').casefold()
        from identity_resolver import resolve_agent_name, resolve_campaign_name, campaign_catalog as identity_campaign_catalog
        identity_campaigns=identity_campaign_catalog(scope)
        for aid,x in agents.items():
            name=resolve_agent_name(aid,admin_users=users,observed_name=x['name'],configured_name=(scope.get('agent_names') or {}).get(aid,''),fallback='Agent non renseigné')
            if term and term not in (aid+' '+name).casefold():continue
            def mean(key):return sum(x[key+'_values'])/len(x[key+'_values']) if x[key+'_values'] else None
            known=bool(x['presence'])
            campaign_counts=[dict(campaign=cid,campaign_name=resolve_campaign_name(cid,v['campaign_name'] or cid,scope=scope,catalog=identity_campaigns),handled=v['handled']) for cid,v in x['call_campaigns'].items()]
            distribution=_call_distribution(aid,campaign_counts,scope) if include_distribution else []
            out.append(dict(agent=aid,name=name,handled=x['handled'] if handled_compatible else None,answered=x['answered'] if calls_compatible else None,
                asa_seconds=(x['wait_sum']/x['wait_count'] if calls_compatible and x['wait_count'] else None),
                disconnected_seconds=union(x['offline']) if known or x['offline'] else None,disconnected_incomplete=bool(x['open_departures']),
                work_seconds=productive_presence_seconds(x['presence'],x['pause']+x['coach']) if known else None,presence_seconds=union(x['presence']) if known else None,
                worked_days=len(x['days']) if x['days'] else (0 if (known or calls_compatible) else None),
                pause_count=x['pause_n'] if known else None,pause_seconds=union(x['pause']) if known else None,
                coaching_count=x['coach_n'] if known else None,coaching_seconds=union(x['coach']) if known else None,
                call_average=(x['inbound_fact_duration_sum']/x['inbound_fact_duration_count'] if x['inbound_fact_duration_count']
                              else (x['inbound_duration_sum']/x['inbound_duration_count'] if x['inbound_duration_count'] else mean('call'))),
                call_average_count=(x['inbound_fact_duration_count'] if x['inbound_fact_duration_count']
                                    else (x['inbound_duration_count'] if x['inbound_duration_count'] else len(x['call_values']))),
                hold_count=x['hold_n'] if hold_known else None,
                hold_average=mean('hold') if hold_known else None,hold_partial=bool(x['unresolved']),
                unresolved_subactions=x['unresolved'],invalid_durations=x['invalid'],distribution=distribution,
                distribution_loaded=bool(include_distribution),
                distribution_exact=sum(r['handled'] for r in distribution if r['mapping']=='exact') if include_distribution else None,
                distribution_ambiguous=sum(r['handled'] for r in distribution if r['mapping']=='ambiguous') if include_distribution else None,
                distribution_unmapped=sum(r['handled'] for r in distribution if r['mapping']=='unmapped') if include_distribution else None))
        out=sorted(out,key=lambda x:x['name'].casefold());available_days=sum(x['available'] for x in coverage)
        def aggregate(key):
            values=[r[key] for r in out if r.get(key) is not None]
            if not values:return 0 if available_days and not out else None
            return sum(values)
        call_weight=sum((r.get('call_average_count') or 0) for r in out)
        weighted_call=sum((r.get('call_average') or 0)*(r.get('call_average_count') or 0) for r in out)
        summary=dict(agent_count=len(out),handled=aggregate('handled') if handled_compatible else None,
            worked_agent_days=aggregate('worked_days'),work_seconds=aggregate('work_seconds'),presence_seconds=aggregate('presence_seconds'),
            disconnected_seconds=aggregate('disconnected_seconds'),pause_count=aggregate('pause_count'),pause_seconds=aggregate('pause_seconds'),
            coaching_count=aggregate('coaching_count'),coaching_seconds=aggregate('coaching_seconds'),
            call_average=(weighted_call/call_weight if call_weight else None),call_average_count=call_weight)
        checks=[]
        for r in out:
            checks.append({'name':'source_durations_valid','agent':r['agent'],'ok':r['invalid_durations']==0,'value':r['invalid_durations']})
            if r['work_seconds'] is not None and r['presence_seconds'] is not None:
                checks.append({'name':'work_within_presence','agent':r['agent'],'ok':r['work_seconds']<=r['presence_seconds']+1e-6,
                               'work_seconds':r['work_seconds'],'presence_seconds':r['presence_seconds']})
            if r['handled'] is not None and r.get('distribution_loaded'):
                mapped=r['distribution_exact']+r['distribution_ambiguous']+r['distribution_unmapped']
                checks.append({'name':'file_distribution_total','agent':r['agent'],'ok':mapped==r['handled'],'expected':r['handled'],'actual':mapped})
            for key in ('work_seconds','presence_seconds','disconnected_seconds','pause_seconds','coaching_seconds'):
                if r.get(key) is not None:checks.append({'name':'non_negative_'+key,'agent':r['agent'],'ok':r[key]>=0,'value':r[key]})
        integrity={'ok':all(x['ok'] for x in checks) if checks else (True if available_days else None),'checks':checks}
        return dict(date_from=first,date_to=last,time_from=t1,time_to=t2,groups=groups,group=group,service=service,services=services,
            group_name=selected['name'] if selected else '',rows=out,summary=summary,integrity=integrity,
            coverage=coverage,available_days=available_days,total_days=len(coverage),calls_available_days=calls_available,
            calls_compatible=bool(calls_compatible),handled_compatible=bool(handled_compatible),
            handled_source=handled_source,
            membership_basis='Groupe = files configurées ; membre = agent ACTIVE sur au moins une file',
            performance_mode='bulk_queries',file_scope_basis=scope.get('basis','configured_files'))
