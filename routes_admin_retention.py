"""Routes Administration : retention ; corps V56.8 deplaces sans changement."""
from datetime import datetime, timedelta

from pathlib import Path

import retention_service

from app_db import db_connect, get_setting, now_text, set_setting

from error_log import log_unexpected_error

from inventory_service import rows_to_dict, followup_config, DEFAULT_FOLLOWUP_LABELS



class AdminRetentionRoutesMixin:
    def api_retention_status(self):
        warnings = []
        try:
            plan = retention_service.retention_plan()
            if isinstance(plan, dict) and plan.get("error"):
                warnings.append("retention_plan")
        except Exception as exc:
            log_unexpected_error('app.api_retention_status.plan')
            plan = {"error": type(exc).__name__, "items": [], "holds": []}
            warnings.append("retention_plan")
        with db_connect() as con:
            try:
                settings = {r["key"]: r["value"] for r in con.execute(
                    "SELECT key,value FROM settings WHERE key LIKE 'retention_%' ORDER BY key"
                ).fetchall()}
            except Exception:
                log_unexpected_error('app.api_retention_status.settings')
                settings = {}
                warnings.append("settings")
            try:
                holds = rows_to_dict(con.execute(
                    "SELECT id,start_day,end_day,reason,active,reevaluate_at,created_at,created_by,updated_at,updated_by "
                    "FROM retention_legal_holds ORDER BY active DESC,start_day DESC,id DESC"
                ).fetchall())
            except Exception:
                log_unexpected_error('app.api_retention_status.holds')
                holds = []
                warnings.append("holds")
            try:
                runs = rows_to_dict(con.execute(
                    "SELECT id,mode,status,started_at,finished_at,actor,error FROM retention_runs ORDER BY id DESC LIMIT 20"
                ).fetchall())
            except Exception:
                log_unexpected_error('app.api_retention_status.runs')
                runs = []
                warnings.append("runs")
        self.send_json({"settings": settings, "plan": plan, "holds": holds, "runs": runs,
                        "policy_version": retention_service.POLICY_VERSION, "warnings": warnings})

    def api_retention_config(self, user):
        data = self.read_json() or {}
        try:
            op = int(data.get("operational_months", 6))
            details = int(data.get("details_months", 12))
            archive = int(data.get("archive_months", 24))
            aggregate = int(data.get("aggregate_months", 36))
            security = int(data.get("security_months", 12))
            health = int(data.get("health_days", 30))
        except (TypeError, ValueError):
            return self.send_json({"error": "Durées de rétention invalides"}, 400)
        if not (1 <= op <= details <= archive <= aggregate <= 240):
            return self.send_json({"error": "Ordre requis : actif ≤ Détails ≤ archive ≤ agrégats (1 à 240 mois)"}, 400)
        if not 1 <= security <= 120 or not 1 <= health <= 3650:
            return self.send_json({"error": "Durée sécurité ou health_points invalide"}, 400)
        enabled = "1" if str(data.get("enabled", "0")).lower() in {"1","true","on","yes"} else "0"
        archive_dir = str(data.get("archive_dir", "") or "").strip().strip('"')
        backup_dir = str(data.get("backup_dir", "") or "").strip().strip('"')
        if not archive_dir or not backup_dir:
            return self.send_json({"error": "Les dossiers d'archive et de sauvegarde sont obligatoires"}, 400)
        try:
            a_path = Path(archive_dir).expanduser().resolve(strict=False)
            b_path = Path(backup_dir).expanduser().resolve(strict=False)
            if a_path == b_path or a_path in b_path.parents or b_path in a_path.parents:
                return self.send_json({"error": "Archives et sauvegardes doivent utiliser deux dossiers séparés et non imbriqués"}, 400)
        except Exception:
            return self.send_json({"error": "Chemin d'archive ou de sauvegarde invalide"}, 400)
        values = {
            "retention_enabled": enabled,
            "retention_archive_dir": archive_dir,
            "retention_backup_dir": backup_dir,
            "retention_operational_months": str(op),
            "retention_details_months": str(details),
            "retention_archive_months": str(archive),
            "retention_aggregate_months": str(aggregate),
            "retention_security_months": str(security),
            "retention_health_days": str(health),
        }
        with db_connect() as con:
            for key, value in values.items():
                set_setting(con, key, value, user["username"])
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "RETENTION_POLICY_UPDATED",
                         f"enabled={enabled}; active={op}m; details={details}m; archive={archive}m; aggregates={aggregate}m; security={security}m; health={health}d",
                         self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "enabled": enabled == "1"})

    def api_retention_hold(self, user):
        data = self.read_json() or {}
        start_day = str(data.get("start_day", "")).strip()
        end_day = str(data.get("end_day", "")).strip()
        reason = " ".join(str(data.get("reason", "") or "").split()).strip()[:500]
        reevaluate = str(data.get("reevaluate_at", "") or "").strip() or None
        try:
            start_dt = datetime.strptime(start_day, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_day, "%Y-%m-%d").date()
            if end_dt < start_dt: raise ValueError()
            if reevaluate: datetime.strptime(reevaluate, "%Y-%m-%d")
        except ValueError:
            return self.send_json({"error": "Dates du gel invalides"}, 400)
        if not reason:
            return self.send_json({"error": "Le motif du gel est obligatoire"}, 400)
        with db_connect() as con:
            cur = con.execute("""INSERT INTO retention_legal_holds(start_day,end_day,reason,active,reevaluate_at,created_by,updated_by)
                                 VALUES(?,?,?,1,?,?,?)""",
                              (start_day,end_day,reason,reevaluate,user["username"],user["username"]))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "RETENTION_HOLD_CREATED", f"{cur.lastrowid}: {start_day}..{end_day}: {reason}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "id": cur.lastrowid})

    def api_retention_hold_toggle(self, user):
        data = self.read_json() or {}
        try: hold_id = int(data.get("id"))
        except (TypeError, ValueError): return self.send_json({"error": "Gel invalide"}, 400)
        active = 1 if str(data.get("active", "1")).lower() in {"1","true","on","yes"} else 0
        with db_connect() as con:
            row = con.execute("SELECT id FROM retention_legal_holds WHERE id=?", (hold_id,)).fetchone()
            if not row: return self.send_json({"error": "Gel introuvable"}, 404)
            con.execute("UPDATE retention_legal_holds SET active=?,updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE id=?",
                        (active,user["username"],hold_id))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "RETENTION_HOLD_TOGGLED", f"{hold_id}: active={active}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True})

    def api_retention_dry_run(self, user):
        try:
            result = retention_service.run_retention(dry_run=True, actor=user["username"])
            self.send_json(result)
        except Exception as exc:
            log_unexpected_error('app.api_retention_dry_run')
            self.send_json({"error": str(exc)}, 400)

    def api_retention_execute(self, user):
        data = self.read_json() or {}
        if str(data.get("confirm", "")).strip().upper() != "PURGER":
            return self.send_json({"error": "Confirmation requise : saisir PURGER"}, 400)
        if str(get_setting("retention_enabled", "0")).lower() not in {"1","true","on","yes"}:
            return self.send_json({"error": "La purge réelle est désactivée dans la politique de rétention"}, 409)
        try:
            result = retention_service.run_retention(dry_run=False, actor=user["username"])
            with db_connect() as con:
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (user["username"], "RETENTION_EXECUTED", f"purged={len(result.get('purged',[]))}; archives={len(result.get('archives',[]))}", self.client_ip()))
                con.commit()
            self.send_json(result)
        except Exception as exc:
            log_unexpected_error('app.api_retention_execute')
            self.send_json({"error": str(exc)}, 400)

