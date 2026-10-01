#!/usr/bin/env python3
"""Generate a read-only, explainable production performance report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import production_observability
import performance_analysis


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=ROOT / "logs" / "performance_analysis.json")
    ap.add_argument("--markdown", type=Path, default=ROOT / "logs" / "performance_analysis.md")
    args = ap.parse_args()
    snapshot = production_observability._snapshot_uncached()
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(snapshot.get("performance_analysis") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
    args.markdown.write_text(performance_analysis.markdown_report(snapshot), encoding="utf-8")
    analysis = snapshot.get("performance_analysis") or {}
    print(json.dumps({
        "status": analysis.get("status"),
        "findings": len(analysis.get("findings") or []),
        "hotspots": len(analysis.get("hotspots") or []),
        "json": str(args.json),
        "markdown": str(args.markdown),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
