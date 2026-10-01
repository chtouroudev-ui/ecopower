import csv
import io
import re
import db_compat as sqlite3
from datetime import datetime

from app_db import db_connect, now_text
from classification import normalize_user_key
from inventory_service import rows_to_dict

CONDITIONS = {"NEUF", "ANCIEN", "KO"}
DIRECTIONS = {"ENTREE", "SORTIE"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _bool(value, default=True):
    if value is None:
        return bool(default)
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "off", "non", "no"}
    return bool(value)


def _clean_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if not DATE_RE.fullmatch(text):
        raise ValueError("Date invalide")
    datetime.strptime(text, "%Y-%m-%d")
    return text


class ConsumablesRoutesMixin:
    def _consumable_items(self, con, include_inactive=True):
        where = "" if include_inactive else "WHERE c.active=1"
        return rows_to_dict(con.execute(f"""
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN b.condition='NEUF' THEN b.quantity ELSE 0 END),0) qty_new,
                   COALESCE(SUM(CASE WHEN b.condition='ANCIEN' THEN b.quantity ELSE 0 END),0) qty_old,
                   COALESCE(SUM(CASE WHEN b.condition='KO' THEN b.quantity ELSE 0 END),0) qty_ko,
                   COALESCE(SUM(b.quantity),0) qty_total
            FROM consumables c
            LEFT JOIN consumable_balances b ON b.consumable_id=c.id
            {where}
            GROUP BY c.id
            ORDER BY c.active DESC,c.name COLLATE NOCASE
        """).fetchall())

    def api_consumables(self, qs):
        q = str(qs.get("q", [""])[0] or "").strip()
        direction = str(qs.get("direction", [""])[0] or "").strip().upper()
        condition = str(qs.get("condition", [""])[0] or "").strip().upper()
        item_id = str(qs.get("item_id", [""])[0] or "").strip()
        try:
            date_from = _clean_date(qs.get("date_from", [""])[0])
            date_to = _clean_date(qs.get("date_to", [""])[0])
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        if date_from and date_to and date_to < date_from:
            return self.send_json({"error": "La date de fin doit être après la date de début"}, 400)

        clauses, params = [], []
        if q:
            like = f"%{q}%"
            clauses.append("(c.name LIKE ? OR c.category LIKE ? OR m.beneficiary_identifier LIKE ? OR m.beneficiary_name LIKE ? OR m.comment LIKE ? OR m.username LIKE ?)")
            params += [like] * 6
        if direction in DIRECTIONS:
            clauses.append("m.direction=?")
            params.append(direction)
        if condition in CONDITIONS:
            clauses.append("m.condition=?")
            params.append(condition)
        if item_id.isdigit():
            clauses.append("m.consumable_id=?")
            params.append(int(item_id))
        if date_from:
            clauses.append("date(m.created_at)>=date(?)")
            params.append(date_from)
        if date_to:
            clauses.append("date(m.created_at)<=date(?)")
            params.append(date_to)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""

        with db_connect() as con:
            items = self._consumable_items(con, include_inactive=True)
            movements = rows_to_dict(con.execute(f"""
                SELECT m.*,c.name item_name,c.unit,c.category
                FROM consumable_movements m JOIN consumables c ON c.id=m.consumable_id
                {where}
                ORDER BY datetime(m.created_at) DESC,m.id DESC
                LIMIT 1000
            """, params).fetchall())
            directory = rows_to_dict(con.execute("""
                SELECT d.user_key,d.user_identifier,d.first_name,d.last_name,COALESCE(g.name,'') group_name,
                       COALESCE(NULLIF(TRIM(COALESCE(d.first_name,'') || ' ' || COALESCE(d.last_name,'')),''),d.user_identifier) display_name
                FROM user_directory d
                LEFT JOIN user_group_members gm ON gm.user_key=d.user_key
                LEFT JOIN user_groups g ON g.id=gm.group_id
                ORDER BY display_name COLLATE NOCASE
            """).fetchall())
        active = [x for x in items if x["active"]]
        low = [x for x in active if int(x["qty_total"] or 0) <= int(x["min_quantity"] or 0)]
        self.send_json({
            "items": items,
            "movements": movements,
            "directory": directory,
            "stats": {
                "active_items": len(active),
                "total_units": sum(int(x["qty_total"] or 0) for x in active),
                "low_stock": len(low),
                "ko_units": sum(int(x["qty_ko"] or 0) for x in active),
            },
            "conditions": ["NEUF", "ANCIEN", "KO"],
        })

    def api_consumable_item(self, user):
        data = self.read_json() or {}
        name = " ".join(str(data.get("name", "") or "").split()).strip()[:100]
        category = " ".join(str(data.get("category", "") or "").split()).strip()[:80]
        unit = " ".join(str(data.get("unit", "unité") or "unité").split()).strip()[:30] or "unité"
        try:
            min_quantity = max(0, min(1_000_000, int(data.get("min_quantity", 0) or 0)))
        except Exception:
            return self.send_json({"error": "Seuil minimum invalide"}, 400)
        if not name:
            return self.send_json({"error": "Nom du consommable requis"}, 400)
        item_raw = str(data.get("id", "") or "").strip()
        item_id = int(item_raw) if item_raw.isdigit() else 0
        active = 1 if _bool(data.get("active", True), True) else 0
        try:
            with db_connect() as con:
                if item_id:
                    row = con.execute("SELECT * FROM consumables WHERE id=?", (item_id,)).fetchone()
                    if not row:
                        return self.send_json({"error": "Consommable introuvable"}, 404)
                    con.execute("UPDATE consumables SET name=?,category=?,unit=?,min_quantity=?,active=?,updated_at=?,updated_by=? WHERE id=?",
                                (name, category, unit, min_quantity, active, now_text(), user["username"], item_id))
                    action = "CONSUMABLE_UPDATED"
                else:
                    con.execute("INSERT INTO consumables(name,category,unit,min_quantity,active,created_by,updated_by) VALUES(?,?,?,?,?,?,?)",
                                (name, category, unit, min_quantity, active, user["username"], user["username"]))
                    item_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
                    for cond in sorted(CONDITIONS):
                        con.execute("INSERT OR IGNORE INTO consumable_balances(consumable_id,condition,quantity) VALUES(?,?,0)", (item_id, cond))
                    action = "CONSUMABLE_CREATED"
                con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                            (user["username"], action, f"#{item_id} {name}", self.client_ip()))
                con.commit()
        except sqlite3.IntegrityError:
            return self.send_json({"error": "Un consommable porte déjà ce nom"}, 409)
        self.send_json({"ok": True, "id": item_id}, 201 if not item_raw else 200)

    def api_consumable_toggle(self, user):
        data = self.read_json() or {}
        try:
            item_id = int(data.get("id"))
        except Exception:
            return self.send_json({"error": "Consommable invalide"}, 400)
        with db_connect() as con:
            row = con.execute("SELECT id,name,active FROM consumables WHERE id=?", (item_id,)).fetchone()
            if not row:
                return self.send_json({"error": "Consommable introuvable"}, 404)
            active = 0 if row["active"] else 1
            con.execute("UPDATE consumables SET active=?,updated_at=?,updated_by=? WHERE id=?", (active, now_text(), user["username"], item_id))
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "CONSUMABLE_TOGGLED", f"#{item_id} {row['name']} active={active}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "active": active})

    def api_consumable_movement(self, user):
        data = self.read_json() or {}
        try:
            item_id = int(data.get("consumable_id"))
            quantity = int(data.get("quantity"))
        except Exception:
            return self.send_json({"error": "Consommable ou quantité invalide"}, 400)
        if quantity <= 0 or quantity > 1_000_000:
            return self.send_json({"error": "La quantité doit être positive"}, 400)
        direction = str(data.get("direction", "") or "").strip().upper()
        condition = str(data.get("condition", "") or "").strip().upper()
        if direction not in DIRECTIONS:
            return self.send_json({"error": "Type de mouvement invalide"}, 400)
        if condition not in CONDITIONS:
            return self.send_json({"error": "État du consommable invalide"}, 400)
        beneficiary = str(data.get("beneficiary", "") or "").strip()[:120]
        comment = str(data.get("comment", "") or "").strip()[:1000]
        beneficiary_key = normalize_user_key(beneficiary) if beneficiary else ""
        beneficiary_identifier = beneficiary
        beneficiary_name = beneficiary
        with db_connect() as con:
            con.execute("BEGIN IMMEDIATE")
            item = con.execute("SELECT id,name,active FROM consumables WHERE id=?", (item_id,)).fetchone()
            if not item:
                con.rollback()
                return self.send_json({"error": "Consommable introuvable"}, 404)
            if not item["active"]:
                con.rollback()
                return self.send_json({"error": "Ce consommable est désactivé"}, 409)
            con.execute("INSERT OR IGNORE INTO consumable_balances(consumable_id,condition,quantity) VALUES(?,?,0)", (item_id, condition))
            balance = con.execute("SELECT quantity FROM consumable_balances WHERE consumable_id=? AND condition=?", (item_id, condition)).fetchone()[0]
            if direction == "SORTIE" and quantity > int(balance):
                con.rollback()
                return self.send_json({"error": f"Stock insuffisant : {balance} disponible(s) en état {condition.lower()}"}, 409)
            if beneficiary_key:
                d = con.execute("SELECT user_identifier,first_name,last_name FROM user_directory WHERE user_key=?", (beneficiary_key,)).fetchone()
                if d:
                    beneficiary_identifier = d["user_identifier"]
                    beneficiary_name = (f"{d['first_name']} {d['last_name']}").strip() or d["user_identifier"]
            delta = quantity if direction == "ENTREE" else -quantity
            con.execute("UPDATE consumable_balances SET quantity=quantity+?,updated_at=? WHERE consumable_id=? AND condition=?",
                        (delta, now_text(), item_id, condition))
            con.execute("""
                INSERT INTO consumable_movements(consumable_id,direction,condition,quantity,beneficiary_key,beneficiary_identifier,beneficiary_name,comment,username,source_ip)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (item_id, direction, condition, quantity, beneficiary_key, beneficiary_identifier, beneficiary_name, comment, user["username"], self.client_ip()))
            movement_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.execute("INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)",
                        (user["username"], "CONSUMABLE_MOVEMENT", f"#{movement_id} {direction} {quantity} {condition} {item['name']} -> {beneficiary_name or '-'}", self.client_ip()))
            con.commit()
        self.send_json({"ok": True, "movement_id": movement_id}, 201)

    def api_consumables_export(self, qs):
        # Reuse the same filters as the UI, without mutating anything.
        q = str(qs.get("q", [""])[0] or "").strip()
        direction = str(qs.get("direction", [""])[0] or "").strip().upper()
        condition = str(qs.get("condition", [""])[0] or "").strip().upper()
        try:
            date_from = _clean_date(qs.get("date_from", [""])[0])
            date_to = _clean_date(qs.get("date_to", [""])[0])
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)
        clauses, params = [], []
        if q:
            like=f"%{q}%"; clauses.append("(c.name LIKE ? OR m.beneficiary_name LIKE ? OR m.comment LIKE ?)"); params += [like]*3
        if direction in DIRECTIONS: clauses.append("m.direction=?"); params.append(direction)
        if condition in CONDITIONS: clauses.append("m.condition=?"); params.append(condition)
        if date_from: clauses.append("date(m.created_at)>=date(?)"); params.append(date_from)
        if date_to: clauses.append("date(m.created_at)<=date(?)"); params.append(date_to)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with db_connect() as con:
            rows = rows_to_dict(con.execute(f"""
                SELECT m.created_at,c.name,c.category,c.unit,m.direction,m.condition,m.quantity,
                       m.beneficiary_identifier,m.beneficiary_name,m.comment,m.username,m.source_ip
                FROM consumable_movements m JOIN consumables c ON c.id=m.consumable_id
                {where} ORDER BY datetime(m.created_at) DESC,m.id DESC
            """, params).fetchall())
        out = io.StringIO(); w = csv.writer(out, delimiter=';')
        w.writerow(['Date','Consommable','Catégorie','Unité','Mouvement','État','Quantité','Bénéficiaire ID','Bénéficiaire','Commentaire','Saisi par','IP source'])
        for r in rows:
            w.writerow([r['created_at'],r['name'],r['category'],r['unit'],r['direction'],r['condition'],r['quantity'],r['beneficiary_identifier'],r['beneficiary_name'],r['comment'],r['username'],r['source_ip']])
        self.send_bytes(out.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8', extra={'Content-Disposition':'attachment; filename=NELYIO_consommables_historique.csv'})
