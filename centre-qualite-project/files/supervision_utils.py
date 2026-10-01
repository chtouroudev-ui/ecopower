"""Pure time, state and range helpers shared by supervision modules."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import csv, html, io
from nelyio_time import day_bounds as france_day_bounds, display as france_display


def latest_agent_names(con, agent_ids=None):
    """Latest display name per agent without rescanning the whole retention.

    Production evidence (25/09/2026) showed the historical DISTINCT ON path
    sorting about 607k activity rows to return about 103 names (2.5-3.6 s).
    Names are a display catalogue, not a historical KPI. For an unscoped
    catalogue use only the newest ACTIVE coverage import; Administration still
    overrides names in Support/Analytics. Explicit ids keep an exact per-agent
    historical lookup, which stays bounded because the id list is small.
    """
    import db_compat
    ids=sorted({str(x) for x in (agent_ids or []) if str(x).strip()})
    if db_compat.postgres_enabled():
        if ids:
            marks=','.join('?'*len(ids))
            sql=f"""SELECT DISTINCT ON (agent) agent,name FROM activities
                    WHERE TRIM(COALESCE(agent,''))<>'' AND agent IN ({marks})
                    ORDER BY agent,import_id DESC,id DESC"""
            params=ids
        else:
            # A display catalogue must include every agent present in the
            # authoritative covered imports. Restricting this to only the
            # newest coverage import made valid group members disappear from
            # Support/Calls/Analytics when the newest export did not contain
            # every active agent.
            sql="""SELECT DISTINCT ON (a.agent) a.agent,a.name
                   FROM activities a
                   JOIN (SELECT DISTINCT import_id FROM coverage) cov ON cov.import_id=a.import_id
                   WHERE TRIM(COALESCE(a.agent,''))<>''
                   ORDER BY a.agent,a.import_id DESC,a.id DESC"""
            params=[]
    else:
        params=[]
        where="TRIM(COALESCE(agent,''))<>''"
        if ids:
            where+=' AND agent IN ('+','.join('?'*len(ids))+')'
            params.extend(ids)
            sql=f"""SELECT agent,name FROM (
                    SELECT agent,name,ROW_NUMBER() OVER (PARTITION BY agent ORDER BY import_id DESC,id DESC) AS rn
                    FROM activities WHERE {where}
                  ) q WHERE rn=1"""
        else:
            sql="""SELECT agent,name FROM (
                    SELECT a.agent,a.name,ROW_NUMBER() OVER (PARTITION BY a.agent ORDER BY a.import_id DESC,a.id DESC) AS rn
                    FROM activities a
                    JOIN (SELECT DISTINCT import_id FROM coverage) cov ON cov.import_id=a.import_id
                    WHERE TRIM(COALESCE(a.agent,''))<>''
                  ) q WHERE rn=1"""
    return {r['agent']:r['name'] for r in con.execute(sql,params)}

def kind(state):
    s=html.unescape(state or '').strip().lower()
    if 'déconnect' in s or 'deconnect' in s or s in ('logout','départ'):return 'offline'
    if 'pause' in s:return 'pause'
    if 'post' in s or 'wrap' in s:return 'wrap'
    if 'prêt' in s or 'pret' in s or 'waiting' in s or 'disponible' in s:return 'ready'
    # Hermes/SIMPLIFY2 exports can use English ActionName values.
    # V60.4 only recognized French call labels, so Inbound call / Manual call /
    # Dialing / Consultation were stored as 'other'. Diagnostic Nelyio then
    # had no exported call ranges and displayed 0 disconnects during calls.
    if (
        'appel' in s or 'en ligne' in s or 'numérotation' in s
        or s in ('call','inbound call','outbound call','manual call','dialing','consultation')
    ):return 'call'
    if 'arrivée' in s or s=='login':return 'arrival'
    return 'other'

def stamp(value, offset):
    try:d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:d=datetime.strptime(value,'%m/%d/%Y %I:%M:%S %p')
    if d.tzinfo is None:d=d.replace(tzinfo=timezone(timedelta(minutes=offset)))
    return d.timestamp()

def display(t, offset=None):return france_display(t)

def day_bounds(day, cfg, work=True):
    if work:return france_day_bounds(day,cfg['work_start'],cfg['work_end'])
    return france_day_bounds(day)

def selected_bounds(day,cfg,qs,default_full_day='1'):
    """Return the selected local time window for one day.

    time_from/time_to override the legacy full_day selector. This makes it
    possible to compare precise slots such as 12:00-13:00 or 13:00-14:00.
    """
    get=lambda k,d='':qs.get(k,[d])[0]
    time_from=get('time_from').strip();time_to=get('time_to').strip()
    if time_from or time_to:
        if not time_from or not time_to:raise ValueError('Renseigner à la fois l’heure de début et l’heure de fin.')
        try:
            start=datetime.strptime(time_from,'%H:%M');end=datetime.strptime(time_to,'%H:%M')
        except ValueError as exc:raise ValueError('Plage horaire invalide. Utiliser HH:MM.') from exc
        if (start.hour,start.minute)>=(end.hour,end.minute):raise ValueError('L’heure de fin doit être après l’heure de début.')
        return france_day_bounds(day,time_from,time_to)
    return day_bounds(day,cfg,work=get('full_day',default_full_day)!='1')

def union_seconds(rows):
    ranges=sorted((r['start'],r['end']) for r in rows if r['end']>r['start'])
    total=0;last=-1e30
    for a,b in ranges:
        total+=max(0,b-max(a,last));last=max(last,b)
    return int(total)

def classify_anomaly(r,cfg):
    limit={'pause':cfg['pause_seconds'],'offline':cfg['offline_seconds'],
           'ready':cfg['ready_seconds'],'wrap':cfg['wrap_seconds']}.get(r['kind'])
    if limit is not None and r['duration']>limit:
        return {'pause':'Pause longue','offline':'Déconnexion prolongée','ready':'Attente prolongée — à vérifier','wrap':'Post-travail prolongé'}[r['kind']]
    return ''

def date_range(qs,cfg):
    today=display(datetime.now().timestamp(),cfg['display_offset'])[:10]
    first=qs.get('date_from',qs.get('day',[today]))[0]
    last=qs.get('date_to',[first])[0]
    a=datetime.strptime(first,'%Y-%m-%d');b=datetime.strptime(last,'%Y-%m-%d')
    length=(b-a).days+1
    if not 1<=length<=93:raise ValueError('Choisir une période de 1 à 93 jours, avec la fin après le début.')
    return [(a+timedelta(days=n)).strftime('%Y-%m-%d') for n in range(length)]

def period_buckets(rows,days,cfg,full=False):
    if len(days)==1:
        a,b=day_bounds(days[0],cfg,work=not full);step=3600
        bounds=[(t,min(t+step,b)) for t in range(int(a),int(b),step)]
        return [dict(label=display(a,cfg['display_offset'])[11:16],end_label=display(b,cfg['display_offset'])[11:16],
          value=sum(bool(r.get('anomaly')) and a<=r['start']<b for r in rows)) for a,b in bounds]
    counts=Counter(display(r['start'],cfg['display_offset'])[:10] for r in rows if r.get('anomaly'))
    return [dict(label=d,end_label=d,value=counts[d]) for d in days]

def archive_csv(z,suffix):
    matches=[i for i in z.infolist() if i.filename.lower().endswith(suffix)]
    if not matches:return None
    if len(matches)!=1:raise ValueError('Plusieurs fichiers '+suffix)
    if matches[0].file_size>80*1024*1024:raise ValueError(suffix+' dépasse 80 Mo.')
    return csv.DictReader(io.StringIO(z.read(matches[0]).decode('utf-8-sig')),delimiter=';')

