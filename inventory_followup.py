"""Inventory follow-up: validated, data-only rules shared by SQL and the UI.

No schema migration, no writes at import time. Legacy settings are read until an
administrator explicitly saves a v2 policy. Raw JSON is a SQL argument so edits
are visible even on an already-open connection; only parsing is cached.
"""
from __future__ import annotations
from functools import lru_cache
import hashlib
import json
import re

POLICY_KEY = "inventory_followup_policy_v2"
MAX_CATEGORIES = 32
MAX_RANGES = 32
MAX_DAYS = 36500
COLORS = ("green", "yellow", "orange", "red", "blue", "purple", "gray")
ADMIN_STATES = ("EN_SERVICE", "STOCK", "REPARATION", "PERDU", "REFORME")
BASE_CATEGORIES = (
    ("EN_SERVICE", "\u00c0 jour", "green"),
    ("PAS_A_JOUR", "Pas \u00e0 jour", "yellow"),
    ("RETARD_7J", "Retard", "orange"),
    ("CRITIQUE", "Critique", "red"),
    ("STOCK", "En stock", "blue"),
    ("REPARATION", "R\u00e9paration", "orange"),
    ("KO", "KO / perdu", "red"),
    ("REFORME", "R\u00e9form\u00e9", "gray"),
)


def legacy_policy(config: dict) -> dict:
    warning, late = config["warning_days"], config["late_days"]
    return {
        "version": 2,
        "categories": [{"id": k, "label": config["labels"].get(k, label), "color": color}
                       for k, label, color in BASE_CATEGORIES],
        "ranges": [
            {"min_days": 0, "max_days": 0, "status": "EN_SERVICE"},
            {"min_days": 1, "max_days": warning, "status": "PAS_A_JOUR"},
            {"min_days": warning + 1, "max_days": late, "status": "RETARD_7J"},
            {"min_days": late + 1, "max_days": None, "status": "CRITIQUE"},
        ],
        "never_seen": "CRITIQUE",
        "admin_overrides": {
            "EN_SERVICE": None,
            "STOCK": "STOCK" if config.get("override_stock", True) else None,
            "REPARATION": "REPARATION" if config.get("override_repair", True) else None,
            "PERDU": "KO" if config.get("override_lost", True) else None,
            "REFORME": "REFORME" if config.get("override_retired", True) else None,
        },
    }


def normalize_policy(data: dict) -> dict:
    """Reject ambiguous ranges, dangling references and executable/style payloads."""
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 2:
        raise ValueError("Version des r\u00e8gles de suivi invalide.")
    categories = data.get("categories")
    if not isinstance(categories, list) or not 1 <= len(categories) <= MAX_CATEGORIES:
        raise ValueError(f"Choisissez entre 1 et {MAX_CATEGORIES} libell\u00e9s de suivi.")
    clean, keys, labels = [], set(), set()
    for item in categories:
        if not isinstance(item, dict):
            raise ValueError("Libell\u00e9 de suivi invalide.")
        key, label, color = item.get("id"), item.get("label"), item.get("color")
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", key) or key in keys:
            raise ValueError("Identifiant de suivi invalide ou dupliqu\u00e9.")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 60 or any(ord(c) < 32 for c in label):
            raise ValueError("Chaque libell\u00e9 doit contenir de 1 \u00e0 60 caract\u00e8res.")
        label = label.strip()
        if label.casefold() in labels:
            raise ValueError("Deux libell\u00e9s de suivi ne peuvent pas porter le m\u00eame nom.")
        if color not in COLORS:
            raise ValueError("Couleur de suivi inconnue.")
        keys.add(key); labels.add(label.casefold())
        clean.append({"id": key, "label": label, "color": color})
    if not {x[0] for x in BASE_CATEGORIES}.issubset(keys):
        raise ValueError("Les cat\u00e9gories historiques doivent \u00eatre conserv\u00e9es (elles peuvent \u00eatre renomm\u00e9es).")
    ranges = data.get("ranges")
    if not isinstance(ranges, list) or not 1 <= len(ranges) <= MAX_RANGES:
        raise ValueError(f"Choisissez entre 1 et {MAX_RANGES} tranches de jours.")
    clean_ranges, next_day = [], 0
    for pos, item in enumerate(ranges):
        if not isinstance(item, dict):
            raise ValueError("Tranche de suivi invalide.")
        start, end, key = item.get("min_days"), item.get("max_days"), item.get("status")
        if type(start) is not int or start != next_day or not 0 <= start <= MAX_DAYS:
            raise ValueError(f"La tranche {pos + 1} doit commencer au jour {next_day}, sans trou ni chevauchement.")
        if key not in keys:
            raise ValueError("Une tranche utilise un libell\u00e9 inexistant.")
        if pos == len(ranges) - 1:
            if end is not None:
                raise ValueError("La derni\u00e8re tranche doit \u00eatre sans limite.")
        elif type(end) is not int or not start <= end < MAX_DAYS:
            raise ValueError(f"Fin de tranche {pos + 1} invalide (jours entiers, de {start} \u00e0 {MAX_DAYS - 1}).")
        clean_ranges.append({"min_days": start, "max_days": end, "status": key})
        next_day = (end + 1) if end is not None else MAX_DAYS + 1
    never = data.get("never_seen")
    if never not in keys:
        raise ValueError("Choisissez un libell\u00e9 pour les postes sans diagnostic exploitable.")
    mappings = data.get("admin_overrides")
    if not isinstance(mappings, dict) or set(mappings) != set(ADMIN_STATES):
        raise ValueError("Les cinq \u00e9tats administratifs doivent \u00eatre renseign\u00e9s.")
    if any(value is not None and value not in keys for value in mappings.values()):
        raise ValueError("Un \u00e9tat administratif utilise un libell\u00e9 inexistant.")
    return {"version": 2, "categories": clean, "ranges": clean_ranges,
            "never_seen": never, "admin_overrides": {k: mappings[k] for k in ADMIN_STATES}}


@lru_cache(maxsize=64)
def _parsed_policy(raw: str) -> dict | None:
    if not raw or len(raw) > 65536:
        return None
    try:
        return normalize_policy(json.loads(raw))
    except (ValueError, TypeError, KeyError, RecursionError):
        return None


def evaluate_policy(policy: dict, days: int | None, admin_status: str = "EN_SERVICE") -> str:
    """Precedence: administrative override -> missing date -> inclusive day range."""
    override = policy["admin_overrides"].get(admin_status)
    if override:
        return override
    if days is None:
        return policy["never_seen"]
    days = max(0, int(days))
    for item in policy["ranges"]:
        if days >= item["min_days"] and (item["max_days"] is None or days <= item["max_days"]):
            return item["status"]
    # Normalized policies cover all non-negative ages.
    return policy["never_seen"]


def followup_sql(admin_status, days, raw):
    policy = _parsed_policy(raw) if isinstance(raw, str) else None
    return evaluate_policy(policy, days, admin_status) if policy else None


def enrich_config(config: dict, settings: dict) -> dict:
    raw = settings.get(POLICY_KEY, "")
    policy = _parsed_policy(raw) if isinstance(raw, str) else None
    # Copy before exposing: cached structures must never be mutated by a caller.
    policy = json.loads(json.dumps(policy)) if policy else legacy_policy(config)
    config["policy"] = policy
    config["customized"] = bool(raw and _parsed_policy(raw))
    config["colors"] = {item["id"]: item["color"] for item in policy["categories"]}
    config["labels"].update({item["id"]: item["label"] for item in policy["categories"]})
    config["revision"] = hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    if raw and not _parsed_policy(raw):
        config["warning"] = "R\u00e8gles personnalis\u00e9es invalides : les anciens seuils restent appliqu\u00e9s. V\u00e9rifiez puis enregistrez les r\u00e8gles."
    return config
