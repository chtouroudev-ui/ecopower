"""Routes Administration : access ; corps V56.8 deplaces sans changement."""
import app_config as cfg
import json

import db_compat as sqlite3

from app_db import db_connect, get_setting, now_text, set_setting

from classification import classify_site_details, normalize_user_key, parse_ip_selector, refresh_classification_cache

ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_INTERFACES = cfg.ACCESS_INTERFACES

ACCESS_NONE = cfg.ACCESS_NONE
ACCESS_READ = cfg.ACCESS_READ
ACCESS_WRITE = cfg.ACCESS_WRITE



class AdminAccessRoutesMixin:
    def _access_group_snapshot(self, con, gid):
        group = con.execute("SELECT id,name FROM access_groups WHERE id=?", (gid,)).fetchone()
        if not group:
            raise KeyError("Groupe d'accès introuvable")
        iface_rows = {
            str(r["interface_key"]): int(r["access_level"] or 0)
            for r in con.execute(
                "SELECT interface_key,access_level FROM access_group_interface_permissions WHERE group_id=?",
                (gid,),
            ).fetchall()
        }
        interfaces = {}
        for key, meta in ACCESS_INTERFACES.items():
            level = max(0, min(2, int(iface_rows.get(key, 0) or 0)))
            if meta.get("write_only"):
                level = ACCESS_WRITE if level >= ACCESS_WRITE else ACCESS_NONE
            elif not meta.get("write") and level > ACCESS_READ:
                level = ACCESS_READ
            interfaces[key] = level
        ani_row = con.execute(
            "SELECT access_level FROM access_group_permissions WHERE group_id=? AND module='ani'",
            (gid,),
        ).fetchone()
        ani = ACCESS_READ if ani_row and int(ani_row[0] or 0) >= ACCESS_READ else ACCESS_NONE
        policy = con.execute(
            "SELECT scope_mode,default_business_group_id,filter_locked FROM access_group_scope_policy WHERE group_id=?",
            (gid,),
        ).fetchone()
        allowed = [
            int(r[0])
            for r in con.execute(
                "SELECT business_group_id FROM access_group_scopes WHERE access_group_id=? ORDER BY business_group_id",
                (gid,),
            ).fetchall()
        ]
        scope = {
            "mode": str(policy["scope_mode"] if policy else "ALL").upper(),
            "allowed_group_ids": allowed,
            "default_group_id": int(policy["default_business_group_id"]) if policy and policy["default_business_group_id"] is not None else None,
            "filter_locked": bool(int(policy["filter_locked"] or 0)) if policy else False,
        }
        return {"schema_version": 1, "interfaces": interfaces, "ani": ani, "scope": scope}

    def _normalize_access_snapshot(self, con, raw):
        if not isinstance(raw, dict):
            raise ValueError("Profil d'accès invalide")
        incoming = raw.get("interfaces") or {}
        if not isinstance(incoming, dict):
            raise ValueError("Permissions d'interface invalides")
        interfaces = {}
        for key, meta in ACCESS_INTERFACES.items():
            try:
                level = int(incoming.get(key, 0))
            except Exception:
                level = 0
            level = max(0, min(2, level))
            if meta.get("write_only"):
                level = ACCESS_WRITE if level >= ACCESS_WRITE else ACCESS_NONE
            elif not meta.get("write") and level > ACCESS_READ:
                level = ACCESS_READ
            interfaces[key] = level
        try:
            ani = ACCESS_READ if int(raw.get("ani", 0) or 0) >= ACCESS_READ else ACCESS_NONE
        except Exception:
            ani = ACCESS_NONE
        scope = raw.get("scope") or {}
        if not isinstance(scope, dict):
            raise ValueError("Périmètre métier invalide")
        mode = str(scope.get("mode") or "ALL").upper()
        if mode not in {"ALL", "SELECTED"}:
            raise ValueError("Mode de périmètre invalide")
        try:
            allowed = sorted({int(x) for x in (scope.get("allowed_group_ids") or []) if str(x).strip()})
        except Exception:
            raise ValueError("Identifiant de groupe métier invalide")
        try:
            default_gid = int(scope.get("default_group_id")) if str(scope.get("default_group_id") or "").strip() else None
        except Exception:
            raise ValueError("Groupe par défaut invalide")
        locked = bool(scope.get("filter_locked"))
        existing = {int(r[0]) for r in con.execute("SELECT id FROM user_groups").fetchall()}
        missing = sorted(x for x in allowed if x not in existing)
        if default_gid is not None and default_gid not in existing:
            missing.append(default_gid)
        if missing:
            raise ValueError("Le profil référence un groupe métier supprimé: " + ", ".join(str(x) for x in sorted(set(missing))))
        if mode == "SELECTED" and not allowed:
            raise ValueError("Un profil limité doit contenir au moins un groupe métier")
        if mode == "SELECTED" and default_gid is not None and default_gid not in set(allowed):
            raise ValueError("Le groupe par défaut doit faire partie des groupes autorisés")
        if locked and default_gid is None:
            raise ValueError("Un filtre verrouillé nécessite un groupe par défaut")
        return {
            "schema_version": 1,
            "interfaces": interfaces,
            "ani": ani,
            "scope": {
                "mode": mode,
                "allowed_group_ids": allowed,
                "default_group_id": default_gid,
                "filter_locked": locked,
            },
        }

    def _apply_access_snapshot(self, con, gid, snapshot, actor_name):
        snap = self._normalize_access_snapshot(con, snapshot)
        if not con.execute("SELECT 1 FROM access_groups WHERE id=?", (gid,)).fetchone():
            raise KeyError("Groupe d'accès introuvable")
        for key, level in snap["interfaces"].items():
            con.execute(
                """INSERT INTO access_group_interface_permissions(group_id,interface_key,access_level,updated_by)
                   VALUES(?,?,?,?) ON CONFLICT(group_id,interface_key) DO UPDATE SET
                   access_level=excluded.access_level,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                (gid, key, level, actor_name),
            )
        con.execute(
            """INSERT INTO access_group_permissions(group_id,module,access_level,updated_by)
               VALUES(?,?,?,?) ON CONFLICT(group_id,module) DO UPDATE SET
               access_level=excluded.access_level,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
            (gid, "ani", snap["ani"], actor_name),
        )
        self._sync_module_permissions_from_interfaces(con, gid, actor_name)
        scope = snap["scope"]
        con.execute("DELETE FROM access_group_scopes WHERE access_group_id=?", (gid,))
        for business_gid in scope["allowed_group_ids"]:
            con.execute(
                "INSERT INTO access_group_scopes(access_group_id,business_group_id,created_by) VALUES(?,?,?)",
                (gid, business_gid, actor_name),
            )
        con.execute(
            """INSERT INTO access_group_scope_policy(group_id,scope_mode,default_business_group_id,filter_locked,updated_by)
               VALUES(?,?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET
               scope_mode=excluded.scope_mode,default_business_group_id=excluded.default_business_group_id,
               filter_locked=excluded.filter_locked,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
            (gid, scope["mode"], scope["default_group_id"], 1 if scope["filter_locked"] else 0, actor_name),
        )
        return snap

    def api_access_profile_save(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        name = " ".join(str(data.get("name", "")).split()).strip()[:80]
        description = str(data.get("description", "") or "").strip()[:300]
        if not name:
            return self.send_json({"error": "Nom du profil requis"}, 400)
        try:
            profile_id = int(data.get("id")) if str(data.get("id", "")).strip() else None
            source_gid = int(data.get("source_group_id")) if str(data.get("source_group_id", "")).strip() else None
            source_pid = int(data.get("source_profile_id")) if str(data.get("source_profile_id", "")).strip() else None
        except Exception:
            return self.send_json({"error": "Source du profil invalide"}, 400)
        if source_gid is not None and source_pid is not None:
            return self.send_json({"error": "Choisissez une seule source pour le profil"}, 400)
        try:
            with db_connect() as con:
                current = None
                if profile_id is not None:
                    current = con.execute("SELECT id,snapshot_json FROM access_profiles WHERE id=?", (profile_id,)).fetchone()
                    if not current:
                        return self.send_json({"error": "Profil introuvable"}, 404)
                if source_gid is not None:
                    snapshot = self._access_group_snapshot(con, source_gid)
                elif source_pid is not None:
                    src = con.execute("SELECT snapshot_json FROM access_profiles WHERE id=?", (source_pid,)).fetchone()
                    if not src:
                        return self.send_json({"error": "Profil source introuvable"}, 404)
                    snapshot = self._normalize_access_snapshot(con, json.loads(src[0]))
                elif current is not None:
                    snapshot = self._normalize_access_snapshot(con, json.loads(current["snapshot_json"]))
                else:
                    return self.send_json({"error": "Sélectionnez un groupe d'accès source"}, 400)
                payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if profile_id is None:
                    cur = con.execute(
                        "INSERT INTO access_profiles(name,description,snapshot_json,created_by,updated_by) VALUES(?,?,?,?,?)",
                        (name, description, payload, actor["username"], actor["username"]),
                    )
                    profile_id = int(cur.lastrowid)
                    action = "ACCESS_PROFILE_CREATED"
                else:
                    con.execute(
                        "UPDATE access_profiles SET name=?,description=?,snapshot_json=?,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE id=?",
                        (name, description, payload, actor["username"], profile_id),
                    )
                    action = "ACCESS_PROFILE_UPDATED"
                con.execute(
                    "INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                    (actor["username"], action, f"{profile_id}: {name}", self.client_ip()),
                )
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Un profil d'accès porte déjà ce nom"}, 409)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 409)
        self.send_json({"ok": True, "id": profile_id})

    def api_access_profile_delete(self, actor):
        data = self.read_json() or {}
        try:
            profile_id = int(data.get("id"))
        except Exception:
            return self.send_json({"error": "Profil invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT name FROM access_profiles WHERE id=?", (profile_id,)).fetchone()
            if not row:
                return self.send_json({"error": "Profil introuvable"}, 404)
            con.execute("DELETE FROM access_profiles WHERE id=?", (profile_id,))
            con.execute(
                "INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                (actor["username"], "ACCESS_PROFILE_DELETED", row["name"], self.client_ip()),
            )
            con.commit()
        self.send_json({"ok": True})

    def api_access_profile_apply(self, actor):
        data = self.read_json() or {}
        try:
            profile_id = int(data.get("profile_id"))
            gid = int(data.get("group_id"))
        except Exception:
            return self.send_json({"error": "Profil ou groupe invalide"}, 400)
        try:
            with db_connect() as con:
                profile = con.execute("SELECT name,snapshot_json FROM access_profiles WHERE id=?", (profile_id,)).fetchone()
                group = con.execute("SELECT name FROM access_groups WHERE id=?", (gid,)).fetchone()
                if not profile:
                    return self.send_json({"error": "Profil introuvable"}, 404)
                if not group:
                    return self.send_json({"error": "Groupe d'accès introuvable"}, 404)
                snapshot = self._apply_access_snapshot(con, gid, json.loads(profile["snapshot_json"]), actor["username"])
                con.execute(
                    "DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM access_group_members WHERE group_id=?) AND user_id<>?",
                    (gid, actor["id"]),
                )
                con.execute(
                    "INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                    (actor["username"], "ACCESS_PROFILE_APPLIED", f"{profile['name']} -> {group['name']}", self.client_ip()),
                )
                con.commit()
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 409)
        self.send_json({"ok": True, "snapshot": snapshot})

    def api_access_group_clone(self, actor):
        data = self.read_json() or {}
        try:
            source_gid = int(data.get("source_group_id"))
        except Exception:
            return self.send_json({"error": "Groupe source invalide"}, 400)
        name = " ".join(str(data.get("name", "")).split()).strip()[:80]
        description = str(data.get("description", "") or "").strip()[:300]
        if not name:
            return self.send_json({"error": "Nom du nouveau groupe requis"}, 400)
        try:
            with db_connect() as con:
                source = con.execute("SELECT name FROM access_groups WHERE id=?", (source_gid,)).fetchone()
                if not source:
                    return self.send_json({"error": "Groupe source introuvable"}, 404)
                snapshot = self._access_group_snapshot(con, source_gid)
                cur = con.execute(
                    "INSERT INTO access_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)",
                    (name, description, actor["username"], actor["username"]),
                )
                gid = int(cur.lastrowid)
                self._apply_access_snapshot(con, gid, snapshot, actor["username"])
                con.execute(
                    "INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                    (actor["username"], "ACCESS_GROUP_CLONED", f"{source['name']} -> {name}", self.client_ip()),
                )
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Un groupe d'accès porte déjà ce nom"}, 409)
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 409)
        self.send_json({"ok": True, "id": gid}, 201)

    def api_access_group_from_profile(self, actor):
        data = self.read_json() or {}
        try:
            profile_id = int(data.get("profile_id"))
        except Exception:
            return self.send_json({"error": "Profil invalide"}, 400)
        name = " ".join(str(data.get("name", "")).split()).strip()[:80]
        description = str(data.get("description", "") or "").strip()[:300]
        if not name:
            return self.send_json({"error": "Nom du nouveau groupe requis"}, 400)
        try:
            with db_connect() as con:
                profile = con.execute("SELECT name,snapshot_json FROM access_profiles WHERE id=?", (profile_id,)).fetchone()
                if not profile:
                    return self.send_json({"error": "Profil introuvable"}, 404)
                snapshot = self._normalize_access_snapshot(con, json.loads(profile["snapshot_json"]))
                cur = con.execute(
                    "INSERT INTO access_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)",
                    (name, description, actor["username"], actor["username"]),
                )
                gid = int(cur.lastrowid)
                self._apply_access_snapshot(con, gid, snapshot, actor["username"])
                con.execute(
                    "INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                    (actor["username"], "ACCESS_GROUP_FROM_PROFILE", f"{profile['name']} -> {name}", self.client_ip()),
                )
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Un groupe d'accès porte déjà ce nom"}, 409)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 409)
        self.send_json({"ok": True, "id": gid}, 201)

    def api_access_group_save(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        name = " ".join(str(data.get("name", "")).split()).strip()[:80]
        description = str(data.get("description", "") or "").strip()[:300]
        if not name:
            return self.send_json({"error": "Nom du groupe requis"}, 400)
        try:
            gid = int(data.get("id")) if str(data.get("id", "")).strip() else None
        except Exception:
            return self.send_json({"error": "Groupe invalide"}, 400)
        try:
            with db_connect() as con:
                if gid:
                    if not con.execute("SELECT 1 FROM access_groups WHERE id=?", (gid,)).fetchone():
                        return self.send_json({"error": "Groupe introuvable"}, 404)
                    con.execute("UPDATE access_groups SET name=?,description=?,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE id=?",
                                (name, description, actor["username"], gid))
                    action = "ACCESS_GROUP_UPDATED"
                else:
                    cur = con.execute("INSERT INTO access_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)",
                                      (name, description, actor["username"], actor["username"]))
                    gid = cur.lastrowid
                    for module in ACCESS_MODULES:
                        con.execute("INSERT INTO access_group_permissions(group_id,module,access_level,updated_by) VALUES(?,?,0,?)",
                                    (gid, module, actor["username"]))
                    for interface_key in ACCESS_INTERFACES:
                        con.execute("INSERT INTO access_group_interface_permissions(group_id,interface_key,access_level,updated_by) VALUES(?,?,0,?)",
                                    (gid, interface_key, actor["username"]))
                    con.execute("INSERT INTO access_group_scope_policy(group_id,scope_mode,filter_locked,updated_by) VALUES(?,'ALL',0,?)",
                                (gid, actor["username"]))
                    action = "ACCESS_GROUP_CREATED"
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (actor["username"], action, f"{gid}: {name}", self.client_ip()))
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Un groupe d'accès porte déjà ce nom"}, 409)
        self.send_json({"ok": True, "id": gid})

    def api_access_group_delete(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try: gid = int(data.get("id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT name FROM access_groups WHERE id=?", (gid,)).fetchone()
            if not row:
                return self.send_json({"error": "Groupe introuvable"}, 404)
            members = con.execute("SELECT COUNT(*) FROM access_group_members WHERE group_id=?", (gid,)).fetchone()[0]
            if members:
                return self.send_json({"error": f"Ce groupe contient encore {members} utilisateur(s). Réaffectez-les avant de le supprimer."}, 409)
            con.execute("DELETE FROM access_groups WHERE id=?", (gid,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor["username"], "ACCESS_GROUP_DELETED", row["name"], self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_access_group_member(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try:
            uid = int(data.get("user_id"))
            gid = int(data.get("group_id")) if str(data.get("group_id", "")).strip() else None
        except Exception:
            return self.send_json({"error": "Utilisateur ou groupe invalide"}, 400)
        with db_connect() as con:
            target = con.execute("SELECT username,role FROM users WHERE id=?", (uid,)).fetchone()
            if not target:
                return self.send_json({"error": "Utilisateur introuvable"}, 404)
            if target["role"] == "admin":
                return self.send_json({"error": "Les administrateurs système ont toujours tous les droits et ne dépendent pas d'un groupe d'accès"}, 400)
            if gid is not None and not con.execute("SELECT 1 FROM access_groups WHERE id=?", (gid,)).fetchone():
                return self.send_json({"error": "Groupe introuvable"}, 404)
            if gid is None:
                con.execute("DELETE FROM access_group_members WHERE user_id=?", (uid,))
            else:
                con.execute("""INSERT INTO access_group_members(user_id,group_id,created_by) VALUES(?,?,?)
                             ON CONFLICT(user_id) DO UPDATE SET group_id=excluded.group_id,created_at=CURRENT_TIMESTAMP,created_by=excluded.created_by""",
                            (uid, gid, actor["username"]))
            con.execute("DELETE FROM sessions WHERE user_id=? AND user_id<>?", (uid, actor["id"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor["username"], "ACCESS_MEMBER_SET", f"{target['username']} -> groupe {gid or 'aucun'}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_access_group_permissions(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try: gid = int(data.get("group_id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        incoming = data.get("permissions") or {}
        if not isinstance(incoming, dict):
            return self.send_json({"error": "Permissions invalides"}, 400)
        with db_connect() as con:
            group = con.execute("SELECT name FROM access_groups WHERE id=?", (gid,)).fetchone()
            if not group:
                return self.send_json({"error": "Groupe introuvable"}, 404)
            normalized = {}
            for module in ACCESS_MODULES:
                try: level = int(incoming.get(module, 0))
                except Exception: level = 0
                level = max(0, min(2, level))
                if not ACCESS_MODULES[module].get("write") and level > ACCESS_READ:
                    level = ACCESS_READ
                normalized[module] = level
                con.execute("""INSERT INTO access_group_permissions(group_id,module,access_level,updated_by)
                             VALUES(?,?,?,?) ON CONFLICT(group_id,module) DO UPDATE SET
                             access_level=excluded.access_level,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                            (gid, module, level, actor["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor["username"], "ACCESS_PERMISSIONS_SET", f"{group['name']}: {json.dumps(normalized, ensure_ascii=False)}", self.client_ip()))
            # Les droits sont relus à chaque requête, mais on invalide les sessions du groupe
            # pour forcer les clients à rafraîchir aussi leur navigation immédiatement.
            con.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM access_group_members WHERE group_id=?) AND user_id<>?", (gid, actor["id"]))
            con.commit()
        self.send_json({"ok": True, "permissions": normalized})

    def _sync_module_permissions_from_interfaces(self, con, gid, actor_name):
        levels = {key: 0 for key in ACCESS_MODULES}
        # ANI remains an explicit sensitive-data capability, not an interface.
        row = con.execute("SELECT access_level FROM access_group_permissions WHERE group_id=? AND module='ani'", (gid,)).fetchone()
        if row:
            levels['ani'] = max(0, min(2, int(row[0] or 0)))
        for r in con.execute("SELECT interface_key,access_level FROM access_group_interface_permissions WHERE group_id=?", (gid,)):
            meta = ACCESS_INTERFACES.get(str(r['interface_key']))
            if not meta:
                continue
            module = str(meta.get('module') or '')
            if module in levels:
                levels[module] = max(levels[module], max(0, min(2, int(r['access_level'] or 0))))
        for module, level in levels.items():
            if module == 'ani':
                continue
            if not ACCESS_MODULES[module].get('write') and level > ACCESS_READ:
                level = ACCESS_READ
            con.execute("""INSERT INTO access_group_permissions(group_id,module,access_level,updated_by)
                         VALUES(?,?,?,?) ON CONFLICT(group_id,module) DO UPDATE SET
                         access_level=excluded.access_level,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                        (gid, module, level, actor_name))

    def api_access_group_interface_permissions(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try:
            gid = int(data.get("group_id"))
        except Exception:
            return self.send_json({"error": "Groupe invalide"}, 400)
        incoming = data.get("interfaces") or {}
        if not isinstance(incoming, dict):
            return self.send_json({"error": "Permissions d'interface invalides"}, 400)
        with db_connect() as con:
            group = con.execute("SELECT name FROM access_groups WHERE id=?", (gid,)).fetchone()
            if not group:
                return self.send_json({"error": "Groupe introuvable"}, 404)
            normalized = {}
            for key, meta in ACCESS_INTERFACES.items():
                try:
                    level = int(incoming.get(key, 0))
                except Exception:
                    level = 0
                level = max(0, min(2, level))
                if meta.get('write_only'):
                    level = ACCESS_WRITE if level >= ACCESS_WRITE else 0
                elif not meta.get('write') and level > ACCESS_READ:
                    level = ACCESS_READ
                normalized[key] = level
                con.execute("""INSERT INTO access_group_interface_permissions(group_id,interface_key,access_level,updated_by)
                             VALUES(?,?,?,?) ON CONFLICT(group_id,interface_key) DO UPDATE SET
                             access_level=excluded.access_level,updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                            (gid, key, level, actor['username']))
            self._sync_module_permissions_from_interfaces(con, gid, actor['username'])
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor['username'], 'ACCESS_INTERFACES_SET', f"{group['name']}: {json.dumps(normalized, ensure_ascii=False)}", self.client_ip()))
            con.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM access_group_members WHERE group_id=?) AND user_id<>?", (gid, actor['id']))
            con.commit()
        self.send_json({"ok": True, "interfaces": normalized})

    def api_access_group_scope(self, actor):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        try:
            gid = int(data.get('group_id'))
        except Exception:
            return self.send_json({"error": "Groupe d'accès invalide"}, 400)
        mode = str(data.get('scope_mode') or 'ALL').upper()
        if mode not in {'ALL', 'SELECTED'}:
            return self.send_json({"error": "Mode de périmètre invalide"}, 400)
        raw_ids = data.get('allowed_group_ids') or []
        if not isinstance(raw_ids, list):
            return self.send_json({"error": "Liste des groupes métier invalide"}, 400)
        try:
            allowed = sorted({int(x) for x in raw_ids if str(x).strip()})
        except Exception:
            return self.send_json({"error": "Identifiant de groupe métier invalide"}, 400)
        try:
            default_gid = int(data.get('default_group_id')) if str(data.get('default_group_id') or '').strip() else None
        except Exception:
            return self.send_json({"error": "Groupe par défaut invalide"}, 400)
        locked = 1 if bool(data.get('filter_locked')) else 0
        with db_connect() as con:
            group = con.execute("SELECT name FROM access_groups WHERE id=?", (gid,)).fetchone()
            if not group:
                return self.send_json({"error": "Groupe d'accès introuvable"}, 404)
            existing = {int(r[0]) for r in con.execute("SELECT id FROM user_groups").fetchall()}
            if any(x not in existing for x in allowed) or (default_gid is not None and default_gid not in existing):
                return self.send_json({"error": "Un groupe métier sélectionné n'existe plus"}, 409)
            if mode == 'SELECTED' and not allowed:
                return self.send_json({"error": "Sélectionnez au moins un groupe métier pour un périmètre limité"}, 400)
            if mode == 'SELECTED' and default_gid is not None and default_gid not in set(allowed):
                return self.send_json({"error": "Le groupe par défaut doit faire partie des groupes autorisés"}, 400)
            if locked and default_gid is None:
                return self.send_json({"error": "Un filtre verrouillé nécessite un groupe par défaut"}, 400)
            con.execute("DELETE FROM access_group_scopes WHERE access_group_id=?", (gid,))
            for business_gid in allowed:
                con.execute("INSERT INTO access_group_scopes(access_group_id,business_group_id,created_by) VALUES(?,?,?)",
                            (gid, business_gid, actor['username']))
            con.execute("""INSERT INTO access_group_scope_policy(group_id,scope_mode,default_business_group_id,filter_locked,updated_by)
                         VALUES(?,?,?,?,?) ON CONFLICT(group_id) DO UPDATE SET scope_mode=excluded.scope_mode,
                         default_business_group_id=excluded.default_business_group_id,filter_locked=excluded.filter_locked,
                         updated_at=CURRENT_TIMESTAMP,updated_by=excluded.updated_by""",
                        (gid, mode, default_gid, locked, actor['username']))
            detail = {'mode': mode, 'allowed': allowed, 'default': default_gid, 'locked': bool(locked)}
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (actor['username'], 'ACCESS_SCOPE_SET', f"{group['name']}: {json.dumps(detail, ensure_ascii=False)}", self.client_ip()))
            con.execute("DELETE FROM sessions WHERE user_id IN (SELECT user_id FROM access_group_members WHERE group_id=?) AND user_id<>?", (gid, actor['id']))
            con.commit()
        self.send_json({"ok": True, **detail})

    def api_group_create(self, user):
        from access_control import effective_group_ids
        if effective_group_ids(user) is not None:
            return self.send_json({"error":"La création de groupes métier nécessite un périmètre global."},403)
        data = self.read_json() or {}
        name = str(data.get("name", "") or "").strip()
        description = str(data.get("description", "") or "").strip()[:300]
        if not name or len(name) > 60:
            return self.send_json({"error": "Nom de groupe requis (60 caractères maximum)"}, 400)
        try:
            with db_connect() as con:
                con.execute("INSERT INTO user_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)", (name, description, user["username"], user["username"]))
                gid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)", (user["username"], "GROUP_CREATED", name, self.client_ip()))
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Ce groupe existe déjà"}, 409)
        self.send_json({"ok": True, "id": gid}, 201)

    def api_group_delete(self, user):
        from access_control import effective_group_ids
        if effective_group_ids(user) is not None:
            return self.send_json({"error":"La suppression de groupes métier nécessite un périmètre global."},403)
        data = self.read_json() or {}
        try: gid = int(data.get("id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT name FROM user_groups WHERE id=?", (gid,)).fetchone()
            if not row: return self.send_json({"error": "Groupe introuvable"}, 404)
            con.execute("DELETE FROM user_groups WHERE id=?", (gid,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)", (user["username"], "GROUP_DELETED", row["name"], self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_group_member(self, user):
        data = self.read_json() or {}
        identifier = str(data.get("user_identifier", "") or "").strip()
        key = normalize_user_key(identifier)
        try: gid = int(data.get("group_id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        from access_control import allowed_group
        if not allowed_group(user,gid):return self.send_json({"error":"Groupe métier hors de votre périmètre autorisé."},403)
        if not key or len(key) > 100:
            return self.send_json({"error": "Identifiant utilisateur invalide"}, 400)
        with db_connect() as con:
            group = con.execute("SELECT name FROM user_groups WHERE id=?", (gid,)).fetchone()
            if not group: return self.send_json({"error": "Groupe introuvable"}, 404)
            old = con.execute("SELECT g.name FROM user_group_members m JOIN user_groups g ON g.id=m.group_id WHERE m.user_key=?", (key,)).fetchone()
            con.execute("""INSERT INTO user_group_members(user_key,user_identifier,group_id,created_by) VALUES(?,?,?,?)
                         ON CONFLICT(user_key) DO UPDATE SET user_identifier=excluded.user_identifier,group_id=excluded.group_id,created_at=CURRENT_TIMESTAMP,created_by=excluded.created_by""",
                        (key, identifier, gid, user["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "GROUP_MEMBER_SET", f"{key}: {old['name'] if old else '—'} -> {group['name']}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "user_key": key, "group": group["name"]})

    def api_group_member_delete(self, user):
        data = self.read_json() or {}
        key = normalize_user_key(data.get("user_key", ""))
        if not key: return self.send_json({"error": "Utilisateur invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT user_identifier,group_id FROM user_group_members WHERE user_key=?", (key,)).fetchone()
            if not row: return self.send_json({"error": "Affectation de groupe introuvable"}, 404)
            from access_control import allowed_group
            if not allowed_group(user,row["group_id"]):return self.send_json({"error":"Affectation hors de votre périmètre métier autorisé."},403)
            con.execute("DELETE FROM user_group_members WHERE user_key=?", (key,))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)", (user["username"], "GROUP_MEMBER_DELETED", key, self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_group_campaign(self, user):
        data = self.read_json() or {}
        campaign_name = " ".join(str(data.get("campaign_name", "") or "").split()).strip()[:160]
        try: gid = int(data.get("group_id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        from access_control import allowed_group
        if not allowed_group(user,gid):return self.send_json({"error":"Groupe métier hors de votre périmètre autorisé."},403)
        if not campaign_name:
            return self.send_json({"error": "Campagne requise"}, 400)
        with db_connect() as con:
            group = con.execute("SELECT name FROM user_groups WHERE id=?", (gid,)).fetchone()
            if not group: return self.send_json({"error": "Groupe introuvable"}, 404)
            con.execute("""INSERT INTO quality_group_campaigns(group_id,campaign_name,created_by) VALUES(?,?,?)
                         ON CONFLICT(group_id,campaign_name) DO UPDATE SET created_at=CURRENT_TIMESTAMP,created_by=excluded.created_by""",
                        (gid, campaign_name, user["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "QUALITY_GROUP_CAMPAIGN_SET", f"{group['name']} -> {campaign_name}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "group": group["name"], "campaign_name": campaign_name})

    def api_group_campaign_delete(self, user):
        data = self.read_json() or {}
        campaign_name = " ".join(str(data.get("campaign_name", "") or "").split()).strip()
        try: gid = int(data.get("group_id"))
        except Exception: return self.send_json({"error": "Groupe invalide"}, 400)
        from access_control import allowed_group
        if not allowed_group(user,gid):return self.send_json({"error":"Groupe métier hors de votre périmètre autorisé."},403)
        if not campaign_name:
            return self.send_json({"error": "Campagne invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT 1 FROM quality_group_campaigns WHERE group_id=? AND campaign_name=? COLLATE NOCASE", (gid, campaign_name)).fetchone()
            if not row: return self.send_json({"error": "Affectation campagne introuvable"}, 404)
            con.execute("DELETE FROM quality_group_campaigns WHERE group_id=? AND campaign_name=? COLLATE NOCASE", (gid, campaign_name))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "QUALITY_GROUP_CAMPAIGN_DELETED", f"{gid}: {campaign_name}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

