"""Read-only interpretation of Nelyio production performance evidence.

The analyzer only interprets already-collected technical evidence. It never changes
performance thresholds, business rules, databases, indexes or service settings.
Findings are intentionally phrased as observations / next checks, never as proven
causes unless the underlying evidence actually proves one.
"""
from __future__ import annotations

from datetime import datetime, timezone


_HTTP_TO_ANALYTICS = {
    "/api/quality/pilotage": "quality_pilotage",
    "/api/quality/overview": "quality_overview",
    "/api/quality/distributions": "quality_distributions",
    "/api/quality/agent-activity": "quality_agents",
    "/api/quality/action-compare": "quality_action_compare",
    "/api/quality/suspicious-calls": "suspicious_calls",
    "/api/live/campaigns": "live_campaigns_history",
}

_SOAK_TO_HTTP = {
    "live": "/api/live/supervision",
    "campaigns": "/api/live/campaigns",
    "analytics": "/api/quality/pilotage",
    "groups": "/api/groups/status",
    "quality": "/api/quality/overview",
}


def _analytics_kind_for_path(path: str) -> str:
    path = str(path or "")
    if path in _HTTP_TO_ANALYTICS:
        return _HTTP_TO_ANALYTICS[path]
    if path.startswith("/api/live/campaigns/"):
        return "live_campaign_drilldown_history"
    return ""


def _attention(max_seconds: float, thresholds: dict) -> str:
    critical = float((thresholds or {}).get("critical_seconds") or 10.0)
    if float(max_seconds or 0.0) >= critical:
        return "ELEVEE"
    return "A_VERIFIER"


def _row(source: str, item: dict, thresholds: dict) -> dict:
    return {
        "source": source,
        "key": str(item.get("key") or ""),
        "count_24h": int(item.get("count") or 0),
        "avg_seconds": item.get("avg_seconds"),
        "p95_seconds": item.get("p95_seconds"),
        "max_seconds": float(item.get("max_seconds") or 0.0),
        "total_seconds": item.get("total_seconds"),
        "attention": _attention(float(item.get("max_seconds") or 0.0), thresholds),
    }


def build(performance: dict, postgres: dict, soak: dict, thresholds: dict) -> dict:
    """Build explainable findings from bounded, sanitized performance summaries."""
    performance = performance or {}
    thresholds = thresholds or {}
    http = performance.get("http") or {}
    analytics = performance.get("analytics") or {}
    http_rows = [_row("web", x, thresholds) for x in (http.get("top_24h_detailed") or http.get("top_24h") or [])]
    analytics_rows = [_row("analytics", x, thresholds) for x in (analytics.get("top_24h_detailed") or analytics.get("top_24h") or [])]
    analytics_by_kind = {r["key"]: r for r in analytics_rows if r["key"]}
    http_by_path = {r["key"]: r for r in http_rows if r["key"]}

    findings = []
    seen_kinds = set()
    for web in http_rows:
        kind = _analytics_kind_for_path(web["key"])
        if kind and kind in analytics_by_kind:
            worker = analytics_by_kind[kind]
            seen_kinds.add(kind)
            findings.append({
                "code": "WEB_ANALYTICS_CORRELATION",
                "attention": "ELEVEE" if "ELEVEE" in {web["attention"], worker["attention"]} else "A_VERIFIER",
                "title": "Correspondance Web ↔ Analytics observée",
                "scope": web["key"],
                "evidence": [
                    f"Route Web : {web['count_24h']} entrée(s) lente(s), max {web['max_seconds']:.3f} s.",
                    f"Calcul Analytics {kind} : {worker['count_24h']} entrée(s) lente(s), max {worker['max_seconds']:.3f} s.",
                ],
                "interpretation": "Les deux couches signalent de la lenteur sur le même parcours fonctionnel. Cette correspondance oriente l'investigation vers le calcul Analytics, mais ne prouve pas à elle seule une cause PostgreSQL.",
                "next_step": f"Mesurer {kind} avec les mêmes filtres dans Analytics/EXPLAIN avant toute optimisation.",
            })
        elif kind:
            findings.append({
                "code": "WEB_WITHOUT_ANALYTICS_SLOW",
                "attention": web["attention"],
                "title": "Lenteur Web sans trace Analytics correspondante",
                "scope": web["key"],
                "evidence": [f"Route Web : {web['count_24h']} entrée(s) lente(s), max {web['max_seconds']:.3f} s."],
                "interpretation": "Aucune entrée du calcul Analytics correspondant n'a dépassé son propre seuil de journalisation dans la fenêtre disponible. Cela ne prouve pas que le worker est instantané.",
                "next_step": "Vérifier sérialisation, cache, attente du worker et réseau/TLS avant de modifier les requêtes SQL.",
            })
        else:
            findings.append({
                "code": "WEB_HOTSPOT",
                "attention": web["attention"],
                "title": "Route Web lente observée",
                "scope": web["key"],
                "evidence": [f"{web['count_24h']} entrée(s) lente(s) sur 24 h, max {web['max_seconds']:.3f} s."],
                "interpretation": "La lenteur est observée au niveau HTTP, sans correspondance Analytics définie pour cette route.",
                "next_step": "Reproduire la route avec le même scénario et mesurer le temps serveur avant toute modification.",
            })

    for worker in analytics_rows:
        if worker["key"] in seen_kinds:
            continue
        mapped_paths = [p for p, kind in _HTTP_TO_ANALYTICS.items() if kind == worker["key"]]
        findings.append({
            "code": "ANALYTICS_HOTSPOT",
            "attention": worker["attention"],
            "title": "Calcul Analytics lent observé",
            "scope": worker["key"],
            "evidence": [f"{worker['count_24h']} entrée(s) lente(s) sur 24 h, max {worker['max_seconds']:.3f} s."],
            "interpretation": "Le worker Analytics a dépassé son seuil de journalisation. L'absence éventuelle de route Web lente peut venir d'un autre seuil, du cache ou d'un autre appelant.",
            "next_step": (f"Rejouer {worker['key']} puis EXPLAIN les requêtes concernées." if mapped_paths else "Identifier l'appelant puis mesurer le calcul avant optimisation."),
        })

    soak_findings = []
    if soak.get("available"):
        warn = float((soak.get("thresholds") or {}).get("warn_p95_seconds") or 2.0)
        by_scenario = soak.get("by_scenario") or {}
        for scenario, row in by_scenario.items():
            p95 = row.get("p95_s")
            if p95 is None or float(p95) <= warn:
                continue
            path = _SOAK_TO_HTTP.get(str(scenario), str(scenario))
            item = {
                "code": "SOAK_P95_HIGH",
                "attention": "ELEVEE" if float(row.get("max_s") or 0.0) >= float((soak.get("thresholds") or {}).get("critical_max_seconds") or 10.0) else "A_VERIFIER",
                "title": "P95 élevé sous charge prolongée",
                "scope": path,
                "evidence": [f"Scénario {scenario} : P95 {float(p95):.3f} s, max {float(row.get('max_s') or 0.0):.3f} s, {int(row.get('count') or 0)} requêtes."],
                "interpretation": "La latence est reproduite avec plusieurs sessions indépendantes. Ce résultat mesure le parcours complet du test, pas uniquement PostgreSQL.",
                "next_step": "Comparer le même créneau avec les journaux Web/Analytics pour localiser la couche qui dépasse son seuil.",
            }
            soak_findings.append(item)
        findings.extend(soak_findings)

    postgres_note = {
        "available": bool(postgres.get("ok")),
        "latency_ms": postgres.get("latency_ms"),
        "interpretation": "Probe SELECT 1 ponctuel : utile pour confirmer la disponibilité, insuffisant pour attribuer une lenteur applicative à PostgreSQL.",
    }

    rank = {"ELEVEE": 0, "A_VERIFIER": 1}
    findings.sort(key=lambda x: (rank.get(x.get("attention"), 9), x.get("scope") or "", x.get("code") or ""))
    hotspots = sorted(http_rows + analytics_rows, key=lambda x: (rank.get(x["attention"], 9), -x["count_24h"], -x["max_seconds"], x["key"]))[:10]

    logs_available = bool(http.get("available") or analytics.get("available"))
    entries = int(http.get("last_24h") or 0) + int(analytics.get("last_24h") or 0)
    if findings:
        status = "A_INVESTIGUER"
    elif logs_available and entries == 0 and not soak.get("available"):
        status = "AUCUN_HOTSPOT_JOURNALISE"
    elif not logs_available and not soak.get("available"):
        status = "DONNEES_INSUFFISANTES"
    else:
        status = "AUCUN_SIGNAL_CIBLE"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "window": "24h",
        "read_only": True,
        "automatic_tuning": False,
        "evidence": {
            "http_log_available": bool(http.get("available")),
            "analytics_log_available": bool(analytics.get("available")),
            "soak_available": bool(soak.get("available")),
            "http_slow_24h": int(http.get("last_24h") or 0),
            "analytics_slow_24h": int(analytics.get("last_24h") or 0),
        },
        "hotspots": hotspots,
        "findings": findings[:12],
        "postgresql": postgres_note,
        "limitations": [
            "Une correspondance Web ↔ Analytics oriente l'investigation mais ne prouve pas une causalité PostgreSQL.",
            "Les journaux ne contiennent que les requêtes ayant dépassé leurs seuils respectifs ; l'absence d'entrée ne signifie pas latence nulle.",
            "Le test de charge mesure un parcours serveur authentifié et ne remplace pas une mesure navigateur/LAN.",
            "Aucune recommandation de ce module n'est appliquée automatiquement.",
        ],
    }


def markdown_report(snapshot: dict) -> str:
    analysis = (snapshot or {}).get("performance_analysis") or {}
    lines = [
        "# Analyse performances production Nelyio",
        "",
        f"- Généré : {analysis.get('generated_at') or snapshot.get('generated_at') or '—'}",
        f"- Version : {snapshot.get('version') or '—'}",
        f"- Statut : **{analysis.get('status') or 'INCONNU'}**",
        "- Mode : lecture seule ; aucun réglage appliqué automatiquement.",
        "",
        "## Couverture des preuves",
        "",
    ]
    ev = analysis.get("evidence") or {}
    lines += [
        f"- http_slow.log : {'oui' if ev.get('http_log_available') else 'non'} · {int(ev.get('http_slow_24h') or 0)} entrée(s) / 24 h",
        f"- analytics_slow.log : {'oui' if ev.get('analytics_log_available') else 'non'} · {int(ev.get('analytics_slow_24h') or 0)} entrée(s) / 24 h",
        f"- test de charge prolongée : {'oui' if ev.get('soak_available') else 'non'}",
        "",
        "## Constats ciblés",
        "",
    ]
    findings = analysis.get("findings") or []
    if not findings:
        lines.append("Aucun constat ciblé ne peut être établi avec les preuves actuellement disponibles.")
    for i, item in enumerate(findings, 1):
        lines += [
            f"### {i}. {item.get('title') or item.get('code') or 'Constat'}",
            "",
            f"- Périmètre : `{item.get('scope') or '—'}`",
            f"- Attention : {item.get('attention') or '—'}",
        ]
        for proof in item.get("evidence") or []:
            lines.append(f"- Preuve : {proof}")
        lines += [
            f"- Interprétation : {item.get('interpretation') or '—'}",
            f"- Prochaine vérification : {item.get('next_step') or '—'}",
            "",
        ]
    lines += ["## Limites", ""]
    for item in analysis.get("limitations") or []:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
