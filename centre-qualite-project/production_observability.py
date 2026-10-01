"""Read-only production observability snapshot for Nelyio administrators.

No business identifiers, request query strings, credentials or patient data are
returned. The module aggregates existing health sources and bounded log tails;
it never starts/stops services and never mutates business data.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
_HTTP_SLOW = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+(?P<method>[A-Z]+)\s+(?P<path>/\S*)\s+(?P<seconds>\d+(?:\.\d+)?)s$")
_ANALYTICS_SLOW = re.compile(r"^(?P<stamp>\S+)\s+kind=(?P<kind>[a-zA-Z0-9_\-]+)\s+elapsed=(?P<seconds>\d+(?:\.\d+)?)s(?:\s+key=\S+)?$")
_CACHE_LOCK = threading.Lock()
_CACHE = {"at": 0.0, "value": None}
_CACHE_SECONDS = 5.0

def _env_float(name, default, low, high):
    try:
        return max(low, min(high, float(os.environ.get(name, str(default)))))
    except (TypeError, ValueError):
        return float(default)

def _env_int(name, default, low, high):
    try:
        return max(low, min(high, int(os.environ.get(name, str(default)))))
    except (TypeError, ValueError):
        return int(default)

def _performance_thresholds():
    return {
        "http_log_seconds": _env_float("NELYIO_HTTP_SLOW_SECONDS", 1.0, 0.1, 60.0),
        "analytics_log_seconds": _env_float("NELYIO_ANALYTICS_SLOW_SECONDS", 2.0, 0.25, 120.0),
        "warn_events_per_hour": _env_int("NELYIO_OBS_SLOW_EVENTS_PER_HOUR", 5, 1, 10000),
        "critical_events_per_hour": _env_int("NELYIO_OBS_CRITICAL_SLOW_EVENTS_PER_HOUR", 20, 1, 10000),
        "critical_seconds": _env_float("NELYIO_OBS_CRITICAL_SLOW_SECONDS", 10.0, 0.5, 600.0),
    }


def _version():
    try:
        return json.loads((BASE / "VERSION.json").read_text(encoding="utf-8-sig"))
    except Exception:
        return {"version": "unknown", "edition": "unknown"}


def _tail_lines(path: Path, *, max_bytes=192 * 1024, max_lines=500):
    if not path.is_file():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            raw = fh.read(max_bytes)
        text = raw.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if size > max_bytes and lines:
            lines = lines[1:]
        return lines[-max_lines:]
    except OSError:
        return []


def _parse_stamp(value, *, utc=False):
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if "T" in value else datetime.fromisoformat(value)
        if utc and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _slow_summary(path: Path, pattern, *, key_name: str, utc=False, now=None):
    now = now or (datetime.now(timezone.utc) if utc else datetime.now())
    rows = []
    for line in _tail_lines(path):
        m = pattern.match(line.strip())
        if not m:
            continue
        dt = _parse_stamp(m.group("stamp"), utc=utc)
        if dt is None:
            continue
        try:
            seconds = float(m.group("seconds"))
        except Exception:
            continue
        key = m.group(key_name)
        rows.append({"stamp": m.group("stamp"), "key": key, "seconds": round(seconds, 3)})
    cutoff_hour = now - timedelta(hours=1)
    cutoff_day = now - timedelta(hours=24)
    hour = [r for r in rows if (_parse_stamp(r["stamp"], utc=utc) or now) >= cutoff_hour]
    day = [r for r in rows if (_parse_stamp(r["stamp"], utc=utc) or now) >= cutoff_day]
    counts = Counter(r["key"] for r in day)
    values_by_key = {}
    for r in day:
        values_by_key.setdefault(r["key"], []).append(float(r["seconds"]))

    def p95(values):
        if not values:
            return 0.0
        ordered = sorted(float(v) for v in values)
        pos = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
        return ordered[pos]

    def top_row(key, count):
        vals = values_by_key.get(key) or []
        total = sum(vals)
        return {
            "key": key,
            "count": int(count),
            "avg_seconds": round(total / len(vals), 3) if vals else 0.0,
            "p95_seconds": round(p95(vals), 3),
            "max_seconds": round(max(vals, default=0.0), 3),
            "total_seconds": round(total, 3),
        }

    ordered_keys = sorted(
        counts.items(),
        key=lambda x: (-x[1], -max(values_by_key.get(x[0]) or [0.0]), x[0]),
    )[:8]
    top = [
        {"key": key, "count": int(count), "max_seconds": round(max(values_by_key.get(key) or [0.0]), 3)}
        for key, count in ordered_keys
    ]
    detailed = [top_row(key, count) for key, count in ordered_keys]
    return {
        "available": path.is_file(),
        "last_hour": len(hour),
        "last_24h": len(day),
        "avg_24h_seconds": round(sum(r["seconds"] for r in day) / len(day), 3) if day else 0.0,
        "p95_24h_seconds": round(p95([r["seconds"] for r in day]), 3),
        "max_last_hour_seconds": round(max((r["seconds"] for r in hour), default=0.0), 3),
        "max_24h_seconds": round(max((r["seconds"] for r in day), default=0.0), 3),
        "total_24h_seconds": round(sum(r["seconds"] for r in day), 3),
        "top_24h": top,
        "top_24h_detailed": detailed,
        "recent": list(reversed(rows[-12:])),
    }


def _postgres_status():
    started = time.perf_counter()
    try:
        import db_compat
        if not db_compat.postgres_enabled():
            return {"engine": "sqlite_compat", "ok": False, "latency_ms": None, "reason": "postgresql_not_enabled"}
        import supervision_db
        with supervision_db.connect() as con:
            con.execute("SELECT 1").fetchone()
        return {"engine": "postgresql", "ok": True, "latency_ms": round((time.perf_counter() - started) * 1000.0, 1), "reason": ""}
    except Exception as exc:
        return {"engine": "postgresql", "ok": False, "latency_ms": round((time.perf_counter() - started) * 1000.0, 1), "reason": type(exc).__name__}


def _session_status():
    try:
        from app_db import db_connect
        now = datetime.now()
        rows = []
        with db_connect() as con:
            rows = con.execute("SELECT expires_at,last_seen_at FROM sessions").fetchall()
        valid = recent = 0
        for row in rows:
            try:
                expires = datetime.fromisoformat(str(row["expires_at"] or ""))
                seen = datetime.fromisoformat(str(row["last_seen_at"] or row["expires_at"] or ""))
            except Exception:
                continue
            if expires > now:
                valid += 1
                if seen >= now - timedelta(minutes=10):
                    recent += 1
        return {"available": True, "valid_sessions": valid, "seen_last_10m": recent}
    except Exception as exc:
        return {"available": False, "valid_sessions": None, "seen_last_10m": None, "reason": type(exc).__name__}


def _acceptance_status():
    path = LOGS / "recette_production.json"
    if not path.is_file():
        path = LOGS / "RECETTE_PRODUCTION.json"
    if not path.is_file():
        return {"available": False, "status": "NON_EXECUTEE"}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return {
            "available": True,
            "status": str(data.get("status") or "INCONNU"),
            "generated_at": data.get("generated_at"),
            "version": data.get("version"),
            "failures": int(data.get("failures") or 0),
            "warnings": int(data.get("warnings") or 0),
            "skipped": int(data.get("skipped") or 0),
            "go": bool(data.get("go")),
        }
    except Exception:
        return {"available": False, "status": "ILLISIBLE"}


def _import_status():
    try:
        from service_mode import external_services_enabled
        import supervision_context as state
        folder = state.import_dir_path()
        pending = 0
        if folder.is_dir():
            for item in folder.iterdir():
                if not item.is_file():
                    continue
                name = item.name.lower()
                if name in {"group", "group.har"} or name.endswith(".zip") or name.endswith(".stats.agent.csv"):
                    pending += 1
        if external_services_enabled():
            return {
                "available": True, "mode": "manual-v60", "manual_importer": True,
                "pending_count": pending, "active_count": None, "retry_due_count": None,
                "message": "Import séparé du Web : état d'exécution détaillé disponible dans le processus Importer.",
            }
        return {
            "available": True, "mode": "web-legacy", "manual_importer": False,
            "pending_count": pending, "active_count": None, "retry_due_count": None,
            "message": "Mode monolithique/laboratoire.",
        }
    except Exception as exc:
        return {"available": False, "reason": type(exc).__name__}



def _soak_status():
    path = LOGS / "soak_test_production.json"
    if not path.is_file():
        return {"available": False, "status": "NON_EXECUTE"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        summary = data.get("summary") or {}
        return {
            "available": True,
            "status": str(data.get("status") or "INCONNU"),
            "generated_at": data.get("generated_at"),
            "virtual_users": int(data.get("virtual_users") or 0),
            "duration_seconds": float(data.get("duration_seconds") or 0),
            "requests": int(summary.get("requests") or 0),
            "errors": int(summary.get("errors") or 0),
            "median_s": summary.get("median_s"),
            "p95_s": summary.get("p95_s"),
            "max_s": summary.get("max_s"),
        }
    except Exception as exc:
        return {"available": False, "status": "ILLISIBLE", "reason": type(exc).__name__}


def _soak_analysis_context():
    """Richer soak evidence for Phase 11 without changing the public RC21 soak contract."""
    base = _soak_status()
    if not base.get("available"):
        return base
    path = LOGS / "soak_test_production.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        summary = data.get("summary") or {}
        return {**base, "by_scenario": summary.get("by_scenario") or {}, "thresholds": data.get("thresholds") or {}}
    except Exception:
        return base

def _service_status():
    try:
        version = _version()
        build = str(version.get("version") or "unknown")
        required = ["web", "live", "analytics"]
        path = BASE / "Nelyio_Services.db"
        if not path.is_file():
            return {"build": build, "all_healthy": False, "services": [], "required": required, "available": False}
        uri = path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        try:
            rows = con.execute("SELECT service,pid,build,started_at,last_seen,state,detail_json FROM service_heartbeats ORDER BY service").fetchall()
        finally:
            con.close()
        now = time.time(); out=[]; by_name={}
        for row in rows:
            item=dict(row); age=max(0.0,now-float(item.get("last_seen") or 0)); item["age_seconds"]=round(age,1)
            item["build_match"]=str(item.get("build") or "")==build
            item["healthy"]=bool(item.get("state")=="running" and age<=12.0 and item["build_match"])
            item.pop("detail_json",None); out.append(item); by_name[item["service"]]=item
        return {"build": build, "all_healthy": all(by_name.get(x,{}).get("healthy",False) for x in required), "services": out, "required": required, "available": True}
    except Exception as exc:
        return {"build": "unknown", "all_healthy": False, "services": [], "required": ["web", "live", "analytics"], "available": False, "reason": type(exc).__name__}


def _live_status():
    try:
        import collection_store
        data = collection_store.brief()
        return {
            "available": True,
            "active": bool(data.get("active")),
            "fresh": bool(data.get("fresh")),
            "day": data.get("day"),
            "status": data.get("status"),
            "connection_state": data.get("connection_state"),
            "last_response_text": data.get("last_response_text") or "",
            "pending": int(data.get("pending") or 0),
            "publication_delayed": bool(data.get("publication_delayed")),
        }
    except Exception as exc:
        return {"available": False, "active": False, "fresh": False, "reason": type(exc).__name__}


def _overall(services, postgres, live, performance, thresholds=None):
    thresholds = thresholds or _performance_thresholds()
    reasons = []
    critical = False
    if not services.get("all_healthy"):
        reasons.append("services")
    if not postgres.get("ok"):
        reasons.append("postgresql")
    if live.get("active") and not live.get("fresh"):
        reasons.append("live_stale")
    for key, reason in (("http", "http_slow"), ("analytics", "analytics_slow")):
        data = performance.get(key) or {}
        count = int(data.get("last_hour") or 0)
        max_seconds = float(data.get("max_last_hour_seconds") or 0.0)
        if count >= int(thresholds["warn_events_per_hour"]):
            reasons.append(reason)
        if count >= int(thresholds["critical_events_per_hour"]) or max_seconds >= float(thresholds["critical_seconds"]):
            critical = True
            if reason not in reasons:
                reasons.append(reason)
    if "services" in reasons or "postgresql" in reasons or critical:
        status = "DEGRADE"
    elif reasons:
        status = "A_SURVEILLER"
    else:
        status = "OK"
    return {"status": status, "reasons": reasons}


def _snapshot_uncached():
    version = _version()
    services = _service_status()
    postgres = _postgres_status()
    live = _live_status()
    thresholds = _performance_thresholds()
    performance = {
        "http": _slow_summary(LOGS / "http_slow.log", _HTTP_SLOW, key_name="path"),
        "analytics": _slow_summary(LOGS / "analytics_slow.log", _ANALYTICS_SLOW, key_name="kind", utc=True),
    }
    soak = _soak_status()
    soak_analysis = _soak_analysis_context()
    import performance_analysis
    performance_analysis_payload = performance_analysis.build(performance, postgres, soak_analysis, thresholds)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": version.get("version") or "unknown",
        "edition": version.get("edition") or "unknown",
        "overall": _overall(services, postgres, live, performance, thresholds),
        "services": services,
        "postgresql": postgres,
        "live": live,
        "sessions": _session_status(),
        "imports": _import_status(),
        "acceptance": _acceptance_status(),
        "soak_test": soak,
        "performance": performance,
        "performance_analysis": performance_analysis_payload,
        "performance_thresholds": thresholds,
        "privacy": {
            "business_identifiers": False,
            "query_strings": False,
            "credentials": False,
            "read_only": True,
        },
        "limitations": [
            "Le nombre de sessions authentifiées n'est pas le nombre exact d'utilisateurs humains simultanés.",
            "L'absence d'entrée lente ne prouve pas qu'un navigateur ou le réseau LAN est rapide.",
            "La recette LAN/HTTPS depuis un autre poste reste une preuve externe au serveur.",
        ],
    }


def snapshot():
    """Shared bounded snapshot: one probe burst for all administrator tabs."""
    now = time.monotonic()
    with _CACHE_LOCK:
        if _CACHE["value"] is not None and now - float(_CACHE["at"] or 0) < _CACHE_SECONDS:
            return _CACHE["value"]
        value = _snapshot_uncached()
        _CACHE["at"] = time.monotonic()
        _CACHE["value"] = value
        return value
