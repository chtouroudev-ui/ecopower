"""Flexible Support-technique priority policy engine.

The Administration DB owns the policy. Support calculations only read it and
fall back to deterministic defaults if the Administration DB is unavailable.

v41 keeps the legacy threshold columns for backward compatibility, but the
actual rule engine uses ``conditions_json``.  This lets administrators create,
rename and delete levels, choose the fallback label, choose a color, and build
conditions with several metrics/operators without changing Python code.
"""
from pathlib import Path
import json
import re
import db_compat as sqlite3

import supervision_context as ctx

OPERATORS = (">", ">=", "<", "<=", "==", "!=")
COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# key -> metadata used by both the evaluator and the Administration UI.
METRICS = {
    "disconnects_per_day": {"label": "Déconnexions / jour couvert", "unit": "/j", "min": 0, "max": 10000},
    "disconnects_per_affected_day": {"label": "Déconnexions / jour touché", "unit": "/j touché", "min": 0, "max": 10000},
    "disconnects_total": {"label": "Déconnexions totales", "unit": "", "min": 0, "max": 1000000},
    "disconnects_during_call": {"label": "Déconnexions pendant appel", "unit": "", "min": 0, "max": 1000000},
    "disconnects_during_call_per_affected_day": {"label": "Coupures en appel / jour touché", "unit": "/j touché", "min": 0, "max": 10000},
    "call_percent": {"label": "% des déconnexions pendant appel", "unit": "%", "min": 0, "max": 100},
    "affected_days": {"label": "Jours touchés", "unit": "j", "min": 0, "max": 3660},
    "affected_days_percent": {"label": "% de jours sélectionnés touchés", "unit": "%", "min": 0, "max": 100},
    "lost_minutes_total": {"label": "Temps perdu total", "unit": "min", "min": 0, "max": 10000000},
    "lost_minutes_per_day": {"label": "Temps perdu / jour couvert", "unit": "min/j", "min": 0, "max": 1000000},
    "lost_minutes_per_affected_day": {"label": "Temps perdu / jour touché", "unit": "min/j touché", "min": 0, "max": 1000000},
    "avg_disconnect_seconds": {"label": "Durée moyenne d'une déconnexion", "unit": "s", "min": 0, "max": 1000000},
    "median_disconnect_seconds": {"label": "Durée médiane d'une déconnexion", "unit": "s", "min": 0, "max": 1000000},
    "max_disconnect_seconds": {"label": "Déconnexion la plus longue", "unit": "s", "min": 0, "max": 1000000},
    "critical_disconnects": {"label": "Déconnexions critiques", "unit": "", "min": 0, "max": 1000000},
    "critical_percent": {"label": "% de déconnexions critiques", "unit": "%", "min": 0, "max": 100},
    "collective_disconnects": {"label": "Déconnexions dans un incident collectif", "unit": "", "min": 0, "max": 1000000},
    "collective_percent": {"label": "% de déconnexions dans un incident collectif", "unit": "%", "min": 0, "max": 100},
    "technical_score": {"label": "Score technique", "unit": "pts", "min": 0, "max": 1000000},
    "technical_disconnects": {"label": "Déconnexions techniques individuelles", "unit": "", "min": 0, "max": 1000000},
    "technical_disconnects_per_worked_day": {"label": "Déconnexions techniques / jour travaillé", "unit": "/j travaillé", "min": 0, "max": 100000},
    "technical_in_call": {"label": "Coupures techniques pendant appel", "unit": "", "min": 0, "max": 1000000},
    "technical_in_call_per_worked_day": {"label": "Coupures en appel / jour travaillé", "unit": "/j travaillé", "min": 0, "max": 100000},
    "worked_days": {"label": "Jours réellement travaillés", "unit": "j", "min": 0, "max": 3660},
    "affected_worked_days_percent": {"label": "% des jours travaillés touchés", "unit": "%", "min": 0, "max": 100},
    "bursts_30m": {"label": "Séries de coupures rapprochées", "unit": "", "min": 0, "max": 1000000},
    "bursts_per_worked_day": {"label": "Séries rapprochées / jour travaillé", "unit": "/j travaillé", "min": 0, "max": 100000},
    "probable_closures": {"label": "Fermetures application / pauses probables", "unit": "", "min": 0, "max": 1000000},
    "technical_lost_minutes_per_affected_day": {"label": "Temps perdu technique / jour touché", "unit": "min/j touché", "min": 0, "max": 1000000},
}

LEGACY_FIELDS = (
    "disconnects_per_day", "call_percent", "affected_days_percent", "lost_minutes_per_day"
)

DEFAULT_POLICIES = [
    # v41 defaults: the event classifier + scoring engine produces a transparent
    # technical_score.  Priority labels remain fully configurable here.
    dict(priority="CRITIQUE", rank=500, match_mode="ANY",
         disconnects_per_day=None, call_percent=None, affected_days_percent=None, lost_minutes_per_day=None,
         color="#B42318", is_fallback=0, enabled=1,
         conditions=[{"metric": "technical_score", "operator": ">=", "value": 30.0}]),
    dict(priority="ÉLEVÉE", rank=400, match_mode="ANY",
         disconnects_per_day=None, call_percent=None, affected_days_percent=None, lost_minutes_per_day=None,
         color="#B54708", is_fallback=0, enabled=1,
         conditions=[{"metric": "technical_score", "operator": ">=", "value": 18.0}]),
    dict(priority="À INVESTIGUER", rank=300, match_mode="ANY",
         disconnects_per_day=None, call_percent=None, affected_days_percent=None, lost_minutes_per_day=None,
         color="#A56A00", is_fallback=0, enabled=1,
         conditions=[{"metric": "technical_score", "operator": ">=", "value": 10.0}]),
    dict(priority="SURVEILLANCE", rank=200, match_mode="ANY",
         disconnects_per_day=None, call_percent=None, affected_days_percent=None, lost_minutes_per_day=None,
         color="#4A58A3", is_fallback=0, enabled=1,
         conditions=[{"metric": "technical_score", "operator": ">=", "value": 5.0}]),
    dict(priority="NORMAL", rank=100, match_mode="ANY", disconnects_per_day=None,
         call_percent=None, affected_days_percent=None, lost_minutes_per_day=None,
         color="#24634A", is_fallback=1, enabled=1, conditions=[]),
]


def metric_catalog():
    return [dict(key=key, **meta) for key, meta in METRICS.items()]


def _as_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off", "no", "non"}
    return bool(value)


def _legacy_conditions(data):
    out = []
    for key in LEGACY_FIELDS:
        raw = data.get(key)
        if raw is None or raw == "":
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        out.append({"metric": key, "operator": ">", "value": value})
    return out


def validate_conditions(raw, *, allow_empty=True):
    """Validate a list of generic priority conditions.

    Returns a normalized list.  ``ValueError`` is intentional so HTTP/config
    import callers can return a precise validation error.
    """
    if raw is None or raw == "":
        raw = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Conditions de priorité invalides") from exc
    if not isinstance(raw, list):
        raise ValueError("Conditions de priorité invalides")
    if len(raw) > 24:
        raise ValueError("Maximum 24 conditions par niveau")
    normalized = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Condition de priorité invalide")
        metric = str(item.get("metric", "")).strip()
        operator = str(item.get("operator", ">")).strip()
        if metric not in METRICS:
            raise ValueError(f"Mesure de priorité inconnue : {metric}")
        if operator not in OPERATORS:
            raise ValueError(f"Opérateur de priorité invalide : {operator}")
        try:
            value = float(item.get("value"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Valeur de seuil invalide") from exc
        meta = METRICS[metric]
        if value < float(meta["min"]) or value > float(meta["max"]):
            raise ValueError(f"Seuil hors limites pour {meta['label']}")
        normalized.append({"metric": metric, "operator": operator, "value": value})
    if not allow_empty and not normalized:
        raise ValueError("Configurez au moins une condition pour ce niveau")
    return normalized


def _normalized_policy(row):
    d = dict(row)
    d["priority"] = " ".join(str(d.get("priority") or "").split()).strip()
    d["rank"] = int(d.get("rank") or 0)
    d["match_mode"] = str(d.get("match_mode") or "ANY").upper()
    if d["match_mode"] not in {"ANY", "ALL"}:
        d["match_mode"] = "ANY"
    d["enabled"] = 1 if _as_bool(d.get("enabled", 1), True) else 0
    d["is_fallback"] = 1 if _as_bool(d.get("is_fallback", 0)) else 0
    color = str(d.get("color") or "#667085").strip().upper()
    d["color"] = color if COLOR_RE.fullmatch(color) else "#667085"
    for key in LEGACY_FIELDS:
        value = d.get(key)
        try:
            d[key] = None if value is None or value == "" else float(value)
        except (TypeError, ValueError):
            d[key] = None

    raw_conditions = d.get("conditions")
    if raw_conditions is None:
        raw_conditions = d.get("conditions_json")
    try:
        conditions = validate_conditions(raw_conditions, allow_empty=True)
    except ValueError:
        conditions = []
    if not conditions and not d["is_fallback"]:
        conditions = _legacy_conditions(d)
    d["conditions"] = conditions
    return d


def _table_columns(con):
    return {r[1] for r in con.execute("PRAGMA table_info(support_priority_policies)").fetchall()}


def load_priority_policies(admin_db=None):
    """Return exactly the configured policies, ordered strongest to weakest.

    Defaults are used only when the table/database is unavailable or empty. We
    intentionally do *not* append deleted default levels: custom level creation
    and deletion must remain under the administrator's control.
    """
    path = Path(admin_db or ctx.admin_db_path())
    if not sqlite3.runtime_database_available(path):
        return [_normalized_policy(x) for x in DEFAULT_POLICIES]
    try:
        con = sqlite3.connect(str(path), timeout=5)
        con.row_factory = sqlite3.Row
        try:
            table = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='support_priority_policies'").fetchone()
            if not table:
                return [_normalized_policy(x) for x in DEFAULT_POLICIES]
            cols = _table_columns(con)
            base = ["priority", "rank", "match_mode", "disconnects_per_day", "call_percent",
                    "affected_days_percent", "lost_minutes_per_day", "enabled"]
            for optional in ("color", "is_fallback", "conditions_json"):
                if optional in cols:
                    base.append(optional)
            rows = [_normalized_policy(r) for r in con.execute(
                f"SELECT {','.join(base)} FROM support_priority_policies ORDER BY rank DESC, priority COLLATE NOCASE"
            )]
        finally:
            con.close()
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return [_normalized_policy(x) for x in DEFAULT_POLICIES]
    if not rows:
        return [_normalized_policy(x) for x in DEFAULT_POLICIES]

    fallbacks = [r for r in rows if r.get("is_fallback")]
    if not fallbacks:
        legacy = next((r for r in rows if r["priority"].casefold() == "faible"), None)
        fallback = legacy or min(rows, key=lambda r: int(r.get("rank") or 0))
        fallback["is_fallback"] = 1
        fallback["enabled"] = 1
    elif len(fallbacks) > 1:
        keep = max(fallbacks, key=lambda r: int(r.get("rank") or 0))
        for r in fallbacks:
            r["is_fallback"] = 1 if r is keep else 0
    for r in rows:
        if r.get("is_fallback"):
            r["enabled"] = 1
            r["conditions"] = []
    return sorted(rows, key=lambda r: (-int(r.get("rank") or 0), r.get("priority", "").casefold()))


def agent_priority_metrics(stat, selected_days, covered_days):
    selected_days = max(1, int(selected_days or 0))
    covered_days = max(1, int(covered_days or 0))
    deco = float(stat.get("deco") or 0)
    deco_call = float(stat.get("deco_call") or 0)
    affected_days = float(stat.get("days_affected") or 0)
    affected_denominator = affected_days if affected_days > 0 else 1.0
    lost_seconds = float(stat.get("lost_seconds") or 0)
    collective = float(stat.get("collective_count") or 0)
    collective_denominator = deco + collective
    return {
        "disconnects_per_day": round(deco / covered_days, 2),
        "disconnects_per_affected_day": round(deco / affected_denominator, 2) if affected_days > 0 else 0.0,
        "disconnects_total": round(deco, 2),
        "disconnects_during_call": round(deco_call, 2),
        "disconnects_during_call_per_affected_day": round(deco_call / affected_denominator, 2) if affected_days > 0 else 0.0,
        "call_percent": round(float(stat.get("call_percent") or 0), 2),
        "affected_days": round(affected_days, 2),
        "affected_days_percent": round(affected_days * 100.0 / selected_days, 2),
        "lost_minutes_total": round(lost_seconds / 60.0, 2),
        "lost_minutes_per_day": round(lost_seconds / 60.0 / covered_days, 2),
        "lost_minutes_per_affected_day": round(lost_seconds / 60.0 / affected_denominator, 2) if affected_days > 0 else 0.0,
        "avg_disconnect_seconds": round(float(stat.get("avg_seconds") or 0), 2),
        "median_disconnect_seconds": round(float(stat.get("median_seconds") or 0), 2),
        "max_disconnect_seconds": round(float(stat.get("max_seconds") or 0), 2),
        "critical_disconnects": round(float(stat.get("critical_count") or 0), 2),
        "critical_percent": round(float(stat.get("critical_percent") or 0), 2),
        "collective_disconnects": round(collective, 2),
        "collective_percent": round(collective * 100.0 / collective_denominator, 2) if collective_denominator else 0.0,
        "technical_score": round(float(stat.get("technical_score") or 0), 2),
        "technical_disconnects": round(float(stat.get("technical_disconnects") or stat.get("deco") or 0), 2),
        "technical_disconnects_per_worked_day": round(float(stat.get("technical_disconnects_per_worked_day") or 0), 2),
        "technical_in_call": round(float(stat.get("technical_in_call") or stat.get("deco_call") or 0), 2),
        "technical_in_call_per_worked_day": round(float(stat.get("technical_in_call_per_worked_day") or 0), 2),
        "worked_days": round(float(stat.get("worked_days") or 0), 2),
        "affected_worked_days_percent": round(float(stat.get("affected_worked_days_percent") or 0), 2),
        "bursts_30m": round(float(stat.get("bursts_30m") or 0), 2),
        "bursts_per_worked_day": round(float(stat.get("bursts_per_worked_day") or 0), 2),
        "probable_closures": round(float(stat.get("probable_closures") or 0), 2),
        "technical_lost_minutes_per_affected_day": round(float(stat.get("technical_lost_minutes_per_affected_day") or 0), 2),
    }


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


def evaluate_priority(stat, selected_days, covered_days, policies=None):
    """Evaluate custom policies from highest rank to lowest rank."""
    policies = [_normalized_policy(p) for p in (policies or load_priority_policies())]
    metrics = agent_priority_metrics(stat, selected_days, covered_days)
    fallback_policy = next((p for p in policies if p.get("is_fallback")), None)
    if fallback_policy is None:
        fallback_policy = min(policies, key=lambda r: int(r.get("rank") or 0), default={"priority": "FAIBLE"})
    fallback = fallback_policy.get("priority") or "FAIBLE"

    for policy in sorted(policies, key=lambda r: -int(r.get("rank") or 0)):
        if policy.get("is_fallback") or not policy.get("enabled", 1):
            continue
        conditions = policy.get("conditions") or []
        if not conditions:
            continue
        checks = []
        reasons = []
        for condition in conditions:
            key = condition["metric"]
            operator = condition["operator"]
            threshold = float(condition["value"])
            actual = float(metrics.get(key, 0))
            passed = _compare(actual, operator, threshold)
            checks.append(passed)
            if passed:
                meta = METRICS[key]
                unit = meta.get("unit") or ""
                unit_text = f" {unit}" if unit else ""
                reasons.append(f"{meta['label']}: {actual:g}{unit_text} {operator} {threshold:g}{unit_text}")
        matched = all(checks) if policy.get("match_mode") == "ALL" else any(checks)
        if matched:
            return policy.get("priority") or fallback, metrics, reasons
    return fallback, metrics, []


def legacy_thresholds_from_conditions(conditions):
    """Populate legacy columns when a simple `metric > value` condition exists."""
    values = {key: None for key in LEGACY_FIELDS}
    for c in conditions or []:
        if c.get("metric") in values and c.get("operator") == ">" and values[c["metric"]] is None:
            values[c["metric"]] = float(c["value"])
    return values


def public_policy_snapshot(policies=None):
    out = []
    for raw in (policies or load_priority_policies()):
        p = _normalized_policy(raw)
        conditions = []
        for c in p.get("conditions") or []:
            meta = METRICS[c["metric"]]
            conditions.append({
                "metric": c["metric"], "operator": c["operator"], "value": c["value"],
                "label": meta["label"], "unit": meta["unit"],
            })
        item = {k: p.get(k) for k in (
            "priority", "rank", "match_mode", "disconnects_per_day", "call_percent",
            "affected_days_percent", "lost_minutes_per_day", "enabled", "color", "is_fallback"
        )}
        item["conditions"] = conditions
        out.append(item)
    return out
