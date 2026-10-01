from datetime import datetime, timedelta
import hashlib
import json
import re
import secrets
import db_compat as sqlite3

import app_config as cfg
from app_db import db_connect, now_text
from auth_service import access_profile, password_hash, verify_password
from error_log import log_unexpected_error
from inventory_service import clean_username, rows_to_dict

SESSION_COOKIE = cfg.SESSION_COOKIE
SESSION_MAX_HOURS = cfg.SESSION_MAX_HOURS
LOGIN_MAX_FAILURES = cfg.LOGIN_MAX_FAILURES
LOGIN_LOCK_MINUTES = cfg.LOGIN_LOCK_MINUTES
ADMIN_PASSWORD_FILE = cfg.ADMIN_PASSWORD_FILE
ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_INTERFACES = cfg.ACCESS_INTERFACES
ROLES = cfg.ROLES

class AuthRoutesMixin:
    def api_login(self):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        username = str(data.get("username", "")).strip()[:80]
        password = str(data.get("password", ""))
        source_ip = self.client_ip()
        now = datetime.now()
        with db_connect() as con:
            row = con.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()
            if row and row["lock_until"]:
                try:
                    lock_until = datetime.fromisoformat(row["lock_until"])
                    if lock_until > now:
                        remaining = max(1, int((lock_until-now).total_seconds()//60)+1)
                        con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                                    (username, "LOGIN_LOCKED", f"Compte verrouillé; {remaining} min restantes", source_ip))
                        con.commit()
                        return self.send_json({"error": f"Compte temporairement verrouillé. Réessayez dans environ {remaining} minute(s)."}, 429)
                except Exception:
                    log_unexpected_error('app.api_login.L1379')
                    pass
            valid = bool(row and row["active"] and verify_password(password, row["password_salt"], row["password_hash"]))
            if not valid:
                if row:
                    failures = int(row["failed_login_count"] or 0) + 1
                    lock_text = None
                    if failures >= LOGIN_MAX_FAILURES:
                        lock_text = (now + timedelta(minutes=LOGIN_LOCK_MINUTES)).strftime("%Y-%m-%d %H:%M:%S")
                        failures = 0
                    con.execute("UPDATE users SET failed_login_count=?,last_failed_at=?,lock_until=? WHERE id=?",
                                (failures, now_text(), lock_text, row["id"]))
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (username, "LOGIN_FAILED", "Échec de connexion", source_ip))
                con.commit()
                return self.send_json({"error": "Identifiant ou mot de passe incorrect"}, 401)

            token = secrets.token_urlsafe(48)
            csrf_token = secrets.token_urlsafe(32)
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            expires = now + timedelta(hours=SESSION_MAX_HOURS)
            con.execute("DELETE FROM sessions WHERE expires_at<=?", (now_text(),))
            con.execute("INSERT INTO sessions(token_hash,user_id,created_at,expires_at,csrf_token,last_seen_at) VALUES(?,?,?,?,?,?)",
                        (th, row["id"], now_text(), expires.strftime("%Y-%m-%d %H:%M:%S"), csrf_token, now_text()))
            con.execute("UPDATE users SET last_login_at=?,failed_login_count=0,last_failed_at=NULL,lock_until=NULL WHERE id=?", (now_text(), row["id"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (row["username"], "LOGIN_OK", "Connexion réussie", source_ip))
            con.commit()
        role = "technician" if row["role"] == "user" else row["role"]
        with db_connect() as access_con:
            profile = access_profile(access_con, row["id"], role)
        cookie = f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_MAX_HOURS*3600}"
        if self.request_is_https():
            cookie += "; Secure"
        login_user = {"id": row["id"], "username": row["username"], "role": role, **profile}
        self.send_json({"ok": True, "user": login_user, "csrf_token": csrf_token}, extra={"Set-Cookie": cookie})

    def api_logout(self):
        token = self.cookie_token()
        username = ""
        if token:
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            with db_connect() as con:
                row = con.execute("SELECT u.username FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (th,)).fetchone()
                username = row["username"] if row else ""
                con.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (username, "LOGOUT", "Déconnexion", self.client_ip()))
                con.commit()
        cookie = f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        if self.request_is_https():
            cookie += "; Secure"
        self.send_json({"ok": True}, extra={"Set-Cookie": cookie})

    def api_change_password(self, user):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        current = str(data.get("current_password", ""))
        new = str(data.get("new_password", ""))
        if (len(new) < 12 or not re.search(r"[a-z]", new) or not re.search(r"[A-Z]", new)
                or not re.search(r"\d", new) or not re.search(r"[^A-Za-z0-9]", new)):
            return self.send_json({"error": "Le nouveau mot de passe doit contenir au moins 12 caractères, majuscule, minuscule, chiffre et caractère spécial."}, 400)
        with db_connect() as con:
            row = con.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
            if not row or not verify_password(current, row["password_salt"], row["password_hash"]):
                return self.send_json({"error": "Mot de passe actuel incorrect"}, 400)
            salt, ph = password_hash(new)
            con.execute("UPDATE users SET password_salt=?,password_hash=?,password_changed_at=? WHERE id=?",
                        (salt, ph, now_text(), user["id"]))
            current_token = self.cookie_token()
            current_hash = hashlib.sha256(current_token.encode("utf-8")).hexdigest() if current_token else ""
            con.execute("DELETE FROM sessions WHERE user_id=? AND token_hash<>?", (user["id"], current_hash))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "PASSWORD_CHANGED", "Mot de passe modifié; autres sessions invalidées", self.client_ip()))
            con.commit()
        try:
            if ADMIN_PASSWORD_FILE.exists() and user["username"].lower() == "admin":
                ADMIN_PASSWORD_FILE.unlink()
        except Exception:
            log_unexpected_error('app.api_change_password.L1458')
            pass
        self.send_json({"ok": True})

    def api_users(self):
        with db_connect() as con:
            rows = rows_to_dict(con.execute("""
                SELECT u.id,u.username,CASE WHEN u.role='user' THEN 'technician' ELSE u.role END role,
                       u.active,u.created_at,u.created_by,u.last_login_at,u.password_changed_at,u.failed_login_count,u.lock_until,
                       g.id access_group_id,g.name access_group_name
                FROM users u
                LEFT JOIN access_group_members m ON m.user_id=u.id
                LEFT JOIN access_groups g ON g.id=m.group_id
                ORDER BY u.username COLLATE NOCASE
            """).fetchall())
            groups = rows_to_dict(con.execute("""
                SELECT g.id,g.name,g.description,g.created_at,g.created_by,COUNT(m.user_id) member_count
                FROM access_groups g LEFT JOIN access_group_members m ON m.group_id=g.id
                GROUP BY g.id ORDER BY g.name COLLATE NOCASE
            """).fetchall())
            permissions = rows_to_dict(con.execute("SELECT group_id,module,access_level FROM access_group_permissions ORDER BY group_id,module").fetchall())
            interface_permissions = rows_to_dict(con.execute("SELECT group_id,interface_key,access_level FROM access_group_interface_permissions ORDER BY group_id,interface_key").fetchall())
            scope_policies = {int(r["group_id"]): dict(r) for r in con.execute("SELECT group_id,scope_mode,default_business_group_id,filter_locked FROM access_group_scope_policy").fetchall()}
            scope_rows = rows_to_dict(con.execute("SELECT access_group_id,business_group_id FROM access_group_scopes ORDER BY access_group_id,business_group_id").fetchall())
            business_groups = rows_to_dict(con.execute("SELECT id,name,service_name,description FROM user_groups ORDER BY COALESCE(service_name,''),name COLLATE NOCASE").fetchall())
            profile_rows = rows_to_dict(con.execute("SELECT id,name,description,snapshot_json,created_at,created_by,updated_at,updated_by FROM access_profiles ORDER BY name COLLATE NOCASE").fetchall())
            effective_profiles = {int(u["id"]): access_profile(con, u["id"], u["role"]) for u in rows}
        perm_map = {}
        for item in permissions:
            perm_map.setdefault(item["group_id"], {})[item["module"]] = int(item["access_level"] or 0)
        iface_map = {}
        for item in interface_permissions:
            iface_map.setdefault(item["group_id"], {})[item["interface_key"]] = int(item["access_level"] or 0)
        scope_map = {}
        for item in scope_rows:
            scope_map.setdefault(int(item["access_group_id"]), []).append(str(item["business_group_id"]))
        for g in groups:
            gid = int(g["id"])
            g["permissions"] = {key: int(perm_map.get(gid, {}).get(key, 0)) for key in ACCESS_MODULES}
            g["interface_permissions"] = {key: int(iface_map.get(gid, {}).get(key, 0)) for key in ACCESS_INTERFACES}
            policy = scope_policies.get(gid) or {}
            g["scope_policy"] = {
                "scope_mode": str(policy.get("scope_mode") or "ALL"),
                "allowed_group_ids": scope_map.get(gid, []),
                "default_group_id": str(policy.get("default_business_group_id") or ""),
                "filter_locked": bool(int(policy.get("filter_locked") or 0)),
            }
        access_profiles = []
        for item in profile_rows:
            try:
                snapshot = json.loads(item.get("snapshot_json") or "{}")
            except Exception:
                snapshot = {}
            interfaces = snapshot.get("interfaces") or {} if isinstance(snapshot, dict) else {}
            scope = snapshot.get("scope") or {} if isinstance(snapshot, dict) else {}
            item["snapshot"] = snapshot if isinstance(snapshot, dict) else {}
            item["summary"] = {
                "write": sum(1 for v in interfaces.values() if int(v or 0) >= 2),
                "read": sum(1 for v in interfaces.values() if int(v or 0) == 1),
                "scope_mode": str(scope.get("mode") or "ALL"),
                "allowed_group_ids": [str(x) for x in (scope.get("allowed_group_ids") or [])],
                "default_group_id": str(scope.get("default_group_id") or ""),
                "filter_locked": bool(scope.get("filter_locked")),
                "ani": bool(int((snapshot or {}).get("ani", 0) or 0)),
            }
            item.pop("snapshot_json", None)
            access_profiles.append(item)
        for u in rows:
            profile = effective_profiles[int(u["id"])]
            u["effective_permissions"] = profile["permissions"]
            u["effective_interface_permissions"] = profile.get("interface_permissions") or {}
            u["effective_group_scope"] = profile.get("group_scope") or {}
        self.send_json({
            "rows": rows,
            "access_groups": groups,
            "modules": [{"key": k, **v} for k, v in ACCESS_MODULES.items()],
            "interfaces": [{"key": k, **v} for k, v in ACCESS_INTERFACES.items()],
            "business_groups": business_groups,
            "access_profiles": access_profiles,
        })

    def api_create_user(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        username = clean_username(data.get("username"))
        password = str(data.get("password", ""))
        role = str(data.get("role", "viewer"))
        if not username:
            return self.send_json({"error": "Identifiant invalide (3-40 caractères: lettres, chiffres, . _ -)"}, 400)
        if role not in ROLES:
            role = "viewer"
        if role == "admin" and actor.get("role") != "admin":
            return self.send_json({"error": "Seul un administrateur système peut créer un autre administrateur système"}, 403)
        try:
            group_id = int(data.get("access_group_id")) if str(data.get("access_group_id", "")).strip() else None
        except Exception:
            return self.send_json({"error": "Groupe d'accès invalide"}, 400)
        if (len(password) < 12 or not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password)
                or not re.search(r"\d", password) or not re.search(r"[^A-Za-z0-9]", password)):
            return self.send_json({"error": "Mot de passe: 12 caractères minimum avec majuscule, minuscule, chiffre et caractère spécial."}, 400)
        salt, ph = password_hash(password)
        try:
            with db_connect() as con:
                if group_id is not None and not con.execute("SELECT 1 FROM access_groups WHERE id=?", (group_id,)).fetchone():
                    return self.send_json({"error": "Groupe d'accès introuvable"}, 404)
                cur = con.execute("INSERT INTO users(username,password_salt,password_hash,role,created_by) VALUES(?,?,?,?,?)",
                                  (username, salt, ph, role, actor["username"]))
                uid = cur.lastrowid
                if role != "admin" and group_id is not None:
                    con.execute("INSERT INTO access_group_members(user_id,group_id,created_by) VALUES(?,?,?)", (uid, group_id, actor["username"]))
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (actor["username"], "USER_CREATED", f"Utilisateur {username} ({role}), groupe={group_id or 'aucun'}", self.client_ip()))
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Cet utilisateur existe déjà"}, 409)
        self.send_json({"ok": True})

    def api_toggle_user(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try:
            uid = int(data.get("id"))
        except Exception:
            return self.send_json({"error": "Utilisateur invalide"}, 400)
        if uid == actor["id"]:
            return self.send_json({"error": "Vous ne pouvez pas désactiver votre propre compte"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT username,active,role FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return self.send_json({"error": "Utilisateur introuvable"}, 404)
            if row["role"] == "admin" and actor.get("role") != "admin":
                return self.send_json({"error": "Seul un administrateur système peut modifier un autre administrateur système"}, 403)
            new = 0 if row["active"] else 1
            con.execute("UPDATE users SET active=? WHERE id=?", (new, uid))
            if not new:
                con.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor["username"], "USER_TOGGLED", f"{row['username']} -> {'actif' if new else 'désactivé'}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "active": new})
