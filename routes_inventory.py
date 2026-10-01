import csv
import io

import app_config as cfg
from app_db import db_connect, now_text
from classification import parse_ip_selector
from inventory_service import clean_pc_name, current_sql, rows_to_dict, site_case, followup_config, dashboard_transitions_sql, pc_users_sql
from analysis_groups import selected_group_members
from agent_directory import canonical_admin_key

ADMIN_STATUS = cfg.ADMIN_STATUS
EDIT_FIELDS = cfg.EDIT_FIELDS

class InventoryRoutesMixin:
    def api_dashboard(self):
        with db_connect() as con:
            rows = rows_to_dict(con.execute(current_sql()).fetchall())
            transitions = rows_to_dict(con.execute(dashboard_transitions_sql(10)).fetchall())
            # PERF1: current_sql() is the expensive latest-PC projection. It was
            # executed twice for every dashboard load. Reuse the first result.
            recent = sorted(rows, key=lambda r: str(r.get("date_evenement") or ""), reverse=True)[:8]
            last_log = con.execute("SELECT * FROM import_log ORDER BY id DESC LIMIT 1").fetchone()
            fcfg = followup_config(con)
        counts = {k: sum(1 for r in rows if r["suivi_statut"] == k) for k in ("EN_SERVICE", "PAS_A_JOUR", "RETARD_7J", "CRITIQUE", "STOCK", "REPARATION", "KO", "REFORME")}
        self.send_json({
            "total": len(rows),
            "en_service": counts["EN_SERVICE"], "pas_a_jour": counts["PAS_A_JOUR"],
            "retard_7j": counts["RETARD_7J"], "critique": counts["CRITIQUE"],
            "stock": counts["STOCK"], "reparation": counts["REPARATION"], "ko": counts["KO"], "reforme": counts["REFORME"],
            "site": sum(1 for r in rows if r["site_actuel"] == "SUR SITE"),
            "remote": sum(1 for r in rows if r["site_actuel"] == "TELETRAVAIL"),
            "unknown": sum(1 for r in rows if r["site_actuel"] == "INCONNU"),
            "ecarts": sum(1 for r in rows if r["emplacement_ecart"]),
            "manual_only": sum(1 for r in rows if r["created_manually"] and not r["has_diagnostic"]),
            "recent": recent, "transitions": transitions,
            "last_import": dict(last_log) if last_log else None, "followup_config": fcfg,
            "followup_counts": {item["id"]: sum(r["suivi_statut"] == item["id"] for r in rows) for item in fcfg["policy"]["categories"]}
        })

    def api_inventory(self, qs):
        q = str(qs.get("q", [""])[0]).strip()
        freshness = str(qs.get("freshness", [""])[0]).strip()
        site = str(qs.get("site", [""])[0]).strip()
        status = str(qs.get("status", [""])[0]).strip()
        group_id = str(qs.get("group", [""])[0]).strip()
        ip_filter = str(qs.get("ip", [""])[0]).strip()
        gateway_filter = str(qs.get("gateway", [""])[0]).strip()
        clauses = []
        params = []
        if q:
            like = f"%{q}%"
            clauses.append("(ordinateur LIKE ? OR utilisateur LIKE ? OR utilisateur_affiche LIKE ? OR adresse_ip LIKE ? OR passerelle LIKE ? OR adresse_mac LIKE ? OR sn_pc LIKE ? OR fabricant LIKE ? OR modele LIKE ? OR affectation LIKE ? OR notes LIKE ? OR asset_tag LIKE ? OR groupe_utilisateur LIKE ?)")
            params += [like] * 13
        if freshness:
            # Bound parameter: unknown values return no rows, not the unfiltered park.
            clauses.append("suivi_statut=?")
            params.append(freshness)
        if site in {"SUR SITE", "TELETRAVAIL", "INCONNU"}:
            clauses.append("site_actuel=?")
            params.append(site)
        if status in ADMIN_STATUS:
            clauses.append("statut=?")
            params.append(status)
        # Analytical group filters are file-based everywhere in Nelyio.
        # Do not use the legacy single administrative groupe_id stored on the PC.
        group_members = selected_group_members([group_id]) if group_id else None
        if ip_filter:
            try:
                parse_ip_selector(ip_filter)
                clauses.append("ip_match(adresse_ip, ?)=1")
                params.append(ip_filter)
            except Exception:
                clauses.append("adresse_ip LIKE ?")
                params.append(f"%{ip_filter}%")
        if gateway_filter:
            try:
                parse_ip_selector(gateway_filter)
                clauses.append("ip_match(passerelle, ?)=1")
                params.append(gateway_filter)
            except Exception:
                clauses.append("passerelle LIKE ?")
                params.append(f"%{gateway_filter}%")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with db_connect() as con:
            rows = rows_to_dict(con.execute(current_sql(where), params).fetchall())
            if group_id:
                allowed = {canonical_admin_key(x) for x in (group_members or set()) if canonical_admin_key(x)}
                rows = [r for r in rows if canonical_admin_key(r.get("utilisateur")) in allowed]
            groups = rows_to_dict(con.execute("SELECT id,name FROM user_groups ORDER BY name COLLATE NOCASE").fetchall())
            fcfg = followup_config(con)
        self.send_json({"rows": rows, "count": len(rows), "groups": groups, "followup_config": fcfg})

    def api_pc(self, qs):
        name = clean_pc_name(qs.get("name", [""])[0])
        if not name:
            return self.send_json({"error": "PC invalide"}, 400)
        with db_connect() as con:
            cur = con.execute(current_sql("WHERE ordinateur=?"), (name,)).fetchone()
            if not cur:
                return self.send_json({"error": "PC introuvable"}, 404)
            hist_site = site_case("d.collecteur", "d.adresse_ip", "d.passerelle")
            hist = rows_to_dict(con.execute(f"""
                SELECT d.*,{hist_site} AS site,classify_reason(d.collecteur,d.adresse_ip,d.passerelle) AS site_reason,
                       COALESCE(g.name,'') AS groupe_utilisateur,
                       COALESCE(NULLIF(TRIM(COALESCE(ud.first_name,'') || ' ' || COALESCE(ud.last_name,'')),''),d.utilisateur,'') AS utilisateur_affiche
                FROM diagnostic d
                LEFT JOIN user_group_members gm ON gm.user_key=user_key(d.utilisateur)
                LEFT JOIN user_groups g ON g.id=gm.group_id
                LEFT JOIN user_directory ud ON ud.user_key=user_key(d.utilisateur)
                WHERE d.ordinateur=? ORDER BY datetime(d.date_evenement) DESC,d.id DESC
            """, (name,)).fetchall())
            users = rows_to_dict(con.execute(pc_users_sql(), (name,)).fetchall())
            audit = rows_to_dict(con.execute("SELECT * FROM manual_audit WHERE ordinateur=? ORDER BY id DESC LIMIT 100", (name,)).fetchall())
            fcfg = followup_config(con)
        self.send_json({"pc": dict(cur), "history": hist, "users": users, "audit": audit, "followup_config": fcfg})

    def normalize_management(self, data):
        out = {f: str(data.get(f, "") or "").strip() for f in EDIT_FIELDS}
        if out["statut"] not in ADMIN_STATUS:
            out["statut"] = "EN_SERVICE"
        if out["emplacement_attendu"] not in {"", "SUR SITE", "TELETRAVAIL"}:
            out["emplacement_attendu"] = ""
        return out

    def log_changes(self, con, name, old, new, user, action):
        changes = 0
        for f in EDIT_FIELDS:
            ov = str(old.get(f, "") if old else "")
            nv = str(new.get(f, "") if new else "")
            if ov != nv:
                con.execute("INSERT INTO manual_audit(ordinateur,action,field_name,old_value,new_value,username,user_id,source_ip) VALUES(?,?,?,?,?,?,?,?)",
                            (name, action, f, ov, nv, user["username"], user["id"], self.client_ip()))
                changes += 1
        return changes

    def api_manage(self, user):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        name = clean_pc_name(data.get("ordinateur"))
        if not name:
            return self.send_json({"error": "Nom du PC invalide"}, 400)
        new = self.normalize_management(data)
        with db_connect() as con:
            exists = con.execute("SELECT 1 FROM diagnostic WHERE ordinateur=? LIMIT 1", (name,)).fetchone()
            oldrow = con.execute("SELECT * FROM asset_management WHERE ordinateur=?", (name,)).fetchone()
            old = dict(oldrow) if oldrow else {f: "" for f in EDIT_FIELDS}
            created_manually = int(old.get("created_manually", 0)) if oldrow else (0 if exists else 1)
            created_by = old.get("created_by") if oldrow else user["username"]
            con.execute("""
                INSERT INTO asset_management(
                    ordinateur,asset_tag,statut,affectation,emplacement_attendu,notes,
                    manual_utilisateur,manual_ip,manual_mac,manual_sn_pc,manual_sn_carte_mere,manual_domaine,
                    manual_fabricant,manual_modele,manual_windows,manual_version_windows,
                    created_manually,created_by,updated_by,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(ordinateur) DO UPDATE SET
                    asset_tag=excluded.asset_tag,statut=excluded.statut,affectation=excluded.affectation,
                    emplacement_attendu=excluded.emplacement_attendu,notes=excluded.notes,
                    manual_utilisateur=excluded.manual_utilisateur,manual_ip=excluded.manual_ip,manual_mac=excluded.manual_mac,
                    manual_sn_pc=excluded.manual_sn_pc,manual_sn_carte_mere=excluded.manual_sn_carte_mere,manual_domaine=excluded.manual_domaine,
                    manual_fabricant=excluded.manual_fabricant,manual_modele=excluded.manual_modele,manual_windows=excluded.manual_windows,
                    manual_version_windows=excluded.manual_version_windows,updated_by=excluded.updated_by,updated_at=excluded.updated_at
            """, (name, new["asset_tag"], new["statut"], new["affectation"], new["emplacement_attendu"], new["notes"],
                  new["manual_utilisateur"], new["manual_ip"], new["manual_mac"], new["manual_sn_pc"], new["manual_sn_carte_mere"], new["manual_domaine"],
                  new["manual_fabricant"], new["manual_modele"], new["manual_windows"], new["manual_version_windows"],
                  created_manually, created_by, user["username"], now_text()))
            changes = self.log_changes(con, name, old, new, user, "UPDATE_PC")
            if changes == 0:
                con.execute("INSERT INTO manual_audit(ordinateur,action,field_name,old_value,new_value,username,user_id,source_ip) VALUES(?,?,?,?,?,?,?,?)",
                            (name, "UPDATE_PC", "_no_change", "", "", user["username"], user["id"], self.client_ip()))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "PC_UPDATED", f"{name}; {changes} champ(s) modifié(s)", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "changes": changes, "updated_by": user["username"]})

    def api_add_pc(self, user):
        data = self.read_json()
        if data is None:
            return self.send_json({"error": "JSON invalide"}, 400)
        name = clean_pc_name(data.get("ordinateur"))
        if not name:
            return self.send_json({"error": "Nom PC requis (lettres, chiffres, . _ -)"}, 400)
        with db_connect() as con:
            if con.execute("SELECT 1 FROM diagnostic WHERE ordinateur=? LIMIT 1", (name,)).fetchone():
                return self.send_json({"error": "Ce PC existe déjà dans les diagnostics. Ouvrez sa fiche pour le modifier."}, 409)
            if con.execute("SELECT 1 FROM asset_management WHERE ordinateur=?", (name,)).fetchone():
                return self.send_json({"error": "Ce PC existe déjà dans le parc manuel."}, 409)
            new = self.normalize_management(data)
            con.execute("""
                INSERT INTO asset_management(
                    ordinateur,asset_tag,statut,affectation,emplacement_attendu,notes,
                    manual_utilisateur,manual_ip,manual_mac,manual_sn_pc,manual_sn_carte_mere,manual_domaine,
                    manual_fabricant,manual_modele,manual_windows,manual_version_windows,
                    created_manually,created_by,updated_by,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)
            """, (name, new["asset_tag"], new["statut"], new["affectation"], new["emplacement_attendu"], new["notes"],
                  new["manual_utilisateur"], new["manual_ip"], new["manual_mac"], new["manual_sn_pc"], new["manual_sn_carte_mere"], new["manual_domaine"],
                  new["manual_fabricant"], new["manual_modele"], new["manual_windows"], new["manual_version_windows"],
                  user["username"], user["username"], now_text(), now_text()))
            con.execute("INSERT INTO manual_audit(ordinateur,action,field_name,old_value,new_value,username,user_id,source_ip) VALUES(?,?,?,?,?,?,?,?)",
                        (name, "CREATE_PC", "ordinateur", "", name, user["username"], user["id"], self.client_ip()))
            for f in EDIT_FIELDS:
                if new[f]:
                    con.execute("INSERT INTO manual_audit(ordinateur,action,field_name,old_value,new_value,username,user_id,source_ip) VALUES(?,?,?,?,?,?,?,?)",
                                (name, "CREATE_PC", f, "", new[f], user["username"], user["id"], self.client_ip()))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "PC_CREATED", name, self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "ordinateur": name}, 201)

    def api_export(self):
        with db_connect() as con:
            rows = rows_to_dict(con.execute(current_sql()).fetchall())
            fcfg = followup_config(con)
        s = io.StringIO()
        w = csv.writer(s, delimiter=';')
        w.writerow(['PC','Statut suivi','Jours depuis vue','Site actuel','Raison emplacement','Collecteur','Utilisateur affiché','Identifiant utilisateur','Groupe','IP','Passerelle','MAC','SN PC','Fabricant','Modele','Windows','Derniere vue','Etat administratif','Affectation','Note','Asset Tag','Emplacement attendu','Ajoute manuellement','Derniere modif par','Libelle du suivi'])
        for r in rows:
            w.writerow([r['ordinateur'],r['suivi_statut'],r['jours_depuis_vue'],r['site_actuel'],r['site_reason'],r['collecteur'],r['utilisateur_affiche'],r['utilisateur'],r['groupe_utilisateur'],r['adresse_ip'],r['passerelle'],r['adresse_mac'],r['sn_pc'],r['fabricant'],r['modele'],r['windows'],r['date_evenement'],r['statut'],r['affectation'],r['notes'],r['asset_tag'],r['emplacement_attendu'],r['created_manually'],r['updated_by'],fcfg['labels'].get(r['suivi_statut'],r['suivi_statut'])])
        self.send_bytes(s.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', extra={'Content-Disposition': 'attachment; filename=TECH-IN_stock_pc.csv'})
