"""Configurable, explainable Live-quality signalling for Nelyio.

Phase 2 principles:
- no second database: administrator configuration stays in the existing APP DB;
- runtime signal/incident state stays in the existing Nelyio_Live.db spool;
- a missing/unproven metric is never coerced to zero;
- rules are explainable (metric/operator/threshold + observed values);
- anti-noise is durable (minimum duration, recovery hysteresis, cooldown);
- one rule + one scope produces at most one active incident.

This module intentionally does *not* invent Hermes queue semantics. Waiting,
QoS and P90 metrics are exposed in the catalogue but remain unavailable until a
source is certified by a later phase.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
import time
import uuid
import unicodedata

from app_db import db_connect

COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
OPERATORS = (">", ">=", "<", "<=", "==", "!=")
MATCH_MODES = ("ANY", "ALL")
SCOPE_TYPES = ("GLOBAL", "SERVICE", "GROUP", "CAMPAIGN", "QUEUE", "AGENT")
INCIDENT_STATUSES = ("NOUVEAU", "VU", "EN_INVESTIGATION", "ACTION_EN_COURS", "RETABLI", "CLOTURE")
INCIDENT_HISTORY_RETENTION_DAYS = 90
_LAST_RETENTION_PURGE_DAY = None
INCIDENT_CATEGORY_LABELS = {
    "post_call": "Post-appel / Post-travail",
    "hold_early": "Mise en attente précoce",
    "hold": "Mise en attente / HOLD",
    "pause_lunch": "Pause déjeuner",
    "pause_coaching": "Coaching",
    "pause_general": "General Break",
    "pause": "Pause",
    "offline": "Déconnexion",
    "inactive_context": "Contexte inactif",
    "other": "Autres",
}
INCIDENT_CATEGORY_ORDER = tuple(INCIDENT_CATEGORY_LABELS)
INCIDENT_STATUS_LABELS = {
    "NOUVEAU": "NOUVEAU",
    "VU": "VU",
    "EN_INVESTIGATION": "EN INVESTIGATION",
    "ACTION_EN_COURS": "ACTION EN COURS",
    "RETABLI": "RÉTABLI",
    "CLOTURE": "CLÔTURÉ",
}
INCIDENT_FORWARD_TRANSITIONS = {
    "NOUVEAU": ("VU", "EN_INVESTIGATION", "ACTION_EN_COURS"),
    "VU": ("EN_INVESTIGATION", "ACTION_EN_COURS"),
    "EN_INVESTIGATION": ("ACTION_EN_COURS",),
    "ACTION_EN_COURS": (),
    "RETABLI": ("CLOTURE",),
    "CLOTURE": (),
}

# Metrics which can be evaluated from the current RC12 Live snapshot now.
# Future/certification-gated metrics deliberately remain in the catalogue so the
# Administration UI can explain why a rule is inactive instead of hiding it.
METRICS = {
    "agents_known": {"label": "Agents connus", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_connected": {"label": "Agents connectés", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_available": {"label": "Agents disponibles", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_in_call": {"label": "Agents en appel (mise en attente incluse)", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_on_hold": {"label": "Agents en mise en attente explicite", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_wrap": {"label": "Agents en post-appel", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_pause": {"label": "Agents en pause", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_pause_normal": {"label": "Agents en pause normale", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_pause_lunch": {"label": "Agents en pause déjeuner", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_pause_coaching": {"label": "Agents en coaching", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_pause_general": {"label": "Agents en General Break", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_inactive_context": {"label": "Agents en contexte inactif explicite", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "agents_offline": {"label": "Agents déconnectés", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "available_percent": {"label": "% agents disponibles / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "in_call_percent": {"label": "% agents en appel / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "hold_percent": {"label": "% agents en mise en attente explicite / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "wrap_percent": {"label": "% agents en post-appel / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "pause_percent": {"label": "% agents en pause / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "inactive_context_percent": {"label": "% agents en contexte inactif explicite / connectés", "unit": "%", "min": 0, "max": 100, "availability": "live"},
    "current_calls": {"label": "Appels actuellement observés", "unit": "", "min": 0, "max": 100000, "availability": "live"},
    "max_state_age_seconds": {"label": "État agent le plus ancien", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_wrap_seconds": {"label": "Post-appel le plus long", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_pause_seconds": {"label": "Pause la plus longue", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_pause_normal_seconds": {"label": "Pause normale la plus longue", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_pause_lunch_seconds": {"label": "Pause déjeuner la plus longue", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_pause_coaching_seconds": {"label": "Coaching le plus long", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_pause_general_seconds": {"label": "General Break le plus long", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_inactive_context_seconds": {"label": "Contexte inactif explicite le plus long", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_hold_seconds": {"label": "Mise en attente explicite la plus longue", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "earliest_hold_start_seconds": {"label": "Début de la première mise en attente dans l’appel", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "max_offline_seconds": {"label": "Déconnexion la plus longue", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    "freshness_seconds": {"label": "Âge de la dernière donnée Hermes", "unit": "s", "min": 0, "max": 604800, "availability": "live"},
    # Certification-gated metrics. These are never synthesized from undocumented
    # arg_n counters or from an unrelated historical source.
    "waiting_now": {"label": "Appels actuellement en attente", "unit": "", "min": 0, "max": 100000, "availability": "certification_required"},
    "oldest_waiting_seconds": {"label": "Plus ancienne attente", "unit": "s", "min": 0, "max": 604800, "availability": "certification_required"},
    "median_wait_seconds": {"label": "Attente médiane Live", "unit": "s", "min": 0, "max": 604800, "availability": "certification_required"},
    "p90_wait_seconds": {"label": "P90 attente Live", "unit": "s", "min": 0, "max": 604800, "availability": "certification_required"},
    "abandon_rate": {"label": "Taux d'abandon Live", "unit": "%", "min": 0, "max": 100, "availability": "certification_required"},
    "qos": {"label": "QoS Live", "unit": "%", "min": 0, "max": 100, "availability": "certification_required"},
}

DEFAULT_LEVELS = [
    {"level_key": "CRITIQUE", "label": "CRITIQUE", "rank": 400, "color": "#B42318", "enabled": 1, "is_fallback": 0},
    {"level_key": "DEGRADE", "label": "DÉGRADÉ", "rank": 300, "color": "#B54708", "enabled": 1, "is_fallback": 0},
    {"level_key": "SURVEILLANCE", "label": "À SURVEILLER", "rank": 200, "color": "#A56A00", "enabled": 1, "is_fallback": 0},
    {"level_key": "NORMAL", "label": "NORMAL", "rank": 100, "color": "#24634A", "enabled": 1, "is_fallback": 1},
]

# Phase 3 guided presets. They are templates only: exposing them in the UI does
# not silently create rules in an existing installation. Thresholds remain
# editable before save.
RULE_PRESETS = [
    {"key":"pause_longue","name":"Pause longue","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":60,"recovery_seconds":30,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_pause","operator":">=","value":1},{"metric":"max_pause_seconds","operator":">=","value":600}]},
    {"key":"post_appel_long","name":"Post-appel long","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":60,"recovery_seconds":30,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_wrap","operator":">=","value":1},{"metric":"max_wrap_seconds","operator":">=","value":300}]},
    {"key":"contexte_inactif_long","name":"Contexte inactif long","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":60,"recovery_seconds":30,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_inactive_context","operator":">=","value":1},{"metric":"max_inactive_context_seconds","operator":">=","value":300}]},
    {"key":"deconnexion_prolongee","name":"Déconnexion prolongée","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":120,"recovery_seconds":60,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_offline","operator":">=","value":1},{"metric":"max_offline_seconds","operator":">=","value":600}]},
    {"key":"aucun_disponible","name":"Aucun disponible","scope_type":"GROUP","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":120,"recovery_seconds":60,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_connected","operator":">=","value":1},{"metric":"agents_available","operator":"<=","value":0}]},
    {"key":"trop_agents_pause","name":"Trop d’agents en pause","scope_type":"GROUP","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":120,"recovery_seconds":60,"cooldown_seconds":300,"min_sample_size":3,"allow_partial":0,"conditions":[{"metric":"agents_pause","operator":">=","value":2},{"metric":"pause_percent","operator":">=","value":40}]},
    {"key":"trop_agents_contexte_inactif","name":"Trop d’agents en contexte inactif","scope_type":"GROUP","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":120,"recovery_seconds":60,"cooldown_seconds":300,"min_sample_size":3,"allow_partial":0,"conditions":[{"metric":"agents_inactive_context","operator":">=","value":2},{"metric":"inactive_context_percent","operator":">=","value":40}]},
]

# FIX4 presets: they are opt-in templates. Administrators keep full control over
# thresholds and level/colors before saving the rule.
RULE_PRESETS.extend([
    {"key":"post_appel_surveillance_10s","name":"Post-appel · surveillance 10 s","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":0,"recovery_seconds":2,"cooldown_seconds":30,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_wrap","operator":">=","value":1},{"metric":"max_wrap_seconds","operator":">=","value":10}]},
    {"key":"post_appel_alerte_15s","name":"Post-appel · alerte 15 s","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":0,"recovery_seconds":2,"cooldown_seconds":30,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_wrap","operator":">=","value":1},{"metric":"max_wrap_seconds","operator":">=","value":15}]},
    {"key":"post_appel_critique_25s","name":"Post-appel · critique >25 s","scope_type":"AGENT","match_mode":"ALL","level_key":"CRITIQUE","min_duration_seconds":0,"recovery_seconds":2,"cooldown_seconds":30,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_wrap","operator":">=","value":1},{"metric":"max_wrap_seconds","operator":">","value":25}]},
    {"key":"pause_normale_longue","name":"Pause normale longue","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":0,"recovery_seconds":10,"cooldown_seconds":120,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_pause_normal","operator":">=","value":1},{"metric":"max_pause_normal_seconds","operator":">=","value":600}]},
    {"key":"pause_dejeuner_plus_1h","name":"Pause déjeuner > 1 h","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":0,"recovery_seconds":10,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_pause_lunch","operator":">=","value":1},{"metric":"max_pause_lunch_seconds","operator":">","value":3600}]},
    {"key":"coaching_long","name":"Coaching long","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":0,"recovery_seconds":10,"cooldown_seconds":180,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_pause_coaching","operator":">=","value":1},{"metric":"max_pause_coaching_seconds","operator":">=","value":1800}]},
    {"key":"general_break_long","name":"General Break long","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":0,"recovery_seconds":10,"cooldown_seconds":180,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_pause_general","operator":">=","value":1},{"metric":"max_pause_general_seconds","operator":">=","value":600}]},
    {"key":"hold_long","name":"Mise en attente / HOLD longue","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":0,"recovery_seconds":5,"cooldown_seconds":120,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_on_hold","operator":">=","value":1},{"metric":"max_hold_seconds","operator":">=","value":30}]},
    {"key":"hold_precoce_10s","name":"Mise en attente dans les 10 premières secondes","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":0,"recovery_seconds":5,"cooldown_seconds":120,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"earliest_hold_start_seconds","operator":"<=","value":10}]},
    {"key":"deconnexion_plus_10min","name":"Déconnexion > 10 min","scope_type":"AGENT","match_mode":"ALL","level_key":"DEGRADE","min_duration_seconds":0,"recovery_seconds":20,"cooldown_seconds":300,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_offline","operator":">=","value":1},{"metric":"max_offline_seconds","operator":">","value":600}]},
    {"key":"contexte_inactif_long_fix4","name":"Contexte inactif long","scope_type":"AGENT","match_mode":"ALL","level_key":"SURVEILLANCE","min_duration_seconds":0,"recovery_seconds":10,"cooldown_seconds":180,"min_sample_size":1,"allow_partial":0,"conditions":[{"metric":"agents_inactive_context","operator":">=","value":1},{"metric":"max_inactive_context_seconds","operator":">=","value":300}]},
])

# Conservative defaults: only signals already grounded in RC12 Live facts.
# Service-quality rules (P90/QoS/waiting) are not seeded before certification.
DEFAULT_RULES = [
    {
        "name": "Aucun agent disponible",
        "enabled": 1,
        "scope_type": "CAMPAIGN",
        "target_key": "",
        "match_mode": "ALL",
        "level_key": "DEGRADE",
        "min_duration_seconds": 120,
        "recovery_seconds": 60,
        "cooldown_seconds": 300,
        "min_sample_size": 1,
        "allow_partial": 0,
        "conditions": [
            {"metric": "agents_connected", "operator": ">=", "value": 1},
            {"metric": "agents_available", "operator": "<=", "value": 0},
        ],
    },
    {
        "name": "Post-appel prolongé",
        "enabled": 1,
        "scope_type": "AGENT",
        "target_key": "",
        "match_mode": "ALL",
        "level_key": "SURVEILLANCE",
        "min_duration_seconds": 60,
        "recovery_seconds": 30,
        "cooldown_seconds": 300,
        "min_sample_size": 1,
        "allow_partial": 0,
        "conditions": [
            {"metric": "agents_wrap", "operator": ">=", "value": 1},
            {"metric": "max_wrap_seconds", "operator": ">=", "value": 300},
        ],
    },
]


def metric_catalog():
    return [dict(key=k, **v) for k, v in METRICS.items()]


def _as_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off", "no", "non"}
    return bool(value)


def _clean_level_key(value):
    key = re.sub(r"[^A-Z0-9_]+", "_", str(value or "").strip().upper()).strip("_")
    if not key or len(key) > 40:
        raise ValueError("Identifiant de niveau invalide")
    return key


def _clean_label(value, field="Libellé"):
    text = " ".join(str(value or "").split()).strip()
    if not text or len(text) > 80:
        raise ValueError(f"{field} invalide")
    return text


def _color(value):
    c = str(value or "").strip().upper()
    if not COLOR_RE.fullmatch(c):
        raise ValueError("Couleur invalide (format #RRGGBB)")
    return c


def _number(value, *, lo, hi, field, integer=False):
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} invalide") from exc
    if not math.isfinite(n) or n < lo or n > hi:
        raise ValueError(f"{field} hors limites")
    return int(round(n)) if integer else n


def validate_conditions(raw, *, allow_empty=False):
    if raw is None:
        raw = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Conditions Qualité Live invalides") from exc
    if not isinstance(raw, list):
        raise ValueError("Conditions Qualité Live invalides")
    if len(raw) > 24:
        raise ValueError("Maximum 24 conditions par règle Live")
    out = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Condition Qualité Live invalide")
        metric = str(item.get("metric") or "").strip()
        operator = str(item.get("operator") or "").strip()
        if metric not in METRICS:
            raise ValueError(f"Métrique Live inconnue : {metric}")
        if operator not in OPERATORS:
            raise ValueError(f"Opérateur Live invalide : {operator}")
        meta = METRICS[metric]
        value = _number(item.get("value"), lo=float(meta["min"]), hi=float(meta["max"]), field=f"Seuil {meta['label']}")
        out.append({"metric": metric, "operator": operator, "value": value})
    if not allow_empty and not out:
        raise ValueError("Configurez au moins une condition")
    return out


def normalize_level(raw):
    raw = dict(raw or {})
    return {
        "level_key": _clean_level_key(raw.get("level_key") or raw.get("key") or raw.get("label")),
        "label": _clean_label(raw.get("label") or raw.get("level_key"), "Nom du niveau"),
        "rank": _number(raw.get("rank", 100), lo=-10000, hi=10000, field="Rang", integer=True),
        "color": _color(raw.get("color") or "#667085"),
        "enabled": 1 if _as_bool(raw.get("enabled", True), True) else 0,
        "is_fallback": 1 if _as_bool(raw.get("is_fallback", False), False) else 0,
    }




def _normalize_target_keys(raw):
    """Return normalized target keys while preserving RC26 mono-target compatibility."""
    values = raw.get("target_keys") if isinstance(raw, dict) else None
    if values is None:
        legacy = str((raw or {}).get("target_key") or "").strip()
        if legacy.startswith("@MULTI:"):
            try:
                values = json.loads(legacy[7:])
            except Exception:
                values = [legacy]
        else:
            values = [legacy] if legacy else []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple)):
        raise ValueError("Cibles Live invalides")
    out=[]
    seen=set()
    for value in values:
        key=" ".join(str(value or "").split()).strip()[:160]
        if not key:
            continue
        folded=key.casefold()
        if folded in seen:
            continue
        seen.add(folded); out.append(key)
    if len(out)>50:
        raise ValueError("Maximum 50 cibles par règle Live")
    return out

def _encode_target_keys(keys):
    keys=list(keys or [])
    if not keys:
        return ""
    if len(keys)==1:
        return keys[0]
    return "@MULTI:"+json.dumps(keys, ensure_ascii=False, separators=(",",":"))

def rule_target_keys(rule):
    return _normalize_target_keys(rule or {})

def normalize_rule(raw, *, known_levels=None):
    raw = dict(raw or {})
    name = _clean_label(raw.get("name"), "Nom de règle")
    scope_type = str(raw.get("scope_type") or "GLOBAL").strip().upper()
    if scope_type not in SCOPE_TYPES:
        raise ValueError("Périmètre Live invalide")
    match_mode = str(raw.get("match_mode") or "ANY").strip().upper()
    if match_mode not in MATCH_MODES:
        raise ValueError("Mode de correspondance Live invalide")
    level_key = _clean_level_key(raw.get("level_key"))
    if known_levels is not None and level_key not in known_levels:
        raise ValueError("Niveau Live inconnu")
    target_keys = _normalize_target_keys(raw)
    target_key = _encode_target_keys(target_keys)
    return {
        "id": int(raw["id"]) if str(raw.get("id") or "").strip().isdigit() else None,
        "name": name,
        "enabled": 1 if _as_bool(raw.get("enabled", True), True) else 0,
        "scope_type": scope_type,
        "target_key": target_key,
        "target_keys": target_keys,
        "match_mode": match_mode,
        "level_key": level_key,
        "min_duration_seconds": _number(raw.get("min_duration_seconds", 0), lo=0, hi=86400, field="Durée minimale", integer=True),
        "recovery_seconds": _number(raw.get("recovery_seconds", 30), lo=0, hi=86400, field="Durée de retour normal", integer=True),
        "cooldown_seconds": _number(raw.get("cooldown_seconds", 300), lo=0, hi=604800, field="Cooldown", integer=True),
        "min_sample_size": _number(raw.get("min_sample_size", 0), lo=0, hi=1000000, field="Échantillon minimum", integer=True),
        "allow_partial": 1 if _as_bool(raw.get("allow_partial", False), False) else 0,
        "conditions": validate_conditions(raw.get("conditions") if "conditions" in raw else raw.get("conditions_json"), allow_empty=False),
    }


def ensure_admin_schema():
    """Idempotent safety net for installations migrated without app_db.ensure_schema."""
    with db_connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS live_quality_levels(
            level_key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            rank INTEGER NOT NULL,
            color TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
            is_fallback INTEGER NOT NULL DEFAULT 0 CHECK(is_fallback IN (0,1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        );
        CREATE TABLE IF NOT EXISTS live_quality_rules(
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
        CREATE INDEX IF NOT EXISTS idx_live_quality_rules_eval ON live_quality_rules(enabled,scope_type,level_key,id);
        """)
        # Seed defaults only once. If an administrator later deletes all rules,
        # a restart must preserve that intentional configuration.
        try:
            seed_row = con.execute("SELECT value FROM settings WHERE key='live_quality_seeded'").fetchone()
        except Exception:
            seed_row = None
        if not seed_row:
            count = con.execute("SELECT COUNT(*) FROM live_quality_levels").fetchone()[0]
            if not count:
                con.executemany(
                    """INSERT INTO live_quality_levels(level_key,label,rank,color,enabled,is_fallback,updated_by)
                       VALUES(?,?,?,?,?,?, 'SYSTEM')""",
                    [(x["level_key"], x["label"], x["rank"], x["color"], x["enabled"], x["is_fallback"]) for x in DEFAULT_LEVELS],
                )
            rule_count = con.execute("SELECT COUNT(*) FROM live_quality_rules").fetchone()[0]
            if not rule_count:
                known = {x["level_key"] for x in DEFAULT_LEVELS}
                for raw in DEFAULT_RULES:
                    rule = normalize_rule(raw, known_levels=known)
                    con.execute(
                        """INSERT INTO live_quality_rules(name,enabled,scope_type,target_key,match_mode,level_key,
                           min_duration_seconds,recovery_seconds,cooldown_seconds,min_sample_size,allow_partial,conditions_json,updated_by)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?, 'SYSTEM')""",
                        (rule["name"], rule["enabled"], rule["scope_type"], rule["target_key"], rule["match_mode"], rule["level_key"],
                         rule["min_duration_seconds"], rule["recovery_seconds"], rule["cooldown_seconds"], rule["min_sample_size"],
                         rule["allow_partial"], json.dumps(rule["conditions"], ensure_ascii=False, separators=(",", ":"))),
                    )
            try:
                con.execute("INSERT INTO settings(key,value,updated_by) VALUES('live_quality_seeded','1','SYSTEM') ON CONFLICT(key) DO UPDATE SET value='1'")
            except Exception:
                pass
        if con.execute("SELECT COUNT(*) FROM live_quality_levels WHERE is_fallback=1").fetchone()[0] == 0:
            row = con.execute("SELECT level_key FROM live_quality_levels ORDER BY rank ASC,level_key LIMIT 1").fetchone()
            if row:
                con.execute("UPDATE live_quality_levels SET is_fallback=1,enabled=1 WHERE level_key=?", (row[0],))
        con.commit()


def load_levels(include_disabled=True):
    ensure_admin_schema()
    with db_connect() as con:
        sql = "SELECT * FROM live_quality_levels"
        if not include_disabled:
            sql += " WHERE enabled=1"
        sql += " ORDER BY rank DESC,level_key"
        rows = [dict(r) for r in con.execute(sql).fetchall()]
    return rows


def load_rules(include_disabled=True):
    ensure_admin_schema()
    with db_connect() as con:
        sql = "SELECT * FROM live_quality_rules"
        if not include_disabled:
            sql += " WHERE enabled=1"
        sql += " ORDER BY id"
        rows = []
        for r in con.execute(sql).fetchall():
            d = dict(r)
            try:
                d["conditions"] = validate_conditions(d.pop("conditions_json", "[]"), allow_empty=False)
            except ValueError:
                d["conditions"] = []
                d["enabled"] = 0
                d["configuration_error"] = "conditions_invalid"
            d["target_keys"] = rule_target_keys(d)
            rows.append(d)
    return rows


def config_snapshot():
    levels = load_levels(include_disabled=True)
    rules = load_rules(include_disabled=True)
    return {
        "levels": levels,
        "rules": rules,
        "metrics": metric_catalog(),
        "operators": list(OPERATORS),
        "match_modes": list(MATCH_MODES),
        "scope_types": list(SCOPE_TYPES),
        "presets": [dict(x) for x in RULE_PRESETS],
        "modes": ["simple", "advanced"],
        "incident_history_retention_days": INCIDENT_HISTORY_RETENTION_DAYS,
        "notes": [
            "Les métriques marquées certification_required restent indisponibles tant que leur source Hermes n'est pas prouvée.",
            "Une couleur n'est jamais la seule explication : chaque signal conserve les conditions et valeurs observées.",
            "other et inactive_context restent distincts : inactive_context exige un libellé Hermes explicite.",
            "Un agent configuré mais non observé reste Non observé ; il n'est jamais converti en offline/pause/inactif.",
            "Les incidents rétablis/clôturés et leur journal sont conservés 90 jours ; un incident actif n'est jamais purgé par la rétention.",
        ],
    }


def save_level(raw, actor="SYSTEM"):
    level = normalize_level(raw)
    original = str((raw or {}).get("original_level_key") or level["level_key"]).strip().upper()
    ensure_admin_schema()
    with db_connect() as con:
        existing = con.execute("SELECT level_key,is_fallback FROM live_quality_levels WHERE level_key=?", (original,)).fetchone()
        duplicate = con.execute("SELECT level_key FROM live_quality_levels WHERE level_key=?", (level["level_key"],)).fetchone()
        if duplicate and (not existing or duplicate[0] != existing[0]):
            raise ValueError("Un niveau Live porte déjà cet identifiant")
        if existing and existing["is_fallback"] and not level["is_fallback"]:
            other = con.execute("SELECT 1 FROM live_quality_levels WHERE is_fallback=1 AND level_key<>? LIMIT 1", (original,)).fetchone()
            if not other:
                raise ValueError("Choisissez d'abord un autre niveau de repli")
        if level["is_fallback"]:
            level["enabled"] = 1
            con.execute("UPDATE live_quality_levels SET is_fallback=0 WHERE is_fallback=1")
        if existing:
            con.execute(
                """UPDATE live_quality_levels SET level_key=?,label=?,rank=?,color=?,enabled=?,is_fallback=?,
                   updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE level_key=?""",
                (level["level_key"], level["label"], level["rank"], level["color"], level["enabled"], level["is_fallback"], actor, original),
            )
        else:
            con.execute(
                """INSERT INTO live_quality_levels(level_key,label,rank,color,enabled,is_fallback,updated_by)
                   VALUES(?,?,?,?,?,?,?)""",
                (level["level_key"], level["label"], level["rank"], level["color"], level["enabled"], level["is_fallback"], actor),
            )
        con.commit()
    return level


def delete_level(level_key, actor="SYSTEM"):
    key = _clean_level_key(level_key)
    ensure_admin_schema()
    with db_connect() as con:
        row = con.execute("SELECT is_fallback FROM live_quality_levels WHERE level_key=?", (key,)).fetchone()
        if not row:
            raise KeyError("Niveau Live introuvable")
        if row["is_fallback"]:
            raise ValueError("Le niveau de repli ne peut pas être supprimé")
        used = con.execute("SELECT COUNT(*) FROM live_quality_rules WHERE level_key=?", (key,)).fetchone()[0]
        if used:
            raise ValueError("Ce niveau est utilisé par une ou plusieurs règles Live")
        con.execute("DELETE FROM live_quality_levels WHERE level_key=?", (key,))
        con.commit()
    return True


def save_rule(raw, actor="SYSTEM"):
    ensure_admin_schema()
    levels = {x["level_key"] for x in load_levels(include_disabled=True)}
    rule = normalize_rule(raw, known_levels=levels)
    with db_connect() as con:
        params = (
            rule["name"], rule["enabled"], rule["scope_type"], rule["target_key"], rule["match_mode"], rule["level_key"],
            rule["min_duration_seconds"], rule["recovery_seconds"], rule["cooldown_seconds"], rule["min_sample_size"],
            rule["allow_partial"], json.dumps(rule["conditions"], ensure_ascii=False, separators=(",", ":")), actor,
        )
        if rule["id"] is not None:
            found = con.execute("SELECT 1 FROM live_quality_rules WHERE id=?", (rule["id"],)).fetchone()
            if not found:
                raise KeyError("Règle Live introuvable")
            con.execute(
                """UPDATE live_quality_rules SET name=?,enabled=?,scope_type=?,target_key=?,match_mode=?,level_key=?,
                   min_duration_seconds=?,recovery_seconds=?,cooldown_seconds=?,min_sample_size=?,allow_partial=?,conditions_json=?,
                   updated_at=CURRENT_TIMESTAMP,updated_by=? WHERE id=?""",
                (*params, rule["id"]),
            )
        else:
            cur = con.execute(
                """INSERT INTO live_quality_rules(name,enabled,scope_type,target_key,match_mode,level_key,
                   min_duration_seconds,recovery_seconds,cooldown_seconds,min_sample_size,allow_partial,conditions_json,updated_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                params,
            )
            rule["id"] = int(cur.lastrowid)
        con.commit()
    return rule


def delete_rule(rule_id):
    try:
        rid = int(rule_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Identifiant de règle Live invalide") from exc
    ensure_admin_schema()
    with db_connect() as con:
        cur = con.execute("DELETE FROM live_quality_rules WHERE id=?", (rid,))
        if cur.rowcount == 0:
            raise KeyError("Règle Live introuvable")
        con.commit()
    return True


def ensure_runtime_schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS live_quality_rule_state(
        rule_id INTEGER NOT NULL,
        scope_type TEXT NOT NULL,
        scope_key TEXT NOT NULL,
        first_match REAL,
        last_match REAL,
        clear_since REAL,
        cooldown_until REAL NOT NULL DEFAULT 0,
        last_incident_id TEXT,
        updated_at REAL NOT NULL,
        PRIMARY KEY(rule_id,scope_type,scope_key)
    );
    CREATE TABLE IF NOT EXISTS live_quality_incidents(
        id TEXT PRIMARY KEY,
        rule_id INTEGER NOT NULL,
        rule_name TEXT NOT NULL,
        scope_type TEXT NOT NULL,
        scope_key TEXT NOT NULL,
        scope_label TEXT NOT NULL,
        level_key TEXT NOT NULL,
        level_label TEXT NOT NULL,
        level_rank INTEGER NOT NULL,
        color TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'NOUVEAU',
        active INTEGER NOT NULL DEFAULT 1,
        first_seen REAL NOT NULL,
        last_seen REAL NOT NULL,
        triggered_at REAL NOT NULL,
        recovered_at REAL,
        closed_at REAL,
        cooldown_until REAL NOT NULL DEFAULT 0,
        reasons_json TEXT NOT NULL DEFAULT '[]',
        metrics_json TEXT NOT NULL DEFAULT '{}',
        contributor_agents_json TEXT NOT NULL DEFAULT '[]',
        updated_at REAL NOT NULL
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_live_quality_incident_active
        ON live_quality_incidents(rule_id,scope_type,scope_key) WHERE active=1;
    CREATE INDEX IF NOT EXISTS idx_live_quality_incident_recent
        ON live_quality_incidents(active,level_rank DESC,last_seen DESC);
    CREATE INDEX IF NOT EXISTS idx_live_quality_incident_period
        ON live_quality_incidents(triggered_at,scope_type,scope_key);
    CREATE TABLE IF NOT EXISTS live_quality_incident_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        from_status TEXT,
        to_status TEXT,
        actor TEXT NOT NULL,
        comment TEXT NOT NULL DEFAULT '',
        action_text TEXT NOT NULL DEFAULT '',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at REAL NOT NULL,
        FOREIGN KEY(incident_id) REFERENCES live_quality_incidents(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_live_quality_incident_events
        ON live_quality_incident_events(incident_id,created_at,id);
    """)
    cols={str(r[1]) for r in con.execute("PRAGMA table_info(live_quality_incidents)").fetchall()}
    if "contributor_agents_json" not in cols:
        con.execute("ALTER TABLE live_quality_incidents ADD COLUMN contributor_agents_json TEXT NOT NULL DEFAULT '[]'")


def _event_snapshot(metrics):
    return dict(metrics or {}) if isinstance(metrics, dict) else {}


def _insert_incident_event(con, incident_id, event_type, *, actor="SYSTEM", from_status=None,
                           to_status=None, comment="", action_text="", snapshot=None, clock=None):
    clock = time.time() if clock is None else float(clock)
    con.execute(
        """INSERT INTO live_quality_incident_events(
           incident_id,event_type,from_status,to_status,actor,comment,action_text,snapshot_json,created_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            str(incident_id), str(event_type or "EVENT"), str(from_status or "") or None,
            str(to_status or "") or None, str(actor or "SYSTEM")[:120], str(comment or "")[:4000],
            str(action_text or "")[:4000],
            json.dumps(_event_snapshot(snapshot), ensure_ascii=False, separators=(",", ":")), float(clock),
        ),
    )


def _metric(value, *, source="Hermes Live", quality="reliable", reason="", sample_size=None, freshness_seconds=None):
    return {
        "value": value,
        "source": source,
        "quality": quality,
        "reason": reason,
        "sample_size": sample_size,
        "freshness_seconds": freshness_seconds,
    }


def _unavailable(reason="source_not_certified", source="Hermes Live"):
    return _metric(None, source=source, quality="unavailable", reason=reason)


def _percent(n, d):
    return round(float(n) * 100.0 / float(d), 2) if d else 0.0


def _normalized_state_text(value):
    text=unicodedata.normalize("NFD",str(value or ""))
    return " ".join("".join(ch for ch in text if unicodedata.category(ch)!="Mn").lower().split())


def _pause_subtype(agent):
    raw=_normalized_state_text((agent or {}).get("state"))
    kind=str((agent or {}).get("kind") or "")
    if "coaching" in raw or raw=="coach" or "pause coaching" in raw:
        return "coaching"
    if "dejeuner" in raw or "lunch" in raw or "pause midi" in raw or "meal break" in raw:
        return "lunch"
    if "general break" in raw or "general breack" in raw or "pause generale" in raw or "general pause" in raw:
        return "general"
    if kind=="pause" or raw=="break" or "pause" in raw:
        return "normal"
    return ""

def _scope_metrics(agents, health, *, global_kpi=None, configured_count=None, current_calls_override=None, reference_scope=False):
    """Summarise only states actually observed by Hermes.

    ``configured_count`` is a catalogue reference used to expose coverage. A
    configured agent with no Live state is never silently converted to offline,
    available or zero. When a configured scope has no observed agent, state
    metrics are explicitly unavailable.
    """
    agents=list(agents or [])
    kinds = {"call": 0, "hold": 0, "ready": 0, "wrap": 0, "pause": 0, "inactive_context": 0, "offline": 0, "other": 0, "arrival": 0}
    ages = []
    max_by_kind = {"wrap": 0.0, "pause": 0.0, "inactive_context": 0.0, "offline": 0.0, "hold": 0.0}
    pause_counts={"normal":0,"lunch":0,"coaching":0,"general":0}
    pause_max={"normal":0.0,"lunch":0.0,"coaching":0.0,"general":0.0}
    early_hold_offsets=[]
    current_calls = 0
    for a in agents:
        k = str(a.get("kind") or "other")
        kinds[k] = kinds.get(k, 0) + 1
        raw_age=a.get("state_age_seconds")
        try:
            age = float(raw_age) if raw_age is not None else 0.0
        except (TypeError, ValueError):
            age = 0.0
        ages.append(age)
        if k in max_by_kind:
            max_by_kind[k] = max(max_by_kind[k], age)
        pause_type=_pause_subtype(a)
        if pause_type:
            pause_counts[pause_type]=pause_counts.get(pause_type,0)+1
            pause_max[pause_type]=max(pause_max.get(pause_type,0.0),age)
        call=a.get("current_call") or {}
        if call:
            current_calls += 1
            offset=call.get("first_hold_offset_seconds")
            if offset is not None:
                try: early_hold_offsets.append(max(0.0,float(offset)))
                except (TypeError,ValueError): pass
    observed = len(agents)
    configured = max(observed, int(configured_count if configured_count is not None else observed))
    freshness = health.get("last_response_age")

    if observed == 0 and (configured > 0 or reference_scope) and not global_kpi:
        out={"agents_known":_metric(configured,source="Configuration files/agents",quality="reliable",reason="configured_reference",sample_size=0,freshness_seconds=freshness)}
        for key in ("agents_connected","agents_available","agents_in_call","agents_on_hold","agents_wrap","agents_pause","agents_pause_normal","agents_pause_lunch","agents_pause_coaching","agents_pause_general","agents_inactive_context","agents_offline",
                    "available_percent","in_call_percent","hold_percent","wrap_percent","pause_percent","inactive_context_percent","current_calls",
                    "max_state_age_seconds","max_wrap_seconds","max_pause_seconds","max_pause_normal_seconds","max_pause_lunch_seconds","max_pause_coaching_seconds","max_pause_general_seconds","max_inactive_context_seconds","max_hold_seconds","earliest_hold_start_seconds","max_offline_seconds"):
            out[key]=_unavailable("no_live_state_observed")
        out["freshness_seconds"]=_metric(float(freshness),quality="reliable") if freshness is not None else _unavailable("live_data_not_fresh")
        for key in ("waiting_now", "oldest_waiting_seconds", "median_wait_seconds", "p90_wait_seconds", "abandon_rate", "qos"):
            out[key] = _unavailable("semantics_not_certified")
        return out

    connected = sum(v for k, v in kinds.items() if k != "offline")
    quality = "reliable" if health.get("fresh") else "partial"
    reason = "" if health.get("fresh") else "live_data_not_fresh"
    if health.get("fresh") and configured > observed:
        quality="partial";reason="live_coverage_partial"
    values = {
        "agents_known": configured,
        "agents_connected": connected,
        "agents_available": kinds.get("ready", 0),
        "agents_in_call": kinds.get("call", 0) + kinds.get("hold", 0),
        "agents_on_hold": kinds.get("hold", 0),
        "agents_wrap": kinds.get("wrap", 0),
        "agents_pause": kinds.get("pause", 0),
        "agents_pause_normal": pause_counts.get("normal",0),
        "agents_pause_lunch": pause_counts.get("lunch",0),
        "agents_pause_coaching": pause_counts.get("coaching",0),
        "agents_pause_general": pause_counts.get("general",0),
        "agents_inactive_context": kinds.get("inactive_context", 0),
        "agents_offline": kinds.get("offline", 0),
        "available_percent": _percent(kinds.get("ready", 0), connected),
        "in_call_percent": _percent(kinds.get("call", 0) + kinds.get("hold", 0), connected),
        "hold_percent": _percent(kinds.get("hold", 0), connected),
        "wrap_percent": _percent(kinds.get("wrap", 0), connected),
        "pause_percent": _percent(kinds.get("pause", 0), connected),
        "inactive_context_percent": _percent(kinds.get("inactive_context", 0), connected),
        "current_calls": (current_calls if current_calls_override is None else int(current_calls_override)) if health.get("fresh") else None,
        "max_state_age_seconds": round(max(ages) if ages else 0.0, 1),
        "max_wrap_seconds": round(max_by_kind["wrap"], 1),
        "max_pause_seconds": round(max_by_kind["pause"], 1),
        "max_pause_normal_seconds": round(pause_max.get("normal",0.0),1),
        "max_pause_lunch_seconds": round(pause_max.get("lunch",0.0),1),
        "max_pause_coaching_seconds": round(pause_max.get("coaching",0.0),1),
        "max_pause_general_seconds": round(pause_max.get("general",0.0),1),
        "max_inactive_context_seconds": round(max_by_kind["inactive_context"], 1),
        "max_hold_seconds": round(max_by_kind["hold"], 1),
        "earliest_hold_start_seconds": round(min(early_hold_offsets),1) if early_hold_offsets else None,
        "max_offline_seconds": round(max_by_kind["offline"], 1),
        "freshness_seconds": float(freshness) if freshness is not None else None,
    }
    if global_kpi:
        # Preserve RC12's own global counters where they are authoritative.
        for source_key, metric_key in (
            ("agents_known", "agents_known"), ("connected", "agents_connected"),
            ("available", "agents_available"), ("in_call", "agents_in_call"), ("on_hold", "agents_on_hold"),
            ("current_calls", "current_calls"),
        ):
            if source_key in global_kpi and global_kpi[source_key] is not None:
                values[metric_key] = global_kpi[source_key]
    out = {}
    for key, value in values.items():
        if value is None:
            out[key] = _unavailable("live_data_not_fresh")
        else:
            out[key] = _metric(value, quality=quality, reason=reason, sample_size=observed, freshness_seconds=freshness)
    for key in ("waiting_now", "oldest_waiting_seconds", "median_wait_seconds", "p90_wait_seconds", "abandon_rate", "qos"):
        out[key] = _unavailable("semantics_not_certified")
    return out


def build_scopes(snapshot):
    """Build Live scopes from the configured hierarchy plus observed Hermes state.

    Groups/files/campaigns are catalogue-backed so supervisors can see the full
    configured perimeter even when a scope has no current Live event. Missing
    state remains unavailable rather than becoming a fabricated zero.
    """
    health = dict(snapshot.get("health") or {})
    agents = list(snapshot.get("agents") or [])
    live_by_agent={str(a.get("agent") or ""):a for a in agents if str(a.get("agent") or "")}
    roster=list(snapshot.get("agent_roster") or agents)
    roster_by_agent={str(a.get("agent") or ""):a for a in roster if str(a.get("agent") or "")}
    scopes = []

    def add(scope_type, key, label, rows, extra=None, global_kpi=None, configured_count=None, current_calls_override=None, reference_scope=False):
        rows=list(rows or [])
        scopes.append({
            "scope_type": scope_type,
            "scope_key": str(key or ""),
            "scope_label": str(label or key or scope_type),
            "metrics": _scope_metrics(rows, health, global_kpi=global_kpi, configured_count=configured_count,
                                      current_calls_override=current_calls_override, reference_scope=reference_scope),
            "agent_count": len(rows),
            "observed_agent_count": len(rows),
            "configured_agent_count": max(len(rows),int(configured_count if configured_count is not None else len(rows))),
            "_agent_rows": rows,
            **(extra or {}),
        })

    add("GLOBAL", "GLOBAL", "Global", agents, global_kpi=snapshot.get("kpi") or {})
    global_scope=scopes[-1]

    cfg={}
    if snapshot.get("catalog_reference"):
        try:
            from quality_scope import load_quality_file_scope
            cfg=load_quality_file_scope()
        except Exception:
            cfg={}
    groups=[g for g in (cfg.get("groups") or []) if str(g.get("id") or "")!='unassigned']
    selected_group=str(((snapshot.get("scope") or {}).get("group_id") or '')).strip()
    if selected_group:
        groups=[g for g in groups if str(g.get("id") or '')==selected_group]
    allowed_lines={str(x) for g in groups for x in (g.get("line_ids") or []) if str(x)} if selected_group else None
    active_by_line={str(k):{str(x) for x in (v or [])} for k,v in (((cfg.get("agents_by_line_state") or {}).get("active") or {}).items())}

    configured_campaign_keys=set();configured_queue_keys=set();configured_group_keys=set();configured_service_keys=set()
    if groups or cfg.get("queues") or cfg.get("campaigns"):
        service_members={}
        service_lines={}
        for g in groups:
            gid=str(g.get("id") or "")
            if not gid:continue
            members={str(x) for x in (g.get("member_agent_ids") or []) if str(x)}
            rows=[live_by_agent[a] for a in members if a in live_by_agent]
            group_lines={str(x) for x in (g.get("line_ids") or []) if str(x)}
            add("GROUP",gid,str(g.get("name") or gid),rows,
                extra={"service_name":str(g.get("service_name") or ""),"coverage_basis":"configured_files","line_ids":sorted(group_lines)},configured_count=len(members),reference_scope=True)
            configured_group_keys.add(gid)
            service=str(g.get("service_name") or '').strip()
            if service:
                configured_service_keys.add(service)
                service_members.setdefault(service,set()).update(members)
                service_lines.setdefault(service,set()).update(group_lines)
        for service,members in sorted(service_members.items(),key=lambda kv:kv[0].casefold()):
            rows=[live_by_agent[a] for a in members if a in live_by_agent]
            add("SERVICE",service,service,rows,extra={"coverage_basis":"configured_groups","line_ids":sorted(service_lines.get(service,set()))},configured_count=len(members),reference_scope=True)

        global_scope['line_ids']=sorted(allowed_lines if allowed_lines is not None else {str(q.get('line_id') or '') for q in (cfg.get('queues') or []) if str(q.get('line_id') or '')})

        for q in cfg.get("queues") or []:
            qid=str(q.get("line_id") or '')
            if not qid or (allowed_lines is not None and qid not in allowed_lines):continue
            members=set(active_by_line.get(qid,set()))
            rows=[live_by_agent[a] for a in members if a in live_by_agent]
            current=sum(1 for a in rows if str((a.get('current_call') or {}).get('line_id') or a.get('line_id') or '')==qid and a.get('current_call'))
            add("QUEUE",qid,str(q.get("display_name") or q.get("line_name") or ('File '+qid)),rows,
                extra={"coverage_basis":"configured_file"},configured_count=len(members),current_calls_override=current,reference_scope=True)
            configured_queue_keys.add(qid)

        campaign_to_files=cfg.get("campaign_to_files") or {}
        campaigns=cfg.get("campaigns") or {}
        live_queue_catalog={str(k):str(v).strip() for k,v in (snapshot.get('live_queue_catalog') or {}).items() if str(k) and str(v).strip()}

        # Hermes agent-state callbacks carry both the current campaign label and
        # the queue/LineId.  Use those observed pairs to repair incomplete
        # historical campaign->file configuration.  This is stronger evidence
        # than inferring a campaign from a generic agent assignment because the
        # pair is observed together in the Live state itself.
        observed_campaign_lines={}
        for a in agents:
            qid=str((a.get('current_call') or {}).get('line_id') or a.get('line_id') or '').strip()
            if not qid:
                continue
            labels={
                str(a.get('campaign_id') or '').strip(),
                str(a.get('campaign_name') or '').strip(),
                str(a.get('campaign') or '').strip(),
                str((a.get('current_call') or {}).get('campaign_id') or '').strip(),
                str((a.get('current_call') or {}).get('campaign_name') or '').strip(),
                str((a.get('current_call') or {}).get('campaign') or '').strip(),
            }
            for value in labels:
                if value:
                    observed_campaign_lines.setdefault(value.casefold(),set()).add(qid)

        campaigns_by_name={str((raw or {}).get('campaign_name') or '').strip().casefold():str(cid)
                           for cid,raw in campaigns.items() if str((raw or {}).get('campaign_name') or '').strip()}
        campaign_lines=set()
        for cid,raw in sorted(campaigns.items(),key=lambda kv:str((kv[1] or {}).get('campaign_name') or kv[0]).casefold()):
            cid=str(cid or '')
            if not cid:continue
            label=str((raw or {}).get('campaign_name') or cid)
            configured_line_ids={str(x.get('line_id') or '') for x in (campaign_to_files.get(cid) or []) if str(x.get('line_id') or '')}
            observed_line_ids=set(observed_campaign_lines.get(cid.casefold(),set()))|set(observed_campaign_lines.get(label.casefold(),set()))
            # InitQueue is a direct Hermes catalogue. An exact label match is a
            # conservative repair path when the imported campaign/file mapping
            # is incomplete; no fuzzy/name-contains inference is permitted.
            catalog_line_ids={qid for qid,qname in live_queue_catalog.items() if qname.casefold()==label.strip().casefold()}
            line_ids=configured_line_ids|observed_line_ids|catalog_line_ids
            # Historical imports can contain campaign identifiers that have no
            # configured file at all. They cannot receive Hermes queue metrics
            # and used to create a large wall of empty rows in Centre Live.
            # Keep only file-backed configured campaigns; genuinely observed
            # campaigns are still added below from the Live agent state.
            if not line_ids:
                continue
            if allowed_lines is not None:
                line_ids &= allowed_lines
                if not line_ids:continue
            campaign_lines.update(line_ids)
            members=set()
            for qid in line_ids:members.update(active_by_line.get(qid,set()))
            candidates={cid.casefold(),label.casefold()}
            # Do not lose an actually observed agent merely because an imported
            # ACTIVE assignment is incomplete. Current LineId/campaign identity
            # is direct Live evidence and only widens this Live row, not history.
            observed_members=set()
            for aid,a in live_by_agent.items():
                aqid=str((a.get('current_call') or {}).get('line_id') or a.get('line_id') or '').strip()
                alabels={str(a.get('campaign_id') or '').strip().casefold(),str(a.get('campaign_name') or '').strip().casefold(),str(a.get('campaign') or '').strip().casefold(),str((a.get('current_call') or {}).get('campaign_id') or '').strip().casefold(),str((a.get('current_call') or {}).get('campaign_name') or '').strip().casefold(),str((a.get('current_call') or {}).get('campaign') or '').strip().casefold()}
                if (aqid and aqid in line_ids) or bool(candidates & {x for x in alabels if x}): observed_members.add(aid)
            rows=[live_by_agent[a] for a in (members|observed_members) if a in live_by_agent]
            current=sum(1 for a in rows if a.get('current_call') and str((a.get('current_call') or {}).get('campaign') or (a.get('current_call') or {}).get('campaign_name') or a.get('campaign') or a.get('campaign_name') or '').strip().casefold() in candidates)
            basis_parts=['configured_files']
            if observed_line_ids-configured_line_ids:basis_parts.append('live_observed_pair')
            if catalog_line_ids-(configured_line_ids|observed_line_ids):basis_parts.append('live_queue_catalog_exact')
            if observed_members-members:basis_parts.append('live_observed_agents')
            basis='+'.join(basis_parts)
            add("CAMPAIGN",cid,label,rows,extra={"identity_quality":"configured_id","coverage_basis":basis,"line_ids":sorted(line_ids),
                "configured_line_ids":sorted(configured_line_ids),"observed_line_ids":sorted(observed_line_ids),"catalog_line_ids":sorted(catalog_line_ids)},
                configured_count=len(members),current_calls_override=current,reference_scope=True)
            configured_campaign_keys.add(cid.casefold());configured_campaign_keys.add(label.casefold())

        # A Hermes file can legitimately have no configured campaign mapping.
        # Surface it as a diagnostic campaign/file row so its native UpQuR/UpQuH
        # counters remain visible instead of being silently discarded.
        live_line_labels={}
        for a in agents:
            qid=str(a.get('line_id') or (a.get('current_call') or {}).get('line_id') or '').strip()
            label=str(a.get('campaign') or (a.get('current_call') or {}).get('campaign') or '').strip()
            if qid and label: live_line_labels.setdefault(qid,label)
        queue_cfg_by_id={str(q.get('line_id') or ''):q for q in (cfg.get("queues") or []) if str(q.get('line_id') or '')}
        native_line_ids=set(str(x) for x in (((snapshot.get('native_queue_metrics') or {}).get('by_line') or {}).keys()) if str(x))
        for qid in sorted(set(queue_cfg_by_id)|native_line_ids):
            if not qid or qid in campaign_lines or (allowed_lines is not None and qid not in allowed_lines):
                continue
            q=queue_cfg_by_id.get(qid) or {}
            members=set(active_by_line.get(qid,set()))
            rows=[live_by_agent[a] for a in members if a in live_by_agent]
            label=live_line_labels.get(qid) or live_queue_catalog.get(qid) or str(q.get('display_name') or q.get('line_name') or ('File '+qid))
            current=sum(1 for a in rows if str((a.get('current_call') or {}).get('line_id') or a.get('line_id') or '')==qid and a.get('current_call'))
            add("CAMPAIGN",'FILE:'+qid,label,rows,extra={"identity_quality":"file_fallback","coverage_basis":"native_or_configured_file","line_ids":[qid],"diagnostic_file_fallback":True},
                configured_count=len(members),current_calls_override=current,reference_scope=True)
            configured_campaign_keys.add(('FILE:'+qid).casefold());configured_campaign_keys.add(label.casefold())

    # Keep genuinely observed-but-not-configured scopes visible as diagnostics.
    by_service={};by_group={};by_campaign={};by_queue={}
    for a in agents:
        for service in a.get("service_names") or []:
            by_service.setdefault(str(service),{})[str(a.get("agent"))]=a
        for group in a.get("groups") or []:
            gid=str(group.get("id") or group.get("name") or "")
            if gid:
                bucket=by_group.setdefault(gid,{"label":str(group.get("name") or gid),"rows":{}});bucket["rows"][str(a.get("agent"))]=a
        campaign=str(a.get("campaign") or (a.get("current_call") or {}).get("campaign") or "").strip()
        if campaign:by_campaign.setdefault(campaign,{})[str(a.get("agent"))]=a
        queue=str(a.get("line_id") or (a.get("current_call") or {}).get("line_id") or "").strip()
        if queue:by_queue.setdefault(queue,{})[str(a.get("agent"))]=a
    for key,rows in sorted(by_service.items(),key=lambda kv:kv[0].casefold()):
        if key not in configured_service_keys:add("SERVICE",key,key,list(rows.values()),extra={"coverage_basis":"observed_only"})
    for key,payload in sorted(by_group.items(),key=lambda kv:kv[1]["label"].casefold()):
        if key not in configured_group_keys:add("GROUP",key,payload["label"],list(payload["rows"].values()),extra={"coverage_basis":"observed_only"})
    for key,rows in sorted(by_campaign.items(),key=lambda kv:kv[0].casefold()):
        if key.casefold() not in configured_campaign_keys:
            observed_lines=sorted(observed_campaign_lines.get(key.casefold(),set())) if 'observed_campaign_lines' in locals() else []
            add("CAMPAIGN",key,key,list(rows.values()),extra={"identity_quality":"observed_label","coverage_basis":"observed_live_pair" if observed_lines else "observed_only","line_ids":observed_lines})
    for key,rows in sorted(by_queue.items(),key=lambda kv:kv[0]):
        if key not in configured_queue_keys:add("QUEUE",key,key,list(rows.values()),extra={"coverage_basis":"observed_only"})

    # Agent scopes follow the configured roster, while absent Live state stays unavailable.
    seen_agents=set()
    for aid,row in sorted(roster_by_agent.items(),key=lambda kv:str(kv[1].get('name') or kv[0]).casefold()):
        observed=live_by_agent.get(aid)
        add("AGENT",aid,str(row.get("name") or aid),[observed] if observed else [],
            extra={"observed":bool(observed),"coverage_basis":"configured_roster" if not observed else "live"},configured_count=1,reference_scope=True)
        seen_agents.add(aid)
    for aid,row in live_by_agent.items():
        if aid not in seen_agents:add("AGENT",aid,str(row.get("name") or aid),[row],extra={"observed":True,"coverage_basis":"observed_only"})

    # Native Hermes legacy-supervision counters, proven from the supplied HAR.
    # RC29.4 Live Center Fix 1: preserve these counters all the way to the UI
    # and aggregate them by the exact configured LineId set of GLOBAL/SERVICE/GROUP.
    # Missing UpQuH/UpQuR remains unavailable; no zero is invented.
    native_by_line=dict(((snapshot.get('native_queue_metrics') or {}).get('by_line') or {}))
    if not global_scope.get('line_ids'):
        global_scope['line_ids']=sorted(str(x) for x in native_by_line if str(x))
    for scope in scopes:
        scope_type=str(scope.get('scope_type') or '')
        if scope_type not in ('GLOBAL','SERVICE','GROUP','QUEUE','CAMPAIGN'):
            continue
        if scope_type=='QUEUE':
            line_ids=[str(scope.get('scope_key') or '')]
        else:
            line_ids=[str(x) for x in (scope.get('line_ids') or []) if str(x)]
            if scope_type=='CAMPAIGN' and not line_ids:
                line_ids=sorted({str(a.get('line_id') or (a.get('current_call') or {}).get('line_id') or '') for a in (scope.get('_agent_rows') or []) if str(a.get('line_id') or (a.get('current_call') or {}).get('line_id') or '')})
        line_ids=sorted(set(line_ids))
        daily=[];realtime=[]
        for lid in line_ids:
            entry=native_by_line.get(lid) or {}
            if entry.get('UpQuH'):daily.append(entry['UpQuH'])
            if entry.get('UpQuR'):realtime.append(entry['UpQuR'])
        missing_daily=[lid for lid in line_ids if not (native_by_line.get(lid) or {}).get('UpQuH')]
        missing_realtime=[lid for lid in line_ids if not (native_by_line.get(lid) or {}).get('UpQuR')]
        queue_names=dict(snapshot.get('live_queue_catalog') or {})
        native={'source':'Hermes Live changes.ashx','line_count':len(line_ids),'daily_coverage':len(daily),'realtime_coverage':len(realtime),
                'missing_daily_line_ids':missing_daily,'missing_realtime_line_ids':missing_realtime,
                'missing_daily_lines':[{'line_id':lid,'name':str(queue_names.get(lid) or '')} for lid in missing_daily[:200]]}
        if daily:
            for key in ('received_today','handled_today','abandoned_today','qos_exclusion_1','qos_exclusion_2','qos_exclusion_3'):
                vals=[x.get(key) for x in daily if x.get(key) is not None]
                native[key]=sum(vals) if vals else None
            den=None
            if native.get('received_today') is not None and all(native.get(k) is not None for k in ('qos_exclusion_1','qos_exclusion_2','qos_exclusion_3')):
                den=native['received_today']-native['qos_exclusion_1']-native['qos_exclusion_2']-native['qos_exclusion_3']
            native['qos_denominator']=den
            native['qos_today']=(100.0*native['handled_today']/den) if den is not None and den>0 and native.get('handled_today') is not None else None
        if realtime:
            for key in ('calls_in_progress','calls_waiting'):
                vals=[x.get(key) for x in realtime if x.get(key) is not None]
                native[key]=sum(vals) if vals else None
            # Do not sum agents_available_on_queue here: the same agent can be
            # ACTIVE on several queues. For a one-file scope only, the Hermes
            # counter is exact and can serve as a fallback if no agent state is observed.
            if len(line_ids)==1:
                one=(native_by_line.get(line_ids[0]) or {}).get('UpQuR') or {}
                native['agents_available_on_queue']=one.get('agents_available_on_queue')
        native['daily_quality']='reliable' if health.get('fresh') and line_ids and len(daily)==len(line_ids) else ('partial' if daily else 'unavailable')
        native['realtime_quality']='reliable' if health.get('fresh') and line_ids and len(realtime)==len(line_ids) else ('partial' if realtime else 'unavailable')
        native['quality']='reliable' if native['daily_quality']=='reliable' and native['realtime_quality']=='reliable' else ('partial' if daily or realtime else 'unavailable')
        scope['native_calls']=native
    return scopes


def _compare(actual, operator, threshold):
    if operator == ">":
        return actual > threshold
    if operator == ">=":
        return actual >= threshold
    if operator == "<":
        return actual < threshold
    if operator == "<=":
        return actual <= threshold
    if operator == "==":
        return actual == threshold
    if operator == "!=":
        return actual != threshold
    return False


def evaluate_rule(rule, scope):
    """Pure evaluation. Missing metrics never become zero and never match by accident."""
    if str(rule.get("scope_type")) != str(scope.get("scope_type")):
        return {"matched": False, "eligible": False, "reason": "scope_type_mismatch", "checks": []}
    targets = {str(x).casefold() for x in rule_target_keys(rule)}
    if targets and not targets.intersection({str(scope.get("scope_key") or "").casefold(), str(scope.get("scope_label") or "").casefold()}):
        return {"matched": False, "eligible": False, "reason": "scope_target_mismatch", "checks": []}
    if int(scope.get("agent_count") or 0) < int(rule.get("min_sample_size") or 0):
        return {"matched": False, "eligible": False, "reason": "sample_too_small", "checks": []}

    checks = []
    available_checks = []
    allow_partial = bool(rule.get("allow_partial"))
    for cond in rule.get("conditions") or []:
        metric_key = cond["metric"]
        observed = (scope.get("metrics") or {}).get(metric_key) or _unavailable("metric_missing")
        value = observed.get("value")
        q = str(observed.get("quality") or "unavailable")
        usable = value is not None and (q == "reliable" or (allow_partial and q == "partial"))
        passed = False
        if usable:
            try:
                passed = _compare(float(value), cond["operator"], float(cond["value"]))
            except (TypeError, ValueError):
                usable = False
        item = {
            "metric": metric_key,
            "label": METRICS[metric_key]["label"],
            "operator": cond["operator"],
            "threshold": cond["value"],
            "value": value,
            "unit": METRICS[metric_key].get("unit") or "",
            "quality": q,
            "source": observed.get("source"),
            "usable": usable,
            "passed": bool(passed),
            "unavailable_reason": observed.get("reason") if not usable else "",
        }
        checks.append(item)
        if usable:
            available_checks.append(bool(passed))

    mode = str(rule.get("match_mode") or "ANY").upper()
    if mode == "ALL":
        eligible = len(available_checks) == len(checks) and bool(checks)
        matched = eligible and all(available_checks)
    else:
        eligible = bool(available_checks)
        matched = eligible and any(available_checks)
    reason = "matched" if matched else ("metric_unavailable" if not eligible else "conditions_not_met")
    return {"matched": matched, "eligible": eligible, "reason": reason, "checks": checks}


def _contributing_agents(scope, result, limit=50):
    """Return observed agents which materially explain a matched incident.

    This is explanatory metadata only. It never changes the rule result. For
    aggregate conditions such as "Aucun disponible", every observed agent in
    the scope is exposed because the absence of a ready agent is a collective
    fact. Unknown/unobserved configured agents are never fabricated.
    """
    rows=list(scope.get("_agent_rows") or [])
    matched={str(x.get("metric") or "") for x in (result.get("checks") or []) if x.get("usable") and x.get("passed")}
    kind_metrics={
        "pause":{"agents_pause","pause_percent","max_pause_seconds"},
        "inactive_context":{"agents_inactive_context","inactive_context_percent","max_inactive_context_seconds"},
        "wrap":{"agents_wrap","wrap_percent","max_wrap_seconds"},
        "offline":{"agents_offline","max_offline_seconds"},
        "hold":{"agents_on_hold","hold_percent","max_hold_seconds"},
        "call":{"agents_in_call","in_call_percent","current_calls"},
        "ready":{"agents_available","available_percent"},
    }
    selected=[]
    collective=bool(matched & {"agents_connected","agents_known","max_state_age_seconds","freshness_seconds"}) or ("agents_available" in matched and any(str(x.get("operator")) in {"<=","<","=="} for x in (result.get("checks") or []) if x.get("metric")=="agents_available"))
    for row in rows:
        k=str(row.get("kind") or "other")
        if collective or not matched or matched & kind_metrics.get(k,set()):
            selected.append({
                "agent":str(row.get("agent") or ""),
                "name":str(row.get("name") or row.get("agent") or ""),
                "state":str(row.get("state") or ""),
                "kind":k,
                "state_age_seconds":row.get("state_age_seconds"),
                "campaign":str(row.get("campaign_name") or row.get("campaign") or ""),
                "line_id":str(row.get("line_id") or ""),
            })
    selected.sort(key=lambda x:(-(float(x.get("state_age_seconds") or 0)),str(x.get("name") or "").casefold(),str(x.get("agent") or "")))
    return selected[:max(1,int(limit))]


def _level_map(levels=None):
    rows = levels if levels is not None else load_levels(include_disabled=True)
    return {str(x["level_key"]): dict(x) for x in rows}


def _load_active_incident(con, rule_id, scope_type, scope_key):
    return con.execute(
        "SELECT * FROM live_quality_incidents WHERE rule_id=? AND scope_type=? AND scope_key=? AND active=1 LIMIT 1",
        (int(rule_id), scope_type, scope_key),
    ).fetchone()


def _state_row(con, rule_id, scope_type, scope_key):
    return con.execute(
        "SELECT * FROM live_quality_rule_state WHERE rule_id=? AND scope_type=? AND scope_key=?",
        (int(rule_id), scope_type, scope_key),
    ).fetchone()


def _save_state(con, rule_id, scope_type, scope_key, *, first_match, last_match, clear_since, cooldown_until, last_incident_id, clock):
    con.execute(
        """INSERT INTO live_quality_rule_state(rule_id,scope_type,scope_key,first_match,last_match,clear_since,cooldown_until,last_incident_id,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?)
           ON CONFLICT(rule_id,scope_type,scope_key) DO UPDATE SET
             first_match=excluded.first_match,last_match=excluded.last_match,clear_since=excluded.clear_since,
             cooldown_until=excluded.cooldown_until,last_incident_id=excluded.last_incident_id,updated_at=excluded.updated_at""",
        (int(rule_id), scope_type, scope_key, first_match, last_match, clear_since, cooldown_until, last_incident_id, clock),
    )


def _open_incident(con, rule, scope, level, result, first_seen, clock):
    incident_id = uuid.uuid4().hex
    con.execute(
        """INSERT INTO live_quality_incidents(id,rule_id,rule_name,scope_type,scope_key,scope_label,
           level_key,level_label,level_rank,color,status,active,first_seen,last_seen,triggered_at,
           reasons_json,metrics_json,contributor_agents_json,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?, 'NOUVEAU',1,?,?,?,?,?,?,?)""",
        (
            incident_id, int(rule["id"]), str(rule["name"]), scope["scope_type"], scope["scope_key"], scope["scope_label"],
            level["level_key"], level["label"], int(level["rank"]), level["color"],
            float(first_seen), float(clock), float(clock),
            json.dumps(result["checks"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(scope.get("metrics") or {}, ensure_ascii=False, separators=(",", ":")),
            json.dumps(_contributing_agents(scope,result), ensure_ascii=False, separators=(",", ":")), float(clock),
        ),
    )
    _insert_incident_event(
        con, incident_id, "OUVERTURE", actor="SYSTEM", from_status=None, to_status="NOUVEAU",
        comment="Incident ouvert automatiquement après persistance du signal.",
        snapshot={"metrics":scope.get("metrics") or {},"contributors":_contributing_agents(scope,result)}, clock=clock,
    )
    return incident_id


def _update_incident(con, incident_id, scope, result, clock):
    con.execute(
        """UPDATE live_quality_incidents SET last_seen=?,reasons_json=?,metrics_json=?,contributor_agents_json=?,updated_at=? WHERE id=?""",
        (float(clock), json.dumps(result["checks"], ensure_ascii=False, separators=(",", ":")),
         json.dumps(scope.get("metrics") or {}, ensure_ascii=False, separators=(",", ":")),
         json.dumps(_contributing_agents(scope,result), ensure_ascii=False, separators=(",", ":")), float(clock), incident_id),
    )


def _recover_incident(con, incident_id, cooldown_until, clock, *, metrics=None, comment="Retour à la normale observé par le moteur Qualité Live."):
    row = con.execute("SELECT status FROM live_quality_incidents WHERE id=?", (str(incident_id),)).fetchone()
    previous = str(row["status"] or "NOUVEAU") if row else "NOUVEAU"
    con.execute(
        """UPDATE live_quality_incidents SET status='RETABLI',active=0,recovered_at=?,cooldown_until=?,updated_at=? WHERE id=?""",
        (float(clock), float(cooldown_until), float(clock), incident_id),
    )
    _insert_incident_event(
        con, incident_id, "RETOUR_NORMAL_AUTOMATIQUE", actor="SYSTEM", from_status=previous, to_status="RETABLI",
        comment=comment, snapshot=metrics or {}, clock=clock,
    )


def _reconcile_removed_rules(con, valid_rule_ids, clock):
    if valid_rule_ids:
        marks = ",".join("?" for _ in valid_rule_ids)
        rows = con.execute(
            f"SELECT id,rule_id FROM live_quality_incidents WHERE active=1 AND rule_id NOT IN ({marks})",
            tuple(sorted(valid_rule_ids)),
        ).fetchall()
    else:
        rows = con.execute("SELECT id,rule_id FROM live_quality_incidents WHERE active=1").fetchall()
    for row in rows:
        _recover_incident(con, row["id"], clock, clock, comment="Règle supprimée ou désactivée ; incident retiré du moteur actif.")


def process_snapshot(snapshot, *, clock=None, rules=None, levels=None, persist=True):
    """Evaluate configured rules and, optionally, advance durable incident state."""
    clock = time.time() if clock is None else float(clock)
    rules = [dict(r) for r in (rules if rules is not None else load_rules(include_disabled=False)) if r.get("enabled", 1)]
    levels_map = _level_map(levels)
    scopes = build_scopes(snapshot)
    scopes_by_type = {}
    for scope in scopes:
        scopes_by_type.setdefault(scope["scope_type"], []).append(scope)

    evaluations = []
    runtime_con = None
    if persist:
        import collection_store
        collection_store.init(force=False)
        runtime_cm = collection_store.connect()
        runtime_con = runtime_cm.__enter__()
        ensure_runtime_schema(runtime_con)
        _purge_retention_once_per_day(runtime_con, clock)
        _reconcile_removed_rules(runtime_con, {int(r["id"]) for r in rules if r.get("id") is not None}, clock)

    try:
        for rule in rules:
            if rule.get("id") is None or not rule.get("conditions"):
                continue
            level = levels_map.get(str(rule.get("level_key")))
            if not level or not level.get("enabled", 1):
                continue
            for scope in scopes_by_type.get(str(rule.get("scope_type")), []):
                result = evaluate_rule(rule, scope)
                if not result["eligible"] and result["reason"] in {"scope_target_mismatch", "scope_type_mismatch"}:
                    continue
                event = {
                    "rule_id": int(rule["id"]), "rule_name": rule["name"],
                    "scope_type": scope["scope_type"], "scope_key": scope["scope_key"], "scope_label": scope["scope_label"],
                    "level_key": level["level_key"], "level_label": level["label"], "rank": int(level["rank"]), "color": level["color"],
                    "matched": bool(result["matched"]), "eligible": bool(result["eligible"]), "reason": result["reason"], "checks": result["checks"],
                }
                evaluations.append(event)
                if not persist:
                    continue
                # An unavailable/insufficient metric is not a proof of recovery.
                # Freeze the durable state until the rule becomes evaluable again.
                if not result["eligible"]:
                    continue

                state = _state_row(runtime_con, rule["id"], scope["scope_type"], scope["scope_key"])
                first_match = float(state["first_match"]) if state and state["first_match"] is not None else None
                last_match = float(state["last_match"]) if state and state["last_match"] is not None else None
                clear_since = float(state["clear_since"]) if state and state["clear_since"] is not None else None
                cooldown_until = float(state["cooldown_until"] or 0) if state else 0.0
                last_incident_id = str(state["last_incident_id"] or "") if state else ""
                active = _load_active_incident(runtime_con, rule["id"], scope["scope_type"], scope["scope_key"])

                if result["matched"]:
                    if first_match is None:
                        first_match = clock
                    last_match = clock
                    clear_since = None
                    if active:
                        _update_incident(runtime_con, active["id"], scope, result, clock)
                        last_incident_id = active["id"]
                    elif clock >= cooldown_until and clock - first_match >= int(rule.get("min_duration_seconds") or 0):
                        last_incident_id = _open_incident(runtime_con, rule, scope, level, result, first_match, clock)
                else:
                    first_match = None
                    if active:
                        if clear_since is None:
                            clear_since = clock
                        if clock - clear_since >= int(rule.get("recovery_seconds") or 0):
                            cooldown_until = clock + int(rule.get("cooldown_seconds") or 0)
                            _recover_incident(runtime_con, active["id"], cooldown_until, clock, metrics=scope.get("metrics") or {})
                            last_incident_id = active["id"]
                            clear_since = None
                    else:
                        clear_since = None
                _save_state(runtime_con, rule["id"], scope["scope_type"], scope["scope_key"],
                            first_match=first_match, last_match=last_match, clear_since=clear_since,
                            cooldown_until=cooldown_until, last_incident_id=last_incident_id, clock=clock)
        if runtime_con is not None:
            runtime_con.commit()
    except BaseException:
        if persist and runtime_con is not None:
            import sys
            runtime_cm.__exit__(*sys.exc_info())
            runtime_con = None
        raise
    finally:
        if persist and runtime_con is not None:
            runtime_cm.__exit__(None, None, None)

    return {"generated_at": clock, "scopes": scopes, "evaluations": evaluations}


def _incident_category(incident):
    reasons=list((incident or {}).get("reasons") or [])
    metrics={str(x.get("metric") or "") for x in reasons if isinstance(x,dict)}
    name=_normalized_state_text((incident or {}).get("rule_name"))
    if "earliest_hold_start_seconds" in metrics or ("mise en attente" in name and ("10" in name or "preco" in name)):
        key="hold_early"
    elif metrics & {"max_hold_seconds","agents_on_hold","hold_percent"} or "hold" in name or "mise en attente" in name:
        key="hold"
    elif metrics & {"max_pause_lunch_seconds","agents_pause_lunch"} or "dejeuner" in name or "lunch" in name:
        key="pause_lunch"
    elif metrics & {"max_pause_coaching_seconds","agents_pause_coaching"} or "coaching" in name:
        key="pause_coaching"
    elif metrics & {"max_pause_general_seconds","agents_pause_general"} or "general break" in name or "general breack" in name:
        key="pause_general"
    elif metrics & {"max_pause_normal_seconds","agents_pause_normal","max_pause_seconds","agents_pause","pause_percent"} or "pause" in name:
        key="pause"
    elif metrics & {"max_offline_seconds","agents_offline"} or "deconnexion" in name or "offline" in name:
        key="offline"
    elif metrics & {"max_inactive_context_seconds","agents_inactive_context","inactive_context_percent"} or "contexte inactif" in name:
        key="inactive_context"
    elif metrics & {"max_wrap_seconds","agents_wrap","wrap_percent"} or "post-appel" in name or "post travail" in name:
        key="post_call"
    else:
        key="other"
    return key, INCIDENT_CATEGORY_LABELS[key]


def _decode_incident_row(row):
    d = dict(row)
    for key in ("reasons_json", "metrics_json", "contributor_agents_json"):
        try:
            default = "{}" if key == "metrics_json" else "[]"
            out_key = "contributors" if key == "contributor_agents_json" else key[:-5]
            d[out_key] = json.loads(d.pop(key) or default)
        except json.JSONDecodeError:
            d[out_key] = {} if key == "metrics_json" else []
    d["status_label"] = INCIDENT_STATUS_LABELS.get(str(d.get("status") or ""), str(d.get("status") or ""))
    category,category_label=_incident_category(d)
    d["category"]=category;d["category_label"]=category_label
    if str(d.get("scope_type") or "").upper()=="AGENT":
        d["agent"]=str(d.get("scope_key") or "")
        d["agent_name"]=str(d.get("scope_label") or d.get("scope_key") or "")
        for contributor in d.get("contributors") or []:
            if str(contributor.get("agent") or "")==d["agent"] and str(contributor.get("name") or "").strip():
                d["agent_name"]=str(contributor.get("name"));break
    else:
        d["agent"]="";d["agent_name"]=""
    start=float(d.get("triggered_at") or d.get("first_seen") or 0)
    end=float(d.get("recovered_at") or d.get("closed_at") or d.get("last_seen") or start)
    d["duration_seconds"]=round(max(0.0,end-start),1) if start else 0.0
    return d


def purge_incident_history(*, clock=None, retention_days=INCIDENT_HISTORY_RETENTION_DAYS, con=None):
    """Purge only resolved/closed incidents older than the configured retention.

    Active incidents are never removed. Event rows are deleted explicitly so
    retention remains correct even when SQLite foreign_keys is disabled.
    """
    import collection_store
    clock=time.time() if clock is None else float(clock)
    days=max(1,min(3650,int(retention_days or INCIDENT_HISTORY_RETENTION_DAYS)))
    cutoff=clock-(days*86400)
    own=con is None
    if own:
        collection_store.init(force=False)
        cm=collection_store.connect();con=cm.__enter__()
    try:
        ensure_runtime_schema(con)
        ids=[str(r[0]) for r in con.execute("""SELECT id FROM live_quality_incidents
            WHERE active=0 AND COALESCE(closed_at,recovered_at,last_seen,updated_at) < ?""",(cutoff,)).fetchall()]
        if ids:
            marks=','.join('?' for _ in ids)
            con.execute(f"DELETE FROM live_quality_incident_events WHERE incident_id IN ({marks})",ids)
            con.execute(f"UPDATE live_quality_rule_state SET last_incident_id=NULL WHERE last_incident_id IN ({marks})",ids)
            con.execute(f"DELETE FROM live_quality_incidents WHERE id IN ({marks})",ids)
        if own: con.commit()
        return len(ids)
    finally:
        if own: cm.__exit__(None,None,None)


def _purge_retention_once_per_day(con, clock):
    global _LAST_RETENTION_PURGE_DAY
    day=int(float(clock)//86400)
    if _LAST_RETENTION_PURGE_DAY==day:return 0
    count=purge_incident_history(clock=clock,con=con)
    _LAST_RETENTION_PURGE_DAY=day
    return count

def incident_snapshot(*, active_only=False, limit=200, start_ts=None, end_ts=None):
    import collection_store
    collection_store.init(force=False)
    limit = max(1, min(10000, int(limit or 200)))
    clauses=[];params=[]
    if active_only:clauses.append("active=1")
    if start_ts is not None:
        clauses.append("triggered_at>=?");params.append(float(start_ts))
    if end_ts is not None:
        clauses.append("triggered_at<?");params.append(float(end_ts))
    where=("WHERE "+" AND ".join(clauses)) if clauses else ""
    with collection_store.connect() as con:
        ensure_runtime_schema(con)
        rows = con.execute(
            f"""SELECT * FROM live_quality_incidents {where}
                ORDER BY triggered_at DESC,level_rank DESC,last_seen DESC LIMIT ?""", (*params,limit)
        ).fetchall()
        out = [_decode_incident_row(row) for row in rows]
    return out


def incident_stats(incidents):
    """Aggregate only persisted Live-quality incidents already filtered for access."""
    from nelyio_time import local_day
    rows=list(incidents or [])
    categories={key:0 for key in INCIDENT_CATEGORY_ORDER}
    daily={}
    agents={}
    collective=0
    for inc in rows:
        key=str(inc.get("category") or "other")
        if key not in categories:key="other"
        categories[key]+=1
        try:day=local_day(float(inc.get("triggered_at") or inc.get("first_seen") or 0))
        except Exception:day=""
        if day:daily[day]=daily.get(day,0)+1
        if str(inc.get("scope_type") or "").upper()!="AGENT":
            collective+=1;continue
        aid=str(inc.get("agent") or inc.get("scope_key") or "").strip()
        if not aid:continue
        item=agents.setdefault(aid,{"agent":aid,"name":str(inc.get("agent_name") or inc.get("scope_label") or aid),"total":0,"counts":{k:0 for k in INCIDENT_CATEGORY_ORDER},"last_incident_at":None})
        item["total"]+=1;item["counts"][key]=item["counts"].get(key,0)+1
        ts=float(inc.get("triggered_at") or inc.get("first_seen") or 0)
        if not item["last_incident_at"] or ts>item["last_incident_at"]:item["last_incident_at"]=ts
    active_categories=[{"key":k,"label":INCIDENT_CATEGORY_LABELS[k],"count":categories[k]} for k in INCIDENT_CATEGORY_ORDER if categories[k]]
    agent_rows=sorted(agents.values(),key=lambda x:(-int(x["total"]),str(x["name"]).casefold(),str(x["agent"])))
    return {
        "total":len(rows),
        "agent_incidents":sum(int(x["total"]) for x in agent_rows),
        "collective_incidents":collective,
        "categories":active_categories,
        "agents":agent_rows,
        "daily":[{"day":k,"count":daily[k]} for k in sorted(daily)],
        "retention_days":INCIDENT_HISTORY_RETENTION_DAYS,
    }


def _decode_incident_event(row):
    d = dict(row)
    try:
        d["snapshot"] = json.loads(d.pop("snapshot_json") or "{}")
    except json.JSONDecodeError:
        d["snapshot"] = {}
    d["from_status_label"] = INCIDENT_STATUS_LABELS.get(str(d.get("from_status") or ""), str(d.get("from_status") or ""))
    d["to_status_label"] = INCIDENT_STATUS_LABELS.get(str(d.get("to_status") or ""), str(d.get("to_status") or ""))
    return d


def _metric_value(snapshot, key):
    metric = (snapshot or {}).get(key) or {}
    value = metric.get("value") if isinstance(metric, dict) else None
    return value, metric if isinstance(metric, dict) else {}


def _before_after_from_events(incident, events):
    actions = [e for e in events if e.get("event_type") == "ACTION_DEMARREE"]
    if not actions:
        return None
    action = actions[-1]
    recoveries = [e for e in events if e.get("event_type") == "RETOUR_NORMAL_AUTOMATIQUE" and float(e.get("created_at") or 0) >= float(action.get("created_at") or 0)]
    recovery = recoveries[0] if recoveries else None
    before = action.get("snapshot") or {}
    after = (recovery or {}).get("snapshot") or {}
    reason_keys = []
    for reason in incident.get("reasons") or []:
        key = str(reason.get("metric") or "")
        if key and key not in reason_keys:
            reason_keys.append(key)
    for key in ("agents_available", "agents_connected", "agents_in_call", "current_calls", "max_wrap_seconds", "max_pause_seconds"):
        if key not in reason_keys:
            reason_keys.append(key)
    changes = []
    for key in reason_keys[:12]:
        before_value, before_meta = _metric_value(before, key)
        after_value, after_meta = _metric_value(after, key)
        if before_value is None and after_value is None:
            continue
        meta = METRICS.get(key, {})
        delta = None
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            delta = round(float(after_value) - float(before_value), 2)
        changes.append({
            "metric": key,
            "label": meta.get("label", key),
            "unit": meta.get("unit", ""),
            "before": before_value,
            "after": after_value,
            "delta": delta,
            "before_quality": before_meta.get("quality") or "unavailable",
            "after_quality": after_meta.get("quality") or "unavailable",
        })
    recovered_after_action = bool(recovery)
    return {
        "action": {
            "text": action.get("action_text") or "",
            "comment": action.get("comment") or "",
            "actor": action.get("actor") or "",
            "at": action.get("created_at"),
        },
        "recovery": {
            "at": recovery.get("created_at") if recovery else None,
            "actor": recovery.get("actor") if recovery else None,
        },
        "before": before,
        "after": after if recovery else None,
        "changes": changes,
        "recovered_after_action": recovered_after_action,
        "observation": "Amélioration observée après l’action." if recovered_after_action else "Action enregistrée ; retour à la normale non encore observé.",
        "causality_note": "La chronologie montre une évolution après l’action ; elle ne prouve pas que l’action a causé cette évolution.",
    }


def incident_detail(incident_id):
    import collection_store
    collection_store.init(force=False)
    incident_id = str(incident_id or "").strip()
    if not incident_id:
        raise ValueError("Identifiant incident requis")
    with collection_store.connect() as con:
        ensure_runtime_schema(con)
        row = con.execute("SELECT * FROM live_quality_incidents WHERE id=?", (incident_id,)).fetchone()
        if not row:
            raise KeyError("Incident Live introuvable")
        incident = _decode_incident_row(row)
        events = [_decode_incident_event(x) for x in con.execute(
            "SELECT * FROM live_quality_incident_events WHERE incident_id=? ORDER BY created_at,id", (incident_id,)
        ).fetchall()]
    status = str(incident.get("status") or "")
    allowed = list(INCIDENT_FORWARD_TRANSITIONS.get(status, ()))
    return {
        "incident": incident,
        "events": events,
        "allowed_transitions": allowed,
        "before_after": _before_after_from_events(incident, events),
        "lifecycle": [
            {"status": key, "label": INCIDENT_STATUS_LABELS[key], "reached": any(e.get("to_status") == key for e in events) or status == key}
            for key in INCIDENT_STATUSES
        ],
    }


def incident_action(incident_id, *, action, actor, target_status=None, comment="", action_text="", clock=None):
    """Apply a user lifecycle action without overriding automatic signal recovery."""
    import collection_store
    collection_store.init(force=False)
    clock = time.time() if clock is None else float(clock)
    incident_id = str(incident_id or "").strip()
    actor = _clean_label(actor or "SYSTEM", "Utilisateur")
    action = str(action or "transition").strip().lower()
    comment = str(comment or "").strip()[:4000]
    action_text = str(action_text or "").strip()[:4000]
    with collection_store.connect() as con:
        ensure_runtime_schema(con)
        row = con.execute("SELECT * FROM live_quality_incidents WHERE id=?", (incident_id,)).fetchone()
        if not row:
            raise KeyError("Incident Live introuvable")
        incident = _decode_incident_row(row)
        current = str(incident.get("status") or "NOUVEAU")
        if action == "comment":
            if not comment:
                raise ValueError("Commentaire requis")
            _insert_incident_event(con, incident_id, "COMMENTAIRE", actor=actor, from_status=current, to_status=current,
                                   comment=comment, snapshot=incident.get("metrics") or {}, clock=clock)
            con.execute("UPDATE live_quality_incidents SET updated_at=? WHERE id=?", (clock, incident_id))
        elif action == "transition":
            target = str(target_status or "").strip().upper()
            allowed = INCIDENT_FORWARD_TRANSITIONS.get(current, ())
            if target not in allowed:
                raise ValueError(f"Transition {current} -> {target or '?'} non autorisée")
            if target == "ACTION_EN_COURS" and not action_text:
                raise ValueError("Décrivez l’action engagée avant de passer à ACTION EN COURS")
            if target == "CLOTURE" and current != "RETABLI":
                raise ValueError("Un incident ne peut être clôturé qu’après retour à la normale")
            if target in {"VU", "EN_INVESTIGATION", "ACTION_EN_COURS"} and not int(incident.get("active") or 0):
                raise ValueError("Cet incident n’est plus actif")
            event_type = "ACTION_DEMARREE" if target == "ACTION_EN_COURS" else ("CLOTURE_MANUELLE" if target == "CLOTURE" else "TRANSITION_MANUELLE")
            con.execute(
                "UPDATE live_quality_incidents SET status=?,closed_at=CASE WHEN ?='CLOTURE' THEN ? ELSE closed_at END,updated_at=? WHERE id=?",
                (target, target, clock, clock, incident_id),
            )
            _insert_incident_event(
                con, incident_id, event_type, actor=actor, from_status=current, to_status=target,
                comment=comment, action_text=action_text, snapshot=incident.get("metrics") or {}, clock=clock,
            )
        else:
            raise ValueError("Action incident Live inconnue")
    return incident_detail(incident_id)


CENTER_SCOPE_METRICS = (
    "agents_connected", "agents_available", "agents_in_call", "agents_wrap", "agents_pause", "current_calls",
)
CENTER_GLOBAL_METRICS = (
    "agents_connected", "agents_available", "agents_in_call", "agents_wrap", "agents_pause",
    "agents_offline", "available_percent", "in_call_percent", "wrap_percent", "pause_percent",
    "current_calls", "max_wrap_seconds", "max_pause_seconds", "max_offline_seconds",
    "waiting_now", "oldest_waiting_seconds", "median_wait_seconds", "p90_wait_seconds",
    "abandon_rate", "qos",
)


def _quality_engine_status(clock):
    """Read the central Live-worker heartbeat without touching business storage."""
    try:
        from service_mode import external_services_enabled
        if not external_services_enabled():
            return {
                "healthy": None,
                "state": "integrated",
                "label": "Mode intégré — heartbeat Qualité séparé non disponible",
                "last_tick": None,
                "last_tick_age_seconds": None,
                "error": "",
            }
        import service_state
        status = service_state.public_status()
        worker = next((x for x in status.get("services", []) if x.get("service") == "live"), None)
        if not worker:
            return {"healthy": False, "state": "not_started", "label": "Moteur Qualité non démarré", "last_tick": None, "last_tick_age_seconds": None, "error": "live_worker_missing"}
        detail = dict((worker.get("detail") or {}).get("quality") or {})
        last_tick = detail.get("last_tick")
        try:
            tick_age = max(0.0, float(clock) - float(last_tick)) if last_tick is not None else None
        except (TypeError, ValueError):
            tick_age = None
        error = str(detail.get("error") or "")
        worker_ok = bool(worker.get("healthy"))
        healthy = bool(worker_ok and last_tick is not None and tick_age is not None and tick_age <= 20 and not error)
        if healthy:
            label = "Moteur Qualité actif"
        elif not worker_ok:
            label = "Worker Live indisponible"
        elif error:
            label = "Moteur Qualité en erreur"
        elif last_tick is None:
            label = "Aucun cycle Qualité confirmé"
        else:
            label = "Cycle Qualité en retard"
        return {
            "healthy": healthy,
            "state": str(worker.get("state") or "unknown"),
            "label": label,
            "last_tick": last_tick,
            "last_tick_age_seconds": round(tick_age, 1) if tick_age is not None else None,
            "scope_count": detail.get("scope_count"),
            "evaluation_count": detail.get("evaluation_count"),
            "error": error,
            "worker_age_seconds": worker.get("age_seconds"),
            "build_match": worker.get("build_match"),
        }
    except Exception:
        return {"healthy": None, "state": "unavailable", "label": "État du moteur Qualité indisponible", "last_tick": None, "last_tick_age_seconds": None, "error": "status_unavailable"}


def _rule_applies_to_scope(rule, scope):
    if str(rule.get("scope_type") or "") != str(scope.get("scope_type") or ""):
        return False
    targets = {str(x).casefold() for x in rule_target_keys(rule)}
    if not targets:
        return True
    return bool(targets.intersection({
        str(scope.get("scope_key") or "").casefold(),
        str(scope.get("scope_label") or "").casefold(),
    }))


def _compact_metric(key, metric):
    meta = METRICS.get(key, {})
    metric = dict(metric or _unavailable("metric_missing"))
    return {
        "key": key,
        "label": meta.get("label", key),
        "unit": meta.get("unit", ""),
        "availability": meta.get("availability", "live"),
        "value": metric.get("value"),
        "quality": metric.get("quality") or "unavailable",
        "source": metric.get("source") or "",
        "reason": metric.get("reason") or "",
        "sample_size": metric.get("sample_size"),
        "freshness_seconds": metric.get("freshness_seconds"),
    }


def _incident_attention(incidents, clock):
    out = []
    for incident in incidents:
        item = dict(incident)
        try:
            item["duration_seconds"] = round(max(0.0, float(clock) - float(item.get("first_seen") or clock)), 1)
        except (TypeError, ValueError):
            item["duration_seconds"] = None
        reasons = list(item.get("reasons") or [])
        item["matched_reasons"] = [x for x in reasons if x.get("usable") and x.get("passed")]
        out.append(item)
    return out


def _center_status(operational, data_quality, engine, active_rule_count, health):
    """Status shown at the top of the cockpit. Never return green on unknown data."""
    if data_quality.get("quality") != "reliable":
        label = "COLLECTE INTERROMPUE"
        state = str((health or {}).get("state") or "")
        if state == "waiting":
            label = "EN ATTENTE DE DONNÉES"
        elif state == "inactive":
            label = "COLLECTE NON DÉMARRÉE"
        return {"level_key": "COLLECTE_INTERROMPUE", "label": label, "rank": 0, "color": "#667085", "reason": "live_data_not_reliable", "kind": "data_quality"}
    if engine.get("healthy") is False:
        return {"level_key": "SIGNALISATION_INDISPONIBLE", "label": "SIGNALISATION INDISPONIBLE", "rank": 0, "color": "#667085", "reason": "quality_engine_unhealthy", "kind": "engine"}
    if int(active_rule_count or 0) <= 0:
        return {"level_key": "INDETERMINE", "label": "INDÉTERMINÉ", "rank": 0, "color": "#667085", "reason": "no_active_rules", "kind": "configuration"}
    return dict(operational, kind="operational")


def quality_center(snapshot, *, clock=None, levels=None, rules=None, incidents=None, operational=None, data_quality=None):
    """Build the read-only Phase 3 cockpit from one already-loaded Live snapshot."""
    clock = time.time() if clock is None else float(clock)
    levels = [dict(x) for x in (levels if levels is not None else load_levels(include_disabled=True))]
    rules = [dict(x) for x in (rules if rules is not None else load_rules(include_disabled=False)) if x.get("enabled", 1)]
    incidents = list(incidents if incidents is not None else incident_snapshot(active_only=True, limit=200))
    level_map = _level_map(levels)
    fallback = next((x for x in levels if x.get("is_fallback")), min(levels, key=lambda x: int(x.get("rank") or 0), default={
        "level_key": "NORMAL", "label": "NORMAL", "rank": 100, "color": "#24634A"
    }))
    health = dict((snapshot or {}).get("health") or {})
    fresh = bool(health.get("fresh"))
    scopes = build_scopes(snapshot or {})
    global_scope = next((x for x in scopes if x.get("scope_type") == "GLOBAL"), {"metrics": {}})
    by_scope = {}
    for incident in incidents:
        by_scope.setdefault((str(incident.get("scope_type") or ""), str(incident.get("scope_key") or "")), []).append(incident)

    scope_rows = []
    for scope in scopes:
        scope_type = str(scope.get("scope_type") or "")
        if scope_type in {"GLOBAL", "AGENT"}:
            continue
        applicable = [r for r in rules if _rule_applies_to_scope(r, scope)]
        active = by_scope.get((scope_type, str(scope.get("scope_key") or "")), [])
        strongest = max(active, key=lambda x: int(x.get("level_rank") or 0), default=None)
        if not fresh:
            status = {"level_key": "INDETERMINE", "label": "INDÉTERMINÉ", "rank": 0, "color": "#667085", "reason": "live_data_not_fresh"}
        elif int(scope.get("observed_agent_count") or scope.get("agent_count") or 0)==0 and str(scope.get("coverage_basis") or "").startswith("configured"):
            status = {"level_key": "NON_OBSERVE", "label": "NON OBSERVÉ", "rank": 0, "color": "#667085", "reason": "no_live_state_observed"}
        elif strongest:
            status = {"level_key": strongest.get("level_key"), "label": strongest.get("level_label"), "rank": int(strongest.get("level_rank") or 0), "color": strongest.get("color") or "#667085", "reason": "active_incident"}
        elif applicable:
            status = {"level_key": fallback.get("level_key"), "label": fallback.get("label"), "rank": int(fallback.get("rank") or 0), "color": fallback.get("color") or "#667085", "reason": "no_rule_triggered"}
        else:
            status = {"level_key": "NON_SURVEILLE", "label": "NON SURVEILLÉ", "rank": 0, "color": "#667085", "reason": "no_applicable_rule"}
        metrics = scope.get("metrics") or {}
        scope_rows.append({
            "scope_type": scope_type,
            "scope_key": scope.get("scope_key"),
            "scope_label": scope.get("scope_label"),
            "identity_quality": scope.get("identity_quality"),
            "agent_count": int(scope.get("agent_count") or 0),
            "observed_agent_count": int(scope.get("observed_agent_count") or scope.get("agent_count") or 0),
            "configured_agent_count": int(scope.get("configured_agent_count") or scope.get("agent_count") or 0),
            "coverage_basis": scope.get("coverage_basis") or "live",
            "monitored": bool(applicable),
            "rule_count": len(applicable),
            "incident_count": len(active),
            "status": status,
            "line_ids": [str(x) for x in (scope.get("line_ids") or []) if str(x)],
            "native_calls": dict(scope.get("native_calls") or {}),
            "metrics": {key: _compact_metric(key, metrics.get(key)) for key in CENTER_SCOPE_METRICS},
        })
    order = {"SERVICE": 0, "GROUP": 1, "CAMPAIGN": 2, "QUEUE": 3}
    scope_rows.sort(key=lambda x: (order.get(x["scope_type"], 9), -int(x["status"].get("rank") or 0), str(x.get("scope_label") or "").casefold()))

    counts = {}
    for incident in incidents:
        key = str(incident.get("level_key") or "INCONNU")
        entry = counts.setdefault(key, {
            "level_key": key,
            "label": incident.get("level_label") or key,
            "rank": int(incident.get("level_rank") or 0),
            "color": incident.get("color") or "#667085",
            "count": 0,
        })
        entry["count"] += 1
    signal_counts = sorted(counts.values(), key=lambda x: (-x["rank"], x["label"]))
    engine = _quality_engine_status(clock)
    if operational is None:
        strongest = max(incidents, key=lambda x: int(x.get("level_rank") or 0), default=None)
        operational = {
            "level_key": strongest.get("level_key") if strongest else fallback.get("level_key"),
            "label": strongest.get("level_label") if strongest else fallback.get("label"),
            "rank": int(strongest.get("level_rank") if strongest else fallback.get("rank") or 0),
            "color": strongest.get("color") if strongest else fallback.get("color"),
            "reason": "active_incident" if strongest else "no_active_incident",
        }
    if data_quality is None:
        if not health:
            data_quality = {"quality": "unavailable", "label": "Données indisponibles", "color": "#667085"}
        elif fresh:
            data_quality = {"quality": "reliable", "label": "Données fraîches", "color": "#2F6FED", "freshness_seconds": health.get("last_response_age")}
        elif health.get("active"):
            data_quality = {"quality": "partial", "label": "Données anciennes / collecte dégradée", "color": "#667085", "freshness_seconds": health.get("last_response_age")}
        else:
            data_quality = {"quality": "unavailable", "label": "Collecte interrompue", "color": "#667085", "freshness_seconds": health.get("last_response_age")}

    scope_counts = {}
    for scope_type in ("SERVICE", "GROUP", "CAMPAIGN", "QUEUE"):
        rows = [x for x in scope_rows if x["scope_type"] == scope_type]
        scope_counts[scope_type] = {
            "total": len(rows),
            "monitored": sum(1 for x in rows if x["monitored"]),
            "with_incident": sum(1 for x in rows if x["incident_count"]),
        }
    global_metrics = {key: _compact_metric(key, (global_scope.get("metrics") or {}).get(key)) for key in CENTER_GLOBAL_METRICS}
    agent_signals={}
    for incident in incidents:
        if str(incident.get("scope_type") or "").upper()!="AGENT":
            continue
        key=str(incident.get("scope_key") or "")
        if not key: continue
        current=agent_signals.get(key)
        if current is None or int(incident.get("level_rank") or 0)>int(current.get("level_rank") or 0):
            agent_signals[key]={
                "incident_id":incident.get("id"),"rule_id":incident.get("rule_id"),"rule_name":incident.get("rule_name"),
                "level_key":incident.get("level_key"),"level_label":incident.get("level_label"),
                "level_rank":int(incident.get("level_rank") or 0),"color":incident.get("color") or "#667085",
                "triggered_at":incident.get("triggered_at"),"status":incident.get("status"),
            }
    return {
        "status": _center_status(operational, data_quality, engine, len(rules), health),
        "last_operational_status": operational,
        "data_quality": data_quality,
        "engine": engine,
        "active_rule_count": len(rules),
        "active_incident_count": len(incidents),
        "signal_counts": signal_counts,
        "attention": _incident_attention(incidents, clock),
        "agent_signals": agent_signals,
        "incident_history_retention_days": INCIDENT_HISTORY_RETENTION_DAYS,
        "global_metrics": global_metrics,
        "global_native_calls": dict(global_scope.get("native_calls") or {}),
        "scopes": scope_rows,
        "scope_counts": scope_counts,
        "metric_catalog": metric_catalog(),
        "status_basis": "configured_rules_and_certified_live_metrics",
        "limitations": [
            "NORMAL signifie qu'aucune règle Qualité Live applicable n'est déclenchée sur des données fraîches ; ce n'est pas une garantie qu'aucun autre problème n'existe.",
            "Les compteurs journaliers Reçus/Traités/Abandonnés/QoS sont exposés quand UpQuH est reçu; l'attente P90/médiane reste indisponible sans source Hermes certifiée.",
            "Les campagnes Live utilisent le libellé réellement observé dans Hermes ; elles ne remplacent jamais la définition des groupes par les files configurées.",
        ],
    }


def quality_summary(snapshot=None, *, clock=None):
    """Read-only payload for /api/live/supervision; no incident writes here."""
    clock = time.time() if clock is None else float(clock)
    levels = load_levels(include_disabled=True)
    rules = load_rules(include_disabled=False)
    fallback = next((x for x in levels if x.get("is_fallback")), min(levels, key=lambda x: int(x.get("rank") or 0), default={
        "level_key": "NORMAL", "label": "NORMAL", "rank": 100, "color": "#24634A"
    }))
    incidents = incident_snapshot(active_only=True, limit=200)
    strongest = max(incidents, key=lambda x: int(x.get("level_rank") or 0), default=None)
    operational = {
        "level_key": strongest.get("level_key") if strongest else fallback.get("level_key"),
        "label": strongest.get("level_label") if strongest else fallback.get("label"),
        "rank": int(strongest.get("level_rank") if strongest else fallback.get("rank") or 0),
        "color": strongest.get("color") if strongest else fallback.get("color"),
        "reason": "active_incident" if strongest else "no_active_incident",
    }
    health = dict((snapshot or {}).get("health") or {})
    if not health:
        data_quality = {"quality": "unavailable", "label": "Données indisponibles", "color": "#667085"}
    elif health.get("fresh"):
        data_quality = {"quality": "reliable", "label": "Données fraîches", "color": "#2F6FED", "freshness_seconds": health.get("last_response_age")}
    elif health.get("active"):
        data_quality = {"quality": "partial", "label": "Données anciennes / collecte dégradée", "color": "#667085", "freshness_seconds": health.get("last_response_age")}
    else:
        data_quality = {"quality": "unavailable", "label": "Collecte interrompue", "color": "#667085", "freshness_seconds": health.get("last_response_age")}
    center = quality_center(snapshot or {}, clock=clock, levels=levels, rules=rules, incidents=incidents,
                            operational=operational, data_quality=data_quality)
    return {
        "generated_at": clock,
        "operational_status": operational,
        "data_quality": data_quality,
        "active_incident_count": len(incidents),
        "active_incidents": incidents,
        "center": center,
    }


def tick(*, clock=None):
    """Central-worker entry point. Exactly one Live service should call this."""
    clock = time.time() if clock is None else float(clock)
    import collection_store
    snapshot = collection_store.live_supervision_snapshot(clock=clock, include_quality=False)
    return process_snapshot(snapshot, clock=clock, persist=True)
