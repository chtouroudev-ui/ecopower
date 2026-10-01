#!/usr/bin/env python3
"""Read-only sustained-load test for Nelyio production.

Creates independent authenticated sessions, repeatedly exercises bounded aggregate
GET endpoints and records latency/error evidence. It never modifies business data;
login creates only the normal Nelyio session/audit rows.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import statistics
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINTS = (
    ("live", "/api/live/supervision"),
    ("campaigns", "/api/live/campaigns"),
    ("analytics", "/api/quality/pilotage"),
    ("groups", "/api/groups/status"),
    ("quality", "/api/quality/overview"),
)


def _opener(insecure=False):
    jar = http.cookiejar.CookieJar()
    context = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=context),
    )


def _json_request(opener, url, *, timeout=60.0, method="GET", payload=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return {"status": int(response.status), "seconds": time.perf_counter() - started, "error": "", "data": data}
    except urllib.error.HTTPError as exc:
        try:
            data = json.loads(exc.read().decode("utf-8"))
        except Exception:
            data = {}
        return {"status": int(exc.code), "seconds": time.perf_counter() - started, "error": str(data.get("error") or exc.reason), "data": data}
    except Exception as exc:
        return {"status": 0, "seconds": time.perf_counter() - started, "error": f"{type(exc).__name__}: {exc}", "data": {}}


def _login(base, username, password, *, insecure=False, timeout=60.0):
    opener = _opener(insecure=insecure)
    result = _json_request(opener, base.rstrip("/") + "/api/login", timeout=timeout, method="POST", payload={"username": username, "password": password})
    if result["status"] != 200 or result["error"]:
        raise RuntimeError(result["error"] or f"HTTP {result['status']}")
    return opener


def _percentile(values, q):
    if not values:
        return None
    ordered = sorted(float(v) for v in values)
    pos = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
    return ordered[pos]


def summarize(records):
    ok = [r for r in records if int(r.get("status") or 0) == 200 and not r.get("error")]
    errors = [r for r in records if r not in ok]
    values = [float(r["seconds"]) for r in ok]
    by_scenario = {}
    for label, _path in DEFAULT_ENDPOINTS:
        vals = [float(r["seconds"]) for r in ok if r.get("scenario") == label]
        if vals:
            by_scenario[label] = {
                "count": len(vals),
                "median_s": round(statistics.median(vals), 4),
                "p95_s": round(_percentile(vals, 0.95), 4),
                "max_s": round(max(vals), 4),
            }
    return {
        "requests": len(records),
        "success": len(ok),
        "errors": len(errors),
        "median_s": round(statistics.median(values), 4) if values else None,
        "p95_s": round(_percentile(values, 0.95), 4) if values else None,
        "max_s": round(max(values), 4) if values else None,
        "by_scenario": by_scenario,
    }


def _health(base, *, insecure=False, timeout=15.0):
    result = _json_request(_opener(insecure=insecure), base.rstrip("/") + "/healthz", timeout=timeout)
    data = result.get("data") or {}
    ok = result.get("status") == 200 and not result.get("error") and data.get("ok") is True
    if data.get("architecture") == "services":
        ok = ok and data.get("services_ok") is True
    return {"ok": bool(ok), "status": result.get("status"), "seconds": round(float(result.get("seconds") or 0), 4), "build": data.get("build"), "database": data.get("database"), "architecture": data.get("architecture"), "services_ok": data.get("services_ok"), "error": result.get("error") or ""}


def run(base, username, password, *, users=5, duration=300.0, interval=2.0, timeout=60.0, insecure=False, warn_seconds=2.0, critical_seconds=10.0):
    users = max(1, min(20, int(users)))
    duration = max(5.0, min(7200.0, float(duration)))
    interval = max(0.2, min(60.0, float(interval)))
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    health_before = _health(base, insecure=insecure, timeout=min(timeout, 15.0))
    clients = [_login(base, username, password, insecure=insecure, timeout=timeout) for _ in range(users)]
    for i in range(users):
        _json_request(clients[i], base.rstrip("/") + DEFAULT_ENDPOINTS[i % len(DEFAULT_ENDPOINTS)][1], timeout=timeout)
    deadline = time.monotonic() + duration
    cycle = 0
    records = []
    while time.monotonic() < deadline:
        cycle += 1
        cycle_started = time.monotonic()
        jobs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=users) as executor:
            for i in range(users):
                label, path = DEFAULT_ENDPOINTS[(i + cycle - 1) % len(DEFAULT_ENDPOINTS)]
                jobs.append((i + 1, label, executor.submit(_json_request, clients[i], base.rstrip("/") + path, timeout=timeout)))
            for virtual_user, label, future in jobs:
                row = future.result()
                records.append({
                    "cycle": cycle,
                    "virtual_user": virtual_user,
                    "scenario": label,
                    "status": int(row.get("status") or 0),
                    "seconds": round(float(row.get("seconds") or 0), 4),
                    "error": row.get("error") or "",
                })
        remaining = interval - (time.monotonic() - cycle_started)
        if remaining > 0 and time.monotonic() + remaining < deadline:
            time.sleep(remaining)
    health_after = _health(base, insecure=insecure, timeout=min(timeout, 15.0))
    summary = summarize(records)
    if not health_before["ok"] or not health_after["ok"] or summary["errors"]:
        status = "FAIL"
    elif (summary.get("p95_s") or 0) > warn_seconds or (summary.get("max_s") or 0) > critical_seconds:
        status = "WARN"
    else:
        status = "PASS"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "started_at": started_at,
        "base_url": base.rstrip("/"),
        "read_only_business": True,
        "virtual_users": users,
        "duration_seconds": round(duration, 1),
        "interval_seconds": round(interval, 3),
        "thresholds": {"warn_p95_seconds": float(warn_seconds), "critical_max_seconds": float(critical_seconds)},
        "health_before": health_before,
        "health_after": health_after,
        "summary": summary,
        "status": status,
        "records": records[-5000:],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=os.environ.get("NELYIO_INTERNAL_URL", "http://127.0.0.1:9051"))
    ap.add_argument("--users", type=int, default=int(os.environ.get("NELYIO_SOAK_USERS", "5")))
    ap.add_argument("--duration", type=float, default=float(os.environ.get("NELYIO_SOAK_DURATION", "300")))
    ap.add_argument("--interval", type=float, default=float(os.environ.get("NELYIO_SOAK_INTERVAL", "2")))
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("NELYIO_SOAK_TIMEOUT", "60")))
    ap.add_argument("--warn-seconds", type=float, default=float(os.environ.get("NELYIO_SOAK_WARN_SECONDS", "2")))
    ap.add_argument("--critical-seconds", type=float, default=float(os.environ.get("NELYIO_SOAK_CRITICAL_SECONDS", "10")))
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--output", type=Path, default=ROOT / "logs" / "soak_test_production.json")
    args = ap.parse_args()
    username = os.environ.get("NELYIO_BENCH_USER", "")
    password = os.environ.get("NELYIO_BENCH_PASSWORD", "")
    if not username or not password:
        raise SystemExit("Definir NELYIO_BENCH_USER et NELYIO_BENCH_PASSWORD dans l'environnement.")
    report = run(args.base_url, username, password, users=args.users, duration=args.duration, interval=args.interval, timeout=args.timeout, insecure=args.insecure, warn_seconds=args.warn_seconds, critical_seconds=args.critical_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}, ensure_ascii=False, indent=2))
    print("Rapport :", args.output)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
