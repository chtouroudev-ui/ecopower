"""Explainable technical scoring for Support technique Nelyio.

v41 separates three concepts that were previously mixed together:
1. raw disconnect events,
2. technical classification / context,
3. agent score and priority.

The score is deliberately transparent and configurable.  It does not evaluate
agent performance; it only ranks technical support signals.
"""
from __future__ import annotations

from collections import defaultdict
from bisect import bisect_left, bisect_right
from pathlib import Path
import json
import math
import db_compat as sqlite3

import supervision_context as ctx
from nelyio_time import local_datetime as france_local_datetime

SCORE_SETTING_KEY = "support_score_config_json"

DEFAULT_SCORE_CONFIG = {
    "version": 1,
    # Event points.
    "technical_disconnect_points": 1.0,
    "in_call_bonus_points": 4.0,
    "collective_disconnect_points": 0.0,
    "probable_closure_points": 0.0,
    # Shared incident detection. Requiring 4 distinct agents inside one minute
    # avoids treating ordinary background noise in a busy call center as a
    # collective infrastructure incident. Both values remain administrator
    # configurable.
    "collective_window_seconds": 60,
    "collective_min_agents": 4,
    # Repeated disconnect burst.
    "burst_window_minutes": 30,
    "burst_min_count": 3,
    "burst_points": 4.0,
    # Recurrence across worked days.
    "recurrence_days_threshold": 3,
    "recurrence_days_points": 4.0,
    "recurrence_percent_threshold": 50.0,
    "recurrence_percent_min_worked_days": 3,
    "recurrence_percent_points": 6.0,
    # Lost technical time. Highest matching tier wins (not cumulative).
    "lost_minutes_low_threshold": 5.0,
    "lost_minutes_low_points": 3.0,
    "lost_minutes_high_threshold": 10.0,
    "lost_minutes_high_points": 6.0,
    # Conservative lunch/application-closure detection.
    "probable_closure_enabled": True,
    "probable_closure_start_from": "11:50",
    "probable_closure_start_to": "13:10",
    "probable_closure_min_minutes": 45.0,
    "probable_closure_max_minutes": 75.0,
    "probable_closure_activity_tolerance_minutes": 10.0,
}

PUBLIC_FIELDS = tuple(DEFAULT_SCORE_CONFIG)


def _as_bool(value, default=False):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off", "no", "non"}
    return bool(value)


def _number(data, key, lo, hi, *, integer=False):
    try:
        value = float(data.get(key, DEFAULT_SCORE_CONFIG[key]))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Valeur de score invalide : {key}") from exc
    if not math.isfinite(value) or value < lo or value > hi:
        raise ValueError(f"Valeur de score hors limites : {key}")
    return int(round(value)) if integer else round(value, 4)


def _clock_minutes(value, key):
    text = str(value or "").strip()
    try:
        h, m = [int(x) for x in text.split(":", 1)]
    except Exception as exc:
        raise ValueError(f"Heure invalide pour {key} (HH:MM)") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Heure invalide pour {key} (HH:MM)")
    return h * 60 + m


def validate_score_config(raw):
    """Normalize and validate an administrator supplied score configuration."""
    data = dict(DEFAULT_SCORE_CONFIG)
    if raw:
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("Configuration de score invalide") from exc
        if not isinstance(raw, dict):
            raise ValueError("Configuration de score invalide")
        data.update(raw)

    normalized = {
        "version": 1,
        "technical_disconnect_points": _number(data, "technical_disconnect_points", 0, 100),
        "in_call_bonus_points": _number(data, "in_call_bonus_points", 0, 100),
        "collective_disconnect_points": _number(data, "collective_disconnect_points", 0, 100),
        "probable_closure_points": _number(data, "probable_closure_points", 0, 100),
        "collective_window_seconds": _number(data, "collective_window_seconds", 15, 600, integer=True),
        "collective_min_agents": _number(data, "collective_min_agents", 2, 50, integer=True),
        "burst_window_minutes": _number(data, "burst_window_minutes", 1, 240, integer=True),
        "burst_min_count": _number(data, "burst_min_count", 2, 50, integer=True),
        "burst_points": _number(data, "burst_points", 0, 100),
        "recurrence_days_threshold": _number(data, "recurrence_days_threshold", 1, 366, integer=True),
        "recurrence_days_points": _number(data, "recurrence_days_points", 0, 100),
        "recurrence_percent_threshold": _number(data, "recurrence_percent_threshold", 0, 100),
        "recurrence_percent_min_worked_days": _number(data, "recurrence_percent_min_worked_days", 1, 366, integer=True),
        "recurrence_percent_points": _number(data, "recurrence_percent_points", 0, 100),
        "lost_minutes_low_threshold": _number(data, "lost_minutes_low_threshold", 0, 1440),
        "lost_minutes_low_points": _number(data, "lost_minutes_low_points", 0, 100),
        "lost_minutes_high_threshold": _number(data, "lost_minutes_high_threshold", 0, 1440),
        "lost_minutes_high_points": _number(data, "lost_minutes_high_points", 0, 100),
        "probable_closure_enabled": _as_bool(data.get("probable_closure_enabled"), True),
        "probable_closure_start_from": str(data.get("probable_closure_start_from") or "11:50").strip(),
        "probable_closure_start_to": str(data.get("probable_closure_start_to") or "13:10").strip(),
        "probable_closure_min_minutes": _number(data, "probable_closure_min_minutes", 1, 240),
        "probable_closure_max_minutes": _number(data, "probable_closure_max_minutes", 1, 240),
        "probable_closure_activity_tolerance_minutes": _number(data, "probable_closure_activity_tolerance_minutes", 0, 60),
    }
    start = _clock_minutes(normalized["probable_closure_start_from"], "probable_closure_start_from")
    end = _clock_minutes(normalized["probable_closure_start_to"], "probable_closure_start_to")
    if end < start:
        raise ValueError("La fin du créneau de fermeture probable doit être après le début")
    if normalized["probable_closure_max_minutes"] < normalized["probable_closure_min_minutes"]:
        raise ValueError("La durée max de fermeture probable doit être supérieure à la durée min")
    if normalized["lost_minutes_high_threshold"] < normalized["lost_minutes_low_threshold"]:
        raise ValueError("Le seuil haut de temps perdu doit être supérieur au seuil bas")
    return normalized


def load_score_config(admin_db=None):
    path = Path(admin_db or ctx.admin_db_path())
    if not sqlite3.runtime_database_available(path):
        return dict(DEFAULT_SCORE_CONFIG)
    try:
        con = sqlite3.connect(str(path), timeout=5)
        try:
            row = con.execute("SELECT value FROM settings WHERE key=?", (SCORE_SETTING_KEY,)).fetchone()
        finally:
            con.close()
        return validate_score_config(row[0] if row else None)
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return dict(DEFAULT_SCORE_CONFIG)


def public_score_config(config=None):
    cfg = validate_score_config(config or DEFAULT_SCORE_CONFIG)
    return {key: cfg[key] for key in PUBLIC_FIELDS}


def _minute_of_day(ts):
    dt = france_local_datetime(ts)
    return dt.hour * 60 + dt.minute + dt.second / 60.0


def build_activity_neighbor_index(rows):
    """Pre-index non-offline activity rows for probable-closure checks.

    V60.3 issued two PostgreSQL queries per lunch-like disconnect to find the
    nearest activity before/after. On long periods this became a classic N+1
    pattern (hundreds of SQL calls). The index is built once from the already
    selected day/import activity rows and preserves the exact same predicates.
    """
    by_agent=defaultdict(list)
    for raw in rows or ():
        r=dict(raw)
        agent=str(r.get('agent') or '').strip()
        if not agent or str(r.get('kind') or '')=='offline':
            continue
        try:start=float(r.get('start') or 0);end=float(r.get('end') or start)
        except (TypeError,ValueError):continue
        by_agent[agent].append((start,end,str(r.get('kind') or '')))
    out={}
    for agent,items in by_agent.items():
        by_end=sorted(items,key=lambda x:(x[1],x[0]));ends=[x[1] for x in by_end]
        by_start=sorted(items,key=lambda x:(x[0],x[1]));starts=[x[0] for x in by_start]
        out[agent]=(ends,by_end,starts,by_start)
    return out


def probable_application_closure_candidate(row, config=None, *, validated_config=False):
    """Cheap predicate used to batch the before/after activity lookup."""
    cfg = (config or DEFAULT_SCORE_CONFIG) if validated_config else validate_score_config(config or DEFAULT_SCORE_CONFIG)
    if not cfg["probable_closure_enabled"] or row.get("during_call"):
        return False
    minutes = float(row.get("seconds") or 0) / 60.0
    if not (cfg["probable_closure_min_minutes"] <= minutes <= cfg["probable_closure_max_minutes"]):
        return False
    start_min = _minute_of_day(float(row.get("start") or 0))
    low = _clock_minutes(cfg["probable_closure_start_from"], "probable_closure_start_from")
    high = _clock_minutes(cfg["probable_closure_start_to"], "probable_closure_start_to")
    return low <= start_min <= high


def probable_application_closure(con, import_id, row, config=None, *, validated_config=False, activity_index=None):
    """Conservatively flag a lunch/application closure, never from time alone.

    Conditions:
    - exported data (callers only use this helper for export rows),
    - offline duration inside the configured lunch-like range,
    - starts inside the configured window,
    - not during a call,
    - a non-offline activity exists shortly before *and* shortly after.

    This is intentionally labelled *probable*: it remains visible in the event
    journal and can be assigned a non-zero score by the administrator.
    """
    cfg = (config or DEFAULT_SCORE_CONFIG) if validated_config else validate_score_config(config or DEFAULT_SCORE_CONFIG)
    if not probable_application_closure_candidate(row,cfg,validated_config=True):
        return False, ""
    minutes = float(row.get("seconds") or 0) / 60.0

    tolerance = float(cfg["probable_closure_activity_tolerance_minutes"]) * 60.0
    start, end = float(row["start"]), float(row["end"])
    if activity_index is not None:
        idx=activity_index.get(str(row.get("agent") or ""))
        before=after=None
        if idx:
            ends,by_end,starts,by_start=idx
            pos=bisect_right(ends,start+2)-1
            if pos>=0 and by_end[pos][1]>=start-tolerance:
                before=by_end[pos]
            pos=bisect_left(starts,end-2)
            if pos<len(by_start) and by_start[pos][0]<=end+tolerance:
                after=by_start[pos]
    else:
        try:
            before = con.execute(
                """SELECT kind,end FROM activities
                   WHERE import_id=? AND agent=? AND kind<>'offline' AND end<=? AND end>=?
                   ORDER BY end DESC LIMIT 1""",
                (import_id, row["agent"], start + 2, start - tolerance),
            ).fetchone()
            after = con.execute(
                """SELECT kind,start FROM activities
                   WHERE import_id=? AND agent=? AND kind<>'offline' AND start>=? AND start<=?
                   ORDER BY start ASC LIMIT 1""",
                (import_id, row["agent"], end - 2, end + tolerance),
            ).fetchone()
        except sqlite3.Error:
            return False, ""
    if not before or not after:
        return False, ""
    return True, (
        f"Fermeture application / pause probable : {minutes:.0f} min dans le créneau configuré, "
        "avec activité normale détectée juste avant et après."
    )


def count_disconnect_bursts(events, window_minutes, min_count):
    """Count non-overlapping same-day bursts of repeated technical events."""
    grouped = defaultdict(list)
    for row in events:
        grouped[str(row.get("day") or "")].append(float(row.get("start") or 0))
    window = max(60.0, float(window_minutes) * 60.0)
    total = 0
    for starts in grouped.values():
        starts.sort()
        i = 0
        while i < len(starts):
            j = i
            while j + 1 < len(starts) and starts[j + 1] - starts[i] <= window:
                j += 1
            if j - i + 1 >= int(min_count):
                total += 1
                i = j + 1
            else:
                i += 1
    return total


def compute_agent_score(events, worked_days, config=None, probable_closure_count=0, collective_count=0):
    """Return an explainable score based only on individual technical events."""
    cfg = validate_score_config(config or DEFAULT_SCORE_CONFIG)
    rows = list(events or [])
    worked_days = max(0, int(worked_days or 0))
    affected_days = len({str(r.get("day") or "") for r in rows if r.get("day")})
    lost_seconds = sum(max(0.0, float(r.get("governance_score_effective_seconds", r.get("governance_effective_seconds", r.get("seconds") or 0)))) for r in rows)
    in_call = sum(1 for r in rows if r.get("during_call"))
    bursts = count_disconnect_bursts(rows, cfg["burst_window_minutes"], cfg["burst_min_count"])
    affected_pct = round(affected_days * 100.0 / worked_days, 2) if worked_days else 0.0
    lost_minutes_per_affected_day = lost_seconds / 60.0 / affected_days if affected_days else 0.0

    components = []
    def add(code, label, points, detail):
        points = round(float(points), 2)
        if points:
            components.append({"code": code, "label": label, "points": points, "detail": detail})
        return points

    # Frequency components are normalized by actual worked days.  This keeps
    # the score comparable whether the administrator selects 2 days or 3 weeks:
    # extending the analysis period must not inflate severity by itself.
    normalizer = max(1, worked_days)
    disconnects_per_worked_day = len(rows) / normalizer
    in_call_per_worked_day = in_call / normalizer
    bursts_per_worked_day = bursts / normalizer

    score = 0.0
    score += add(
        "technical_disconnects", "Déconnexions techniques / jour travaillé",
        disconnects_per_worked_day * cfg["technical_disconnect_points"],
        f"{len(rows)} coupure(s) / {normalizer} j travaillé(s) = {disconnects_per_worked_day:.2f} × {cfg['technical_disconnect_points']:g} pt",
    )
    score += add(
        "in_call", "Coupures pendant appel / jour travaillé",
        in_call_per_worked_day * cfg["in_call_bonus_points"],
        f"{in_call} coupure(s) en appel / {normalizer} j travaillé(s) = {in_call_per_worked_day:.2f} × {cfg['in_call_bonus_points']:g} pt",
    )
    score += add(
        "bursts", "Répétitions rapprochées / jour travaillé",
        bursts_per_worked_day * cfg["burst_points"],
        f"{bursts} série(s) / {normalizer} j travaillé(s) = {bursts_per_worked_day:.2f} × {cfg['burst_points']:g} pt",
    )
    if affected_days >= cfg["recurrence_days_threshold"]:
        score += add(
            "recurrence_days", "Récurrence sur plusieurs jours", cfg["recurrence_days_points"],
            f"{affected_days} jour(s) touché(s) ≥ {cfg['recurrence_days_threshold']}",
        )
    if worked_days >= cfg["recurrence_percent_min_worked_days"] and affected_pct >= cfg["recurrence_percent_threshold"]:
        score += add(
            "recurrence_percent", "Récurrence sur jours travaillés", cfg["recurrence_percent_points"],
            f"{affected_pct:g}% des {worked_days} jour(s) travaillé(s)",
        )
    if lost_minutes_per_affected_day >= cfg["lost_minutes_high_threshold"]:
        score += add(
            "lost_time_high", "Temps perdu technique", cfg["lost_minutes_high_points"],
            f"{lost_minutes_per_affected_day:.1f} min/j touché ≥ {cfg['lost_minutes_high_threshold']:g}",
        )
    elif lost_minutes_per_affected_day >= cfg["lost_minutes_low_threshold"]:
        score += add(
            "lost_time_low", "Temps perdu technique", cfg["lost_minutes_low_points"],
            f"{lost_minutes_per_affected_day:.1f} min/j touché ≥ {cfg['lost_minutes_low_threshold']:g}",
        )
    probable_rate = float(probable_closure_count or 0) / normalizer
    collective_rate = float(collective_count or 0) / normalizer
    score += add(
        "probable_closure", "Fermeture application / pause probable",
        probable_rate * cfg["probable_closure_points"],
        f"{int(probable_closure_count or 0)} événement(s) / {normalizer} j travaillé(s) × {cfg['probable_closure_points']:g} pt",
    )
    score += add(
        "collective", "Incidents collectifs",
        collective_rate * cfg["collective_disconnect_points"],
        f"{int(collective_count or 0)} événement(s) / {normalizer} j travaillé(s) × {cfg['collective_disconnect_points']:g} pt",
    )

    return {
        "technical_score": round(score, 2),
        "score_components": components,
        "worked_days": worked_days,
        "technical_affected_days": affected_days,
        "affected_worked_days_percent": affected_pct,
        "bursts_30m": bursts,
        "technical_lost_seconds": round(lost_seconds),
        "technical_lost_minutes_per_affected_day": round(lost_minutes_per_affected_day, 2),
        "technical_disconnects": len(rows),
        "technical_in_call": in_call,
        "technical_disconnects_per_worked_day": round(disconnects_per_worked_day, 2),
        "technical_in_call_per_worked_day": round(in_call_per_worked_day, 2),
        "bursts_per_worked_day": round(bursts_per_worked_day, 2),
        "probable_closures": int(probable_closure_count or 0),
        "collective_disconnects_for_agent": int(collective_count or 0),
    }
