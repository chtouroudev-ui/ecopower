"""CRUD/validation layer for generic Nelyio Policies."""
import json
import re
from datetime import datetime
from app_db import db_connect
from policy_engine import ALLOWED_MODULES,ALLOWED_TYPES,ACTION_KEYS,policy_snapshot


def _text(v,n=300):return str(v or '').strip()[:n]
def _date(v):
    v=_text(v,10)
    if not v:return None
    datetime.strptime(v,'%Y-%m-%d');return v

def _time(v):
    v=_text(v,5)
    if not v:return None
    datetime.strptime(v,'%H:%M');return v

def _bool(v):return v is True or str(v).lower() in ('1','true','yes','on')


def validate_policy(data):
    name=_text(data.get('name'),100)
    if not name:raise ValueError('Nom de Policy requis')
    ptype=_text(data.get('policy_type','AUTRE'),40).upper().replace(' ','_')
    if ptype not in ALLOWED_TYPES:ptype='AUTRE'
    date_from=_date(data.get('date_from'));date_to=_date(data.get('date_to'))
    if date_from and date_to and date_to<date_from:raise ValueError('La date de fin doit être après la date de début')
    time_from=_time(data.get('time_from'));time_to=_time(data.get('time_to'))
    if bool(time_from)!=bool(time_to):raise ValueError('Renseigner les deux heures ou aucune')
    weekdays=[]
    for x in data.get('weekdays',[]) if isinstance(data.get('weekdays',[]),list) else []:
        try:n=int(x)
        except Exception:continue
        if 0<=n<=6 and n not in weekdays:weekdays.append(n)
    modules=[m for m in (data.get('modules') or []) if str(m) in ALLOWED_MODULES]
    if not modules:modules=['support','analytics','reports','details']
    actions={}
    raw=data.get('actions') if isinstance(data.get('actions'),dict) else {}
    for k in ('exclude_statistics','exclude_lost_time','exclude_score','mark_authorized'):
        actions[k]=_bool(raw.get(k))
    actions['reclassify']=_text(raw.get('reclassify'),80)
    if not any(actions.values()):raise ValueError('Choisir au moins une action')
    targets=[]
    for t in data.get('targets',[]) if isinstance(data.get('targets'),list) else []:
        typ=_text(t.get('target_type'),10).upper();key=_text(t.get('target_key'),120)
        if typ not in ('GLOBAL','GROUP','AGENT'):continue
        if typ=='GLOBAL':key='*'
        if typ!='GLOBAL' and not key:continue
        item={'target_type':typ,'target_key':key}
        if item not in targets:targets.append(item)
    if not targets:targets=[{'target_type':'GLOBAL','target_key':'*'}]
    types={t['target_type'] for t in targets}
    scope=next(iter(types)) if len(types)==1 else 'MIXED'
    try:priority=max(-10000,min(10000,int(data.get('priority',100))))
    except Exception:priority=100
    return dict(name=name,description=_text(data.get('description'),600),enabled=_bool(data.get('enabled',True)),policy_type=ptype,target_scope=scope,
        date_from=date_from,date_to=date_to,weekdays=weekdays,time_from=time_from,time_to=time_to,actions=actions,modules=modules,priority=priority,targets=targets)


def _snapshot_one(con,pid):
    row=con.execute('SELECT * FROM nelyio_policies WHERE id=?',(pid,)).fetchone()
    if not row:return None
    d=dict(row);d['weekdays']=json.loads(d.pop('weekdays_json') or '[]');d['actions']=json.loads(d.pop('action_json') or '{}');d['modules']=json.loads(d.pop('modules_json') or '[]')
    d['targets']=[dict(r) for r in con.execute('SELECT target_type,target_key FROM nelyio_policy_targets WHERE policy_id=? ORDER BY id',(pid,))]
    return d


def save_policy(data,actor):
    clean=validate_policy(data);pid=data.get('id')
    try:pid=int(pid) if pid not in (None,'') else None
    except Exception:raise ValueError('Policy invalide')
    with db_connect() as con:
        old=_snapshot_one(con,pid) if pid else None
        if pid and not old:raise LookupError('Policy introuvable')
        args=(clean['name'],clean['description'],int(clean['enabled']),clean['policy_type'],clean['target_scope'],clean['date_from'],clean['date_to'],json.dumps(clean['weekdays']),clean['time_from'],clean['time_to'],json.dumps(clean['actions'],ensure_ascii=False,separators=(',',':')),json.dumps(clean['modules'],ensure_ascii=False,separators=(',',':')),clean['priority'],actor)
        if pid:
            con.execute('''UPDATE nelyio_policies SET name=?,description=?,enabled=?,policy_type=?,target_scope=?,date_from=?,date_to=?,weekdays_json=?,time_from=?,time_to=?,action_json=?,modules_json=?,priority=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',args+(pid,))
            action='UPDATED'
            con.execute('DELETE FROM nelyio_policy_targets WHERE policy_id=?',(pid,))
        else:
            con.execute('''INSERT INTO nelyio_policies(name,description,enabled,policy_type,target_scope,date_from,date_to,weekdays_json,time_from,time_to,action_json,modules_json,priority,created_by,updated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',args+(actor,))
            pid=int(con.execute('SELECT last_insert_rowid()').fetchone()[0]);action='CREATED'
        for t in clean['targets']:
            con.execute('INSERT INTO nelyio_policy_targets(policy_id,target_type,target_key) VALUES(?,?,?)',(pid,t['target_type'],t['target_key']))
        new=_snapshot_one(con,pid)
        con.execute('INSERT INTO nelyio_policy_audit(policy_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)',(pid,action,json.dumps(old or {},ensure_ascii=False),json.dumps(new or {},ensure_ascii=False),actor))
        con.execute('INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)',(actor,'NELYIO_POLICY_'+action,f'{pid}: {clean["name"]}'))
        con.commit();return new


def set_enabled(pid,enabled,actor):
    with db_connect() as con:
        old=_snapshot_one(con,int(pid))
        if not old:raise LookupError('Policy introuvable')
        con.execute('UPDATE nelyio_policies SET enabled=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(1 if enabled else 0,actor,int(pid)))
        new=_snapshot_one(con,int(pid))
        con.execute('INSERT INTO nelyio_policy_audit(policy_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)',(int(pid),'ENABLED' if enabled else 'DISABLED',json.dumps(old,ensure_ascii=False),json.dumps(new,ensure_ascii=False),actor))
        con.commit();return new


def delete_policy(pid,actor):
    with db_connect() as con:
        old=_snapshot_one(con,int(pid))
        if not old:raise LookupError('Policy introuvable')
        con.execute('UPDATE nelyio_policies SET enabled=0,deleted_at=CURRENT_TIMESTAMP,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(actor,int(pid)))
        con.execute('INSERT INTO nelyio_policy_audit(policy_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)',(int(pid),'DELETED',json.dumps(old,ensure_ascii=False),'{}',actor));con.commit()


def list_audit(pid=None,limit=200):
    with db_connect() as con:
        if pid is None: rows=con.execute('SELECT * FROM nelyio_policy_audit ORDER BY id DESC LIMIT ?',(int(limit),)).fetchall()
        else: rows=con.execute('SELECT * FROM nelyio_policy_audit WHERE policy_id=? ORDER BY id DESC LIMIT ?',(int(pid),int(limit))).fetchall()
        return [dict(r) for r in rows]
