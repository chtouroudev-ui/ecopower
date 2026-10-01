"""Admin-triggered launcher for the dedicated Hermes supervision browser.

FIX5.1 no longer equates process creation with success. It starts the short-lived
worker, then waits briefly for the worker state file so the API can report a
real browser/CDP stage or an actionable error.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from hermes_credentials import status as credential_status

ROOT = Path(__file__).resolve().parent
WORKER = ROOT / "hermes_supervision_worker.py"
LOG_DIR = ROOT / "logs"
STATE_FILE = ROOT / "run" / "hermes_supervision_state.json"
AUTO_GUARD = ROOT / "run" / "hermes_supervision_auto_launch.json"
AUTO_MIN_INTERVAL = 120


def _read_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def status() -> dict:
    state = _read_state()
    cred = credential_status(check_decrypt=False)
    return {
        "stage": state.get("stage") or "idle",
        "ok": state.get("ok"),
        "message": state.get("message") or "",
        "updated_at": state.get("updated_at"),
        "port": state.get("port"),
        "auto_login": bool(cred.get("configured") and cred.get("auto_login")),
        "configured": bool(cred.get("configured")),
    }


def launch_supervision(port: int = 9222, *, wait_seconds: float = 8.0) -> dict:
    if isinstance(port, bool):
        raise ValueError("Port CDP invalide.")
    try:
        port = int(port)
    except (TypeError, ValueError) as exc:
        raise ValueError("Port CDP invalide.") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("Port CDP invalide.")
    if os.name != "nt":
        raise RuntimeError("L'ouverture de la supervision est disponible uniquement sur le serveur Windows Nelyio.")
    if not WORKER.exists():
        raise RuntimeError("Worker d'ouverture Hermes introuvable.")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        STATE_FILE.unlink()
    except OSError:
        pass
    out_path = LOG_DIR / "open_hermes_supervision.log"
    err_path = LOG_DIR / "open_hermes_supervision_error.log"
    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    with out_path.open("ab") as out, err_path.open("ab") as err:
        proc = subprocess.Popen(
            [sys.executable, str(WORKER), "--port", str(port)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            shell=False,
            creationflags=creationflags,
        )

    deadline = time.time() + max(1.0, float(wait_seconds))
    last = {}
    while time.time() < deadline:
        last = _read_state()
        stage = str(last.get("stage") or "")
        if stage in {"browser_ready", "auto_login", "completed", "error"}:
            break
        if proc.poll() is not None and not stage:
            break
        time.sleep(0.2)

    last = _read_state() or last
    if str(last.get("stage") or "") == "error":
        raise RuntimeError(str(last.get("message") or "Ouverture Hermes échouée."))
    if proc.poll() is not None and proc.returncode not in {None, 0} and not last:
        raise RuntimeError(f"Le worker Hermes s'est arrêté avec le code {proc.returncode}.")

    cred = credential_status(check_decrypt=False)
    auto = bool(cred.get("configured") and cred.get("auto_login"))
    stage = str(last.get("stage") or "starting")
    message = str(last.get("message") or "Ouverture Hermes démarrée.")
    return {
        "started": True,
        "pid": int(proc.pid),
        "port": port,
        "auto_login": auto,
        "stage": stage,
        "message": message,
    }


def maybe_launch_for_auto(port: int = 9222, *, clock: float | None = None) -> dict:
    now = float(time.time() if clock is None else clock)
    cred = credential_status(check_decrypt=False)
    if not (cred.get("configured") and cred.get("auto_login")):
        return {"started": False, "reason": "auto_login_not_configured"}
    if cred.get("cooldown_active"):
        return {"started": False, "reason": "login_cooldown", "cooldown_until": cred.get("cooldown_until")}
    try:
        guard = json.loads(AUTO_GUARD.read_text(encoding="utf-8")) if AUTO_GUARD.exists() else {}
    except (OSError, ValueError, TypeError):
        guard = {}
    last = float(guard.get("last_launch") or 0)
    if last and now - last < AUTO_MIN_INTERVAL:
        return {"started": False, "reason": "launch_rate_limited", "retry_in": int(AUTO_MIN_INTERVAL - (now-last))}
    result = launch_supervision(port)
    AUTO_GUARD.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTO_GUARD.with_suffix('.tmp')
    tmp.write_text(json.dumps({"last_launch": int(now), "pid": result.get("pid")}, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, AUTO_GUARD)
    return {**result, "reason": "waiting_browser_auto_open"}
