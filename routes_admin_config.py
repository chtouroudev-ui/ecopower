"""Routes Administration : config ; corps V56.8 deplaces sans changement."""
import app_config as cfg
from group_workspace import export_group_links, validate_group_links, restore_group_links

from datetime import datetime, timedelta

import json

import os

import re

import runtime

import supervision

from app_db import db_connect, get_setting, now_text, set_setting

from classification import classify_site_details, normalize_user_key, parse_ip_selector, refresh_classification_cache

from diagnostic_import import import_diagnostic_source, source_schema_info

from error_log import log_unexpected_error

from inventory_service import rows_to_dict, followup_config, DEFAULT_FOLLOWUP_LABELS

from support_priority import (
    COLOR_RE, LEGACY_FIELDS, legacy_thresholds_from_conditions, load_priority_policies,
    metric_catalog, public_policy_snapshot, validate_conditions,
)

from support_scoring import (
    SCORE_SETTING_KEY, load_score_config, public_score_config, validate_score_config,
)

import live_quality

SITE_VALUES = cfg.SITE_VALUES

SESSION_MAX_HOURS = cfg.SESSION_MAX_HOURS

SESSION_IDLE_MINUTES = cfg.SESSION_IDLE_MINUTES

LOGIN_MAX_FAILURES = cfg.LOGIN_MAX_FAILURES

LOGIN_LOCK_MINUTES = cfg.LOGIN_LOCK_MINUTES

DEFAULT_HOST = cfg.DEFAULT_HOST

DEFAULT_PORT = cfg.DEFAULT_PORT

APP_DB = cfg.APP_DB

BASE = cfg.BASE

validate_host = runtime.validate_host

local_lan_ip = runtime.local_lan_ip


from routes_admin_support import _priority_bool, _priority_name, _priority_color


class AdminConfigRoutesMixin:
    def api_config_export(self, user):
        allowed_settings = ["diagnostic_source_path", "web_host", "web_port", "auto_import_enabled", "auto_import_minutes", "tls_enabled", "tls_cert_path", "tls_key_path", "public_hostname"]
        live_quality_config = live_quality.config_snapshot()
        with db_connect() as con:
            settings = {r["key"]: r["value"] for r in con.execute(
                "SELECT key,value FROM settings WHERE key IN (%s)" % ",".join("?" * len(allowed_settings)), allowed_settings
            ).fetchall()}
            quality_group_links = export_group_links(con)
            policies = rows_to_dict(con.execute("SELECT collector,default_site FROM site_policies ORDER BY collector").fetchall())
            rules = rows_to_dict(con.execute("SELECT collector,network,gateway_network,result_site,label,priority,enabled FROM site_rules ORDER BY priority DESC,id ASC").fetchall())
            groups = rows_to_dict(con.execute("SELECT name,service_name,description FROM user_groups ORDER BY name COLLATE NOCASE").fetchall())
            members = rows_to_dict(con.execute("""SELECT m.user_key,m.user_identifier,g.name group_name
                                                 FROM user_group_members m JOIN user_groups g ON g.id=m.group_id
                                                 ORDER BY g.name,m.user_identifier""").fetchall())
            group_campaigns = rows_to_dict(con.execute("""SELECT g.name group_name,q.campaign_name
                                                        FROM quality_group_campaigns q JOIN user_groups g ON g.id=q.group_id
                                                        ORDER BY g.name COLLATE NOCASE,q.campaign_name COLLATE NOCASE""").fetchall())
            directory = rows_to_dict(con.execute("SELECT user_key,user_identifier,first_name,last_name FROM user_directory ORDER BY user_key").fetchall())
            support_exclusions = rows_to_dict(con.execute("SELECT user_key,user_identifier,reason FROM support_agent_exclusions ORDER BY user_key").fetchall())
            support_priority_rows = rows_to_dict(con.execute("""
                SELECT priority,rank,match_mode,disconnects_per_day,call_percent,affected_days_percent,lost_minutes_per_day,
                       enabled,color,is_fallback,conditions_json
                FROM support_priority_policies ORDER BY rank DESC
            """).fetchall())
            support_priority_policies = public_policy_snapshot(support_priority_rows)
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "CONFIG_EXPORTED", "Configuration JSON exportée", self.client_ip()))
            con.commit()
        payload = {
            "format": "TECH-IN Stock Manager configuration",
            "version": 1,
            "exported_at": now_text(),
            "settings": settings,
            "site_policies": policies,
            "site_rules": rules,
            "user_groups": groups,
            "user_group_members": members,
            "quality_group_links": quality_group_links,
            "quality_group_campaigns": group_campaigns,
            "user_directory": directory,
            "support_agent_exclusions": support_exclusions,
            "support_priority_policies": support_priority_policies,
            "support_score_config": public_score_config(load_score_config()),
            "live_quality_levels": live_quality_config.get("levels", []),
            "live_quality_rules": live_quality_config.get("rules", []),
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = f"TECH-IN_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.send_bytes(data, "application/json; charset=utf-8", extra={"Content-Disposition": f"attachment; filename={filename}"})

    def api_config_import(self, user):
        data = self.read_json()
        if not isinstance(data, dict) or data.get("format") != "TECH-IN Stock Manager configuration":
            return self.send_json({"error": "Fichier de configuration TECH-IN invalide"}, 400)
        try:
            config_version = int(data.get("version", 0) or 0)
        except Exception:
            return self.send_json({"error": "Version de configuration invalide"}, 400)
        if config_version != 1:
            return self.send_json({"error": "Version de configuration non prise en charge"}, 400)
        allowed_settings = {"diagnostic_source_path", "web_host", "web_port", "auto_import_enabled", "auto_import_minutes", "tls_enabled", "tls_cert_path", "tls_key_path", "public_hostname"}
        try:
            settings = data.get("settings", {}) or {}
            if not isinstance(settings, dict):
                raise ValueError("Section settings invalide")
            if "web_host" in settings:
                validate_host(settings["web_host"])
            if "web_port" in settings and not (1 <= int(settings["web_port"]) <= 65535):
                raise ValueError("Port web invalide")
            if "auto_import_minutes" in settings and not (1 <= int(settings["auto_import_minutes"]) <= 1440):
                raise ValueError("Intervalle d'import invalide")
            if "public_hostname" in settings:
                ph = str(settings["public_hostname"] or "").strip()
                if ph and (len(ph) > 253 or not re.fullmatch(r"[A-Za-z0-9.-]+", ph)):
                    raise ValueError("Nom DNS public invalide")
            if "tls_enabled" in settings:
                settings["tls_enabled"] = "1" if str(settings["tls_enabled"]).lower() in {"1","true","yes","on"} else "0"
                if settings["tls_enabled"] == "1":
                    cert = str(settings.get("tls_cert_path", "") or "").strip().strip('"')
                    key = str(settings.get("tls_key_path", "") or "").strip().strip('"')
                    if not cert or not os.path.isfile(cert) or not key or not os.path.isfile(key):
                        raise ValueError("HTTPS direct activé mais certificat/clé PEM introuvables sur ce serveur")

            policies = data.get("site_policies", []) or []
            rules = data.get("site_rules", []) or []
            group_links = validate_group_links(data['quality_group_links']) if 'quality_group_links' in data else None
            groups = data.get("user_groups", []) or []
            members = data.get("user_group_members", []) or []
            group_campaigns = data.get("quality_group_campaigns", []) or []
            directory = data.get("user_directory", []) or []
            support_exclusions = data.get("support_agent_exclusions", []) or []
            priority_policies = data.get("support_priority_policies", []) or []
            score_config_raw = data.get("support_score_config", None)
            normalized_score_config = validate_score_config(score_config_raw) if score_config_raw is not None else None
            live_quality_present = "live_quality_levels" in data or "live_quality_rules" in data
            normalized_live_levels = None
            normalized_live_rules = None
            if live_quality_present:
                if "live_quality_levels" not in data or "live_quality_rules" not in data:
                    raise ValueError("La configuration Qualité Live doit contenir niveaux et règles")
                raw_live_levels = data.get("live_quality_levels") or []
                raw_live_rules = data.get("live_quality_rules") or []
                if not isinstance(raw_live_levels, list) or not isinstance(raw_live_rules, list):
                    raise ValueError("Configuration Qualité Live invalide")
                normalized_live_levels = [live_quality.normalize_level(x) for x in raw_live_levels]
                if not normalized_live_levels:
                    raise ValueError("La Qualité Live doit conserver au moins un niveau")
                keys = [x["level_key"] for x in normalized_live_levels]
                if len(set(keys)) != len(keys):
                    raise ValueError("Niveau Qualité Live en double")
                if sum(int(x.get("is_fallback") or 0) for x in normalized_live_levels) != 1:
                    raise ValueError("La Qualité Live doit avoir exactement un niveau de repli")
                normalized_live_rules = []
                known_live_levels = set(keys)
                for raw_rule in raw_live_rules:
                    if not isinstance(raw_rule, dict):
                        raise ValueError("Règle Qualité Live invalide")
                    clean_rule = dict(raw_rule)
                    clean_rule.pop("id", None)
                    normalized_live_rules.append(live_quality.normalize_rule(clean_rule, known_levels=known_live_levels))
            if not all(isinstance(x, list) for x in (policies, rules, groups, members, group_campaigns, directory, support_exclusions, priority_policies)):
                raise ValueError("Une section de configuration est invalide")
            normalized_priorities = []
            seen_priority_names = set()
            explicit_fallback = any("is_fallback" in pp for pp in priority_policies if isinstance(pp, dict))
            for index, pp in enumerate(priority_policies):
                if not isinstance(pp, dict):
                    raise ValueError("Politique de priorité Support invalide")
                priority = _priority_name(pp.get("priority"))
                folded = priority.casefold()
                if folded in seen_priority_names:
                    raise ValueError(f"Priorité Support en double : {priority}")
                seen_priority_names.add(folded)
                mode = str(pp.get("match_mode", "ANY")).strip().upper()
                if mode not in {"ANY","ALL"}:
                    raise ValueError("Mode priorité Support invalide")
                rank = max(-10000, min(10000, int(pp.get("rank", 100))))
                color = _priority_color(pp.get("color", "#667085"))
                is_fallback = 1 if _priority_bool(pp.get("is_fallback", False)) else 0
                if "conditions" in pp:
                    conditions = validate_conditions(pp.get("conditions"), allow_empty=True)
                else:
                    legacy_conditions = []
                    for field in LEGACY_FIELDS:
                        raw = pp.get(field)
                        if raw is None or str(raw).strip() == "":
                            continue
                        legacy_conditions.append({"metric": field, "operator": ">", "value": float(raw)})
                    conditions = validate_conditions(legacy_conditions, allow_empty=True)
                normalized_priorities.append({
                    "priority": priority, "rank": rank, "mode": mode, "conditions": conditions,
                    "enabled": 1 if _priority_bool(pp.get("enabled", True), True) else 0,
                    "color": color, "is_fallback": is_fallback, "index": index,
                })
            if normalized_priorities:
                if explicit_fallback:
                    if sum(x["is_fallback"] for x in normalized_priorities) != 1:
                        raise ValueError("La configuration doit contenir exactement un niveau de repli")
                else:
                    # Compatibilité v38 : FAIBLE est le repli, sinon le rang le plus bas.
                    fallback = next((x for x in normalized_priorities if x["priority"].casefold() == "faible"), None)
                    fallback = fallback or min(normalized_priorities, key=lambda x: x["rank"])
                    fallback["is_fallback"] = 1
                for item in normalized_priorities:
                    if item["is_fallback"]:
                        item["conditions"] = []
                        item["enabled"] = 1
                    elif not item["conditions"]:
                        raise ValueError(f"Le niveau {item['priority']} doit avoir au moins une condition")

            normalized_rules = []
            for r in rules:
                collector = str(r.get("collector", "*")).strip().upper() or "*"
                network = parse_ip_selector(str(r.get("network", "")).strip())["normalized"]
                gw_text = str(r.get("gateway_network", "") or "").strip()
                gateway_network = parse_ip_selector(gw_text)["normalized"] if gw_text else ""
                result_site = str(r.get("result_site", "")).strip().upper()
                if result_site not in SITE_VALUES or not re.fullmatch(r"[A-Z0-9_*.-]{1,30}", collector):
                    raise ValueError("Règle de classification invalide")
                normalized_rules.append((collector, network, gateway_network, result_site, str(r.get("label", "") or "")[:120], int(r.get("priority", 100)), 1 if r.get("enabled", 1) else 0))
        except Exception as exc:
            return self.send_json({"error": f"Configuration invalide : {exc}"}, 400)

        if normalized_live_levels is not None:
            live_quality.ensure_admin_schema()
        with db_connect() as con:
            for k, v in settings.items():
                if k in allowed_settings:
                    set_setting(con, k, v, user["username"])
            con.execute("DELETE FROM site_rules")
            con.execute("DELETE FROM site_policies")
            for p in policies:
                collector = str(p.get("collector", "")).strip().upper()
                site = str(p.get("default_site", "INCONNU")).strip().upper()
                if collector and site in SITE_VALUES:
                    con.execute("INSERT OR REPLACE INTO site_policies(collector,default_site,updated_by) VALUES(?,?,?)", (collector, site, user["username"]))
            for collector, default_site in (("DC1", "SUR SITE"), ("DC2", "TELETRAVAIL"), ("*", "INCONNU")):
                con.execute("INSERT OR IGNORE INTO site_policies(collector,default_site,updated_by) VALUES(?,?,?)", (collector, default_site, user["username"]))
            for r in normalized_rules:
                con.execute("INSERT INTO site_rules(collector,network,gateway_network,result_site,label,priority,enabled,created_by,updated_by) VALUES(?,?,?,?,?,?,?,?,?)", (*r, user["username"], user["username"]))

            # Backups created before F3.9 preserve links on exactly matching group names.
            links_to_restore = group_links if group_links is not None else export_group_links(con)
            con.execute("DELETE FROM user_group_members")
            con.execute("DELETE FROM user_groups")
            group_ids = {}
            for g in groups:
                name = str(g.get("name", "") or "").strip()[:60]
                if not name:
                    continue
                con.execute("INSERT INTO user_groups(name,service_name,description,created_by,updated_by) VALUES(?,?,?,?,?)", (name, str(g.get("service_name", "") or "").strip()[:60], str(g.get("description", "") or "")[:300], user["username"], user["username"]))
                group_ids[name.casefold()] = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            for m in members:
                key = normalize_user_key(m.get("user_key") or m.get("user_identifier"))
                group_name = str(m.get("group_name", "") or "").strip()
                gid = group_ids.get(group_name.casefold())
                if key and gid:
                    con.execute("INSERT OR REPLACE INTO user_group_members(user_key,user_identifier,group_id,created_by) VALUES(?,?,?,?)", (key, str(m.get("user_identifier", key)), gid, user["username"]))
            for c in group_campaigns:
                group_name = str(c.get("group_name", "") or "").strip()
                campaign_name = " ".join(str(c.get("campaign_name", "") or "").split()).strip()[:160]
                gid = group_ids.get(group_name.casefold())
                if gid and campaign_name:
                    con.execute("INSERT OR IGNORE INTO quality_group_campaigns(group_id,campaign_name,created_by) VALUES(?,?,?)", (gid, campaign_name, user["username"]))

            restore_group_links(con, links_to_restore, group_ids, user["username"])

            con.execute("DELETE FROM user_directory")
            for d in directory:
                key = normalize_user_key(d.get("user_key") or d.get("user_identifier"))
                if not key:
                    continue
                con.execute("INSERT INTO user_directory(user_key,user_identifier,first_name,last_name,created_by,updated_by) VALUES(?,?,?,?,?,?)",
                            (key, str(d.get("user_identifier", key)), str(d.get("first_name", "") or "")[:80], str(d.get("last_name", "") or "")[:80], user["username"], user["username"]))
            con.execute("DELETE FROM support_agent_exclusions")
            for e in support_exclusions:
                key = normalize_user_key(e.get("user_key") or e.get("user_identifier"))
                if re.fullmatch(r"S\d+", key or ""):
                    key = key[1:]
                if not key:
                    continue
                con.execute("INSERT OR REPLACE INTO support_agent_exclusions(user_key,user_identifier,reason,created_by) VALUES(?,?,?,?)",
                            (key, str(e.get("user_identifier", key)), str(e.get("reason", "") or "")[:300], user["username"]))
            if normalized_score_config is not None:
                set_setting(con, SCORE_SETTING_KEY, json.dumps(normalized_score_config, ensure_ascii=False, separators=(",", ":")), user["username"])
            if normalized_priorities:
                con.execute("DELETE FROM support_priority_policies")
                for pp in normalized_priorities:
                    legacy = legacy_thresholds_from_conditions(pp["conditions"])
                    con.execute("""INSERT INTO support_priority_policies(
                        priority,rank,match_mode,disconnects_per_day,call_percent,affected_days_percent,lost_minutes_per_day,
                        enabled,color,is_fallback,conditions_json,updated_by
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                        pp["priority"], pp["rank"], pp["mode"], legacy["disconnects_per_day"], legacy["call_percent"],
                        legacy["affected_days_percent"], legacy["lost_minutes_per_day"], pp["enabled"], pp["color"],
                        pp["is_fallback"], json.dumps(pp["conditions"], ensure_ascii=False, separators=(",", ":")), user["username"]
                    ))
            if normalized_live_levels is not None:
                con.execute("DELETE FROM live_quality_rules")
                con.execute("DELETE FROM live_quality_levels")
                for lvl in normalized_live_levels:
                    con.execute("""INSERT INTO live_quality_levels(level_key,label,rank,color,enabled,is_fallback,updated_by)
                                   VALUES(?,?,?,?,?,?,?)""",
                                (lvl["level_key"],lvl["label"],lvl["rank"],lvl["color"],lvl["enabled"],lvl["is_fallback"],user["username"]))
                for rr in normalized_live_rules:
                    con.execute("""INSERT INTO live_quality_rules(name,enabled,scope_type,target_key,match_mode,level_key,
                                   min_duration_seconds,recovery_seconds,cooldown_seconds,min_sample_size,allow_partial,conditions_json,updated_by)
                                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (rr["name"],rr["enabled"],rr["scope_type"],rr["target_key"],rr["match_mode"],rr["level_key"],
                                 rr["min_duration_seconds"],rr["recovery_seconds"],rr["cooldown_seconds"],rr["min_sample_size"],
                                 rr["allow_partial"],json.dumps(rr["conditions"],ensure_ascii=False,separators=(",",":")),user["username"]))
            live_rule_count = len(normalized_live_rules or []) if normalized_live_rules is not None else 0
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "CONFIG_IMPORTED", f"{len(normalized_rules)} règles; {len(group_ids)} groupes; {len(directory)} entrées annuaire; {len(support_exclusions)} exclusions Support; {len(normalized_priorities)} politiques priorité; {live_rule_count} règles Qualité Live", self.client_ip()))
            con.commit()
        refresh_classification_cache()
        self.send_json({"ok": True, "rules": len(normalized_rules), "groups": len(group_ids), "directory": len(directory), "support_exclusions": len(support_exclusions), "priority_policies": len(normalized_priorities), "live_quality_rules": len(normalized_live_rules or []) if normalized_live_rules is not None else None, "restart_required": True})

    def api_import_coverage(self, qs):
        """Check which business dates are present in the active Support databases.

        A date is considered imported when the authoritative daily export is mapped
        in ``coverage``. Calls are reported independently through ``call_coverage``.
        Retention tombstones are surfaced as ARCHIVED instead of incorrectly
        reporting the date as never imported.
        """
        def first(name, default=""):
            values = qs.get(name, []) if isinstance(qs, dict) else []
            return str(values[0] if values else default).strip()

        today = datetime.now().date()
        start_raw = first("date_from", today.isoformat())
        end_raw = first("date_to", start_raw)
        try:
            start = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            return self.send_json({"error": "Date invalide. Utilisez AAAA-MM-JJ."}, 400)
        if end < start:
            return self.send_json({"error": "La date de fin doit être postérieure ou égale à la date de début."}, 400)
        total_days = (end - start).days + 1
        if total_days > 31:
            return self.send_json({"error": "Le contrôle est limité à 31 jours par vérification."}, 400)

        with supervision.connect() as con:
            exports = {
                str(r["day"]): dict(r)
                for r in con.execute(
                    """SELECT c.day,c.import_id,i.name,i.imported_at,i.imported_by,i.rows_count,i.offset_minutes,i.reference_day
                       FROM coverage c LEFT JOIN imports i ON i.id=c.import_id
                       WHERE c.day>=? AND c.day<=? ORDER BY c.day""",
                    (start.isoformat(), end.isoformat()),
                ).fetchall()
            }
            calls = {
                str(r["day"]): dict(r)
                for r in con.execute(
                    """SELECT cc.day,cc.import_id,COALESCE(ci.rows_count,0) AS call_rows
                       FROM call_coverage cc LEFT JOIN call_imports ci ON ci.import_id=cc.import_id
                       WHERE cc.day>=? AND cc.day<=? ORDER BY cc.day""",
                    (start.isoformat(), end.isoformat()),
                ).fetchall()
            }
            archived = {}
            for r in con.execute(
                """SELECT reference_day,name,archive_path,purged_at,original_import_id
                   FROM retention_import_tombstones
                   WHERE reference_day>=? AND reference_day<=?
                   ORDER BY reference_day,purged_at DESC""",
                (start.isoformat(), end.isoformat()),
            ).fetchall():
                archived.setdefault(str(r["reference_day"] or ""), dict(r))

        rows = []
        complete = imported = calls_present = missing = archived_count = partial = 0
        cursor = start
        while cursor <= end:
            day = cursor.isoformat()
            exp = exports.get(day)
            call = calls.get(day)
            old = archived.get(day)
            if exp and call:
                status, label = "COMPLETE", "Import complet"
                complete += 1
                imported += 1
                calls_present += 1
            elif exp:
                status, label = "IMPORTED_NO_CALLS", "Importé - appels absents"
                imported += 1
                partial += 1
            elif call:
                status, label = "CALLS_ONLY", "Appels présents - export absent"
                calls_present += 1
                partial += 1
            elif old:
                status, label = "ARCHIVED", "Archivé / purgé"
                archived_count += 1
            else:
                status, label = "MISSING", "Non importé"
                missing += 1
            rows.append({
                "day": day,
                "status": status,
                "label": label,
                "activities_present": bool(exp),
                "calls_present": bool(call),
                "import_id": int(exp["import_id"]) if exp and exp.get("import_id") is not None else (int(call["import_id"]) if call and call.get("import_id") is not None else None),
                "filename": (exp or {}).get("name") or (old or {}).get("name") or "",
                "imported_at": (exp or {}).get("imported_at") or "",
                "imported_by": (exp or {}).get("imported_by") or "",
                "activity_rows": int((exp or {}).get("rows_count") or 0),
                "call_rows": int((call or {}).get("call_rows") or 0),
                "archive_path": (old or {}).get("archive_path") or "",
                "purged_at": (old or {}).get("purged_at") or "",
            })
            cursor += timedelta(days=1)

        if complete == total_days:
            overall = "COMPLETE"
        elif missing == total_days:
            overall = "MISSING"
        else:
            overall = "PARTIAL"
        self.send_json({
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "days": total_days,
            "status": overall,
            "summary": {
                "complete": complete,
                "imported": imported,
                "calls": calls_present,
                "partial": partial,
                "archived": archived_count,
                "missing": missing,
            },
            "rows": rows,
            "meaning": {
                "COMPLETE": "Export d'activités et appels présents dans les bases actives.",
                "IMPORTED_NO_CALLS": "Export d'activités présent mais aucune couverture appels pour ce jour.",
                "CALLS_ONLY": "Couverture appels présente mais export d'activités absent.",
                "ARCHIVED": "La date a déjà été importée puis purgée/archivée par la rétention.",
                "MISSING": "Aucune trace active ou archive d'import trouvée pour cette date.",
            },
        })

    def api_security_audit(self):
        with db_connect() as con:
            events = rows_to_dict(con.execute("SELECT id,username,action,details,source_ip,created_at FROM auth_audit ORDER BY id DESC LIMIT 250").fetchall())
            locked = con.execute("SELECT COUNT(*) FROM users WHERE lock_until IS NOT NULL AND datetime(lock_until)>datetime('now','localtime')").fetchone()[0]
        direct_https = bool(getattr(self.server, "techin_https", False))
        request_https = self.request_is_https()
        proxy_hint = (not direct_https and runtime.ACTIVE_HOST in {"127.0.0.1", "::1"})
        if direct_https:
            mode = "HTTPS direct"
        elif request_https and proxy_hint:
            mode = "HTTPS via reverse proxy local"
        elif proxy_hint:
            mode = "Backend local prêt pour reverse proxy HTTPS"
        else:
            mode = "HTTP direct - à éviter sur le LAN"
        self.send_json({
            "events": events,
            "policy": {"idle_minutes": SESSION_IDLE_MINUTES, "max_hours": SESSION_MAX_HOURS, "max_failures": LOGIN_MAX_FAILURES, "lock_minutes": LOGIN_LOCK_MINUTES, "locked_accounts": locked},
            "runtime": {"host": runtime.ACTIVE_HOST, "port": runtime.ACTIVE_PORT, "https": request_https, "mode": mode},
        })

    def api_config(self):
        with db_connect() as con:
            settings = {r['key']: r['value'] for r in con.execute("SELECT key,value FROM settings").fetchall()}
            logs = rows_to_dict(con.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 12").fetchall())
            diag_count = con.execute("SELECT COUNT(*) FROM diagnostic").fetchone()[0]
            pc_count = con.execute("SELECT COUNT(DISTINCT ordinateur) FROM diagnostic WHERE ordinateur IS NOT NULL AND TRIM(ordinateur)<>''").fetchone()[0]
        try:
            size_mb = round(APP_DB.stat().st_size / 1024 / 1024, 2)
        except Exception:
            log_unexpected_error('app.api_config.L2354')
            size_mb = 0
        source_info = None
        source_error = ""
        source_path = settings.get("diagnostic_source_path", "")
        if source_path:
            try:
                source_info = source_schema_info(source_path)
            except Exception as exc:
                source_error = str(exc)
        try:
            details_db = supervision.details_store.status()
            details_db["size_mb"] = round((details_db.get("size_bytes") or 0) / 1024 / 1024, 2)
        except Exception as exc:
            log_unexpected_error('app.api_config.L2367')
            details_db = {"path": str(BASE / "Nelyio_Details.db"), "events": 0, "imports": 0, "days": 0, "size_mb": 0, "error": str(exc)}
        self.send_json({
            "settings": settings,
            "runtime": {"host": runtime.ACTIVE_HOST, "port": runtime.ACTIVE_PORT, "lan_ip": local_lan_ip(), "https": bool(getattr(self.server, "techin_https", False))},
            "central_db": {"path": str(APP_DB), "size_mb": size_mb, "diagnostics": diag_count, "pcs": pc_count},
            "details_db": details_db,
            "source_info": source_info,
            "source_error": source_error,
            "import_logs": logs
        })

    def api_save_config(self, user):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try:
            host = validate_host(data.get("web_host", DEFAULT_HOST))
            port = int(data.get("web_port", DEFAULT_PORT))
            if port < 1 or port > 65535:
                raise ValueError("Le port doit être compris entre 1 et 65535")
            minutes = int(data.get("auto_import_minutes", 5))
            if minutes < 1 or minutes > 1440:
                raise ValueError("L'intervalle d'import doit être compris entre 1 et 1440 minutes")
        except (ValueError, TypeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        source = str(data.get("diagnostic_source_path", "") or "").strip().strip('"')
        enabled = "1" if str(data.get("auto_import_enabled", "0")).lower() in {"1", "true", "on", "yes"} else "0"
        tls_enabled = "1" if str(data.get("tls_enabled", "0")).lower() in {"1", "true", "on", "yes"} else "0"
        tls_cert_path = str(data.get("tls_cert_path", "") or "").strip().strip('"')
        tls_key_path = str(data.get("tls_key_path", "") or "").strip().strip('"')
        public_hostname = str(data.get("public_hostname", "stock-manager.nelyio.local") or "").strip()[:253]
        if public_hostname and not re.fullmatch(r"[A-Za-z0-9.-]+", public_hostname):
            return self.send_json({"error": "Nom DNS public invalide"}, 400)
        if tls_enabled == "1":
            if not tls_cert_path or not os.path.isfile(tls_cert_path):
                return self.send_json({"error": "Certificat TLS PEM introuvable"}, 400)
            if not tls_key_path or not os.path.isfile(tls_key_path):
                return self.send_json({"error": "Clé privée TLS PEM introuvable"}, 400)
        with db_connect() as con:
            set_setting(con, "diagnostic_source_path", source, user["username"])
            set_setting(con, "web_host", host, user["username"])
            set_setting(con, "web_port", port, user["username"])
            set_setting(con, "auto_import_enabled", enabled, user["username"])
            set_setting(con, "auto_import_minutes", minutes, user["username"])
            set_setting(con, "tls_enabled", tls_enabled, user["username"])
            set_setting(con, "tls_cert_path", tls_cert_path, user["username"])
            set_setting(con, "tls_key_path", tls_key_path, user["username"])
            set_setting(con, "public_hostname", public_hostname, user["username"])
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "CONFIG_UPDATED", f"host={host}; port={port}; tls={tls_enabled}; auto_import={enabled}; source={source}", self.client_ip()))
            con.commit()
        runtime_tls = bool(getattr(self.server, "techin_https", False))
        restart_required = (host != runtime.ACTIVE_HOST or port != runtime.ACTIVE_PORT or (tls_enabled == "1") != runtime_tls)
        self.send_json({"ok": True, "restart_required": restart_required, "host": host, "port": port, "tls_enabled": tls_enabled})

    def api_test_source(self):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        path = str(data.get("source_path", "") or "").strip()
        try:
            info = source_schema_info(path)
            self.send_json({"ok": True, "info": info})
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def api_import(self, user):
        data = self.read_json() or {}
        path = str(data.get("source_path", "") or get_setting("diagnostic_source_path", "")).strip()
        try:
            result = import_diagnostic_source(path, user["username"])
            self.send_json(result)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

