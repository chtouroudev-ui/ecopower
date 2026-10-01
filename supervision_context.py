"""Runtime paths shared by the modular supervision package.

The compatibility facade ``supervision.py`` keeps DB/ADMIN_DB/IMPORT_DIR public.
These helpers resolve those values dynamically so existing launchers/tests that
replace ``supervision.DB`` continue to work after the implementation split.
"""
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
DEFAULT_DB = BASE / 'NELYIO_Supervision.db'
DEFAULT_ADMIN_DB = BASE / 'TECHIN_Stock_Manager.db'
DEFAULT_IMPORT_DIR = BASE / 'import'


def facade_attr(name, default):
    facade = sys.modules.get('supervision')
    return getattr(facade, name, default) if facade is not None else default


def db_path():
    return Path(facade_attr('DB', DEFAULT_DB))


def admin_db_path():
    return Path(facade_attr('ADMIN_DB', DEFAULT_ADMIN_DB))


def import_dir_path():
    return Path(facade_attr('IMPORT_DIR', DEFAULT_IMPORT_DIR))


def tech_labels():
    value = facade_attr('TECH_LABELS', {})
    return value if isinstance(value, dict) else {}


def set_facade_attr(name, value):
    facade = sys.modules.get('supervision')
    if facade is not None:
        setattr(facade, name, value)
    return value
