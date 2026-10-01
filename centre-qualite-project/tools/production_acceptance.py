#!/usr/bin/env python3
"""Recette de production Nelyio, orientee preuves et sans mutation metier.

Le script ne modifie ni les KPI, ni les groupes, ni les appels. Il effectue des
lectures de sante, des GET authentifies et un benchmark multi-session. La
connexion cree toutefois des sessions/audits de connexion normaux dans Nelyio.

Exemple Windows (serveur):
  python tools/production_acceptance.py --public-url https://stock-manager.nelyio.local:9050

Identifiants via environnement, jamais ecrits dans le rapport:
  NELYIO_BENCH_USER / NELYIO_BENCH_PASSWORD
"""
from __future__ import annotations

import argparse
import concurrent.futures
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERNAL = "http://127.0.0.1:9051"
DEFAULT_PUBLIC = "https://stock-manager.nelyio.local:9050"
REQUIRED_PERMISSIONS = ("collection", "quality", "classification", "config")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _level_rank(status: str) -> int:
    return {"PASS": 0, "SKIP": 1, "WARN": 2, "FAIL": 3}.get(status, 3)


class Report:
    def __init__(self, *, version: str, internal_url: str, public_url: str):
        self.data = {
            "generated_at": now_iso(),
            "version": version,
            "internal_url": internal_url,
            "public_url": public_url,
            "read_only_business": True,
            "note": "Les connexions de recette creent des sessions/audits normaux; aucune ecriture metier n'est effectuee.",
            "checks": [],
            "benchmark": {},
        }

    def add(self, name: str, status: str, detail: str, *, category: str = "general", evidence=None):
        status = status if status in {"PASS", "WARN", "FAIL", "SKIP"} else "FAIL"
        row = {"name": name, "status": status, "detail": str(detail), "category": category}
        if evidence is not None:
            row["evidence"] = evidence
        self.data["checks"].append(row)
        return row

    def finish(self):
        statuses = [x["status"] for x in self.data["checks"]]
        self.data["failures"] = sum(s == "FAIL" for s in statuses)
        self.data["warnings"] = sum(s == "WARN" for s in statuses)
        self.data["skipped"] = sum(s == "SKIP" for s in statuses)
        self.data["go"] = self.data["failures"] == 0 and self.data["skipped"] == 0
        self.data["status"] = "GO" if self.data["go"] else ("BLOQUE" if self.data["failures"] else "INCOMPLET")
        return self.data


def load_version(root: Path) -> str:
    try:
        return str(json.loads((root / "VERSION.json").read_text(encoding="utf-8-sig")).get("version") or "unknown")
    except Exception:
        return "unknown"


def json_request(opener, url: str, *, timeout=15.0, method="GET", payload=None):
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            data = json.loads(raw.decode("utf-8")) if raw else {}
            return {"ok": 200 <= response.status < 300, "status": int(response.status), "seconds": time.perf_counter() - started, "data": data, "error": ""}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}
        return {"ok": False, "status": int(exc.code), "seconds": time.perf_counter() - started, "data": data, "error": str(data.get("error") or exc.reason)}
    except Exception as exc:
        return {"ok": False, "status": 0, "seconds": time.perf_counter() - started, "data": {}, "error": f"{type(exc).__name__}: {exc}"}


def build_opener(*, insecure=False):
    jar = http.cookiejar.CookieJar()
    context = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=context),
    )


def login(base: str, username: str, password: str, *, insecure=False, timeout=15.0):
    opener = build_opener(insecure=insecure)
    result = json_request(opener, base.rstrip("/") + "/api/login", timeout=timeout, method="POST", payload={"username": username, "password": password})
    if not result["ok"]:
        raise RuntimeError(result["error"] or f"HTTP {result['status']}")
    return opener, result["data"]


def _permission(user: dict, name: str) -> int:
    if str(user.get("role") or "") == "admin":
        return 2
    try:
        return int((user.get("permissions") or {}).get(name, 0) or 0)
    except Exception:
        return 0


def _health_summary(data: dict) -> dict:
    return {
        "ok": data.get("ok"),
        "build": data.get("build"),
        "database": data.get("database"),
        "architecture": data.get("architecture"),
        "services_ok": data.get("services_ok"),
        "services": data.get("services"),
    }


def check_preflight(report: Report):
    try:
        import preflight
        result = preflight.check(ROOT)
    except Exception as exc:
        report.add("Preflight statique", "FAIL", f"{type(exc).__name__}: {exc}", category="static")
        return
    hard = [x for x in result.get("checks", []) if not x.get("ok") and x.get("level") != "warning"]
    warnings = [x for x in result.get("checks", []) if not x.get("ok") and x.get("level") == "warning"]
    if hard:
        report.add("Preflight statique", "FAIL", f"{len(hard)} echec(s) bloquant(s)", category="static", evidence=[{"check": x.get("check"), "detail": x.get("detail")} for x in hard])
    elif warnings:
        report.add("Preflight statique", "WARN", f"OK avec {len(warnings)} avertissement(s)", category="static", evidence=[{"check": x.get("check"), "detail": x.get("detail")} for x in warnings])
    else:
        report.add("Preflight statique", "PASS", "Integrite, syntaxe et SQLite OK.", category="static")


def check_postgres_preflight(report: Report, *, timeout=90.0):
    output = ROOT / "logs" / "recette_postgres_runtime.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROOT / "postgres_runtime_preflight.py"), "--json", str(output)]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        data = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
        failures = [x for x in data.get("checks", []) if not x.get("ok") and x.get("level") != "warning"]
        warnings = [x for x in data.get("checks", []) if not x.get("ok") and x.get("level") == "warning"]
        if proc.returncode != 0 or failures:
            report.add("PostgreSQL runtime", "FAIL", f"{len(failures)} echec(s) bloquant(s)", category="database", evidence=[{"check": x.get("check"), "detail": x.get("detail")} for x in failures[:12]])
        elif warnings:
            report.add("PostgreSQL runtime", "WARN", f"Connexion/schemas OK avec {len(warnings)} avertissement(s)", category="database", evidence=[{"check": x.get("check"), "detail": x.get("detail")} for x in warnings[:12]])
        else:
            report.add("PostgreSQL runtime", "PASS", "Connexion, schema, fonctions et smoke checks OK.", category="database")
    except subprocess.TimeoutExpired:
        report.add("PostgreSQL runtime", "FAIL", f"Timeout apres {timeout:.0f}s", category="database")
    except Exception as exc:
        report.add("PostgreSQL runtime", "FAIL", f"{type(exc).__name__}: {exc}", category="database")


def check_internal_health(report: Report, base: str, version: str, *, timeout=10.0):
    result = json_request(build_opener(), base.rstrip("/") + "/healthz", timeout=timeout)
    if not result["ok"]:
        report.add("Backend interne /healthz", "FAIL", result["error"] or f"HTTP {result['status']}", category="runtime")
        return None
    data = result["data"]
    failures = []
    if not data.get("ok"):
        failures.append("ok=false")
    if version != "unknown" and str(data.get("build") or "") != version:
        failures.append(f"build={data.get('build')!r} attendu={version!r}")
    if data.get("database") != "postgresql":
        failures.append(f"database={data.get('database')!r}")
    if data.get("architecture") != "services":
        failures.append(f"architecture={data.get('architecture')!r}")
    if data.get("services_ok") is not True:
        failures.append("services_ok!=true")
    if failures:
        report.add("Backend interne /healthz", "FAIL", "; ".join(failures), category="runtime", evidence=_health_summary(data))
    else:
        report.add("Backend interne /healthz", "PASS", f"Build {version}, PostgreSQL, services sains ({result['seconds']:.3f}s).", category="runtime", evidence=_health_summary(data))
    return data


def check_public_https(report: Report, url: str, version: str, *, timeout=10.0, allow_untrusted_local=False):
    if not url:
        report.add("HTTPS public", "SKIP", "URL publique non fournie.", category="https")
        return
    target = url.rstrip("/") + "/healthz"
    strict = json_request(build_opener(insecure=False), target, timeout=timeout)
    if strict["ok"]:
        data = strict["data"]
        if version != "unknown" and str(data.get("build") or "") not in {"", version}:
            report.add("HTTPS public", "FAIL", f"Build HTTPS {data.get('build')!r} != {version!r}", category="https")
        else:
            report.add("HTTPS public", "PASS", f"HTTPS et confiance TLS valides ({strict['seconds']:.3f}s).", category="https", evidence={"url": url, "status": strict["status"]})
        return
    parsed = urllib.parse.urlparse(url)
    is_local = (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}
    if allow_untrusted_local and is_local:
        retry = json_request(build_opener(insecure=True), target, timeout=timeout)
        if retry["ok"]:
            report.add("HTTPS public", "WARN", "HTTPS repond, mais la confiance du certificat n'est pas validee dans ce processus Python local.", category="https", evidence={"url": url, "strict_error": strict["error"]})
            return
    report.add("HTTPS public", "FAIL", strict["error"] or f"HTTP {strict['status']}", category="https", evidence={"url": url})


def check_authenticated_runtime(report: Report, base: str, username: str, password: str, *, insecure=False, timeout=30.0, day=""):
    if not username or not password:
        report.add("Connexion recette", "SKIP", "NELYIO_BENCH_USER / NELYIO_BENCH_PASSWORD non definis.", category="auth")
        return None, None
    try:
        opener, auth = login(base, username, password, insecure=insecure, timeout=timeout)
    except Exception as exc:
        report.add("Connexion recette", "FAIL", str(exc), category="auth")
        return None, None
    user = auth.get("user") or {}
    report.add("Connexion recette", "PASS", f"Compte {user.get('username') or username} authentifie; mot de passe non journalise dans le rapport.", category="auth")
    missing = [name for name in REQUIRED_PERMISSIONS if _permission(user, name) < 1]
    if missing:
        report.add("Droits compte recette", "FAIL", "Droits de lecture manquants: " + ", ".join(missing), category="auth")
    else:
        report.add("Droits compte recette", "PASS", "Live, Qualite, Groupes et Configuration accessibles.", category="auth")

    endpoints = [
        ("Etat services", "/api/services/status", "config"),
        ("Groupes analytiques", "/api/groups/status", "classification"),
        ("Centre Qualite Live", "/api/live/supervision", "collection"),
        ("Campagnes Live", "/api/live/campaigns", "collection"),
        ("Pilotage Qualite", "/api/quality/pilotage" + (("?day=" + urllib.parse.quote(day)) if day else ""), "quality"),
    ]
    payloads = {}
    for label, path, permission in endpoints:
        if _permission(user, permission) < 1:
            report.add(label, "SKIP", f"Permission {permission} absente.", category="api")
            continue
        result = json_request(opener, base.rstrip("/") + path, timeout=timeout)
        if not result["ok"]:
            report.add(label, "FAIL", result["error"] or f"HTTP {result['status']}", category="api")
            continue
        payloads[label] = result["data"]
        report.add(label, "PASS", f"HTTP {result['status']} en {result['seconds']:.3f}s", category="api")

    services = payloads.get("Etat services") or {}
    if services:
        if services.get("all_healthy") is True:
            report.add("Heartbeats services", "PASS", "Web, Live et Analytics sains et du meme build.", category="runtime")
        else:
            bad = [x for x in services.get("services", []) if x.get("service") in set(services.get("required") or []) and not x.get("healthy")]
            report.add("Heartbeats services", "FAIL", "Service(s) requis non sain(s).", category="runtime", evidence=[{"service": x.get("service"), "state": x.get("state"), "age_seconds": x.get("age_seconds"), "build_match": x.get("build_match")} for x in bad])

    groups = payloads.get("Groupes analytiques") or {}
    if groups:
        summary = groups.get("group_summary") or {}
        if not groups.get("assignment_source_available"):
            report.add("Affectations groupes", "WARN", "Source Agents/Queues non disponible; les filtres groupe ne peuvent pas etre certifies.", category="data", evidence=summary)
        elif int(summary.get("saved") or 0) <= 0:
            report.add("Affectations groupes", "WARN", "Aucun groupe analytique sauvegarde.", category="data", evidence=summary)
        else:
            unclassified = int(summary.get("unclassified_agent_count") or 0)
            status = "WARN" if unclassified else "PASS"
            report.add("Affectations groupes", status, f"{summary.get('saved',0)} groupe(s), {summary.get('scoped_agents',0)} agent(s) classes, {unclassified} non classe(s).", category="data", evidence=summary)

    live = payloads.get("Centre Qualite Live") or {}
    if live:
        health = live.get("health") or {}
        if health.get("worker_healthy") is False:
            report.add("Fraicheur Hermes", "FAIL", "Worker Live declare KO.", category="live", evidence={k: health.get(k) for k in ("connection_state", "last_response_age", "fresh", "worker_healthy")})
        elif health.get("fresh") is True:
            report.add("Fraicheur Hermes", "PASS", f"Donnees Live fraiches; age={health.get('last_response_age')}s.", category="live", evidence={k: health.get(k) for k in ("connection_state", "last_response_age", "fresh", "worker_healthy")})
        else:
            report.add("Fraicheur Hermes", "WARN", "Service Live accessible mais donnees Hermes non fraiches au moment de la recette.", category="live", evidence={k: health.get(k) for k in ("connection_state", "last_response_age", "fresh", "worker_healthy")})

    campaigns = payloads.get("Campagnes Live") or {}
    if campaigns:
        rows = campaigns.get("campaigns") or []
        windows = campaigns.get("windows") or {}
        report.add("Contrat campagnes", "PASS", f"{len(rows)} campagne(s) exposee(s); fenetres separees Live / 15 min / aujourd'hui / reference.", category="live", evidence={"count": len(rows), "windows": {k: (v or {}).get("quality") for k, v in windows.items()}})

    quality = payloads.get("Pilotage Qualite") or {}
    if quality:
        current = quality.get("current")
        reliability = quality.get("reliability") or {}
        if not current:
            report.add("Couverture Qualite", "WARN", "Aucune journee Stats.INBOUND exploitable sur le perimetre choisi.", category="data", evidence={"day": quality.get("day"), "status": reliability.get("status")})
        else:
            coherent = current.get("coherence_ok") is not False
            status = "PASS" if coherent else "FAIL"
            report.add("Couverture Qualite", status, f"Jour {quality.get('day')}: recus={current.get('received')} traites={current.get('treated')} abandons={current.get('abandoned')} QoS={current.get('qos')}", category="data", evidence={"reliability": reliability.get("status"), "baseline_status": quality.get("baseline_status"), "coherence_ok": current.get("coherence_ok")})
    return opener, user


def benchmark(report: Report, base: str, username: str, password: str, *, users=5, rounds=3, timeout=60.0, insecure=False, warn_seconds=2.0):
    if not username or not password:
        report.add("Benchmark 5 utilisateurs", "SKIP", "Identifiants recette absents.", category="performance")
        return
    users = max(1, min(20, int(users)))
    rounds = max(1, min(20, int(rounds)))
    endpoints = [
        ("live", "/api/live/supervision"),
        ("campaigns", "/api/live/campaigns"),
        ("analytics", "/api/quality/pilotage"),
        ("groups", "/api/groups/status"),
        ("quality", "/api/quality/overview"),
    ]
    clients = []
    try:
        for _ in range(users):
            clients.append(login(base, username, password, insecure=insecure, timeout=timeout)[0])
    except Exception as exc:
        report.add("Benchmark 5 utilisateurs", "FAIL", "Connexion d'un utilisateur virtuel impossible: " + str(exc), category="performance")
        return

    records = []
    for i, (_label, path) in enumerate(endpoints[:min(users, len(endpoints))]):
        json_request(clients[i], base.rstrip("/") + path, timeout=timeout)
    for rnd in range(rounds):
        jobs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=users) as executor:
            for i in range(users):
                label, path = endpoints[i % len(endpoints)]
                jobs.append((label, executor.submit(json_request, clients[i], base.rstrip("/") + path, timeout=timeout)))
            for label, future in jobs:
                row = future.result()
                records.append({"round": rnd + 1, "scenario": label, "status": row["status"], "seconds": round(row["seconds"], 4), "error": row["error"]})
    errors = [x for x in records if x["status"] != 200 or x["error"]]
    values = [x["seconds"] for x in records if x["status"] == 200 and not x["error"]]
    summary = {"virtual_users": users, "rounds": rounds, "requests": len(records), "errors": len(errors)}
    if values:
        ordered = sorted(values)
        pos = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
        summary.update({"median_s": round(statistics.median(values), 4), "p95_s": round(ordered[pos], 4), "max_s": round(max(values), 4)})
    report.data["benchmark"] = {"summary": summary, "records": records}
    if errors:
        report.add("Benchmark 5 utilisateurs", "FAIL", f"{len(errors)} requete(s) en erreur sur {len(records)}.", category="performance", evidence=summary)
    elif summary.get("p95_s", 0) > warn_seconds:
        report.add("Benchmark 5 utilisateurs", "WARN", f"0 erreur; P95={summary.get('p95_s')}s depasse le seuil de surveillance configurable {warn_seconds:.2f}s.", category="performance", evidence=summary)
    else:
        report.add("Benchmark 5 utilisateurs", "PASS", f"0 erreur; mediane={summary.get('median_s')}s, P95={summary.get('p95_s')}s.", category="performance", evidence=summary)


def check_new_slow_log(report: Report, before_size: int):
    path = ROOT / "logs" / "http_slow.log"
    if not path.exists():
        report.add("Requetes lentes pendant recette", "PASS", "Aucune entree http_slow.log creee.", category="performance")
        return
    try:
        with path.open("rb") as handle:
            handle.seek(min(before_size, path.stat().st_size))
            raw = handle.read().decode("utf-8", "replace")
        lines = [x.strip() for x in raw.splitlines() if x.strip()]
        if lines:
            report.add("Requetes lentes pendant recette", "WARN", f"{len(lines)} requete(s) >= seuil serveur pendant la recette.", category="performance", evidence=lines[-20:])
        else:
            report.add("Requetes lentes pendant recette", "PASS", "Aucune nouvelle requete lente journalisee.", category="performance")
    except Exception as exc:
        report.add("Requetes lentes pendant recette", "WARN", f"Lecture impossible: {type(exc).__name__}: {exc}", category="performance")


def write_markdown(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Recette production Nelyio",
        "",
        f"- Version : **{data.get('version')}**",
        f"- Genere : `{data.get('generated_at')}`",
        f"- Statut : **{data.get('status')}**",
        f"- Echecs : {data.get('failures')} · Avertissements : {data.get('warnings')} · Etapes ignorees : {data.get('skipped')}",
        "",
        "> Les connexions de recette creent des sessions/audits normaux. Aucune modification metier n'est effectuee.",
        "",
        "## Controles",
        "",
        "| Etat | Controle | Detail |",
        "|---|---|---|",
    ]
    for row in data.get("checks", []):
        detail = str(row.get("detail") or "").replace("|", "\\|").replace("\n", " ")
        name = str(row.get("name") or "").replace("|", "\\|")
        lines.append(f"| {row.get('status')} | {name} | {detail} |")
    bench = data.get("benchmark", {}).get("summary") or {}
    if bench:
        lines += ["", "## Benchmark", "", "```json", json.dumps(bench, ensure_ascii=False, indent=2), "```"]
    lines += [
        "",
        "## Condition de bascule",
        "",
        "- `GO` signifie que tous les controles automatisables ont ete executes sans FAIL ni SKIP.",
        "- La validation depuis **un autre poste du LAN** reste une preuve externe a effectuer manuellement si le script est lance sur le serveur lui-meme.",
        "- Un WARN ne transforme jamais une donnee absente en resultat positif; il exige une verification explicite.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--internal-url", default=os.environ.get("NELYIO_INTERNAL_URL", DEFAULT_INTERNAL))
    parser.add_argument("--public-url", default=os.environ.get("NELYIO_PUBLIC_URL", DEFAULT_PUBLIC))
    parser.add_argument("--day", default=os.environ.get("NELYIO_ACCEPT_DAY", ""))
    parser.add_argument("--users", type=int, default=int(os.environ.get("NELYIO_ACCEPT_USERS", "5")))
    parser.add_argument("--rounds", type=int, default=int(os.environ.get("NELYIO_ACCEPT_ROUNDS", "3")))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("NELYIO_ACCEPT_TIMEOUT", "60")))
    parser.add_argument("--warn-seconds", type=float, default=float(os.environ.get("NELYIO_ACCEPT_WARN_SECONDS", "2")))
    parser.add_argument("--allow-untrusted-local", action="store_true")
    parser.add_argument("--skip-postgres", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--json", type=Path, default=ROOT / "logs" / "recette_production.json")
    parser.add_argument("--markdown", type=Path, default=ROOT / "logs" / "RECETTE_PRODUCTION.md")
    args = parser.parse_args()

    version = load_version(ROOT)
    report = Report(version=version, internal_url=args.internal_url.rstrip("/"), public_url=args.public_url.rstrip("/"))
    slow = ROOT / "logs" / "http_slow.log"
    slow_before = slow.stat().st_size if slow.exists() else 0

    check_preflight(report)
    if args.skip_postgres:
        report.add("PostgreSQL runtime", "SKIP", "Controle PostgreSQL ignore par option.", category="database")
    else:
        check_postgres_preflight(report, timeout=max(30.0, args.timeout))
    check_internal_health(report, args.internal_url, version, timeout=min(args.timeout, 15.0))
    check_public_https(report, args.public_url, version, timeout=min(args.timeout, 15.0), allow_untrusted_local=args.allow_untrusted_local)

    username = os.environ.get("NELYIO_BENCH_USER", "")
    password = os.environ.get("NELYIO_BENCH_PASSWORD", "")
    check_authenticated_runtime(report, args.internal_url, username, password, timeout=args.timeout, day=args.day)
    if args.skip_benchmark:
        report.add("Benchmark 5 utilisateurs", "SKIP", "Benchmark ignore par option.", category="performance")
    else:
        benchmark(report, args.internal_url, username, password, users=args.users, rounds=args.rounds, timeout=args.timeout, warn_seconds=args.warn_seconds)
    check_new_slow_log(report, slow_before)

    data = report.finish()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(data, args.markdown)

    for row in data["checks"]:
        print(f"{row['status']:4} - {row['name']} : {row['detail']}")
    print()
    print(f"RESULTAT : {data['status']}")
    print(f"JSON     : {args.json}")
    print(f"Rapport  : {args.markdown}")
    return 0 if data["status"] == "GO" else (2 if data["status"] == "INCOMPLET" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
