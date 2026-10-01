"""Filesystem stop flags for graceful Nelyio process shutdown on Windows.

Windows ``Stop-Process`` terminates Python abruptly, so worker ``finally``
blocks (especially the Live publisher) are not guaranteed to run.  The launcher
creates a per-service flag; each process polls it and exits through its normal
cleanup path.  A force kill remains a bounded last resort in the PowerShell
stop scripts.
"""
from __future__ import annotations

from pathlib import Path

RUN = Path(__file__).resolve().parent / "run"


def _path(name: str) -> Path:
    clean = "".join(ch for ch in str(name) if ch.isalnum() or ch in "_-")
    if not clean:
        raise ValueError("service name required")
    return RUN / (clean + ".stop")


def clear_stop(name: str) -> None:
    try:
        _path(name).unlink(missing_ok=True)
    except OSError:
        pass


def stop_requested(name: str) -> bool:
    try:
        return _path(name).is_file()
    except OSError:
        return False
