"""Routes Administration : support ; corps V56.8 deplaces sans changement."""
import json

import re

import db_compat as sqlite3

from app_db import db_connect, get_setting, now_text, set_setting

from classification import classify_site_details, normalize_user_key, parse_ip_selector, refresh_classification_cache

from support_priority import (
    COLOR_RE, LEGACY_FIELDS, legacy_thresholds_from_conditions, load_priority_policies,
    metric_catalog, public_policy_snapshot, validate_conditions,
)

from support_scoring import (
    SCORE_SETTING_KEY, load_score_config, public_score_config, validate_score_config,
)


def _priority_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off", "no", "non"}
    return bool(value)


def _priority_name(value):
    name = " ".join(str(value or "").split()).strip()
    if not name or len(name) > 60 or any(ord(ch) < 32 for ch in name):
        raise ValueError("Nom de priorité invalide (1 à 60 caractères)")
    return name


def _priority_color(value):
    color = str(value or "#667085").strip().upper()
    if not COLOR_RE.fullmatch(color):
        raise ValueError("Couleur de priorité invalide")
    return color



class AdminSupportRoutesMixin:
    def api_support_score_policy(self, user):
        data = self.read_json() or {}
        try:
            score_config = validate_score_config(data)
        except (TypeError, ValueError) as exc:
            return self.send_json({"error": str(exc) or "Configuration de score invalide"}, 400)
        payload = json.dumps(score_config, ensure_ascii=False, separators=(",", ":"))
        with db_connect() as con:
            set_setting(con, SCORE_SETTING_KEY, payload, user["username"])
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SUPPORT_SCORE_POLICY_UPDATED", payload, self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "support_score_config": score_config})

    def api_support_priority_policy(self, user):
        data = self.read_json() or {}
        try:
            priority = _priority_name(data.get("priority"))
            original = _priority_name(data.get("original_priority")) if str(data.get("original_priority", "")).strip() else ""
            match_mode = str(data.get("match_mode", "ANY")).strip().upper()
            if match_mode not in {"ANY", "ALL"}:
                raise ValueError("Mode de correspondance invalide")
            rank = max(-10000, min(10000, int(data.get("rank", 100))))
            color = _priority_color(data.get("color"))
            enabled = 1 if _priority_bool(data.get("enabled", True), True) else 0
            is_fallback = 1 if _priority_bool(data.get("is_fallback", False)) else 0
            conditions = validate_conditions(data.get("conditions", []), allow_empty=is_fallback == 1)
            if is_fallback:
                conditions = []
                enabled = 1
            elif not conditions:
                raise ValueError("Configurez au moins une condition ou définissez ce niveau comme repli")
        except (TypeError, ValueError) as exc:
            return self.send_json({"error": str(exc) or "Politique de priorité invalide"}, 400)

        legacy = legacy_thresholds_from_conditions(conditions)
        conditions_json = json.dumps(conditions, ensure_ascii=False, separators=(",", ":"))
        with db_connect() as con:
            current = None
            lookup = original or priority
            existing = con.execute("SELECT priority,is_fallback FROM support_priority_policies").fetchall()
            if lookup:
                current = next((r for r in existing if r["priority"] == lookup), None)
            duplicate = next((r for r in existing if str(r["priority"]).casefold() == priority.casefold()), None)
            if duplicate and (not current or duplicate["priority"] != current["priority"]):
                return self.send_json({"error": "Un niveau de priorité porte déjà ce nom"}, 409)
            if current and current["is_fallback"] and not is_fallback:
                other = con.execute("SELECT 1 FROM support_priority_policies WHERE is_fallback=1 AND priority<>? LIMIT 1", (current["priority"],)).fetchone()
                if not other:
                    return self.send_json({"error": "Choisissez d'abord un autre niveau de repli. Il doit toujours en rester un."}, 409)
            if is_fallback:
                # The previous fallback has no conditions by design. Disable it
                # when another level becomes the fallback so it cannot look
                # active while matching nothing; the administrator can give it
                # new conditions and reactivate it afterwards.
                con.execute("UPDATE support_priority_policies SET is_fallback=0,enabled=0 WHERE is_fallback=1")

            params = (priority, rank, match_mode, legacy["disconnects_per_day"], legacy["call_percent"],
                      legacy["affected_days_percent"], legacy["lost_minutes_per_day"], enabled, color,
                      is_fallback, conditions_json, user["username"])
            try:
                if current:
                    con.execute("""UPDATE support_priority_policies SET
                        priority=?,rank=?,match_mode=?,disconnects_per_day=?,call_percent=?,
                        affected_days_percent=?,lost_minutes_per_day=?,enabled=?,color=?,is_fallback=?,
                        conditions_json=?,updated_at=CURRENT_TIMESTAMP,updated_by=?
                        WHERE priority=?""", (*params, current["priority"]))
                    action = "SUPPORT_PRIORITY_POLICY_UPDATED"
                else:
                    con.execute("""INSERT INTO support_priority_policies(
                        priority,rank,match_mode,disconnects_per_day,call_percent,affected_days_percent,
                        lost_minutes_per_day,enabled,color,is_fallback,conditions_json,updated_at,updated_by
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?)""", params)
                    action = "SUPPORT_PRIORITY_POLICY_CREATED"
            except sqlite3.IntegrityError:
                return self.send_json({"error": "Un niveau de priorité porte déjà ce nom"}, 409)
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], action,
                         f"{original or priority} -> {priority}; rang={rank}; repli={is_fallback}; mode={match_mode}; conditions={conditions_json}",
                         self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "priority": priority})

    def api_support_priority_delete(self, user):
        data = self.read_json() or {}
        try:
            priority = _priority_name(data.get("priority"))
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        with db_connect() as con:
            row = con.execute("SELECT priority,is_fallback FROM support_priority_policies WHERE priority=?", (priority,)).fetchone()
            if not row:
                return self.send_json({"error": "Niveau de priorité introuvable"}, 404)
            if row["is_fallback"]:
                return self.send_json({"error": "Le niveau de repli ne peut pas être supprimé. Choisissez d'abord un autre repli."}, 409)
            con.execute("DELETE FROM support_priority_policies WHERE priority=?", (priority,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SUPPORT_PRIORITY_POLICY_DELETED", priority, self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_support_exclusion(self, user):
        data = self.read_json() or {}
        identifier = str(data.get("user_identifier", "") or "").strip()
        raw_key = normalize_user_key(identifier)
        key = raw_key[1:] if re.fullmatch(r"S\d+", raw_key or "") else raw_key
        reason = str(data.get("reason", "") or "").strip()[:300]
        if not key or len(key) > 100:
            return self.send_json({"error": "Agent invalide"}, 400)
        aliases = [key]
        if re.fullmatch(r"\d+", key):
            aliases.append("S" + key)
        with db_connect() as con:
            known = None
            for candidate in aliases:
                known = con.execute("SELECT user_key,user_identifier FROM user_directory WHERE user_key=?", (candidate,)).fetchone()
                if known:
                    key = known["user_key"]
                    break
            stored_identifier = str(known["user_identifier"] if known else (key or identifier))
            con.execute("""INSERT INTO support_agent_exclusions(user_key,user_identifier,reason,created_by) VALUES(?,?,?,?)
                         ON CONFLICT(user_key) DO UPDATE SET user_identifier=excluded.user_identifier,reason=excluded.reason,created_at=CURRENT_TIMESTAMP,created_by=excluded.created_by""",
                        (key, stored_identifier, reason, user["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SUPPORT_AGENT_EXCLUDED", f"{key}: {reason or 'sans motif'}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "user_key": key})

    def api_support_exclusion_delete(self, user):
        data = self.read_json() or {}
        raw_key = normalize_user_key(data.get("user_key") or data.get("user_identifier"))
        if not raw_key:
            return self.send_json({"error": "Agent invalide"}, 400)
        aliases = [raw_key]
        if re.fullmatch(r"S\d+", raw_key):
            aliases.append(raw_key[1:])
        elif re.fullmatch(r"\d+", raw_key):
            aliases.append("S" + raw_key)
        with db_connect() as con:
            row = None
            key = raw_key
            for candidate in aliases:
                row = con.execute("SELECT user_key,user_identifier FROM support_agent_exclusions WHERE user_key=?", (candidate,)).fetchone()
                if row:
                    key = row["user_key"]
                    break
            if not row:
                return self.send_json({"error": "Agent non exclu"}, 404)
            con.execute("DELETE FROM support_agent_exclusions WHERE user_key=?", (key,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "SUPPORT_AGENT_RESTORED", key, self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

