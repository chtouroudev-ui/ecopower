"""Routes Administration : governance ; corps V56.8 deplaces sans changement."""
from datetime import datetime, timedelta

from app_db import db_connect, get_setting, now_text, set_setting

from inventory_service import rows_to_dict, followup_config, DEFAULT_FOLLOWUP_LABELS

from policy_admin import save_policy, set_enabled as set_policy_enabled, delete_policy, list_audit

from policy_engine import policy_snapshot

from governance_migration import migration_status, migrate_legacy_exclusions, set_legacy_mode

from declaration_admin import save_declaration, cancel_declaration, delete_declaration, list_audit as list_declaration_audit

from declaration_engine import declaration_snapshot, DECLARATION_TYPES, DEFAULT_ACTIONS


def _scope_sets(user):
    from access_control import effective_group_ids, allowed_agent_ids
    groups=effective_group_ids(user)
    agents=allowed_agent_ids(user)
    return groups,agents

def _targets_allowed(user, targets, allow_global_read=False):
    groups,agents=_scope_sets(user)
    if groups is None:return True
    groups={str(x) for x in groups};agents={str(x) for x in (agents or set())}
    for t in targets or []:
        typ=str((t or {}).get('target_type') or '').upper();key=str((t or {}).get('target_key') or '')
        if typ=='GLOBAL':
            if not allow_global_read:return False
        elif typ=='GROUP':
            if key not in groups:return False
        elif typ=='AGENT':
            if key not in agents:return False
        else:return False
    return True

def _filter_governance_rows(user, rows):
    groups,_agents=_scope_sets(user)
    if groups is None:return list(rows or [])
    # Global rules are visible because they apply to the restricted group, but a
    # restricted supervisor cannot create/modify a global target.
    return [r for r in (rows or []) if _targets_allowed(user,r.get('targets') or [],allow_global_read=True)]


class AdminGovernanceRoutesMixin:
    def api_policies(self, user):
        with db_connect() as con:
            groups=rows_to_dict(con.execute("SELECT id,name,description FROM user_groups ORDER BY name COLLATE NOCASE").fetchall())
            directory=rows_to_dict(con.execute("""SELECT d.user_key,d.user_identifier,d.first_name,d.last_name,COALESCE(m.group_id,0) group_id,COALESCE(g.name,'') group_name FROM user_directory d LEFT JOIN user_group_members m ON m.user_key=d.user_key LEFT JOIN user_groups g ON g.id=m.group_id ORDER BY COALESCE(NULLIF(TRIM(COALESCE(d.first_name,'') || ' ' || COALESCE(d.last_name,'')),''),d.user_identifier) COLLATE NOCASE""").fetchall())
        from access_control import visible_groups, allowed_agent_ids, effective_group_ids
        groups=visible_groups(user,groups)
        allowed_agents=allowed_agent_ids(user)
        if allowed_agents is not None:directory=[x for x in directory if str(x.get('user_key') or x.get('user_identifier') or '') in allowed_agents]
        restricted=effective_group_ids(user) is not None
        self.send_json({"policies":_filter_governance_rows(user,policy_snapshot(include_disabled=True)),"groups":groups,"directory":directory,"audit":([] if restricted else list_audit(limit=100)),"legacy_migration":migration_status()})

    def api_policy_migrate_legacy(self, user):
        data=self.read_json() or {}
        try:result=migrate_legacy_exclusions(data,user["username"])
        except ValueError as exc:return self.send_json({"error":str(exc)},400)
        self.send_json({"ok":True,**result})

    def api_policy_legacy_mode(self, user):
        data=self.read_json() or {}
        try:status=set_legacy_mode(data.get("mode"),user["username"])
        except ValueError as exc:return self.send_json({"error":str(exc)},400)
        self.send_json({"ok":True,"legacy_migration":status})

    def api_policy_save(self, user):
        data=self.read_json() or {}
        if not _targets_allowed(user,data.get('targets') or [],allow_global_read=False):
            return self.send_json({"error":"Policy hors du périmètre métier autorisé."},403)
        try: saved=save_policy(data,user["username"])
        except ValueError as exc:return self.send_json({"error":str(exc)},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True,"policy":saved},201 if not data.get("id") else 200)

    def api_policy_toggle(self, user):
        data=self.read_json() or {}
        target=next((x for x in policy_snapshot(include_disabled=True) if int(x.get('id') or 0)==int(data.get('id') or 0)),None)
        if not target or not _targets_allowed(user,target.get('targets') or [],allow_global_read=False):return self.send_json({"error":"Policy hors du périmètre métier autorisé."},403)
        try: saved=set_policy_enabled(int(data.get("id")),bool(data.get("enabled")),user["username"])
        except (ValueError,TypeError):return self.send_json({"error":"Policy invalide"},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True,"policy":saved})

    def api_policy_delete(self, user):
        data=self.read_json() or {}
        target=next((x for x in policy_snapshot(include_disabled=True) if int(x.get('id') or 0)==int(data.get('id') or 0)),None)
        if not target or not _targets_allowed(user,target.get('targets') or [],allow_global_read=False):return self.send_json({"error":"Policy hors du périmètre métier autorisé."},403)
        try: delete_policy(int(data.get("id")),user["username"])
        except (ValueError,TypeError):return self.send_json({"error":"Policy invalide"},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True})

    def api_declarations(self, user, qs=None):
        qs=qs or {}
        day_from=(qs.get("date_from") or [None])[0]
        day_to=(qs.get("date_to") or [None])[0]
        with db_connect() as con:
            groups=rows_to_dict(con.execute("SELECT id,name,description FROM user_groups ORDER BY name COLLATE NOCASE").fetchall())
            directory=rows_to_dict(con.execute("""SELECT d.user_key,d.user_identifier,d.first_name,d.last_name,COALESCE(m.group_id,0) group_id,COALESCE(g.name,'') group_name FROM user_directory d LEFT JOIN user_group_members m ON m.user_key=d.user_key LEFT JOIN user_groups g ON g.id=m.group_id ORDER BY COALESCE(NULLIF(TRIM(COALESCE(d.first_name,'') || ' ' || COALESCE(d.last_name,'')),''),d.user_identifier) COLLATE NOCASE""").fetchall())
        actions={k:{**v} for k,v in DEFAULT_ACTIONS.items()}
        from access_control import visible_groups, allowed_agent_ids, effective_group_ids
        groups=visible_groups(user,groups);allowed_agents=allowed_agent_ids(user)
        if allowed_agents is not None:directory=[x for x in directory if str(x.get('user_key') or x.get('user_identifier') or '') in allowed_agents]
        restricted=effective_group_ids(user) is not None
        declarations=_filter_governance_rows(user,declaration_snapshot(day_from,day_to,include_cancelled=True,limit=1000))
        self.send_json({
            "declarations":declarations,
            "groups":groups,"directory":directory,"audit":([] if restricted else list_declaration_audit(limit=100)),
            "types":DECLARATION_TYPES,"default_actions":actions,"today":datetime.now().strftime("%Y-%m-%d")
        })

    def api_declaration_save(self, user):
        data=self.read_json() or {}
        if not _targets_allowed(user,data.get('targets') or [],allow_global_read=False):return self.send_json({"error":"Déclaration hors du périmètre métier autorisé."},403)
        try:saved=save_declaration(data,user["username"])
        except ValueError as exc:return self.send_json({"error":str(exc)},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True,"declaration":saved},201 if not data.get("id") else 200)

    def api_declaration_cancel(self, user):
        data=self.read_json() or {}
        target=next((x for x in declaration_snapshot(include_cancelled=True,limit=10000) if int(x.get('id') or 0)==int(data.get('id') or 0)),None)
        if not target or not _targets_allowed(user,target.get('targets') or [],allow_global_read=False):return self.send_json({"error":"Déclaration hors du périmètre métier autorisé."},403)
        try:saved=cancel_declaration(int(data.get("id")),user["username"])
        except (ValueError,TypeError) as exc:return self.send_json({"error":str(exc) or "Déclaration invalide"},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True,"declaration":saved})

    def api_declaration_delete(self, user):
        data=self.read_json() or {}
        target=next((x for x in declaration_snapshot(include_cancelled=True,limit=10000) if int(x.get('id') or 0)==int(data.get('id') or 0)),None)
        if not target or not _targets_allowed(user,target.get('targets') or [],allow_global_read=False):return self.send_json({"error":"Déclaration hors du périmètre métier autorisé."},403)
        try:delete_declaration(int(data.get("id")),user["username"])
        except (ValueError,TypeError) as exc:return self.send_json({"error":str(exc) or "Déclaration invalide"},400)
        except LookupError as exc:return self.send_json({"error":str(exc)},404)
        self.send_json({"ok":True})

