"""Fail-fast PostgreSQL runtime validation and safe schema repair for Nelyio.

This script is intentionally run before app.py on production startup.  It does
not import SIMPLIFY2 data and never resets PostgreSQL.  With --repair it only
creates missing runtime tables/columns, PostgreSQL helper functions, triggers
and indexes required by the current build.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import secrets
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
EXPECTED_SCHEMAS = ("admin", "supervision", "details", "live")
REQUIRED_TABLES = {
    "admin": {
        "settings", "users", "sessions", "user_directory", "user_groups",
        "user_group_members", "access_groups", "access_group_members", "access_group_permissions",
        "access_group_interface_permissions", "access_group_scope_policy", "access_group_scopes", "access_profiles",
        "diagnostic", "asset_management", "import_log", "site_policies", "site_rules",
        "quality_group_campaigns", "quality_group_lines", "support_priority_policies",
        "live_quality_levels", "live_quality_rules",
        "support_agent_exclusions", "retention_legal_holds", "retention_runs",
    },
    "supervision": {
        "settings", "imports", "coverage", "activities", "phone_calls", "phone_call_details",
        "phone_call_relations", "phone_call_relation_imports", "call_recordings", "call_recording_sizes", "live_call_observation_history",
        "call_coverage", "call_imports", "import_jobs", "ingestion_sequences",
        "live_events", "technical_signals", "quality_inbound_imports",
        "quality_inbound_facts", "quality_agent_imports", "quality_agent_facts", "quality_call_holds",
    },
    "details": {
        "detail_meta", "detail_imports", "detail_events", "detail_event_agents",
        "active_days", "sync_state", "sync_runs", "detail_read_revision",
    },
    "live": {
        "collection_settings", "collection_sessions", "collection_responses",
        "collection_events", "collection_catalog", "collection_audit",
        "collection_call_details",
    },
}
REQUIRED_FUNCTIONS = {
    "user_key", "ip_match", "classify_site", "classify_reason", "julianday",
    "followup_status", "strftime", "quality_local_hour", "distribution_hour",
    "distribution_agent",
}
REQUIRED_TRIGGERS = {
    "detail_read_events_insert", "detail_read_events_update", "detail_read_events_delete",
    "detail_read_agents_insert", "detail_read_agents_update", "detail_read_agents_delete",
    "detail_read_days_insert", "detail_read_days_update", "detail_read_days_delete",
}
REQUIRED_SUPERVISION_SETTINGS = {
    "export_offset", "display_offset", "capture_offset", "pause_seconds",
    "offline_seconds", "ready_seconds", "wrap_seconds", "stale_seconds",
    "work_start", "work_end", "bridge_key", "recording_reference_bps",
    "recording_low_percent", "recording_critical_percent", "recording_min_seconds",
}
REQUIRED_SUPERVISION_INDEXES = {
    "supervision_live_events_ingest_seq",
    "supervision_technical_signals_ingest_seq",
    "supervision_quality_inbound_day",
    "supervision_quality_inbound_selected",
    "supervision_quality_inbound_agent_selected",
    "supervision_quality_outbound_selected",
    "supervision_quality_outbound_agent_selected",
    "supervision_quality_agent_time",
    "supervision_quality_agent_selected",
    "supervision_quality_call_holds_session",
    "supervision_activity_import_agent_time",
    "supervision_calls_import_agent_time",
    "supervision_calls_import_campaign_time",
    "supervision_call_details_queue",
    "supervision_call_details_transfer",
    "supervision_call_relations_call",
    "supervision_call_relations_ref",
    "supervision_call_recordings_indice",
    "supervision_call_recordings_day_agent",
}


def _load_env() -> Path:
    env = ROOT / "data" / "postgres.env"
    if not env.is_file():
        raise RuntimeError("data\\postgres.env absent. Lancez CONFIGURER_POSTGRESQL_AUTO.bat.")
    for raw in env.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())
    if os.environ.get("NELYIO_DATABASE_ENGINE", "").strip().lower() not in {"postgres", "postgresql"}:
        raise RuntimeError("NELYIO_DATABASE_ENGINE n est pas PostgreSQL.")
    if not os.environ.get("NELYIO_DATABASE_URL", "").strip():
        raise RuntimeError("NELYIO_DATABASE_URL absent dans data\\postgres.env.")
    return env


def _add(result: dict[str, Any], name: str, ok: bool, detail: Any, level: str = "error") -> None:
    result["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail), "level": level})


def _repair_stage(label: str, fn):
    """Run one repair stage and preserve the first/root error in diagnostics."""
    try:
        return fn()
    except Exception as exc:
        raise RuntimeError(f"{label}: {type(exc).__name__}: {exc}") from exc


def _repair(pg) -> None:
    # Prevent the Web-only Details full sync from running in this preflight.
    os.environ["NELYIO_SKIP_STARTUP_DETAILS_SYNC"] = "1"
    import app_db
    import collection_store
    import details_store
    import group_har_import
    import import_workflow
    import postgres_migrate
    import quality_agents
    import quality_metrics
    import supervision_db

    # Never inherit an aborted/read transaction from an earlier preflight step.
    try:
        pg.rollback()
    except Exception:
        pass

    _repair_stage("admin.ensure_schema", app_db.ensure_schema)
    _repair_stage("supervision.init", supervision_db.init)
    _repair_stage("details.init", details_store.init)
    _repair_stage("live.collection_store.init", lambda: collection_store.init(force=True))

    def _repair_supervision_modules():
        with supervision_db.connect() as con:
            quality_metrics.ensure_schema(con)
            quality_agents.ensure_schema(con)
            import_workflow.ensure_schema(con)
    _repair_stage("supervision modules", _repair_supervision_modules)

    def _repair_admin_modules():
        with app_db.db_connect() as con:
            group_har_import.ensure_schema(con)
    _repair_stage("admin group_har", _repair_admin_modules)

    # Persist every required legacy setting. A prior failed transaction could
    # have left an old migrated settings table incomplete (the observed
    # export_offset KeyError). These inserts are idempotent and non-destructive.
    def _repair_defaults():
        defaults=dict(supervision_db.DEFAULTS)
        with pg.cursor() as cur:
            for key, value in defaults.items():
                cur.execute(
                    "INSERT INTO supervision.settings(key,value) VALUES(%s,%s) "
                    "ON CONFLICT (key) DO NOTHING",
                    (key, str(value)),
                )
            cur.execute(
                "INSERT INTO supervision.settings(key,value) VALUES(%s,%s) "
                "ON CONFLICT (key) DO NOTHING",
                ("bridge_key", secrets.token_urlsafe(32)),
            )
        pg.commit()
    try:
        _repair_stage("supervision settings defaults", _repair_defaults)
    except Exception:
        pg.rollback()
        raise

    # PostgreSQL-only insertion cursors replace SQLite rowid in incremental
    # Details sync. Execute/commit each DDL group so a future incompatibility
    # reports its real statement instead of a later InFailedSqlTransaction.
    ddl_steps = [
        ("live_events ingest_seq",
         "ALTER TABLE supervision.live_events ADD COLUMN IF NOT EXISTS ingest_seq BIGINT GENERATED BY DEFAULT AS IDENTITY"),
        ("technical_signals ingest_seq",
         "ALTER TABLE supervision.technical_signals ADD COLUMN IF NOT EXISTS ingest_seq BIGINT GENERATED BY DEFAULT AS IDENTITY"),
        ("live_events ingest_seq index",
         "CREATE UNIQUE INDEX IF NOT EXISTS supervision_live_events_ingest_seq ON supervision.live_events(ingest_seq)"),
        ("technical_signals ingest_seq index",
         "CREATE UNIQUE INDEX IF NOT EXISTS supervision_technical_signals_ingest_seq ON supervision.technical_signals(ingest_seq)"),
        ("quality inbound index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_inbound_day ON supervision.quality_inbound_facts(import_id,day,campaign,start)"),
        ("quality inbound selected-day index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_inbound_selected ON supervision.quality_inbound_facts(import_id,day,start)"),
        ("quality inbound selected-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_inbound_agent_selected ON supervision.quality_inbound_facts(import_id,day,agent,start)"),
        ("quality outbound selected-day index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_outbound_selected ON supervision.quality_outbound_facts(import_id,day,start)"),
        ("quality outbound selected-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_outbound_agent_selected ON supervision.quality_outbound_facts(import_id,day,agent,start)"),
        ("quality agent index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_agent_time ON supervision.quality_agent_facts(import_id,start,\"end\",agent)"),
        ("quality agent selected-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_agent_selected ON supervision.quality_agent_facts(import_id,agent,start,\"end\")"),
        ("quality call holds session index",
         "CREATE INDEX IF NOT EXISTS supervision_quality_call_holds_session ON supervision.quality_call_holds(import_id,call_id)"),
        ("support activity selected-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_activity_import_agent_time ON supervision.activities(import_id,agent,start,\"end\")"),
        ("support calls selected-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_calls_import_agent_time ON supervision.phone_calls(import_id,first_agent,start)"),
        ("support calls campaign-time index",
         "CREATE INDEX IF NOT EXISTS supervision_calls_import_campaign_time ON supervision.phone_calls(import_id,campaign,start)"),
        ("call details queue index",
         "CREATE INDEX IF NOT EXISTS supervision_call_details_queue ON supervision.phone_call_details(import_id,first_queue)"),
        ("call details transfer index",
         "CREATE INDEX IF NOT EXISTS supervision_call_details_transfer ON supervision.phone_call_details(import_id,last_transfer)"),
        ("call relations call index",
         "CREATE INDEX IF NOT EXISTS supervision_call_relations_call ON supervision.phone_call_relations(import_id,call_id)"),
        ("call relations ref index",
         "CREATE INDEX IF NOT EXISTS supervision_call_relations_ref ON supervision.phone_call_relations(import_id,ref_call_id)"),
        ("call recordings indice index",
         "CREATE INDEX IF NOT EXISTS supervision_call_recordings_indice ON supervision.call_recordings(indice)"),
        ("call recordings day-agent index",
         "CREATE INDEX IF NOT EXISTS supervision_call_recordings_day_agent ON supervision.call_recordings(recorded_day,agent)"),
    ]
    for label, sql in ddl_steps:
        try:
            with pg.cursor() as cur:
                cur.execute(sql)
            pg.commit()
        except Exception as exc:
            pg.rollback()
            raise RuntimeError(f"{label}: {type(exc).__name__}: {exc}") from exc

    try:
        postgres_migrate.create_helpers(pg)
    except Exception as exc:
        pg.rollback()
        raise RuntimeError(f"postgres helpers/triggers: {type(exc).__name__}: {exc}") from exc



def _application_smoke() -> dict[str, Any]:
    """Run representative read-only application queries against PostgreSQL."""
    os.environ["NELYIO_SKIP_STARTUP_DETAILS_SYNC"] = "1"
    import agent_directory
    import details_store
    import import_workflow
    import quality_agents
    import quality_metrics
    import retention_service
    import app_db
    import inventory_service

    def step(label, fn):
        try:
            return fn()
        except Exception as exc:
            raise RuntimeError(f"{label}: {type(exc).__name__}: {exc}") from exc

    service=step("Qualite service overview", lambda: quality_metrics.overview({}))
    agents=step("Qualite agents view", lambda: quality_agents.view({}))
    from calls import calls_view
    calls=step("Recherche appels", lambda: calls_view({}))
    step("Serialisation JSON metriques", lambda: json.dumps({'service':service,'agents':agents,'calls':calls},ensure_ascii=False))
    directory=step("Annuaire admin", agent_directory.load_admin_directory)
    workflow=step("Workflow import", import_workflow.workflow_status)
    detail_status=step("Details status", details_store.status)

    def dashboard_probe():
        with app_db.db_connect() as con:
            rows=con.execute(inventory_service.current_sql()).fetchall()
            con.execute(inventory_service.dashboard_transitions_sql(10)).fetchall()
            # Probe the second aggregate-alias query used by the PC detail page.
            # A dummy PC keeps the check read-only while validating PostgreSQL syntax.
            con.execute(inventory_service.pc_users_sql(), ("__NELYIO_PREFLIGHT__",)).fetchall()
        return len(rows)

    def classification_probe():
        # Cover the SQL used by /api/classification without mutating data.
        with app_db.db_connect() as con:
            con.execute("""
                SELECT g.id,g.name,g.description,g.created_at,g.created_by,g.updated_at,g.updated_by,COUNT(m.user_key) member_count
                FROM user_groups g LEFT JOIN user_group_members m ON m.group_id=g.id
                GROUP BY g.id,g.name,g.description,g.created_at,g.created_by,g.updated_at,g.updated_by
                ORDER BY g.name COLLATE NOCASE
            """).fetchall()
            con.execute("""
                SELECT user_key(utilisateur) user_key,MAX(utilisateur) exemple,COUNT(*) passages,MAX(date_evenement) derniere_vue
                FROM diagnostic WHERE TRIM(COALESCE(utilisateur,''))<>''
                GROUP BY user_key(utilisateur) ORDER BY MAX(date_evenement) DESC LIMIT 250
            """).fetchall()
            inventory_service.followup_config(con)
        agent_directory.support_directory_candidates()
        return True

    dashboard_count=step("Dashboard PostgreSQL", dashboard_probe)
    classification_ok=step("Classification PostgreSQL", classification_probe)
    retention=step("Retention PostgreSQL", retention_service.retention_plan)
    return {
        "quality_source":service.get("source"),
        "quality_available_days":service.get("available_days"),
        "quality_agents_available_days":agents.get("available_days"),
        "directory_users":len(directory.get("users",{})),
        "import_jobs":len(workflow.get("jobs",[])),
        "details_ok":bool(detail_status),
        "dashboard_rows":dashboard_count,
        "classification_ok":bool(classification_ok),
        "retention_items":len(retention.get("items",[])),
    }


def run(repair: bool = False, startup: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "repair": bool(repair), "checks": []}
    try:
        _load_env()
        if startup:
            # Startup must never wait indefinitely on PostgreSQL DDL locks or
            # long validation queries.  PGOPTIONS is inherited by every
            # psycopg connection opened by the schema helpers in this process.
            existing = os.environ.get("PGOPTIONS", "").strip()
            bounded = "-c lock_timeout=5000 -c statement_timeout=60000"
            os.environ["PGOPTIONS"] = (existing + " " + bounded).strip()
        import db_compat
        _add(result, "Mode PostgreSQL", db_compat.postgres_enabled(), db_compat.DB_COMPAT_BUILD)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg absent. Relancez CONFIGURER_POSTGRESQL_AUTO.bat.") from exc
        dsn = os.environ["NELYIO_DATABASE_URL"].strip()
        pg = psycopg.connect(dsn, connect_timeout=5)
        try:
            with pg.cursor() as cur:
                cur.execute("SET TIME ZONE 'Europe/Paris'")
                cur.execute("SELECT current_database(), current_user, current_setting('TimeZone'), version()")
                database, user, timezone, version = cur.fetchone()
            _add(result, "Connexion PostgreSQL", True, f"base={database}; user={user}")
            _add(result, "Fuseau PostgreSQL", timezone == "Europe/Paris", timezone)
            _add(result, "Version PostgreSQL", True, str(version).split(",")[0])
            # End the metadata transaction before runtime repair.
            pg.commit()

            if repair:
                try:
                    _repair(pg)
                    _add(result, "Reparation schema runtime", True, "schémas/fonctions/index mis à niveau sans reset")
                except Exception as exc:
                    try:
                        pg.rollback()
                    except Exception:
                        pass
                    _add(result, "Reparation schema runtime", False, f"{type(exc).__name__}: {exc}")

            with pg.cursor() as cur:
                cur.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name=ANY(%s)", (list(EXPECTED_SCHEMAS),))
                schemas = {r[0] for r in cur.fetchall()}
            missing_schemas = sorted(set(EXPECTED_SCHEMAS) - schemas)
            _add(result, "Schemas PostgreSQL", not missing_schemas, "OK" if not missing_schemas else "absents: " + ", ".join(missing_schemas))

            missing_tables: list[str] = []
            with pg.cursor() as cur:
                for schema, expected in REQUIRED_TABLES.items():
                    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s", (schema,))
                    present = {r[0] for r in cur.fetchall()}
                    missing_tables.extend(f"{schema}.{name}" for name in sorted(expected - present))
            _add(result, "Tables runtime", not missing_tables, "OK" if not missing_tables else "absentes: " + ", ".join(missing_tables))

            with pg.cursor() as cur:
                cur.execute("""SELECT table_schema,table_name,column_name FROM information_schema.columns
                    WHERE table_schema=ANY(%s) AND data_type='real'
                    AND column_name IN ('start','end','stamp','first_response','last_response')""",(list(EXPECTED_SCHEMAS),))
                low_precision=['.'.join(r) for r in cur.fetchall()]
            _add(result,"Precision horodatages",not low_precision,
                 'OK' if not low_precision else 'Colonnes REAL 32 bits: '+', '.join(low_precision)+'. Réimport source nécessaire si précision déjà perdue; aucune conversion automatique.')
            missing_settings=[]
            if "supervision.settings" not in missing_tables:
                with pg.cursor() as cur:
                    cur.execute("SELECT key FROM supervision.settings WHERE key=ANY(%s)", (list(REQUIRED_SUPERVISION_SETTINGS),))
                    present_settings={r[0] for r in cur.fetchall()}
                missing_settings=sorted(REQUIRED_SUPERVISION_SETTINGS-present_settings)
            _add(result, "Parametres supervision", not missing_settings,
                 "OK" if not missing_settings else "absents: " + ", ".join(missing_settings))

            missing_indexes=[]
            if "supervision.quality_inbound_facts" not in missing_tables:
                with pg.cursor() as cur:
                    cur.execute("SELECT indexname FROM pg_indexes WHERE schemaname='supervision'")
                    present_indexes={r[0] for r in cur.fetchall()}
                missing_indexes=sorted(REQUIRED_SUPERVISION_INDEXES-present_indexes)
            _add(result, "Index performance PostgreSQL", not missing_indexes,
                 "OK" if not missing_indexes else "absents: " + ", ".join(missing_indexes))

            with pg.cursor() as cur:
                cur.execute("SELECT routine_name FROM information_schema.routines WHERE routine_schema='public'")
                funcs = {r[0] for r in cur.fetchall()}
            missing_funcs = sorted(REQUIRED_FUNCTIONS - funcs)
            _add(result, "Fonctions compatibilite", not missing_funcs, "OK" if not missing_funcs else "absentes: " + ", ".join(missing_funcs))

            with pg.cursor() as cur:
                cur.execute("SELECT trigger_name FROM information_schema.triggers WHERE trigger_schema='details'")
                triggers = {r[0] for r in cur.fetchall()}
            missing_triggers = sorted(REQUIRED_TRIGGERS - triggers)
            _add(result, "Triggers Details", not missing_triggers, "OK" if not missing_triggers else "absents: " + ", ".join(missing_triggers))

            with pg.cursor() as cur:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='supervision' AND table_name='live_events'")
                live_cols = {r[0] for r in cur.fetchall()}
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='supervision' AND table_name='technical_signals'")
                sig_cols = {r[0] for r in cur.fetchall()}
            _add(result, "Curseurs Details PostgreSQL", "ingest_seq" in live_cols and "ingest_seq" in sig_cols,
                 "live_events.ingest_seq + technical_signals.ingest_seq")

            # Functional probes exercise the helpers needed by quality and filters.
            try:
                with pg.cursor() as cur:
                    cur.execute("SELECT public.quality_local_hour(0), public.distribution_hour(0), public.distribution_agent('S1001'), public.user_key('DOMAIN\\\\1001')")
                    probe = cur.fetchone()
                _add(result, "Probe fonctions Qualite",
                     probe[0] == probe[1] and probe[2] == "1001" and probe[3] == "1001", probe)
            except Exception as exc:
                pg.rollback()
                _add(result, "Probe fonctions Qualite", False, f"{type(exc).__name__}: {exc}")

            # psycopg interprets percent signs as pyformat placeholders when a
            # parameter sequence is supplied. Legacy Nelyio SQL legitimately
            # contains literal percent wildcards in LIKE/strftime expressions.
            # Exercise both parameterless and parameterized compatibility paths.
            try:
                import app_db
                with app_db.db_connect() as con:
                    con.execute("SELECT key FROM settings WHERE key LIKE 'inventory_followup_%' LIMIT 1").fetchall()
                    con.execute("SELECT key FROM settings WHERE key LIKE 'inventory_followup_%' AND key<>? LIMIT 1", ("__NELYIO_PREFLIGHT__",)).fetchall()
                _add(result, "Compatibilite pourcent psycopg", True, "LIKE % sans parametres + avec parametres")
            except Exception as exc:
                _add(result, "Compatibilite pourcent psycopg", False, f"{type(exc).__name__}: {exc}")

            # Tables must be readable. This also detects grants/search-path issues.
            read_errors=[]
            with pg.cursor() as cur:
                for schema, table in (("admin","settings"),("supervision","imports"),("details","detail_events"),("live","collection_events")):
                    try:
                        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
                        cur.fetchone()
                    except Exception as exc:
                        read_errors.append(f"{schema}.{table}: {exc}")
                        pg.rollback()
            _add(result, "Lecture schemas", not read_errors, "OK" if not read_errors else " | ".join(read_errors))

            if (not missing_schemas and not missing_tables and not missing_settings and not missing_indexes
                    and not missing_funcs and not missing_triggers):
                if startup:
                    _add(result, "Validation startup rapide", True,
                         "schema/fonctions/triggers/lectures verifies; smoke applicatif complet reporte aux outils de validation")
                else:
                    try:
                        smoke=_application_smoke()
                        _add(result, "Smoke test applicatif", True, smoke)
                    except Exception as exc:
                        _add(result, "Smoke test applicatif", False, f"{type(exc).__name__}: {exc}")
        finally:
            pg.close()
    except Exception as exc:
        _add(result, "Preflight PostgreSQL", False, f"{type(exc).__name__}: {exc}")
    result["ok"] = all(c["ok"] or c["level"] == "warning" for c in result["checks"])
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repair", action="store_true", help="Créer/mettre à niveau uniquement les objets runtime manquants")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--startup", action="store_true",
                    help="Mode demarrage rapide: timeouts PostgreSQL bornes et smoke applicatif complet reporte")
    args = ap.parse_args()
    result = run(args.repair, startup=args.startup)
    for c in result["checks"]:
        label = "OK" if c["ok"] else ("ATTENTION" if c["level"] == "warning" else "ECHEC")
        print(f"{label} - {c['check']} : {c['detail']}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
