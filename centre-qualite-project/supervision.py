"""Nelyio supervision: authoritative daily exports and provisional capture.
Standard library only; independent SQLite database, existing app authentication.
"""
from error_log import log_unexpected_error
from pathlib import Path
from datetime import datetime, timedelta, timezone
import csv, io, json, hashlib
import db_compat as sqlite3, html, zipfile, secrets, hmac, re, math, threading, time
from collections import Counter
from contextlib import contextmanager
import details_store
from nelyio_time import (
    DISPLAY_TIMEZONE, day_bounds as france_day_bounds, display as france_display,
    france_offset_for_day, france_offset_for_utc_timestamp,
    local_datetime as france_local_datetime, local_day as france_local_day,
    today as france_today,
)
import weekly_reports
from supervision_db import (DEFAULTS, connect, _reference_day_from_name, _local_day_from_stamp,
    _dominant_import_day, _reference_day_for_import, migrate_reference_days,
    repair_reference_coverage, init, config, now, audit, save_config)
from agent_directory import (normalize_admin_key, admin_key_candidates, load_admin_directory,
    admin_user_for, admin_name_for, admin_group_for, canonical_admin_key,
    support_directory_candidates, sync_admin_groups_from_export, _split_support_name,
    sync_admin_directory_from_support, support_agent_is_excluded)
from supervision_utils import (kind, stamp, display, day_bounds, selected_bounds, union_seconds,
    classify_anomaly, date_range, period_buckets, archive_csv)
from support_filters import (TECH_LABELS, MAX_NORMAL_DISCONNECT_SECONDS, _minute_label,
    _parse_excluded_time, _support_excluded_slots, _local_minute_of_day, _in_support_excluded_slot,
    _overlaps_support_excluded_slot, valid_gap_key)
from export_import import read_export, import_export, parse_phone_calls, store_phone_calls
from auto_import import (automatic_import_offset, _auto_import_log, auto_import_status, _is_auto_import_file,
    process_auto_import_file, scan_auto_import_folder, _auto_import_loop, start_auto_importer, stop_auto_importer)
from live_capture import ingest, live_intervals, record_technical_signal
from calls import call_rows, attach_notes, calls_view
from disconnects import _merge_disconnect_intervals, detect_clusters, data_integrity, disconnect_statistics
from support_views import chart_data, view, add_note, support_view
from analytics import (_analytics_days, _analytics_delta, _analytics_is_inactive_state,
    _analytics_latest_devices, _analytics_clusters, _analytics_collect_period, analytics_view)
from report_data import (_report_get, _report_values, _report_bool, _report_week, _report_period,
    _report_dataset, _report_delta_status, _report_comparison, _report_overview, _report_scope_accept,
    _report_collect_signals, _report_build_agent_profiles, _report_score_agents, _report_agent_comparison,
    _weekly_report_data, weekly_report_preview, weekly_report_details, weekly_report_pdf)
from supervision_routes import _access, get_route, post_route, bridge_route, details_view

DB = Path(__file__).with_name('NELYIO_Supervision.db')
ADMIN_DB = Path(__file__).with_name('TECHIN_Stock_Manager.db')
IMPORT_DIR = Path(__file__).with_name('import')
AUTO_IMPORT_SCAN_SECONDS = 10
AUTO_IMPORT_MIN_AGE_SECONDS = 3
AUTO_IMPORT_STOP = threading.Event()
AUTO_IMPORT_THREAD = None
IMPORT_LOCK = threading.Lock()
_AUTO_IMPORT_ERROR_SIGNATURES = {}
# export_offset is explicitly selected/confirmed by the importer, never guessed.


















































# ---- Technical support and exported call detail --------------------------------


































































init()
