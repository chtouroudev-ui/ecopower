"""Phase 4 campaign monitoring contract for Nelyio.

The module keeps four time windows explicit and source-separated:
- ``live_now``: facts proven by the current Hermes Live snapshot;
- ``last_15m`` / ``today`` / ``reference``: canonical Stats.INBOUND imports;
- queue concentration: ODCalls.FirstQueue, used only for operational drill-down.

Campaign is never treated as Group.  Campaign identity is resolved against the
configured campaign catalogue only when the id/label match is unambiguous.
Missing or uncertified Live service metrics stay ``None`` (never zero).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median
import math
import time

from nelyio_time import day_bounds, display, local_day, local_datetime
from quality_importer import agent_key
from quality_scope import load_quality_file_scope
from supervision_db import connect, config

LOW_VOLUME_DEFAULT = 20
REFERENCE_DAYS = 4


def _clean(value):
    return str(value or "").strip()


def _cf(value):
    return _clean(value).casefold()


def _metric(value, *, source, quality="reliable", reason="", sample_size=None, freshness_seconds=None):
    return {
        "value": value,
        "source": source,
        "quality": quality,
        "reason": reason,
        "sample_size": sample_size,
        "freshness_seconds": freshness_seconds,
    }


def _unavailable(reason, source):
    return _metric(None, source=source, quality="unavailable", reason=reason)


def _campaign_catalog(scope=None):
    from identity_resolver import campaign_catalog
    # Keep this module's loader as the injection point used by existing tests
    # and callers; identity_resolver only normalizes the supplied catalogue.
    if scope is None:
        scope=load_quality_file_scope()
    return campaign_catalog(scope)


def _resolver(scope=None):
    from identity_resolver import resolve_campaign_identity
    catalog=_campaign_catalog(scope)

    def resolve(raw_id="", raw_label=""):
        item=resolve_campaign_identity(raw_id,raw_label,scope=scope,catalog=catalog)
        return item["campaign_id"],item["campaign_label"],item["identity_quality"]

    return resolve, catalog[0]


def _percentile(values, p):
    vals = sorted(float(v) for v in values if v is not None and float(v) >= 0)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * float(p)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return vals[lo] * (1.0 - frac) + vals[hi] * frac


def _day_ref(c, day):
    from quality_metrics import _version_ready
    row = c.execute(
        """SELECT cc.import_id,q.version FROM call_coverage cc
           LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id WHERE cc.day=?""",
        (day,),
    ).fetchone()
    return row if row and _version_ready(row["version"]) else None


def _previous_same_weekdays(c, target, limit=REFERENCE_DAYS):
    from quality_metrics import _version_ready
    d = date.fromisoformat(target)
    rows = c.execute(
        """SELECT cc.day,q.version FROM call_coverage cc
           LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id
           WHERE cc.day<? ORDER BY cc.day DESC LIMIT 90""",
        (target,),
    ).fetchall()
    return [
        str(r["day"])
        for r in rows
        if _version_ready(r["version"]) and date.fromisoformat(str(r["day"])).weekday() == d.weekday()
    ][: int(limit)]


def _fact_rows(c, day, lo, hi):
    ref = _day_ref(c, day)
    if not ref or float(hi) <= float(lo):
        return [], ref
    rows = [
        dict(r)
        for r in c.execute(
            """SELECT f.start,f.agent,f.campaign,f.campaign_name,f.received,f.answered,f.abandoned,
                      f.closed,f.overflow,f.rerouted,f.before_queue,f.transferred,f.wait,
                      f.invalid_duration,f.lost,f.call_duration,f.payload
               FROM quality_inbound_facts f
               WHERE f.import_id=? AND f.day=? AND f.start>=? AND f.start<?""",
            (ref["import_id"], day, float(lo), float(hi)),
        )
    ]
    return rows, ref


def _governance_context(days):
    try:
        from pilotage_quality import _catalog, _governance_context
        groups, _services = _catalog()
        return _governance_context(groups, days)
    except Exception:
        return None


def _campaign_metrics(rows, governance, *, min_volume=LOW_VOLUME_DEFAULT):
    from pilotage_quality import _aggregate_fact_rows
    resolve, _ = _resolver()
    buckets = defaultdict(list)
    labels = {}
    identities = {}
    latest = None
    for row in rows:
        cid, label, identity = resolve(row.get("campaign"), row.get("campaign_name"))
        if not cid:
            continue
        buckets[cid].append(row)
        labels[cid] = label
        identities[cid] = identity
        try:
            latest = max(float(row.get("start") or 0), latest or 0)
        except (TypeError, ValueError):
            pass
    out = {}
    for cid, items in buckets.items():
        aggregate, visible = _aggregate_fact_rows(items, 60, governance)
        waits = []
        for r in visible:
            aid = agent_key(r.get("agent"))
            if aid in ("", "0"):
                continue
            try:
                w = float(r.get("wait"))
            except (TypeError, ValueError):
                continue
            if w >= 0:
                waits.append(w)
        received = int(aggregate.get("received") or 0)
        abandoned = int(aggregate.get("abandoned") or 0)
        handled = int(aggregate.get("qos_numerator") or 0)
        out[cid] = {
            "campaign_id": cid,
            "campaign_label": labels.get(cid, cid),
            "identity_quality": identities.get(cid, "observed_only"),
            "received": received,
            "handled": handled,
            "treated_agent": int(aggregate.get("treated_agent") or 0),
            "abandoned": abandoned,
            "abandon_rate": (100.0 * abandoned / received if received else None),
            "qos": aggregate.get("qos_percent"),
            "wait_average_seconds": aggregate.get("asa_seconds"),
            "wait_median_seconds": (median(waits) if waits else None),
            "wait_p90_seconds": _percentile(waits, 0.90),
            "wait_sample_size": len(waits),
            "low_volume_flag": received < int(min_volume),
            "agents_treating": int(aggregate.get("agents_treating") or 0),
            "coherence_ok": bool(aggregate.get("coherence_ok")),
            "invalid_durations": int(aggregate.get("invalid_durations") or 0),
            "governance_excluded": int(aggregate.get("governance_excluded") or 0),
        }
    return out, latest


def _queue_rows(c, day, lo, hi, governance):
    """Operational campaign/file distribution from certified ODCalls.FirstQueue."""
    if float(hi) <= float(lo):
        return {}
    row = c.execute("SELECT import_id FROM call_coverage WHERE day=?", (day,)).fetchone()
    if not row:
        return {}
    import_id = int(row["import_id"])
    resolve, _ = _resolver()
    queue_names = {}
    for q in load_quality_file_scope().get("queues", []) or []:
        queue_names[str(q.get("line_id") or "")] = _clean(q.get("display_name") or q.get("line_name"))
    acc = defaultdict(lambda: defaultdict(lambda: {"received": 0, "treated": 0, "abandoned": 0, "agents": set()}))
    sql = """SELECT p.start,p.first_agent,p.abandon,p.duration,p.campaign,
                    d.call_duration,d.first_queue,d.first_campaign,d.last_campaign
             FROM phone_calls p
             JOIN phone_call_details d ON d.import_id=p.import_id AND d.call_id=p.call_id
             WHERE p.import_id=? AND p.start>=? AND p.start<? AND COALESCE(p.call_type,'')='1'
               AND COALESCE(TRIM(d.first_queue),'') NOT IN ('','0','-1')"""
    try:
        from pilotage_quality import _governance_decision
    except Exception:
        _governance_decision = None
    for r in c.execute(sql, (import_id, float(lo), float(hi))):
        line = _clean(r["first_queue"])
        raw_campaign = _clean(r["last_campaign"] or r["first_campaign"] or r["campaign"])
        cid, _label, _identity = resolve(raw_campaign, raw_campaign)
        if not cid:
            continue
        aid = agent_key(r["first_agent"])
        assigned = aid not in ("", "0")
        if governance and _governance_decision:
            reason = _governance_decision(
                governance,
                r["start"],
                r["call_duration"] or r["duration"] or 1,
                aid,
                raw_campaign,
                line,
            )
            if reason:
                continue
        item = acc[cid][line]
        item["received"] += 1
        item["treated"] += int(assigned)
        item["abandoned"] += int(bool(r["abandon"]) and not assigned)
        if assigned:
            item["agents"].add(aid)
    out = {}
    for cid, files in acc.items():
        total = sum(v["received"] for v in files.values())
        rows = []
        for fid, values in files.items():
            received = int(values["received"])
            rows.append(
                {
                    "file_id": fid,
                    "file_label": queue_names.get(fid) or ("File " + fid),
                    "received": received,
                    "treated": int(values["treated"]),
                    "abandoned": int(values["abandoned"]),
                    "agents_treating": len(values["agents"]),
                    "share_percent": (100.0 * received / total if total else None),
                }
            )
        rows.sort(key=lambda x: (-x["received"], x["file_label"].casefold()))
        out[cid] = {"total": total, "files": rows}
    return out


def _window(clock, target_day, cfg):
    """Return work-window epochs and display labels, clamped to 'now' for today."""
    start, end_full = day_bounds(target_day, cfg["work_start"], cfg["work_end"])
    if target_day == local_day(clock):
        end = min(max(float(clock), start), end_full)
    else:
        end = end_full
    last_start = max(start, end - 900.0)
    return {
        "start": start,
        "end": end,
        "last15_start": last_start,
        "time_from": display(start)[11:16],
        "time_to": display(end)[11:16],
        "last15_from": display(last_start)[11:16],
    }


def _reference_ranges(days, target_window):
    start_hm = target_window["time_from"]
    end_hm = target_window["time_to"]
    last_hm = target_window["last15_from"]
    out = []
    for day in days:
        start, end = day_bounds(day, start_hm, end_hm) if start_hm != end_hm else (0.0, 0.0)
        last_start, _ = day_bounds(day, last_hm, end_hm) if last_hm != end_hm else (0.0, 0.0)
        out.append((day, start, end, last_start))
    return out


def _median_reference(per_day, min_volume=LOW_VOLUME_DEFAULT):
    all_ids = sorted({cid for day in per_day for cid in day})
    fields = (
        "received", "handled", "treated_agent", "abandoned", "abandon_rate", "qos",
        "wait_average_seconds", "wait_median_seconds", "wait_p90_seconds", "wait_sample_size", "agents_treating",
    )
    out = {}
    for cid in all_ids:
        samples = [d[cid] for d in per_day if cid in d]
        if not samples:
            continue
        row = {
            "campaign_id": cid,
            "campaign_label": next((x.get("campaign_label") for x in samples if x.get("campaign_label")), cid),
            "identity_quality": next((x.get("identity_quality") for x in samples if x.get("identity_quality")), "observed_only"),
            "sample_days": len(samples),
        }
        for field in fields:
            vals = [x.get(field) for x in samples if x.get(field) is not None]
            row[field] = median(vals) if vals else None
        row["low_volume_flag"] = bool(row.get("received") is not None and row["received"] < int(min_volume))
        out[cid] = row
    return out


def empty_history(day, *, reason="quality_permission_required", clock=None):
    clock = time.time() if clock is None else float(clock)
    section = {"source": "Stats.INBOUND importé", "quality": "unavailable", "reason": reason, "campaigns": []}
    if reason in {"quality_permission_required", "permission_unavailable"}:
        note = "Répartition non chargée sans accès Qualité."
    elif reason == "analytics_unavailable":
        note = "Répartition historique temporairement indisponible ; le Live Hermes reste actif."
    else:
        note = "Répartition historique indisponible."
    return {
        "day": str(day),
        "generated_at": clock,
        "today": dict(section),
        "last_15m": dict(section),
        "reference": dict(section, days=[], label="référence indisponible"),
        "queue_distribution": {
            "source": "ODCalls.FirstQueue", "quality": "unavailable", "reason": reason,
            "last_15m": {}, "today": {},
            "note": note,
        },
        "query_plan": {"bounded": True, "historical_loaded": False, "reason": reason},
    }


def historical_view(qs=None, *, clock=None):
    """Bounded historical half of /api/live/campaigns (Analytics worker safe)."""
    qs = qs or {}
    get = lambda key, default="": _clean(qs.get(key, [default])[0])
    clock = time.time() if clock is None else float(clock)
    target = get("day") or local_day(clock)
    date.fromisoformat(target)
    try:
        min_volume = max(1, min(1000, int(get("min_volume", str(LOW_VOLUME_DEFAULT)) or LOW_VOLUME_DEFAULT)))
    except ValueError as exc:
        raise ValueError("Volume minimum campagne invalide") from exc
    cfg = config()
    window = _window(clock, target, cfg)
    with connect() as c:
        reference_days = _previous_same_weekdays(c, target, REFERENCE_DAYS)
        governance = _governance_context([target, *reference_days])
        today_rows, today_ref = _fact_rows(c, target, window["start"], window["end"])
        last_rows, last_ref = _fact_rows(c, target, window["last15_start"], window["end"])
        today, latest_today = _campaign_metrics(today_rows, governance, min_volume=min_volume)
        last15, latest_last15 = _campaign_metrics(last_rows, governance, min_volume=min_volume)
        reference_per_day = []
        for ref_day, ref_start, ref_end, _ref_last in _reference_ranges(reference_days, window):
            rows, _ref = _fact_rows(c, ref_day, ref_start, ref_end)
            metrics, _latest = _campaign_metrics(rows, governance, min_volume=min_volume)
            reference_per_day.append(metrics)
        reference = _median_reference(reference_per_day, min_volume=min_volume) if len(reference_per_day) >= 2 else {}
        queues_today = _queue_rows(c, target, window["start"], window["end"], governance)
        queues_15m = _queue_rows(c, target, window["last15_start"], window["end"], governance)
    source_quality = "reliable" if today_ref else "unavailable"
    if target == local_day(clock) and source_quality == "reliable":
        source_quality = "partial"  # current-day import can still be incomplete; never pretend it is Hermes Live.
    return {
        "day": target,
        "generated_at": clock,
        "work_window": {"from": window["time_from"], "to": window["time_to"]},
        "last_15m_window": {"from": window["last15_from"], "to": window["time_to"]},
        "today": {
            "source": "Stats.INBOUND importé",
            "quality": source_quality,
            "reason": ("current_day_import_is_not_live" if source_quality == "partial" else ("" if today_ref else "no_certified_import")),
            "latest_event_at": latest_today,
            "campaigns": list(today.values()),
        },
        "last_15m": {
            "source": "Stats.INBOUND importé",
            "quality": source_quality,
            "reason": ("current_day_import_is_not_live" if source_quality == "partial" else ("" if last_ref else "no_certified_import")),
            "latest_event_at": latest_last15,
            "campaigns": list(last15.values()),
        },
        "reference": {
            "source": "Stats.INBOUND importé",
            "quality": ("reliable" if len(reference_days) >= 2 else "unavailable"),
            "reason": ("" if len(reference_days) >= 2 else "insufficient_reference_days"),
            "days": reference_days,
            "label": ("médiane de " + str(len(reference_days)) + " même(s) jour(s) de semaine, même tranche") if len(reference_days) >= 2 else "référence insuffisante",
            "campaigns": list(reference.values()),
        },
        "queue_distribution": {
            "source": "ODCalls.FirstQueue",
            "quality": ("partial" if target == local_day(clock) else "reliable") if today_ref else "unavailable",
            "last_15m": queues_15m,
            "today": queues_today,
            "note": "Répartition opérationnelle uniquement ; ne remplace pas les KPI QoS Stats.INBOUND.",
        },
        "query_plan": {
            "bounded": True,
            "stats_inbound_queries_max": 2 + REFERENCE_DAYS,
            "odcalls_queries_max": 2,
            "independent_of_campaign_count": True,
        },
    }


def _indexed(rows):
    return {str(x.get("campaign_id") or ""): dict(x) for x in (rows or []) if x.get("campaign_id")}


def _format_history_metric(row, key, section):
    source = section.get("source") or "Stats.INBOUND importé"
    if not row:
        return _unavailable("campaign_not_present_in_window", source)
    return _metric(row.get(key), source=source, quality=section.get("quality") or "unavailable", reason=section.get("reason") or "", sample_size=row.get("wait_sample_size"))


def _campaign_status(snapshot, campaign_id, campaign_label):
    center = (((snapshot or {}).get("quality") or {}).get("center") or {})
    rows = center.get("scopes") or []
    candidates = {_cf(campaign_id), _cf(campaign_label)}
    for row in rows:
        if row.get("scope_type") != "CAMPAIGN":
            continue
        if _cf(row.get("scope_key")) in candidates or _cf(row.get("scope_label")) in candidates:
            return dict(row.get("status") or {}), int(row.get("incident_count") or 0)
    dq = center.get("data_quality") or ((snapshot or {}).get("quality") or {}).get("data_quality") or {}
    if dq.get("quality") != "reliable":
        return {"level_key": "INDETERMINE", "label": "INDÉTERMINÉ", "rank": 0, "color": "#667085", "reason": "live_data_not_reliable"}, 0
    return {"level_key": "NON_SURVEILLE", "label": "NON SURVEILLÉ", "rank": 0, "color": "#667085", "reason": "no_live_campaign_scope"}, 0


def combine(snapshot, history, *, clock=None, include_inactive=False):
    """Merge one Live snapshot and one bounded historical payload into Phase 4 contract."""
    clock = time.time() if clock is None else float(clock)
    scope = load_quality_file_scope()
    resolve, configured_catalog = _resolver(scope)
    today_section = history.get("today") or {}
    last_section = history.get("last_15m") or {}
    ref_section = history.get("reference") or {}
    today = _indexed(today_section.get("campaigns"))
    last15 = _indexed(last_section.get("campaigns"))
    reference = _indexed(ref_section.get("campaigns"))
    queue_distribution = history.get("queue_distribution") or {}
    q_today = dict(queue_distribution.get("today") or {})
    q_15 = dict(queue_distribution.get("last_15m") or {})

    entries = {}
    def ensure(raw_id="", raw_label="", identity_hint=""):
        cid, label, identity = resolve(raw_id, raw_label)
        if not cid:
            return None
        e = entries.setdefault(cid, {"campaign_id": cid, "campaign_label": label, "identity_quality": identity_hint or identity})
        if identity in {"configured_id", "configured_label"}:
            e["campaign_label"] = label
            e["identity_quality"] = identity
        return e

    for item in configured_catalog:
        ensure(item["campaign_id"], item["campaign_label"])
    for section in (today, last15, reference):
        for cid, row in section.items():
            ensure(cid, row.get("campaign_label"), row.get("identity_quality"))
    for agent in (snapshot or {}).get("agents") or []:
        raw = _clean(agent.get("campaign") or (agent.get("current_call") or {}).get("campaign"))
        if raw:
            ensure(raw, raw, "observed_label")

    groups = [g for g in (scope.get("groups") or []) if str(g.get("id")) != "unassigned"]
    agent_files = {str(a): {str(x) for x in files} for a, files in (scope.get("agent_files") or {}).items()}
    configured_by_line = {str(k): set(v or []) for k, v in (scope.get("configured_agents_by_line") or {}).items()}
    active_by_line = {str(k): set(v or []) for k, v in ((scope.get("agents_by_line_state") or {}).get("active") or {}).items()}
    active_agents = set(agent_files)
    live_agents = {str(a.get("agent") or ""): a for a in (snapshot or {}).get("agents") or [] if a.get("agent")}
    live_lines = defaultdict(set)
    live_campaign_agents = defaultdict(set)
    current_calls_by_campaign = defaultdict(int)
    observed_lines_by_campaign = defaultdict(set)
    for aid, agent in live_agents.items():
        line = _clean(agent.get("line_id") or (agent.get("current_call") or {}).get("line_id"))
        if line:
            live_lines[line].add(aid)
        raw_campaign = _clean(agent.get("campaign") or (agent.get("current_call") or {}).get("campaign"))
        if raw_campaign:
            cid, _label, _ident = resolve(raw_campaign, raw_campaign)
            if cid:
                live_campaign_agents[cid].add(aid)
                if line:
                    observed_lines_by_campaign[cid].add(line)
                if agent.get("current_call"):
                    current_calls_by_campaign[cid] += 1

    queue_status = {}
    for row in ((((snapshot or {}).get("quality") or {}).get("center") or {}).get("scopes") or []):
        if row.get("scope_type") == "QUEUE":
            queue_status[str(row.get("scope_key") or "")] = row

    campaign_to_files = scope.get("campaign_to_files") or {}
    result = []
    for cid, e in entries.items():
        configured_files = [dict(x) for x in (campaign_to_files.get(cid) or [])]
        configured_ids = {str(x.get("line_id") or "") for x in configured_files if x.get("line_id") is not None}
        observed_ids = set(observed_lines_by_campaign.get(cid, set()))
        file_ids = configured_ids | observed_ids
        group_rows = []
        services = set()
        for g in groups:
            glines = {str(x) for x in (g.get("line_ids") or [])}
            if file_ids and glines & file_ids:
                group_rows.append({"id": str(g.get("id") or ""), "name": _clean(g.get("name")), "service": _clean(g.get("service_name"))})
                if _clean(g.get("service_name")):
                    services.add(_clean(g.get("service_name")))
        configured_agents = set()
        for line in configured_ids:
            configured_agents.update(configured_by_line.get(line, set()))
        active_on_queues = {aid for aid in active_agents if agent_files.get(aid, set()) & configured_ids} if configured_ids else set()
        coverage_pool = active_on_queues or set(live_campaign_agents.get(cid, set()))
        state_counts = {"connected": 0, "available": 0, "on_call": 0, "on_hold": 0, "wrap_up": 0, "on_break": 0}
        for aid in coverage_pool:
            agent = live_agents.get(aid)
            if not agent:
                continue
            kind = str(agent.get("kind") or "other")
            if kind != "offline":
                state_counts["connected"] += 1
            if kind == "ready": state_counts["available"] += 1
            if kind in ("call", "hold"): state_counts["on_call"] += 1
            if kind == "hold": state_counts["on_hold"] += 1
            if kind == "wrap": state_counts["wrap_up"] += 1
            if kind == "pause": state_counts["on_break"] += 1

        trow = today.get(cid)
        lrow = last15.get(cid)
        rrow = reference.get(cid)
        qdist = q_15.get(cid) if (q_15.get(cid) or {}).get("total") else q_today.get(cid)
        concentration_window = "last_15m" if (q_15.get(cid) or {}).get("total") else ("today" if (q_today.get(cid) or {}).get("total") else "unavailable")
        raw_qfiles = list((qdist or {}).get("files") or [])
        qfiles = []
        for raw_file in raw_qfiles:
            f = dict(raw_file)
            fid = str(f.get("file_id") or "")
            active_ids = set(active_by_line.get(fid, set()))
            f["active_agents"] = len(active_ids)
            f["connected_agents"] = sum(1 for aid in active_ids if aid in live_agents and str(live_agents[aid].get("kind") or "") != "offline")
            f["available_agents"] = sum(1 for aid in active_ids if aid in live_agents and str(live_agents[aid].get("kind") or "") == "ready")
            f["on_call_agents"] = sum(1 for aid in active_ids if aid in live_agents and str(live_agents[aid].get("kind") or "") in ("call", "hold"))
            f["on_hold_agents"] = sum(1 for aid in active_ids if aid in live_agents and str(live_agents[aid].get("kind") or "") == "hold")
            f["status"] = dict((queue_status.get(fid) or {}).get("status") or {})
            f["incident_count"] = int((queue_status.get(fid) or {}).get("incident_count") or 0)
            qfiles.append(f)
        top_share = qfiles[0].get("share_percent") if qfiles else None
        active_file_ids = set(observed_ids)
        if qdist:
            active_file_ids.update(str(x.get("file_id") or "") for x in qfiles if int(x.get("received") or 0) > 0)
        with_active_agents = {fid for fid in configured_ids if active_by_line.get(fid)}
        with_calls = {str(x.get("file_id") or "") for x in qfiles if int(x.get("received") or 0) > 0}
        under_tension = sum(1 for fid in file_ids if int((queue_status.get(fid) or {}).get("incident_count") or 0) > 0)
        status, incident_count = _campaign_status(snapshot, cid, e.get("campaign_label"))
        ref_received = rrow.get("received") if rrow else None
        today_received = trow.get("received") if trow else None
        volume_change = None
        if ref_received not in (None, 0) and today_received is not None:
            volume_change = 100.0 * (float(today_received) - float(ref_received)) / float(ref_received)

        observed_today=observed_15m=observed_60m=0
        for aid in coverage_pool:
            act=(live_agents.get(aid) or {}).get("activity") or {}
            for raw,stats in (act.get("campaigns") or {}).items():
                if _campaign_matches(resolve,cid,e.get("campaign_label") or cid,raw):
                    observed_today += int((stats or {}).get("today") or 0)
                    observed_15m += int((stats or {}).get("last_15m") or 0)
                    observed_60m += int((stats or {}).get("last_60m") or 0)
        live_quality = "reliable" if ((snapshot or {}).get("health") or {}).get("fresh") else "unavailable"
        live_reason = "" if live_quality == "reliable" else "live_data_not_fresh"
        live_now = {
            "source": "Hermes Live + configuration files/agents",
            "quality": live_quality,
            "agents": {
                "configured": _metric(len(configured_agents), source="Agents.csv/Queues", quality="reliable" if configured_ids else "unavailable", reason="" if configured_ids else "campaign_queue_mapping_unavailable"),
                "active_on_queues": _metric(len(active_on_queues), source="Agents.csv/Queues ACTIVE", quality="reliable" if configured_ids else "unavailable", reason="" if configured_ids else "campaign_queue_mapping_unavailable"),
                "connected": _metric(state_counts["connected"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "available": _metric(state_counts["available"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "on_call": _metric(state_counts["on_call"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "on_hold": _metric(state_counts["on_hold"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "wrap_up": _metric(state_counts["wrap_up"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "on_break": _metric(state_counts["on_break"] if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
            },
            "calls": {
                "current_observed": _metric(current_calls_by_campaign.get(cid, 0) if live_quality == "reliable" else None, source="Hermes Live", quality=live_quality, reason=live_reason),
                "observed_15m": _metric(observed_15m, source="Hermes Live observations", quality="reliable"),
                "observed_60m": _metric(observed_60m, source="Hermes Live observations", quality="reliable"),
                "observed_today": _metric(observed_today, source="Hermes Live observations", quality="reliable"),
                "waiting_now": _unavailable("semantics_not_certified", "Hermes Live"),
                "waiting_now_status": "unavailable",
                "oldest_waiting_seconds": _unavailable("semantics_not_certified", "Hermes Live"),
            },
        }
        def history_block(row, section):
            return {
                "source": section.get("source") or "Stats.INBOUND importé",
                "quality": section.get("quality") or "unavailable",
                "reason": section.get("reason") or "",
                "calls": {
                    "received": _format_history_metric(row, "received", section),
                    "handled": _format_history_metric(row, "handled", section),
                    "abandoned": _format_history_metric(row, "abandoned", section),
                    "abandon_rate": _format_history_metric(row, "abandon_rate", section),
                    "qos": _format_history_metric(row, "qos", section),
                },
                "wait": {
                    "average_seconds": _format_history_metric(row, "wait_average_seconds", section),
                    "median_seconds": _format_history_metric(row, "wait_median_seconds", section),
                    "p90_seconds": _format_history_metric(row, "wait_p90_seconds", section),
                    "sample_size": (row.get("wait_sample_size") if row else None),
                    "low_volume_flag": bool(row.get("low_volume_flag")) if row else False,
                },
                "agents_treating": _format_history_metric(row, "agents_treating", section),
            }

        item = {
            "campaign_id": cid,
            "campaign_label": e.get("campaign_label") or cid,
            "identity_quality": e.get("identity_quality") or "observed_only",
            "services": sorted(services, key=str.casefold),
            "service": (sorted(services, key=str.casefold)[0] if len(services) == 1 else None),
            "service_quality": ("unique" if len(services) == 1 else ("multiple" if len(services) > 1 else "unavailable")),
            "groups": group_rows,
            "queues": {
                "configured": configured_files,
                "observed_live": sorted(observed_ids),
                "count_configured": len(configured_ids),
                "count_active": len(active_file_ids),
                "count_with_calls": len(with_calls),
                "count_with_active_agents": len(with_active_agents),
                "count_under_tension": under_tension,
                "distribution_window": concentration_window,
                "distribution_source": queue_distribution.get("source") or "ODCalls.FirstQueue",
                "distribution_quality": queue_distribution.get("quality") or "unavailable",
                "top_share_percent": top_share,
                "top_files": qfiles[:5],
            },
            "live_now": live_now,
            "last_15m": history_block(lrow, last_section),
            "today": history_block(trow, today_section),
            "reference": history_block(rrow, ref_section),
            "trend": {
                "volume_change_vs_reference": volume_change,
                "reference_label": ref_section.get("label") or "référence indisponible",
            },
            "status": status,
            "incident_count": incident_count,
        }
        active = bool(current_calls_by_campaign.get(cid) or state_counts["connected"] or (lrow or {}).get("received") or (trow or {}).get("received") or incident_count)
        item["active"] = active
        if active or include_inactive:
            result.append(item)

    result.sort(key=lambda x: (-int((x.get("status") or {}).get("rank") or 0), -int(x.get("incident_count") or 0), -int((((x.get("last_15m") or {}).get("calls") or {}).get("received") or {}).get("value") or 0), str(x.get("campaign_label") or "").casefold()))
    return {
        "generated_at": clock,
        "day": history.get("day") or local_day(clock),
        "windows": {
            "live_now": {"source": "Hermes Live", "quality": "reliable" if ((snapshot or {}).get("health") or {}).get("fresh") else "unavailable"},
            "last_15m": {k: v for k, v in last_section.items() if k != "campaigns"},
            "today": {k: v for k, v in today_section.items() if k != "campaigns"},
            "reference": {k: v for k, v in ref_section.items() if k != "campaigns"},
        },
        "campaigns": result,
        "count": len(result),
        "query_plan": history.get("query_plan") or {},
        "limitations": [
            "Campagne et groupe restent deux dimensions distinctes ; les groupes sont déduits uniquement des files configurées concernées.",
            "15 dernières minutes / aujourd'hui / référence proviennent de Stats.INBOUND importé, jamais présentés comme Hermes temps réel.",
            "La concentration par file utilise ODCalls.FirstQueue uniquement pour le drill-down opérationnel ; elle ne remplace pas les KPI QoS officiels.",
            "waiting_now et oldest_waiting restent non disponibles tant que la sémantique des compteurs Hermes n'est pas certifiée.",
        ],
    }


def historical_drilldown_view(qs, campaign_id, *, clock=None):
    """Historical half of the Phase 5 campaign drill-down.

    The expensive part stays in the Analytics worker in external-service mode.
    Stats.AGENT is used only for campaign/agent handled-call ownership and
    conversation/HOLD evidence; the canonical service KPIs remain Stats.INBOUND.
    """
    clock=time.time() if clock is None else float(clock)
    qs=qs or {}
    history=historical_view(qs,clock=clock)
    scope=load_quality_file_scope()
    resolve,_=_resolver(scope)
    cid,label,identity=resolve(campaign_id,campaign_id)
    source='Stats.AGENT importé'
    result=dict(source=source,quality='unavailable',reason='',campaign_id=cid,campaign_label=label,agents={},query_plan={'bounded':True,'agent_queries_max':2})
    if not cid or cid.startswith('RAW:') or identity not in {'configured_id','configured_label'}:
        result['reason']='campaign_identity_not_certified'
        return {'history':history,'agent_metrics':result}
    target=history.get('day') or local_day(clock)
    cfg=config();window=_window(clock,target,cfg)
    try:
        with connect() as c:
            ref=c.execute("""SELECT cov.import_id,q.hold_reference FROM coverage cov
                             LEFT JOIN quality_agent_imports q ON q.import_id=cov.import_id
                             WHERE cov.day=?""",(target,)).fetchone()
            if not ref:
                result['reason']='stats_agent_import_unavailable'
                return {'history':history,'agent_metrics':result}
            import_id=int(ref['import_id']);hold_known=bool(ref['hold_reference'])
            rows=c.execute("""SELECT agent,MAX(name) AS name,
                       COUNT(DISTINCT CASE WHEN kind='inbound' AND TRIM(COALESCE(session,''))<>'' THEN session
                                           WHEN kind='inbound' THEN row_key END) AS handled,
                       SUM(CASE WHEN kind='inbound' AND "end">start THEN "end"-start ELSE 0 END) AS conversation_sum,
                       SUM(CASE WHEN kind='inbound' AND "end">start THEN 1 ELSE 0 END) AS conversation_count,
                       SUM(CASE WHEN kind='hold' AND "end">start THEN "end"-start ELSE 0 END) AS hold_seconds,
                       SUM(CASE WHEN kind='hold' AND "end">start THEN 1 ELSE 0 END) AS hold_segments
                    FROM quality_agent_facts
                    WHERE import_id=? AND start>=? AND start<? AND TRIM(COALESCE(campaign,''))=?
                    GROUP BY agent""",(import_id,float(window['start']),float(window['end']),cid)).fetchall()
        q='partial' if target==local_day(clock) else 'reliable'
        result.update(quality=q,reason='current_day_import_is_not_live' if q=='partial' else '',hold_quality=('reliable' if hold_known else 'unavailable'))
        for r in rows:
            aid=agent_key(r['agent'])
            if not aid:continue
            count=int(r['conversation_count'] or 0)
            result['agents'][aid]=dict(
                agent=aid,name=_clean(r['name']),handled=int(r['handled'] or 0),
                call_average_seconds=(float(r['conversation_sum'] or 0)/count if count else None),
                call_sample_size=count,hold_seconds=(float(r['hold_seconds'] or 0) if hold_known else None),
                hold_segments=(int(r['hold_segments'] or 0) if hold_known else None),
                source=source,quality=q,hold_quality=('reliable' if hold_known else 'unavailable'))
    except Exception:
        result['reason']='stats_agent_metrics_unavailable'
    return {'history':history,'agent_metrics':result}


def _campaign_matches(resolve, cid, label, raw):
    raw=_clean(raw)
    if not raw:return False
    rid,rlabel,_=resolve(raw,raw)
    return bool(rid==cid or (_cf(raw) in {_cf(cid),_cf(label),_cf(rlabel)}))


def drilldown(snapshot, historical_bundle, campaign_id, *, calls_preview=None, clock=None):
    """Build the bounded Phase 5 campaign -> file -> agent -> call contract."""
    clock=time.time() if clock is None else float(clock)
    bundle=historical_bundle or {}
    history=bundle.get('history') if isinstance(bundle,dict) and 'history' in bundle else bundle
    history=history or empty_history(local_day(clock),clock=clock,reason='analytics_unavailable')
    agent_history=(bundle.get('agent_metrics') or {}) if isinstance(bundle,dict) else {}
    combined=combine(snapshot,history,clock=clock,include_inactive=True)
    selected=next((x for x in combined.get('campaigns',[]) if str(x.get('campaign_id'))==str(campaign_id)),None)
    if not selected:
        raise KeyError('Campagne Live introuvable')
    scope=load_quality_file_scope();resolve,_=_resolver(scope)
    cid=str(selected.get('campaign_id') or '');label=str(selected.get('campaign_label') or cid)
    configured=list((selected.get('queues') or {}).get('configured') or [])
    configured_ids={str(x.get('line_id') or '') for x in configured if str(x.get('line_id') or '')}
    observed_ids={str(x) for x in ((selected.get('queues') or {}).get('observed_live') or []) if str(x)}
    queue_names={str(q.get('line_id') or ''):_clean(q.get('display_name') or q.get('line_name') or ('File '+str(q.get('line_id') or ''))) for q in (scope.get('queues') or [])}
    live_agents={str(a.get('agent') or ''):a for a in (snapshot or {}).get('agents') or [] if a.get('agent')}
    active_by_line={str(k):set(v or []) for k,v in (((scope.get('agents_by_line_state') or {}).get('active') or {}).items())}
    agent_files={str(a):{str(x) for x in files} for a,files in (scope.get('agent_files') or {}).items()}
    queue_status={}
    for row in ((((snapshot or {}).get('quality') or {}).get('center') or {}).get('scopes') or []):
        if row.get('scope_type')=='QUEUE':queue_status[str(row.get('scope_key') or '')]=row
    qdist_root=(history.get('queue_distribution') or {})
    q15=((qdist_root.get('last_15m') or {}).get(cid) or {})
    qt=((qdist_root.get('today') or {}).get(cid) or {})
    qdist=q15 if q15.get('total') else qt
    qwindow='last_15m' if q15.get('total') else ('today' if qt.get('total') else 'unavailable')
    qby={str(x.get('file_id') or ''):dict(x) for x in (qdist.get('files') or [])}
    all_file_ids=configured_ids|observed_ids|set(qby)
    queues=[]
    for fid in sorted(all_file_ids,key=lambda x:(queue_names.get(x,x).casefold(),x)):
        hist=qby.get(fid)
        active_ids=set(active_by_line.get(fid,set()))
        live_ids={aid for aid in active_ids if aid in live_agents}
        stat=queue_status.get(fid) or {}
        queues.append(dict(
            file_id=fid,file_label=(hist or {}).get('file_label') or queue_names.get(fid) or ('File '+fid),
            configured=fid in configured_ids,observed_live=fid in observed_ids,
            received=(hist.get('received') if hist else None),treated=(hist.get('treated') if hist else None),
            abandoned=(hist.get('abandoned') if hist else None),share_percent=(hist.get('share_percent') if hist else None),
            agents_treating=(hist.get('agents_treating') if hist else None),
            active_agents=len(active_ids),connected_agents=sum(1 for aid in live_ids if str(live_agents[aid].get('kind') or '')!='offline'),
            available_agents=sum(1 for aid in live_ids if str(live_agents[aid].get('kind') or '')=='ready'),
            on_call_agents=sum(1 for aid in live_ids if str(live_agents[aid].get('kind') or '') in ('call','hold')),
            on_hold_agents=sum(1 for aid in live_ids if str(live_agents[aid].get('kind') or '')=='hold'),
            post_call_agents=sum(1 for aid in live_ids if str(live_agents[aid].get('kind') or '')=='wrap'),
            status=dict(stat.get('status') or {}),incident_count=int(stat.get('incident_count') or 0),
            history_quality=qdist_root.get('quality') or 'unavailable',history_window=qwindow))
    active_campaign_agents=set().union(*(active_by_line.get(fid,set()) for fid in configured_ids)) if configured_ids else set()
    observed_campaign_agents=set()
    for aid,a in live_agents.items():
        raw=_clean(a.get('campaign') or (a.get('current_call') or {}).get('campaign'))
        if _campaign_matches(resolve,cid,label,raw):observed_campaign_agents.add(aid)
    agent_ids=active_campaign_agents|observed_campaign_agents
    h_agents=dict(agent_history.get('agents') or {})
    agents=[]
    for aid in agent_ids:
        a=live_agents.get(aid) or {}
        kind=str(a.get('kind') or 'unobserved')
        active_files=sorted(agent_files.get(aid,set())&configured_ids)
        hm=h_agents.get(aid) or {}
        agents.append(dict(
            agent=aid,name=_clean(a.get('name') or hm.get('name') or aid),kind=kind,state=_clean(a.get('state')),
            state_age_seconds=a.get('state_age_seconds'),ticking=bool(a.get('ticking')),fresh=a.get('fresh'),
            line_id=_clean(a.get('line_id') or (a.get('current_call') or {}).get('line_id')),
            campaign=_clean(a.get('campaign') or (a.get('current_call') or {}).get('campaign')),
            groups=list(a.get('groups') or []),service_names=list(a.get('service_names') or []),
            current_call=a.get('current_call'),activity=a.get('activity') or {},active_on_campaign_queues=aid in active_campaign_agents,
            live_on_campaign=aid in observed_campaign_agents,active_files=active_files,
            handled_today=hm.get('handled'),call_average_seconds=hm.get('call_average_seconds'),
            call_sample_size=hm.get('call_sample_size'),hold_seconds=hm.get('hold_seconds'),hold_segments=hm.get('hold_segments'),
            history_source=hm.get('source') or agent_history.get('source'),history_quality=hm.get('quality') or agent_history.get('quality') or 'unavailable',
            hold_quality=hm.get('hold_quality') or agent_history.get('hold_quality') or 'unavailable'))
    agents.sort(key=lambda x:(not x['live_on_campaign'],x['kind']=='offline',x['kind']=='unobserved',x['name'].casefold(),x['agent']))
    calls=calls_preview or dict(day=combined.get('day'),window='30m',count=0,rows=[],source='Hermes Live',quality='unavailable',truncated=False)
    return dict(
        generated_at=clock,day=combined.get('day'),campaign_id=cid,campaign_label=label,
        summary=selected,queues=queues,agents=agents,calls=calls,
        agent_history=dict(source=agent_history.get('source') or 'Stats.AGENT importé',quality=agent_history.get('quality') or 'unavailable',reason=agent_history.get('reason') or ''),
        calls_links={
            'live_search':dict(campaign=label,window='30m'),
            'suspicious_calls':dict(campaign=cid,day=combined.get('day')),
        },
        query_plan=dict(bounded=True,independent_of_queue_count=True,independent_of_agent_count=True,live_spool_queries_max=3,analytics_queries='bounded worker payload'),
        limitations=[
            'Le drill-down conserve Campagne != Groupe ; les agents ACTIVE viennent uniquement des files configurées.',
            'Les appels affichés ici sont des observations Live récentes, pas un historique certifié complet.',
            'Attente en file, durée de conversation Live certifiée et origine de fin ne sont jamais inventées.',
            'Les métriques agent Stats.AGENT sont un contexte importé ; elles ne sont pas présentées comme temps réel.',
        ])

def view(qs=None, *, clock=None, historical=None):
    """Single-process convenience path used outside external-service mode."""
    import collection_store
    clock = time.time() if clock is None else float(clock)
    qs = qs or {}
    get = lambda key, default="": _clean(qs.get(key, [default])[0])
    day = get("day") or local_day(clock)
    history = historical if historical is not None else historical_view(qs, clock=clock)
    snapshot = collection_store.live_supervision_snapshot(day=day, clock=clock)
    include_inactive = get("include_inactive", "0").lower() in {"1", "true", "yes", "on"}
    return combine(snapshot, history, clock=clock, include_inactive=include_inactive)
