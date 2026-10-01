"""Tiny cross-process lock files for short Nelyio coordination points.

This complements SQLite WAL. It is not a data lock: it prevents the Live
publisher and the heavy Import pipeline from competing for the same Support
writer window across separate Python processes.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
import uuid

BASE = Path(__file__).resolve().parent
RUN = BASE / 'run'


class LockBusy(RuntimeError):
    pass


def _windows_alive(pid):
    # os.kill(pid, 0) terminates processes on Windows. Query a handle instead.
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
    if not handle:
        # Only ERROR_INVALID_PARAMETER proves that this PID no longer exists.
        # Access denied/unknown must never cause a live lock to be deleted.
        return ctypes.get_last_error() != 87
    try:
        return kernel.WaitForSingleObject(handle, 0) != 0
    finally:
        kernel.CloseHandle(handle)


def _alive(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        if os.name == 'nt':
            return _windows_alive(pid)
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except OSError:
        return True  # unknown status: preserve the lock


def _try_cleanup(path: Path, stale_after: float):
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        age = time.time() - float(raw.get('created_at') or 0)
        alive = _alive(raw.get('pid'))
        if (not alive and age >= 2.0) or (not alive and age >= stale_after):
            path.unlink(missing_ok=True)
            return True
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        try:
            if time.time() - path.stat().st_mtime >= stale_after:
                path.unlink(missing_ok=True)
                return True
        except OSError:
            pass
    return False


@contextmanager
def named_lock(name: str, timeout: float = 0.0, poll: float = 0.05, stale_after: float = 21600.0):
    RUN.mkdir(parents=True, exist_ok=True)
    safe = ''.join(ch for ch in str(name) if ch.isalnum() or ch in ('-', '_'))
    if not safe:
        raise ValueError('Nom de verrou invalide.')
    path = RUN / (safe + '.lock')
    token = uuid.uuid4().hex
    deadline = time.monotonic() + max(0.0, float(timeout))
    payload = json.dumps({'pid': os.getpid(), 'token': token, 'created_at': time.time()})
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, payload.encode('utf-8'))
                os.fsync(fd)
            finally:
                os.close(fd)
            break
        except FileExistsError:
            _try_cleanup(path, stale_after)
            if time.monotonic() >= deadline:
                raise LockBusy('Verrou inter-processus occupé : ' + safe)
            time.sleep(max(0.01, min(0.25, poll)))
    try:
        yield path
    finally:
        try:
            current = json.loads(path.read_text(encoding='utf-8'))
            if current.get('token') == token:
                path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
