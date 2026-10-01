"""Low-overhead request/query performance tracing for Nelyio.

The tracer never records SQL parameters, ANI values, filter values or response
content.  It is intentionally process-local and safe to leave installed in
production.  Records are emitted only for slow requests (default >=500 ms) or
when NELYIO_PERF_TRACE=1.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_CTX = contextvars.ContextVar("nelyio_perf_trace", default=None)
_LOG_LOCK = threading.Lock()


def _enabled_all() -> bool:
    return os.environ.get("NELYIO_PERF_TRACE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _slow_ms() -> float:
    try:
        return max(50.0, float(os.environ.get("NELYIO_PERF_SLOW_MS", "500")))
    except (TypeError, ValueError):
        return 500.0


def begin(kind: str, *, service: str = "", endpoint: str = ""):
    state = {
        "kind": str(kind or "request")[:120],
        "service": str(service or "")[:40],
        "endpoint": str(endpoint or "")[:180],
        "started": time.perf_counter(),
        "db_acquire_ms": 0.0,
        "db_acquire_count": 0,
        "sql_ms": 0.0,
        "sql_count": 0,
        "sql_max_ms": 0.0,
        "sql_max_sig": "",
        "json_ms": 0.0,
        "auth_ms": 0.0,
        "worker_ms": 0.0,
        "compute_ms": 0.0,
        "response_bytes": 0,
        "cache_hit": None,
    }
    return _CTX.set(state)


def current():
    return _CTX.get()


def reset(token):
    try:
        _CTX.reset(token)
    except Exception:
        pass


def add_db_acquire(seconds: float):
    s = _CTX.get()
    if s is None:
        return
    s["db_acquire_ms"] += max(0.0, float(seconds)) * 1000.0
    s["db_acquire_count"] += 1


def _sql_signature(sql: str) -> str:
    # Hash only normalized SQL shape; never persist parameter values.
    normalized = " ".join(str(sql or "").split())[:4000]
    return hashlib.sha256(normalized.encode("utf-8", "replace")).hexdigest()[:12]


def add_sql(seconds: float, sql: str = ""):
    s = _CTX.get()
    if s is None:
        return
    ms = max(0.0, float(seconds)) * 1000.0
    s["sql_ms"] += ms
    s["sql_count"] += 1
    if ms >= s["sql_max_ms"]:
        s["sql_max_ms"] = ms
        s["sql_max_sig"] = _sql_signature(sql)


def add_json(seconds: float):
    s = _CTX.get()
    if s is not None:
        s["json_ms"] += max(0.0, float(seconds)) * 1000.0


def add_auth(seconds: float):
    s = _CTX.get()
    if s is not None:
        s["auth_ms"] += max(0.0, float(seconds)) * 1000.0


def add_worker(seconds: float):
    s = _CTX.get()
    if s is not None:
        s["worker_ms"] += max(0.0, float(seconds)) * 1000.0


def add_compute(seconds: float):
    s = _CTX.get()
    if s is not None:
        s["compute_ms"] += max(0.0, float(seconds)) * 1000.0


def add_response_bytes(value: int):
    s = _CTX.get()
    if s is not None:
        try:
            s["response_bytes"] += max(0, int(value))
        except (TypeError, ValueError):
            pass


def set_cache_hit(value):
    s = _CTX.get()
    if s is not None:
        s["cache_hit"] = bool(value)


def snapshot(extra=None):
    s = _CTX.get()
    if s is None:
        return None
    total_ms = max(0.0, time.perf_counter() - s["started"]) * 1000.0
    known = (s["db_acquire_ms"] + s["sql_ms"] + s["json_ms"] +
             s["auth_ms"] + s["worker_ms"] + s["compute_ms"])
    out = {
        "kind": s["kind"],
        "service": s["service"],
        "endpoint": s["endpoint"],
        "total_ms": round(total_ms, 3),
        "db_acquire_ms": round(s["db_acquire_ms"], 3),
        "db_acquire_count": int(s["db_acquire_count"]),
        "sql_ms": round(s["sql_ms"], 3),
        "sql_count": int(s["sql_count"]),
        "sql_max_ms": round(s["sql_max_ms"], 3),
        "sql_max_sig": s["sql_max_sig"],
        "json_ms": round(s["json_ms"], 3),
        "auth_ms": round(s["auth_ms"], 3),
        "worker_ms": round(s["worker_ms"], 3),
        "compute_ms": round(s["compute_ms"], 3),
        "response_bytes": int(s["response_bytes"]),
        "python_other_ms": round(max(0.0, total_ms - known), 3),
        "cache_hit": s["cache_hit"],
    }
    if extra:
        for k, v in dict(extra).items():
            if k not in out and isinstance(v, (str, int, float, bool, type(None))):
                out[str(k)[:60]] = v if not isinstance(v, str) else v[:180]
    return out


def finish(*, extra=None, base_dir=None):
    out = snapshot(extra)
    if out is None:
        return None
    if not _enabled_all() and out["total_ms"] < _slow_ms():
        return out
    root = Path(base_dir or Path(__file__).resolve().parent)
    folder = root / "logs"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **out,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with _LOG_LOCK:
            with (folder / "performance.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError:
        pass
    return out
