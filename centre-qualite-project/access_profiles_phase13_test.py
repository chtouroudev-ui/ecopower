import json
import sqlite3
from pathlib import Path

import app_config as cfg
import routes_admin_access as ra


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE access_groups(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT COLLATE NOCASE UNIQUE,description TEXT DEFAULT '',created_by TEXT,updated_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE access_group_members(user_id INTEGER PRIMARY KEY,group_id INTEGER NOT NULL,created_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE access_group_permissions(group_id INTEGER,module TEXT,access_level INTEGER,updated_by TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(group_id,module));
CREATE TABLE access_group_interface_permissions(group_id INTEGER,interface_key TEXT,access_level INTEGER,updated_by TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(group_id,interface_key));
CREATE TABLE access_group_scope_policy(group_id INTEGER PRIMARY KEY,scope_mode TEXT DEFAULT 'ALL',default_business_group_id INTEGER,filter_locked INTEGER DEFAULT 0,updated_by TEXT,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE access_group_scopes(access_group_id INTEGER,business_group_id INTEGER,created_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(access_group_id,business_group_id));
CREATE TABLE access_profiles(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT COLLATE NOCASE UNIQUE,description TEXT DEFAULT '',snapshot_json TEXT NOT NULL,created_by TEXT,updated_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE user_groups(id INTEGER PRIMARY KEY,name TEXT,service_name TEXT,description TEXT);
CREATE TABLE sessions(user_id INTEGER,token_hash TEXT);
CREATE TABLE auth_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT,action TEXT,details TEXT,source_ip TEXT);
"""


def make_connect(tmp_path):
    db = tmp_path / 'access.db'
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    con.commit()
    con.close()

    def connect():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c
    return connect, db


def seed_group(connect, name='Source'):
    with connect() as con:
        con.execute("INSERT INTO user_groups(id,name,service_name) VALUES(10,'MED1','MEDICAL')")
        con.execute("INSERT INTO user_groups(id,name,service_name) VALUES(11,'MED2','MEDICAL')")
        gid = con.execute("INSERT INTO access_groups(name,description) VALUES(?,?)", (name, 'desc')).lastrowid
        for key, meta in cfg.ACCESS_INTERFACES.items():
            level = 0
            if key == 'live_supervision': level = 1
            if key == 'live_incidents': level = 2
            con.execute("INSERT INTO access_group_interface_permissions(group_id,interface_key,access_level) VALUES(?,?,?)", (gid, key, level))
        con.execute("INSERT INTO access_group_permissions(group_id,module,access_level) VALUES(?,?,?)", (gid, 'ani', 1))
        con.execute("INSERT INTO access_group_scope_policy(group_id,scope_mode,default_business_group_id,filter_locked) VALUES(?,?,?,?)", (gid, 'SELECTED', 10, 1))
        con.execute("INSERT INTO access_group_scopes(access_group_id,business_group_id) VALUES(?,10)", (gid,))
        con.commit()
        return gid


class Dummy(ra.AdminAccessRoutesMixin):
    def __init__(self, payload=None):
        self.payload = payload or {}
        self.response = None
    def read_json(self): return self.payload
    def client_ip(self): return '127.0.0.1'
    def send_json(self, payload, status=200):
        self.response = (status, payload)
        return self.response


def test_snapshot_copies_interfaces_ani_and_business_scope(tmp_path):
    connect, _ = make_connect(tmp_path)
    gid = seed_group(connect)
    d = Dummy()
    with connect() as con:
        snap = d._access_group_snapshot(con, gid)
    assert snap['interfaces']['live_supervision'] == 1
    assert snap['interfaces']['live_incidents'] == 2
    assert snap['ani'] == 1
    assert snap['scope'] == {'mode':'SELECTED','allowed_group_ids':[10],'default_group_id':10,'filter_locked':True}


def test_apply_profile_replaces_target_without_changing_name_or_members(tmp_path):
    connect, _ = make_connect(tmp_path)
    source = seed_group(connect)
    with connect() as con:
        target = con.execute("INSERT INTO access_groups(name,description) VALUES('Target','x')").lastrowid
        con.execute("INSERT INTO access_group_members(user_id,group_id) VALUES(99,?)", (target,))
        con.execute("INSERT INTO access_group_interface_permissions(group_id,interface_key,access_level) VALUES(?,?,2)", (target,'dashboard'))
        con.commit()
    d = Dummy()
    with connect() as con:
        snap = d._access_group_snapshot(con, source)
        d._apply_access_snapshot(con, target, snap, 'admin')
        con.commit()
    with connect() as con:
        assert con.execute("SELECT name FROM access_groups WHERE id=?",(target,)).fetchone()[0] == 'Target'
        assert con.execute("SELECT group_id FROM access_group_members WHERE user_id=99").fetchone()[0] == target
        assert con.execute("SELECT access_level FROM access_group_interface_permissions WHERE group_id=? AND interface_key='dashboard'",(target,)).fetchone()[0] == 0
        assert con.execute("SELECT access_level FROM access_group_interface_permissions WHERE group_id=? AND interface_key='live_incidents'",(target,)).fetchone()[0] == 2
        assert con.execute("SELECT access_level FROM access_group_permissions WHERE group_id=? AND module='ani'",(target,)).fetchone()[0] == 1
        policy = con.execute("SELECT scope_mode,default_business_group_id,filter_locked FROM access_group_scope_policy WHERE group_id=?",(target,)).fetchone()
        assert tuple(policy) == ('SELECTED',10,1)


def test_stale_profile_never_expands_scope_silently(tmp_path):
    connect, _ = make_connect(tmp_path)
    d = Dummy()
    bad = {'interfaces':{},'ani':0,'scope':{'mode':'SELECTED','allowed_group_ids':[999],'default_group_id':999,'filter_locked':True}}
    with connect() as con:
        try:
            d._normalize_access_snapshot(con, bad)
        except ValueError as exc:
            assert 'supprimé' in str(exc)
        else:
            raise AssertionError('stale business group must fail')


def test_clone_group_copies_rights_but_not_members(tmp_path, monkeypatch):
    connect, _ = make_connect(tmp_path)
    source = seed_group(connect)
    with connect() as con:
        con.execute("INSERT INTO access_group_members(user_id,group_id) VALUES(7,?)", (source,))
        con.commit()
    monkeypatch.setattr(ra, 'db_connect', connect)
    d = Dummy({'source_group_id':source,'name':'MED1 superviseurs copie','description':'clone'})
    d.api_access_group_clone({'id':1,'username':'admin'})
    status, payload = d.response
    assert status == 201 and payload['ok'] is True
    target = payload['id']
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM access_group_members WHERE group_id=?",(target,)).fetchone()[0] == 0
        assert con.execute("SELECT access_level FROM access_group_interface_permissions WHERE group_id=? AND interface_key='live_supervision'",(target,)).fetchone()[0] == 1
        assert con.execute("SELECT default_business_group_id FROM access_group_scope_policy WHERE group_id=?",(target,)).fetchone()[0] == 10


def test_profile_save_duplicate_and_create_group(tmp_path, monkeypatch):
    connect, _ = make_connect(tmp_path)
    source = seed_group(connect)
    monkeypatch.setattr(ra, 'db_connect', connect)
    actor={'id':1,'username':'admin'}
    d = Dummy({'name':'Superviseur MED1','description':'template','source_group_id':source})
    d.api_access_profile_save(actor)
    status, out = d.response
    assert status == 200 and out['ok']
    pid = out['id']
    d.payload={'name':'Superviseur MED1 copie','description':'template','source_profile_id':pid}
    d.api_access_profile_save(actor)
    status, out2 = d.response
    assert status == 200 and out2['id'] != pid
    d.payload={'profile_id':pid,'name':'MED1 depuis profil','description':'créé depuis modèle'}
    d.api_access_group_from_profile(actor)
    status, out3 = d.response
    assert status == 201
    with connect() as con:
        gid=out3['id']
        assert con.execute("SELECT COUNT(*) FROM access_group_members WHERE group_id=?",(gid,)).fetchone()[0] == 0
        assert con.execute("SELECT access_level FROM access_group_interface_permissions WHERE group_id=? AND interface_key='live_supervision'",(gid,)).fetchone()[0] == 1


def test_phase13_routes_and_ui_are_present():
    handler=Path('http_handler.py').read_text(encoding='utf-8')
    ui=Path('static/app.js').read_text(encoding='utf-8')
    schema=Path('app_db.py').read_text(encoding='utf-8')
    assert 'CREATE TABLE IF NOT EXISTS access_profiles' in schema
    for route in ['/api/access-profiles/save','/api/access-profiles/apply','/api/access-profiles/create-group','/api/access-groups/clone']:
        assert route in handler and route in ui
    assert 'Profils d\'accès réutilisables' in ui
    assert 'Dupliquer le profil' in ui
