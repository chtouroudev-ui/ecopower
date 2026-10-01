"""Nelyio application entry point and backward-compatible public facade.

The implementation is split into focused modules so changes to authentication,
classification, imports, inventory, HTTP routing, and runtime startup can be
made independently. Public names historically imported from ``app`` remain
available here for compatibility.
"""

import os
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

import app_config as cfg
import runtime

# FIX4 - bootstrap diagnostics before importing supervision.  supervision.py
# performs schema initialization at import time, so a slow import used to leave
# all regular startup logs empty.  Also defer the expensive Details projection
# rebuild when the production launcher uses external services.
def _bootstrap_note(message):
    try:
        log_dir = Path(__file__).resolve().parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "startup_progress.log").open("a", encoding="utf-8") as fh:
            fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + str(message) + "\n")
    except Exception:
        pass

_bootstrap_note("Bootstrap Python : avant import supervision")
if os.environ.get("NELYIO_EXTERNAL_SERVICES", "").strip().lower() in {"1", "true", "yes", "on"}:
    os.environ.setdefault("NELYIO_SKIP_STARTUP_DETAILS_SYNC", "1")
import supervision
_bootstrap_note("Bootstrap Python : import supervision termine")
from service_mode import external_services_enabled
import service_state
from error_log import log_unexpected_error
from service_control import clear_stop, stop_requested

# Backward-compatible configuration names.
BASE = cfg.BASE
APP_DB = cfg.APP_DB
STATIC = cfg.STATIC
LEGACY_DIAG_DB = cfg.LEGACY_DIAG_DB
LEGACY_STOCK_DB = cfg.LEGACY_STOCK_DB
LEGACY_AUTH_DB = cfg.LEGACY_AUTH_DB
ADMIN_PASSWORD_FILE = cfg.ADMIN_PASSWORD_FILE
SESSION_COOKIE = cfg.SESSION_COOKIE
SESSION_MAX_HOURS = cfg.SESSION_MAX_HOURS
SESSION_IDLE_MINUTES = cfg.SESSION_IDLE_MINUTES
LOGIN_MAX_FAILURES = cfg.LOGIN_MAX_FAILURES
LOGIN_LOCK_MINUTES = cfg.LOGIN_LOCK_MINUTES
MAX_JSON_BYTES = cfg.MAX_JSON_BYTES
PBKDF2_ROUNDS = cfg.PBKDF2_ROUNDS
DEFAULT_HOST = cfg.DEFAULT_HOST
DEFAULT_PORT = cfg.DEFAULT_PORT
FALLBACK_PORTS = cfg.FALLBACK_PORTS
ADMIN_STATUS = cfg.ADMIN_STATUS
ROLES = cfg.ROLES
ROLE_LEVEL = cfg.ROLE_LEVEL
ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_NONE = cfg.ACCESS_NONE
ACCESS_READ = cfg.ACCESS_READ
ACCESS_WRITE = cfg.ACCESS_WRITE
EDIT_FIELDS = cfg.EDIT_FIELDS
DIAG_FIELDS = cfg.DIAG_FIELDS
SITE_VALUES = cfg.SITE_VALUES

ACTIVE_HOST = runtime.ACTIVE_HOST
ACTIVE_PORT = runtime.ACTIVE_PORT
AUTO_IMPORT_STOP = runtime.AUTO_IMPORT_STOP

# Public service facade retained for compatibility with existing scripts/tests.
from classification import (  # noqa: E402
    normalize_user_key,
    parse_ip_selector,
    selector_contains,
    ip_matches_selector,
    classify_site_details,
    classify_site_value,
    classify_site_reason,
    refresh_classification_cache,
)
from app_db import (  # noqa: E402
    now_text,
    db_connect,
    get_setting,
    set_setting,
    ensure_schema,
)
from auth_service import (  # noqa: E402
    _legacy_permissions,
    access_profile,
    user_has_access,
    password_hash,
    verify_password,
    bootstrap_admin,
)
from diagnostic_import import (  # noqa: E402
    normalize_diagnostic_path,
    open_sqlite_readonly,
    source_schema_info,
    import_diagnostic_source,
    migrate_legacy_once,
)
from inventory_service import (  # noqa: E402
    site_case,
    current_sql,
    rows_to_dict,
    clean_pc_name,
    clean_username,
)
from runtime import (  # noqa: E402
    validate_host,
    local_lan_ip,
    auto_import_loop,
    create_server,
    configured_network,
    configured_tls,
    enable_direct_tls,
)
from production_http import Handler, BUILD  # noqa: E402


def _startup_note(message):
    """Persist startup progress even when stdout is redirected by Windows."""
    text = str(message)
    line = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + text
    try:
        log_dir = BASE / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "startup_progress.log").open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    print("[STARTUP] " + text, flush=True)


def _startup_step(label, fn, critical=False):
    started = time.perf_counter()
    _startup_note(label + " ...")
    try:
        result = fn()
    except Exception as exc:
        elapsed = time.perf_counter() - started
        _startup_note(f"{label} ECHEC apres {elapsed:.2f}s : {type(exc).__name__}: {exc}")
        if critical:
            raise
        return None
    elapsed = time.perf_counter() - started
    _startup_note(f"{label} OK ({elapsed:.2f}s)")
    return result


def _post_startup_maintenance(services_external):
    """Run non-critical maintenance after HTTP is already able to answer.

    These jobs used to execute before create_server()/serve_forever(), which
    meant a slow Support directory sync, legacy migration, group recovery or
    startup import could keep port 9051 closed for minutes without a Python
    traceback.  They are deliberately best-effort and must never gate /healthz.
    """
    # PERF1: in production the Web/API process must stay dedicated to HTTP.
    # Import/live workers already persist new data and synchronize the derived
    # stores. Running the same maintenance from the Web process causes
    # PostgreSQL write contention and makes even simple HTTP pages stall.
    if services_external:
        _startup_note("Maintenance lourde deleguee aux services externes : Web/API reste disponible")
        return

    # FIX4: supervision.init() used to force a full Details rebuild while
    # supervision.py was imported, i.e. before main() and before port 9051.
    # START_NELYIO.ps1 now skips that import-time rebuild; execute it here after
    # the HTTP server is already accepting /healthz.
    try:
        import details_store
        import supervision_context as supervision_state
        _startup_step(
            "Synchronisation Details differee",
            lambda: details_store.sync_from_sources(
                supervision_state.db_path(),
                supervision_state.admin_db_path(),
                supervision_state.tech_labels(),
                force=True,
            ),
        )
    except Exception as exc:
        log_unexpected_error("app.startup.details_deferred")
        _startup_note("Synchronisation Details differee ignoree : " + str(exc))

    try:
        _startup_step(
            "Synchronisation annuaire Support",
            lambda: supervision.sync_admin_directory_from_support('SUPPORT_SYNC'),
        )
    except Exception as exc:
        log_unexpected_error('app.startup.support_directory')
        _startup_note("Synchronisation annuaire Support ignoree : " + str(exc))

    try:
        _startup_step("Migration legacy", migrate_legacy_once)
    except Exception as exc:
        log_unexpected_error('app.startup.legacy_migration')
        _startup_note("Migration legacy ignoree : " + str(exc))

    try:
        from group_workspace import recover_known_groups_once
        _startup_step("Reprise groupes F4.1", recover_known_groups_once)
    except Exception as exc:
        log_unexpected_error('app.startup.group_recovery_f41')
        _startup_note("Reprise groupes non appliquee : " + str(exc))

    # Startup import is intentionally background work.  A large diagnostic
    # source must not prevent the web application from binding port 9051.
    try:
        if get_setting("auto_import_enabled", "0") == "1":
            source = get_setting("diagnostic_source_path", "").strip()
            if source:
                def do_startup_import():
                    result = import_diagnostic_source(source, "AUTO_START")
                    _startup_note(f"Import demarrage : {result['imported_rows']} nouveau(x) diagnostic(s)")
                _startup_step("Import diagnostic de demarrage", do_startup_import)
    except Exception as exc:
        log_unexpected_error('app.startup.auto_import')
        _startup_note("Import demarrage ignore : " + str(exc))

    if not services_external:
        try:
            supervision.start_auto_importer()
            _startup_note(f"Import auto Support/Appels actif : {supervision.IMPORT_DIR}")
        except Exception as exc:
            log_unexpected_error('app.startup.auto_importer')
            _startup_note("Import auto Support/Appels indisponible : " + str(exc))
        try:
            from collection_service import manager as live_manager
            live_manager().resume()
            _startup_note("Collecte live reprise")
        except Exception as exc:
            log_unexpected_error("app.startup.collection")
            _startup_note("Collecte live non reprise : " + str(exc))
        try:
            thread = threading.Thread(target=auto_import_loop, name="techin-auto-import", daemon=True)
            thread.start()
        except Exception as exc:
            log_unexpected_error("app.startup.auto_import_loop")
            _startup_note("Boucle auto-import non demarree : " + str(exc))

    _startup_note("Maintenance post-demarrage terminee")


def main():
    """Initialize the web core first; run non-critical maintenance afterwards."""
    global ACTIVE_HOST, ACTIVE_PORT

    clear_stop('backend')
    _startup_note("Debut app.py")

    # START_NELYIO.ps1 performs the PostgreSQL runtime preflight immediately
    # before launching this process.  Replaying the full schema DDL here was
    # redundant and, under a PostgreSQL lock, could keep 9051 closed for an
    # unbounded amount of time.  Keep ensure_schema() for direct/manual starts
    # and for SQLite mode, but skip it after a successful PostgreSQL preflight.
    preflight_ok = os.environ.get("NELYIO_POSTGRES_PREFLIGHT_OK", "") == "1"
    postgres_mode = False
    try:
        import db_compat
        postgres_mode = bool(db_compat.postgres_enabled())
    except Exception:
        postgres_mode = False

    if postgres_mode and preflight_ok:
        _startup_note("Schema PostgreSQL deja valide par le preflight : ensure_schema() non rejoue")
    else:
        _startup_step("Verification schema application", ensure_schema, critical=True)

    _startup_step("Chargement classification", refresh_classification_cache, critical=True)
    _startup_step("Bootstrap administration", bootstrap_admin, critical=True)

    host, configured_port = configured_network()
    server, active_port = _startup_step(
        "Creation serveur HTTP",
        lambda: create_server(host, configured_port),
        critical=True,
    )
    tls_enabled, tls_cert_path, tls_key_path = configured_tls()
    if tls_enabled:
        try:
            enable_direct_tls(server, tls_cert_path, tls_key_path)
        except Exception as exc:
            server.server_close()
            raise RuntimeError(f"HTTPS activé mais configuration TLS invalide : {exc}") from exc
    else:
        server.techin_https = False

    ACTIVE_HOST = host
    ACTIVE_PORT = active_port
    runtime.ACTIVE_HOST = host
    runtime.ACTIVE_PORT = active_port

    if active_port != configured_port:
        print(f"Port {configured_port} indisponible ou bloqué. Utilisation automatique du port {active_port}.", flush=True)

    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    scheme = "https" if tls_enabled else "http"
    print(f"Nelyio {BUILD} - Edition complete : {scheme}://{display_host}:{active_port}", flush=True)
    if host == "0.0.0.0":
        lan = local_lan_ip()
        if lan:
            print(f"Accès réseau local : {scheme}://{lan}:{active_port}", flush=True)
    if host == "127.0.0.1" and not tls_enabled:
        print("Mode recommandé reverse proxy : backend local uniquement (127.0.0.1).", flush=True)
    print(f"Base centrale : {APP_DB}", flush=True)

    services_external = external_services_enabled()
    if services_external:
        from production_http import start_health_monitor
        start_health_monitor(active_port)
        print('Mode services actifs : Live et Analytics sont separes du Web/API. Import SIMPLIFY2 via OPEN_NELYIO_IMPORTER.bat.', flush=True)

    # The maintenance thread starts before serve_forever but does not gate it.
    # As soon as serve_forever() is entered, /healthz can answer while the
    # directory/group/import housekeeping continues in the background.
    maintenance = threading.Thread(
        target=_post_startup_maintenance,
        args=(services_external,),
        name="nelyio-post-startup",
        daemon=True,
    )
    maintenance.start()

    def watch_stop_flag():
        while True:
            if stop_requested('backend'):
                _startup_note("Arret backend demande par le lanceur")
                try: server.shutdown()
                except Exception: pass
                return
            time.sleep(0.5)
    threading.Thread(target=watch_stop_flag,name='nelyio-backend-stop-watcher',daemon=True).start()
    _startup_note(f"Serveur HTTP pret a ecouter sur {host}:{active_port}; entree dans serve_forever")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de TECH-IN Stock Manager.", flush=True)
    finally:
        AUTO_IMPORT_STOP.set()
        if services_external:
            service_state.stop('web', {'port':active_port})
        else:
            try:
                from collection_service import manager as live_manager
                live_manager().shutdown()
            except Exception:
                pass
            try:
                supervision.stop_auto_importer()
            except Exception:
                pass
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Keep a persistent startup trace for Windows/service launches where
        # the console may close before the operator can read the exception.
        try:
            log_dir = BASE / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            with (log_dir / "startup_error.log").open("a", encoding="utf-8") as fh:
                fh.write("\n" + "=" * 78 + "\n")
                fh.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " - STARTUP FAILURE\n")
                traceback.print_exc(file=fh)
        except Exception:
            pass
        traceback.print_exc()
        raise
