"""Live Hermes capture ingestion and provisional interval reconstruction."""
from datetime import datetime
import hashlib, re
import details_store
from error_log import log_unexpected_error
import supervision_context as ctx
from supervision_db import connect, config
from supervision_utils import kind, stamp
from support_filters import TECH_LABELS

def ingest(data, *, sync_details=True):
    source=str(data.get('source','')).strip()
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',source):raise ValueError('Identifiant de capture invalide.')
    rows=data.get('rows',[])
    if not isinstance(rows,list) or len(rows)>2000:raise ValueError('Lot limité à 2000 lignes.')
    cfg=config();inserted=0;max_event=None;heartbeat=None
    # Original capture records state transitions. Heartbeat only comes from the
    # patched capture receiving an actual changes.ashx response, never the relay.
    with connect() as c:
        for r in rows:
            line=str(r.get('line',''))
            if len(line)>20000:raise ValueError('Ligne trop longue.')
            ts=stamp(str(r['ts']),cfg['capture_offset'])
            if ts>datetime.now().timestamp()+300:raise ValueError('Horloge de capture dans le futur (>5 minutes).')
            if 'NELYIO_HEARTBEAT' in line:
                heartbeat=max(heartbeat or ts,ts)
                c.execute('INSERT OR IGNORE INTO health_points VALUES(?,?)',(source,ts))
                continue
            record_technical_signal(c,source,ts,line)
            m=re.search(r'\| (ETAT_INITIAL|ETAT) \| Agent ([^|]+) \| ([^|]+)',line)
            if not m:continue
            state=m[3].strip()
            if m[1]=='ETAT':state=state.split(' -> ',1)[-1].strip()
            agent=m[2].strip();campaign=re.search(r'\| client=([^|]*)',line)
            # Content hash makes retries and relay cursor loss idempotent.
            key=hashlib.sha256(f'{source}|{ts}|{agent}|{state}|{line}'.encode()).hexdigest()
            cur=c.execute('INSERT OR IGNORE INTO live_events(event_key,source,agent,start,state,kind,campaign,initial) VALUES(?,?,?,?,?,?,?,?)',
                (key,source,agent,ts,state,kind(state),campaign[1].strip() if campaign else '',int(m[1]=='ETAT_INITIAL')))
            inserted+=cur.rowcount;max_event=max(max_event or ts,ts)
        c.execute('''INSERT INTO health(source,heartbeat,received,last_event,error) VALUES(?,?,?,?,?)
          ON CONFLICT(source) DO UPDATE SET heartbeat=CASE WHEN COALESCE(health.heartbeat,0)>COALESCE(excluded.heartbeat,0) THEN health.heartbeat ELSE excluded.heartbeat END,
          last_event=CASE WHEN COALESCE(health.last_event,0)>COALESCE(excluded.last_event,0) THEN health.last_event ELSE excluded.last_event END,received=excluded.received,error=excluded.error''',
          (source,heartbeat,datetime.now().timestamp(),max_event,str(data.get('error',''))[:300]))
    if not sync_details:
        return dict(inserted=inserted,accepted=len(rows),details_sync={'deferred':True})
    try:details_sync=details_store.sync_from_sources(ctx.db_path(),ctx.admin_db_path(),TECH_LABELS,force=False)
    except Exception as exc:
        log_unexpected_error('supervision.ingest.L664')
        details_sync={'ok':False,'error':str(exc)}
    return dict(inserted=inserted,accepted=len(rows),details_sync=details_sync)

def live_intervals(c,a,b,cfg,clock):
    # Bound interval length at any gap in the observed capture heartbeats.
    # Original unpatched capture retains transitions, but cannot prove continuity.
    events=c.execute('''SELECT * FROM live_events WHERE start>=? AND start<? ORDER BY source,agent,start,event_key''',(a-86400,b)).fetchall()
    points={}
    for r in c.execute('SELECT source,stamp FROM health_points WHERE stamp>=? AND stamp<=? ORDER BY stamp',(a-86400,b+cfg['stale_seconds'])):
        points.setdefault(r['source'],[]).append(r['stamp'])
    segments={}
    for source,ps in points.items():
        ss=[]
        for p in ps:
            if not ss or p-ss[-1][1]>cfg['stale_seconds']:ss.append([p,p])
            else:ss[-1][1]=p
        segments[source]=ss
    import bisect
    grouped={}
    for e in events:grouped.setdefault((e['source'],e['agent']),[]).append(dict(e))
    result=[]
    for (source,agent),es in grouped.items():
        ss=segments.get(source,[]);starts=[x[0] for x in ss]
        for i,e in enumerate(es):
            nxt=es[i+1]['start'] if i+1<len(es) else min(clock,b)
            start=e['start'];idx=bisect.bisect_right(starts,start+5)-1
            segment=ss[idx] if idx>=0 else None
            if segment and segment[0]<=start+5 and start<=segment[1]+5:
                end=min(nxt,segment[1],clock,b)
                continuous=nxt<=segment[1]+5 and i+1<len(es)
            else:
                end=start;continuous=False
            if end<a or start>=b:continue
            result.append(dict(key='live:'+e['event_key'],agent=agent,name='',start=max(start,a),end=max(max(start,a),end),
                state=e['state'],kind=e['kind'],campaign=e['campaign'],source='capture',
                quality='Provisoire' if continuous and not e['initial'] else 'Observation partielle',
                initial=bool(e['initial']),observed_start=start,collector=source))
    return result

def record_technical_signal(c,source,ts,line):
    agent_match=re.search(r'\| Agent ([^|]+)',line)
    agent=agent_match[1].strip() if agent_match else ''
    category=None
    if 'DECONNEXION_EN_APPEL' in line:category='disconnect_call'
    elif 'MICRO_ERREUR' in line:category='audio_signal'
    elif any(x in line for x in ['ERREUR_CAPTURE','ERREUR_SCRIPT','AVERTISSEMENT_BUFFER_DEVTOOLS','WATCHDOG']):category='capture_error'
    m=re.search(r'\| ETAT \| Agent [^|]+ \| ([^|]+)',line)
    if m and ' -> ' in m[1]:
        old,new=m[1].split(' -> ',1)
        if kind(old)=='call' and kind(new)=='offline':category='disconnect_call'
    if not category:return
    key=hashlib.sha256(f'{source}|{int(ts)}|{agent}|{category}'.encode()).hexdigest()
    detail={'disconnect_call':'Transition appel → déconnecté ou signal de la capture. Cause à vérifier.',
            'audio_signal':'La capture signale un état audio anormal. Vérifier casque, navigateur et autorisations.',
            'capture_error':'Erreur ou redémarrage signalé par le programme de capture.'}[category]
    c.execute('INSERT OR IGNORE INTO technical_signals(signal_key,source,agent,start,category,detail) VALUES(?,?,?,?,?,?)',(key,source,agent,ts,category,detail))

