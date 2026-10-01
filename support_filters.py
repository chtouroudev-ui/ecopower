"""Support Nelyio exclusion windows and incident-key helpers."""
import re
from nelyio_time import local_datetime as france_local_datetime

TECH_LABELS={'offline':'Déconnexion prolongée','disconnect_call':'Déconnexion pendant un appel',
             'pause':'Pause prolongée','wrap':'Post-appel prolongé','ready':'Prêt prolongé',
             'audio_signal':'Signal audio','capture_error':'Erreur de capture',
             'capture_gap':'Absence de signal de capture','end_code':'Code de fin non nul',
             'invalid_duration':'Durée incohérente'}
MAX_NORMAL_DISCONNECT_SECONDS=3600

def _minute_label(value):
    value=max(0,min(24*60,int(round(value))))
    if value==24*60:return '24:00'
    return f'{value//60:02d}:{value%60:02d}'

def _parse_excluded_time(value,label):
    value=str(value or '').strip()
    if not value:return None
    m=re.fullmatch(r'(\d{1,2}):(\d{2})',value)
    if not m:raise ValueError(f'{label} invalide. Format attendu : HH:MM.')
    hour=int(m.group(1));minute=int(m.group(2))
    if not (0<=hour<=23 and 0<=minute<=59):raise ValueError(f'{label} invalide.')
    return hour*60+minute

def _support_excluded_slots(qs, respect_mode=True):
    """Return merged local-time windows excluded from technical report logs.

    The rule is deliberately interval based: a disconnect, anomaly or phone call
    is excluded as soon as its interval overlaps a selected window. Adjacent
    selections (12-13 + 13-14) are merged into one continuous 12-14 exclusion.
    An optional custom window is supported by the PDF report builder.
    """
    get=lambda k,d='':qs.get(k,[d])[0]
    if respect_mode:
        mode=str(get('_legacy_exclusion_mode','compat') or 'compat').strip().lower()
        if mode=='policy_only':
            return []
    raw=[]
    if str(get('exclude_12_13','')).strip().lower() in ('1','true','yes','on'):
        raw.append((12*60,13*60))
    if str(get('exclude_13_14','')).strip().lower() in ('1','true','yes','on'):
        raw.append((13*60,14*60))
    custom_from=_parse_excluded_time(get('exclude_custom_from',''),'Heure de début de l’exclusion personnalisée')
    custom_to=_parse_excluded_time(get('exclude_custom_to',''),'Heure de fin de l’exclusion personnalisée')
    if (custom_from is None)!=(custom_to is None):
        raise ValueError('Renseigner les deux heures de l’exclusion personnalisée.')
    if custom_from is not None:
        if custom_to<=custom_from:raise ValueError('La fin de l’exclusion personnalisée doit être après le début.')
        raw.append((custom_from,custom_to))
    if not raw:return []
    raw.sort()
    merged=[]
    for start,end in raw:
        if merged and start<=merged[-1][1]:
            merged[-1]=(merged[-1][0],max(merged[-1][1],end))
        else:
            merged.append((start,end))
    return [(start,end,f'{_minute_label(start)}-{_minute_label(end)}') for start,end in merged]

def _local_minute_of_day(ts,cfg):
    dt=france_local_datetime(ts)
    return dt.hour*60+dt.minute

def _in_support_excluded_slot(ts,cfg,slots):
    minute=_local_minute_of_day(ts,cfg)
    return any(start<=minute<end for start,end,_ in slots)

def _overlaps_support_excluded_slot(start_ts,end_ts,cfg,slots):
    if not slots:return False
    start_dt=france_local_datetime(start_ts)
    end_dt=france_local_datetime(end_ts)
    start_min=start_dt.hour*60+start_dt.minute+start_dt.second/60
    end_min=end_dt.hour*60+end_dt.minute+end_dt.second/60
    if end_dt.date()!=start_dt.date() or end_min<start_min:end_min=24*60
    return any(start_min<slot_end and end_min>slot_start for slot_start,slot_end,_ in slots)

def valid_gap_key(c,key):
    try:
        _,source,start,end=key.split(':');start=float(start);end=float(end)
        if start>=end:return False
        return c.execute('SELECT 1 FROM health_points WHERE source=? AND stamp=?',(source,start)).fetchone() and c.execute('SELECT 1 FROM health_points WHERE source=? AND stamp=?',(source,end)).fetchone()
    except (ValueError,TypeError):return False

