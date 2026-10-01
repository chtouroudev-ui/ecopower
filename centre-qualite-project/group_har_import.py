"""Import explicit group-file links; agents remain calculated from their assignments."""
import base64
import hashlib
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit
from app_db import db_connect

class Inputs(HTMLParser):
    def __init__(self):
        super().__init__(); self.values={}
    def handle_starttag(self,tag,attrs):
        d=dict(attrs)
        if tag=='input':self.values[d.get('id','')]=d.get('value','')

def ensure_schema(c):
    c.execute('''CREATE TABLE IF NOT EXISTS supervision_group_imports(
      group_id INTEGER PRIMARY KEY REFERENCES user_groups(id) ON DELETE CASCADE,
      captured REAL NOT NULL, digest TEXT NOT NULL)''')

def parse(raw):
    try:entries=json.loads(raw)['log']['entries']
    except (ValueError,KeyError,TypeError) as exc:raise ValueError('HAR invalide') from exc
    groups={}
    if not isinstance(entries,list):raise ValueError('Entrées HAR invalides')
    for e in entries:
        if not isinstance(e,dict):raise ValueError('Entrée HAR invalide')
        if not urlsplit(e.get('request',{}).get('url','')).path.lower().endswith('/main.aspx'):continue
        content=e.get('response',{}).get('content',{});text=content.get('text','')
        if content.get('encoding')=='base64':
            try:text=base64.b64decode(text,validate=True).decode('utf-8-sig')
            except (ValueError,UnicodeError) as exc:raise ValueError('Contenu HAR illisible') from exc
        match=re.search(r'var\s+currentGroupId\s*=\s*(\d+)\s*;',text)
        if not match:continue
        if e.get('response',{}).get('status')!=200:raise ValueError('Page groupe sans réponse valide')
        gid=match[1]
        if gid=='0':continue  # Special default group has different membership semantics.
        p=Inputs();p.feed(text)
        if p.values.get('HumanResourceSupervisionFormID_SelectedGroupId')!=gid:raise ValueError('Identifiant de groupe incohérent')
        name=p.values.get('HumanResourceSupervisionFormID_Description','').strip()
        if not name or len(name)>60:raise ValueError('Nom de groupe invalide')
        try:
            dt=datetime.fromisoformat(e['startedDateTime'].replace('Z','+00:00'))
            if dt.tzinfo is None:raise ValueError('Fuseau absent')
            stamp=dt.timestamp()
        except (KeyError,ValueError,TypeError) as exc:raise ValueError('Date de capture invalide') from exc
        row=dict(id=gid,name=name,captured=stamp)
        for typ in ('Queue',):
            members={}; seen=set()
            calls=re.findall(r'\badd'+typ+r'\(([^\r\n]*)\)\s*;?\s*(?:\r?\n|$)',text)
            if not calls or len(calls)!=len(re.findall(r'\badd'+typ+r'\(',text)):raise ValueError('Liste '+typ+' absente ou tronquée : capture incomplète')
            for args in calls:
                try:
                    # Hermes escapes apostrophes inside double-quoted JS strings.
                    args=re.sub(r"\\(.)", lambda m: "'" if m[1]=="'" else m[0], args)
                    a=json.loads('['+args+']')
                    if len(a)<3 or a[2] not in (0,1):raise ValueError()
                    key=str(a[0]);label=str(a[1])
                    if not key or len(key)>240 or len(label)>300 or key in seen:raise ValueError()
                    seen.add(key)
                    if a[2]:members[key]=label
                except (ValueError,TypeError) as exc:raise ValueError('Liste '+typ+' invalide') from exc
            if typ=='Queue' and any(not k.isdigit() or int(k)<=0 for k in members):raise ValueError('File invalide')
            row[typ]=members
        previous=groups.get(gid)
        if previous and previous['captured']==stamp and previous!=row:raise ValueError('Deux versions contradictoires du groupe')
        if not previous or stamp>=previous['captured']:groups[gid]=row
    if not groups:raise ValueError('Aucun détail de groupe de supervision exploitable')
    return groups

def ingest(raw):
    groups=parse(raw);updated=unchanged=0
    with db_connect() as c:
        c.execute('BEGIN IMMEDIATE');ensure_schema(c)
        for external,g in groups.items():
            # Digest the group itself, not the complete HAR. The same group page
            # can legitimately be captured alongside different unrelated pages.
            digest=hashlib.sha256(json.dumps(g,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
            found=c.execute('SELECT group_id FROM quality_group_meta WHERE supervision_id=?',(external,)).fetchone()
            if found:gid=found[0]
            else:
                same=c.execute('SELECT id FROM user_groups WHERE name=? COLLATE NOCASE',(g['name'],)).fetchall()
                if len(same)>1:raise ValueError('Nom de groupe ambigu')
                if same:
                    gid=same[0][0]
                    meta=c.execute('SELECT supervision_id FROM quality_group_meta WHERE group_id=?',(gid,)).fetchone()
                    if meta and meta[0] and meta[0]!=external:raise ValueError('Conflit de correspondance du groupe')
                else:gid=c.execute('INSERT INTO user_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)',(g['name'],'Groupe de supervision Hermes','GROUP_HAR','GROUP_HAR')).lastrowid
            prior=c.execute('SELECT captured,digest FROM supervision_group_imports WHERE group_id=?',(gid,)).fetchone()
            if prior and prior['captured']>g['captured']:raise ValueError('Capture plus ancienne que le groupe déjà importé : '+g['name'])
            if prior and prior['captured']==g['captured']:
                if prior['digest']==digest:unchanged+=1;continue
                raise ValueError('Même date de capture avec un contenu différent : '+g['name'])
            c.execute('UPDATE user_groups SET name=?,updated_by=? WHERE id=?',(g['name'],'GROUP_HAR',gid))
            c.execute('INSERT INTO quality_group_meta(group_id,supervision_id,source_note) VALUES(?,?,?) ON CONFLICT(group_id) DO UPDATE SET supervision_id=excluded.supervision_id,source_note=excluded.source_note',(gid,external,'group.har'))
            c.execute('DELETE FROM quality_group_lines WHERE group_id=?',(gid,))
            line_rows=[(gid,int(key),'GROUP_HAR') for key in g['Queue']]
            if line_rows:
                c.executemany('INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)',line_rows)
            c.execute('INSERT OR REPLACE INTO supervision_group_imports VALUES(?,?,?)',(gid,g['captured'],digest));updated+=1
    projection = None
    try:
        from quality_scope import invalidate_quality_scope_cache, load_quality_file_scope
        from quality_service import invalidate_quality_priorities_cache
        from group_workspace import invalidate_group_workspace_cache
        invalidate_quality_scope_cache(); invalidate_quality_priorities_cache(); invalidate_group_workspace_cache()
        # Rebuild from the current configured assignment snapshot only. Archive
        # recovery belongs to the Import Worker and never blocks this request.
        projection = load_quality_file_scope(force=True)
    except Exception:
        projection = None
    saved = [g for g in (projection or {}).get('groups', []) if str(g.get('id')) != 'unassigned']
    return dict(status='completed',source_saved=True,groups=updated,unchanged=unchanged,
                projected_agents=sum(int(g.get('member_count') or 0) for g in saved),
                projected_campaigns=sum(int(g.get('campaign_count') or 0) for g in saved),
                assignment_source_available=bool((projection or {}).get('assignment_source_available')),
                assignment_recovered=bool((projection or {}).get('assignment_recovered')),
                assignment_warning=str((projection or {}).get('assignment_warning') or ''),
                message=f'Groupes mis à jour : {updated} ; inchangés : {unchanged}. Projection analytique reconstruite.')
