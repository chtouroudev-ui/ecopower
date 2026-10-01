"""Short-lived worker: open/reuse the Nelyio Edge profile, then auto-login if configured.

FIX5.1 writes a small non-secret runtime state file so the admin UI can report
what actually happened instead of treating process creation as success.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from hermes_credentials import status as credential_status
from hermes_cdp_login import auto_login

LOGIN_URL = "https://fr06-cloud.vocalcom.com/Hermes360/Admin/Launcher/login"
DIRECT_URL = (
    "https://fr06-supervision.vocalcom.com/hermes360/Supervision/Login.aspx?"
    "Id_Admin=1&Culture_inf=fr-FR&Oid_Company=hzKSeX0K&Oid_Network=&"
    "Oid_Network_Agent=WAN&Station=&Phone=&COLOR=LIGHT&Tz=Romance%20Standard%20Time"
)

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "OPEN_HERMES_SUPERVISION.ps1"
LOG = ROOT / "logs" / "hermes_supervision_auto.jsonl"
STATE = ROOT / "run" / "hermes_supervision_state.json"


def _write_state(stage: str, *, ok: bool | None = None, message: str = "", **extra) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": str(stage),
        "updated_at": int(time.time()),
        "ok": ok,
        "message": str(message or "")[:500],
        **{k: v for k, v in extra.items() if k not in {"password", "username", "secret"}},
    }
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, STATE)


def _log(event: str, **fields) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": int(time.time()), "event": event, **fields}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9222)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        _write_state("error", ok=False, message="Port CDP invalide.", code=2)
        _log("failed", stage="port", message="Port CDP invalide")
        return 2

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell or not SCRIPT.exists():
        _write_state("error", ok=False, message="PowerShell ou lanceur Hermes introuvable.", code=3)
        _log("failed", stage="launcher", message="PowerShell ou lanceur Hermes introuvable")
        return 3

    status = credential_status(check_decrypt=False)
    auto = bool(status.get("configured") and status.get("auto_login"))
    _write_state("opening_browser", ok=None, message="Ouverture du profil Edge Nelyio…", port=args.port, auto_login=auto)
    _log("start", port=args.port, auto_login=auto)

    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(SCRIPT),
        "-Port",
        str(args.port),
        "-WaitSeconds",
        "20",
        "-DirectSupervisionUrl",
        LOGIN_URL if auto else DIRECT_URL,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=55,
            check=False,
        )
    except subprocess.TimeoutExpired:
        _write_state("error", ok=False, message="Délai dépassé pendant l'ouverture d'Edge/Hermes.", code=6)
        _log("failed", stage="open_edge_timeout")
        return 6
    except Exception as exc:
        msg = f"Impossible de lancer PowerShell: {exc}"[:400]
        _write_state("error", ok=False, message=msg, code=7)
        _log("failed", stage="open_edge_exception", message=msg)
        return 7

    stdout = (result.stdout or "").strip()[-800:]
    stderr = (result.stderr or "").strip()[-800:]
    if result.returncode != 0:
        msg = stderr or stdout or f"Le lanceur Hermes a retourné le code {result.returncode}."
        _write_state("error", ok=False, message=msg, code=int(result.returncode))
        _log("failed", stage="open_edge", code=result.returncode, message=msg[:300])
        return 4

    _write_state("browser_ready", ok=True, message=stdout or "Edge/Hermes détecté.", port=args.port, auto_login=auto)
    if not auto:
        _write_state("completed", ok=True, message="Supervision Hermes ouverte. Connexion manuelle si la session est expirée.", port=args.port, auto_login=False)
        _log("opened", auto_login=False)
        return 0

    _write_state("auto_login", ok=None, message="Connexion Hermes automatique en cours…", port=args.port, auto_login=True)
    login = auto_login(args.port)
    ok = bool(login.get("ok"))
    state = "completed" if ok else "error"
    _write_state(state, ok=ok, message=str(login.get("message") or "")[:500], port=args.port, auto_login=True, login_state=login.get("state"))
    _log("login_result", state=login.get("state"), ok=ok, message=str(login.get("message") or "")[:300])
    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
