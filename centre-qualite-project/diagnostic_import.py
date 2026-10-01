from pathlib import Path
import os
import re
import db_compat as sqlite3

import app_config as cfg
from app_db import db_connect, get_setting, now_text, set_setting

DIAG_FIELDS = cfg.DIAG_FIELDS

def normalize_diagnostic_path(source_path):
    """Normalize a diagnostic DB path, including legacy file:// UNC values."""
    path = str(source_path or "").strip().strip('\"')
    if not path:
        return ""

    low = path.lower()
    if low.startswith("file://"):
        from urllib.parse import urlsplit, unquote
        parts = urlsplit(path)
        if parts.netloc and parts.netloc.lower() != "localhost":
            unc_tail = unquote(parts.path).lstrip("/").replace("/", "\\")
            return "\\\\" + parts.netloc + "\\" + unc_tail
        local_path = unquote(parts.path)
        if re.match(r"^/[A-Za-z]:/", local_path):
            local_path = local_path[1:]
        return local_path.replace("/", os.sep)

    if low.startswith("file:"):
        from urllib.parse import urlsplit, unquote
        parts = urlsplit(path)
        local_path = unquote(parts.path)
        if re.match(r"^/[A-Za-z]:/", local_path):
            local_path = local_path[1:]
        return local_path.replace("/", os.sep)

    return path

def open_sqlite_readonly(source_path, timeout=5):
    """Open diagnostic source for SELECT-only access.

    Local files use SQLite mode=ro. Windows UNC paths are opened as native
    filenames because standard SQLite builds reject file://SERVER authorities.
    PRAGMA query_only prevents writes from this connection.
    """
    path = normalize_diagnostic_path(source_path)
    if not path:
        raise ValueError("Chemin de la base diagnostic non configuré")

    if path.startswith("\\\\"):
        con = sqlite3.connect(path, timeout=timeout)
    else:
        abs_path = os.path.abspath(path)
        uri = Path(abs_path).as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=timeout)

    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con

def source_schema_info(source_path):
    path = normalize_diagnostic_path(source_path)
    if not path:
        raise ValueError("Chemin de la base diagnostic non configuré")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Base introuvable : {path}")
    try:
        if os.path.samefile(path, cfg.APP_DB):
            raise ValueError("La base source ne peut pas être la base centrale de l'application")
    except FileNotFoundError:
        pass
    con = open_sqlite_readonly(path, timeout=5)
    try:
        table = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='diagnostic'").fetchone()
        if not table:
            raise ValueError("La table 'diagnostic' est absente de cette base")
        columns = [r[1] for r in con.execute("PRAGMA table_info(diagnostic)").fetchall()]
        missing = [c for c in ("event_uuid", "date_evenement", "ordinateur") if c not in columns]
        if missing:
            raise ValueError("Colonnes obligatoires absentes : " + ", ".join(missing))
        count = con.execute("SELECT COUNT(*) FROM diagnostic").fetchone()[0]
        latest = con.execute("SELECT MAX(date_evenement) FROM diagnostic").fetchone()[0]
        max_id = con.execute("SELECT MAX(id) FROM diagnostic").fetchone()[0] if "id" in columns else None
        return {"path": path, "columns": columns, "rows": count, "latest": latest, "max_id": max_id}
    finally:
        con.close()

def import_diagnostic_source(source_path, actor="SYSTEM"):
    started = now_text()
    path = normalize_diagnostic_path(source_path)
    with db_connect() as con:
        cur = con.execute("INSERT INTO import_log(source_path,actor,started_at,status) VALUES(?,?,?,'RUNNING')",
                          (path, actor, started))
        batch_id = cur.lastrowid
        con.commit()
    try:
        info = source_schema_info(path)
        available = set(info["columns"])
        has_source_id = "id" in available
        last_source_id = 0
        if has_source_id:
            with db_connect() as state_con:
                state = state_con.execute("SELECT last_source_id FROM import_sources WHERE path=?", (path,)).fetchone()
                last_source_id = int(state[0]) if state else 0
            if info.get("max_id") is not None and int(info["max_id"] or 0) < last_source_id:
                last_source_id = 0

        src = open_sqlite_readonly(path, timeout=5)
        try:
            select_cols = ["id"] if has_source_id else []
            select_cols += [c for c in DIAG_FIELDS if c in available]
            if has_source_id:
                rows = src.execute("SELECT " + ",".join(select_cols) + " FROM diagnostic WHERE id>? ORDER BY id", (last_source_id,)).fetchall()
            else:
                rows = src.execute("SELECT " + ",".join(select_cols) + " FROM diagnostic").fetchall()
        finally:
            src.close()

        imported = 0
        skipped = 0
        with db_connect() as con:
            con.execute("BEGIN")
            for row in rows:
                d = dict(row)
                values = [d.get(c) for c in DIAG_FIELDS]
                if not d.get("event_uuid") or not d.get("date_evenement"):
                    skipped += 1
                    continue
                cur = con.execute("""
                    INSERT OR IGNORE INTO diagnostic(
                        event_uuid,date_evenement,action,utilisateur,ordinateur,adresse_ip,passerelle,adresse_mac,
                        sn_pc,sn_carte_mere,domaine,fabricant,modele,windows,version_windows,collecteur,version_script,
                        date_import,source_path,source_row_id,import_batch_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, tuple(values + [path, d.get("id"), batch_id]))
                if cur.rowcount == 1:
                    imported += 1
                else:
                    skipped += 1
            finished = now_text()
            con.execute("""
                UPDATE import_log SET finished_at=?,source_rows=?,imported_rows=?,skipped_rows=?,status='OK',error=''
                WHERE id=?
            """, (finished, len(rows), imported, skipped, batch_id))
            if has_source_id:
                con.execute("""
                    INSERT INTO import_sources(path,last_source_id,last_source_rows,last_seen_at,last_imported_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(path) DO UPDATE SET
                        last_source_id=excluded.last_source_id,last_source_rows=excluded.last_source_rows,
                        last_seen_at=excluded.last_seen_at,last_imported_at=excluded.last_imported_at
                """, (path, int(info.get("max_id") or last_source_id), int(info.get("rows") or 0), finished, finished))
            set_setting(con, "last_import_at", finished, actor)
            set_setting(con, "last_import_count", imported, actor)
            set_setting(con, "last_import_error", "", actor)
            con.commit()
        return {"ok": True, "source_rows": int(info.get("rows") or 0), "scanned_rows": len(rows),
                "imported_rows": imported, "skipped_rows": skipped, "latest": info["latest"],
                "finished_at": finished, "batch_id": batch_id}
    except Exception as exc:
        finished = now_text()
        with db_connect() as con:
            con.execute("UPDATE import_log SET finished_at=?,status='ERROR',error=? WHERE id=?",
                        (finished, str(exc)[:1000], batch_id))
            set_setting(con, "last_import_error", str(exc)[:1000], actor)
            con.commit()
        raise

def migrate_legacy_once():
    if get_setting("legacy_migration_done", "0") == "1":
        return
    messages = []
    try:
        if cfg.LEGACY_DIAG_DB.exists() and cfg.LEGACY_DIAG_DB.resolve() != cfg.APP_DB.resolve():
            r = import_diagnostic_source(str(cfg.LEGACY_DIAG_DB), "MIGRATION_V4")
            messages.append(f"diagnostic.db: {r['imported_rows']} diagnostic(s) importé(s)")
    except Exception as exc:
        messages.append(f"diagnostic.db ignoré: {exc}")

    if cfg.LEGACY_STOCK_DB.exists():
        try:
            src = sqlite3.connect(cfg.LEGACY_STOCK_DB)
            src.row_factory = sqlite3.Row
            with db_connect() as con:
                if src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_management'").fetchone():
                    rows = src.execute("SELECT * FROM asset_management").fetchall()
                    cols = [r[1] for r in src.execute("PRAGMA table_info(asset_management)").fetchall()]
                    target_cols = [c for c in cols if c in {"ordinateur","asset_tag","statut","affectation","emplacement_attendu","notes","manual_utilisateur","manual_ip","manual_mac","manual_sn_pc","manual_sn_carte_mere","manual_domaine","manual_fabricant","manual_modele","manual_windows","manual_version_windows","created_manually","created_by","created_at","updated_by","updated_at"}]
                    for row in rows:
                        d = dict(row)
                        vals = [d.get(c) for c in target_cols]
                        placeholders = ",".join("?" for _ in target_cols)
                        updates = ",".join(f"{c}=excluded.{c}" for c in target_cols if c != "ordinateur")
                        con.execute(f"INSERT INTO asset_management({','.join(target_cols)}) VALUES({placeholders}) ON CONFLICT(ordinateur) DO UPDATE SET {updates}", vals)
                if src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='manual_audit'").fetchone():
                    for row in src.execute("SELECT ordinateur,action,field_name,old_value,new_value,username,user_id,created_at FROM manual_audit"):
                        con.execute("INSERT INTO manual_audit(ordinateur,action,field_name,old_value,new_value,username,user_id,created_at) VALUES(?,?,?,?,?,?,?,?)", tuple(row))
                con.commit()
            src.close()
            messages.append("stock.db migré")
        except Exception as exc:
            messages.append(f"stock.db ignoré: {exc}")

    if cfg.LEGACY_AUTH_DB.exists():
        try:
            src = sqlite3.connect(cfg.LEGACY_AUTH_DB)
            src.row_factory = sqlite3.Row
            with db_connect() as con:
                if src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                    for row in src.execute("SELECT username,password_salt,password_hash,role,active,created_at,created_by,last_login_at,password_changed_at FROM users"):
                        con.execute("""
                            INSERT OR IGNORE INTO users(username,password_salt,password_hash,role,active,created_at,created_by,last_login_at,password_changed_at)
                            VALUES(?,?,?,?,?,?,?,?,?)
                        """, tuple(row))
                if src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_audit'").fetchone():
                    for row in src.execute("SELECT username,action,details,created_at FROM auth_audit"):
                        con.execute("INSERT INTO auth_audit(username,action,details,created_at) VALUES(?,?,?,?)", tuple(row))
                con.commit()
            src.close()
            messages.append("auth.db migré")
        except Exception as exc:
            messages.append(f"auth.db ignoré: {exc}")

    with db_connect() as con:
        set_setting(con, "legacy_migration_done", "1", "SYSTEM")
        set_setting(con, "legacy_migration_note", " | ".join(messages), "SYSTEM")
        con.commit()
    if messages:
        print("Migration v4 : " + " | ".join(messages))
