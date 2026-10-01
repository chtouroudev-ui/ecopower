"""Facade historique : compose les six domaines sans redefinir leurs methodes."""
from group_workspace import export_group_links, validate_group_links, restore_group_links
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re
import db_compat as sqlite3

import app_config as cfg
import runtime
import supervision
import retention_service
from app_db import db_connect, get_setting, now_text, set_setting
from classification import classify_site_details, normalize_user_key, parse_ip_selector, refresh_classification_cache
from diagnostic_import import import_diagnostic_source, source_schema_info
from error_log import log_unexpected_error
from inventory_service import rows_to_dict, followup_config, DEFAULT_FOLLOWUP_LABELS
from support_priority import (
    COLOR_RE, LEGACY_FIELDS, legacy_thresholds_from_conditions, load_priority_policies,
    metric_catalog, public_policy_snapshot, validate_conditions,
)
from policy_admin import save_policy, set_enabled as set_policy_enabled, delete_policy, list_audit
from policy_engine import policy_snapshot
from governance_migration import migration_status, migrate_legacy_exclusions, set_legacy_mode
from declaration_admin import save_declaration, cancel_declaration, delete_declaration, list_audit as list_declaration_audit
from declaration_engine import declaration_snapshot, DECLARATION_TYPES, DEFAULT_ACTIONS
from quality_service import load_quality_priorities
from support_scoring import (
    SCORE_SETTING_KEY, load_score_config, public_score_config, validate_score_config,
)

ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_READ = cfg.ACCESS_READ
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
from routes_admin_access import AdminAccessRoutesMixin
from routes_admin_governance import AdminGovernanceRoutesMixin
from routes_admin_support import AdminSupportRoutesMixin
from routes_admin_directory import AdminDirectoryRoutesMixin
from routes_admin_config import AdminConfigRoutesMixin
from routes_admin_retention import AdminRetentionRoutesMixin


class AdminRoutesMixin(
    AdminAccessRoutesMixin,
    AdminGovernanceRoutesMixin,
    AdminSupportRoutesMixin,
    AdminDirectoryRoutesMixin,
    AdminConfigRoutesMixin,
    AdminRetentionRoutesMixin,
):
    """Point d'entree compatible, egalement utilise par le Handler HTTP."""

    pass
