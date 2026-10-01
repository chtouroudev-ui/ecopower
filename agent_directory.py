"""Administration directory/group integration for Support Nelyio."""
import re
import threading
import time
import db_compat as sqlite3
from error_log import log_unexpected_error
import supervision_context as state
from supervision_db import connect, config
from supervision_utils import display

_SUPPORT_CANDIDATE_LOCK=threading.RLock()
_SUPPORT_CANDIDATE_CACHE={'stamp':0.0,'rows':None}
_SUPPORT_CANDIDATE_TTL=15.0

def invalidate_support_directory_cache():
    with _SUPPORT_CANDIDATE_LOCK:
        _SUPPORT_CANDIDATE_CACHE.update(stamp=0.0,rows=None)

def normalize_admin_key(value):
    value=str(value or '').strip()
    if not value:return ''
    if '\\' in value:value=value.rsplit('\\',1)[-1]
    if '/' in value:value=value.rsplit('/',1)[-1]
    if '@' in value:value=value.split('@',1)[0]
    return value.strip().upper()

def admin_key_candidates(value):
    key=normalize_admin_key(value);out=[]
    if key:out.append(key)
    # Hermes360 peut prefixer les identifiants numeriques par S alors que
    # l'annuaire Administration conserve l'identifiant AD/agent sans prefixe.
    if len(key)>1 and key.startswith('S') and key[1:].isdecimal():out.append(key[1:])
    elif key.isdecimal():out.append('S'+key)
    return out

def load_admin_directory():
    # TECHIN_Stock_Manager.db reste la source de verite de l'Administration.
    # Support Nelyio lit cet annuaire sans recopier les utilisateurs.
    result={'available':False,'groups':[],'users':{},'exclusions':set()}
    if not sqlite3.runtime_database_available(state.admin_db_path()):return result
    try:
        con=sqlite3.connect(str(state.admin_db_path()),timeout=5);con.row_factory=sqlite3.Row
        try:
            groups=[dict(r) for r in con.execute('SELECT id,name,description FROM user_groups ORDER BY name COLLATE NOCASE')]
            members={r['user_key']:dict(r) for r in con.execute("SELECT m.user_key,m.user_identifier,m.group_id,g.name AS group_name FROM user_group_members m JOIN user_groups g ON g.id=m.group_id")}
            directory={r['user_key']:dict(r) for r in con.execute('SELECT user_key,user_identifier,first_name,last_name FROM user_directory')}
            try:
                exclusions={normalize_admin_key(r['user_key']) for r in con.execute('SELECT user_key FROM support_agent_exclusions')}
            except sqlite3.Error:
                log_unexpected_error('supervision.load_admin_directory.L74')
                exclusions=set()
        finally:con.close()
    except sqlite3.Error:
        log_unexpected_error('supervision.load_admin_directory.L77')
        return result
    keys=set(members)|set(directory);users={}
    for raw_key in keys:
        d=directory.get(raw_key,{}) or {};m=members.get(raw_key,{}) or {}
        key=normalize_admin_key(raw_key or d.get('user_identifier') or m.get('user_identifier'))
        if not key:continue
        first=str(d.get('first_name') or '').strip();last=str(d.get('last_name') or '').strip()
        identifier=str(d.get('user_identifier') or m.get('user_identifier') or raw_key or '').strip()
        display_name=' '.join(x for x in [first,last] if x).strip() or identifier
        users[key]=dict(user_key=key,user_identifier=identifier,display_name=display_name,
            first_name=first,last_name=last,group_id=m.get('group_id'),group_name=str(m.get('group_name') or ''))
    result.update(available=True,groups=groups,users=users,exclusions=exclusions)
    return result

def admin_user_for(agent,admin_users):
    for key in admin_key_candidates(agent):
        if key in admin_users:return admin_users[key]
    return None

def admin_name_for(agent,admin_users,fallback=''):
    u=admin_user_for(agent,admin_users)
    return (u or {}).get('display_name') or fallback or str(agent or '')

def admin_group_for(agent,admin_users):
    u=admin_user_for(agent,admin_users) or {}
    return u.get('group_id'),u.get('group_name','')

def canonical_admin_key(value):
    key=normalize_admin_key(value)
    if len(key)>1 and key.startswith('S') and key[1:].isdecimal():return key[1:]
    return key


def build_agent_roster(names=None,admin_directory=None,devices=None,*,include_directory=True,exclude_support=True):
    """Return one canonical Agent/Groupe roster for every Nelyio interface.

    Observed SIMPLIFY2 identities are merged with the Administration directory;
    Administration wins for display name and group. Numeric/S-prefixed numeric
    directory identities may be included even when they have no activity in the
    selected period.
    """
    names=names or {};admin_directory=admin_directory or load_admin_directory();devices=devices or {}
    users=admin_directory.get('users',{});rows={};aliases={}
    def add(identifier,fallback=''):
        raw=str(identifier or '').strip();key=canonical_admin_key(raw)
        if not key:return
        user=admin_user_for(raw,users) or users.get(normalize_admin_key(raw)) or {}
        if exclude_support and support_agent_is_excluded(raw,admin_directory):return
        preferred=str(user.get('user_identifier') or raw or key).strip()
        # Keep the actually observed Hermes identity when available; it is the
        # safest value to send back to Support calculations.
        agent=aliases.get(key) or raw or preferred
        if raw:aliases.setdefault(key,raw);agent=aliases[key]
        dev=devices.get(key,{}) or {}
        try:
            from analysis_groups import group_ids_for_agent, group_names_for_agent
            analysis_ids=group_ids_for_agent(raw or preferred or key)
            analysis_names=group_names_for_agent(raw or preferred or key)
        except Exception:
            analysis_ids=[];analysis_names=[]
        rows[key]=dict(agent=agent,name=user.get('display_name') or fallback or names.get(raw) or preferred or key,
            group_id=user.get('group_id'),group_name=user.get('group_name',''),
            group_ids=analysis_ids,group_names=analysis_names,
            pc=dev.get('pc',''),ip=dev.get('ip',''),
            user_key=key,agent_key=key,user_identifier=preferred)
    for agent,name in names.items():add(agent,name)
    if include_directory:
        for user in users.values():
            ident=str(user.get('user_identifier') or user.get('user_key') or '').strip()
            if ident and re.fullmatch(r'S?\d+',normalize_admin_key(ident)):add(ident,user.get('display_name') or ident)
    return sorted(rows.values(),key=lambda r:(str(r.get('name') or r.get('agent')).casefold(),str(r.get('agent') or '')))

def agent_scope_match(agent,name,group_id,filters,*,pc=''):
    """Common Agent/Groupe matcher. Analysis groups come from configured files."""
    f=filters or {};term=str(f.get('agent') or '').strip().lower();groups={str(x) for x in (f.get('groups') or []) if str(x)}
    if term and term not in f"{agent or ''} {name or ''} {pc or ''}".lower():return False
    if groups:
        try:
            from analysis_groups import matches_agent_groups
            if not matches_agent_groups(agent,groups):return False
        except Exception:
            if str(group_id or '') not in groups:return False
    return True

def support_directory_candidates(force=False):
    """Return latest Support/SIMPLIFY2 identities with a short burst cache.

    The source query aggregates the full activities table. Administration used
    to execute it on every reload, even when the user was editing Groups.
    Fifteen seconds is enough to collapse repeated UI reads; the explicit
    Synchroniser action requests `force=True`.
    """
    now=time.monotonic()
    with _SUPPORT_CANDIDATE_LOCK:
        cached=_SUPPORT_CANDIDATE_CACHE.get('rows')
        if not force and cached is not None and now-_SUPPORT_CANDIDATE_CACHE['stamp']<_SUPPORT_CANDIDATE_TTL:
            return [dict(x) for x in cached]
    if not state.db_path().is_file():return []
    with connect() as c:
        rows=[dict(r) for r in c.execute('''
            SELECT a.agent,a.name,a.start,COALESCE(x.passages,0) passages
            FROM activities a
            JOIN (SELECT agent,MAX(id) last_id,COUNT(*) passages FROM activities
                  WHERE TRIM(COALESCE(agent,''))<>'' GROUP BY agent) x ON x.last_id=a.id
            ORDER BY COALESCE(NULLIF(a.name,''),a.agent) COLLATE NOCASE
        ''')]
    out=[];seen=set()
    for r in rows:
        key=canonical_admin_key(r.get('agent'))
        if not key or key in seen:continue
        seen.add(key)
        name=str(r.get('name') or '').strip()
        out.append(dict(user_key=key,user_identifier=key,support_agent=str(r.get('agent') or '').strip(),
                        display_name=name or key,passages=int(r.get('passages') or 0),
                        last_seen=display(r.get('start') or 0,config()['display_offset']) if r.get('start') else ''))
    with _SUPPORT_CANDIDATE_LOCK:
        _SUPPORT_CANDIDATE_CACHE.update(stamp=time.monotonic(),rows=[dict(x) for x in out])
    return out

def sync_admin_groups_from_export(group_map,actor='SUPPORT_GROUP_SYNC'):
    """Import non-empty DistributionGroup values into the Administration groups.

    Existing manual memberships are never overwritten. This lets a SIMPLIFY2
    export enrich the directory safely while preserving Administration as the
    source of truth when an agent was already classified manually.
    """
    if not group_map or not sqlite3.runtime_database_available(state.admin_db_path()):
        return dict(created_groups=0,assigned=0,preserved=0,conflicts=0,available=sqlite3.runtime_database_available(state.admin_db_path()))
    con=sqlite3.connect(str(state.admin_db_path()),timeout=10);con.row_factory=sqlite3.Row
    created_groups=assigned=preserved=conflicts=0
    try:
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'user_directory','user_groups','user_group_members'}.issubset(tables):
            return dict(created_groups=0,assigned=0,preserved=0,conflicts=0,available=False)
        directory={canonical_admin_key(r['user_key']):dict(r) for r in con.execute('SELECT user_key,user_identifier FROM user_directory')}
        memberships={canonical_admin_key(r['user_key']) for r in con.execute('SELECT user_key FROM user_group_members')}
        groups={str(r['name']).strip().casefold():dict(r) for r in con.execute('SELECT id,name FROM user_groups')}
        for key,raw_names in group_map.items():
            names=sorted({' '.join(str(x or '').split())[:60] for x in raw_names if str(x or '').strip()},key=str.casefold)
            if not names:continue
            if len(names)!=1:
                conflicts+=1;continue
            row=directory.get(canonical_admin_key(key))
            if not row:continue
            if canonical_admin_key(key) in memberships:
                preserved+=1;continue
            name=names[0];g=groups.get(name.casefold())
            if not g:
                cur=con.execute('INSERT INTO user_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)',
                    (name,'Import automatique depuis DistributionGroup SIMPLIFY2',actor,actor))
                g={'id':cur.lastrowid,'name':name};groups[name.casefold()]=g;created_groups+=1
            con.execute('INSERT INTO user_group_members(user_key,user_identifier,group_id,created_by) VALUES(?,?,?,?)',
                (row['user_key'],row['user_identifier'],g['id'],actor))
            memberships.add(canonical_admin_key(key));assigned+=1
        con.commit()
    finally:
        con.close()
    return dict(created_groups=created_groups,assigned=assigned,preserved=preserved,conflicts=conflicts,available=True)

def _split_support_name(name):
    clean=' '.join(str(name or '').split()).strip()
    if not clean:return '',''
    parts=clean.split(' ',1)
    return parts[0],parts[1] if len(parts)>1 else ''

def sync_admin_directory_from_support(actor='SUPPORT_SYNC'):
    """Populate missing Administration directory users from Support data.
    Existing non-empty manually configured names are preserved.
    """
    candidates=support_directory_candidates(force=True)
    if not candidates or not sqlite3.runtime_database_available(state.admin_db_path()):
        return dict(created=0,updated=0,candidates=len(candidates),available=sqlite3.runtime_database_available(state.admin_db_path()))
    con=sqlite3.connect(str(state.admin_db_path()),timeout=10);con.row_factory=sqlite3.Row
    created=updated=0
    try:
        # Old project databases may not have been migrated yet.
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'user_directory' not in tables:
            return dict(created=0,updated=0,candidates=len(candidates),available=False)
        existing={str(r['user_key']).upper():dict(r) for r in con.execute('SELECT user_key,user_identifier,first_name,last_name,created_by FROM user_directory')}
        member_keys={str(r[0]).upper() for r in con.execute('SELECT user_key FROM user_group_members')} if 'user_group_members' in tables else set()
        for c in candidates:
            key=canonical_admin_key(c['user_key'])
            aliases=[x for x in admin_key_candidates(c.get('support_agent') or key) if x]
            row_key=next((k for k in aliases if k in existing or k in member_keys),key)
            row=existing.get(row_key)
            first,last=_split_support_name(c.get('display_name'))
            identifier=row.get('user_identifier') if row else row_key
            if not row:
                cur=con.execute('''INSERT OR IGNORE INTO user_directory(user_key,user_identifier,first_name,last_name,created_by,updated_by)
                               VALUES(?,?,?,?,?,?)''',(row_key,identifier,first,last,'SUPPORT_SYNC','SUPPORT_SYNC'))
                if cur.rowcount:
                    created+=1
                existing[row_key]=dict(user_key=row_key,user_identifier=identifier,first_name=first,last_name=last,created_by='SUPPORT_SYNC')
            elif not (str(row.get('first_name') or '').strip() or str(row.get('last_name') or '').strip()) and (first or last):
                con.execute('UPDATE user_directory SET first_name=?,last_name=?,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE user_key=?',
                            (first,last,'SUPPORT_SYNC',row_key))
                updated+=1
        con.commit()
    finally:
        con.close()
    return dict(created=created,updated=updated,candidates=len(candidates),available=True)

def support_agent_is_excluded(agent,admin_directory):
    excluded=admin_directory.get('exclusions',set()) if admin_directory else set()
    return any(canonical_admin_key(k) in excluded or k in excluded for k in admin_key_candidates(agent))

