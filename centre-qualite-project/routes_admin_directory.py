"""Routes Administration : directory ; corps V56.8 deplaces sans changement."""
import app_config as cfg
import json

import re

import supervision

from app_db import db_connect, get_setting, now_text, set_setting

from classification import classify_site_details, normalize_user_key, parse_ip_selector, refresh_classification_cache

from error_log import log_unexpected_error

from inventory_service import rows_to_dict, followup_config, DEFAULT_FOLLOWUP_LABELS
from inventory_followup import POLICY_KEY, normalize_policy

from support_priority import (
    COLOR_RE, LEGACY_FIELDS, legacy_thresholds_from_conditions, load_priority_policies,
    metric_catalog, public_policy_snapshot, validate_conditions,
)


from support_scoring import (
    SCORE_SETTING_KEY, load_score_config, public_score_config, validate_score_config,
)

SITE_VALUES = cfg.SITE_VALUES



class AdminDirectoryRoutesMixin:
    def api_support_priority_config(self, user=None):
        """Dedicated payload for the Priorités Support interface.

        Do not expose the broader Classification/Directory administration when a
        security group is allowed to manage only support priority settings.
        """
        warnings = []
        try:
            priority_policies = public_policy_snapshot(load_priority_policies())
        except Exception:
            log_unexpected_error('app.api_support_priority.priority_policies')
            priority_policies = []
            warnings.append('priority_policies')
        try:
            score_config = public_score_config(load_score_config())
        except Exception:
            log_unexpected_error('app.api_support_priority.score_config')
            score_config = public_score_config()
            warnings.append('score_config')
        self.send_json({
            "priority_policies": priority_policies,
            "priority_metrics": metric_catalog(),
            "priority_operators": [">", ">=", "<", "<=", "==", "!="],
            "support_score_config": score_config,
            "warnings": warnings,
        })

    def api_classification(self, user=None):
        # Administration must remain usable even if one optional source is
        # temporarily inconsistent after a PostgreSQL migration. Core sections
        # are isolated and returned with warnings instead of turning the whole
        # page into HTTP 500.
        warnings = []
        # GET must stay read-only and fast.  A full Support -> Administration
        # synchronization scans candidates and writes the directory; it is kept
        # behind the explicit `Synchroniser maintenant` POST action.
        sync_result = {"created": 0, "updated": 0, "candidates": 0, "mode": "manual"}
        try:
            support_candidates = supervision.support_directory_candidates()
            sync_result['candidates'] = len(support_candidates)
        except Exception:
            log_unexpected_error('app.api_classification.candidates')
            support_candidates = []
            warnings.append("Candidats Support indisponibles")

        with db_connect() as con:
            def q(label, sql):
                try:
                    return rows_to_dict(con.execute(sql).fetchall())
                except Exception:
                    log_unexpected_error('app.api_classification.' + label)
                    warnings.append(label)
                    return []

            policies = q('site_policies', "SELECT collector,default_site,updated_at,updated_by FROM site_policies ORDER BY CASE collector WHEN 'DC1' THEN 1 WHEN 'DC2' THEN 2 ELSE 3 END,collector")
            rules = q('site_rules', "SELECT * FROM site_rules ORDER BY priority DESC,id ASC")
            groups = q('groups', """
                SELECT g.id,g.name,g.description,g.created_at,g.created_by,g.updated_at,g.updated_by,COUNT(m.user_key) member_count
                FROM user_groups g LEFT JOIN user_group_members m ON m.group_id=g.id
                GROUP BY g.id,g.name,g.description,g.created_at,g.created_by,g.updated_at,g.updated_by
                ORDER BY g.name COLLATE NOCASE
            """)
            members = q('members', """
                SELECT m.user_key,m.user_identifier,m.group_id,g.name group_name,m.created_at,m.created_by
                FROM user_group_members m JOIN user_groups g ON g.id=m.group_id
                ORDER BY g.name COLLATE NOCASE,m.user_identifier COLLATE NOCASE
            """)
            directory = q('directory', """
                SELECT d.user_key,d.user_identifier,d.first_name,d.last_name,d.created_at,d.created_by,d.updated_at,d.updated_by,
                       COALESCE(m.group_id,0) group_id,COALESCE(g.name,'') group_name,
                       CASE WHEN d.created_by='SUPPORT_SYNC' THEN 1 ELSE 0 END imported_from_support
                FROM user_directory d
                LEFT JOIN user_group_members m ON m.user_key=d.user_key
                LEFT JOIN user_groups g ON g.id=m.group_id
                ORDER BY COALESCE(NULLIF(d.first_name,''),d.user_identifier) COLLATE NOCASE,d.last_name COLLATE NOCASE
            """)
            discovered = q('discovered_users', """
                SELECT user_key(utilisateur) user_key,MAX(utilisateur) exemple,COUNT(*) passages,MAX(date_evenement) derniere_vue
                FROM diagnostic WHERE TRIM(COALESCE(utilisateur,''))<>''
                GROUP BY user_key(utilisateur) ORDER BY MAX(date_evenement) DESC LIMIT 250
            """)
            exclusions = q('support_exclusions', """
                SELECT e.user_key,e.user_identifier,e.reason,e.created_at,e.created_by,
                       COALESCE(NULLIF(TRIM(COALESCE(d.first_name,'') || ' ' || COALESCE(d.last_name,'')),''),e.user_identifier) display_name,
                       COALESCE(g.name,'') group_name
                FROM support_agent_exclusions e
                LEFT JOIN user_directory d ON d.user_key=e.user_key
                LEFT JOIN user_group_members m ON m.user_key=e.user_key
                LEFT JOIN user_groups g ON g.id=m.group_id
                ORDER BY display_name COLLATE NOCASE,e.user_identifier COLLATE NOCASE
            """)
            group_campaigns = q('group_campaigns', """
                SELECT q.group_id,g.name group_name,q.campaign_name,q.created_at,q.created_by
                FROM quality_group_campaigns q JOIN user_groups g ON g.id=q.group_id
                ORDER BY g.name COLLATE NOCASE,q.campaign_name COLLATE NOCASE
            """)
            try:
                fcfg = followup_config(con)
            except Exception:
                log_unexpected_error('app.api_classification.followup')
                warnings.append('followup_config')
                fcfg = {"warning_days": 7, "late_days": 20, "labels": dict(DEFAULT_FOLLOWUP_LABELS)}
        # Legacy payload field; the current Groups workspace no longer consumes
        # this global Quality catalogue. Avoid constructing the full Quality
        # projection merely to render Administration.
        quality_campaigns = sorted({str(x.get('campaign_name') or '') for x in group_campaigns if x.get('campaign_name')})
        try:
            priority_policies = public_policy_snapshot(load_priority_policies())
        except Exception:
            log_unexpected_error('app.api_classification.priority_policies')
            priority_policies = []
            warnings.append('priority_policies')
        try:
            score_config = public_score_config(load_score_config())
        except Exception:
            log_unexpected_error('app.api_classification.score_config')
            score_config = public_score_config()
            warnings.append('score_config')
        if user is not None:
            from access_control import effective_group_ids, allowed_agent_ids
            allowed=effective_group_ids(user);agent_ids=allowed_agent_ids(user)
            if allowed is not None:
                allowed={str(x) for x in allowed};agent_ids={str(x) for x in (agent_ids or set())}
                groups=[g for g in groups if str(g.get('id') or '') in allowed]
                members=[m for m in members if str(m.get('group_id') or '') in allowed]
                directory=[d for d in directory if str(d.get('group_id') or '') in allowed or str(d.get('user_key') or '') in agent_ids]
                discovered=[d for d in discovered if str(d.get('user_key') or '') in agent_ids]
                support_candidates=[d for d in support_candidates if str(d.get('user_key') or d.get('agent') or d.get('user_identifier') or '') in agent_ids]
                exclusions=[d for d in exclusions if str(d.get('user_key') or '') in agent_ids]
                group_campaigns=[x for x in group_campaigns if str(x.get('group_id') or '') in allowed]
                quality_campaigns=sorted({str(x.get('campaign_name') or '') for x in group_campaigns if x.get('campaign_name')})
        self.send_json({"policies": policies, "rules": rules, "groups": groups, "members": members, "directory": directory,
                        "discovered_users": discovered, "support_candidates": support_candidates,
                        "support_exclusions": exclusions, "priority_policies": priority_policies,
                        "priority_metrics": metric_catalog(), "priority_operators": [">", ">=", "<", "<=", "==", "!="],
                        "support_score_config": score_config, "followup_config": fcfg,
                        "group_campaigns": group_campaigns, "quality_campaigns": quality_campaigns,
                        "directory_sync": sync_result, "warnings": warnings})

    def api_inventory_followup_policy(self, user):
        data = self.read_json() or {}
        if not isinstance(data, dict):
            return self.send_json({"error": "Configuration de suivi invalide."}, 400)
        if "policy" in data:
            try:
                policy = normalize_policy(data["policy"])
            except (ValueError, TypeError) as exc:
                return self.send_json({"error": str(exc)}, 400)
            with db_connect() as con:
                con.execute("BEGIN IMMEDIATE")
                current = followup_config(con)
                if data.get("expected_revision") != current["revision"]:
                    return self.send_json({"error": "Les r\u00e8gles ont chang\u00e9. Rechargez la page avant d'enregistrer."}, 409)
                raw = json.dumps(policy, ensure_ascii=False, separators=(",", ":"))
                set_setting(con, POLICY_KEY, raw, user["username"])
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (user["username"], "INVENTORY_FOLLOWUP_POLICY_UPDATED",
                             json.dumps({"version": 2, "before": current["policy"], "after": policy}, ensure_ascii=False),
                             self.client_ip()))
                con.commit()
                config = followup_config(con)
            return self.send_json({"ok": True, "followup_config": config})
        # Legacy clients cannot silently overwrite a v2 policy.
        with db_connect() as con:
            if con.execute("SELECT 1 FROM settings WHERE key=? AND value<>''", (POLICY_KEY,)).fetchone():
                return self.send_json({"error": "R\u00e8gles personnalis\u00e9es actives : utilisez la nouvelle interface de suivi."}, 409)
        try:
            warning = max(1, min(3650, int(data.get("warning_days", 7))))
            late = max(2, min(3650, int(data.get("late_days", 20))))
        except Exception:
            return self.send_json({"error": "Intervalles de suivi invalides"}, 400)
        if late <= warning:
            return self.send_json({"error": "Le seuil Retard/Critique doit être supérieur au seuil Pas à jour/Retard"}, 400)
        labels = dict(DEFAULT_FOLLOWUP_LABELS)
        incoming = data.get("labels", {})
        if isinstance(incoming, dict):
            for key in labels:
                value = str(incoming.get(key, labels[key]) or "").strip()
                if value:
                    labels[key] = value[:60]
        flags = {
            "inventory_followup_override_stock": "1" if bool(data.get("override_stock", True)) else "0",
            "inventory_followup_override_repair": "1" if bool(data.get("override_repair", True)) else "0",
            "inventory_followup_override_lost": "1" if bool(data.get("override_lost", True)) else "0",
            "inventory_followup_override_retired": "1" if bool(data.get("override_retired", True)) else "0",
        }
        with db_connect() as con:
            set_setting(con, "inventory_followup_warning_days", warning, user["username"])
            set_setting(con, "inventory_followup_late_days", late, user["username"])
            set_setting(con, "inventory_followup_labels", json.dumps(labels, ensure_ascii=False, separators=(",", ":")), user["username"])
            for key, value in flags.items():
                set_setting(con, key, value, user["username"])
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "INVENTORY_FOLLOWUP_POLICY_UPDATED", f"warning={warning}; late={late}; overrides={flags}", self.client_ip()))
            con.commit()
            cfg_now = followup_config(con)
        self.send_json({"ok": True, "followup_config": cfg_now})

    def api_site_policy(self, user):
        data = self.read_json() or {}
        collector = str(data.get("collector", "")).strip().upper()
        site = str(data.get("default_site", "")).strip().upper()
        if not collector or len(collector) > 30 or not re.fullmatch(r"[A-Z0-9_*.-]+", collector):
            return self.send_json({"error": "Collecteur invalide"}, 400)
        if site not in SITE_VALUES:
            return self.send_json({"error": "Résultat d'emplacement invalide"}, 400)
        with db_connect() as con:
            con.execute("""INSERT INTO site_policies(collector,default_site,updated_at,updated_by) VALUES(?,?,?,?)
                         ON CONFLICT(collector) DO UPDATE SET default_site=excluded.default_site,updated_at=excluded.updated_at,updated_by=excluded.updated_by""",
                        (collector, site, now_text(), user["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SITE_POLICY_UPDATED", f"{collector} -> {site}", self.client_ip()))
            con.commit()
        refresh_classification_cache()
        self.send_json({"ok": True})

    def api_site_rule(self, user):
        data = self.read_json() or {}
        collector = str(data.get("collector", "*")).strip().upper() or "*"
        network_text = str(data.get("network", "")).strip()
        gateway_text = str(data.get("gateway_network", "") or "").strip()
        result_site = str(data.get("result_site", "")).strip().upper()
        label = str(data.get("label", "") or "").strip()[:120]
        try:
            priority = max(-10000, min(10000, int(data.get("priority", 100))))
            network_selector = parse_ip_selector(network_text)
            network = network_selector["normalized"]
            gateway_network = parse_ip_selector(gateway_text)["normalized"] if gateway_text else ""
        except Exception as exc:
            return self.send_json({"error": f"Plage IP ou passerelle invalide : {exc}. Formats acceptés : IP, CIDR ou début-fin."}, 400)
        if result_site not in SITE_VALUES:
            return self.send_json({"error": "Résultat d'emplacement invalide"}, 400)
        if not re.fullmatch(r"[A-Z0-9_*.-]{1,30}", collector):
            return self.send_json({"error": "Collecteur invalide"}, 400)
        with db_connect() as con:
            con.execute("INSERT INTO site_rules(collector,network,gateway_network,result_site,label,priority,enabled,created_by,updated_by) VALUES(?,?,?,?,?,?,1,?,?)",
                        (collector, network, gateway_network, result_site, label, priority, user["username"], user["username"]))
            rid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SITE_RULE_CREATED", f"#{rid} {collector} {network} GW={gateway_network or '*'} -> {result_site}", self.client_ip()))
            con.commit()
        refresh_classification_cache()
        self.send_json({"ok": True, "id": rid}, 201)

    def api_site_rule_delete(self, user):
        data = self.read_json() or {}
        try: rid = int(data.get("id"))
        except Exception: return self.send_json({"error": "Règle invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT * FROM site_rules WHERE id=?", (rid,)).fetchone()
            if not row: return self.send_json({"error": "Règle introuvable"}, 404)
            con.execute("DELETE FROM site_rules WHERE id=?", (rid,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SITE_RULE_DELETED", f"#{rid} {row['collector']} {row['network']}", self.client_ip()))
            con.commit()
        refresh_classification_cache()
        self.send_json({"ok": True})

    def api_site_rule_toggle(self, user):
        data = self.read_json() or {}
        try: rid = int(data.get("id"))
        except Exception: return self.send_json({"error": "Règle invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT enabled FROM site_rules WHERE id=?", (rid,)).fetchone()
            if not row: return self.send_json({"error": "Règle introuvable"}, 404)
            enabled = 0 if row["enabled"] else 1
            con.execute("UPDATE site_rules SET enabled=?,updated_at=?,updated_by=? WHERE id=?", (enabled, now_text(), user["username"], rid))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SITE_RULE_TOGGLED", f"#{rid} enabled={enabled}", self.client_ip()))
            con.commit()
        refresh_classification_cache()
        self.send_json({"ok": True, "enabled": enabled})

    def api_classification_test(self, user):
        data = self.read_json() or {}
        collector = str(data.get("collector", "")).strip()
        ip_value = str(data.get("ip", "")).strip()
        gateway_value = str(data.get("gateway", "")).strip()
        result = classify_site_details(collector, ip_value, gateway_value)
        result.update({"collector": collector or "—", "ip": ip_value or "—", "gateway": gateway_value or "—"})
        self.send_json({"ok": True, "result": result})

    def api_directory_user(self, user):
        data = self.read_json() or {}
        identifier = str(data.get("user_identifier", "") or "").strip()
        key = normalize_user_key(identifier)
        first_name = str(data.get("first_name", "") or "").strip()[:80]
        last_name = str(data.get("last_name", "") or "").strip()[:80]
        group_raw = str(data.get("group_id", "") or "").strip()
        if not key or len(key) > 100:
            return self.send_json({"error": "Identifiant utilisateur invalide"}, 400)
        gid = None
        if group_raw:
            try:
                gid = int(group_raw)
            except Exception:
                return self.send_json({"error": "Groupe invalide"}, 400)
        from access_control import effective_group_ids, allowed_group
        allowed=effective_group_ids(user)
        if allowed is not None and (gid is None or not allowed_group(user,gid)):
            return self.send_json({"error":"Affectation hors de votre périmètre métier autorisé."},403)
        with db_connect() as con:
            if gid is not None and not con.execute("SELECT 1 FROM user_groups WHERE id=?", (gid,)).fetchone():
                return self.send_json({"error": "Groupe introuvable"}, 404)
            con.execute("""INSERT INTO user_directory(user_key,user_identifier,first_name,last_name,created_by,updated_by)
                         VALUES(?,?,?,?,?,?)
                         ON CONFLICT(user_key) DO UPDATE SET user_identifier=excluded.user_identifier,first_name=excluded.first_name,last_name=excluded.last_name,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                        (key, identifier, first_name, last_name, user["username"], user["username"]))
            if gid is None:
                con.execute("DELETE FROM user_group_members WHERE user_key=?", (key,))
            else:
                con.execute("""INSERT INTO user_group_members(user_key,user_identifier,group_id,created_by) VALUES(?,?,?,?)
                             ON CONFLICT(user_key) DO UPDATE SET user_identifier=excluded.user_identifier,group_id=excluded.group_id,created_at=CURRENT_TIMESTAMP,created_by=excluded.created_by""",
                            (key, identifier, gid, user["username"]))
            display = (first_name + " " + last_name).strip() or identifier
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "DIRECTORY_USER_SET", f"{key} -> {display}; group={gid or 'none'}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "user_key": key, "display_name": display})

    def api_directory_user_delete(self, user):
        data = self.read_json() or {}
        key = normalize_user_key(data.get("user_key", ""))
        if not key:
            return self.send_json({"error": "Utilisateur invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT d.user_identifier,m.group_id FROM user_directory d LEFT JOIN user_group_members m ON m.user_key=d.user_key WHERE d.user_key=?", (key,)).fetchone()
            if not row:
                return self.send_json({"error": "Utilisateur d'annuaire introuvable"}, 404)
            from access_control import effective_group_ids, allowed_group
            if effective_group_ids(user) is not None and not allowed_group(user,row["group_id"]):
                return self.send_json({"error":"Utilisateur hors de votre périmètre métier autorisé."},403)
            con.execute("DELETE FROM user_directory WHERE user_key=?", (key,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)", (user["username"], "DIRECTORY_USER_DELETED", key, self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_directory_sync_support(self, user):
        from access_control import effective_group_ids
        if effective_group_ids(user) is not None:
            return self.send_json({"error":"La synchronisation globale de l'annuaire nécessite un périmètre métier global."},403)
        try:
            result = supervision.sync_admin_directory_from_support(user["username"])
        except Exception as exc:
            log_unexpected_error('app.api_directory_sync_support.L2090')
            return self.send_json({"error": f"Synchronisation Support impossible : {exc}"}, 500)
        with db_connect() as con:
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "DIRECTORY_SUPPORT_SYNC", f"created={result.get('created',0)} updated={result.get('updated',0)} candidates={result.get('candidates',0)}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, **result})

