from datetime import datetime
import json
import db_compat as sqlite3

import app_config as cfg
from inventory_followup import followup_sql
from auth_service import _legacy_permissions
from classification import (
    classify_site_reason, classify_site_value, ip_matches_selector, normalize_user_key,
)
from error_log import log_unexpected_error
from support_scoring import DEFAULT_SCORE_CONFIG, SCORE_SETTING_KEY

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class ClosingConnection(sqlite3.Connection):
    """Commit/rollback AND close: sqlite3's default context manager does not close."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def db_connect():
    con = sqlite3.connect(cfg.APP_DB, timeout=10, factory=ClosingConnection)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    con.create_function("classify_site", 2, lambda c, i: classify_site_value(c, i, ""))
    con.create_function("classify_site", 3, classify_site_value)
    con.create_function("classify_reason", 2, lambda c, i: classify_site_reason(c, i, ""))
    con.create_function("classify_reason", 3, classify_site_reason)
    con.create_function("user_key", 1, normalize_user_key)
    con.create_function("ip_match", 2, ip_matches_selector)
    con.create_function("followup_status", 3, followup_sql, deterministic=True)
    return con

def get_setting(key, default=""):
    try:
        with db_connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default
    except Exception:
        log_unexpected_error('app.get_setting.L345')
        return default

def set_setting(con, key, value, actor="SYSTEM"):
    con.execute("""
        INSERT INTO settings(key,value,updated_at,updated_by) VALUES(?,?,?,?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at,updated_by=excluded.updated_by
    """, (key, str(value), now_text(), actor))

def ensure_schema():
    cfg.APP_DB.parent.mkdir(parents=True, exist_ok=True)
    with db_connect() as con:
        con.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS diagnostic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_uuid TEXT NOT NULL UNIQUE,
            date_evenement TEXT NOT NULL,
            action TEXT,
            utilisateur TEXT,
            ordinateur TEXT,
            adresse_ip TEXT,
            passerelle TEXT,
            adresse_mac TEXT,
            sn_pc TEXT,
            sn_carte_mere TEXT,
            domaine TEXT,
            fabricant TEXT,
            modele TEXT,
            windows TEXT,
            version_windows TEXT,
            collecteur TEXT,
            version_script TEXT,
            date_import TEXT DEFAULT CURRENT_TIMESTAMP,
            source_path TEXT DEFAULT '',
            source_row_id INTEGER,
            import_batch_id INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_diag_pc_date ON diagnostic(ordinateur,date_evenement DESC);
        CREATE INDEX IF NOT EXISTS idx_diag_pc_date_id ON diagnostic(ordinateur,date_evenement DESC,id DESC);
        CREATE INDEX IF NOT EXISTS idx_diag_collector ON diagnostic(collecteur);
        CREATE INDEX IF NOT EXISTS idx_diag_user_latest
            ON diagnostic(utilisateur,datetime(date_evenement) DESC,id DESC)
            WHERE TRIM(COALESCE(utilisateur,''))<>'' AND TRIM(COALESCE(ordinateur,''))<>'';

        CREATE TABLE IF NOT EXISTS asset_management (
            ordinateur TEXT PRIMARY KEY COLLATE NOCASE,
            asset_tag TEXT DEFAULT '',
            statut TEXT NOT NULL DEFAULT 'EN_SERVICE',
            affectation TEXT DEFAULT '',
            emplacement_attendu TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            manual_utilisateur TEXT DEFAULT '',
            manual_ip TEXT DEFAULT '',
            manual_mac TEXT DEFAULT '',
            manual_sn_pc TEXT DEFAULT '',
            manual_sn_carte_mere TEXT DEFAULT '',
            manual_domaine TEXT DEFAULT '',
            manual_fabricant TEXT DEFAULT '',
            manual_modele TEXT DEFAULT '',
            manual_windows TEXT DEFAULT '',
            manual_version_windows TEXT DEFAULT '',
            created_manually INTEGER NOT NULL DEFAULT 0,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS manual_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ordinateur TEXT NOT NULL,
            action TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            username TEXT NOT NULL,
            user_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_manual_audit_pc ON manual_audit(ordinateur,created_at DESC);

        CREATE TABLE IF NOT EXISTS consumables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            category TEXT DEFAULT '',
            unit TEXT NOT NULL DEFAULT 'unité',
            min_quantity INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS consumable_balances (
            consumable_id INTEGER NOT NULL,
            condition TEXT NOT NULL CHECK(condition IN ('NEUF','ANCIEN','KO')),
            quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(consumable_id,condition),
            FOREIGN KEY(consumable_id) REFERENCES consumables(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS consumable_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            consumable_id INTEGER NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('ENTREE','SORTIE')),
            condition TEXT NOT NULL CHECK(condition IN ('NEUF','ANCIEN','KO')),
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            beneficiary_key TEXT DEFAULT '',
            beneficiary_identifier TEXT DEFAULT '',
            beneficiary_name TEXT DEFAULT '',
            comment TEXT DEFAULT '',
            username TEXT NOT NULL,
            source_ip TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(consumable_id) REFERENCES consumables(id) ON DELETE RESTRICT
        );
        CREATE INDEX IF NOT EXISTS idx_consumable_movements_date ON consumable_movements(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_consumable_movements_item ON consumable_movements(consumable_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            last_login_at TEXT,
            password_changed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS auth_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS site_policies (
            collector TEXT PRIMARY KEY COLLATE NOCASE,
            default_site TEXT NOT NULL DEFAULT 'INCONNU',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS site_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collector TEXT NOT NULL DEFAULT '*',
            network TEXT NOT NULL,
            gateway_network TEXT DEFAULT '',
            result_site TEXT NOT NULL,
            label TEXT DEFAULT '',
            priority INTEGER NOT NULL DEFAULT 100,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_site_rules_collector ON site_rules(collector,enabled,priority DESC);

        CREATE TABLE IF NOT EXISTS user_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            service_name TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS quality_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            service_name TEXT NOT NULL DEFAULT '',
            group_id TEXT NOT NULL DEFAULT '',
            file_id TEXT NOT NULL DEFAULT '',
            anomaly_key TEXT NOT NULL DEFAULT '',
            anomaly_label TEXT NOT NULL DEFAULT '',
            comment TEXT NOT NULL DEFAULT '',
            application_date TEXT,
            status TEXT NOT NULL DEFAULT 'À faire',
            context_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_quality_actions_status_date ON quality_actions(status,application_date,created_at);

        CREATE TABLE IF NOT EXISTS user_group_members (
            user_key TEXT PRIMARY KEY COLLATE NOCASE,
            user_identifier TEXT NOT NULL,
            group_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_group_members_group ON user_group_members(group_id);

        CREATE TABLE IF NOT EXISTS quality_group_campaigns (
            group_id INTEGER NOT NULL,
            campaign_name TEXT NOT NULL COLLATE NOCASE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            PRIMARY KEY(group_id,campaign_name),
            FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_quality_group_campaigns_campaign
            ON quality_group_campaigns(campaign_name,group_id);

        -- F3.9: external supervision IDs are NOT the internal user_groups IDs.
        CREATE TABLE IF NOT EXISTS quality_group_meta (
            group_id INTEGER PRIMARY KEY,
            supervision_id TEXT UNIQUE,
            source_note TEXT NOT NULL DEFAULT 'manual',
            FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS quality_group_lines (
            group_id INTEGER NOT NULL,
            line_id INTEGER NOT NULL CHECK(line_id > 0),
            created_by TEXT,
            PRIMARY KEY(group_id,line_id),
            FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS quality_group_campaign_refs (
            group_id INTEGER NOT NULL,
            campaign_key TEXT NOT NULL,
            campaign_name TEXT NOT NULL DEFAULT '',
            created_by TEXT,
            PRIMARY KEY(group_id,campaign_key),
            FOREIGN KEY(group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user_directory (
            user_key TEXT PRIMARY KEY COLLATE NOCASE,
            user_identifier TEXT NOT NULL,
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS support_agent_exclusions (
            user_key TEXT PRIMARY KEY COLLATE NOCASE,
            user_identifier TEXT NOT NULL,
            reason TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_support_exclusions_identifier ON support_agent_exclusions(user_identifier);

        CREATE TABLE IF NOT EXISTS support_priority_policies (
            priority TEXT PRIMARY KEY,
            rank INTEGER NOT NULL,
            match_mode TEXT NOT NULL DEFAULT 'ANY' CHECK(match_mode IN ('ANY','ALL')),
            disconnects_per_day REAL,
            call_percent REAL,
            affected_days_percent REAL,
            lost_minutes_per_day REAL,
            enabled INTEGER NOT NULL DEFAULT 1,
            color TEXT NOT NULL DEFAULT '#667085',
            is_fallback INTEGER NOT NULL DEFAULT 0,
            conditions_json TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS live_quality_levels (
            level_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            rank INTEGER NOT NULL,
            color TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            is_fallback INTEGER NOT NULL DEFAULT 0 CHECK(is_fallback IN (0,1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE TABLE IF NOT EXISTS live_quality_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            scope_type TEXT NOT NULL DEFAULT 'GLOBAL',
            target_key TEXT NOT NULL DEFAULT '',
            match_mode TEXT NOT NULL DEFAULT 'ANY' CHECK(match_mode IN ('ANY','ALL')),
            level_key TEXT NOT NULL,
            min_duration_seconds INTEGER NOT NULL DEFAULT 0,
            recovery_seconds INTEGER NOT NULL DEFAULT 30,
            cooldown_seconds INTEGER NOT NULL DEFAULT 300,
            min_sample_size INTEGER NOT NULL DEFAULT 0,
            allow_partial INTEGER NOT NULL DEFAULT 0 CHECK(allow_partial IN (0,1)),
            conditions_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            FOREIGN KEY(level_key) REFERENCES live_quality_levels(level_key) ON UPDATE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_live_quality_rules_eval
            ON live_quality_rules(enabled,scope_type,level_key,id);

        -- Phase B: schema-only preparation for the future generic Policies
        -- engine. These tables are intentionally empty and are not consulted by
        -- Support/Analytics/Reports until Phase C enables the policy engine.
        CREATE TABLE IF NOT EXISTS nelyio_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            policy_type TEXT NOT NULL DEFAULT 'AUTRE',
            target_scope TEXT NOT NULL DEFAULT 'GLOBAL' CHECK(target_scope IN ('GLOBAL','GROUP','AGENT','MIXED')),
            date_from TEXT,
            date_to TEXT,
            weekdays_json TEXT NOT NULL DEFAULT '[]',
            time_from TEXT,
            time_to TEXT,
            action_json TEXT NOT NULL DEFAULT '{}',
            modules_json TEXT NOT NULL DEFAULT '[]',
            priority INTEGER NOT NULL DEFAULT 100,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_policies_active
            ON nelyio_policies(enabled,deleted_at,priority DESC,id);
        CREATE INDEX IF NOT EXISTS idx_nelyio_policies_dates
            ON nelyio_policies(date_from,date_to);

        CREATE TABLE IF NOT EXISTS nelyio_policy_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('GLOBAL','GROUP','AGENT')),
            target_key TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(policy_id,target_type,target_key),
            FOREIGN KEY(policy_id) REFERENCES nelyio_policies(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_policy_targets_lookup
            ON nelyio_policy_targets(target_type,target_key,policy_id);

        CREATE TABLE IF NOT EXISTS nelyio_policy_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            policy_id INTEGER,
            action TEXT NOT NULL,
            old_json TEXT DEFAULT '',
            new_json TEXT DEFAULT '',
            actor TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(policy_id) REFERENCES nelyio_policies(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_policy_audit_policy
            ON nelyio_policy_audit(policy_id,created_at DESC);

        -- Phase E: registry for legacy hard-coded exclusion windows migrated
        -- to explicit Policies. It prevents duplicate migrations and keeps a
        -- durable audit link between the old filter and the generated rule.
        CREATE TABLE IF NOT EXISTS nelyio_governance_migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            migration_key TEXT NOT NULL UNIQUE,
            source_kind TEXT NOT NULL DEFAULT 'LEGACY_TIME_EXCLUSION',
            source_json TEXT NOT NULL DEFAULT '{}',
            policy_id INTEGER,
            status TEXT NOT NULL DEFAULT 'MIGRATED' CHECK(status IN ('MIGRATED','REVERTED')),
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reverted_by TEXT,
            reverted_at TEXT,
            FOREIGN KEY(policy_id) REFERENCES nelyio_policies(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_governance_migrations_policy
            ON nelyio_governance_migrations(policy_id,status,created_at DESC);

        -- Phase D: punctual declarations made by team leads/responsables.
        -- They never delete raw technical evidence; they are evaluated after
        -- generic Policies and only change how a matching event is interpreted.
        CREATE TABLE IF NOT EXISTS nelyio_declarations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            declaration_type TEXT NOT NULL DEFAULT 'AUTRE',
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','CANCELLED')),
            start_at TEXT NOT NULL,
            end_at TEXT NOT NULL,
            action_json TEXT NOT NULL DEFAULT '{}',
            comment TEXT DEFAULT '',
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            cancelled_by TEXT,
            cancelled_at TEXT,
            deleted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_declarations_window
            ON nelyio_declarations(status,deleted_at,start_at,end_at);
        CREATE INDEX IF NOT EXISTS idx_nelyio_declarations_created
            ON nelyio_declarations(created_at DESC,id DESC);

        CREATE TABLE IF NOT EXISTS nelyio_declaration_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            declaration_id INTEGER NOT NULL,
            target_type TEXT NOT NULL CHECK(target_type IN ('GROUP','AGENT')),
            target_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(declaration_id,target_type,target_key),
            FOREIGN KEY(declaration_id) REFERENCES nelyio_declarations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_declaration_targets_lookup
            ON nelyio_declaration_targets(target_type,target_key,declaration_id);

        CREATE TABLE IF NOT EXISTS nelyio_declaration_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            declaration_id INTEGER,
            action TEXT NOT NULL,
            old_json TEXT DEFAULT '',
            new_json TEXT DEFAULT '',
            actor TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(declaration_id) REFERENCES nelyio_declarations(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_nelyio_declaration_audit_decl
            ON nelyio_declaration_audit(declaration_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS retention_legal_holds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_day TEXT NOT NULL,
            end_day TEXT NOT NULL,
            reason TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            reevaluate_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_retention_holds_range ON retention_legal_holds(active,start_day,end_day);

        CREATE TABLE IF NOT EXISTS retention_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            actor TEXT,
            summary_json TEXT,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_retention_runs_time ON retention_runs(id DESC);

        CREATE TABLE IF NOT EXISTS access_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS access_group_members (
            user_id INTEGER PRIMARY KEY,
            group_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(group_id) REFERENCES access_groups(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_access_members_group ON access_group_members(group_id);

        CREATE TABLE IF NOT EXISTS access_group_permissions (
            group_id INTEGER NOT NULL,
            module TEXT NOT NULL,
            access_level INTEGER NOT NULL DEFAULT 0 CHECK(access_level BETWEEN 0 AND 2),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            PRIMARY KEY(group_id,module),
            FOREIGN KEY(group_id) REFERENCES access_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS access_group_interface_permissions (
            group_id INTEGER NOT NULL,
            interface_key TEXT NOT NULL,
            access_level INTEGER NOT NULL DEFAULT 0 CHECK(access_level BETWEEN 0 AND 2),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            PRIMARY KEY(group_id,interface_key),
            FOREIGN KEY(group_id) REFERENCES access_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS access_group_scope_policy (
            group_id INTEGER PRIMARY KEY,
            scope_mode TEXT NOT NULL DEFAULT 'ALL' CHECK(scope_mode IN ('ALL','SELECTED')),
            default_business_group_id INTEGER,
            filter_locked INTEGER NOT NULL DEFAULT 0 CHECK(filter_locked IN (0,1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT,
            FOREIGN KEY(group_id) REFERENCES access_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(default_business_group_id) REFERENCES user_groups(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS access_group_scopes (
            access_group_id INTEGER NOT NULL,
            business_group_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            PRIMARY KEY(access_group_id,business_group_id),
            FOREIGN KEY(access_group_id) REFERENCES access_groups(id) ON DELETE CASCADE,
            FOREIGN KEY(business_group_id) REFERENCES user_groups(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_access_group_scopes_business ON access_group_scopes(business_group_id,access_group_id);

        CREATE TABLE IF NOT EXISTS access_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );

        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            actor TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            source_rows INTEGER DEFAULT 0,
            imported_rows INTEGER DEFAULT 0,
            skipped_rows INTEGER DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            error TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_import_log_date ON import_log(started_at DESC);

        CREATE TABLE IF NOT EXISTS import_sources (
            path TEXT PRIMARY KEY,
            last_source_id INTEGER NOT NULL DEFAULT 0,
            last_source_rows INTEGER NOT NULL DEFAULT 0,
            last_seen_at TEXT,
            last_imported_at TEXT
        );
        """)
        # Migrations légères pour les bases provenant des versions précédentes.
        group_cols = {r[1] for r in con.execute("PRAGMA table_info(user_groups)").fetchall()}
        if "service_name" not in group_cols:
            con.execute("ALTER TABLE user_groups ADD COLUMN service_name TEXT NOT NULL DEFAULT ''")

        rule_cols = {r[1] for r in con.execute("PRAGMA table_info(site_rules)").fetchall()}
        if "gateway_network" not in rule_cols:
            con.execute("ALTER TABLE site_rules ADD COLUMN gateway_network TEXT DEFAULT ''")

        user_cols = {r[1] for r in con.execute("PRAGMA table_info(users)").fetchall()}
        if "failed_login_count" not in user_cols:
            con.execute("ALTER TABLE users ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0")
        if "last_failed_at" not in user_cols:
            con.execute("ALTER TABLE users ADD COLUMN last_failed_at TEXT")
        if "lock_until" not in user_cols:
            con.execute("ALTER TABLE users ADD COLUMN lock_until TEXT")
        # Ancien rôle v7: user = technicien.
        con.execute("UPDATE users SET role='technician' WHERE role='user'")

        session_cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)").fetchall()}
        if "csrf_token" not in session_cols:
            con.execute("ALTER TABLE sessions ADD COLUMN csrf_token TEXT DEFAULT ''")
        if "last_seen_at" not in session_cols:
            con.execute("ALTER TABLE sessions ADD COLUMN last_seen_at TEXT")

        auth_cols = {r[1] for r in con.execute("PRAGMA table_info(auth_audit)").fetchall()}
        if "source_ip" not in auth_cols:
            con.execute("ALTER TABLE auth_audit ADD COLUMN source_ip TEXT DEFAULT ''")

        manual_cols = {r[1] for r in con.execute("PRAGMA table_info(manual_audit)").fetchall()}
        if "source_ip" not in manual_cols:
            con.execute("ALTER TABLE manual_audit ADD COLUMN source_ip TEXT DEFAULT ''")

        # v40 - moteur de priorités Support libre : nom, couleur, fallback et
        # conditions génériques. Les anciennes colonnes de seuil restent pour
        # importer les configurations v38 sans perte.
        priority_cols = {r[1] for r in con.execute("PRAGMA table_info(support_priority_policies)").fetchall()}
        added_priority_color = "color" not in priority_cols
        added_priority_fallback = "is_fallback" not in priority_cols
        if added_priority_color:
            con.execute("ALTER TABLE support_priority_policies ADD COLUMN color TEXT NOT NULL DEFAULT '#667085'")
        if added_priority_fallback:
            con.execute("ALTER TABLE support_priority_policies ADD COLUMN is_fallback INTEGER NOT NULL DEFAULT 0")
        if "conditions_json" not in priority_cols:
            con.execute("ALTER TABLE support_priority_policies ADD COLUMN conditions_json TEXT NOT NULL DEFAULT ''")
        if added_priority_color:
            con.execute("UPDATE support_priority_policies SET color='#B42318' WHERE priority='CRITIQUE'")
            con.execute("UPDATE support_priority_policies SET color='#B54708' WHERE priority='ÉLEVÉE'")
            con.execute("UPDATE support_priority_policies SET color='#4A58A3' WHERE priority='MODÉRÉE'")
            con.execute("UPDATE support_priority_policies SET color='#24634A' WHERE priority='FAIBLE'")
        if added_priority_fallback:
            con.execute("UPDATE support_priority_policies SET is_fallback=CASE WHEN priority='FAIBLE' THEN 1 ELSE 0 END")

        defaults = {
            "diagnostic_source_path": "",
            "web_host": cfg.DEFAULT_HOST,
            "web_port": str(cfg.DEFAULT_PORT),
            "auto_import_enabled": "0",
            "auto_import_minutes": "5",
            "last_import_at": "",
            "last_import_count": "0",
            "last_import_error": "",
            "tls_enabled": "0",
            "tls_cert_path": "",
            "tls_key_path": "",
            "public_hostname": "stock-manager.nelyio.local",
            "retention_enabled": "0",
            "retention_archive_dir": "archives",
            "retention_backup_dir": "backups/retention",
            "retention_operational_months": "6",
            "retention_details_months": "12",
            "retention_archive_months": "24",
            "retention_aggregate_months": "36",
            "retention_security_months": "12",
            "retention_health_days": "30",
            "inventory_followup_warning_days": "7",
            "inventory_followup_late_days": "20",
            "inventory_followup_override_stock": "1",
            "inventory_followup_override_repair": "1",
            "inventory_followup_override_lost": "1",
            "inventory_followup_override_retired": "1",
            "governance_legacy_exclusion_mode": "compat",
            "governance_legacy_exclusion_migrated_at": "",
            "governance_legacy_exclusion_migrated_by": "",
            "inventory_followup_labels": json.dumps({
                "EN_SERVICE": "À jour", "PAS_A_JOUR": "Pas à jour", "RETARD_7J": "Retard",
                "CRITIQUE": "Critique", "STOCK": "En stock", "REPARATION": "Réparation",
                "KO": "KO / perdu", "REFORME": "Réformé"
            }, ensure_ascii=False, separators=(",", ":")),
            SCORE_SETTING_KEY: json.dumps(DEFAULT_SCORE_CONFIG, ensure_ascii=False, separators=(",", ":")),
        }
        for k, v in defaults.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value,updated_by) VALUES(?,?,?)", (k, v, "SYSTEM"))
        for collector, default_site in (("DC1", "SUR SITE"), ("DC2", "TELETRAVAIL"), ("*", "INCONNU")):
            con.execute("INSERT OR IGNORE INTO site_policies(collector,default_site,updated_by) VALUES(?,?,?)", (collector, default_site, "SYSTEM"))

        # Priorités Support initiales. Elles restent entièrement modifiables :
        # l'administrateur peut les renommer, les supprimer, en ajouter et
        # choisir un autre niveau de repli.
        priority_defaults = [
            ("CRITIQUE", 500, "ANY", None, None, None, None, "#B42318", 0,
             '[{"metric":"technical_score","operator":">=","value":30.0}]'),
            ("ÉLEVÉE", 400, "ANY", None, None, None, None, "#B54708", 0,
             '[{"metric":"technical_score","operator":">=","value":18.0}]'),
            ("À INVESTIGUER", 300, "ANY", None, None, None, None, "#A56A00", 0,
             '[{"metric":"technical_score","operator":">=","value":10.0}]'),
            ("SURVEILLANCE", 200, "ANY", None, None, None, None, "#4A58A3", 0,
             '[{"metric":"technical_score","operator":">=","value":5.0}]'),
            ("NORMAL", 100, "ANY", None, None, None, None, "#24634A", 1, '[]'),
        ]

        # v41: migrate only the exact v40 data-driven default policy.  Any
        # administrator-customized policy is preserved verbatim.
        current_priority_rows = con.execute(
            "SELECT priority,is_fallback,conditions_json FROM support_priority_policies ORDER BY priority"
        ).fetchall()
        current_names = {r["priority"] for r in current_priority_rows}
        v40_names = {"CRITIQUE", "ÉLEVÉE", "SURVEILLANCE", "FAIBLE"}
        v40_markers = {
            "CRITIQUE": {("disconnects_per_affected_day", 20.0), ("disconnects_during_call_per_affected_day", 2.5)},
            "ÉLEVÉE": {("disconnects_per_affected_day", 8.0), ("disconnects_during_call_per_affected_day", 1.5)},
            "SURVEILLANCE": {("disconnects_per_affected_day", 4.0), ("disconnects_during_call_per_affected_day", 1.0)},
        }
        looks_like_v40_default = current_names == v40_names
        if looks_like_v40_default:
            for row in current_priority_rows:
                if row["priority"] == "FAIBLE":
                    looks_like_v40_default = bool(row["is_fallback"])
                    continue
                try:
                    parsed = json.loads(row["conditions_json"] or "[]")
                    marker = {(str(x.get("metric")), float(x.get("value"))) for x in parsed}
                except (TypeError, ValueError, json.JSONDecodeError):
                    looks_like_v40_default = False
                    break
                if marker != v40_markers.get(row["priority"], set()):
                    looks_like_v40_default = False
                    break
        if looks_like_v40_default:
            con.execute("DELETE FROM support_priority_policies")

        # Seed only an empty policy table. Once an administrator customizes the
        # list, a later restart must never recreate a renamed/deleted default.
        if con.execute("SELECT COUNT(*) FROM support_priority_policies").fetchone()[0] == 0:
            con.executemany("""
                INSERT INTO support_priority_policies(
                    priority,rank,match_mode,disconnects_per_day,call_percent,
                    affected_days_percent,lost_minutes_per_day,color,is_fallback,enabled,conditions_json,updated_by
                ) VALUES(?,?,?,?,?,?,?,?,?,1,?,'SYSTEM')
            """, priority_defaults)
        # Une base migrée très ancienne peut ne pas avoir FAIBLE. Garantir un
        # seul fallback sans réintroduire les niveaux que l'administrateur a
        # volontairement supprimés.
        if con.execute("SELECT COUNT(*) FROM support_priority_policies WHERE is_fallback=1").fetchone()[0] == 0:
            row = con.execute("SELECT priority FROM support_priority_policies ORDER BY rank ASC LIMIT 1").fetchone()
            if row:
                con.execute("UPDATE support_priority_policies SET is_fallback=1,enabled=1 WHERE priority=?", (row[0],))

        # Groupes d'accès par défaut : ils préservent le comportement des anciens rôles.
        default_access = {
            "Techniciens": _legacy_permissions("technician"),
            "Lecture seule": _legacy_permissions("viewer"),
        }
        for group_name, permissions in default_access.items():
            con.execute("INSERT OR IGNORE INTO access_groups(name,description,created_by,updated_by) VALUES(?,?,?,?)",
                        (group_name, "Groupe d'accès créé automatiquement lors de la migration", "SYSTEM", "SYSTEM"))
            gid = con.execute("SELECT id FROM access_groups WHERE name=? COLLATE NOCASE", (group_name,)).fetchone()[0]
            for module, level in permissions.items():
                con.execute("INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by) VALUES(?,?,?,?)",
                            (gid, module, level, "SYSTEM"))
        # Nouvelle interface Comparaisons : lors de la migration, elle hérite une fois
        # du droit de lecture Support de chaque groupe existant. L'administrateur peut
        # ensuite la désactiver indépendamment depuis Utilisateurs & accès.
        con.execute("""
            INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by)
            SELECT group_id,'analytics',CASE WHEN access_level>0 THEN 1 ELSE 0 END,'SYSTEM'
            FROM access_group_permissions WHERE module='support'
        """)
        # Nouvelle interface Détails : elle hérite une fois du droit de lecture Support.
        # Elle reste ensuite configurable indépendamment dans Utilisateurs & accès.
        con.execute("""
            INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by)
            SELECT group_id,'details',CASE WHEN access_level>0 THEN 1 ELSE 0 END,'SYSTEM'
            FROM access_group_permissions WHERE module='support'
        """)
        # Confidentialité ANI - les groupes existants conservent une fois leur
        # capacité historique à voir les numéros, puis ce droit devient
        # indépendant de Recherche d'appels dans Utilisateurs & accès.
        con.execute("""
            INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by)
            SELECT group_id,'ani',CASE WHEN access_level>0 THEN 1 ELSE 0 END,'SYSTEM'
            FROM access_group_permissions WHERE module='calls'
        """)
        # v49 - Consommables hérite une fois des droits Gestion du parc, puis devient indépendant.
        con.execute("""
            INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by)
            SELECT group_id,'consumables',access_level,'SYSTEM'
            FROM access_group_permissions WHERE module='inventory'
        """)
        # Phase D - Déclarations hérite une fois du niveau Support. Les responsables
        # peuvent ensuite recevoir un droit lecture ou modification indépendant.
        con.execute("""
            INSERT OR IGNORE INTO access_group_permissions(group_id,module,access_level,updated_by)
            SELECT group_id,'declarations',access_level,'SYSTEM'
            FROM access_group_permissions WHERE module='support'
        """)
        # Phase 12 - permissions fines par interface. Les groupes existants héritent
        # une seule fois de leur ancien droit de module afin de conserver le comportement
        # avant migration. L'administrateur peut ensuite restreindre chaque interface.
        for access_row in con.execute("SELECT id FROM access_groups").fetchall():
            gid = int(access_row[0])
            module_levels = {
                str(r["module"]): int(r["access_level"] or 0)
                for r in con.execute("SELECT module,access_level FROM access_group_permissions WHERE group_id=?", (gid,)).fetchall()
            }
            for interface_key, meta in cfg.ACCESS_INTERFACES.items():
                level = int(module_levels.get(str(meta.get("module") or ""), 0))
                if meta.get("write_only"):
                    level = cfg.ACCESS_WRITE if level >= cfg.ACCESS_WRITE else cfg.ACCESS_NONE
                elif not meta.get("write") and level > cfg.ACCESS_READ:
                    level = cfg.ACCESS_READ
                con.execute(
                    "INSERT OR IGNORE INTO access_group_interface_permissions(group_id,interface_key,access_level,updated_by) VALUES(?,?,?,?)",
                    (gid, interface_key, level, "SYSTEM"),
                )
            con.execute(
                "INSERT OR IGNORE INTO access_group_scope_policy(group_id,scope_mode,default_business_group_id,filter_locked,updated_by) VALUES(?,'ALL',NULL,0,?)",
                (gid, "SYSTEM"),
            )

        tech_gid = con.execute("SELECT id FROM access_groups WHERE name='Techniciens' COLLATE NOCASE").fetchone()[0]
        read_gid = con.execute("SELECT id FROM access_groups WHERE name='Lecture seule' COLLATE NOCASE").fetchone()[0]
        for u in con.execute("SELECT id,role FROM users WHERE role<>'admin'").fetchall():
            gid = tech_gid if ("technician" if u["role"] == "user" else u["role"]) == "technician" else read_gid
            con.execute("INSERT OR IGNORE INTO access_group_members(user_id,group_id,created_by) VALUES(?,?,?)", (u["id"], gid, "SYSTEM"))
        con.commit()
