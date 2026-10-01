"""Runtime switch for Nelyio's local multi-process service architecture.

The default remains monolithic when app.py is launched directly so existing
operator habits and tests stay compatible. The Windows launcher enables the
external services explicitly with NELYIO_EXTERNAL_SERVICES=1.
"""
from __future__ import annotations

import os

_TRUE = {'1', 'true', 'yes', 'on'}


def external_services_enabled() -> bool:
    return os.environ.get('NELYIO_EXTERNAL_SERVICES', '0').strip().lower() in _TRUE


def service_poll_seconds(name: str, default: float) -> float:
    key = 'NELYIO_' + str(name).upper().replace('-', '_') + '_POLL_SECONDS'
    try:
        value = float(os.environ.get(key, str(default)))
    except ValueError:
        return float(default)
    return max(0.2, min(60.0, value))
