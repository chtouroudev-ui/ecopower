"""CRUD, validation and audit for Phase D declarations."""
from datetime import datetime, timedelta
import json

from app_db import db_connect
from declaration_engine import DECLARATION_TYPES, declaration_actions, declaration_snapshot


def _text(v, n=600):
    return str(v or "").strip()[:n]


def _parse_date(v):
    text = _text(v, 10)
    if not text:
        raise ValueError("Date requise")
    return datetime.strptime(text, "%Y-%m-%d")


def _parse_time(v, label):
    text = _text(v, 5)
    if not text:
        raise ValueError(f"{label} requise")
    return datetime.strptime(text, "%H:%M").time()


def validate_declaration(data):
    typ = _text(data.get("declaration_type") or "AUTRE", 40).upper().replace(" ", "_")
    if typ not in DECLARATION_TYPES:
        typ = "AUTRE"
    day = _parse_date(data.get("date"))
    start_time = _parse_time(data.get("start_time"), "Heure de début")
    start = datetime.combine(day.date(), start_time)

    duration_raw = str(data.get("duration_minutes") or "").strip()
    end_raw = _text(data.get("end_time"), 5)
    if duration_raw:
        try:
            duration = int(duration_raw)
        except ValueError:
            raise ValueError("Durée invalide")
        if duration < 1 or duration > 1440:
            raise ValueError("La durée doit être comprise entre 1 minute et 24 heures")
        end = start + timedelta(minutes=duration)
    elif end_raw:
        end_time = _parse_time(end_raw, "Heure de fin")
        end = datetime.combine(day.date(), end_time)
        if end <= start:
            end += timedelta(days=1)
        duration = int((end - start).total_seconds() // 60)
        if duration < 1 or duration > 1440:
            raise ValueError("La déclaration doit durer entre 1 minute et 24 heures")
    else:
        raise ValueError("Renseigner une heure de fin ou une durée")

    targets = []
    raw_targets = data.get("targets") if isinstance(data.get("targets"), list) else []
    for t in raw_targets:
        if not isinstance(t, dict):
            continue
        target_type = _text(t.get("target_type"), 10).upper()
        target_key = _text(t.get("target_key"), 120)
        if target_type not in ("AGENT", "GROUP") or not target_key:
            continue
        item = {"target_type": target_type, "target_key": target_key}
        if item not in targets:
            targets.append(item)
    if not targets:
        raise ValueError("Choisir au moins un agent ou un groupe")
    kinds = {t["target_type"] for t in targets}
    if len(kinds) > 1:
        raise ValueError("Une déclaration doit cibler des agents ou des groupes, pas les deux en même temps")

    return {
        "declaration_type": typ,
        "status": "ACTIVE",
        "start_at": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end_at": end.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_minutes": duration,
        "comment": _text(data.get("comment"), 1000),
        "actions": declaration_actions(typ),
        "targets": targets,
    }


def _snapshot_one(con, declaration_id):
    row = con.execute("SELECT * FROM nelyio_declarations WHERE id=?", (int(declaration_id),)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["actions"] = json.loads(d.pop("action_json") or "{}")
    except Exception:
        d["actions"] = {}
    d["targets"] = [dict(r) for r in con.execute(
        "SELECT target_type,target_key FROM nelyio_declaration_targets WHERE declaration_id=? ORDER BY id",
        (int(declaration_id),),
    )]
    start = datetime.strptime(d["start_at"], "%Y-%m-%d %H:%M:%S")
    end = datetime.strptime(d["end_at"], "%Y-%m-%d %H:%M:%S")
    d["duration_minutes"] = int((end - start).total_seconds() // 60)
    d["date"] = start.strftime("%Y-%m-%d")
    d["start_time"] = start.strftime("%H:%M")
    d["end_time"] = end.strftime("%H:%M")
    return d


def save_declaration(data, actor):
    clean = validate_declaration(data)
    declaration_id = data.get("id")
    try:
        declaration_id = int(declaration_id) if declaration_id not in (None, "") else None
    except Exception:
        raise ValueError("Déclaration invalide")
    with db_connect() as con:
        old = _snapshot_one(con, declaration_id) if declaration_id else None
        if declaration_id and not old:
            raise LookupError("Déclaration introuvable")
        if declaration_id and old.get("deleted_at"):
            raise ValueError("Cette déclaration est supprimée")
        if declaration_id and old.get("status") == "CANCELLED":
            raise ValueError("Une déclaration annulée ne peut plus être modifiée")
        action_json = json.dumps(clean["actions"], ensure_ascii=False, separators=(",", ":"))
        if declaration_id:
            con.execute(
                """UPDATE nelyio_declarations SET declaration_type=?,status='ACTIVE',start_at=?,end_at=?,action_json=?,comment=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (clean["declaration_type"], clean["start_at"], clean["end_at"], action_json, clean["comment"], actor, declaration_id),
            )
            con.execute("DELETE FROM nelyio_declaration_targets WHERE declaration_id=?", (declaration_id,))
            action = "UPDATED"
        else:
            cur = con.execute(
                """INSERT INTO nelyio_declarations(declaration_type,status,start_at,end_at,action_json,comment,created_by,updated_by) VALUES(?,'ACTIVE',?,?,?,?,?,?)""",
                (clean["declaration_type"], clean["start_at"], clean["end_at"], action_json, clean["comment"], actor, actor),
            )
            declaration_id = int(cur.lastrowid)
            action = "CREATED"
        for target in clean["targets"]:
            con.execute(
                "INSERT INTO nelyio_declaration_targets(declaration_id,target_type,target_key) VALUES(?,?,?)",
                (declaration_id, target["target_type"], target["target_key"]),
            )
        new = _snapshot_one(con, declaration_id)
        con.execute(
            "INSERT INTO nelyio_declaration_audit(declaration_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)",
            (declaration_id, action, json.dumps(old or {}, ensure_ascii=False), json.dumps(new or {}, ensure_ascii=False), actor),
        )
        con.execute(
            "INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)",
            (actor, "NELYIO_DECLARATION_" + action, f"{declaration_id}: {clean['declaration_type']} {clean['start_at']} -> {clean['end_at']}"),
        )
        con.commit()
        return new


def cancel_declaration(declaration_id, actor):
    with db_connect() as con:
        old = _snapshot_one(con, int(declaration_id))
        if not old:
            raise LookupError("Déclaration introuvable")
        if old.get("deleted_at"):
            raise ValueError("Déclaration supprimée")
        if old.get("status") == "CANCELLED":
            return old
        con.execute(
            "UPDATE nelyio_declarations SET status='CANCELLED',cancelled_by=?,cancelled_at=CURRENT_TIMESTAMP,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (actor, actor, int(declaration_id)),
        )
        new = _snapshot_one(con, int(declaration_id))
        con.execute(
            "INSERT INTO nelyio_declaration_audit(declaration_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)",
            (int(declaration_id), "CANCELLED", json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False), actor),
        )
        con.execute("INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)", (actor, "NELYIO_DECLARATION_CANCELLED", str(declaration_id)))
        con.commit()
        return new


def delete_declaration(declaration_id, actor):
    with db_connect() as con:
        old = _snapshot_one(con, int(declaration_id))
        if not old:
            raise LookupError("Déclaration introuvable")
        if old.get("deleted_at"):
            return
        con.execute(
            "UPDATE nelyio_declarations SET status='CANCELLED',deleted_at=CURRENT_TIMESTAMP,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (actor, int(declaration_id)),
        )
        con.execute(
            "INSERT INTO nelyio_declaration_audit(declaration_id,action,old_json,new_json,actor) VALUES(?,?,?,?,?)",
            (int(declaration_id), "DELETED", json.dumps(old, ensure_ascii=False), "{}", actor),
        )
        con.execute("INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)", (actor, "NELYIO_DECLARATION_DELETED", str(declaration_id)))
        con.commit()


def list_audit(declaration_id=None, limit=200):
    with db_connect() as con:
        if declaration_id is None:
            rows = con.execute("SELECT * FROM nelyio_declaration_audit ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM nelyio_declaration_audit WHERE declaration_id=? ORDER BY id DESC LIMIT ?",
                (int(declaration_id), int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]
