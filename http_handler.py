from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse, unquote
from http.cookies import SimpleCookie
from datetime import datetime, timedelta
import hashlib
import hmac
import ipaddress
import json
import os
import time
import mimetypes

import app_config as cfg
import supervision
from app_db import db_connect, now_text
from auth_service import access_profile, user_has_access, user_has_interface
# Facade compatible : les six domaines Administration sont composes sans changer le dispatch.
from routes_admin import AdminRoutesMixin
from routes_auth import AuthRoutesMixin
from routes_inventory import InventoryRoutesMixin
from routes_consumables import ConsumablesRoutesMixin
from routes_quality import QualityRoutesMixin
from routes_groups import GroupWorkspaceRoutesMixin

BASE = cfg.BASE
STATIC = cfg.STATIC
SESSION_COOKIE = cfg.SESSION_COOKIE
SESSION_IDLE_MINUTES = cfg.SESSION_IDLE_MINUTES
MAX_JSON_BYTES = cfg.MAX_JSON_BYTES
ROLE_LEVEL = cfg.ROLE_LEVEL
ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_INTERFACES = cfg.ACCESS_INTERFACES


from routes_collection import CollectionRoutesMixin


class Handler(CollectionRoutesMixin, GroupWorkspaceRoutesMixin, AuthRoutesMixin, InventoryRoutesMixin, ConsumablesRoutesMixin, QualityRoutesMixin, AdminRoutesMixin, BaseHTTPRequestHandler):
    server_version = "TECHINStock/8.0"
    sys_version = ""

    def version_string(self):
        return self.server_version

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def request_is_https(self):
        if bool(getattr(self.server, "techin_https", False)):
            return True
        # Only trust reverse-proxy protocol headers from a local proxy.
        peer = str(self.client_address[0] if self.client_address else "")
        if peer in {"127.0.0.1", "::1"}:
            return self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower() == "https"
        return False

    def client_ip(self):
        peer = str(self.client_address[0] if self.client_address else "")
        if peer in {"127.0.0.1", "::1"}:
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                try:
                    return str(ipaddress.ip_address(forwarded))
                except ValueError:
                    pass
        return peer[:80]

    def security_headers(self):
        headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin",
        }
        if self.request_is_https():
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return headers

    def send_bytes(self, data, ctype="application/octet-stream", status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in self.security_headers().items():
            self.send_header(k, v)
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200, extra=None):
        started = time.perf_counter()
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            import perf_trace
            perf_trace.add_json(time.perf_counter() - started)
            perf_trace.add_response_bytes(len(payload))
        except Exception:
            pass
        self.send_bytes(payload, "application/json; charset=utf-8", status, extra)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n < 0 or n > MAX_JSON_BYTES:
                raise ValueError("payload too large")
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw)
        except Exception:
            return None

    def cookie_token(self):
        raw = self.headers.get("Cookie", "")
        c = SimpleCookie()
        try:
            c.load(raw)
            return c[SESSION_COOKIE].value if SESSION_COOKIE in c else ""
        except Exception:
            return ""

    def session_user(self):
        auth_started = time.perf_counter()
        try:
            token = self.cookie_token()
            if not token:
                return None
            th = hashlib.sha256(token.encode("utf-8")).hexdigest()
            with db_connect() as con:
                row = con.execute("""
                    SELECT u.id,u.username,u.role,u.active,s.expires_at,s.csrf_token,s.last_seen_at
                    FROM sessions s JOIN users u ON u.id=s.user_id
                    WHERE s.token_hash=?
                """, (th,)).fetchone()
                if not row or not row["active"]:
                    return None
                try:
                    now = datetime.now()
                    expires = datetime.fromisoformat(row["expires_at"])
                    last_seen = datetime.fromisoformat(row["last_seen_at"] or row["expires_at"])
                    if expires <= now or last_seen + timedelta(minutes=SESSION_IDLE_MINUTES) <= now:
                        con.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
                        con.commit()
                        return None
                except Exception:
                    con.execute("DELETE FROM sessions WHERE token_hash=?", (th,))
                    con.commit()
                    return None
                # Avoid a write+commit on every polling/API request. The idle timeout
                # remains unchanged; only persistence of the heartbeat is throttled.
                try:
                    refresh_seconds = max(5, min(300, int(os.environ.get("NELYIO_SESSION_TOUCH_SECONDS", "60"))))
                except (TypeError, ValueError):
                    refresh_seconds = 60
                if (now - last_seen).total_seconds() >= refresh_seconds:
                    con.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (now_text(), th))
                    con.commit()
                out = dict(row)
                if out.get("role") == "user":
                    out["role"] = "technician"
                profile = access_profile(con, out["id"], out["role"])
                out.update(profile)
                return out
        finally:
            try:
                import perf_trace; perf_trace.add_auth(time.perf_counter() - auth_started)
            except Exception:
                pass

    def require_user(self, role=None, min_role=None):
        user = self.session_user()
        if not user:
            self.send_json({"error": "Authentification requise"}, 401)
            return None
        if role and user.get("role") != role:
            self.send_json({"error": "Droits administrateur requis"}, 403)
            return None
        if min_role and ROLE_LEVEL.get(user.get("role"), 0) < ROLE_LEVEL.get(min_role, 999):
            self.send_json({"error": "Droits insuffisants pour cette opération"}, 403)
            return None
        return user

    def require_access(self, user, module, write=False):
        if user_has_access(user, module, write=write):
            return True
        level = "modification" if write else "lecture"
        self.send_json({"error": f"Accès refusé : droit de {level} requis pour {ACCESS_MODULES.get(module, {}).get('label', module)}"}, 403)
        return False

    def require_interface(self, user, interface_key, write=False):
        if user_has_interface(user, interface_key, write=write):
            return True
        level = "modification" if write else "lecture"
        label = ACCESS_INTERFACES.get(interface_key, {}).get("label", interface_key)
        self.send_json({"error": f"Accès refusé : droit de {level} requis pour {label}"}, 403)
        return False

    def validate_csrf(self, user):
        supplied = self.headers.get("X-CSRF-Token", "")
        expected = str(user.get("csrf_token") or "")
        if not supplied or not expected or not hmac.compare_digest(supplied, expected):
            with db_connect() as con:
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (user.get("username"), "CSRF_REJECTED", self.path[:300], self.client_ip()))
                con.commit()
            self.send_json({"error": "Jeton de sécurité invalide. Rechargez la page."}, 403)
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        qs = parse_qs(u.query)
        if path == "/":
            return self.serve_file(BASE / "index.html", "text/html; charset=utf-8")
        if path == "/healthz":
            return self.send_json({"ok": True, "service": "nelyio-backend", "port": int(getattr(self.server, "server_port", 0) or 0)})
        if path == "/favicon.ico":
            # Browsers request this automatically before authentication.
            # No icon is bundled, so answer cleanly instead of returning a 401 JSON error.
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "public, max-age=86400")
            for k, v in self.security_headers().items():
                self.send_header(k, v)
            self.end_headers()
            return
        if path.startswith("/static/"):
            p = (STATIC / path.removeprefix("/static/")).resolve()
            if STATIC.resolve() not in p.parents:
                return self.send_json({"error": "forbidden"}, 403)
            return self.serve_file(p)
        if path == "/api/me":
            user = self.session_user()
            if not user:
                return self.send_json({"authenticated": False}, 401)
            return self.send_json({"authenticated": True, "user": {k:v for k,v in user.items() if k not in {"csrf_token","last_seen_at","expires_at"}}, "csrf_token": user.get("csrf_token", "")})

        user = self.require_user()
        if not user:
            return
        if path == "/api/collection/summary":
            if not any(user_has_access(user, module) for module in ("collection","support","details","calls","quality","analytics")):
                return self.send_json({"error":"Acces collecte refuse"},403)
            from collection_store import brief
            return self.send_json(brief())
        if path == "/api/collection/status":
            if not self.require_interface(user, "collection_admin"): return
            return self.api_collection_status()
        if path == "/api/collection/live":
            if not self.require_interface(user, "collection_admin"): return
            return self.api_collection_live(qs)
        if path == "/api/live/supervision":
            if not self.require_interface(user, "live_supervision"): return
            return self.api_live_supervision(qs, user, show_phone=user_has_access(user, "ani"))
        if path == "/api/live/scope-quality":
            if not self.require_interface(user, "live_supervision"): return
            return self.api_live_scope_quality(qs, user)
        if path == "/api/live/campaigns":
            if not self.require_interface(user, "live_campaigns"): return
            return self.api_live_campaigns(qs, user, include_history=user_has_interface(user, "quality_pilotage") or user_has_interface(user, "analytics_home"))
        if path.startswith("/api/live/campaigns/"):
            if not self.require_interface(user, "live_campaigns"): return
            campaign_id=unquote(path[len("/api/live/campaigns/"):]).strip()
            if not campaign_id:
                return self.send_json({"error":"Campagne Live requise"},400)
            return self.api_live_campaign_detail(campaign_id,qs,include_history=user_has_interface(user,"quality_pilotage") or user_has_interface(user,"analytics_home"),
                                                 include_calls=user_has_interface(user,"live_search") or user_has_interface(user,"calls"),show_phone=user_has_access(user,"ani"),user=user)
        if path == "/api/live/search":
            if not self.require_interface(user, "live_search"): return
            return self.api_live_search(qs, show_phone=user_has_access(user, "ani"), user=user)
        if path == "/api/live/diagnostic":
            if not self.require_interface(user, "collection_admin", write=True): return
            return self.api_live_diagnostic()
        if path == "/api/live/incidents":
            if not self.require_interface(user, "live_incidents"): return
            return self.api_live_incidents(qs, user)
        if path == "/api/live/incident-stats":
            if not self.require_interface(user, "live_incidents"): return
            return self.api_live_incident_stats(qs, user)
        if path.startswith("/api/live/incidents/"):
            if not self.require_interface(user, "live_incidents"): return
            incident_id=unquote(path[len("/api/live/incidents/"):]).strip()
            if not incident_id:
                return self.send_json({"error":"Incident Live requis"},400)
            return self.api_live_incident_detail(incident_id, user)
        if path == "/api/live/quality/config":
            if not self.require_interface(user, "live_quality_admin"): return
            return self.api_live_quality_config()
        if path == "/api/services/status":
            if not self.require_interface(user, "production_health"): return
            import service_state
            service_state.beat('web', detail={'port':int(getattr(self.server,'server_port',0) or 0),'mode':'external-services'})
            return self.send_json(service_state.public_status())
        if path == "/api/production/observability":
            # Backward-compatible coarse capability + RC23 fine interface gate.
            if not self.require_access(user, "config"): return
            if not self.require_interface(user, "production_health"): return
            import production_observability
            return self.send_json(production_observability.snapshot())
        if path.startswith("/api/supervision/"):
            iface_map={
                "/api/supervision/calls":"calls",
                "/api/supervision/analytics":"analytics",
                "/api/supervision/details":"details",
                "/api/supervision/diagnostic-incidents":"disconnect_details",
                "/api/supervision/incident-evidence":"disconnect_details",
                "/api/supervision/report-preview":"reports",
                "/api/supervision/report-details":"reports",
                "/api/supervision/report.pdf":"reports",
                "/api/supervision/config":"support",
                "/api/supervision/support":"support",
                "/api/supervision/view":"support",
            }
            if path == "/api/supervision/auto-import":
                if not (user_has_interface(user,"support") or user_has_interface(user,"calls")):
                    return self.send_json({"error":"Accès Support ou Recherche d’appels requis"},403)
            else:
                iface=iface_map.get(path,"support")
                if not self.require_interface(user,iface,write=(path=="/api/supervision/config")): return
            return supervision.get_route(self,path,qs,user)
        if path == "/api/dashboard":
            if not self.require_interface(user, "dashboard"): return
            return self.api_dashboard()
        if path == "/api/inventory":
            if not self.require_interface(user, "inventory"): return
            return self.api_inventory(qs)
        if path == "/api/consumables":
            if not self.require_interface(user, "consumables"): return
            return self.api_consumables(qs)
        if path == "/api/consumables/export.csv":
            if not self.require_interface(user, "consumables"): return
            return self.api_consumables_export(qs)
        if path == "/api/pc":
            if not self.require_interface(user, "inventory"): return
            return self.api_pc(qs)
        if path == "/api/export.csv":
            if not self.require_interface(user, "inventory"): return
            return self.api_export()
        if path == "/api/users":
            if not self.require_interface(user, "users"): return
            return self.api_users()
        if path == "/api/config":
            if not self.require_interface(user, "config"): return
            return self.api_config()
        if path == "/api/config/export":
            if not self.require_interface(user, "config"): return
            return self.api_config_export(user)
        if path == "/api/retention":
            if not self.require_interface(user, "config"): return
            return self.api_retention_status()
        if path == "/api/groups/status":
            if not any(user_has_interface(user, key) for key in ("dashboard", "classification_groups", "quality_agents", "quality_bases", "analytics_home")):
                return self.send_json({"error": "Acces refuse"}, 403)
            return self.api_group_status(user)
        if path == "/api/groups/workspace":
            if not self.require_interface(user, "classification_groups"): return
            return self.api_group_workspace(user)
        if path == "/api/classification":
            if not self.require_interface(user, "classification"): return
            return self.api_classification(user)
        if path == "/api/support-priority":
            if not self.require_interface(user, "support_priority"): return
            return self.api_support_priority_config(user)
        if path == "/api/policies":
            if not self.require_interface(user, "policies"): return
            return self.api_policies(user)
        if path == "/api/declarations":
            if not self.require_interface(user, "declarations"): return
            return self.api_declarations(user, qs)
        if path == "/api/quality/agent-activity":
            if not self.require_interface(user, "quality_activity"): return
            return self.api_quality_agents(qs, user)
        if path == "/api/quality/distributions":
            if not self.require_interface(user, "quality_distributions"): return
            return self.api_quality_distributions(qs, user)
        if path == "/api/quality/overview":
            if not self.require_interface(user, "quality_overview"): return
            return self.api_quality_overview(qs, user)
        if path == "/api/quality/pilotage":
            if not self.require_interface(user, "quality_pilotage"): return
            return self.api_quality_pilotage(qs, user)
        if path == "/api/quality/actions":
            if not self.require_interface(user, "quality_pilotage"): return
            return self.api_quality_actions(user)
        if path == "/api/quality/action-compare":
            if not self.require_interface(user, "quality_pilotage"): return
            return self.api_quality_action_compare(qs, user)
        if path == "/api/quality/suspicious-calls":
            if not self.require_interface(user, "suspicious_calls"): return
            scoped = dict(qs)
            scoped["_show_ani"] = ["1" if user_has_access(user, "ani") else "0"]
            return self.api_suspicious_calls(scoped, user)
        if path == "/api/quality/priorities":
            if not (user_has_interface(user, "quality_agents") or user_has_interface(user, "quality_bases")):
                return self.send_json({"error": "Accès Priorités Qualité refusé"}, 403)
            return self.api_quality_priorities(user)
        if path == "/api/security-audit":
            if not self.require_interface(user, "security"): return
            return self.api_security_audit()
        if path == "/api/security-import-coverage":
            if not self.require_interface(user, "security"): return
            return self.api_import_coverage(qs)
        return self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/supervision/ingest":
            return supervision.bridge_route(self)
        if path == "/api/login":
            return self.api_login()
        if path == "/api/logout":
            user = self.require_user()
            if not user:
                return
            if not self.validate_csrf(user):
                return
            return self.api_logout()

        user = self.require_user()
        if not user:
            return
        if not self.validate_csrf(user):
            return
        if path.startswith("/api/live/quality/"):
            if not self.require_interface(user, "live_quality_admin", write=True): return
            return self.api_live_quality_action(path.rsplit("/",1)[-1], user)
        if path == "/api/live/incident":
            if not self.require_interface(user, "live_incidents", write=True): return
            return self.api_live_incident_create(user)
        if path.startswith("/api/live/incidents/"):
            if not self.require_interface(user, "live_incidents", write=True): return
            incident_id=unquote(path[len("/api/live/incidents/"):]).strip()
            if not incident_id:
                return self.send_json({"error":"Incident Live requis"},400)
            return self.api_live_incident_action(incident_id,user)
        if path.startswith("/api/collection/"):
            if not self.require_interface(user, "collection_admin", write=True): return
            return self.api_collection_action(path.rsplit("/",1)[-1], user)
        if path == "/api/quality/action/save":
            if not self.require_interface(user, "quality_pilotage", write=True): return
            return self.api_quality_action_save(user)
        if path == "/api/quality/import":
            if not (user_has_interface(user,"classification_groups",write=True) or user_has_interface(user,"quality_pilotage",write=True)):
                return self.send_json({"error":"Droit d’import Qualité refusé"},403)
            return self.api_quality_import(parse_qs(urlparse(self.path).query))
        if path.startswith("/api/supervision/"):
            if path == "/api/supervision/import":
                if not (user_has_interface(user,"support",write=True) or user_has_interface(user,"calls",write=True)):
                    return self.send_json({"error":"Droit de modification Support ou Recherche d’appels requis"},403)
            elif path == "/api/supervision/note":
                # supervision_routes validates the exact target (Support or Appels).
                if not (user_has_interface(user,"support",write=True) or user_has_interface(user,"calls",write=True)):
                    return self.send_json({"error":"Droit de modification requis"},403)
            elif not self.require_interface(user,"support",write=True):
                return
            return supervision.post_route(self,path,parse_qs(urlparse(self.path).query),user)
        if path == "/api/manage":
            if not self.require_interface(user, "inventory", write=True): return
            return self.api_manage(user)
        if path == "/api/pc/add":
            if not self.require_interface(user, "inventory_add", write=True): return
            return self.api_add_pc(user)
        if path == "/api/consumables/item":
            if not self.require_interface(user, "consumables", write=True): return
            return self.api_consumable_item(user)
        if path == "/api/consumables/item/toggle":
            if not self.require_interface(user, "consumables", write=True): return
            return self.api_consumable_toggle(user)
        if path == "/api/consumables/movement":
            if not self.require_interface(user, "consumables", write=True): return
            return self.api_consumable_movement(user)
        if path == "/api/change-password":
            return self.api_change_password(user)
        if path == "/api/users":
            if not self.require_interface(user, "users", write=True): return
            return self.api_create_user(user)
        if path == "/api/users/toggle":
            if not self.require_interface(user, "users", write=True): return
            return self.api_toggle_user(user)
        if path == "/api/access-groups/save":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_save(user)
        if path == "/api/access-groups/delete":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_delete(user)
        if path == "/api/access-groups/member":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_member(user)
        if path == "/api/access-groups/permissions":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_permissions(user)
        if path == "/api/access-groups/interface-permissions":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_interface_permissions(user)
        if path == "/api/access-groups/scope":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_scope(user)
        if path == "/api/access-groups/clone":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_clone(user)
        if path == "/api/access-profiles/save":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_profile_save(user)
        if path == "/api/access-profiles/delete":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_profile_delete(user)
        if path == "/api/access-profiles/apply":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_profile_apply(user)
        if path == "/api/access-profiles/create-group":
            if not self.require_interface(user, "users", write=True): return
            return self.api_access_group_from_profile(user)
        if path == "/api/config":
            if not self.require_interface(user, "config", write=True): return
            return self.api_save_config(user)
        if path == "/api/config/test-source":
            if not self.require_interface(user, "config", write=True): return
            return self.api_test_source()
        if path == "/api/config/import":
            if not self.require_interface(user, "config", write=True): return
            return self.api_import(user)
        if path == "/api/config/import-settings":
            if not self.require_interface(user, "config", write=True): return
            return self.api_config_import(user)
        if path.startswith("/api/retention/"):
            if not self.require_interface(user, "config", write=True): return
            routes = {
                "/api/retention/config": self.api_retention_config,
                "/api/retention/hold": self.api_retention_hold,
                "/api/retention/hold/toggle": self.api_retention_hold_toggle,
                "/api/retention/dry-run": self.api_retention_dry_run,
                "/api/retention/execute": self.api_retention_execute,
            }
            fn = routes.get(path)
            if fn: return fn(user)
            return self.send_json({"error": "not found"}, 404)
        if path.startswith("/api/policies/"):
            if not self.require_interface(user, "policies", write=True): return
            routes={
                "/api/policies/save":self.api_policy_save,
                "/api/policies/toggle":self.api_policy_toggle,
                "/api/policies/delete":self.api_policy_delete,
                "/api/policies/migrate-legacy":self.api_policy_migrate_legacy,
                "/api/policies/legacy-mode":self.api_policy_legacy_mode,
            }
            fn=routes.get(path)
            if fn:return fn(user)
            return self.send_json({"error":"not found"},404)
        if path.startswith("/api/declarations/"):
            if not self.require_interface(user, "declarations", write=True): return
            routes={
                "/api/declarations/save":self.api_declaration_save,
                "/api/declarations/cancel":self.api_declaration_cancel,
                "/api/declarations/delete":self.api_declaration_delete,
            }
            fn=routes.get(path)
            if fn:return fn(user)
            return self.send_json({"error":"not found"},404)
        if path.startswith("/api/classification/") or path.startswith("/api/groups/") or path.startswith("/api/directory/"):
            if path.startswith("/api/groups/"):
                if not self.require_interface(user, "classification_groups", write=True): return
            elif path in {
                "/api/classification/support-priority",
                "/api/classification/support-priority/delete",
                "/api/classification/support-score",
            }:
                if not self.require_interface(user, "support_priority", write=True): return
            elif not self.require_interface(user, "classification", write=True): return
            routes = {
                "/api/classification/policy": self.api_site_policy,
                "/api/classification/rule": self.api_site_rule,
                "/api/classification/rule/delete": self.api_site_rule_delete,
                "/api/classification/rule/toggle": self.api_site_rule_toggle,
                "/api/classification/test": self.api_classification_test,
                "/api/groups/workspace/save": self.api_group_workspace_save,
                "/api/groups/workspace/add-capture": self.api_group_capture_add,
                "/api/groups/create": self.api_group_create,
                "/api/groups/delete": self.api_group_delete,
                "/api/groups/member": self.api_group_member,
                "/api/groups/member/delete": self.api_group_member_delete,
                "/api/groups/campaign": self.api_group_campaign,
                "/api/groups/campaign/delete": self.api_group_campaign_delete,
                "/api/directory/user": self.api_directory_user,
                "/api/directory/user/delete": self.api_directory_user_delete,
                "/api/directory/sync-support": self.api_directory_sync_support,
                "/api/classification/support-exclusion": self.api_support_exclusion,
                "/api/classification/support-exclusion/delete": self.api_support_exclusion_delete,
                "/api/classification/support-priority": self.api_support_priority_policy,
                "/api/classification/support-priority/delete": self.api_support_priority_delete,
                "/api/classification/support-score": self.api_support_score_policy,
                "/api/classification/followup": self.api_inventory_followup_policy,
            }
            fn = routes.get(path)
            if fn:
                return fn(user)
        return self.send_json({"error": "not found"}, 404)

    def serve_file(self, p, ctype=None):
        if not p.exists() or not p.is_file():
            return self.send_json({"error": "not found"}, 404)
        # Do not rely only on the Windows registry-backed mimetypes table for
        # executable static assets. Explicit types avoid strict MIME failures.
        if ctype is None:
            explicit = {
                ".js": "application/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".json": "application/json; charset=utf-8",
                ".svg": "image/svg+xml",
            }
            ctype = explicit.get(p.suffix.lower()) or mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        if ctype.startswith("text/") and "charset" not in ctype:
            ctype += "; charset=utf-8"
        self.send_bytes(p.read_bytes(), ctype)
