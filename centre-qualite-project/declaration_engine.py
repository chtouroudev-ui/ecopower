"""Punctual Nelyio declarations (Phase D).

A declaration is deliberately simpler than a generic Policy: a responsable
selects an agent/group, a date and a duration.  It never removes raw evidence.
The engine only annotates matching technical events and exposes a decision that
can be merged after the generic Policy decision.
"""
from datetime import datetime, timedelta
import json

from app_db import db_connect
from governance_intervals import event_datetime, declaration_ranges, summarize_actions, attach_decision

DECLARATION_TYPES = {
    "AUTORISATION": "Autorisation",
    "INTERVENTION": "Intervention",
    "REUNION": "Réunion",
    "FORMATION": "Formation",
    "PAUSE_EXCEPTIONNELLE": "Pause exceptionnelle",
    "PROBLEME_TECHNIQUE": "Problème technique déclaré",
    "AUTRE": "Autre",
}

# Deliberately conservative and predictable.  Organizational/authorized
# periods are removed from technical KPIs and support prioritization, while a
# declared technical problem remains a technical signal and is only annotated.
DEFAULT_ACTIONS = {
    "AUTORISATION": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
    "INTERVENTION": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
    "REUNION": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
    "FORMATION": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
    "PAUSE_EXCEPTIONNELLE": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
    "PROBLEME_TECHNIQUE": dict(exclude_statistics=False, exclude_lost_time=False, exclude_score=False, mark_authorized=False),
    "AUTRE": dict(exclude_statistics=True, exclude_lost_time=True, exclude_score=True, mark_authorized=True),
}

AUTO_FILTER_DECLARATION_TYPES = set(DECLARATION_TYPES) - {"PROBLEME_TECHNIQUE"}


def declaration_actions(declaration_type):
    return dict(DEFAULT_ACTIONS.get(str(declaration_type or "AUTRE").upper(), DEFAULT_ACTIONS["AUTRE"]))


def _json(raw, default):
    try:
        value = json.loads(raw or "")
        return value if isinstance(value, type(default)) else default
    except Exception:
        return default


def _norm(value):
    return str(value or "").strip().casefold()


def _row(row, targets=()):
    d = dict(row)
    d["actions"] = _json(d.pop("action_json", "{}"), {})
    d["targets"] = [{"target_type": x["target_type"], "target_key": x["target_key"]} for x in targets]
    d["type_label"] = DECLARATION_TYPES.get(d.get("declaration_type"), d.get("declaration_type") or "Autre")
    d["active"] = d.get("status") == "ACTIVE" and not d.get("deleted_at")
    d["_agent_targets"] = frozenset(_norm(x.get("target_key")) for x in d["targets"] if str(x.get("target_type") or "").upper() == "AGENT")
    d["_group_targets"] = frozenset(_norm(x.get("target_key")) for x in d["targets"] if str(x.get("target_type") or "").upper() == "GROUP")
    try:
        d["_start_dt"] = datetime.strptime(str(d.get("start_at")), "%Y-%m-%d %H:%M:%S")
        d["_end_dt"] = datetime.strptime(str(d.get("end_at")), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        d["_start_dt"] = None; d["_end_dt"] = None
    return d


def load_declarations(day_from=None, day_to=None, include_cancelled=False, include_deleted=False, limit=None):
    """Load declarations, optionally restricted to declarations overlapping a local date range."""
    where = []
    params = []
    if not include_cancelled:
        where.append("d.status='ACTIVE'")
    if not include_deleted:
        where.append("d.deleted_at IS NULL")
    if day_from:
        where.append("d.end_at>?")
        params.append(str(day_from)[:10] + " 00:00:00")
    if day_to:
        try:
            end_exclusive = datetime.strptime(str(day_to)[:10], "%Y-%m-%d") + timedelta(days=1)
            end_text = end_exclusive.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            end_text = str(day_to)[:10] + " 23:59:59"
        where.append("d.start_at<?")
        params.append(end_text)
    sql = "SELECT d.* FROM nelyio_declarations d"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY d.start_at DESC,d.id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(max(1, min(5000, int(limit))))
    with db_connect() as con:
        rows = con.execute(sql, params).fetchall()
        by = {int(r["id"]): [] for r in rows}
        if by:
            marks = ",".join("?" for _ in by)
            for t in con.execute(
                f"SELECT declaration_id,target_type,target_key FROM nelyio_declaration_targets WHERE declaration_id IN ({marks}) ORDER BY id",
                tuple(by),
            ):
                by[int(t["declaration_id"])].append(t)
        return [_row(r, by.get(int(r["id"]), [])) for r in rows]


def public_declaration(d):
    out = {k:v for k,v in dict(d or {}).items() if not str(k).startswith('_')}
    out["actions"] = {k: bool((out.get("actions") or {}).get(k)) for k in ("exclude_statistics", "exclude_lost_time", "exclude_score", "mark_authorized")}
    return out


def declaration_snapshot(day_from=None, day_to=None, include_cancelled=True, limit=500):
    return [public_declaration(x) for x in load_declarations(day_from, day_to, include_cancelled=include_cancelled, limit=limit)]


def _event_dt(event):
    return event_datetime(event)


def _target_matches(declaration, event):
    agent_keys = {_norm(event.get("agent")), _norm(event.get("name"))}
    group_keys = {_norm(event.get("group_id")), _norm(event.get("group_name"))}
    if "_agent_targets" in declaration:
        return bool(agent_keys & set(declaration.get("_agent_targets") or ())) or bool(group_keys & set(declaration.get("_group_targets") or ()))
    for t in declaration.get("targets") or []:
        typ = str(t.get("target_type") or "").upper()
        key = _norm(t.get("target_key"))
        if typ == "AGENT" and key in agent_keys:
            return True
        if typ == "GROUP" and key in group_keys:
            return True
    return False


def declaration_matches(declaration, event):
    if declaration.get("status") != "ACTIVE" or declaration.get("deleted_at"):
        return False
    if not _target_matches(declaration, event):
        return False
    return bool(declaration_ranges(declaration, event))


def matching_declarations(event, declarations=None):
    rows = declarations if declarations is not None else load_declarations()
    matches = [d for d in rows if declaration_matches(d, event)]
    # Most recently created declaration is shown first; all matching declarations
    # contribute additive boolean actions.
    matches.sort(key=lambda d: (str(d.get("start_at") or ""), int(d.get("id") or 0)), reverse=True)
    return matches


def evaluate_event(event, declarations=None):
    matches = matching_declarations(event, declarations)
    decision = {
        "applied": False,
        "declaration_ids": [],
        "declaration_types": [],
        "exclude_statistics": False,
        "exclude_lost_time": False,
        "exclude_score": False,
        "mark_authorized": False,
        "reason": "",
        "comments": [],
    }
    intervals = {}
    if not matches:
        decision.update(summarize_actions(event, intervals))
        return decision
    decision["applied"] = True
    reasons = []
    for d in matches:
        actions = d.get("actions") or declaration_actions(d.get("declaration_type"))
        decision["declaration_ids"].append(int(d.get("id") or 0))
        typ = str(d.get("declaration_type") or "AUTRE")
        decision["declaration_types"].append(typ)
        effective_actions = {key: bool(actions.get(key)) for key in ("exclude_statistics", "exclude_lost_time", "exclude_score", "mark_authorized")}
        if typ in AUTO_FILTER_DECLARATION_TYPES:
            effective_actions = {key: True for key in effective_actions}
        ranges = declaration_ranges(d, event)
        for key, enabled in effective_actions.items():
            if enabled:
                intervals.setdefault(key, []).extend(ranges)
        label = DECLARATION_TYPES.get(typ, typ)
        reasons.append(f"{label} #{int(d.get('id') or 0)}")
        comment = str(d.get("comment") or "").strip()
        if comment:
            decision["comments"].append(comment)
    decision["reason"] = "; ".join(reasons)
    decision.update(summarize_actions(event, intervals))
    return decision


def apply_event_declarations(event, declarations=None):
    out = dict(event)
    d = evaluate_event(out, declarations)
    out["declaration_decision"] = d
    out["declaration_applied"] = bool(d["applied"])
    out["declaration_reason"] = d["reason"]
    attach_decision(out, "declaration", d)
    return out
