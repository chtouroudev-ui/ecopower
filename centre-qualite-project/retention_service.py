"""Nelyio retention/archive engine (Step 8).

Safety properties:
- dry-run by default;
- full-month eligibility only;
- coherent SQLite backups before destructive work;
- atomic monthly archives + manifest + SHA-256 + integrity_check;
- source/archive row-count verification before DELETE;
- transaction rollback on any failure;
- file lock against concurrent purge;
- legal holds from the Administration DB;
- import tombstones prevent purged SIMPLIFY2 exports from being resurrected.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import db_compat as sqlite3

import app_config as app_cfg
import details_store
import supervision_context as sup_ctx
from nelyio_time import day_bounds as local_day_bounds

POLICY_VERSION = "STEP8_OPTION_B_2026-09-15"
ARCHIVE_SCHEMA_VERSION = 1

DEFAULT_POLICY = {
    "operational_months": 6,
    "details_months": 12,
    "archive_months": 24,
    "aggregate_months": 36,
    "security_months": 12,
    "health_days": 30,
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _first_of_month(value: date):
    return date(value.year, value.month, 1)


def _shift_month(value: date, delta: int):
    idx = value.year * 12 + value.month - 1 + int(delta)
    return date(idx // 12, idx % 12 + 1, 1)



def _month_key(value: date):
    return value.strftime("%Y-%m")


def _month_bounds(month: date):
    start = _first_of_month(month)
    end = _shift_month(start, 1)
    a = local_day_bounds(start.isoformat())[0]
    b = local_day_bounds(end.isoformat())[0]
    return start, end, a, b


def _connect(path: Path, readonly=False):
    path = Path(path)
    # Runtime data lives in PostgreSQL after the total migration.  SQLite
    # file:// read-only URIs intentionally bypass db_compat, so using them here
    # would silently read stale rollback copies.  Route runtime databases to
    # PostgreSQL even for read-only planning; legacy/archive files remain SQLite.
    if sqlite3.postgres_enabled() and sqlite3.schema_for_database(path):
        con = sqlite3.connect(str(path), timeout=30)
    elif readonly:
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)
    else:
        con = sqlite3.connect(str(path), timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=30000")
    if not readonly:
        con.execute("PRAGMA foreign_keys=ON")
    return con


def _table_exists(con, name):
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def ensure_supervision_retention_schema(con):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS retention_import_tombstones(
          digest TEXT PRIMARY KEY,
          name TEXT,
          reference_day TEXT,
          original_import_id INTEGER,
          archive_path TEXT,
          purged_at TEXT NOT NULL,
          policy_version TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS retention_tombstone_day ON retention_import_tombstones(reference_day);
        CREATE TABLE IF NOT EXISTS retention_monthly_aggregates(
          month TEXT PRIMARY KEY,
          calls INTEGER NOT NULL DEFAULT 0,
          activities INTEGER NOT NULL DEFAULT 0,
          offline_events INTEGER NOT NULL DEFAULT 0,
          live_events INTEGER NOT NULL DEFAULT 0,
          technical_signals INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL
        );
    """)


def _admin_policy(admin_db: Path):
    policy = dict(DEFAULT_POLICY)
    archive_dir = app_cfg.BASE / "archives"
    backup_dir = app_cfg.BASE / "backups" / "retention"
    enabled = False
    if Path(admin_db).is_file():
        con = _connect(admin_db, readonly=True)
        try:
            if _table_exists(con, "settings"):
                settings = dict(con.execute("SELECT key,value FROM settings WHERE key LIKE 'retention_%'"))
                def integer(key, default, lo, hi):
                    try: return max(lo, min(hi, int(settings.get(key, default))))
                    except Exception: return default
                policy.update({
                    "operational_months": integer("retention_operational_months", 6, 1, 120),
                    "details_months": integer("retention_details_months", 12, 1, 120),
                    "archive_months": integer("retention_archive_months", 24, 1, 240),
                    "aggregate_months": integer("retention_aggregate_months", 36, 1, 240),
                    "security_months": integer("retention_security_months", 12, 1, 120),
                    "health_days": integer("retention_health_days", 30, 1, 3650),
                })
                enabled = str(settings.get("retention_enabled", "0")).lower() in {"1","true","yes","on"}
                if settings.get("retention_archive_dir"):
                    archive_dir = Path(settings["retention_archive_dir"])
                if settings.get("retention_backup_dir"):
                    backup_dir = Path(settings["retention_backup_dir"])
        finally:
            con.close()
    return policy, Path(archive_dir), Path(backup_dir), enabled


def _legal_holds(admin_db: Path):
    if not Path(admin_db).is_file():
        return []
    con = _connect(admin_db, readonly=True)
    try:
        if not _table_exists(con, "retention_legal_holds"):
            return []
        return [dict(r) for r in con.execute(
            "SELECT id,start_day,end_day,reason,active,reevaluate_at,created_at,created_by FROM retention_legal_holds WHERE active=1 ORDER BY start_day"
        )]
    finally:
        con.close()


def _held(month: date, holds):
    start, end, _, _ = _month_bounds(month)
    for hold in holds:
        try:
            hs = date.fromisoformat(str(hold.get("start_day")))
            he = date.fromisoformat(str(hold.get("end_day")))
        except Exception:
            continue
        if hs < end and he >= start:
            return hold
    return None


def _source_months_supervision(path: Path):
    if not path.is_file():
        return set()
    con = _connect(path, readonly=True)
    months = set()
    try:
        queries = [
            ("imports", "SELECT substr(reference_day,1,7) m FROM imports WHERE reference_day IS NOT NULL GROUP BY m"),
            ("live_events", "SELECT strftime('%Y-%m',start,'unixepoch') m FROM live_events GROUP BY m"),
            ("technical_signals", "SELECT strftime('%Y-%m',start,'unixepoch') m FROM technical_signals GROUP BY m"),
            ("health_points", "SELECT strftime('%Y-%m',stamp,'unixepoch') m FROM health_points GROUP BY m"),
            ("audit", "SELECT substr(stamp,1,7) m FROM audit WHERE stamp IS NOT NULL GROUP BY m"),
            ("auto_import_log", "SELECT substr(processed_at,1,7) m FROM auto_import_log WHERE processed_at IS NOT NULL GROUP BY m"),
            ("notes", "SELECT substr(stamp,1,7) m FROM notes WHERE stamp IS NOT NULL GROUP BY m"),
        ]
        for table, sql in queries:
            if not _table_exists(con, table):
                continue
            for row in con.execute(sql):
                if row[0] and re.fullmatch(r"\d{4}-\d{2}", str(row[0])):
                    months.add(str(row[0]))
    finally:
        con.close()
    return months


def _source_months_details(path: Path):
    if not path.is_file():
        return set()
    con = _connect(path, readonly=True)
    months = set()
    try:
        queries = [
            ("detail_events", "SELECT strftime('%Y-%m',start,'unixepoch') m FROM detail_events GROUP BY m"),
            ("sync_runs", "SELECT substr(started_at,1,7) m FROM sync_runs WHERE started_at IS NOT NULL GROUP BY m"),
            ("detail_imports", "SELECT substr(COALESCE(imported_at,synced_at),1,7) m FROM detail_imports WHERE COALESCE(imported_at,synced_at) IS NOT NULL GROUP BY m"),
        ]
        for table, sql in queries:
            if not _table_exists(con, table): continue
            for row in con.execute(sql):
                if row[0] and re.fullmatch(r"\d{4}-\d{2}", str(row[0])):
                    months.add(str(row[0]))
        return months
    finally:
        con.close()


def _source_months_admin(path: Path):
    if not path.is_file():
        return set()
    con = _connect(path, readonly=True)
    months = set()
    try:
        for table, column in (("auth_audit", "created_at"), ("retention_runs", "started_at")):
            if not _table_exists(con, table):
                continue
            for row in con.execute(f"SELECT substr({column},1,7) m FROM {table} WHERE {column} IS NOT NULL GROUP BY m"):
                if row[0] and re.fullmatch(r"\d{4}-\d{2}", str(row[0])):
                    months.add(str(row[0]))
    finally:
        con.close()
    return months


def _counts_admin_month(con, month: date, cutoffs):
    if month >= cutoffs["security"]:
        return {}
    key = _month_key(month)
    out = {}
    if _table_exists(con, "auth_audit"):
        out["auth_audit"] = con.execute("SELECT COUNT(*) FROM auth_audit WHERE substr(created_at,1,7)=?", (key,)).fetchone()[0]
    if _table_exists(con, "retention_runs"):
        out["retention_runs"] = con.execute("SELECT COUNT(*) FROM retention_runs WHERE substr(started_at,1,7)=?", (key,)).fetchone()[0]
    return {k:int(v) for k,v in out.items() if int(v)>0}


def _counts_supervision_month(con, month: date, policy, cutoffs):
    start, end, a, b = _month_bounds(month)
    key = _month_key(month)
    out = {}
    eligible_operational = month < cutoffs["operational"]
    eligible_security = month < cutoffs["security"]
    eligible_notes = month < cutoffs["archive"]
    # health is intentionally full-month only; this may retain slightly more
    # than 30 days but never purges a partial month.
    eligible_health = end <= cutoffs["health_month"]
    if eligible_operational:
        ids = [r[0] for r in con.execute("SELECT id FROM imports WHERE reference_day>=? AND reference_day<?", (start.isoformat(), end.isoformat()))]
        out["imports"] = len(ids)
        if ids:
            marks = ",".join("?" * len(ids))
            for table in ("activities", "phone_calls", "phone_call_details", "call_imports", "quality_inbound_facts", "quality_inbound_imports", "quality_agent_facts", "quality_agent_imports"):
                if _table_exists(con, table):
                    out[table] = con.execute(f"SELECT COUNT(*) FROM {table} WHERE import_id IN ({marks})", ids).fetchone()[0]
            out["coverage"] = con.execute("SELECT COUNT(*) FROM coverage WHERE day>=? AND day<?", (start.isoformat(), end.isoformat())).fetchone()[0]
            out["call_coverage"] = con.execute("SELECT COUNT(*) FROM call_coverage WHERE day>=? AND day<?", (start.isoformat(), end.isoformat())).fetchone()[0]
        else:
            out.update({"activities":0,"phone_calls":0,"phone_call_details":0,"call_imports":0,"coverage":0,"call_coverage":0})
        out["live_events"] = con.execute("SELECT COUNT(*) FROM live_events WHERE start>=? AND start<?", (a,b)).fetchone()[0]
        out["technical_signals"] = con.execute("SELECT COUNT(*) FROM technical_signals WHERE start>=? AND start<?", (a,b)).fetchone()[0]
    if eligible_health and _table_exists(con, "health_points"):
        out["health_points"] = con.execute("SELECT COUNT(*) FROM health_points WHERE stamp>=? AND stamp<?", (a,b)).fetchone()[0]
    if eligible_security:
        if _table_exists(con, "audit"):
            out["audit"] = con.execute("SELECT COUNT(*) FROM audit WHERE substr(stamp,1,7)=?", (key,)).fetchone()[0]
        if _table_exists(con, "auto_import_log"):
            out["auto_import_log"] = con.execute("SELECT COUNT(*) FROM auto_import_log WHERE substr(processed_at,1,7)=?", (key,)).fetchone()[0]
    if eligible_notes and _table_exists(con, "notes"):
        out["notes"] = con.execute("SELECT COUNT(*) FROM notes WHERE substr(stamp,1,7)=?", (key,)).fetchone()[0]
    return {k:int(v) for k,v in out.items() if int(v)>0}


def _counts_details_month(con, month: date, cutoffs):
    start, end, a, b = _month_bounds(month); key=_month_key(month)
    out={}
    if month < cutoffs["details"]:
        if _table_exists(con,"detail_events"):
            events=con.execute("SELECT COUNT(*) FROM detail_events WHERE start>=? AND start<?",(a,b)).fetchone()[0]
            if events:
                out["detail_events"]=int(events)
                out["detail_event_agents"]=int(con.execute("SELECT COUNT(*) FROM detail_event_agents WHERE event_uid IN (SELECT event_uid FROM detail_events WHERE start>=? AND start<?)",(a,b)).fetchone()[0])
        if _table_exists(con,"sync_runs"):
            count=con.execute("SELECT COUNT(*) FROM sync_runs WHERE substr(started_at,1,7)=?",(key,)).fetchone()[0]
            if count: out["sync_runs"]=int(count)
    if month < cutoffs["archive"] and _table_exists(con,"detail_imports"):
        count=con.execute("SELECT COUNT(*) FROM detail_imports WHERE substr(COALESCE(imported_at,synced_at),1,7)=?",(key,)).fetchone()[0]
        if count: out["detail_imports"]=int(count)
    return out


def retention_plan(as_of=None, supervision_db=None, details_db=None, admin_db=None):
    as_of = as_of or datetime.now(timezone.utc).date()
    if isinstance(as_of, datetime): as_of = as_of.date()
    if isinstance(as_of, str): as_of = date.fromisoformat(as_of)
    supervision_db = Path(supervision_db or sup_ctx.db_path())
    details_db = Path(details_db or details_store.DETAILS_DB)
    admin_db = Path(admin_db or sup_ctx.admin_db_path())
    policy, archive_dir, backup_dir, enabled = _admin_policy(admin_db)
    first = _first_of_month(as_of)
    cutoffs = {
        "operational": _shift_month(first, -policy["operational_months"]),
        "details": _shift_month(first, -policy["details_months"]),
        "archive": _shift_month(first, -policy["archive_months"]),
        "aggregate": _shift_month(first, -policy["aggregate_months"]),
        "security": _shift_month(first, -policy["security_months"]),
        "health_month": _first_of_month(as_of - timedelta(days=policy["health_days"])),
    }
    holds = _legal_holds(admin_db)
    sup_months = _source_months_supervision(supervision_db)
    det_months = _source_months_details(details_db)
    admin_months = _source_months_admin(admin_db)
    months = sorted(sup_months | det_months | admin_months)
    items=[]
    sup_con = _connect(supervision_db, readonly=True) if supervision_db.is_file() else None
    det_con = _connect(details_db, readonly=True) if details_db.is_file() else None
    admin_con = _connect(admin_db, readonly=True) if admin_db.is_file() else None
    try:
        for key in months:
            month = date.fromisoformat(key+"-01")
            hold = _held(month, holds)
            sup_counts = _counts_supervision_month(sup_con, month, policy, cutoffs) if sup_con else {}
            det_counts = _counts_details_month(det_con, month, cutoffs) if det_con else {}
            admin_counts = _counts_admin_month(admin_con, month, cutoffs) if admin_con else {}
            if not sup_counts and not det_counts and not admin_counts:
                continue
            items.append({"month":key,"held":bool(hold),"hold":hold,"supervision":sup_counts,"details":det_counts,"admin":admin_counts})
    finally:
        if sup_con: sup_con.close()
        if det_con: det_con.close()
        if admin_con: admin_con.close()
    return {
        "policy_version": POLICY_VERSION,
        "as_of": as_of.isoformat(),
        "enabled": enabled,
        "policy": policy,
        "cutoffs": {k:v.isoformat() for k,v in cutoffs.items()},
        "archive_dir": str(archive_dir),
        "backup_dir": str(backup_dir),
        "supervision_db": str(supervision_db),
        "details_db": str(details_db),
        "admin_db": str(admin_db),
        "holds": holds,
        "items": items,
    }


def _create_table_like(src, dst, table):
    row = src.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row or not row[0]:
        return False
    dst.execute(row[0])
    return True


def _copy_select(src, dst, table, where="", params=()):
    if not _table_exists(src, table):
        return 0
    if not _table_exists(dst, table):
        _create_table_like(src, dst, table)
    cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
    if not cols:
        return 0
    sql = f"SELECT {','.join(cols)} FROM {table}" + (" WHERE "+where if where else "")
    rows = src.execute(sql, params).fetchall()
    if rows:
        dst.executemany(f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?'*len(cols))})", [tuple(r) for r in rows])
    return len(rows)


def _archive_supervision_month(src, month, counts, destination: Path, backup_id):
    start,end,a,b = _month_bounds(month); key=_month_key(month)
    tmp = destination.with_suffix(destination.suffix+".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    dst = sqlite3.connect(str(tmp))
    copied={}
    try:
        dst.execute("PRAGMA journal_mode=DELETE")
        ids=[r[0] for r in src.execute("SELECT id FROM imports WHERE reference_day>=? AND reference_day<?",(start.isoformat(),end.isoformat()))]
        if counts.get("imports"):
            marks=",".join("?"*len(ids))
            copied["imports"]=_copy_select(src,dst,"imports",f"id IN ({marks})",ids)
            copied["activities"]=_copy_select(src,dst,"activities",f"import_id IN ({marks})",ids)
            copied["phone_calls"]=_copy_select(src,dst,"phone_calls",f"import_id IN ({marks})",ids)
            if _table_exists(src,"phone_call_details"):copied["phone_call_details"]=_copy_select(src,dst,"phone_call_details",f"import_id IN ({marks})",ids)
            copied["call_imports"]=_copy_select(src,dst,"call_imports",f"import_id IN ({marks})",ids)
            for table in ("quality_inbound_facts", "quality_inbound_imports", "quality_agent_facts", "quality_agent_imports"):
                if _table_exists(src,table):copied[table]=_copy_select(src,dst,table,f"import_id IN ({marks})",ids)
            copied["coverage"]=_copy_select(src,dst,"coverage","day>=? AND day<?",(start.isoformat(),end.isoformat()))
            copied["call_coverage"]=_copy_select(src,dst,"call_coverage","day>=? AND day<?",(start.isoformat(),end.isoformat()))
        if counts.get("live_events"): copied["live_events"]=_copy_select(src,dst,"live_events","start>=? AND start<?",(a,b))
        if counts.get("technical_signals"): copied["technical_signals"]=_copy_select(src,dst,"technical_signals","start>=? AND start<?",(a,b))
        if counts.get("health_points"): copied["health_points"]=_copy_select(src,dst,"health_points","stamp>=? AND stamp<?",(a,b))
        if counts.get("audit"): copied["audit"]=_copy_select(src,dst,"audit","substr(stamp,1,7)=?",(key,))
        if counts.get("auto_import_log"): copied["auto_import_log"]=_copy_select(src,dst,"auto_import_log","substr(processed_at,1,7)=?",(key,))
        if counts.get("notes"): copied["notes"]=_copy_select(src,dst,"notes","substr(stamp,1,7)=?",(key,))
        dst.execute("CREATE TABLE retention_archive_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        meta={"policy_version":POLICY_VERSION,"source":"NELYIO_Supervision.db","month":key,"created_at":_utc_now(),"backup_id":backup_id}
        dst.executemany("INSERT INTO retention_archive_meta VALUES(?,?)",meta.items())
        dst.commit()
        integrity=dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok": raise RuntimeError("Archive supervision integrity_check != ok")
        for table, expected in counts.items():
            if copied.get(table,0)!=expected:
                raise RuntimeError(f"Archive supervision count mismatch {table}: {copied.get(table,0)} != {expected}")
    finally:
        dst.close()
    os.replace(tmp,destination)
    digest=_sha256(destination)
    manifest={"status":"VERIFIED","period":key,"schema_version":ARCHIVE_SCHEMA_VERSION,"created_at":_utc_now(),"source":"NELYIO_Supervision.db","row_counts":copied,"sha256":digest,"integrity_check":"ok","backup_id":backup_id,"policy_version":POLICY_VERSION}
    mp=destination.with_suffix(".manifest.json")
    mt=mp.with_suffix(mp.suffix+".tmp");mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8");os.replace(mt,mp)
    return manifest


def _archive_details_month(src, month, counts, destination: Path, backup_id):
    start,end,a,b=_month_bounds(month);key=_month_key(month)
    tmp=destination.with_suffix(destination.suffix+".tmp");tmp.parent.mkdir(parents=True,exist_ok=True);tmp.unlink(missing_ok=True)
    dst=sqlite3.connect(str(tmp));copied={}
    try:
        dst.execute("PRAGMA foreign_keys=OFF")
        if counts.get("detail_events"):
            copied["detail_events"]=_copy_select(src,dst,"detail_events","start>=? AND start<?",(a,b))
            copied["detail_event_agents"]=_copy_select(src,dst,"detail_event_agents","event_uid IN (SELECT event_uid FROM detail_events WHERE start>=? AND start<?)",(a,b))
        if counts.get("sync_runs"):
            copied["sync_runs"]=_copy_select(src,dst,"sync_runs","substr(started_at,1,7)=?",(key,))
        if counts.get("detail_imports"):
            copied["detail_imports"]=_copy_select(src,dst,"detail_imports","substr(COALESCE(imported_at,synced_at),1,7)=?",(key,))
        dst.execute("CREATE TABLE retention_archive_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        meta={"policy_version":POLICY_VERSION,"source":"Nelyio_Details.db","month":key,"created_at":_utc_now(),"backup_id":backup_id}
        dst.executemany("INSERT INTO retention_archive_meta VALUES(?,?)",meta.items());dst.commit()
        integrity=dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok":raise RuntimeError("Archive details integrity_check != ok")
        for table,expected in counts.items():
            if copied.get(table,0)!=expected:raise RuntimeError(f"Archive details count mismatch {table}: {copied.get(table,0)} != {expected}")
    finally:dst.close()
    os.replace(tmp,destination);digest=_sha256(destination)
    manifest={"status":"VERIFIED","period":key,"schema_version":ARCHIVE_SCHEMA_VERSION,"created_at":_utc_now(),"source":"Nelyio_Details.db","row_counts":copied,"sha256":digest,"integrity_check":"ok","backup_id":backup_id,"policy_version":POLICY_VERSION}
    mp=destination.with_suffix(".manifest.json");mt=mp.with_suffix(mp.suffix+".tmp");mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8");os.replace(mt,mp)
    return manifest


def _archive_admin_month(src, month, counts, destination: Path, backup_id):
    key = _month_key(month)
    tmp = destination.with_suffix(destination.suffix+".tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.unlink(missing_ok=True)
    dst = sqlite3.connect(str(tmp)); copied = {}
    try:
        if counts.get("auth_audit"):
            copied["auth_audit"] = _copy_select(src,dst,"auth_audit","substr(created_at,1,7)=?",(key,))
        if counts.get("retention_runs"):
            copied["retention_runs"] = _copy_select(src,dst,"retention_runs","substr(started_at,1,7)=?",(key,))
        dst.execute("CREATE TABLE retention_archive_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        meta={"policy_version":POLICY_VERSION,"source":"TECHIN_Stock_Manager.db/security","month":key,"created_at":_utc_now(),"backup_id":backup_id}
        dst.executemany("INSERT INTO retention_archive_meta VALUES(?,?)",meta.items()); dst.commit()
        integrity=dst.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok": raise RuntimeError("Archive admin integrity_check != ok")
        for table, expected in counts.items():
            if copied.get(table,0)!=expected:
                raise RuntimeError(f"Archive admin count mismatch {table}: {copied.get(table,0)} != {expected}")
    finally:
        dst.close()
    os.replace(tmp,destination); digest=_sha256(destination)
    manifest={"status":"VERIFIED","period":key,"schema_version":ARCHIVE_SCHEMA_VERSION,"created_at":_utc_now(),"source":"TECHIN_Stock_Manager.db/security","row_counts":copied,"sha256":digest,"integrity_check":"ok","backup_id":backup_id,"policy_version":POLICY_VERSION}
    mp=destination.with_suffix(".manifest.json"); mt=mp.with_suffix(mp.suffix+".tmp"); mt.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8"); os.replace(mt,mp)
    return manifest


def _purge_admin_month(con, month, counts):
    key=_month_key(month)
    if counts.get("auth_audit"):
        con.execute("DELETE FROM auth_audit WHERE substr(created_at,1,7)=?",(key,))
    if counts.get("retention_runs"):
        con.execute("DELETE FROM retention_runs WHERE substr(started_at,1,7)=?",(key,))


def _mark_archive_purged(destination: Path):
    manifest=Path(destination).with_suffix(".manifest.json")
    if not manifest.is_file():
        raise RuntimeError(f"Manifeste archive introuvable après purge: {manifest}")
    data=json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("sha256") != _sha256(Path(destination)):
        raise RuntimeError(f"SHA-256 archive modifié avant finalisation: {destination}")
    data["status"]="PURGED_FROM_ACTIVE"
    data["purged_from_active_at"]=_utc_now()
    tmp=manifest.with_suffix(manifest.suffix+".tmp")
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    os.replace(tmp,manifest)
    return data


def _backup_one(src: Path, destination: Path):
    if not src.is_file(): return None
    destination.parent.mkdir(parents=True,exist_ok=True);tmp=destination.with_suffix(destination.suffix+".tmp");tmp.unlink(missing_ok=True)
    s=_connect(src,readonly=True);d=sqlite3.connect(str(tmp))
    try:
        s.backup(d);d.commit();integrity=d.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok":raise RuntimeError(f"Backup integrity failure: {src.name}")
    finally:s.close();d.close()
    os.replace(tmp,destination)
    return {"source":str(src),"backup":str(destination),"sha256":_sha256(destination),"integrity_check":"ok","size":destination.stat().st_size}


def _create_backup_set(supervision_db, details_db, admin_db, backup_dir):
    backup_id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder=Path(backup_dir)/backup_id;folder.mkdir(parents=True,exist_ok=False)
    files=[]
    for src in (Path(supervision_db),Path(details_db),Path(admin_db)):
        info=_backup_one(src,folder/src.name)
        if info:files.append(info)
    if not files:raise RuntimeError("Aucune base disponible pour la sauvegarde de rétention")
    manifest={"backup_id":backup_id,"created_at":_utc_now(),"policy_version":POLICY_VERSION,"files":files}
    mp=folder/"backup.manifest.json";mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return backup_id,manifest


@contextmanager
def _retention_lock(base: Path):
    lock=Path(base)/"retention.lock";lock.parent.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Une opération de rétention est déjà verrouillée : {lock}") from exc
    try:
        os.write(fd,f"pid={os.getpid()} started={_utc_now()}\n".encode());os.close(fd);yield lock
    finally:
        try:lock.unlink()
        except FileNotFoundError:pass


def _save_run(admin_db,mode,status,actor,summary=None,error="",run_id=None):
    if not Path(admin_db).is_file():return run_id
    con=_connect(admin_db)
    try:
        if not _table_exists(con,"retention_runs"):return run_id
        if run_id is None:
            cur=con.execute("INSERT INTO retention_runs(mode,status,started_at,actor,summary_json,error) VALUES(?,?,?,?,?,?)",
                (mode,status,_utc_now(),actor,json.dumps(summary or {},ensure_ascii=False),error));run_id=cur.lastrowid
        else:
            con.execute("UPDATE retention_runs SET status=?,finished_at=?,summary_json=?,error=? WHERE id=?",
                (status,_utc_now(),json.dumps(summary or {},ensure_ascii=False),error,run_id))
        con.commit();return run_id
    finally:con.close()


def _purge_supervision_month(con, month, counts, archive_path):
    start,end,a,b=_month_bounds(month);key=_month_key(month)
    ensure_supervision_retention_schema(con)
    ids=[r[0] for r in con.execute("SELECT id FROM imports WHERE reference_day>=? AND reference_day<?",(start.isoformat(),end.isoformat()))]
    aggregate={"calls":0,"activities":0,"offline_events":0,"live_events":0,"technical_signals":0}
    if ids:
        marks=",".join("?"*len(ids))
        aggregate["activities"]=con.execute(f"SELECT COUNT(*) FROM activities WHERE import_id IN ({marks})",ids).fetchone()[0]
        aggregate["offline_events"]=con.execute(f"SELECT COUNT(*) FROM activities WHERE import_id IN ({marks}) AND kind='offline'",ids).fetchone()[0]
        aggregate["calls"]=con.execute(f"SELECT COUNT(*) FROM phone_calls WHERE import_id IN ({marks})",ids).fetchone()[0]
        for r in con.execute(f"SELECT id,digest,name,reference_day FROM imports WHERE id IN ({marks})",ids):
            con.execute("INSERT OR REPLACE INTO retention_import_tombstones(digest,name,reference_day,original_import_id,archive_path,purged_at,policy_version) VALUES(?,?,?,?,?,?,?)",
                (r["digest"],r["name"],r["reference_day"],r["id"],str(archive_path),_utc_now(),POLICY_VERSION))
        con.execute(f"DELETE FROM phone_calls WHERE import_id IN ({marks})",ids)
        if _table_exists(con,"phone_call_details"):con.execute(f"DELETE FROM phone_call_details WHERE import_id IN ({marks})",ids)
        con.execute(f"DELETE FROM call_imports WHERE import_id IN ({marks})",ids)
        for table in ("quality_inbound_facts", "quality_inbound_imports", "quality_agent_facts", "quality_agent_imports"):
            if _table_exists(con,table):con.execute(f"DELETE FROM {table} WHERE import_id IN ({marks})",ids)
        con.execute("DELETE FROM call_coverage WHERE day>=? AND day<?",(start.isoformat(),end.isoformat()))
        con.execute(f"DELETE FROM activities WHERE import_id IN ({marks})",ids)
        con.execute("DELETE FROM coverage WHERE day>=? AND day<?",(start.isoformat(),end.isoformat()))
        if _table_exists(con,"import_reference_states"):
            con.execute(f"DELETE FROM import_reference_states WHERE import_id IN ({marks})",ids)
        if _table_exists(con,"import_reference_choices"):
            con.execute("DELETE FROM import_reference_choices WHERE day>=? AND day<?",(start.isoformat(),end.isoformat()))
        if _table_exists(con,"import_jobs"):
            con.execute(f"UPDATE import_jobs SET status='purged',import_id=NULL WHERE import_id IN ({marks})",ids)
        con.execute(f"DELETE FROM imports WHERE id IN ({marks})",ids)
    if counts.get("live_events"):
        aggregate["live_events"]=counts["live_events"];con.execute("DELETE FROM live_events WHERE start>=? AND start<?",(a,b))
    if counts.get("technical_signals"):
        aggregate["technical_signals"]=counts["technical_signals"];con.execute("DELETE FROM technical_signals WHERE start>=? AND start<?",(a,b))
    if counts.get("health_points"):con.execute("DELETE FROM health_points WHERE stamp>=? AND stamp<?",(a,b))
    if counts.get("audit"):con.execute("DELETE FROM audit WHERE substr(stamp,1,7)=?",(key,))
    if counts.get("auto_import_log"):con.execute("DELETE FROM auto_import_log WHERE substr(processed_at,1,7)=?",(key,))
    if counts.get("notes"):con.execute("DELETE FROM notes WHERE substr(stamp,1,7)=?",(key,))
    if any(aggregate.values()):
        con.execute("""INSERT INTO retention_monthly_aggregates(month,calls,activities,offline_events,live_events,technical_signals,updated_at)
          VALUES(?,?,?,?,?,?,?) ON CONFLICT(month) DO UPDATE SET calls=excluded.calls,activities=excluded.activities,
          offline_events=excluded.offline_events,live_events=excluded.live_events,technical_signals=excluded.technical_signals,updated_at=excluded.updated_at""",
          (key,aggregate["calls"],aggregate["activities"],aggregate["offline_events"],aggregate["live_events"],aggregate["technical_signals"],_utc_now()))
    return aggregate


def _purge_details_month(con, month, counts):
    start,end,a,b=_month_bounds(month);key=_month_key(month)
    con.execute("PRAGMA foreign_keys=ON")
    if counts.get("detail_events"):
        con.execute("DELETE FROM detail_events WHERE start>=? AND start<?",(a,b))
        # active_days is only a current routing aid; discard stale rows for the month.
        con.execute("DELETE FROM active_days WHERE day>=? AND day<?",(start.isoformat(),end.isoformat()))
    if counts.get("sync_runs"):
        con.execute("DELETE FROM sync_runs WHERE substr(started_at,1,7)=?",(key,))
    if counts.get("detail_imports"):
        con.execute("DELETE FROM detail_imports WHERE substr(COALESCE(imported_at,synced_at),1,7)=?",(key,))


def _expire_aggregates(con, cutoff: date):
    if _table_exists(con,"retention_monthly_aggregates"):
        con.execute("DELETE FROM retention_monthly_aggregates WHERE month<?",(_month_key(cutoff),))


def _expire_archives(archive_dir: Path, cutoff: date, holds, dry_run):
    removed=[]
    if not archive_dir.exists():return removed
    pattern=re.compile(r"_(\d{4}-\d{2})\.sqlite$")
    for path in archive_dir.rglob("*.sqlite"):
        m=pattern.search(path.name)
        if not m:continue
        month=date.fromisoformat(m.group(1)+"-01")
        if month>=cutoff or _held(month,holds):continue
        manifest=path.with_suffix(".manifest.json")
        if not manifest.is_file():continue
        try:data=json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:continue
        if data.get("status") not in {"VERIFIED","PURGED_FROM_ACTIVE"} or data.get("sha256")!=_sha256(path):continue
        removed.append(str(path))
        if not dry_run:
            path.unlink();manifest.unlink(missing_ok=True)
    return removed


def _validate_storage_roots(archive_root: Path, backup_root: Path, source_paths):
    archive_root=Path(archive_root).expanduser().resolve(strict=False)
    backup_root=Path(backup_root).expanduser().resolve(strict=False)
    if archive_root == backup_root or archive_root in backup_root.parents or backup_root in archive_root.parents:
        raise RuntimeError("Les dossiers archives et sauvegardes doivent être séparés et non imbriqués.")
    for source in source_paths:
        source=Path(source).expanduser().resolve(strict=False)
        if archive_root == source or backup_root == source:
            raise RuntimeError("Un dossier de rétention ne peut pas être un fichier de base active.")
    return archive_root, backup_root


def run_retention(*, dry_run=True, actor="SYSTEM", as_of=None, supervision_db=None, details_db=None, admin_db=None,
                  archive_dir=None, backup_dir=None):
    """Plan or execute the validated Option-B policy.

    A real run never proceeds without a fresh backup set created by this
    function itself. This makes the backup precondition deterministic.
    """
    supervision_db=Path(supervision_db or sup_ctx.db_path())
    details_db=Path(details_db or details_store.DETAILS_DB)
    admin_db=Path(admin_db or sup_ctx.admin_db_path())
    plan=retention_plan(as_of,supervision_db,details_db,admin_db)
    if archive_dir is not None:plan["archive_dir"]=str(Path(archive_dir))
    if backup_dir is not None:plan["backup_dir"]=str(Path(backup_dir))
    mode="DRY_RUN" if dry_run else "EXECUTE"
    if not dry_run and sqlite3.postgres_enabled():
        # The historical destructive retention flow creates SQLite online
        # backups.  Those are not authoritative after a PostgreSQL migration.
        # Refuse destructive purge rather than claiming a rollback point that
        # does not contain the live PostgreSQL data.  Dry-run remains available;
        # backups are handled by SAUVEGARDER_POSTGRESQL.bat / pg_dump.
        raise RuntimeError(
            "Rétention destructive temporairement bloquée en mode PostgreSQL : "
            "utilisez le dry-run et SAUVEGARDER_POSTGRESQL.bat. Aucun purge n'a été effectué."
        )
    run_id=_save_run(admin_db,mode,"RUNNING",actor,{"plan":plan})
    summary={"mode":mode,"policy_version":POLICY_VERSION,"plan":plan,"archives":[],"purged":[],"expired_archives":[],"backup":None}
    if dry_run:
        summary["eligible_months"]=[x for x in plan["items"] if not x["held"]]
        summary["held_months"]=[x for x in plan["items"] if x["held"]]
        _save_run(admin_db,mode,"OK",actor,summary,run_id=run_id)
        return summary
    if not plan.get("enabled"):
        error="La rétention destructive est désactivée (retention_enabled=0). Utilisez le dry-run ou activez-la explicitement dans Administration."
        summary["error"]=error
        _save_run(admin_db,mode,"BLOCKED",actor,summary,error=error,run_id=run_id)
        raise RuntimeError(error)
    archive_root,backup_root=_validate_storage_roots(Path(plan["archive_dir"]),Path(plan["backup_dir"]),(supervision_db,details_db,admin_db))
    try:
        with _retention_lock(Path(admin_db).parent / "logs"):
            # Sync Details before any active rows can disappear.
            if supervision_db.is_file():
                try:details_store.sync_from_sources(supervision_db,admin_db,sup_ctx.tech_labels(),force=True)
                except Exception as exc:raise RuntimeError(f"Synchronisation Détails impossible avant purge: {exc}") from exc
                # The sync can add old rows to Nelyio_Details.db. Recompute the
                # plan so a destructive run never purges an old source month
                # while overlooking its newly synchronized Details rows.
                plan=retention_plan(plan["as_of"],supervision_db,details_db,admin_db)
                if archive_dir is not None:plan["archive_dir"]=str(Path(archive_dir))
                if backup_dir is not None:plan["backup_dir"]=str(Path(backup_dir))
                summary["plan"]=plan
            backup_id,backup_manifest=_create_backup_set(supervision_db,details_db,admin_db,backup_root)
            summary["backup"]=backup_manifest
            sup_con=_connect(supervision_db) if supervision_db.is_file() else None
            det_con=_connect(details_db) if details_db.is_file() else None
            admin_con=_connect(admin_db) if admin_db.is_file() else None
            try:
                if sup_con:ensure_supervision_retention_schema(sup_con);sup_con.commit()
                for item in plan["items"]:
                    if item["held"]:continue
                    month=date.fromisoformat(item["month"]+"-01")
                    year=f"{month.year:04d}";mon=f"{month.month:02d}"
                    # The source DB is locked for writing before the archive
                    # snapshot/count verification starts. Concurrent imports can
                    # therefore never slip between verification and deletion.
                    if sup_con and item["supervision"]:
                        dest=archive_root/year/mon/f"Nelyio_Supervision_{item['month']}.sqlite"
                        sup_con.execute("BEGIN IMMEDIATE")
                        try:
                            sup_manifest=_archive_supervision_month(sup_con,month,item["supervision"],dest,backup_id)
                            agg=_purge_supervision_month(sup_con,month,item["supervision"],dest)
                            sup_con.commit()
                            sup_manifest=_mark_archive_purged(dest)
                            summary["archives"].append({"path":str(dest),"manifest":sup_manifest})
                            summary["purged"].append({"month":item["month"],"database":"supervision","counts":item["supervision"],"aggregate":agg})
                        except Exception:
                            sup_con.rollback();raise
                    if det_con and item["details"]:
                        dest=archive_root/year/mon/f"Nelyio_Details_{item['month']}.sqlite"
                        det_con.execute("BEGIN IMMEDIATE")
                        try:
                            det_manifest=_archive_details_month(det_con,month,item["details"],dest,backup_id)
                            _purge_details_month(det_con,month,item["details"]);det_con.commit()
                            det_manifest=_mark_archive_purged(dest)
                            summary["archives"].append({"path":str(dest),"manifest":det_manifest})
                            summary["purged"].append({"month":item["month"],"database":"details","counts":item["details"]})
                        except Exception:
                            det_con.rollback();raise
                    if admin_con and item.get("admin"):
                        dest=archive_root/year/mon/f"Nelyio_AdminAudit_{item['month']}.sqlite"
                        admin_con.execute("BEGIN IMMEDIATE")
                        try:
                            admin_manifest=_archive_admin_month(admin_con,month,item["admin"],dest,backup_id)
                            _purge_admin_month(admin_con,month,item["admin"]);admin_con.commit()
                            admin_manifest=_mark_archive_purged(dest)
                            summary["archives"].append({"path":str(dest),"manifest":admin_manifest})
                            summary["purged"].append({"month":item["month"],"database":"admin_security","counts":item["admin"]})
                        except Exception:
                            admin_con.rollback();raise
                if sup_con:
                    aggregate_cutoff=date.fromisoformat(plan["cutoffs"]["aggregate"])
                    _expire_aggregates(sup_con,aggregate_cutoff);sup_con.commit()
            finally:
                if sup_con:sup_con.close()
                if det_con:det_con.close()
                if admin_con:admin_con.close()
            summary["expired_archives"]=_expire_archives(archive_root,date.fromisoformat(plan["cutoffs"]["archive"]),plan["holds"],False)
        _save_run(admin_db,mode,"OK",actor,summary,run_id=run_id)
        return summary
    except Exception as exc:
        summary["error"]=str(exc)
        _save_run(admin_db,mode,"ERROR",actor,summary,error=str(exc),run_id=run_id)
        raise
