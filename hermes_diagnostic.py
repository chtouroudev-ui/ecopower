"""Admin-only passive Hermes supervision diagnostics over localhost CDP.

The scanner is disabled by default. It may be started manually by an admin or
from an explicitly enabled schedule. Reports contain only normalized metadata
(endpoint paths, detected callback/schema names and Live coverage); raw network
bodies, cookies, auth headers and credentials are never persisted.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RUN_DIR = ROOT / "run"
REPORT_DIR = DATA_DIR / "hermes_scan_reports"
SCHEDULE_FILE = DATA_DIR / "hermes_scan_schedule.json"
STATE_FILE = RUN_DIR / "hermes_scan_state.json"
LOCK_FILE = RUN_DIR / "hermes_scan.lock"
SCHEDULE_STATE_FILE = RUN_DIR / "hermes_scan_schedule_state.json"
WORKER = ROOT / "hermes_scan_worker.py"
ALLOWED_DURATIONS = {30, 60, 120}
ACTIVE_STATUSES = {"preparing","checking_browser","opening_browser","waiting_browser","running"}
MAX_REPORTS = 100
REPORT_RETENTION_DAYS = 30


def _json_read(path: Path, default):
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError, TypeError):
        return default


def _json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    os.replace(tmp,path)


def _duration(value) -> int:
    if isinstance(value,bool): raise ValueError("Durée de scan invalide.")
    try:value=int(value)
    except (TypeError,ValueError) as exc:raise ValueError("Durée de scan invalide.") from exc
    if value not in ALLOWED_DURATIONS:raise ValueError("Durée de scan autorisée : 30, 60 ou 120 secondes.")
    return value


def _port(value) -> int:
    if isinstance(value,bool):raise ValueError("Port CDP invalide.")
    try:value=int(value)
    except (TypeError,ValueError) as exc:raise ValueError("Port CDP invalide.") from exc
    if not 1024<=value<=65535:raise ValueError("Port CDP invalide.")
    return value


def _days(value) -> list[int]:
    if value is None:return [1,2,3,4,5,6,7]
    if not isinstance(value,list):raise ValueError("Jours planifiés invalides.")
    out=[]
    for item in value:
        if isinstance(item,bool):raise ValueError("Jours planifiés invalides.")
        try:n=int(item)
        except (TypeError,ValueError) as exc:raise ValueError("Jours planifiés invalides.") from exc
        if n<1 or n>7:raise ValueError("Jours planifiés invalides.")
        if n not in out:out.append(n)
    if not out:raise ValueError("Sélectionnez au moins un jour.")
    return sorted(out)


def _hhmm(value) -> str:
    text=str(value or "").strip()
    try:datetime.strptime(text,"%H:%M")
    except ValueError as exc:raise ValueError("Heure planifiée invalide (HH:MM).") from exc
    return text


def default_schedule() -> dict:
    return {"enabled":False,"time":"10:30","active_days":[1,2,3,4,5,6,7],"duration":60,
            "open_if_missing":False,"debug_port":9222,"updated_at":None,"updated_by":""}


def schedule() -> dict:
    raw=_json_read(SCHEDULE_FILE,{})
    base=default_schedule();base.update({k:v for k,v in raw.items() if k in base})
    try:
        base["enabled"]=bool(base.get("enabled"))
        base["time"]=_hhmm(base.get("time"))
        base["active_days"]=_days(base.get("active_days"))
        base["duration"]=_duration(base.get("duration"))
        base["debug_port"]=_port(base.get("debug_port"))
        base["open_if_missing"]=bool(base.get("open_if_missing"))
    except ValueError:
        return default_schedule()
    return base


def save_schedule(data: dict, actor: str) -> dict:
    if not isinstance(data,dict):raise ValueError("Configuration de planification invalide.")
    if not isinstance(data.get("enabled",False),bool):raise ValueError("Activation de planification invalide.")
    if not isinstance(data.get("open_if_missing",False),bool):raise ValueError("Option d'ouverture automatique invalide.")
    result={"enabled":data.get("enabled",False),"time":_hhmm(data.get("time") or "10:30"),
            "active_days":_days(data.get("active_days")),"duration":_duration(data.get("duration") or 60),
            "open_if_missing":data.get("open_if_missing",False),"debug_port":_port(data.get("debug_port") or 9222),
            "updated_at":int(time.time()),"updated_by":str(actor or "admin")[:128]}
    _json_write(SCHEDULE_FILE,result)
    return result


def _stale_seconds(state: dict) -> float:
    started=float(state.get("started_at") or 0)
    duration=int(state.get("duration") or 60)
    return max(0.0,time.time()-started-(duration+180)) if started else 0.0


def _clear_stale_lock() -> None:
    if not LOCK_FILE.exists():return
    state=_json_read(STATE_FILE,{})
    if state.get("status") not in ACTIVE_STATUSES or _stale_seconds(state)>0:
        try:LOCK_FILE.unlink()
        except OSError:pass
        if state.get("status") in ACTIVE_STATUSES:
            state.update(status="error",error="worker_timeout",message="Le worker Diagnostic Hermes n'a pas terminé dans le délai attendu.",finished_at=int(time.time()))
            _json_write(STATE_FILE,state)


def _acquire_lock() -> None:
    RUN_DIR.mkdir(parents=True,exist_ok=True)
    _clear_stale_lock()
    try:
        fd=os.open(str(LOCK_FILE),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError as exc:
        raise RuntimeError("Une analyse Hermes est déjà en cours.") from exc
    with os.fdopen(fd,"w",encoding="ascii") as handle:handle.write(str(os.getpid()))


def _release_lock() -> None:
    try:LOCK_FILE.unlink()
    except OSError:pass


def update_scan_state(**fields) -> dict:
    state=_json_read(STATE_FILE,{})
    state.update({k:v for k,v in fields.items() if k not in {"password","username","secret"}})
    state["updated_at"]=int(time.time())
    _json_write(STATE_FILE,state)
    return state


def _scanner_dependency_ready() -> None:
    try:
        from websockets.sync.client import connect as _connect  # noqa: F401
    except Exception as exc:
        raise RuntimeError("Module websockets absent pour le diagnostic Hermes. Lancez INSTALL_CAPTURE_DEPENDENCIES.bat puis redemarrez Nelyio.") from exc


def _supervision_target_present(port: int) -> bool:
    try:
        from hermes_cdp_login import _find_target, SUPERVISION_HOST
        return bool(_find_target(port, SUPERVISION_HOST))
    except Exception:
        return False


def start_scan(*, duration=60, debug_port=9222, open_if_missing=False, actor="admin", scheduled=False) -> dict:
    duration=_duration(duration);debug_port=_port(debug_port)
    if not isinstance(open_if_missing,bool):raise ValueError("Option d'ouverture automatique invalide.")
    if os.name!="nt":raise RuntimeError("L'analyse Hermes est disponible uniquement sur le serveur Windows Nelyio.")
    if not WORKER.exists():raise RuntimeError("Worker d'analyse Hermes introuvable.")
    _scanner_dependency_ready()
    if not open_if_missing and not _supervision_target_present(debug_port):
        raise RuntimeError("Onglet Supervision Hermes introuvable. Cochez 'Ouvrir / connecter Hermes si absent' ou ouvrez la supervision avant de lancer l'analyse.")
    _acquire_lock()
    started=int(time.time())
    state={"status":"preparing","started_at":started,"finished_at":None,"duration":duration,"debug_port":debug_port,
           "open_if_missing":open_if_missing,"actor":str(actor or "admin")[:128],"scheduled":bool(scheduled),
           "stop_requested":False,"report":"","error":""}
    _json_write(STATE_FILE,state)
    args=[sys.executable,str(WORKER),"--duration",str(duration),"--port",str(debug_port),"--actor",state["actor"]]
    if open_if_missing:args.append("--open-if-missing")
    creationflags=int(getattr(subprocess,"CREATE_NO_WINDOW",0))
    try:
        proc=subprocess.Popen(args,cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                              shell=False,creationflags=creationflags)
    except Exception:
        _release_lock();state.update(status="error",error="worker_start_failed",finished_at=int(time.time()));_json_write(STATE_FILE,state);raise
    state["pid"]=int(proc.pid);_json_write(STATE_FILE,state)
    return state


def request_stop() -> dict:
    state=_json_read(STATE_FILE,{})
    if state.get("status") not in ACTIVE_STATUSES:return {**state,"stop_requested":False}
    state["stop_requested"]=True;state["stop_requested_at"]=int(time.time());_json_write(STATE_FILE,state)
    return state


def stop_requested() -> bool:
    return bool(_json_read(STATE_FILE,{}).get("stop_requested"))


def finish_scan(*, report_path: str="", error: str="") -> None:
    state=_json_read(STATE_FILE,{})
    message=(str(error or "")[:500] if error else "Analyse Hermes terminée. Rapport normalisé enregistré.")
    state.update(status="error" if error else "completed",finished_at=int(time.time()),report=str(report_path or ""),error=str(error or "")[:500],message=message)
    _json_write(STATE_FILE,state);_release_lock();_cleanup_reports()


def _cleanup_reports() -> None:
    REPORT_DIR.mkdir(parents=True,exist_ok=True)
    cutoff=time.time()-REPORT_RETENTION_DAYS*86400
    files=sorted(REPORT_DIR.glob("scan_*.json"),key=lambda p:p.stat().st_mtime if p.exists() else 0,reverse=True)
    for idx,path in enumerate(files):
        try:
            if idx>=MAX_REPORTS or path.stat().st_mtime<cutoff:path.unlink()
        except OSError:pass


def last_report() -> dict | None:
    state=_json_read(STATE_FILE,{})
    path=Path(str(state.get("report") or "")) if state.get("report") else None
    if path and path.exists() and path.parent.resolve()==REPORT_DIR.resolve():
        data=_json_read(path,{})
        if data:return data
    files=sorted(REPORT_DIR.glob("scan_*.json"),key=lambda p:p.stat().st_mtime if p.exists() else 0,reverse=True) if REPORT_DIR.exists() else []
    return _json_read(files[0],{}) if files else None


def status() -> dict:
    _clear_stale_lock()
    state=_json_read(STATE_FILE,{"status":"idle"})
    report=last_report()
    summary=None
    if report:
        coverage=report.get("coverage") or {}
        summary={"started_at":report.get("started_at"),"finished_at":report.get("finished_at"),"duration_seconds":report.get("duration_seconds"),
                 "source_count":len(report.get("sources") or []),"candidate_count":sum(1 for x in (report.get("sources") or []) if not x.get("known")),
                 "functions":report.get("functions") or [],"coverage":coverage,"report_id":report.get("report_id")}
    return {"state":state,"schedule":schedule(),"last_report":summary,"retention_days":REPORT_RETENTION_DAYS,
            "allowed_durations":sorted(ALLOWED_DURATIONS)}


def _local_clock(clock: float) -> datetime:
    try:
        from nelyio_time import local_datetime
        return local_datetime(clock)
    except Exception:
        return datetime.fromtimestamp(clock)


def scheduler_tick(*, clock=None) -> dict:
    now=float(time.time() if clock is None else clock);cfg=schedule()
    if not cfg.get("enabled"):return {"started":False,"reason":"schedule_disabled"}
    dt=_local_clock(now);today=dt.strftime("%Y-%m-%d")
    if dt.isoweekday() not in cfg.get("active_days",[]):return {"started":False,"reason":"inactive_day"}
    hh,mm=map(int,cfg["time"].split(":"));target=dt.replace(hour=hh,minute=mm,second=0,microsecond=0)
    delta=(dt-target).total_seconds()
    if delta<0 or delta>600:return {"started":False,"reason":"outside_schedule_window"}
    sched_state=_json_read(SCHEDULE_STATE_FILE,{})
    if sched_state.get("last_attempt_day")==today:return {"started":False,"reason":"already_attempted_today"}
    sched_state.update(last_attempt_day=today,last_attempt_at=int(now));_json_write(SCHEDULE_STATE_FILE,sched_state)
    try:
        state=start_scan(duration=cfg["duration"],debug_port=cfg["debug_port"],open_if_missing=cfg["open_if_missing"],actor="schedule",scheduled=True)
        return {"started":True,"reason":"scheduled","pid":state.get("pid")}
    except Exception as exc:
        sched_state.update(last_error=str(exc)[:300]);_json_write(SCHEDULE_STATE_FILE,sched_state)
        return {"started":False,"reason":"scheduled_start_failed","error":str(exc)[:300]}
