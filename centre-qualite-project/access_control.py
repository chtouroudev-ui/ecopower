"""Fine-grained interface permissions and business-group scoping.

Security groups (access_groups) are deliberately separate from Nelyio business
analysis groups (user_groups). This module only projects the policy already
attached to an authenticated user; it never guesses memberships from campaigns.
"""
from __future__ import annotations

import copy

import app_config as cfg


class ScopeDenied(ValueError):
    pass


def interface_level(user, interface_key):
    if not user or interface_key not in cfg.ACCESS_INTERFACES:
        return cfg.ACCESS_NONE
    if user.get("role") == "admin":
        return cfg.ACCESS_WRITE
    try:
        return max(cfg.ACCESS_NONE, min(cfg.ACCESS_WRITE, int((user.get("interface_permissions") or {}).get(interface_key, 0))))
    except Exception:
        return cfg.ACCESS_NONE


def has_interface(user, interface_key, write=False):
    meta = cfg.ACCESS_INTERFACES.get(interface_key)
    if not meta:
        return False
    required = cfg.ACCESS_WRITE if write or meta.get("write_only") else cfg.ACCESS_READ
    return interface_level(user, interface_key) >= required


def scope_policy(user):
    if not user or user.get("role") == "admin":
        return {"mode": "ALL", "allowed_group_ids": [], "default_group_id": "", "filter_locked": False, "all_groups": True}
    raw = dict(user.get("group_scope") or {})
    mode = str(raw.get("mode") or "SELECTED").upper()
    if mode not in {"ALL", "SELECTED"}:
        mode = "SELECTED"
    allowed = sorted({str(x).strip() for x in raw.get("allowed_group_ids") or [] if str(x).strip()})
    default = str(raw.get("default_group_id") or "").strip()
    locked = bool(raw.get("filter_locked"))
    return {
        "mode": mode,
        "allowed_group_ids": allowed,
        "default_group_id": default,
        "filter_locked": locked,
        "all_groups": mode == "ALL",
    }


def effective_group_ids(user):
    """None means unrestricted. A set means server-side business scope."""
    p = scope_policy(user)
    if p["filter_locked"]:
        return {p["default_group_id"]} if p["default_group_id"] else set()
    if p["mode"] == "ALL":
        return None
    return set(p["allowed_group_ids"])


def default_group_id(user):
    return scope_policy(user)["default_group_id"]


def allowed_group(user, group_id):
    gid = str(group_id or "").strip()
    if not gid:
        return False
    allowed = effective_group_ids(user)
    return allowed is None or gid in allowed


def scope_query(user, query, *, param="group"):
    """Return a detached query with server-side group scope applied.

    ALL + unlocked keeps an empty group as "all". SELECTED never permits an
    empty query to escape the allowed list: it resolves to the configured
    default, or the first allowed group. LOCKED always forces the default group.
    """
    q = {k: list(v) if isinstance(v, (list, tuple)) else [v] for k, v in (query or {}).items()}
    p = scope_policy(user)
    requested = str((q.get(param) or [""])[0] or "").strip()
    if p["filter_locked"]:
        target = p["default_group_id"]
        if not target:
            raise ScopeDenied("Périmètre verrouillé sans groupe par défaut. Contactez un administrateur.")
        q[param] = [target]
        return q
    if p["mode"] == "ALL":
        return q
    allowed = p["allowed_group_ids"]
    if not allowed:
        raise ScopeDenied("Aucun groupe métier n'est autorisé pour ce compte.")
    target = requested or p["default_group_id"] or allowed[0]
    if target not in allowed:
        raise ScopeDenied("Accès refusé à ce groupe métier.")
    q[param] = [target]
    return q


def scope_multi_query(user, query, *, param="group"):
    """Apply scope to a multi-select group parameter (reports)."""
    q = {k: list(v) if isinstance(v, (list, tuple)) else [v] for k, v in (query or {}).items()}
    p = scope_policy(user)
    requested = [str(x).strip() for x in q.get(param, []) if str(x).strip()]
    if p["filter_locked"]:
        if not p["default_group_id"]:
            raise ScopeDenied("Périmètre verrouillé sans groupe par défaut. Contactez un administrateur.")
        q[param] = [p["default_group_id"]]
        return q
    if p["mode"] == "ALL":
        return q
    allowed = set(p["allowed_group_ids"])
    if not allowed:
        raise ScopeDenied("Aucun groupe métier n'est autorisé pour ce compte.")
    if requested:
        if any(x not in allowed for x in requested):
            raise ScopeDenied("Accès refusé à un groupe métier demandé.")
        q[param] = requested
    else:
        q[param] = list(p["allowed_group_ids"])
    return q


def allowed_agent_ids(user):
    allowed = effective_group_ids(user)
    if allowed is None:
        return None
    return {str(x) for x in _selected_scope_ids(allowed).get("member_agent_ids") or []}


def allowed_line_ids(user):
    allowed = effective_group_ids(user)
    if allowed is None:
        return None
    return {str(x) for x in _selected_scope_ids(allowed).get("line_ids") or []}


def visible_groups(user, groups):
    allowed = effective_group_ids(user)
    if allowed is None:
        return list(groups or [])
    return [g for g in (groups or []) if str(g.get("id") or g.get("group_id") or "") in allowed]


def filter_group_catalog_payload(user, payload):
    """Remove unauthorized business-group catalogue entries from common views."""
    if not isinstance(payload, dict):
        return payload
    allowed = effective_group_ids(user)
    if allowed is None:
        return payload
    out = copy.deepcopy(payload)
    for key in ("groups", "admin_groups", "selected_groups"):
        value = out.get(key)
        if isinstance(value, list):
            if key == "selected_groups" and value and not isinstance(value[0], dict):
                out[key] = [x for x in value if str(x) in allowed]
            else:
                out[key] = [g for g in value if str((g or {}).get("id") or (g or {}).get("group_id") or "") in allowed]
    return out


def _agent_group_ids(agent):
    ids = set()
    for key in ("groups", "assigned_groups", "current_groups"):
        for g in agent.get(key) or []:
            gid = str((g or {}).get("id") or (g or {}).get("group_id") or "").strip()
            if gid:
                ids.add(gid)
    if agent.get("group_id") is not None:
        ids.add(str(agent.get("group_id")))
    return ids


def _selected_scope_ids(group_ids):
    try:
        from analysis_groups import selected_group_scope
        return selected_group_scope(sorted(group_ids))
    except Exception:
        return {"group_ids": sorted(group_ids), "member_agent_ids": [], "campaign_ids": [], "line_ids": []}


def _incident_allowed(incident, group_ids):
    scope = _selected_scope_ids(group_ids)
    st = str(incident.get("scope_type") or "").upper()
    sk = str(incident.get("scope_key") or "").strip()
    if st == "GROUP":
        return sk in group_ids
    if st == "AGENT":
        return sk in {str(x) for x in scope.get("member_agent_ids") or []}
    if st == "QUEUE":
        return sk in {str(x) for x in scope.get("line_ids") or []}
    if st == "CAMPAIGN":
        if sk not in {str(x) for x in scope.get("campaign_ids") or []}:
            return False
        try:
            from analysis_groups import group_ids_for_campaign
            owners={str(x) for x in group_ids_for_campaign(sk)}
            return bool(owners) and owners.issubset(group_ids)
        except Exception:
            return False
    # GLOBAL and SERVICE aggregate other business groups, so restricted users
    # must not receive them as if they represented only their own group.
    return False


def filter_live_incidents(user, incidents):
    allowed = effective_group_ids(user)
    if allowed is None:
        return list(incidents or [])
    return [x for x in (incidents or []) if _incident_allowed(x, allowed)]


def filter_live_snapshot(user, snapshot, requested_group=""):
    """Project one Live snapshot to the user's permitted business group."""
    p = scope_policy(user)
    allowed = effective_group_ids(user)
    target = str(requested_group or "").strip()
    if p["filter_locked"]:
        target = p["default_group_id"]
    elif p["mode"] == "SELECTED":
        if not target:
            target = p["default_group_id"] or (p["allowed_group_ids"][0] if p["allowed_group_ids"] else "")
        if target not in set(p["allowed_group_ids"]):
            raise ScopeDenied("Accès refusé à ce groupe métier.")
    elif target and allowed is not None and target not in allowed:
        raise ScopeDenied("Accès refusé à ce groupe métier.")

    try:
        from analysis_groups import catalog as analysis_group_catalog
        catalog_rows = analysis_group_catalog(include_unassigned=False)
    except Exception:
        catalog_rows = []
    if allowed is not None:
        catalog_rows = [g for g in catalog_rows if str(g.get("id") or "") in allowed]
    access_scope = {
        "mode": p["mode"],
        "locked": bool(p["filter_locked"]),
        "default_group_id": p.get("default_group_id") or "",
        "selected_group_id": target,
        "groups": [{"id": str(g.get("id") or ""), "name": str(g.get("name") or ""), "service_name": str(g.get("service_name") or "")} for g in catalog_rows],
    }
    if allowed is None and not target:
        out = copy.deepcopy(snapshot)
        out["access_scope"] = access_scope
        return out
    if not target:
        # SELECTED without any usable group is denied rather than returning all.
        raise ScopeDenied("Aucun groupe métier n'est disponible pour ce compte.")

    if catalog_rows and target not in {str(g.get("id") or "") for g in catalog_rows}:
        raise ScopeDenied("Groupe métier introuvable ou non autorisé.")
    out = copy.deepcopy(snapshot)
    out["access_scope"] = access_scope
    agents = [a for a in out.get("agents") or [] if target in _agent_group_ids(a)]
    out["agents"] = agents
    if isinstance(out.get("agent_roster"), list):
        roster=[a for a in out.get("agent_roster") or [] if target in _agent_group_ids(a)]
        out["agent_roster"]=roster
        out["roster_counts"]={
            "configured":len(roster),
            "observed":sum(1 for a in roster if a.get("observed")),
            "unobserved":sum(1 for a in roster if not a.get("observed")),
        }
    fresh = bool((out.get("health") or {}).get("fresh"))
    counts = {
        "agents_known": len(agents),
        "connected": sum(1 for a in agents if str(a.get("kind") or "") != "offline"),
        "disconnected": sum(1 for a in agents if str(a.get("kind") or "") == "offline"),
        "in_call": sum(1 for a in agents if str(a.get("kind") or "") in {"call", "hold"}),
        "on_hold": sum(1 for a in agents if str(a.get("kind") or "") == "hold"),
        "available": sum(1 for a in agents if str(a.get("kind") or "") == "ready"),
        "unavailable": sum(1 for a in agents if str(a.get("kind") or "") not in {"offline", "ready", "call", "hold"}),
        "current_calls": sum(1 for a in agents if a.get("current_call")) if fresh else None,
        "calls_waiting": None,
    }
    out["kpi"] = counts
    out["scope"] = {"group_id": target, "locked": bool(p["filter_locked"]), "mode": p["mode"]}
    try:
        import live_quality
        raw_incidents = live_quality.incident_snapshot(active_only=True, limit=200)
        incidents = [x for x in raw_incidents if _incident_allowed(x, {target})] if target else filter_live_incidents(user, raw_incidents)
        center = live_quality.quality_center(out, incidents=incidents)
        out["quality"] = {
            "generated_at": center.get("engine", {}).get("checked_at"),
            "operational_status": center.get("last_operational_status") or center.get("status"),
            "data_quality": center.get("data_quality"),
            "active_incident_count": len(incidents),
            "active_incidents": incidents,
            "center": center,
        }
    except Exception:
        out["quality"] = {
            "operational_status": {"level_key": "INDETERMINE", "label": "INDÉTERMINÉ", "rank": 0, "color": "#667085", "reason": "quality_engine_unavailable"},
            "data_quality": {"quality": "unavailable", "label": "Qualité Live indisponible", "color": "#667085"},
            "active_incident_count": 0, "active_incidents": [],
        }
    return out


def filter_live_campaign_payload(user, payload):
    allowed = effective_group_ids(user)
    if allowed is None:
        return payload
    out = copy.deepcopy(payload)
    out["groups"] = visible_groups(user, out.get("groups") or [])
    services = {str(g.get("service_name") or "") for g in out["groups"] if str(g.get("service_name") or "")}
    if isinstance(out.get("services"), list):
        out["services"] = [s for s in out["services"] if str((s or {}).get("name") if isinstance(s, dict) else s) in services]
    campaigns = []
    allowed_lines={str(x) for x in _selected_scope_ids(allowed).get("line_ids") or []}
    for c in out.get("campaigns") or []:
        gids = {str((g or {}).get("id") or (g or {}).get("group_id") or "") for g in c.get("groups") or []}
        if gids & allowed:
            item = copy.deepcopy(c)
            item["groups"] = [g for g in c.get("groups") or [] if str((g or {}).get("id") or (g or {}).get("group_id") or "") in allowed]
            queues=item.get("queues") or {}
            if isinstance(queues,dict):
                queues["configured"]=[q for q in queues.get("configured") or [] if str((q or {}).get("line_id") or "") in allowed_lines]
                queues["observed_live"]=[x for x in queues.get("observed_live") or [] if str(x) in allowed_lines]
                queues["top_files"]=[q for q in queues.get("top_files") or [] if str((q or {}).get("file_id") or "") in allowed_lines]
            if gids-allowed:
                # Campaign-level historical KPI would aggregate queues outside the user's scope.
                # Redact rather than presenting cross-group data as if it belonged to this group.
                for key in ("last_15m","today","reference"):
                    item[key]={"source":"Stats.INBOUND importé","quality":"unavailable","reason":"campaign_spans_unauthorized_groups","calls":{},"wait":{},"agents_treating":{}}
                item["trend"]={"volume_change_vs_reference":None,"reference_label":"indisponible pour ce périmètre"}
                item["scope_warning"]="Campagne partagée avec un groupe non autorisé : KPI historiques masqués."
            campaigns.append(item)
    out["campaigns"] = campaigns
    return out


def filter_live_search_payload(user, payload):
    allowed = effective_group_ids(user)
    if allowed is None:
        return payload
    scope = _selected_scope_ids(allowed)
    agents = {str(x) for x in scope.get("member_agent_ids") or []}
    lines = {str(x) for x in scope.get("line_ids") or []}
    campaigns = {str(x).casefold() for x in scope.get("campaign_ids") or []}
    out = copy.deepcopy(payload)
    rows = []
    for row in out.get("rows") or []:
        agent = str(row.get("agent") or "")
        line = str(row.get("line_id") or "")
        campaign = str(row.get("campaign") or "").casefold()
        if (agent and agent in agents) or (line and line in lines):
            rows.append(row)
    out["rows"] = rows
    out["count"] = len(rows)
    if isinstance(out.get("agents"), list):
        out["agents"] = [a for a in out["agents"] if str((a or {}).get("agent") if isinstance(a, dict) else a) in agents]
    return out


def incident_allowed(user, incident):
    allowed = effective_group_ids(user)
    if allowed is None:
        return True
    return _incident_allowed(incident or {}, allowed)


def filter_live_campaign_detail(user, payload):
    """Restrict campaign drill-down rows to the user's business-group scope."""
    allowed = effective_group_ids(user)
    if allowed is None or not isinstance(payload, dict):
        return payload
    scope = _selected_scope_ids(allowed)
    agents = {str(x) for x in scope.get("member_agent_ids") or []}
    lines = {str(x) for x in scope.get("line_ids") or []}
    campaigns = {str(x) for x in scope.get("campaign_ids") or []}
    out = copy.deepcopy(payload)
    summary = out.get("summary") or {}
    original_groups=list(summary.get("groups") or [])
    original_gids={str((g or {}).get("id") or (g or {}).get("group_id") or "") for g in original_groups}
    groups = [g for g in original_groups if str((g or {}).get("id") or (g or {}).get("group_id") or "") in allowed]
    cid = str(out.get("campaign_id") or summary.get("campaign_id") or "")
    if not groups and cid and cid not in campaigns:
        raise ScopeDenied("Accès refusé à cette campagne pour le périmètre métier autorisé.")
    summary["groups"] = groups
    if original_gids-allowed:
        for key in ("last_15m","today","reference"):
            summary[key]={"source":"Stats.INBOUND importé","quality":"unavailable","reason":"campaign_spans_unauthorized_groups","calls":{},"wait":{},"agents_treating":{}}
        summary["trend"]={"volume_change_vs_reference":None,"reference_label":"indisponible pour ce périmètre"}
        summary["scope_warning"]="Campagne partagée avec un groupe non autorisé : KPI historiques masqués."
    out["summary"] = summary
    out["queues"] = [q for q in out.get("queues") or [] if str((q or {}).get("file_id") or "") in lines]
    out["agents"] = [a for a in out.get("agents") or [] if str((a or {}).get("agent") or "") in agents]
    rows=[]
    for row in ((out.get("calls") or {}).get("rows") or []):
        aid=str(row.get("agent") or ""); line=str(row.get("line_id") or "")
        if (aid and aid in agents) or (line and line in lines):
            rows.append(row)
    if isinstance(out.get("calls"), dict):
        out["calls"]["rows"] = rows
        out["calls"]["count"] = len(rows)
    return out


def filter_quality_priority_payload(user, payload):
    if not isinstance(payload, dict):
        return payload
    allowed = effective_group_ids(user)
    if allowed is None:
        return payload
    scope = _selected_scope_ids(allowed)
    agents={str(x) for x in scope.get("member_agent_ids") or []}
    lines={str(x) for x in scope.get("line_ids") or []}
    out=filter_group_catalog_payload(user, payload)
    for key in ("agents","agent_priorities"):
        if isinstance(out.get(key),list):
            out[key]=[x for x in out[key] if str((x or {}).get("agent") or (x or {}).get("agent_id") or (x or {}).get("id") or "") in agents]
    for key in ("queues","files","queue_priorities"):
        if isinstance(out.get(key),list):
            out[key]=[x for x in out[key] if str((x or {}).get("line_id") or (x or {}).get("file_id") or (x or {}).get("id") or "") in lines]
    return out
