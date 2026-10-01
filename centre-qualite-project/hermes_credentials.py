"""Windows-DPAPI storage for Hermes supervision credentials.

The encrypted blob is bound to the Windows account running Nelyio. Secrets are
never returned by status helpers and are decrypted only in-memory for the
short-lived Hermes login worker.
"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import getpass
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
SECRET_DIR = ROOT / "data" / "secrets"
CREDENTIAL_FILE = SECRET_DIR / "hermes_credentials.dpapi"
GUARD_FILE = SECRET_DIR / "hermes_login_guard.json"
VERSION = 1
ENTROPY = b"Nelyio/HermesSupervision/v1"
CRYPTPROTECT_UI_FORBIDDEN = 0x1
COOLDOWN_SECONDS = 15 * 60


class CredentialError(RuntimeError):
    pass


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    raw = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(raw, ctypes.POINTER(ctypes.c_byte))), raw


def _protect_windows(data: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialError("Le chiffrement DPAPI est disponible uniquement sous Windows.")
    crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    in_blob, in_raw = _blob(data)
    entropy_blob, entropy_raw = _blob(ENTROPY)
    out_blob = DATA_BLOB()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Nelyio Hermes supervision",
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    # Keep backing buffers alive until the call returns.
    _ = (in_raw, entropy_raw)
    if not ok:
        raise CredentialError(f"DPAPI CryptProtectData a echoue (code {ctypes.get_last_error()}).")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(ctypes.cast(out_blob.pbData, ctypes.c_void_p))


def _unprotect_windows(data: bytes) -> bytes:
    if os.name != "nt":
        raise CredentialError("Le dechiffrement DPAPI est disponible uniquement sous Windows.")
    crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    in_blob, in_raw = _blob(data)
    entropy_blob, entropy_raw = _blob(ENTROPY)
    out_blob = DATA_BLOB()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    _ = (in_raw, entropy_raw)
    if not ok:
        raise CredentialError(
            "DPAPI ne peut pas dechiffrer les identifiants Hermes avec le compte Windows courant."
        )
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(ctypes.cast(out_blob.pbData, ctypes.c_void_p))


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _read_document() -> dict:
    if not CREDENTIAL_FILE.exists():
        return {}
    try:
        doc = json.loads(CREDENTIAL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise CredentialError("Le fichier d'identifiants Hermes est illisible.") from exc
    if not isinstance(doc, dict) or int(doc.get("version") or 0) != VERSION:
        raise CredentialError("Version du coffre Hermes non prise en charge.")
    return doc


def save_credentials(username: str, password: str, *, auto_login: bool = True) -> dict:
    if not isinstance(auto_login, bool):
        raise ValueError("Valeur auto-login invalide.")
    username = str(username or "").strip()
    password = str(password or "")
    if not username or len(username) > 256 or "\x00" in username:
        raise ValueError("Identifiant Hermes invalide.")
    if not password or len(password) > 1024 or "\x00" in password:
        raise ValueError("Mot de passe Hermes invalide.")
    plaintext = json.dumps({"username": username, "password": password}, ensure_ascii=False).encode("utf-8")
    encrypted = _protect_windows(plaintext)
    doc = {
        "version": VERSION,
        "scope": "windows-current-user",
        "auto_login": bool(auto_login),
        "created_at": int(time.time()),
        "blob": base64.b64encode(encrypted).decode("ascii"),
    }
    _atomic_write(CREDENTIAL_FILE, json.dumps(doc, separators=(",", ":")))
    clear_login_guard()
    return status(check_decrypt=True)


def load_credentials() -> dict:
    doc = _read_document()
    encoded = str(doc.get("blob") or "")
    if not encoded:
        raise CredentialError("Aucun identifiant Hermes configure.")
    try:
        encrypted = base64.b64decode(encoded, validate=True)
        raw = _unprotect_windows(encrypted)
        payload = json.loads(raw.decode("utf-8"))
    except CredentialError:
        raise
    except Exception as exc:
        raise CredentialError("Les identifiants Hermes chiffres sont invalides.") from exc
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    if not username or not password:
        raise CredentialError("Les identifiants Hermes chiffres sont incomplets.")
    return {"username": username, "password": password, "auto_login": bool(doc.get("auto_login", True))}


def set_auto_login(enabled: bool) -> dict:
    if not isinstance(enabled, bool):
        raise ValueError("Valeur auto-login invalide.")
    doc = _read_document()
    if not doc:
        raise CredentialError("Configurez d'abord les identifiants Hermes.")
    doc["auto_login"] = bool(enabled)
    _atomic_write(CREDENTIAL_FILE, json.dumps(doc, separators=(",", ":")))
    if enabled:
        clear_login_guard()
    return status(check_decrypt=False)


def delete_credentials() -> dict:
    try:
        CREDENTIAL_FILE.unlink(missing_ok=True)
    finally:
        clear_login_guard()
    return status(check_decrypt=False)


def status(*, check_decrypt: bool = False) -> dict:
    configured = CREDENTIAL_FILE.exists()
    result = {
        "supported": os.name == "nt",
        "configured": configured,
        "auto_login": False,
        "storage": "Windows DPAPI - compte utilisateur courant",
        "windows_account": getpass.getuser(),
        "decryptable": None,
    }
    if not configured:
        return result
    try:
        doc = _read_document()
        result["auto_login"] = bool(doc.get("auto_login", True))
        if check_decrypt:
            load_credentials()
            result["decryptable"] = True
    except CredentialError:
        if check_decrypt:
            result["decryptable"] = False
    guard = login_guard_status()
    result.update({
        "cooldown_active": guard["blocked"],
        "cooldown_until": guard.get("blocked_until"),
        "last_login_error": guard.get("reason") or "",
    })
    return result


def login_guard_status(*, clock: float | None = None) -> dict:
    now = float(time.time() if clock is None else clock)
    try:
        doc = json.loads(GUARD_FILE.read_text(encoding="utf-8")) if GUARD_FILE.exists() else {}
    except (OSError, ValueError, TypeError):
        doc = {}
    until = float(doc.get("blocked_until") or 0)
    return {
        "blocked": until > now,
        "blocked_until": int(until) if until else None,
        "reason": str(doc.get("reason") or "")[:300],
        "failed_at": int(float(doc.get("failed_at") or 0)) if doc.get("failed_at") else None,
    }


def record_login_failure(reason: str, *, clock: float | None = None) -> None:
    now = float(time.time() if clock is None else clock)
    _atomic_write(GUARD_FILE, json.dumps({
        "failed_at": int(now),
        "blocked_until": int(now + COOLDOWN_SECONDS),
        "reason": str(reason or "Echec authentification Hermes")[:300],
    }, separators=(",", ":")))


def clear_login_guard() -> None:
    try:
        GUARD_FILE.unlink(missing_ok=True)
    except OSError:
        pass
