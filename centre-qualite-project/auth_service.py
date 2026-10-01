import hashlib
import hmac
import secrets

import app_config as cfg

ACCESS_MODULES = cfg.ACCESS_MODULES
ACCESS_INTERFACES = cfg.ACCESS_INTERFACES
ACCESS_NONE = cfg.ACCESS_NONE
ACCESS_READ = cfg.ACCESS_READ
ACCESS_WRITE = cfg.ACCESS_WRITE
PBKDF2_ROUNDS = cfg.PBKDF2_ROUNDS
ADMIN_PASSWORD_FILE = cfg.ADMIN_PASSWORD_FILE

def _legacy_permissions(role):
    """Compatibilité pour un ancien compte pas encore affecté à un groupe d'accès."""
    if role == "admin":
        return {key: ACCESS_WRITE for key in ACCESS_MODULES}
    if role == "technician":
        return {
            "dashboard": ACCESS_READ, "inventory": ACCESS_WRITE, "support": ACCESS_WRITE,
            "analytics": ACCESS_READ, "details": ACCESS_READ, "calls": ACCESS_WRITE, "ani": ACCESS_READ, "config": ACCESS_NONE, "classification": ACCESS_NONE,
            "policies": ACCESS_NONE, "declarations": ACCESS_WRITE, "users": ACCESS_NONE, "security": ACCESS_NONE,
        }
    return {
        "dashboard": ACCESS_READ, "inventory": ACCESS_READ, "support": ACCESS_READ,
        "analytics": ACCESS_READ, "details": ACCESS_READ, "calls": ACCESS_READ, "ani": ACCESS_READ, "config": ACCESS_NONE, "classification": ACCESS_NONE,
        "policies": ACCESS_NONE, "declarations": ACCESS_READ, "users": ACCESS_NONE, "security": ACCESS_NONE,
    }

def access_profile(con, user_id, role):
    role = "technician" if role == "user" else str(role or "viewer")
    if role == "admin":
        return {
            "group_id": None, "group_name": "Administrateur système",
            "permissions": {key: ACCESS_WRITE for key in ACCESS_MODULES},
            "interface_permissions": {key: ACCESS_WRITE for key in ACCESS_INTERFACES},
            "group_scope": {
                "mode": "ALL", "allowed_group_ids": [], "default_group_id": "",
                "filter_locked": False, "all_groups": True,
            },
        }
    row = con.execute("""
        SELECT g.id,g.name FROM access_group_members m
        JOIN access_groups g ON g.id=m.group_id WHERE m.user_id=?
    """, (user_id,)).fetchone()
    if not row:
        return {
            "group_id": None, "group_name": "Non affecté",
            "permissions": {key: ACCESS_NONE for key in ACCESS_MODULES},
            "interface_permissions": {key: ACCESS_NONE for key in ACCESS_INTERFACES},
            "group_scope": {
                "mode": "SELECTED", "allowed_group_ids": [], "default_group_id": "",
                "filter_locked": True, "all_groups": False,
            },
        }
    perms = {key: ACCESS_NONE for key in ACCESS_MODULES}
    for r in con.execute("SELECT module,access_level FROM access_group_permissions WHERE group_id=?", (row["id"],)):
        if r["module"] in perms:
            perms[r["module"]] = max(ACCESS_NONE, min(ACCESS_WRITE, int(r["access_level"] or 0)))
    interface_perms = {key: ACCESS_NONE for key in ACCESS_INTERFACES}
    seen = False
    for r in con.execute("SELECT interface_key,access_level FROM access_group_interface_permissions WHERE group_id=?", (row["id"],)):
        if r["interface_key"] in interface_perms:
            seen = True
            interface_perms[r["interface_key"]] = max(ACCESS_NONE, min(ACCESS_WRITE, int(r["access_level"] or 0)))
    if not seen:
        for key, meta in ACCESS_INTERFACES.items():
            level = int(perms.get(meta.get("module"), ACCESS_NONE))
            if meta.get("write_only"):
                level = ACCESS_WRITE if level >= ACCESS_WRITE else ACCESS_NONE
            elif not meta.get("write") and level > ACCESS_READ:
                level = ACCESS_READ
            interface_perms[key] = level
    policy = con.execute(
        "SELECT scope_mode,default_business_group_id,filter_locked FROM access_group_scope_policy WHERE group_id=?",
        (row["id"],),
    ).fetchone()
    allowed = [str(r[0]) for r in con.execute(
        "SELECT business_group_id FROM access_group_scopes WHERE access_group_id=? ORDER BY business_group_id",
        (row["id"],),
    ).fetchall()]
    mode = str(policy["scope_mode"] if policy else "ALL").upper()
    if mode not in {"ALL", "SELECTED"}:
        mode = "ALL"
    default_gid = str(policy["default_business_group_id"] or "") if policy else ""
    locked = bool(int(policy["filter_locked"] or 0)) if policy else False
    return {
        "group_id": row["id"], "group_name": row["name"], "permissions": perms,
        "interface_permissions": interface_perms,
        "group_scope": {
            "mode": mode, "allowed_group_ids": allowed, "default_group_id": default_gid,
            "filter_locked": locked, "all_groups": mode == "ALL",
        },
    }

def user_has_access(user, module, write=False):
    if not user or module not in ACCESS_MODULES:
        return False
    if user.get("role") == "admin":
        return True
    needed = ACCESS_WRITE if write else ACCESS_READ
    try:
        return int((user.get("permissions") or {}).get(module, ACCESS_NONE)) >= needed
    except Exception:
        return False

def password_hash(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return salt.hex(), digest.hex()

def verify_password(password, salt_hex, hash_hex):
    try:
        _, candidate = password_hash(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(candidate, hash_hex)
    except Exception:
        return False

def bootstrap_admin():
    from app_db import db_connect
    with db_connect() as con:
        count = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            return
        password = secrets.token_urlsafe(12) + "!"
        salt, ph = password_hash(password)
        con.execute("INSERT INTO users(username,password_salt,password_hash,role,created_by) VALUES(?,?,?,?,?)",
                    ("admin", salt, ph, "admin", "SYSTEM"))
        con.execute("INSERT INTO auth_audit(username,action,details) VALUES(?,?,?)",
                    ("admin", "BOOTSTRAP_ADMIN", "Compte administrateur initial créé localement"))
        con.commit()
        ADMIN_PASSWORD_FILE.write_text(
            "Nelyio - Compte initial local\n"
            "======================================\n\n"
            "Utilisateur : admin\n"
            f"Mot de passe temporaire : {password}\n\n"
            "Connectez-vous puis changez ce mot de passe depuis Mon compte.\n",
            encoding="utf-8"
        )
        try:
            ADMIN_PASSWORD_FILE.chmod(0o600)
        except OSError:
            pass  # Windows ACLs remain the responsibility of the local administrator.
        print("\n=== PREMIER DEMARRAGE ===")
        print("Utilisateur : admin")
        print("Mot de passe temporaire : consultez le fichier local INITIAL_ADMIN.txt.")
        print(f"Une copie est disponible dans : {ADMIN_PASSWORD_FILE.name}\n")

def user_has_interface(user, interface_key, write=False):
    if not user or interface_key not in ACCESS_INTERFACES:
        return False
    if user.get("role") == "admin":
        return True
    needed = ACCESS_WRITE if write else ACCESS_READ
    try:
        level = int((user.get("interface_permissions") or {}).get(interface_key, ACCESS_NONE))
    except Exception:
        level = ACCESS_NONE
    meta = ACCESS_INTERFACES[interface_key]
    if meta.get("write_only") and not write:
        needed = ACCESS_WRITE
    return level >= needed

